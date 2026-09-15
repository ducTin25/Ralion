"""F6 Phase 6 — HITL Review Queue backend (F6_RULE_MINING_PLAN.md §4, F6_RULE_MINING_SPEC.md
§2.3). Operates entirely on `RuleFamily`: Phase 5's eligibility guardrail
(`>=2 distinct evidence_unit_id AND >=2 distinct pr_number`, `src.modules.knowledge.mining.
eligibility`) already ran at mining time and deleted every ineligible family, so every
`RuleFamily` row this module can see already satisfies "evidence_count>=2" — this module only
re-reads status, it never recomputes eligibility (CLAUDE.md Phase 6 §1).
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.providers.embeddings import Embedder
from src.ai.retrieval_engine.chunking_config import rule_mining_params
from src.core.security.secret_scan import redact
from src.dto.admin_console_dto import PageMetaDTO
from src.dto.response.rule_review_dto import (
    MemberConventionEvidenceDTO,
    MemberConventionExampleDTO,
    MemberConventionItemDTO,
    MemberConventionListDTO,
    RuleEvidenceItemDTO,
    RuleFamilyActionResultDTO,
    RuleFamilyItemDTO,
    RuleFamilyListDTO,
)
from src.model.enums import RuleFamilyStatus
from src.model.project import Project
from src.model.raw_pr_comment import RawPrComment
from src.model.rule_candidate import RuleCandidate
from src.model.rule_evidence import RuleEvidence
from src.model.rule_family import RuleFamily
from src.model.user import User
from src.modules.knowledge.mining.clustering import confidence_from_cosine
from src.modules.knowledge.mining.convention_ingestion import (
    ConventionIngestError,
    ingest_approved_rule_family,
    select_anchor,
)

logger = logging.getLogger(__name__)


class RuleFamilyNotFoundError(Exception):
    pass


class RuleFamilyAlreadyReviewedError(Exception):
    """Optimistic-lock loss — someone else already approved/rejected this family."""


class RuleFamilyNotApprovedError(Exception):
    """Re-index was asked for a family that is not APPROVED, so has nothing to index."""


def _raw_pr_comment_id(evidence_unit_id: str) -> int:
    # Business key format from EvidenceUnit.evidence_unit_id: "<type>:<raw_pr_comment_id>".
    return int(evidence_unit_id.rsplit(":", 1)[1])


async def _build_items(db: AsyncSession, families: list[RuleFamily]) -> list[RuleFamilyItemDTO]:
    if not families:
        return []

    clustering_config = rule_mining_params()["clustering"]
    merge_threshold = float(clustering_config["cosine_merge_threshold"])
    high_threshold = float(clustering_config["cosine_high_confidence_threshold"])

    family_ids = [family.rule_family_id for family in families]
    evidence_rows = (
        await db.execute(
            select(RuleEvidence, RuleCandidate.rule_text_draft)
            .join(RuleCandidate, RuleCandidate.rule_candidate_id == RuleEvidence.rule_candidate_id)
            .where(RuleEvidence.rule_family_id.in_(family_ids))
            .order_by(RuleEvidence.rule_evidence_id)
        )
    ).all()

    raw_comment_ids = {_raw_pr_comment_id(evidence.evidence_unit_id) for evidence, _ in evidence_rows}
    permalinks: dict[int, str] = {}
    if raw_comment_ids:
        rows = (
            await db.execute(
                select(RawPrComment.raw_pr_comment_id, RawPrComment.url).where(
                    RawPrComment.raw_pr_comment_id.in_(raw_comment_ids)
                )
            )
        ).all()
        permalinks = dict(rows)

    members_by_family: dict[int, list[tuple[RuleEvidence, str]]] = {}
    for evidence, rule_text_draft in evidence_rows:
        members_by_family.setdefault(evidence.rule_family_id, []).append((evidence, rule_text_draft))

    items: list[RuleFamilyItemDTO] = []
    for family in families:
        members = members_by_family.get(family.rule_family_id, [])
        # Anchor selection is defined once, in convention_ingestion, so the rule text shown
        # here is provably the same text Phase 10 indexes for F5 on approval.
        anchor = select_anchor([evidence for evidence, _ in members])
        rule_text = next((text for evidence, text in members if evidence is anchor), "")

        cosines = [e.cluster_edge_cosine_similarity for e, _ in members if e.cluster_edge_cosine_similarity is not None]
        # Weakest edge in the family is the conservative confidence for the family as a whole
        # (a family is only as strong as its least-similar member).
        confidence = (
            confidence_from_cosine(min(cosines), merge_threshold=merge_threshold, high_threshold=high_threshold)
            if cosines
            else None
        )

        items.append(
            RuleFamilyItemDTO(
                rule_family_id=family.rule_family_id,
                rule_text=rule_text,
                status=family.status,
                distinct_reviewer_count=family.distinct_reviewer_count,
                family_match_confidence=confidence,
                evidence=[
                    RuleEvidenceItemDTO(
                        # Defense-in-depth (CLAUDE.md invariant #6): ingestion already redacts
                        # every raw_pr_comments row before persist, so this should be a no-op in
                        # the normal path. It is the second, independent layer for the case where
                        # a secret slipped through that first scan anyway — same `redact()` used
                        # at every other egress boundary (chat, plan-generation), not a new scanner.
                        comment_snippet_snapshot=redact(evidence.comment_snippet_snapshot)[0],
                        original_author=evidence.original_author,
                        evidence_created_at=evidence.evidence_created_at,
                        permalink=permalinks.get(_raw_pr_comment_id(evidence.evidence_unit_id), ""),
                        cluster_edge_cosine_similarity=evidence.cluster_edge_cosine_similarity,
                    )
                    for evidence, _ in members
                ],
            )
        )
    return items


async def _resolve_family_repos(db: AsyncSession, family_ids: list[int]) -> dict[int, str | None]:
    """One repo per family (or `None` if its evidence doesn't resolve to exactly one repo).

    `RuleFamily`/`RuleCandidate` carry no `project_id`/`repo` column — a family's repo is only
    derivable transitively through its evidence's `RawPrComment.repo`. This is the exact
    resolution `list_member_conventions` already does for the Member handbook; extracted here so
    the PM-facing project-scoped queries below reuse it instead of a second implementation.
    """
    if not family_ids:
        return {}
    evidence_rows = (
        await db.execute(
            select(RuleEvidence.rule_family_id, RuleEvidence.evidence_unit_id).where(
                RuleEvidence.rule_family_id.in_(family_ids)
            )
        )
    ).all()
    raw_comment_ids = {_raw_pr_comment_id(evidence_unit_id) for _, evidence_unit_id in evidence_rows}
    repo_by_comment_id: dict[int, str] = (
        dict(
            (
                await db.execute(
                    select(RawPrComment.raw_pr_comment_id, RawPrComment.repo).where(
                        RawPrComment.raw_pr_comment_id.in_(raw_comment_ids)
                    )
                )
            ).all()
        )
        if raw_comment_ids
        else {}
    )
    repos_by_family: dict[int, set[str]] = {}
    for family_id, evidence_unit_id in evidence_rows:
        repo = repo_by_comment_id.get(_raw_pr_comment_id(evidence_unit_id))
        if repo is not None:
            repos_by_family.setdefault(family_id, set()).add(repo)
    return {
        family_id: (repos.pop() if len(repos) == 1 else None)
        for family_id, repos in repos_by_family.items()
    }


async def _list_by_status(
    db: AsyncSession,
    family_status: RuleFamilyStatus,
    *,
    page: int,
    page_size: int,
    repo: str | None = None,
) -> RuleFamilyListDTO:
    """`repo=None` (the default) is unfiltered/company-wide — the one remaining caller of this
    is the global `GET /conventions` endpoint the chat Member Conventions panel depends on
    (out of scope for the F6 project-ACL fix). Every PM-facing caller now passes a real `repo`.
    """
    rows = list(
        (
            await db.scalars(
                select(RuleFamily)
                .where(RuleFamily.status == family_status)
                .order_by(RuleFamily.rule_family_id.desc())
            )
        ).all()
    )
    if repo is not None:
        family_repos = await _resolve_family_repos(db, [family.rule_family_id for family in rows])
        rows = [family for family in rows if family_repos.get(family.rule_family_id) == repo]

    total = len(rows)
    page_rows = rows[(page - 1) * page_size : (page - 1) * page_size + page_size]
    items = await _build_items(db, page_rows)
    return RuleFamilyListDTO(items=items, meta=PageMetaDTO(page=page, page_size=page_size, total=total))


async def list_pending(
    db: AsyncSession, *, page: int, page_size: int, repo: str | None = None
) -> RuleFamilyListDTO:
    return await _list_by_status(db, RuleFamilyStatus.PENDING, page=page, page_size=page_size, repo=repo)


async def list_approved(
    db: AsyncSession, *, page: int, page_size: int, repo: str | None = None
) -> RuleFamilyListDTO:
    return await _list_by_status(db, RuleFamilyStatus.APPROVED, page=page, page_size=page_size, repo=repo)


_FENCED_CODE_BLOCK = re.compile(r"```[^\n`]*\n(.*?)```", re.DOTALL)


async def list_member_conventions(
    db: AsyncSession, *, project_id: int, page: int, page_size: int
) -> MemberConventionListDTO:
    """Return the approved handbook projection for one server-authorized project.

    F6 families predate a direct ``project_id`` column. Their immutable evidence units point
    to persisted raw PR comments, whose repository is the same project mapping used by the F6
    ingestion path. Resolving that mapping here keeps the handbook a structured DB read and
    prevents an approved convention from another repository leaking across project boundaries.
    """

    project = await db.get(Project, project_id)
    if project is None or not project.github_repo:
        return MemberConventionListDTO(
            items=[], meta=PageMetaDTO(page=page, page_size=page_size, total=0)
        )

    families = (
        await db.scalars(
            select(RuleFamily)
            .where(RuleFamily.status == RuleFamilyStatus.APPROVED)
            .order_by(RuleFamily.rule_family_id.desc())
        )
    ).all()
    if not families:
        return MemberConventionListDTO(
            items=[], meta=PageMetaDTO(page=page, page_size=page_size, total=0)
        )

    family_ids = [family.rule_family_id for family in families]
    evidence_rows = (
        await db.execute(
            select(RuleEvidence, RuleCandidate.rule_text_draft)
            .join(RuleCandidate, RuleCandidate.rule_candidate_id == RuleEvidence.rule_candidate_id)
            .where(RuleEvidence.rule_family_id.in_(family_ids))
            .order_by(RuleEvidence.rule_evidence_id)
        )
    ).all()
    raw_comment_ids = {_raw_pr_comment_id(evidence.evidence_unit_id) for evidence, _ in evidence_rows}
    raw_comments = (
        await db.scalars(
            select(RawPrComment).where(RawPrComment.raw_pr_comment_id.in_(raw_comment_ids))
        )
    ).all()
    source_by_id = {source.raw_pr_comment_id: source for source in raw_comments}

    members_by_family: dict[int, list[tuple[RuleEvidence, str]]] = {}
    for evidence, rule_text in evidence_rows:
        members_by_family.setdefault(evidence.rule_family_id, []).append((evidence, rule_text))

    scoped: list[MemberConventionItemDTO] = []
    for family in families:
        members = members_by_family.get(family.rule_family_id, [])
        source_ids = {_raw_pr_comment_id(evidence.evidence_unit_id) for evidence, _ in members}
        # A family is mined from one repository; require every persisted source to match the
        # active project rather than treating a partial/malformed provenance set as authorized.
        if not source_ids or any(
            source_by_id.get(source_id) is None
            or source_by_id[source_id].repo != project.github_repo
            for source_id in source_ids
        ):
            continue

        anchor = select_anchor([evidence for evidence, _ in members])
        rule_text = next((text for evidence, text in members if evidence is anchor), "")
        evidence_items: list[MemberConventionEvidenceDTO] = []
        actual_examples: list[MemberConventionExampleDTO] = []
        for evidence, _ in members:
            source = source_by_id[_raw_pr_comment_id(evidence.evidence_unit_id)]
            permalink = source.url
            snippet = redact(evidence.comment_snippet_snapshot)[0]
            evidence_items.append(
                MemberConventionEvidenceDTO(
                    comment_snippet_snapshot=snippet,
                    code_snippet_snapshot=(
                        redact(source.code_snippet_snapshot)[0]
                        if source.code_snippet_snapshot is not None
                        else None
                    ),
                    code_before_snapshot=(
                        redact(source.code_before_snapshot)[0]
                        if source.code_before_snapshot is not None
                        else None
                    ),
                    code_after_snapshot=(
                        redact(source.code_after_snapshot)[0]
                        if source.code_after_snapshot is not None
                        else None
                    ),
                    original_author=evidence.original_author,
                    pr_number=evidence.pr_number,
                    evidence_created_at=evidence.evidence_created_at,
                    permalink=permalink,
                )
            )
            # This is extraction, not reconstruction: the code is only shown when a complete
            # fenced block was already captured in the immutable review snapshot.
            for match in _FENCED_CODE_BLOCK.finditer(snippet):
                code = match.group(1).strip("\n")
                if code:
                    actual_examples.append(
                        MemberConventionExampleDTO(
                            code=code,
                            pr_number=evidence.pr_number,
                            original_author=evidence.original_author,
                            permalink=permalink,
                        )
                    )

        scoped.append(
            MemberConventionItemDTO(
                rule_family_id=family.rule_family_id,
                rule_text=rule_text,
                actual_examples=actual_examples,
                evidence=evidence_items,
            )
        )

    total = len(scoped)
    start = (page - 1) * page_size
    return MemberConventionListDTO(
        items=scoped[start : start + page_size],
        meta=PageMetaDTO(page=page, page_size=page_size, total=total),
    )


async def _ensure_family_in_repo(db: AsyncSession, rule_family_id: int, repo: str) -> None:
    """PM-facing ACL boundary for a single family: 404 (not 403) if it doesn't resolve to the
    caller's project's repo — same as any other cross-project resource lookup in this codebase,
    so this doesn't confirm to an unauthorized PM that a family from another repo even exists.
    """
    family_repos = await _resolve_family_repos(db, [rule_family_id])
    if family_repos.get(rule_family_id) != repo:
        raise RuleFamilyNotFoundError(rule_family_id)


async def _apply_decision(
    db: AsyncSession, rule_family_id: int, new_status: RuleFamilyStatus, reviewer: User
) -> RuleFamilyActionResultDTO:
    now = datetime.now(UTC).replace(tzinfo=None)
    values: dict[str, object] = {"status": new_status}
    if new_status == RuleFamilyStatus.APPROVED:
        values["approved_by"] = reviewer.user_id
        values["approved_at"] = now
    else:
        values["rejected_by"] = reviewer.user_id
        values["rejected_at"] = now

    # Optimistic lock: the WHERE status=PENDING clause is the whole guard. If another
    # reviewer already decided this family, rowcount is 0 and nothing is overwritten.
    result = await db.execute(
        update(RuleFamily)
        .where(RuleFamily.rule_family_id == rule_family_id, RuleFamily.status == RuleFamilyStatus.PENDING)
        .values(**values)
    )
    if result.rowcount == 0:
        await db.rollback()
        existing = await db.get(RuleFamily, rule_family_id)
        if existing is None:
            raise RuleFamilyNotFoundError(rule_family_id)
        raise RuleFamilyAlreadyReviewedError(rule_family_id)

    await db.commit()
    family = await db.get(RuleFamily, rule_family_id)
    assert family is not None
    return RuleFamilyActionResultDTO(
        rule_family_id=family.rule_family_id,
        status=family.status,
        approved_by=family.approved_by,
        approved_at=family.approved_at,
        rejected_by=family.rejected_by,
        rejected_at=family.rejected_at,
    )


async def _index_approved_family(
    db: AsyncSession, rule_family_id: int, embedder: Embedder | None, *, actor_user_id: int
) -> bool:
    """Push one approved family into the shared retrieval engine. Never raises.

    Phase 10 §4 — event-driven, in the approve flow itself, no cron sweep and no message
    queue. The approval is already committed by `_apply_decision` before this runs, and that
    ordering is the design: approval is a human decision and must not be undone because an
    embedding call timed out. A failure here therefore leaves the family APPROVED, logs loud
    enough to find, and is recoverable through `reindex()` — never a silent drop.

    The bare `except Exception` is deliberate, not the F-07 anti-pattern: this is not guessing
    at an SDK's exception names, it is an explicit "nothing that happens downstream may fail
    the approval" boundary, and everything caught is logged with a traceback.
    """
    if embedder is None:
        logger.warning(
            "rule_family %s approved without an embedder; not indexed for F5 retrieval. "
            "Call reindex() with an embedder to make it answerable.",
            rule_family_id,
        )
        return False
    try:
        # A SAVEPOINT, not a plain rollback: a failed ingest must undo its own partial writes
        # and nothing else. Rolling the whole session back here would also expire the caller's
        # already-committed objects, letting an ingest problem corrupt state that has nothing
        # to do with it.
        async with db.begin_nested():
            document = await ingest_approved_rule_family(
                db, rule_family_id, embedder, actor_user_id=actor_user_id
            )
        await db.commit()
    except ConventionIngestError:
        logger.exception(
            "rule_family %s approved but NOT indexed for F5 retrieval (content/scope problem). "
            "Approval stands; retry with reindex().",
            rule_family_id,
        )
        return False
    except Exception:
        logger.exception(
            "rule_family %s approved but NOT indexed for F5 retrieval (ingest failed). "
            "Approval stands; retry with reindex().",
            rule_family_id,
        )
        return False
    logger.info(
        "rule_family %s indexed for F5 retrieval as knowledge_document %s",
        rule_family_id,
        document.document_id,
    )
    return True


async def approve(
    db: AsyncSession,
    rule_family_id: int,
    reviewer: User,
    *,
    repo: str,
    embedder: Embedder | None = None,
) -> RuleFamilyActionResultDTO:
    await _ensure_family_in_repo(db, rule_family_id, repo)
    actor_user_id = reviewer.user_id
    outcome = await _apply_decision(db, rule_family_id, RuleFamilyStatus.APPROVED, reviewer)
    indexed = await _index_approved_family(
        db, rule_family_id, embedder, actor_user_id=actor_user_id
    )
    return outcome.model_copy(update={"retrieval_indexed": indexed})


async def reject(
    db: AsyncSession, rule_family_id: int, reviewer: User, *, repo: str
) -> RuleFamilyActionResultDTO:
    # No cascade delete of the indexed chunk is needed here, and none is written on purpose:
    # `_apply_decision` transitions only `WHERE status = PENDING`, so APPROVED is terminal and
    # a family can never be rejected after it was approved (Phase 6 §2, confirmed in code, not
    # inferred from prose). If that guard is ever relaxed, this is the place that has to grow
    # a matching un-index step.
    await _ensure_family_in_repo(db, rule_family_id, repo)
    return await _apply_decision(db, rule_family_id, RuleFamilyStatus.REJECTED, reviewer)


async def reindex(
    db: AsyncSession, rule_family_id: int, *, repo: str, actor_user_id: int, embedder: Embedder
) -> RuleFamilyActionResultDTO:
    """Manual retry for an approved family whose ingest failed (Phase 10 §4).

    Takes an actor id rather than a `User` on purpose: re-indexing is an operational retry,
    not a review decision, and a plain int stays readable on a session whose ORM instances an
    earlier failed ingest already expired by rolling back.

    Idempotent: the ingest core resolves the document by `source_key` and short-circuits on an
    unchanged checksum, so re-running on an already-indexed family updates nothing.
    """
    await _ensure_family_in_repo(db, rule_family_id, repo)
    family = await db.get(RuleFamily, rule_family_id)
    if family is None:
        raise RuleFamilyNotFoundError(rule_family_id)
    if family.status is not RuleFamilyStatus.APPROVED:
        raise RuleFamilyNotApprovedError(rule_family_id)
    indexed = await _index_approved_family(db, rule_family_id, embedder, actor_user_id=actor_user_id)
    family = await db.get(RuleFamily, rule_family_id)
    assert family is not None
    return RuleFamilyActionResultDTO(
        rule_family_id=family.rule_family_id,
        status=family.status,
        approved_by=family.approved_by,
        approved_at=family.approved_at,
        rejected_by=family.rejected_by,
        rejected_at=family.rejected_at,
        retrieval_indexed=indexed,
    )
