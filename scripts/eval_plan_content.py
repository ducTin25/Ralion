"""Chạy Evaluation cho bước sinh nội dung Onboarding Plan bằng AI.

Gọi ĐÚNG pipeline thật (steps.py + content_llm.generate_ai_content, model sinh: deepseek-chat) —
KHÔNG mô phỏng lại logic 3 pha, đúng yêu cầu mục 2 của plan. So với Baseline B0
(generate_baseline_content, deterministic). Chấm điểm bằng judge model Groq (openai/gpt-oss-120b) —
khác hẳn model sinh, tránh self-preference bias (Day 14).

Xem docs/PM/evaluation/plan-evaluation.md cho toàn bộ thiết kế, và
docs/PM/report-evaluation.md cho danh sách hàm/hướng dẫn sử dụng chi tiết.

Cách chạy:
    python scripts/eval_plan_content.py --pilot 3          # chạy thử 3 case đầu, 1 lần/case
    python scripts/eval_plan_content.py                    # chạy đủ golden set, 3 lần/case AI
    python scripts/eval_plan_content.py --runs 3 --out docs/PM/Phase-4/eval-report.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from scripts import eval_metrics, eval_prompts, eval_stats  # noqa: E402
from src.model.project import Project  # noqa: E402
from src.model.session import AsyncSessionLocal  # noqa: E402
from src.services.llm import get_judge_llm  # noqa: E402
from src.services.plan_generation import content_llm, steps  # noqa: E402
from src.services.plan_generation.tools import fetch_all_document_chunks  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("eval_plan_content")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "docs" / "PM" / "Phase-4" / "eval-golden-dataset.jsonl"
DEFAULT_REPORT = ROOT / "docs" / "PM" / "Phase-4" / "eval-report.md"

# Groq free tier trần 8000 token/phút (đo thật lúc pilot — xem docs/PM/report-evaluation.md mục 7).
# Nội dung tài liệu nguồn gửi cho JUDGE bị cắt ngắn ở đây — KHÔNG ảnh hưởng tới nội dung tài liệu
# đưa cho model SINH nội dung (content_llm.py dùng MAX_CHUNK_CHARS=1200 riêng, không đổi). Đây là
# giới hạn CHỈ áp dụng cho bước chấm điểm, làm giảm độ chính xác của Faithfulness/Recall/Precision
# với case có nhiều tài liệu (đặc biệt COMPANY, tới 70 chunk) — đánh đổi có chủ đích để chạy được
# trên Groq free tier, ghi rõ trong eval-report.md, không âm thầm.
MAX_CHUNK_CHARS_FOR_JUDGE = 500
MAX_TOTAL_CHUNK_CHARS_FOR_JUDGE = 6000


def _cap_chunks_for_judge(chunk_texts: list[str]) -> list[str]:
    capped = []
    total = 0
    for text in chunk_texts:
        piece = text[:MAX_CHUNK_CHARS_FOR_JUDGE]
        if total + len(piece) > MAX_TOTAL_CHUNK_CHARS_FOR_JUDGE:
            break
        capped.append(piece)
        total += len(piece)
    return capped


@dataclass
class GoldenCase:
    case_id: str
    template_task_id: int
    task_category: str
    project_key: str
    reference_content: str | None
    expected_source_chunks: list[str]
    difficulty: str
    created_by: str | None
    reviewed_by: str | None
    version: str


@dataclass
class CaseResult:
    case: GoldenCase
    task_objective: str
    retrieved_text: str
    chunks_used: list[str]
    baseline_content: str
    ai_contents: list[str] = field(default_factory=list)
    ai_faithfulness: list[float] = field(default_factory=list)
    ai_judge_mean: list[float] = field(default_factory=list)
    ai_judge_detail: list[dict] = field(default_factory=list)
    baseline_faithfulness: float | None = None
    baseline_judge_mean: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    error: str | None = None
    # Khác `error`: nội dung ĐÃ sinh được (pha 1 xong), chỉ việc CHẤM ĐIỂM (pha 2, gọi Groq) bị lỗi
    # giữa chừng — case này vẫn xuất hiện trong bảng chính với phần metric đã chấm được, không bị
    # loại như `error` (dành cho case không sinh được nội dung).
    scoring_note: str | None = None


def load_golden_dataset(path: Path) -> list[GoldenCase]:
    cases = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            cases.append(GoldenCase(**row))
    return cases


async def _build_project_context(db, project_key: str) -> steps.GenerationContext:
    project = (await db.execute(select(Project).where(Project.key == project_key))).scalar_one()
    context = await steps.load_template_for_project(db, project.project_id)
    context = await steps.merge_company_core(db, context)
    context = await steps.collect_project_docs(db, context)
    context = steps.map_task_sources(context)
    return context


async def run_eval(
    dataset_path: Path, *, runs: int, pilot: int | None, out_path: Path
) -> None:
    cases = load_golden_dataset(dataset_path)
    if pilot is not None:
        cases = cases[:pilot]
    logger.info("eval_plan_content: %s case, %s lần chạy AI/case", len(cases), runs)

    judge_llm = get_judge_llm()
    started = time.perf_counter()

    by_project: dict[str, list[GoldenCase]] = defaultdict(list)
    for case in cases:
        by_project[case.project_key].append(case)

    results: dict[str, CaseResult] = {}

    async with AsyncSessionLocal() as db:
        for project_key, project_cases in by_project.items():
            logger.info("eval_plan_content: dự án %s — %s case", project_key, len(project_cases))
            context = await _build_project_context(db, project_key)
            task_input_by_id = {
                ti.template_task.template_task_id: ti for ti in context.task_inputs
            }

            baseline_contents = content_llm.generate_baseline_content(context)

            ai_runs: list[dict[int, content_llm.TaskContent]] = []
            for run_index in range(runs):
                logger.info(
                    "eval_plan_content: %s — lần chạy AI #%s/%s", project_key, run_index + 1, runs
                )
                ai_runs.append(
                    await content_llm.generate_ai_content(db, context, project_key)
                )

            chunks_by_version: dict[int, list] = {}
            for case in project_cases:
                task_input = task_input_by_id.get(case.template_task_id)
                if task_input is None:
                    results[case.case_id] = CaseResult(
                        case=case,
                        task_objective="",
                        retrieved_text="",
                        chunks_used=[],
                        baseline_content="",
                        error=f"template_task_id {case.template_task_id} không có trong template hiện tại",
                    )
                    continue

                chunk_texts: list[str] = []
                for doc in task_input.allowed_documents:
                    if doc.version_id not in chunks_by_version:
                        chunks_by_version[doc.version_id] = await fetch_all_document_chunks(
                            db, version_id=doc.version_id
                        )
                    chunk_texts.extend(c.content for c in chunks_by_version[doc.version_id])
                chunks_for_judge = _cap_chunks_for_judge(chunk_texts)
                retrieved_text = "\n\n".join(chunks_for_judge)
                task_objective = task_input.template_task.objective

                baseline_content = baseline_contents[case.template_task_id].instruction
                ai_contents = [
                    ai_runs[i][case.template_task_id].instruction for i in range(runs)
                ]

                results[case.case_id] = CaseResult(
                    case=case,
                    task_objective=task_objective,
                    retrieved_text=retrieved_text,
                    chunks_used=chunks_for_judge,
                    baseline_content=baseline_content,
                    ai_contents=ai_contents,
                )

    # Pha 2: tính metric bằng judge (Groq) — tách khỏi pha 1 (đọc DB + sinh nội dung) để lỗi judge
    # không làm mất dữ liệu đã sinh, và để dễ theo dõi tiến độ 2 pha riêng.
    for i, case in enumerate(cases):
        result = results[case.case_id]
        if result.error:
            continue
        logger.info("eval_plan_content: chấm case %s/%s (%s)", i + 1, len(cases), case.case_id)
        try:
            await _score_case(judge_llm, case, result)
        except Exception as exc:  # noqa: BLE001 - 1 case lỗi (vd Groq hết retry) không được làm
            # mất kết quả đã chấm được của MỌI case khác — hạ cấp có kiểm soát, giữ nguyên phần
            # metric đã tính được của case này (partial), chỉ đánh dấu để báo cáo biết mà đọc lại.
            logger.warning(
                "eval_plan_content: chấm case %s lỗi (%s) — giữ phần đã chấm được, bỏ phần còn lại",
                case.case_id,
                type(exc).__name__,
            )
            result.scoring_note = f"Chấm điểm dở dang ({type(exc).__name__}): {exc}"

    elapsed = time.perf_counter() - started
    logger.info("eval_plan_content: xong toàn bộ, %.1f giây", elapsed)

    write_report(list(results.values()), out_path, elapsed_seconds=elapsed, runs=runs)


async def _score_case(judge_llm, case: GoldenCase, result: CaseResult) -> None:
    if result.chunks_used:
        result.context_precision = await eval_metrics.context_precision(
            judge_llm, result.chunks_used, result.task_objective
        )
    if case.reference_content:
        result.context_recall = await eval_metrics.context_recall(
            judge_llm, case.reference_content, result.retrieved_text
        )

    for ai_content in result.ai_contents:
        faith = await eval_metrics.faithfulness(judge_llm, ai_content, result.retrieved_text)
        if faith is not None:
            result.ai_faithfulness.append(faith)
        judged = await eval_metrics.judge_score(
            judge_llm,
            ai_content,
            reference_content=case.reference_content,
            task_objective=result.task_objective,
        )
        if judged is not None:
            result.ai_judge_detail.append(judged)
            result.ai_judge_mean.append(eval_prompts.judge_mean_score(judged))

    result.baseline_faithfulness = await eval_metrics.faithfulness(
        judge_llm, result.baseline_content, result.retrieved_text
    )
    baseline_judged = await eval_metrics.judge_score(
        judge_llm,
        result.baseline_content,
        reference_content=case.reference_content,
        task_objective=result.task_objective,
    )
    if baseline_judged is not None:
        result.baseline_judge_mean = eval_prompts.judge_mean_score(baseline_judged)


def _fmt(value: float | None, *, digits: int = 2) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def write_report(
    results: list[CaseResult], out_path: Path, *, elapsed_seconds: float, runs: int
) -> None:
    ok_results = [r for r in results if r.error is None]
    error_results = [r for r in results if r.error is not None]

    by_category: dict[str, list[CaseResult]] = defaultdict(list)
    for r in ok_results:
        by_category[r.case.task_category].append(r)

    lines: list[str] = []
    lines.append("# Eval Report — Sinh nội dung Onboarding Plan bằng AI vs Baseline B0")
    lines.append("")
    lines.append(
        f"> Sinh tự động bởi `scripts/eval_plan_content.py`, KHÔNG viết tay. "
        f"{len(ok_results)}/{len(results)} case chạy thành công, {runs} lần/case cho nhánh AI, "
        f"tổng thời gian {elapsed_seconds:.1f}s. Xem "
        f"`docs/PM/evaluation/plan-evaluation.md` cho thiết kế đầy đủ, "
        f"`docs/PM/report-evaluation.md` cho hướng dẫn đọc report này."
    )
    lines.append("")

    if error_results:
        lines.append("## Case lỗi (không sinh được)")
        lines.append("")
        lines.append("| case_id | Lỗi |")
        lines.append("|---|---|")
        for r in error_results:
            lines.append(f"| {r.case.case_id} | {r.error} |")
        lines.append("")

    scoring_note_results = [r for r in ok_results if r.scoring_note]
    if scoring_note_results:
        lines.append(
            "## Case chấm điểm dở dang (nội dung đã sinh xong, judge lỗi giữa chừng — vẫn có mặt "
            "trong bảng chính bên dưới với phần metric đã chấm được)"
        )
        lines.append("")
        lines.append("| case_id | Ghi chú |")
        lines.append("|---|---|")
        for r in scoring_note_results:
            lines.append(f"| {r.case.case_id} | {r.scoring_note} |")
        lines.append("")

    # ---- Tổng hợp theo category ----
    lines.append("## 1. RAGAS scores + Judge scores theo category")
    lines.append("")
    lines.append(
        "| Category | N case | Faithfulness AI (mean±std) | Faithfulness B0 | Context Precision | "
        "Context Recall (N có reference) | Judge AI (mean±std) | Judge B0 | % AI thắng B0 |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for category in sorted(by_category):
        rs = by_category[category]
        all_faith_ai = [f for r in rs for f in r.ai_faithfulness]
        all_faith_b0 = [r.baseline_faithfulness for r in rs if r.baseline_faithfulness is not None]
        all_precision = [r.context_precision for r in rs if r.context_precision is not None]
        recall_vals = [r.context_recall for r in rs if r.context_recall is not None]
        all_judge_ai = [j for r in rs for j in r.ai_judge_mean]
        all_judge_b0 = [r.baseline_judge_mean for r in rs if r.baseline_judge_mean is not None]

        ai_case_means = [
            eval_stats.mean_std(r.ai_judge_mean)[0] for r in rs if r.ai_judge_mean
        ]
        b0_case_means = [
            r.baseline_judge_mean
            for r in rs
            if r.baseline_judge_mean is not None and r.ai_judge_mean
        ]
        win = (
            eval_stats.win_rate(ai_case_means, b0_case_means)
            if len(ai_case_means) == len(b0_case_means) and ai_case_means
            else None
        )

        faith_ai_mean, faith_ai_std = eval_stats.mean_std(all_faith_ai) if all_faith_ai else (None, None)
        judge_ai_mean, judge_ai_std = eval_stats.mean_std(all_judge_ai) if all_judge_ai else (None, None)

        lines.append(
            f"| {category} | {len(rs)} "
            f"| {_fmt(faith_ai_mean)}±{_fmt(faith_ai_std)} "
            f"| {_fmt(eval_stats.mean_std(all_faith_b0)[0] if all_faith_b0 else None)} "
            f"| {_fmt(eval_stats.mean_std(all_precision)[0] if all_precision else None)} "
            f"| {_fmt(eval_stats.mean_std(recall_vals)[0] if recall_vals else None)} (N={len(recall_vals)}) "
            f"| {_fmt(judge_ai_mean)}±{_fmt(judge_ai_std)} "
            f"| {_fmt(eval_stats.mean_std(all_judge_b0)[0] if all_judge_b0 else None)} "
            f"| {'—' if win is None else f'{win * 100:.0f}%'} |"
        )
    lines.append("")

    # ---- Tổng quan toàn bộ ----
    all_case_ai_means = [eval_stats.mean_std(r.ai_judge_mean)[0] for r in ok_results if r.ai_judge_mean]
    all_case_b0_means = [
        r.baseline_judge_mean for r in ok_results if r.baseline_judge_mean is not None and r.ai_judge_mean
    ]
    overall_win = (
        eval_stats.win_rate(all_case_ai_means, all_case_b0_means)
        if len(all_case_ai_means) == len(all_case_b0_means) and all_case_ai_means
        else None
    )
    lines.append("## 2. Kết luận nhanh")
    lines.append("")
    lines.append(
        f"- Tổng {len(ok_results)} case, **{'—' if overall_win is None else f'{overall_win * 100:.0f}%'}** "
        "case AI được Judge chấm trung bình CAO HƠN Baseline B0."
    )
    lines.append(
        "- Không dùng paired t-test (mẫu nhỏ theo từng category, xem mục 7 plan-evaluation.md) — "
        "đọc bảng trên theo category, không chỉ 1 con số tổng."
    )
    lines.append("")

    # ---- Chi tiết từng case ----
    lines.append("## 3. Chi tiết từng case")
    lines.append("")
    lines.append(
        "| case_id | project | category | difficulty | reference? | Faithfulness AI | "
        "Context Precision | Judge AI | Judge B0 |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in ok_results:
        faith_mean = eval_stats.mean_std(r.ai_faithfulness)[0] if r.ai_faithfulness else None
        judge_mean = eval_stats.mean_std(r.ai_judge_mean)[0] if r.ai_judge_mean else None
        lines.append(
            f"| {r.case.case_id} | {r.case.project_key} | {r.case.task_category} | "
            f"{r.case.difficulty} | {'có' if r.case.reference_content else 'không'} | "
            f"{_fmt(faith_mean)} | {_fmt(r.context_precision)} | {_fmt(judge_mean)} | "
            f"{_fmt(r.baseline_judge_mean)} |"
        )
    lines.append("")

    # ---- Failure analysis ----
    scored = [
        (eval_stats.mean_std(r.ai_judge_mean)[0], r)
        for r in ok_results
        if r.ai_judge_mean
    ]
    scored.sort(key=lambda t: t[0])
    worst = scored[:3]
    lines.append("## 4. Failure analysis — 3 case điểm Judge thấp nhất")
    lines.append("")
    if not worst:
        lines.append("_Không có case nào chấm được điểm Judge (kiểm tra lỗi ở mục case lỗi phía trên)._")
    for score, r in worst:
        lines.append(f"### {r.case.case_id} — {r.case.project_key}/{r.case.task_category} (Judge={score:.2f})")
        lines.append("")
        lines.append(
            "- **5 Whys**: _cần điền tay sau khi đọc lại nội dung AI sinh thật cho case này "
            "(script không tự suy luận nguyên nhân) — xem `ai_judge_detail`/log console lúc chạy._"
        )
        lines.append("- **Failure Taxonomy**: _phân loại tay: Wrong Answer / Hallucination / "
                      "Retrieval Failure / Inconsistent._")
        lines.append("")

    lines.append("## 5. Improvement log")
    lines.append("")
    lines.append("_Điền ≥3 action item sau khi đọc mục 4, ưu tiên theo cluster lớn nhất — xem "
                  "plan-evaluation.md mục 9._")
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("eval_plan_content: đã ghi report -> %s", out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--runs", type=int, default=3, help="Số lần chạy AI/case (temperature=0.2)")
    parser.add_argument("--pilot", type=int, default=None, help="Chỉ chạy N case đầu để thử")
    args = parser.parse_args()
    asyncio.run(run_eval(args.dataset, runs=args.runs, pilot=args.pilot, out_path=args.out))


if __name__ == "__main__":
    main()
