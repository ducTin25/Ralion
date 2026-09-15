"""F6 Phase 6 — HITL Review Queue service (CLAUDE.md Phase 6). Real SQLite AsyncSession
(db_session, tests/conftest.py) — builds RuleFamily/RuleCandidate/RuleEvidence/RawPrComment
rows directly (bypassing the mining pipeline) since this module only reads/reviews families
that already passed the Phase 5 eligibility guardrail.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from src.model.enums import RuleEvidenceType, RuleFamilyStatus, UserStatus
from src.model.raw_pr_comment import RawPrComment
from src.model.rule_candidate import RuleCandidate
from src.model.rule_evidence import RuleEvidence
from src.model.rule_family import RuleFamily
from src.model.user import User
from src.services import rule_review_service
from src.services.rule_review_service import RuleFamilyAlreadyReviewedError, RuleFamilyNotFoundError

REPO = "acme/widgets"


async def _seed_user(db_session, email: str) -> User:
    user = User(email=email, display_name=email, status=UserStatus.ACTIVE)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _seed_family(
    db_session,
    *,
    status: RuleFamilyStatus = RuleFamilyStatus.PENDING,
    cosine: float = 0.9,
) -> RuleFamily:
    now = datetime(2025, 8, 1)
    comment1 = RawPrComment(
        repo=REPO,
        pr_number=100,
        pr_author="x",
        type="review_comment(diff)",
        author="alice",
        is_bot_comment=False,
        body="avoid X",
        url="https://github.com/acme/widgets/pull/100#discussion_r1",
        created_at=now,
        secret_scanned_at=now,
    )
    comment2 = RawPrComment(
        repo=REPO,
        pr_number=200,
        pr_author="y",
        type="review_comment(diff)",
        author="bob",
        is_bot_comment=False,
        body="avoid X too",
        url="https://github.com/acme/widgets/pull/200#discussion_r2",
        created_at=now,
        secret_scanned_at=now,
    )
    db_session.add_all([comment1, comment2])
    await db_session.flush()

    candidate1 = RuleCandidate(
        evidence_type=RuleEvidenceType.CONVENTION, reuse_scope=2, rule_text_draft="Avoid X.", rationale="r"
    )
    candidate2 = RuleCandidate(
        evidence_type=RuleEvidenceType.CONVENTION, reuse_scope=2, rule_text_draft="Avoid X please.", rationale="r"
    )
    db_session.add_all([candidate1, candidate2])
    await db_session.flush()

    family = RuleFamily(distinct_reviewer_count=2, status=status)
    db_session.add(family)
    await db_session.flush()

    db_session.add_all(
        [
            RuleEvidence(
                rule_candidate_id=candidate1.rule_candidate_id,
                rule_family_id=family.rule_family_id,
                evidence_unit_id=f"review_comment(diff):{comment1.raw_pr_comment_id}",
                pr_number=100,
                comment_snippet_snapshot="avoid X",
                original_author="alice",
                evidence_created_at=now,
                cluster_edge_cosine_similarity=None,  # anchor node
            ),
            RuleEvidence(
                rule_candidate_id=candidate2.rule_candidate_id,
                rule_family_id=family.rule_family_id,
                evidence_unit_id=f"review_comment(diff):{comment2.raw_pr_comment_id}",
                pr_number=200,
                comment_snippet_snapshot="avoid X too",
                original_author="bob",
                evidence_created_at=now,
                cluster_edge_cosine_similarity=cosine,
            ),
        ]
    )
    await db_session.commit()
    await db_session.refresh(family)
    return family


@pytest.mark.asyncio
async def test_list_pending_returns_anchor_rule_text_permalinks_and_confidence(db_session) -> None:
    family = await _seed_family(db_session, cosine=0.9)  # >= high_threshold 0.85 -> HIGH

    result = await rule_review_service.list_pending(db_session, page=1, page_size=20)

    assert result.meta.total == 1
    item = result.items[0]
    assert item.rule_family_id == family.rule_family_id
    assert item.rule_text == "Avoid X."  # anchor evidence (NULL cosine)'s rule_text_draft
    assert item.family_match_confidence == "HIGH"
    assert item.distinct_reviewer_count == 2
    permalinks = {e.permalink for e in item.evidence}
    assert permalinks == {
        "https://github.com/acme/widgets/pull/100#discussion_r1",
        "https://github.com/acme/widgets/pull/200#discussion_r2",
    }
    assert sorted(e.cluster_edge_cosine_similarity is None for e in item.evidence) == [False, True]


@pytest.mark.asyncio
async def test_medium_confidence_below_high_threshold(db_session) -> None:
    await _seed_family(db_session, cosine=0.75)  # >= merge 0.70, < high 0.85 -> MEDIUM

    result = await rule_review_service.list_pending(db_session, page=1, page_size=20)

    assert result.items[0].family_match_confidence == "MEDIUM"


@pytest.mark.asyncio
async def test_approve_moves_family_from_pending_to_conventions(db_session) -> None:
    reviewer = await _seed_user(db_session, "pm@f6.dev")
    family = await _seed_family(db_session)

    outcome = await rule_review_service.approve(db_session, family.rule_family_id, reviewer, repo=REPO)

    assert outcome.status == RuleFamilyStatus.APPROVED
    assert outcome.approved_by == reviewer.user_id
    assert outcome.approved_at is not None

    pending = await rule_review_service.list_pending(db_session, page=1, page_size=20)
    assert pending.meta.total == 0

    approved = await rule_review_service.list_approved(db_session, page=1, page_size=20)
    assert approved.meta.total == 1
    assert approved.items[0].rule_family_id == family.rule_family_id


@pytest.mark.asyncio
async def test_reject_never_leaks_into_conventions_or_pending(db_session) -> None:
    reviewer = await _seed_user(db_session, "pm2@f6.dev")
    family = await _seed_family(db_session)

    outcome = await rule_review_service.reject(db_session, family.rule_family_id, reviewer, repo=REPO)

    assert outcome.status == RuleFamilyStatus.REJECTED
    assert outcome.rejected_by == reviewer.user_id

    pending = await rule_review_service.list_pending(db_session, page=1, page_size=20)
    assert pending.meta.total == 0
    approved = await rule_review_service.list_approved(db_session, page=1, page_size=20)
    assert approved.meta.total == 0


@pytest.mark.asyncio
async def test_concurrent_approve_race_condition_second_call_gets_conflict(db_session) -> None:
    """Required race-condition test (CLAUDE.md Phase 6 exit criteria): 2 approve calls on the
    same family — only the first succeeds, the second gets a conflict, never a silent
    overwrite."""
    reviewer_a = await _seed_user(db_session, "pm-a@f6.dev")
    reviewer_b = await _seed_user(db_session, "pm-b@f6.dev")
    family = await _seed_family(db_session)

    first = await rule_review_service.approve(db_session, family.rule_family_id, reviewer_a, repo=REPO)
    assert first.status == RuleFamilyStatus.APPROVED
    assert first.approved_by == reviewer_a.user_id

    with pytest.raises(RuleFamilyAlreadyReviewedError):
        await rule_review_service.approve(db_session, family.rule_family_id, reviewer_b, repo=REPO)

    # The loser must not have overwritten the winner's attribution.
    approved = await rule_review_service.list_approved(db_session, page=1, page_size=20)
    assert approved.meta.total == 1


@pytest.mark.asyncio
async def test_approve_nonexistent_family_raises_not_found(db_session) -> None:
    reviewer = await _seed_user(db_session, "pm3@f6.dev")

    with pytest.raises(RuleFamilyNotFoundError):
        await rule_review_service.approve(db_session, 999999, reviewer, repo=REPO)


@pytest.mark.asyncio
async def test_reject_after_already_approved_raises_conflict(db_session) -> None:
    reviewer = await _seed_user(db_session, "pm4@f6.dev")
    family = await _seed_family(db_session)

    await rule_review_service.approve(db_session, family.rule_family_id, reviewer, repo=REPO)

    with pytest.raises(RuleFamilyAlreadyReviewedError):
        await rule_review_service.reject(db_session, family.rule_family_id, reviewer, repo=REPO)
