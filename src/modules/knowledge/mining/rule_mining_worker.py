"""F6_RULE_MINING_SPEC.md §4.2 — RuleMiningWorker orchestrator, one-shot (no incremental
mining, §4.6). Ties together: noise/bot filter -> evidence-unit grouping -> LLM extraction
(one call/unit, no tool-calling) -> eligibility filter -> embed rule_text_draft -> connected-
components clustering -> query-layer eligibility guardrail (§5.3) -> snapshot persistence.

Does not re-run secret scanning: `raw_pr_comments` rows were already scanned at F2 ingestion
time (Phase 3) — this worker only reads rows where `secret_scanned_at IS NOT NULL`, per
CLAUDE.md Phase 5 §1.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime

from langchain_openai import ChatOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.providers.embeddings import Embedder
from src.ai.retrieval_engine.chunking_config import rule_mining_params
from src.infrastructure.observability.langfuse import flush_traces
from src.model.enums import RuleFamilyStatus
from src.model.llm_call_log import LlmCallLog
from src.model.raw_pr_comment import RawPrComment
from src.model.rule_candidate import RuleCandidate
from src.model.rule_evidence import RuleEvidence
from src.model.rule_family import RuleFamily
from src.modules.knowledge.ingestion.pr_corpus_filters import is_noise
from src.modules.knowledge.mining.clustering import cluster_by_cosine
from src.modules.knowledge.mining.convention_ingestion import select_anchor
from src.modules.knowledge.mining.eligibility import prune_ineligible_families
from src.modules.knowledge.mining.evidence_grouping import EvidenceUnit, group_comments_into_evidence_units
from src.modules.knowledge.mining.rule_extraction import (
    ELIGIBLE_EVIDENCE_TYPES,
    RuleCandidateExtraction,
    extract_rule_candidates,
)


@dataclass
class MiningSummary:
    repo: str
    comments_loaded: int = 0
    comments_after_noise_filter: int = 0
    evidence_units_total: int = 0
    evidence_units_eligible: int = 0
    evidence_units_filtered_out: dict[str, int] = field(default_factory=dict)
    # Extraction failures are distinct from a semantic "not reusable" verdict.
    evidence_units_extraction_failed: list[str] = field(default_factory=list)
    candidate_families: int = 0
    families_created: int = 0
    families_pruned_ineligible: int = 0
    # Used by mine_new_evidence(); mine_rules() never reinforces a family.
    families_reinforced: int = 0
    # Conflicting pending families are not auto-merged.
    family_merge_conflicts_skipped: int = 0


async def _load_repo_comments(session: AsyncSession, repo: str) -> list[RawPrComment]:
    """Load secret-scanned, non-bot comments using ingestion's bot classification."""
    rows = (
        await session.scalars(
            select(RawPrComment).where(
                RawPrComment.repo == repo,
                RawPrComment.secret_scanned_at.is_not(None),
                RawPrComment.is_bot_comment.is_(False),
            )
        )
    ).all()
    return list(rows)


async def mine_rules(
    session: AsyncSession,
    llm: ChatOpenAI,
    embedder: Embedder,
    *,
    repo: str,
    trace_id_prefix: str = "f6-mining",
) -> MiningSummary:
    clustering_config = rule_mining_params()["clustering"]
    merge_threshold = float(clustering_config["cosine_merge_threshold"])

    summary = MiningSummary(repo=repo)
    loaded = await _load_repo_comments(session, repo)
    summary.comments_loaded = len(loaded)
    comments = [row for row in loaded if not is_noise(row.body)]
    summary.comments_after_noise_filter = len(comments)

    units = group_comments_into_evidence_units(comments)
    summary.evidence_units_total = len(units)

    # Complete concurrent extraction before writing through this single session.
    results = await extract_rule_candidates(llm, units)

    # Sequential from here on — a single AsyncSession is never written to concurrently.
    extractions: list[RuleCandidateExtraction] = []
    for extraction in results:
        unit_id = extraction.unit.evidence_unit_id
        # Eligible results require a non-empty rule draft.
        invalid_output = extraction.eligible and not extraction.rule_text_draft.strip()

        if extraction.error is not None or invalid_output:
            gate_decision = "extraction_failed" if extraction.error is not None else "invalid_output"
            decision_details = (
                {"error": extraction.error}
                if extraction.error is not None
                else {
                    "evidence_type": extraction.evidence_type.value,
                    "reuse_scope": extraction.reuse_scope,
                    "reason": "blank rule_text_draft despite eligible classification",
                }
            )
            summary.evidence_units_extraction_failed.append(unit_id)
        else:
            gate_decision = "eligible" if extraction.eligible else "filtered_out"
            decision_details = {
                "evidence_type": extraction.evidence_type.value,
                "reuse_scope": extraction.reuse_scope,
            }

        # Mark terminal outcomes; leave failed units available for incremental retry.
        if gate_decision in ("eligible", "filtered_out"):
            extraction.unit.comments[0].mining_processed_at = datetime.now(UTC).replace(tzinfo=None)

        session.add(
            LlmCallLog(
                trace_id=f"{trace_id_prefix}:{unit_id}"[:64],
                module="rule_mining",
                stage="extraction",
                gate_decision=gate_decision,
                prompt_tokens=extraction.prompt_tokens,
                completion_tokens=extraction.completion_tokens,
                latency_ms=extraction.latency_ms,
                model=extraction.model,
                retry_count=0,
                error_code=(extraction.error or "")[:64] or None,
                decision_details=decision_details,
            )
        )

        if gate_decision in ("extraction_failed", "invalid_output"):
            continue
        if gate_decision == "filtered_out":
            key = extraction.evidence_type.value
            summary.evidence_units_filtered_out[key] = summary.evidence_units_filtered_out.get(key, 0) + 1
            continue
        extractions.append(extraction)
    await session.commit()

    summary.evidence_units_eligible = len(extractions)
    if not extractions:
        # Flush extraction traces even when no units are eligible.
        flush_traces()
        return summary

    # Step 4 — embed rule_text_draft only, never the raw body (SPEC §4.3).
    vector_list = await embedder.embed([e.rule_text_draft for e in extractions])
    vectors = {e.unit.evidence_unit_id: vector for e, vector in zip(extractions, vector_list, strict=True)}
    extraction_by_unit_id = {e.unit.evidence_unit_id: e for e in extractions}

    # Persist each eligible candidate, whether or not it joins a family.
    candidate_by_unit_id: dict[str, RuleCandidate] = {}
    for extraction in extractions:
        candidate = RuleCandidate(
            evidence_type=extraction.evidence_type,
            reuse_scope=extraction.reuse_scope,
            rule_text_draft=extraction.rule_text_draft,
            rationale=extraction.rationale,
        )
        session.add(candidate)
        candidate_by_unit_id[extraction.unit.evidence_unit_id] = candidate
    await session.flush()

    # Step 5 — connected components. Clustering itself knows nothing about PR distribution;
    # the >=2-distinct-PR guardrail is a separate, later step (step 6 below).
    components = cluster_by_cosine(vectors, merge_threshold=merge_threshold)
    multi_node_components = [c for c in components if len(c.node_ids) >= 2]
    summary.candidate_families = len(multi_node_components)

    created_family_ids: set[int] = set()
    for component in multi_node_components:
        member_extractions = [extraction_by_unit_id[node_id] for node_id in component.node_ids]
        distinct_reviewer_count = len(
            {author for extraction in member_extractions for author in extraction.unit.distinct_authors}
        )
        family = RuleFamily(distinct_reviewer_count=distinct_reviewer_count)
        session.add(family)
        await session.flush()
        created_family_ids.add(family.rule_family_id)

        for extraction in member_extractions:
            candidate = candidate_by_unit_id[extraction.unit.evidence_unit_id]
            root = extraction.unit.comments[0]
            session.add(
                RuleEvidence(
                    rule_candidate_id=candidate.rule_candidate_id,
                    rule_family_id=family.rule_family_id,
                    evidence_unit_id=extraction.unit.evidence_unit_id,
                    pr_number=extraction.unit.pr_number,
                    comment_snippet_snapshot="\n\n---\n\n".join(extraction.unit.bodies),
                    original_author=root.author,
                    evidence_created_at=root.created_at,
                    cluster_edge_cosine_similarity=component.edge_cosine[extraction.unit.evidence_unit_id],
                )
            )
    await session.commit()
    summary.families_created = len(created_family_ids)

    # Apply the PR-distribution guardrail after clustering.
    pruned = await prune_ineligible_families(session, created_family_ids)
    summary.families_pruned_ineligible = len(pruned)
    summary.families_created -= len(pruned)

    # This background job owns its trace flush.
    flush_traces()
    return summary


def _raw_pr_comment_id(evidence_unit_id: str) -> int:
    # Same business-key format `rule_review_service`/`convention_ingestion` each parse locally
    # (private helper, "<type>:<raw_pr_comment_id>") — not imported from either, matching this
    # codebase's existing small-duplication-over-coupling convention for this one-liner.
    return int(evidence_unit_id.rsplit(":", 1)[1])


@dataclass(frozen=True)
class _MemberFields:
    """The exact fields a RuleEvidence row needs, regardless of whether the member is a
    brand-new extraction (unit_id key) or a reused orphan RuleCandidate (orphan:<id> key)."""

    evidence_unit_id: str
    pr_number: int
    comment_snippet_snapshot: str
    original_author: str
    evidence_created_at: datetime


def _resolve_member(
    node_id: str,
    candidate_by_unit_id: dict[str, RuleCandidate],
    orphan_by_key: dict[str, RuleCandidate],
    extraction_by_unit_id: dict[str, RuleCandidateExtraction],
) -> tuple[RuleCandidate, _MemberFields]:
    if node_id.startswith("orphan:"):
        candidate = orphan_by_key[node_id]
        assert candidate.evidence_unit_id is not None  # orphan pool is pre-filtered on this
        return candidate, _MemberFields(
            evidence_unit_id=candidate.evidence_unit_id,
            pr_number=candidate.pr_number,  # type: ignore[arg-type]
            comment_snippet_snapshot=candidate.comment_snippet_snapshot,  # type: ignore[arg-type]
            original_author=candidate.original_author,  # type: ignore[arg-type]
            evidence_created_at=candidate.evidence_created_at,  # type: ignore[arg-type]
        )
    extraction = extraction_by_unit_id[node_id]
    root = extraction.unit.comments[0]
    return candidate_by_unit_id[node_id], _MemberFields(
        evidence_unit_id=extraction.unit.evidence_unit_id,
        pr_number=extraction.unit.pr_number,
        comment_snippet_snapshot="\n\n---\n\n".join(extraction.unit.bodies),
        original_author=root.author,
        evidence_created_at=root.created_at,
    )


async def _load_repo_comment_ids(session: AsyncSession, repo: str) -> set[int]:
    rows = await session.scalars(select(RawPrComment.raw_pr_comment_id).where(RawPrComment.repo == repo))
    return set(rows.all())


async def _load_repo_orphan_candidates(
    session: AsyncSession, repo_comment_ids: set[int]
) -> list[RuleCandidate]:
    """Eligible RuleCandidates with no RuleEvidence row yet (never clustered into a family),
    scoped to this repo via their persisted `evidence_unit_id` -> RawPrComment.raw_pr_comment_id.
    Rows created before this feature (evidence_unit_id IS NULL) can never be reused this way —
    a documented gap, not a crash (RuleCandidate.evidence_unit_id's docstring)."""
    has_evidence = select(RuleEvidence.rule_candidate_id)
    rows = (
        await session.scalars(
            select(RuleCandidate).where(
                RuleCandidate.evidence_type.in_(ELIGIBLE_EVIDENCE_TYPES),
                RuleCandidate.reuse_scope >= 1,
                RuleCandidate.evidence_unit_id.is_not(None),
                RuleCandidate.rule_candidate_id.not_in(has_evidence),
            )
        )
    ).all()
    return [c for c in rows if _raw_pr_comment_id(c.evidence_unit_id) in repo_comment_ids]  # type: ignore[arg-type]


async def _load_repo_pending_family_anchor_vectors(
    session: AsyncSession, repo_comment_ids: set[int], embedder: Embedder
) -> dict[int, list[float]]:
    """One anchor embedding per existing PENDING RuleFamily whose evidence belongs to this repo.
    Re-embeds (and persists) on demand when the anchor's RuleCandidate has no stored embedding
    (every family mined before this feature) or a stale `embedding_model_version` — cheap,
    embed-only, no LLM call, and self-heals legacy rows for the next run too."""
    rows = (
        await session.execute(
            select(RuleEvidence, RuleCandidate)
            .join(RuleFamily, RuleFamily.rule_family_id == RuleEvidence.rule_family_id)
            .join(RuleCandidate, RuleCandidate.rule_candidate_id == RuleEvidence.rule_candidate_id)
            .where(RuleFamily.status == RuleFamilyStatus.PENDING)
        )
    ).all()

    by_family: dict[int, list[tuple[RuleEvidence, RuleCandidate]]] = defaultdict(list)
    for evidence, candidate in rows:
        if _raw_pr_comment_id(evidence.evidence_unit_id) in repo_comment_ids:
            by_family[evidence.rule_family_id].append((evidence, candidate))

    anchors: dict[int, list[float]] = {}
    for family_id, members in by_family.items():
        anchor_evidence = select_anchor([m[0] for m in members])
        assert anchor_evidence is not None  # members is non-empty by construction
        anchor_candidate = next(
            c for e, c in members if e.rule_evidence_id == anchor_evidence.rule_evidence_id
        )
        vector = anchor_candidate.embedding
        if vector is None or anchor_candidate.embedding_model_version != embedder.model_version:
            vector = (await embedder.embed([anchor_candidate.rule_text_draft]))[0]
            anchor_candidate.embedding = vector
            anchor_candidate.embedding_model_version = embedder.model_version
        anchors[family_id] = list(vector)
    return anchors


async def _recompute_reviewer_count(session: AsyncSession, family_id: int) -> None:
    authors = await session.scalars(
        select(RuleEvidence.original_author).where(RuleEvidence.rule_family_id == family_id)
    )
    family = await session.get(RuleFamily, family_id)
    assert family is not None
    family.distinct_reviewer_count = len(set(authors.all()))


async def mine_new_evidence(
    session: AsyncSession,
    llm: ChatOpenAI,
    embedder: Embedder,
    *,
    repo: str,
    trace_id_prefix: str = "f6-discovery",
) -> MiningSummary:
    """Incremental sibling of mine_rules() (F6 Scheduled Incremental Convention Discovery).

    Reuses every primitive unchanged (noise filter, evidence grouping, extract_rule_candidates,
    cluster_by_cosine, prune_ineligible_families) — no second clustering algorithm, no second
    LLM call shape. The only differences from mine_rules(): (1) only evidence units whose root
    comment has no `mining_processed_at` yet are extracted; (2) the clustering pool also
    includes existing orphan RuleCandidates and one anchor vector per existing PENDING
    RuleFamily, so a resulting multi-node component either REINFORCES an existing family (new
    RuleEvidence rows, no re-run of the eligibility guardrail — adding evidence can only help
    meet a >=2 threshold, never hurt it) or CREATES a new one exactly as mine_rules() does.

    APPROVED/REJECTED families are excluded from the pool on purpose — see
    convention_discovery.py's module docstring for the product decision.
    """
    clustering_config = rule_mining_params()["clustering"]
    merge_threshold = float(clustering_config["cosine_merge_threshold"])

    summary = MiningSummary(repo=repo)
    loaded = await _load_repo_comments(session, repo)
    summary.comments_loaded = len(loaded)
    comments = [row for row in loaded if not is_noise(row.body)]
    summary.comments_after_noise_filter = len(comments)

    # Grouped over ALL loaded comments (not just new ones) so a new reply's chain still
    # resolves to its true root even if that root is old — then filtered to unprocessed units
    # only. A unit whose root is already processed stays skipped even if a brand new reply just
    # landed on it: an evidence unit's boundary is frozen once processed (known simplification,
    # documented in the F6 Scheduled Incremental Convention Discovery plan).
    all_units: list[EvidenceUnit] = group_comments_into_evidence_units(comments)
    # Second, authoritative guard alongside `mining_processed_at IS NULL`: a unit whose
    # evidence_unit_id already has a RuleEvidence row is never re-extracted, independent of
    # whether `mining_processed_at` was actually set. This is what makes a re-run safe against
    # a repo whose evidence was seeded by the older, one-shot `mine_rules()` (which historically
    # never set `mining_processed_at` — see the comment there) or against any other drift
    # between the two fields; without it, re-extracting an already-evidenced unit collides on
    # uq_rule_evidences_evidence_unit_id when the resulting family is persisted below.
    existing_evidence_unit_ids = set(
        (await session.scalars(select(RuleEvidence.evidence_unit_id))).all()
    )
    units = [
        u
        for u in all_units
        if u.comments[0].mining_processed_at is None
        and u.evidence_unit_id not in existing_evidence_unit_ids
    ]
    summary.evidence_units_total = len(units)

    if not units:
        flush_traces()
        return summary

    results = await extract_rule_candidates(llm, units)

    extractions: list[RuleCandidateExtraction] = []
    for extraction in results:
        unit_id = extraction.unit.evidence_unit_id
        invalid_output = extraction.eligible and not extraction.rule_text_draft.strip()

        if extraction.error is not None or invalid_output:
            gate_decision = "extraction_failed" if extraction.error is not None else "invalid_output"
            decision_details = (
                {"error": extraction.error}
                if extraction.error is not None
                else {
                    "evidence_type": extraction.evidence_type.value,
                    "reuse_scope": extraction.reuse_scope,
                    "reason": "blank rule_text_draft despite eligible classification",
                }
            )
            summary.evidence_units_extraction_failed.append(unit_id)
        else:
            gate_decision = "eligible" if extraction.eligible else "filtered_out"
            decision_details = {
                "evidence_type": extraction.evidence_type.value,
                "reuse_scope": extraction.reuse_scope,
            }

        session.add(
            LlmCallLog(
                trace_id=f"{trace_id_prefix}:{unit_id}"[:64],
                module="rule_mining",
                stage="extraction",
                gate_decision=gate_decision,
                prompt_tokens=extraction.prompt_tokens,
                completion_tokens=extraction.completion_tokens,
                latency_ms=extraction.latency_ms,
                model=extraction.model,
                retry_count=0,
                error_code=(extraction.error or "")[:64] or None,
                decision_details=decision_details,
            )
        )

        # Terminal outcome only — extraction_failed/invalid_output stay unmarked so this unit
        # retries on the next incremental run instead of being silently skipped forever.
        if gate_decision in ("eligible", "filtered_out"):
            extraction.unit.comments[0].mining_processed_at = datetime.now(UTC).replace(tzinfo=None)

        if gate_decision in ("extraction_failed", "invalid_output"):
            continue
        if gate_decision == "filtered_out":
            key = extraction.evidence_type.value
            summary.evidence_units_filtered_out[key] = summary.evidence_units_filtered_out.get(key, 0) + 1
            continue
        extractions.append(extraction)
    await session.commit()

    summary.evidence_units_eligible = len(extractions)
    if not extractions:
        flush_traces()
        return summary

    vector_list = await embedder.embed([e.rule_text_draft for e in extractions])
    extraction_by_unit_id = {e.unit.evidence_unit_id: e for e in extractions}

    # Snapshot the existing orphan/PENDING-family pool BEFORE this run's own new candidates are
    # created — otherwise a brand-new candidate would still have no RuleEvidence row yet at
    # query time and would match itself as an "orphan", clustering with its own unit_id key and
    # producing two RuleEvidence rows for the same evidence_unit_id (UNIQUE violation).
    repo_comment_ids = await _load_repo_comment_ids(session, repo)
    orphan_candidates = await _load_repo_orphan_candidates(session, repo_comment_ids)
    orphan_by_key: dict[str, RuleCandidate] = {}
    vectors: dict[str, list[float]] = {}
    for candidate in orphan_candidates:
        key = f"orphan:{candidate.rule_candidate_id}"
        vec = candidate.embedding
        if vec is None or candidate.embedding_model_version != embedder.model_version:
            vec = (await embedder.embed([candidate.rule_text_draft]))[0]
            candidate.embedding = vec
            candidate.embedding_model_version = embedder.model_version
        vectors[key] = list(vec)
        orphan_by_key[key] = candidate

    family_anchors = await _load_repo_pending_family_anchor_vectors(session, repo_comment_ids, embedder)
    for family_id, vector in family_anchors.items():
        vectors[f"family:{family_id}"] = vector
    await session.flush()  # persist any re-embedded orphan/anchor vectors above

    candidate_by_unit_id: dict[str, RuleCandidate] = {}
    for extraction, vector in zip(extractions, vector_list, strict=True):
        root = extraction.unit.comments[0]
        candidate = RuleCandidate(
            evidence_type=extraction.evidence_type,
            reuse_scope=extraction.reuse_scope,
            rule_text_draft=extraction.rule_text_draft,
            rationale=extraction.rationale,
            embedding=vector,
            embedding_model_version=embedder.model_version,
            evidence_unit_id=extraction.unit.evidence_unit_id,
            pr_number=extraction.unit.pr_number,
            comment_snippet_snapshot="\n\n---\n\n".join(extraction.unit.bodies),
            original_author=root.author,
            evidence_created_at=root.created_at,
        )
        session.add(candidate)
        candidate_by_unit_id[extraction.unit.evidence_unit_id] = candidate
        vectors[extraction.unit.evidence_unit_id] = vector
    await session.flush()

    components = cluster_by_cosine(vectors, merge_threshold=merge_threshold)
    multi_node_components = [c for c in components if len(c.node_ids) >= 2]
    summary.candidate_families = len(multi_node_components)

    created_family_ids: set[int] = set()
    reinforced_family_ids: set[int] = set()

    for component in multi_node_components:
        family_keys = [n for n in component.node_ids if n.startswith("family:")]
        if len(family_keys) > 1:
            # A component touching >=2 existing PENDING families at once — never auto-merge
            # two independently-pending review items. Left for a human/future run to notice.
            summary.family_merge_conflicts_skipped += 1
            continue

        member_node_ids = [n for n in component.node_ids if n not in family_keys]

        if family_keys:
            family_id = int(family_keys[0].split(":", 1)[1])
            for node_id in member_node_ids:
                candidate, fields = _resolve_member(
                    node_id, candidate_by_unit_id, orphan_by_key, extraction_by_unit_id
                )
                session.add(
                    RuleEvidence(
                        rule_candidate_id=candidate.rule_candidate_id,
                        rule_family_id=family_id,
                        evidence_unit_id=fields.evidence_unit_id,
                        pr_number=fields.pr_number,
                        comment_snippet_snapshot=fields.comment_snippet_snapshot,
                        original_author=fields.original_author,
                        evidence_created_at=fields.evidence_created_at,
                        cluster_edge_cosine_similarity=component.edge_cosine[node_id],
                    )
                )
            reinforced_family_ids.add(family_id)
        else:
            distinct_authors: set[str] = set()
            resolved: list[tuple[RuleCandidate, _MemberFields]] = []
            for node_id in member_node_ids:
                candidate, fields = _resolve_member(
                    node_id, candidate_by_unit_id, orphan_by_key, extraction_by_unit_id
                )
                resolved.append((candidate, fields))
                distinct_authors.add(fields.original_author)

            family = RuleFamily(distinct_reviewer_count=len(distinct_authors))
            session.add(family)
            await session.flush()
            created_family_ids.add(family.rule_family_id)

            for node_id, (candidate, fields) in zip(member_node_ids, resolved, strict=True):
                session.add(
                    RuleEvidence(
                        rule_candidate_id=candidate.rule_candidate_id,
                        rule_family_id=family.rule_family_id,
                        evidence_unit_id=fields.evidence_unit_id,
                        pr_number=fields.pr_number,
                        comment_snippet_snapshot=fields.comment_snippet_snapshot,
                        original_author=fields.original_author,
                        evidence_created_at=fields.evidence_created_at,
                        cluster_edge_cosine_similarity=component.edge_cosine[node_id],
                    )
                )

    for family_id in reinforced_family_ids:
        await _recompute_reviewer_count(session, family_id)
    await session.commit()

    summary.families_created = len(created_family_ids)
    summary.families_reinforced = len(reinforced_family_ids)

    pruned = await prune_ineligible_families(session, created_family_ids)
    summary.families_pruned_ineligible = len(pruned)
    summary.families_created -= len(pruned)

    flush_traces()
    return summary
