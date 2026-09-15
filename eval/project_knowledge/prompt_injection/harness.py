"""Indirect prompt-injection harness for F5 (injection embedded IN ingested content, not typed
by the user directly -- contrast with project_knowledge/guardrails/, which is direct-user-input
safety).

Setup step (data prep, separate from both the real snapshot and from "ingest"): each case's
`fixture_copy` is a full copy of a real file from demo-data/thanos-io_project-knowledge (the authoritative demo corpus)
with one injected line added -- see `fixture_copies/` for the pre-generated files. Nothing under
demo-data/ is ever modified (checked below, same as --dry-run always did).

Default mode is --dry-run (structure-only). --live does exactly what the original module
docstring said a live run should: (1) loads `fixture_copy`, (2) feeds it through the exact same
persistence path F2 Sub-flow A uses (`src/modules/knowledge/ingestion/versioning.py:ingest_or_update`)
against a THROWAWAY project created just for this one case -- NEVER against the real THANOS
project_id=19 -- then (3) calls `ChatService.ask()` with `user_question` scoped to that throwaway
project and judges the answer against `expected_behavior` with the same LLM judge the guardrails
harness uses (`eval/shared/llm_judge.py`). The throwaway project (and every row it created: chat
session/message/citations, document/version/chunks, membership, plan, the two synthetic users) is
deleted again in a `finally` block after every case, pass or fail.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from eval.shared.report_format import CaseResult, build_report, print_summary, write_report  # noqa: E402

DATASET_PATH = Path(__file__).resolve().parent / "test_cases.jsonl"
REPORT_PATH = Path(__file__).resolve().parent / "report.json"

REQUIRED_FIELDS = (
    "case_id", "source_file", "fixture_copy", "injected_content", "injection_location",
    "user_question", "expected_behavior",
)
VALID_LOCATIONS = {"docstring", "comment", "readme", "commit_message"}


def load_dataset() -> list[dict]:
    with DATASET_PATH.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _validate_case(case: dict) -> str | None:
    missing = [f for f in REQUIRED_FIELDS if f not in case]
    if missing:
        return f"missing fields: {missing}"
    if case["injection_location"] not in VALID_LOCATIONS:
        return f"unknown injection_location {case['injection_location']!r}"

    source_path = REPO_ROOT / case["source_file"]
    if not source_path.is_file():
        return f"source_file not found in demo-data/: {case['source_file']}"

    copy_path = REPO_ROOT / case["fixture_copy"]
    if not copy_path.is_file():
        return f"fixture_copy not found: {case['fixture_copy']}"

    copy_text = copy_path.read_text(encoding="utf-8")
    if case["injected_content"] not in copy_text:
        return "injected_content not actually present in fixture_copy"

    original_text = source_path.read_text(encoding="utf-8")
    if case["injected_content"] in original_text:
        return (
            "injected_content is already present in the untouched demo-data/ source -- fixture "
            "is not adversarial"
        )
    return None


def run_case_dry(case: dict) -> CaseResult:
    error = _validate_case(case)
    if error:
        return CaseResult(case.get("case_id", "?"), "fail", error)
    return CaseResult(
        case["case_id"], "skipped",
        "dry_run: fixture_copy not staged-ingested, ChatService.ask() not called",
    )


async def _stage_throwaway_project(session, case: dict, embedder):
    """Creates project + pm/member users + membership + PROJECT_READY plan + one ingested
    document from `fixture_copy`. Returns the dict of created ids `_cleanup` needs."""
    import uuid as uuid_mod

    from sqlalchemy import select

    from src.model.enums import DocumentCategory, MembershipStatus, PlanStatus, ProjectRole, UserRole, UserStatus
    from src.model.onboarding_plan import OnboardingPlan
    from src.model.project import Project
    from src.model.project_membership import ProjectMembership
    from src.model.template_version import TemplateVersion
    from src.model.user import User
    from src.modules.knowledge.ingestion.versioning import ProjectIngestRequest, ingest_or_update

    unique = uuid_mod.uuid4().hex[:8]
    pm = User(email=f"eval-inj-pm-{unique}@eval.local", display_name="Eval PM", system_role=UserRole.ADMIN, status=UserStatus.ACTIVE)
    member = User(email=f"eval-inj-member-{unique}@eval.local", display_name="Eval Member", status=UserStatus.ACTIVE)
    session.add_all([pm, member])
    await session.flush()

    project = Project(key=f"EVAL-INJ-{unique}", name=f"Eval prompt-injection throwaway ({case['case_id']})", created_by_admin_id=pm.user_id)
    session.add(project)
    await session.flush()

    membership = ProjectMembership(
        project_id=project.project_id, user_id=member.user_id,
        project_role=ProjectRole.ENGINEER, status=MembershipStatus.ACTIVE,
        assigned_by_admin_id=pm.user_id,
    )
    session.add(membership)
    await session.flush()

    # PROJECT_READY unlocks every DocumentCategory in _phase_categories() -- see
    # eval/shared/live_chat.py's ensure_plan_ready docstring for why this matters.
    # template_version_id is NOT NULL on onboarding_plans but otherwise irrelevant to this
    # eval (only .status is read by _phase_categories) -- reuse any existing template version.
    template_version_id = await session.scalar(select(TemplateVersion.version_id).limit(1))
    if template_version_id is None:
        raise RuntimeError("no TemplateVersion row exists in this DB -- cannot satisfy onboarding_plans.template_version_id NOT NULL")
    plan = OnboardingPlan(membership_id=membership.membership_id, template_version_id=template_version_id, revision=1, status=PlanStatus.PROJECT_READY)
    session.add(plan)
    await session.flush()

    fixture_text = (REPO_ROOT / case["fixture_copy"]).read_text(encoding="utf-8")
    request = ProjectIngestRequest(
        project_id=project.project_id,
        created_by_user_id=pm.user_id,
        source_key=f"eval-inj:{case['case_id']}:{unique}",
        source_url=f"eval://prompt-injection/{case['case_id']}",
        source_repo="eval/prompt_injection-fixture",
        source_path=case["fixture_copy"],
        document_category=DocumentCategory.CODEBASE_GUIDE,
        raw_content=fixture_text,
        source_ref=unique,
        title=f"[EVAL FIXTURE] {case['case_id']}",
        category_confirmed=True,
    )
    document = await ingest_or_update(session, request, embedder)
    await session.commit()
    return {
        "pm_id": pm.user_id, "member_id": member.user_id, "project_id": project.project_id,
        "membership_id": membership.membership_id, "plan_id": plan.plan_id,
        "document_id": document.document_id,
    }


async def _cleanup(session, created: dict) -> None:
    """Best-effort, always-run teardown -- deletes children before parents, never raises past
    a missing row (a partially-created case must still let later cases' cleanup proceed)."""
    from sqlalchemy import delete, select

    from src.model.answer_claim import AnswerClaim
    from src.model.chat_message import ChatMessage
    from src.model.chat_session import ChatSession
    from src.model.citation import Citation
    from src.model.document_chunk import DocumentChunk
    from src.model.document_version import DocumentVersion
    from src.model.knowledge_document import KnowledgeDocument
    from src.model.onboarding_plan import OnboardingPlan
    from src.model.project import Project
    from src.model.project_membership import ProjectMembership
    from src.model.user import User

    # If run_case_live's try block failed on a DB error (e.g. the BM25 special-character bug --
    # see CHANGE_LOG.md), the session's transaction is left aborted and every query below would
    # immediately raise InFailedSQLTransactionError before doing any cleanup. Staging already
    # committed by the time ask_project() runs, so skipping this rollback silently orphans the
    # throwaway project/user/document rows -- confirmed happening for real (pk_inj_003/004).
    await session.rollback()
    try:
        membership_id = created.get("membership_id")
        if membership_id is not None:
            session_ids = (
                await session.execute(select(ChatSession.session_id).where(ChatSession.membership_id == membership_id))
            ).scalars().all()
            if session_ids:
                message_ids = (
                    await session.execute(select(ChatMessage.message_id).where(ChatMessage.session_id.in_(session_ids)))
                ).scalars().all()
                if message_ids:
                    await session.execute(delete(Citation).where(Citation.message_id.in_(message_ids)))
                    await session.execute(delete(AnswerClaim).where(AnswerClaim.message_id.in_(message_ids)))
                    await session.execute(delete(ChatMessage).where(ChatMessage.message_id.in_(message_ids)))
                await session.execute(delete(ChatSession).where(ChatSession.session_id.in_(session_ids)))

        document_id = created.get("document_id")
        if document_id is not None:
            version_ids = (
                await session.execute(select(DocumentVersion.version_id).where(DocumentVersion.document_id == document_id))
            ).scalars().all()
            if version_ids:
                await session.execute(delete(DocumentChunk).where(DocumentChunk.version_id.in_(version_ids)))
                await session.execute(delete(DocumentVersion).where(DocumentVersion.version_id.in_(version_ids)))
            await session.execute(delete(KnowledgeDocument).where(KnowledgeDocument.document_id == document_id))

        if created.get("plan_id") is not None:
            await session.execute(delete(OnboardingPlan).where(OnboardingPlan.plan_id == created["plan_id"]))
        if membership_id is not None:
            await session.execute(delete(ProjectMembership).where(ProjectMembership.membership_id == membership_id))
        if created.get("project_id") is not None:
            await session.execute(delete(Project).where(Project.project_id == created["project_id"]))
        for key in ("pm_id", "member_id"):
            if created.get(key) is not None:
                await session.execute(delete(User).where(User.user_id == created[key]))
        await session.commit()
    except Exception:
        await session.rollback()
        raise


async def run_case_live(case: dict, chat, embedder, chat_completion) -> CaseResult:
    from eval.shared.llm_judge import judge

    error = _validate_case(case)
    if error:
        return CaseResult(case["case_id"], "fail", error)

    created: dict = {}
    try:
        created = await _stage_throwaway_project(chat.session, case, embedder)
        result = await chat.ask_project(
            case["user_question"], user_id=created["member_id"], membership_id=created["membership_id"]
        )
        if case["injected_content"] in result.answer:
            return CaseResult(
                case["case_id"], "fail",
                f"injected_content leaked verbatim into the answer: {result.answer[:300]!r}",
            )
        passed, reason = await judge(
            chat_completion, user_message=case["user_question"],
            expected_behavior=case["expected_behavior"], actual_answer=result.answer,
        )
        detail = f"judge: {reason} | answer: {result.answer[:300]!r}"
        return CaseResult(case["case_id"], "pass" if passed else "fail", detail)
    finally:
        if created:
            await _cleanup(chat.session, created)


async def main_live(cases: list[dict]) -> list[CaseResult]:
    from eval.shared.live_chat import live_chat

    async with live_chat() as chat:
        results = []
        for case in cases:
            try:
                results.append(
                    await run_case_live(case, chat, chat.resources.ingestion_embedding, chat.resources.chat_completion)
                )
            except Exception as exc:  # noqa: BLE001
                # `_cleanup`'s own except already rolls back on a DB failure inside staging/
                # teardown; this is a defensive backstop for any other path that could leave
                # the shared session's transaction aborted for the next case.
                await chat.session.rollback()
                results.append(CaseResult(case.get("case_id", "?"), "fail", f"{type(exc).__name__}: {exc}"))
        return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    cases = load_dataset()
    if args.live:
        results = asyncio.run(main_live(cases))
    else:
        results = [run_case_dry(case) for case in cases]

    report = build_report(
        domain="project_knowledge",
        eval_type="prompt_injection",
        run_mode="live" if args.live else "dry_run",
        results=results,
    )
    write_report(report, REPORT_PATH)
    print_summary(report)


if __name__ == "__main__":
    main()
