"""F6 Phase 10 — an APPROVED RuleFamily becomes retrievable knowledge for F5.

This module is an **adapter, not a pipeline**. Everything below ends in one call to
`src.modules.knowledge.ingestion.versioning.ingest_or_update` — the same core GitHub sync
(`github_sync_worker`) and PM upload (`knowledge_document_service`) already go through. No
second chunker, no second embedder call, no second secret scanner, no second index: the
"single shared retrieval engine, no second pipeline may exist" invariant (NFR-14) is kept
structurally, by having nothing here that could diverge from it.

Survey result that shaped the design (CLAUDE.md Phase 10 §1) — the retrieval engine has **no
`source_type` column**. Its actual source discriminators, all on `KnowledgeDocument` and all
already consumed by `_ScopedRetriever.scope_predicates`, are:

* `knowledge_domain` — PROJECT | POLICY, the hard scope split;
* `document_category` — the PROJECT-side type, whose `CONVENTION` member already means
  exactly "a convention";
* `source_key` — "stable identity from the source system", unique per domain.

So no field is added to the shared schema. An approved convention is a PROJECT document of
category CONVENTION whose `source_key` carries the F6 namespace, and that prefix is what
tells it apart from the repo-sourced CONVENTION documents already indexed for the same
project.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.providers.embeddings import Embedder
from src.model.document_chunk import DocumentChunk
from src.model.document_version import DocumentVersion
from src.model.enums import (
    DocumentCategory,
    DocumentDomain,
    ProjectStatus,
    RuleFamilyStatus,
    VersionStatus,
)
from src.model.knowledge_document import KnowledgeDocument
from src.model.project import Project
from src.model.raw_pr_comment import RawPrComment
from src.model.rule_candidate import RuleCandidate
from src.model.rule_evidence import RuleEvidence
from src.model.rule_family import RuleFamily
from src.modules.knowledge.ingestion.versioning import ProjectIngestRequest, ingest_or_update

logger = logging.getLogger(__name__)

# `source_key` namespace for F6 output. This prefix is the *only* thing separating an approved
# convention from a CONVENTION-classified file synced out of the repository, so it must never
# be reused for another source.
CONVENTION_SOURCE_KEY_PREFIX = "f6-rule-family:"

# Where a citation to an approved convention points. Deliberately the Conventions page entry
# and not one evidence permalink: a single PR link reads as "one reviewer's opinion", while
# this route shows what actually justifies the answer — an HITL-approved rule with all N
# evidence behind it (CLAUDE.md Phase 10 §3). The frontend route may not exist yet; this
# constant is the contract it has to match.
CONVENTIONS_ROUTE_PREFIX = "/conventions/"

MISSING_RATIONALE = "Chưa tìm thấy lý do tường minh"


class ConventionIngestError(Exception):
    """Raised when an approved family cannot be turned into a retrievable document.

    Never fatal to the approval itself — see `rule_review_service.approve`.
    """


def convention_source_key(rule_family_id: int) -> str:
    return f"{CONVENTION_SOURCE_KEY_PREFIX}{rule_family_id}"


def rule_family_id_from_source_key(source_key: str | None) -> int | None:
    """Recover the `rule_family_id` metadata from an indexed document.

    NOTE — this is the ONE place in F6 where a live reference is stored instead of an
    immutable snapshot, and it is deliberate, not an oversight. `RuleEvidence` snapshots its
    source comment precisely so the audit trail cannot be rewritten by later upstream edits.
    The retrieval index has the opposite requirement: it must mirror the *current* approval
    state, so it has to be able to name the row whose state it mirrors. Do not "fix" this
    into a snapshot.
    """
    if not source_key or not source_key.startswith(CONVENTION_SOURCE_KEY_PREFIX):
        return None
    suffix = source_key[len(CONVENTION_SOURCE_KEY_PREFIX) :]
    return int(suffix) if suffix.isdigit() else None


def conventions_route(rule_family_id: int) -> str:
    return f"{CONVENTIONS_ROUTE_PREFIX}{rule_family_id}"


def is_conventions_route(url: str | None) -> bool:
    """True for an internal Conventions page route, false for every external artifact URL."""
    return bool(url) and url.startswith(CONVENTIONS_ROUTE_PREFIX)


def select_anchor(members: Sequence[RuleEvidence]) -> RuleEvidence | None:
    """The family's anchor is the node with no incoming cluster edge (spec §4.1).

    Defined once and shared with `rule_review_service._build_items`, so the rule text F5
    indexes can never drift from the rule text the Review Queue showed the approver.
    """
    if not members:
        return None
    for member in members:
        if member.cluster_edge_cosine_similarity is None:
            return member
    return members[0]


def build_convention_markdown(
    *, rule_text: str, rationale: str, evidence_count: int, distinct_pr_count: int, repo: str
) -> str:
    """Exactly the body of CLAUDE.md Phase 10 §2 — one chunk per family, never per evidence.

    `rationale` is passed through verbatim from the RuleCandidate the approver actually read.
    Ingest does not paraphrase, summarise or "improve" it: doing so would put text in front of
    a member that no human ever approved.
    """
    return (
        f"[Convention] {rule_text.strip()}\n"
        "\n"
        f"Lý do: {rationale.strip() or MISSING_RATIONALE}\n"
        "\n"
        f"Đã xác nhận qua {evidence_count} evidence từ {distinct_pr_count} PR khác nhau "
        f"trong {repo}.\n"
    )


@dataclass(frozen=True)
class _FamilyContent:
    rule_text: str
    rationale: str
    evidence_count: int
    distinct_pr_count: int
    repo: str


def _raw_pr_comment_id(evidence_unit_id: str) -> int:
    # Same business-key format `rule_review_service` parses: "<type>:<raw_pr_comment_id>".
    return int(evidence_unit_id.rsplit(":", 1)[1])


async def _load_family_content(session: AsyncSession, rule_family_id: int) -> _FamilyContent:
    rows = (
        await session.execute(
            select(RuleEvidence, RuleCandidate.rule_text_draft, RuleCandidate.rationale)
            .join(RuleCandidate, RuleCandidate.rule_candidate_id == RuleEvidence.rule_candidate_id)
            .where(RuleEvidence.rule_family_id == rule_family_id)
            .order_by(RuleEvidence.rule_evidence_id)
        )
    ).all()
    if not rows:
        raise ConventionIngestError(f"RuleFamily {rule_family_id} has no evidence to describe")

    members = [row[0] for row in rows]
    anchor = select_anchor(members)
    assert anchor is not None  # `rows` is non-empty, so `select_anchor` cannot return None.
    by_evidence_id = {row[0].rule_evidence_id: row for row in rows}
    _, rule_text, rationale = by_evidence_id[anchor.rule_evidence_id]

    repos = set(
        (
            await session.scalars(
                select(RawPrComment.repo).where(
                    RawPrComment.raw_pr_comment_id.in_(
                        [_raw_pr_comment_id(member.evidence_unit_id) for member in members]
                    )
                )
            )
        ).all()
    )
    if len(repos) != 1:
        raise ConventionIngestError(
            f"RuleFamily {rule_family_id} resolves to {len(repos)} repositories; expected exactly 1"
        )

    return _FamilyContent(
        rule_text=rule_text,
        rationale=rationale,
        evidence_count=len(members),
        distinct_pr_count=len({member.pr_number for member in members}),
        repo=repos.pop(),
    )


async def _active_chunk_count(session: AsyncSession, document_id: int) -> int:
    version_id = await session.scalar(
        select(DocumentVersion.version_id).where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.status == VersionStatus.ACTIVE,
        )
    )
    if version_id is None:
        return 0
    rows = await session.scalars(
        select(DocumentChunk.chunk_id).where(DocumentChunk.version_id == version_id)
    )
    return len(rows.all())


async def ingest_approved_rule_family(
    session: AsyncSession,
    rule_family_id: int,
    embedder: Embedder,
    *,
    actor_user_id: int,
) -> KnowledgeDocument:
    """Index one APPROVED RuleFamily as exactly one retrievable chunk.

    Does not commit — the caller owns the transaction boundary, exactly as every other
    `ingest_or_update` adapter does. Secret scanning is not repeated here on purpose: the
    ingest core scans unconditionally, so this path cannot bypass it (F-20 chokepoint).
    """
    family = await session.get(RuleFamily, rule_family_id)
    if family is None:
        raise ConventionIngestError(f"RuleFamily {rule_family_id} not found")
    if family.status is not RuleFamilyStatus.APPROVED:
        # Only an approved rule is knowledge. A PENDING or REJECTED family reaching this
        # function is a wiring bug, not a recoverable state.
        raise ConventionIngestError(
            f"RuleFamily {rule_family_id} is {family.status}, only APPROVED may be indexed"
        )

    content = await _load_family_content(session, rule_family_id)

    project_id = await session.scalar(
        select(Project.project_id).where(
            Project.github_repo == content.repo, Project.status == ProjectStatus.ACTIVE
        )
    )
    if project_id is None:
        # PROJECT knowledge without a project has nowhere to be ACL-scoped to, and the
        # `ck_knowledge_documents_knowledge_domain_category` CHECK would reject it anyway.
        raise ConventionIngestError(
            f"No ACTIVE project is configured for repository {content.repo!r}"
        )

    request = ProjectIngestRequest(
        project_id=project_id,
        created_by_user_id=actor_user_id,
        source_key=convention_source_key(rule_family_id),
        # The citation target, not a storage location: an approved convention has no artifact
        # file, its canonical presentation is the Conventions page entry.
        source_url=conventions_route(rule_family_id),
        source_repo=content.repo,
        source_path=conventions_route(rule_family_id),
        document_category=DocumentCategory.CONVENTION,
        raw_content=build_convention_markdown(
            rule_text=content.rule_text,
            rationale=content.rationale,
            evidence_count=content.evidence_count,
            distinct_pr_count=content.distinct_pr_count,
            repo=content.repo,
        ),
        # No commit SHA exists for mined knowledge; the approval decision is the version. A
        # re-index after the same approval is therefore the same version, and the core's
        # checksum short-circuit makes it a no-op rather than a duplicate.
        source_ref=f"rule-family-{rule_family_id}@approved",
        title=f"Convention #{rule_family_id}",
        # The PM's approval *is* the classification — an authoritative human decision, the
        # same standing as a PM choosing a category at upload time.
        category_confirmed=True,
        category_classification_status="CLASSIFIED",
        category_review_reason="Convention đã được PM/Admin duyệt trong Review Queue (F6)",
    )
    document = await ingest_or_update(session, request, embedder)
    await session.flush()

    chunk_count = await _active_chunk_count(session, document.document_id)
    if chunk_count != 1:
        # CLAUDE.md Phase 10 §2 is a hard contract: 1 APPROVED family == 1 chunk. More than
        # one would let F5 quote half a convention as if it were the whole rule.
        raise ConventionIngestError(
            f"RuleFamily {rule_family_id} produced {chunk_count} chunks; exactly 1 is required"
        )
    return document


async def find_convention_document(
    session: AsyncSession, rule_family_id: int
) -> KnowledgeDocument | None:
    """Look the indexed document back up by its F6 `source_key` — used by tests and tooling."""
    return await session.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.knowledge_domain == DocumentDomain.PROJECT,
            KnowledgeDocument.source_key == convention_source_key(rule_family_id),
        )
    )
