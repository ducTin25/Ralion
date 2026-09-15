"""Hàm gọi judge model THẬT để tính từng metric — xem docs/PM/evaluation/plan-evaluation.md mục 5.

Tách khỏi eval_prompts.py (thuần, không mạng) để phần build-prompt/parse-response test được không
cần key/API thật; module này chỉ điều phối lời gọi, không tự bịa logic tính điểm.
"""

from __future__ import annotations

import asyncio
import logging

from scripts import eval_prompts
from src.observability.tracing import get_langchain_callbacks

logger = logging.getLogger("eval_plan_content")

# Bằng chứng thật từ Groq dashboard (console.groq.com/dashboard/logs): request bị 429 có
# INPUT/OUTPUT TOKENS = 0 và LATENCY ≈ 0 — bị từ chối NGAY, chưa xử lý gì — và luôn xảy ra khi 2+
# request tới CÙNG LÚC (cùng giây); request cách nhau vài chục giây đều 200 OK. Tức là tier free
# giới hạn SỐ REQUEST ĐỒNG THỜI (có vẻ chỉ chịu 1 lúc), không phải token/phút như header ghi —
# 2 lời gọi song song vẫn đủ để va nhau. Đặt 1 để đảm bảo tuần tự tuyệt đối.
MAX_CONCURRENT_JUDGE_CALLS = 1


# Đo thật lúc pilot: Groq free tier 429 CHỚP NHOÁNG dù header báo còn dư token/request (vd 3 lời
# gọi liên tiếp cỡ vài chục token: 429, 200, 429) — không phải hết ngân sách token/phút như tài
# liệu Groq mô tả, giống hơn 1 giới hạn tốc độ (rate) ngầm không công bố ở tier free. Giãn cách cố
# định là cách đơn giản nhất giảm khả năng đụng giới hạn đó khi không đọc được con số thật.
_PACE_SECONDS = 1.5


async def _ask(llm, prompt: str) -> str:
    response = await llm.ainvoke(
        [("user", prompt)], config={"callbacks": get_langchain_callbacks()}
    )
    await asyncio.sleep(_PACE_SECONDS)
    return str(response.content)


async def extract_claims(llm, text: str) -> list[str]:
    if not text.strip():
        return []
    response_text = await _ask(llm, eval_prompts.build_extract_claims_prompt(text))
    return eval_prompts.parse_claims_response(response_text)


def _chunked(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


async def _batch_check_supported(llm, claims: list[str], source_text: str) -> list[bool]:
    """1 lời gọi/lô (≤ MAX_ITEMS_PER_JUDGE_BATCH claim) thay vì 1 lời gọi/claim — xem
    eval_prompts.MAX_ITEMS_PER_JUDGE_BATCH vì sao cần gộp (trần token/phút của Groq, đo thật lúc
    chạy pilot: case COMPANY 70 chunk tự nó vượt trần nếu bắn 1-lời-gọi-1-item)."""
    batches = _chunked(claims, eval_prompts.MAX_ITEMS_PER_JUDGE_BATCH)

    async def run_batch(batch: list[str]) -> list[bool]:
        response_text = await _ask(
            llm, eval_prompts.build_batch_supported_check_prompt(batch, source_text)
        )
        return eval_prompts.parse_batch_yes_no(response_text, len(batch))

    results = await _bounded_gather((run_batch(b) for b in batches), MAX_CONCURRENT_JUDGE_CALLS)
    return [value for batch_result in results for value in batch_result]


async def _batch_check_relevant(llm, chunks: list[str], task_objective: str) -> list[bool]:
    batches = _chunked(chunks, eval_prompts.MAX_ITEMS_PER_JUDGE_BATCH)

    async def run_batch(batch: list[str]) -> list[bool]:
        response_text = await _ask(
            llm, eval_prompts.build_batch_relevance_check_prompt(batch, task_objective)
        )
        return eval_prompts.parse_batch_yes_no(response_text, len(batch))

    results = await _bounded_gather((run_batch(b) for b in batches), MAX_CONCURRENT_JUDGE_CALLS)
    return [value for batch_result in results for value in batch_result]


async def _bounded_gather(coros, limit: int):
    semaphore = asyncio.Semaphore(limit)

    async def run(coro):
        async with semaphore:
            return await coro

    return await asyncio.gather(*(run(c) for c in coros))


async def faithfulness(llm, ai_content: str, source_text: str) -> float | None:
    """§5.1 — tỉ lệ claim (tách từ nội dung AI sinh) được chính đoạn tài liệu nguồn xác nhận.
    `None` nếu nội dung không tách được claim nào (case NO_HIT_NOTICE — không có gì để chấm)."""
    claims = await extract_claims(llm, ai_content)
    if not claims:
        return None
    results = await _batch_check_supported(llm, claims, source_text)
    return sum(results) / len(results)


async def context_recall(llm, reference_content: str, retrieved_text: str) -> float | None:
    """§5.2 — bao nhiêu ý trong bản chuẩn được tìm thấy trong đoạn tài liệu ĐÃ THỰC SỰ lấy ra
    dùng. Cần `reference_content` — chỉ tính được cho case có bản chuẩn (mục 4 của plan)."""
    reference_claims = await extract_claims(llm, reference_content)
    if not reference_claims:
        return None
    results = await _batch_check_supported(llm, reference_claims, retrieved_text)
    return sum(results) / len(results)


async def context_precision(llm, chunks_used: list[str], task_objective: str) -> float | None:
    """§5.3 — bao nhiêu đoạn trong số đã lấy thực sự liên quan tới mục tiêu task."""
    if not chunks_used:
        return None
    results = await _batch_check_relevant(llm, chunks_used, task_objective)
    return sum(results) / len(results)


async def judge_score(
    llm, ai_content: str, *, reference_content: str | None, task_objective: str
) -> dict | None:
    """§5.4 — rubric 1-5, reference-based nếu có bản chuẩn, ngược lại chấm tuyệt đối (mục 4). Trả
    `None` nếu judge không trả JSON hợp lệ sau khi thử — người gọi tự quyết định retry/bỏ case."""
    prompt = (
        eval_prompts.build_judge_prompt_with_reference(reference_content, ai_content)
        if reference_content
        else eval_prompts.build_judge_prompt_no_reference(ai_content, task_objective)
    )
    response_text = await _ask(llm, prompt)
    parsed = eval_prompts.parse_judge_response(response_text)
    if parsed is None:
        logger.warning("eval_plan_content: judge trả JSON không hợp lệ, bỏ qua lần chấm này")
    return parsed
