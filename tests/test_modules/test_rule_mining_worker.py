"""RuleMiningWorker end-to-end (CLAUDE.md Phase 5). Real SQLite AsyncSession (db_session,
tests/conftest.py), real FakeEmbedder (deterministic — identical text -> identical vector, so
cosine=1.0 for two evidence units given the same LLM-extracted rule_text_draft), and a stub LLM
keyed by a substring of the evidence unit's comment body so ordering never matters.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.ai.providers.embeddings_fake import FakeEmbedder
from src.model.base import Base
from src.model.enums import RuleEvidenceType
from src.model.llm_call_log import LlmCallLog
from src.model.raw_pr_comment import RawPrComment
from src.model.rule_candidate import RuleCandidate
from src.model.rule_evidence import RuleEvidence
from src.model.rule_family import RuleFamily
from src.modules.knowledge.mining.rule_mining_worker import mine_new_evidence, mine_rules

REPO = "acme/widgets"


@dataclass
class _StubResponse:
    content: str
    response_metadata: dict = field(default_factory=dict)
    usage_metadata: dict = field(default_factory=dict)


class _KeywordLLM:
    def __init__(self, rules: list[tuple[str, dict]]) -> None:
        self._rules = rules

    async def ainvoke(self, messages, config=None):
        user_content = messages[1][1]
        for keyword, payload in self._rules:
            if keyword in user_content:
                return _StubResponse(json.dumps(payload), response_metadata={"model_name": "stub"})
        raise AssertionError(f"no stub rule matched user content: {user_content!r}")


def _row(comment_id: int, pr_number: int, author: str, body: str, *, created_at: datetime) -> RawPrComment:
    return RawPrComment(
        raw_pr_comment_id=comment_id,
        repo=REPO,
        pr_number=pr_number,
        pr_author="pr-author",
        type="review_comment(diff)",
        author=author,
        is_bot_comment=False,
        body=body,
        review_state=None,
        in_reply_to_id=None,
        url=f"https://x/{comment_id}",
        created_at=created_at,
        secret_scanned_at=datetime(2025, 8, 1),
    )


@pytest.mark.asyncio
async def test_two_evidence_units_from_different_prs_form_an_eligible_family(db_session) -> None:
    db_session.add(_row(1, 100, "alice", "please avoid double negative boolean naming here, it makes the return value confusing", created_at=datetime(2025, 8, 1)))
    db_session.add(_row(2, 200, "bob", "reviewer flags avoid double negative boolean naming again in this other function too", created_at=datetime(2025, 8, 2)))
    await db_session.commit()

    llm = _KeywordLLM(
        [
            (
                "double negative",
                {
                    "evidence_type": "REUSABLE_CORRECTION",
                    "reuse_scope": 2,
                    "rule_text_draft": "Avoid double-negative boolean naming.",
                    "rationale": "Chưa tìm thấy lý do tường minh",
                },
            ),
        ]
    )

    summary = await mine_rules(db_session, llm, FakeEmbedder(), repo=REPO)

    assert summary.evidence_units_total == 2
    assert summary.evidence_units_eligible == 2
    assert summary.families_created == 1
    assert summary.families_pruned_ineligible == 0

    families = (await db_session.scalars(select(RuleFamily))).all()
    assert len(families) == 1
    assert families[0].distinct_reviewer_count == 2

    evidences = (await db_session.scalars(select(RuleEvidence))).all()
    assert len(evidences) == 2
    assert {e.pr_number for e in evidences} == {100, 200}
    cosines = sorted(e.cluster_edge_cosine_similarity is None for e in evidences)
    assert cosines == [False, True]  # exactly one NULL (first node), one real cosine

    candidates = (await db_session.scalars(select(RuleCandidate))).all()
    assert len(candidates) == 2

    logs = (await db_session.scalars(select(LlmCallLog).where(LlmCallLog.module == "rule_mining"))).all()
    assert len(logs) == 2
    assert all(log.gate_decision == "eligible" for log in logs)


@pytest.mark.asyncio
async def test_two_evidence_units_from_the_same_pr_are_not_promoted_to_a_family(db_session) -> None:
    """Required negative test (CLAUDE.md Phase 5 exit criteria): a connected component of >=2
    nodes from the SAME PR must not become a RuleFamily, even though clustering (blind to PR
    distribution) merges them."""
    db_session.add(_row(1, 300, "alice", "please avoid shallow functions in this module, inline it directly instead", created_at=datetime(2025, 8, 1)))
    db_session.add(_row(2, 300, "alice", "again avoid shallow functions in this other spot, same reasoning applies here", created_at=datetime(2025, 8, 1, 1)))
    await db_session.commit()

    llm = _KeywordLLM(
        [
            (
                "shallow functions",
                {
                    "evidence_type": "CONVENTION",
                    "reuse_scope": 2,
                    "rule_text_draft": "Avoid shallow functions called from one place.",
                    "rationale": "Chưa tìm thấy lý do tường minh",
                },
            ),
        ]
    )

    summary = await mine_rules(db_session, llm, FakeEmbedder(), repo=REPO)

    assert summary.evidence_units_eligible == 2
    assert summary.candidate_families == 1  # clustering DID merge them into one component...
    assert summary.families_created == 0  # ...but the guardrail rejected it
    assert summary.families_pruned_ineligible == 1

    assert (await db_session.scalars(select(RuleFamily))).all() == []
    assert (await db_session.scalars(select(RuleEvidence))).all() == []
    # The RuleCandidate rows themselves are NOT deleted — they represent real LLM extraction
    # output, independent of whether a family formed (RuleCandidate.__doc__).
    candidates = (await db_session.scalars(select(RuleCandidate))).all()
    assert len(candidates) == 2


@pytest.mark.asyncio
async def test_ineligible_evidence_type_never_reaches_embedding_or_clustering(db_session) -> None:
    db_session.add(_row(1, 400, "alice", "why is this check inside the if statement here, seems unnecessary to me", created_at=datetime(2025, 8, 1)))
    await db_session.commit()

    llm = _KeywordLLM(
        [
            (
                "check inside",
                {
                    "evidence_type": "LOCAL_CORRECTION",
                    "reuse_scope": 0,
                    "rule_text_draft": "",
                    "rationale": "Chưa tìm thấy lý do tường minh",
                },
            ),
        ]
    )

    summary = await mine_rules(db_session, llm, FakeEmbedder(), repo=REPO)

    assert summary.evidence_units_eligible == 0
    assert summary.evidence_units_filtered_out == {"LOCAL_CORRECTION": 1}
    assert summary.candidate_families == 0
    assert (await db_session.scalars(select(RuleCandidate))).all() == []


@pytest.mark.asyncio
async def test_only_secret_scanned_and_non_bot_rows_are_read(db_session) -> None:
    unscanned = _row(1, 500, "alice", "avoid shallow functions unscanned row", created_at=datetime(2025, 8, 1))
    unscanned.secret_scanned_at = None
    db_session.add(unscanned)
    bot_row = _row(2, 500, "some-bot[bot]", "avoid shallow functions bot row", created_at=datetime(2025, 8, 1))
    bot_row.is_bot_comment = True
    db_session.add(bot_row)
    await db_session.commit()

    llm = _KeywordLLM([("avoid shallow functions", {"evidence_type": "NOISE_OTHER", "reuse_scope": 0, "rule_text_draft": "", "rationale": "x"})])

    summary = await mine_rules(db_session, llm, FakeEmbedder(), repo=REPO)

    assert summary.comments_loaded == 0
    assert summary.evidence_units_total == 0


# ------------------------------------------ NOISE_OTHER vs extraction-failure (CLAUDE.md Phase 7)


class _FailingKeywordLLM(_KeywordLLM):
    """Like _KeywordLLM, but raises for a chosen keyword — simulates a provider/LLM failure
    (429/timeout/5xx/etc, not a real semantic verdict)."""

    def __init__(self, rules: list[tuple[str, dict]], *, fail_keyword: str) -> None:
        super().__init__(rules)
        self._fail_keyword = fail_keyword

    async def ainvoke(self, messages, config=None):
        if self._fail_keyword in messages[1][1]:
            raise RuntimeError("provider timeout")
        return await super().ainvoke(messages)


@pytest.mark.asyncio
async def test_provider_failure_is_logged_as_extraction_failed_not_noise_other(db_session) -> None:
    db_session.add(
        _row(
            1, 600, "alice",
            "trigger provider outage here during this particular review comment thread today",
            created_at=datetime(2025, 8, 1),
        )
    )
    await db_session.commit()

    llm = _FailingKeywordLLM([], fail_keyword="trigger provider outage")

    summary = await mine_rules(db_session, llm, FakeEmbedder(), repo=REPO)

    assert summary.evidence_units_extraction_failed == ["review_comment(diff):1"]
    # Must NOT be silently absorbed into the NOISE_OTHER/filtered_out bucket.
    assert summary.evidence_units_filtered_out == {}
    assert (await db_session.scalars(select(RuleCandidate))).all() == []

    logs = (await db_session.scalars(select(LlmCallLog).where(LlmCallLog.module == "rule_mining"))).all()
    assert len(logs) == 1
    assert logs[0].gate_decision == "extraction_failed"
    assert logs[0].decision_details.get("evidence_type") is None  # never a fake NOISE_OTHER classification
    assert logs[0].error_code == "provider timeout"


@pytest.mark.asyncio
async def test_blank_rule_text_draft_despite_eligible_is_invalid_output_not_candidate(db_session) -> None:
    db_session.add(
        _row(
            1, 700, "alice",
            "avoid blank output case entirely in this particular review comment scenario today",
            created_at=datetime(2025, 8, 1),
        )
    )
    await db_session.commit()

    llm = _KeywordLLM(
        [
            (
                "avoid blank output case",
                {
                    "evidence_type": "REUSABLE_CORRECTION",
                    "reuse_scope": 1,
                    "rule_text_draft": "   ",  # blank after strip — invalid, despite eligible verdict
                    "rationale": "Chưa tìm thấy lý do tường minh",
                },
            ),
        ]
    )

    summary = await mine_rules(db_session, llm, FakeEmbedder(), repo=REPO)

    assert summary.evidence_units_extraction_failed == ["review_comment(diff):1"]
    assert summary.evidence_units_filtered_out == {}
    assert summary.evidence_units_eligible == 0
    assert (await db_session.scalars(select(RuleCandidate))).all() == []

    logs = (await db_session.scalars(select(LlmCallLog).where(LlmCallLog.module == "rule_mining"))).all()
    assert logs[0].gate_decision == "invalid_output"


# --------------------------------------------------- completion-order independence (regression)


class _DelayedKeywordLLM(_KeywordLLM):
    def __init__(self, rules: list[tuple[str, dict]], delays: dict[str, float]) -> None:
        super().__init__(rules)
        self._delays = delays

    async def ainvoke(self, messages, config=None):
        user_content = messages[1][1]
        for keyword, delay in self._delays.items():
            if keyword in user_content:
                await asyncio.sleep(delay)
                break
        return await super().ainvoke(messages)


async def _fresh_sqlite_session():
    """Independent in-memory SQLite DB, mirroring tests/conftest.py's `db_session` fixture
    inline — needed here because this test compares two full mine_rules() runs against two
    genuinely separate databases in a single test function."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory()


async def _run_family_scenario(session, llm) -> tuple:
    """3 evidence units, 3 different PRs: unit A and unit B extract to the IDENTICAL
    rule_text_draft (FakeEmbedder gives identical text cosine=1.0, guaranteeing a cluster
    regardless of extraction order), unit C is a real semantic non-match."""
    session.add_all(
        [
            _row(
                1, 810, "alice",
                "please dispatch-A avoid duplicated resource cleanup logic across this particular module today",
                created_at=datetime(2025, 8, 1),
            ),
            _row(
                2, 820, "bob",
                "please dispatch-B avoid duplicated resource cleanup logic across this particular module today",
                created_at=datetime(2025, 8, 2),
            ),
            _row(
                3, 830, "carol",
                "dispatch-C just wondering why this particular pattern exists in the codebase",
                created_at=datetime(2025, 8, 3),
            ),
        ]
    )
    await session.commit()

    summary = await mine_rules(session, llm, FakeEmbedder(), repo=REPO)
    families = (await session.scalars(select(RuleFamily))).all()
    evidences = (await session.scalars(select(RuleEvidence))).all()
    return summary, families, evidences


@pytest.mark.asyncio
async def test_family_membership_is_identical_regardless_of_llm_completion_order(db_session) -> None:
    rules = [
        ("dispatch-A", {"evidence_type": "CONVENTION", "reuse_scope": 2, "rule_text_draft": "Avoid duplicated resource cleanup.", "rationale": "x"}),
        ("dispatch-B", {"evidence_type": "CONVENTION", "reuse_scope": 2, "rule_text_draft": "Avoid duplicated resource cleanup.", "rationale": "x"}),
        ("dispatch-C", {"evidence_type": "QUESTION_DISCUSSION", "reuse_scope": 0, "rule_text_draft": "", "rationale": "x"}),
    ]

    # Baseline: no artificial delay (dispatch order == completion order).
    baseline_summary, baseline_families, baseline_evidences = await _run_family_scenario(
        db_session, _DelayedKeywordLLM(rules, delays={})
    )

    # Reordered: unit A (dispatched first) finishes LAST, unit C (dispatched last) finishes
    # FIRST — completion order is the exact reverse of dispatch/units order.
    engine, reordered_session = await _fresh_sqlite_session()
    try:
        reordered_summary, reordered_families, reordered_evidences = await _run_family_scenario(
            reordered_session,
            _DelayedKeywordLLM(rules, delays={"dispatch-A": 0.3, "dispatch-B": 0.15, "dispatch-C": 0.0}),
        )
    finally:
        await reordered_session.close()
        await engine.dispose()

    for summary, families, evidences, label in (
        (baseline_summary, baseline_families, baseline_evidences, "baseline"),
        (reordered_summary, reordered_families, reordered_evidences, "reordered"),
    ):
        assert summary.evidence_units_eligible == 2, label
        assert summary.evidence_units_extraction_failed == [], label
        assert summary.evidence_units_filtered_out == {"QUESTION_DISCUSSION": 1}, label
        assert summary.families_created == 1, label
        assert len(families) == 1, label
        assert families[0].distinct_reviewer_count == 2, label
        assert {e.pr_number for e in evidences} == {810, 820}, label
        assert len(evidences) == 2, label

    # Not just "same shape" — the two runs must agree on every one of these fields exactly.
    assert baseline_summary.evidence_units_eligible == reordered_summary.evidence_units_eligible
    assert baseline_summary.families_created == reordered_summary.families_created
    assert {e.pr_number for e in baseline_evidences} == {e.pr_number for e in reordered_evidences}
    assert baseline_families[0].distinct_reviewer_count == reordered_families[0].distinct_reviewer_count


# --------------------------------------------------------------------------------------
# Idempotent re-run — the bug reproduced live in the manual E2E session (CHANGE_LOG.md):
# mine_new_evidence() run against a repo already mined by mine_rules() crashed with
# IntegrityError on uq_rule_evidences_evidence_unit_id after ~5 minutes.
# --------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mine_rules_marks_processed_comments_so_a_later_incremental_run_sees_nothing_new(
    db_session,
) -> None:
    db_session.add(_row(1, 100, "alice", "please avoid double negative boolean naming here, it makes the return value confusing", created_at=datetime(2025, 8, 1)))
    db_session.add(_row(2, 200, "bob", "reviewer flags avoid double negative boolean naming again in this other function too", created_at=datetime(2025, 8, 2)))
    await db_session.commit()

    llm = _KeywordLLM(
        [
            (
                "double negative",
                {
                    "evidence_type": "REUSABLE_CORRECTION",
                    "reuse_scope": 2,
                    "rule_text_draft": "Avoid double-negative boolean naming.",
                    "rationale": "x",
                },
            ),
        ]
    )
    first = await mine_rules(db_session, llm, FakeEmbedder(), repo=REPO)
    assert first.families_created == 1

    rows = (await db_session.scalars(select(RawPrComment))).all()
    assert all(row.mining_processed_at is not None for row in rows)

    evidences_before = (await db_session.scalars(select(RuleEvidence))).all()
    second = await mine_new_evidence(db_session, llm, FakeEmbedder(), repo=REPO)
    evidences_after = (await db_session.scalars(select(RuleEvidence))).all()

    assert second.evidence_units_total == 0
    assert len(evidences_after) == len(evidences_before)


@pytest.mark.asyncio
async def test_mine_new_evidence_tolerates_legacy_evidence_with_unset_mining_processed_at(
    db_session,
) -> None:
    """Reproduces the exact bug: evidence seeded the way the old `mine_rules()` used to leave
    it — a RuleEvidence row exists, but the root comment's `mining_processed_at` was never set
    (true for every repo mined before that field existed/was populated). An incremental run
    must not re-extract and re-insert these — it used to crash on the unique constraint.
    """
    comment1 = _row(1, 100, "alice", "please avoid double negative boolean naming here, it makes the return value confusing", created_at=datetime(2025, 8, 1))
    comment2 = _row(2, 200, "bob", "reviewer flags avoid double negative boolean naming again in this other function too", created_at=datetime(2025, 8, 2))
    db_session.add_all([comment1, comment2])
    await db_session.flush()

    candidate1 = RuleCandidate(
        evidence_type=RuleEvidenceType.REUSABLE_CORRECTION,
        reuse_scope=2,
        rule_text_draft="Avoid double-negative boolean naming.",
        rationale="x",
        evidence_unit_id=f"review_comment(diff):{comment1.raw_pr_comment_id}",
        pr_number=100,
        comment_snippet_snapshot=comment1.body,
        original_author="alice",
        evidence_created_at=comment1.created_at,
    )
    candidate2 = RuleCandidate(
        evidence_type=RuleEvidenceType.REUSABLE_CORRECTION,
        reuse_scope=2,
        rule_text_draft="Avoid double-negative boolean naming.",
        rationale="x",
        evidence_unit_id=f"review_comment(diff):{comment2.raw_pr_comment_id}",
        pr_number=200,
        comment_snippet_snapshot=comment2.body,
        original_author="bob",
        evidence_created_at=comment2.created_at,
    )
    db_session.add_all([candidate1, candidate2])
    await db_session.flush()

    family = RuleFamily(distinct_reviewer_count=2)
    db_session.add(family)
    await db_session.flush()

    db_session.add_all(
        [
            RuleEvidence(
                rule_candidate_id=candidate1.rule_candidate_id,
                rule_family_id=family.rule_family_id,
                evidence_unit_id=candidate1.evidence_unit_id,
                pr_number=100,
                comment_snippet_snapshot=comment1.body,
                original_author="alice",
                evidence_created_at=comment1.created_at,
                cluster_edge_cosine_similarity=None,
            ),
            RuleEvidence(
                rule_candidate_id=candidate2.rule_candidate_id,
                rule_family_id=family.rule_family_id,
                evidence_unit_id=candidate2.evidence_unit_id,
                pr_number=200,
                comment_snippet_snapshot=comment2.body,
                original_author="bob",
                evidence_created_at=comment2.created_at,
                cluster_edge_cosine_similarity=0.9,
            ),
        ]
    )
    await db_session.commit()
    # The bug: neither comment's mining_processed_at was ever set, despite already having
    # RuleEvidence rows — exactly what the pre-fix mine_rules() left behind.
    assert comment1.mining_processed_at is None
    assert comment2.mining_processed_at is None

    llm = _KeywordLLM([("double negative", {"evidence_type": "REUSABLE_CORRECTION", "reuse_scope": 2, "rule_text_draft": "x", "rationale": "x"})])
    summary = await mine_new_evidence(db_session, llm, FakeEmbedder(), repo=REPO)

    assert summary.evidence_units_total == 0
    evidences = (await db_session.scalars(select(RuleEvidence))).all()
    assert len(evidences) == 2
