"""The shared dense + BM25 retrieval pipeline for PROJECT and POLICY."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import date

from sqlalchemy import Select, and_, desc, func, or_, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.providers.embeddings import EMBEDDING_DIMENSION
from src.ai.retrieval_engine.chunking_config import retrieval_params
from src.core.telemetry import current_trace, telemetry_span
from src.model.document_chunk import DocumentChunk
from src.model.document_version import DocumentVersion
from src.model.enums import (
    DocumentCategory,
    DocumentDomain,
    DocumentStatus,
    ProjectStatus,
    VersionStatus,
)
from src.model.knowledge_document import KnowledgeDocument
from src.model.project import Project
from src.shared.ai.ports import QueryEmbeddingPort
from src.shared.ai.request_budget import RequestBudget

_NUMBERED_SECTION = re.compile(
    r"^\s*(?:(?:bước|step)\s*)?\d+\s*(?:[.):\-–—]|\s)",
    re.IGNORECASE,
)


def _section_root(section_path: str | None) -> str | None:
    """Return the nearest parent shared by numbered sibling chunks."""
    if not section_path:
        return None
    parts = [part.strip() for part in section_path.split(">") if part.strip()]
    for index, part in enumerate(parts):
        if _NUMBERED_SECTION.match(part):
            root = " > ".join(parts[:index])
            return root or None
    normalized = " > ".join(parts)
    return normalized or None


@dataclass(frozen=True)
class RetrievalFilters:
    """The single ACL/domain scope consumed by every retrieval branch."""

    knowledge_domains: frozenset[DocumentDomain] = frozenset({DocumentDomain.PROJECT, DocumentDomain.POLICY})
    project_id: int | None = None
    document_categories: frozenset[DocumentCategory] | None = None
    document_status: DocumentStatus = DocumentStatus.ACTIVE
    project_status: ProjectStatus = ProjectStatus.ACTIVE
    embedding_model_version: str | None = None

    def validate(self) -> None:
        if not self.knowledge_domains:
            raise ValueError("knowledge_domains must not be empty")
        if DocumentDomain.PROJECT in self.knowledge_domains and self.project_id is None:
            raise ValueError("project_id is required when PROJECT is in the retrieval scope")
        if self.project_id is not None and DocumentDomain.PROJECT not in self.knowledge_domains:
            raise ValueError("project_id is only valid when PROJECT is in the retrieval scope")


@dataclass(frozen=True)
class CatalogGroup:
    """One category's worth of document titles, for `RetrievalEngine.list_catalog` (F5
    implementation spec §4/§8): a metadata-only grouping, never a retrieval result."""

    category: str
    titles: tuple[str, ...]


@dataclass(frozen=True)
class RetrievalOptions:
    dense_candidate_k: int = 30
    bm25_candidate_k: int = 30
    final_top_k: int = 10
    rrf_k: int = 60
    # Adaptive BM25 weighting -- see `bm25_weight` in chunking_params.yaml for the measurements.
    # Defaults reproduce the un-weighted behaviour exactly (`spread_ceiling=0.0` makes every
    # spread >= ceiling, so the weight is always 1.0), so any caller constructing
    # `RetrievalOptions()` directly is byte-identical to before this existed.
    bm25_weight_min_samples: int = 0
    bm25_weight_spread_floor: float = 0.0
    bm25_weight_spread_ceiling: float = 0.0

    def validate(self) -> None:
        if min(self.dense_candidate_k, self.bm25_candidate_k, self.final_top_k, self.rrf_k) < 1:
            raise ValueError("Retrieval options must all be positive")
        if self.bm25_weight_spread_floor > self.bm25_weight_spread_ceiling:
            raise ValueError("bm25_weight spread_floor must not exceed spread_ceiling")

    @classmethod
    def from_config(cls, config: dict | None = None) -> RetrievalOptions:
        settings = retrieval_params(config)
        weight = settings["fusion"].get("bm25_weight") or {}
        return cls(
            dense_candidate_k=int(settings["dense"]["candidate_k"]),
            bm25_candidate_k=int(settings["bm25"]["candidate_k"]),
            final_top_k=int(settings["final_top_k"]),
            rrf_k=int(settings["fusion"]["rrf_k"]),
            bm25_weight_min_samples=int(weight.get("min_samples", 0)),
            bm25_weight_spread_floor=float(weight.get("spread_floor", 0.0)),
            bm25_weight_spread_ceiling=float(weight.get("spread_ceiling", 0.0)),
        )


@dataclass(frozen=True)
class RetrievalResult:
    chunk: DocumentChunk
    knowledge_domain: DocumentDomain
    document_id: int
    version_id: int
    document_title: str | None = None
    source_url: str | None = None
    effective_date: date | None = None
    dense_score: float | None = None
    dense_rank: int | None = None
    bm25_score: float | None = None
    bm25_rank: int | None = None
    hybrid_score: float = 0.0
    final_rank: int | None = None

    @property
    def similarity(self) -> float | None:
        """Compatibility alias for callers that previously used dense-only results."""
        return self.dense_score


@dataclass(frozen=True)
class _Candidate:
    chunk: DocumentChunk
    knowledge_domain: DocumentDomain
    document_id: int
    version_id: int
    score: float
    document_title: str | None = None
    source_url: str | None = None
    effective_date: date | None = None


class _ScopedRetriever:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def scope_predicates(filters: RetrievalFilters) -> list[object]:
        filters.validate()
        predicates: list[object] = [
            KnowledgeDocument.status == filters.document_status,
            DocumentVersion.status == VersionStatus.ACTIVE,
        ]
        if filters.embedding_model_version is not None:
            predicates.extend(
                (
                    DocumentVersion.embedding_model_version == filters.embedding_model_version,
                    DocumentChunk.embedding_model_version == filters.embedding_model_version,
                )
            )
        domain_clauses: list[object] = []
        if DocumentDomain.POLICY in filters.knowledge_domains:
            domain_clauses.append(
                and_(
                    KnowledgeDocument.knowledge_domain == DocumentDomain.POLICY,
                    KnowledgeDocument.project_id.is_(None),
                )
            )
        if DocumentDomain.PROJECT in filters.knowledge_domains:
            project_clause: list[object] = [
                KnowledgeDocument.knowledge_domain == DocumentDomain.PROJECT,
                KnowledgeDocument.project_id == filters.project_id,
                Project.status == filters.project_status,
                KnowledgeDocument.document_category.is_not(None),
            ]
            if filters.document_categories is not None:
                project_clause.append(KnowledgeDocument.document_category.in_(filters.document_categories))
            domain_clauses.append(and_(*project_clause))
        predicates.append(or_(*domain_clauses))
        return predicates

    def base_statement(self, filters: RetrievalFilters) -> Select:
        return (
            select(
                DocumentChunk,
                KnowledgeDocument.knowledge_domain,
                KnowledgeDocument.document_id,
                DocumentVersion.version_id,
                KnowledgeDocument.title,
                KnowledgeDocument.source_url,
                DocumentVersion.effective_date,
            )
            .join(DocumentVersion, DocumentVersion.version_id == DocumentChunk.version_id)
            .join(KnowledgeDocument, KnowledgeDocument.document_id == DocumentVersion.document_id)
            .outerjoin(Project, Project.project_id == KnowledgeDocument.project_id)
            .where(*self.scope_predicates(filters))
        )


class PgvectorDenseRetriever(_ScopedRetriever):
    async def retrieve(
        self, query_vector: list[float], filters: RetrievalFilters, candidate_k: int
    ) -> list[_Candidate]:
        distance = DocumentChunk.embedding.cosine_distance(query_vector)
        rows = (
            await self.session.execute(
                self.base_statement(filters)
                .add_columns((1 - distance).label("dense_score"))
                .where(DocumentChunk.embedding.is_not(None))
                .order_by(distance)
                .limit(candidate_k)
            )
        ).all()
        return [
            _Candidate(*row[:4], score=float(row[7]), document_title=row[4], source_url=row[5], effective_date=row[6])
            for row in rows
        ]


class ParadeDbBm25Retriever(_ScopedRetriever):
    """ParadeDB pg_search BM25 branch; score units stay branch-local."""

    async def retrieve(self, query: str, filters: RetrievalFilters, candidate_k: int) -> list[_Candidate]:
        # pg_search 0.23.4 can assert on an invalid internal CTID in its parallel
        # custom scan. Keep this transaction-local so it neither leaks through the
        # pool nor changes dense retrieval or any other database workload.
        await self.session.execute(text("SET LOCAL max_parallel_workers_per_gather = 0"))
        score = func.pdb.score(DocumentChunk.chunk_id)
        rows = (
            await self.session.execute(
                self.base_statement(filters)
                .add_columns(score.label("bm25_score"))
                # `column @@@ text` binds to paradedb.search_with_parse (verified against
                # pg_operator): the plain-text RHS is run through Tantivy's query-string parser,
                # so free text containing reserved syntax (":", "()", etc. -- ordinary things
                # like "Close()" or "note:") throws an unhandled InternalServerError instead of
                # being treated as a search term. `paradedb.match()` builds a `searchqueryinput`
                # instead, which binds to paradedb.search_with_query_input and is tokenized by
                # the field's own configured tokenizer (unicode_words) with no query-string
                # parsing -- the safe/parameterized primitive ParadeDB itself provides for this,
                # not a hand-rolled escaping layer. See CHANGE_LOG.md for the eval run that found
                # this crashing on ordinary questions.
                .where(text("document_chunks.embedding_text @@@ paradedb.match('embedding_text', :bm25_query)"))
                .params(bm25_query=query)
                .order_by(desc(score), DocumentChunk.chunk_id)
                .limit(candidate_k)
            )
        ).all()
        return [
            _Candidate(*row[:4], score=float(row[7]), document_title=row[4], source_url=row[5], effective_date=row[6])
            for row in rows
        ]


def bm25_branch_weight(
    scores: Sequence[float], *, min_samples: int, spread_floor: float, spread_ceiling: float
) -> float:
    """How much of BM25's RANK ORDER to believe, from its own score dispersion. Pure function.

    RRF's premise is that a branch's ordering is evidence. That premise fails when the branch did
    not actually discriminate -- a query whose only lexical hits are ubiquitous terms produces a
    near-flat score band, and its "ranking" is arbitrary. Fusing that as if it were evidence is
    what pushed a dense-rank-2 chunk to fused rank 15 (see chunking_params.yaml).

    Relative spread `(max - min) / max`, not raw magnitude: BM25 scores scale with corpus size and
    document length, so an absolute cut-off would need re-calibrating per corpus while a ratio
    does not. Returns 1.0 (today's behaviour) unless the distribution is measurably degenerate.

    Deliberately continuous between floor and ceiling rather than a switch: a query sitting near
    the boundary should shift a little, never flip its whole ranking on a rounding difference.
    """
    if len(scores) < min_samples or spread_ceiling <= 0.0:
        # Too few hits to have a distribution at all -- and few hits means BM25 was SELECTIVE,
        # the opposite of the failure this guards. Keep full weight.
        return 1.0
    top = max(scores)
    if top <= 0.0:
        return 1.0
    spread = (top - min(scores)) / top
    if spread >= spread_ceiling:
        return 1.0
    if spread <= spread_floor:
        return 0.0
    return (spread - spread_floor) / (spread_ceiling - spread_floor)


class ReciprocalRankFusion:
    @staticmethod
    def fuse(
        dense: Iterable[_Candidate],
        bm25: Iterable[_Candidate],
        *,
        rrf_k: int,
        bm25_weight: float = 1.0,
    ) -> list[RetrievalResult]:
        """`bm25_weight` scales the BM25 arm's rank contribution (see `bm25_branch_weight`).
        Equivalent framing, and the one to keep in mind: because only the RATIO of the two arms
        affects ordering, down-weighting BM25 IS raising the dense arm's relative weight. 1.0 is
        the default and reproduces the original un-weighted fusion exactly."""
        merged: dict[int, RetrievalResult] = {}
        for rank, candidate in enumerate(dense, start=1):
            merged[candidate.chunk.chunk_id] = RetrievalResult(
                chunk=candidate.chunk,
                knowledge_domain=candidate.knowledge_domain,
                document_id=candidate.document_id,
                version_id=candidate.version_id,
                document_title=candidate.document_title,
                source_url=candidate.source_url,
                effective_date=candidate.effective_date,
                dense_score=candidate.score,
                dense_rank=rank,
                hybrid_score=1 / (rrf_k + rank),
            )
        for rank, candidate in enumerate(bm25, start=1):
            existing = merged.get(candidate.chunk.chunk_id)
            contribution = bm25_weight / (rrf_k + rank)
            if existing is None:
                merged[candidate.chunk.chunk_id] = RetrievalResult(
                    chunk=candidate.chunk,
                    knowledge_domain=candidate.knowledge_domain,
                    document_id=candidate.document_id,
                    version_id=candidate.version_id,
                    document_title=candidate.document_title,
                    source_url=candidate.source_url,
                    effective_date=candidate.effective_date,
                    bm25_score=candidate.score,
                    bm25_rank=rank,
                    hybrid_score=contribution,
                )
            else:
                merged[candidate.chunk.chunk_id] = replace(
                    existing,
                    bm25_score=candidate.score,
                    bm25_rank=rank,
                    hybrid_score=existing.hybrid_score + contribution,
                )
        return sorted(merged.values(), key=lambda result: (-result.hybrid_score, result.chunk.chunk_id))


class RetrievalUnavailableError(Exception):
    """The retrieval pipeline's own datastore (Postgres/pgvector/ParadeDB) failed after query
    embedding already succeeded -- a database-layer anticipated failure, deliberately typed the
    same way `ExternalServiceFailure` types an embedding/LLM outage, so `ChatService` can
    translate it into the same controlled `system_error` fallback instead of it escaping as a
    raw 500 (F5 audit 2026-08-29, HTTP 500 root cause: an unhandled `SQLAlchemyError` between the
    BM25 span closing and the fusion/evidence-scope-validation spans opening had no anticipated
    translation, so it propagated to the transport-level exception middleware).

    Raised ONLY by `RetrievalEngine.retrieve()` catching `SQLAlchemyError` around its own
    datastore calls (dense/bm25/fusion/evidence-scope-validation/dense-backfill) -- never a
    blanket `except Exception`. A defect in this module's own logic (fusion, ranking) raises
    whatever it naturally raises (`KeyError`, `AttributeError`, ...), which is NOT a
    `SQLAlchemyError`, so it is not caught here and keeps propagating as an observable,
    fail-loud unexpected error, exactly as before this type existed.
    """

    def __init__(self, stage: str, cause: BaseException) -> None:
        self.stage = stage
        self.cause = cause
        super().__init__(f"retrieval datastore failure at {stage}: {type(cause).__name__}")


class RetrievalEngine:
    """One ACL-safe orchestration point for dense + BM25 + RRF retrieval."""

    def __init__(self, session: AsyncSession, query_encoder: QueryEmbeddingPort | None = None) -> None:
        self.session = session
        self.query_encoder = query_encoder
        self.dense_retriever = PgvectorDenseRetriever(session)
        self.bm25_retriever = ParadeDbBm25Retriever(session)

    @staticmethod
    def _validate_query_vector(query_vector: list[float]) -> None:
        if len(query_vector) != EMBEDDING_DIMENSION:
            raise ValueError(f"BGE-M3 query vector must have {EMBEDDING_DIMENSION} dimensions")

    def _with_query_embedding_model(self, filters: RetrievalFilters) -> RetrievalFilters:
        if self.query_encoder is None:
            raise RuntimeError("RetrievalEngine requires a QueryEmbeddingPort for retrieval")
        model_version = self.query_encoder.model_version
        if filters.embedding_model_version is not None and filters.embedding_model_version != model_version:
            raise ValueError("Retrieval filter model version must match the query embedder")
        return replace(filters, embedding_model_version=model_version)

    # Kept as a dense SQL diagnostic/compatibility hook; the public API is retrieve(query, ...).
    def _statement(
        self, query_vector: list[float], *, knowledge_domain: DocumentDomain | None, project_id: int | None, limit: int
    ) -> Select:
        domains = frozenset({knowledge_domain}) if knowledge_domain else frozenset(DocumentDomain)
        filters = RetrievalFilters(knowledge_domains=domains, project_id=project_id)
        distance = DocumentChunk.embedding.cosine_distance(query_vector)
        return (
            self.dense_retriever.base_statement(filters)
            .add_columns((1 - distance).label("similarity"))
            .where(DocumentChunk.embedding.is_not(None))
            .order_by(distance)
            .limit(limit)
        )

    async def _validate_evidence(
        self, results: list[RetrievalResult], filters: RetrievalFilters
    ) -> set[int]:
        if not results:
            return set()
        statement = (
            self.dense_retriever.base_statement(filters)
            .with_only_columns(DocumentChunk.chunk_id)
            .where(DocumentChunk.chunk_id.in_([result.chunk.chunk_id for result in results]))
        )
        return set((await self.session.scalars(statement)).all())

    async def _backfill_dense_scores(
        self, results: list[RetrievalResult], query_vector: list[float]
    ) -> list[RetrievalResult]:
        """A BM25-only candidate (not in the dense top-k) has `dense_score=None`, which
        `RelevanceGate` coerces to 0.0 -- indistinguishable from "genuinely dissimilar" even
        though its real cosine may sit close to the accept threshold (AUDIT.md F-15). Backfill
        the real value for exactly those chunk ids with one extra vector op, scoped to the
        already fused+scoped result set (<= final_top_k rows), not a second retrieval pass.
        """
        missing_ids = [result.chunk.chunk_id for result in results if result.dense_score is None]
        if not missing_ids:
            return results
        distance = DocumentChunk.embedding.cosine_distance(query_vector)
        rows = (
            await self.session.execute(
                select(DocumentChunk.chunk_id, (1 - distance).label("dense_score"))
                .where(DocumentChunk.chunk_id.in_(missing_ids), DocumentChunk.embedding.is_not(None))
            )
        ).all()
        backfilled = {chunk_id: float(score) for chunk_id, score in rows}
        return [
            replace(result, dense_score=backfilled[result.chunk.chunk_id])
            if result.chunk.chunk_id in backfilled
            else result
            for result in results
        ]

    async def load_scoped_chunks(
        self, chunk_ids: Sequence[int], *, filters: RetrievalFilters
    ) -> list[RetrievalResult]:
        """Re-read specific chunks through the *same* scope predicates as every retrieval branch.

        Used when rehydrating a stored conversation: a chunk whose document has since been
        archived or moved out of scope simply does not come back, so a reload can never re-serve
        source text the caller may no longer see. No second pipeline, no second predicate set.
        """
        if not chunk_ids:
            return []
        filters = self._with_query_embedding_model(filters)
        filters.validate()
        rows = (
            await self.session.execute(
                self.dense_retriever.base_statement(filters).where(
                    DocumentChunk.chunk_id.in_(list(chunk_ids))
                )
            )
        ).all()
        return [
            RetrievalResult(
                chunk=row[0],
                knowledge_domain=row[1],
                document_id=row[2],
                version_id=row[3],
                document_title=row[4],
                source_url=row[5],
                effective_date=row[6],
            )
            for row in rows
        ]

    async def expand_numbered_section(
        self,
        accepted: Sequence[RetrievalResult],
        *,
        filters: RetrievalFilters,
        max_sequence_chunks: int = 6,
        max_other_chunks: int = 1,
    ) -> list[RetrievalResult]:
        """Fill gaps between accepted chunks from one ordered procedural section.

        Semantic top-k ranks chunks independently, so it can return steps 1, 4 and 5 while
        omitting steps 2 and 3 from the same setup guide.  Once at least two accepted chunks
        identify a section, this method loads its numbered siblings through the exact same ACL
        statement used by dense retrieval.  It is a scoped database read only: no embedding or
        LLM call is made.
        """
        if not accepted or max_sequence_chunks <= 0:
            return list(accepted)

        groups: dict[tuple[int, str], list[RetrievalResult]] = {}
        for item in accepted:
            root = _section_root(item.chunk.section_path)
            if root is not None:
                groups.setdefault((item.version_id, root), []).append(item)
        if not groups:
            return list(accepted)

        selected_key, seeds = max(
            groups.items(),
            key=lambda entry: (
                len(entry[1]),
                sum(item.hybrid_score for item in entry[1]),
                -min(item.final_rank or 10_000 for item in entry[1]),
            ),
        )
        # One isolated hit is not enough evidence that the question targets the whole section.
        if len(seeds) < 2:
            return list(accepted)

        filters = self._with_query_embedding_model(filters)
        filters.validate()
        version_id, root = selected_key
        prefix = f"{root} > "
        rows = (
            await self.session.execute(
                self.dense_retriever.base_statement(filters)
                .where(
                    DocumentVersion.version_id == version_id,
                    or_(
                        DocumentChunk.section_path == root,
                        DocumentChunk.section_path.startswith(prefix, autoescape=True),
                    ),
                )
                .order_by(DocumentChunk.chunk_index, DocumentChunk.chunk_id)
            )
        ).all()

        originals = {item.chunk.chunk_id: item for item in accepted}
        sequence: list[RetrievalResult] = []
        for row in rows:
            section_path = row[0].section_path or ""
            if not section_path.startswith(prefix):
                continue
            child_path = section_path[len(prefix) :]
            if not _NUMBERED_SECTION.match(child_path):
                continue
            sequence.append(
                originals.get(row[0].chunk_id)
                or RetrievalResult(
                    chunk=row[0],
                    knowledge_domain=row[1],
                    document_id=row[2],
                    version_id=row[3],
                    document_title=row[4],
                    source_url=row[5],
                    effective_date=row[6],
                )
            )
            if len(sequence) >= max_sequence_chunks:
                break

        # Avoid replacing ranked evidence when the section structure is not convincingly a
        # sequence (for example, a heading that merely begins with a number).
        if len(sequence) < 2:
            return list(accepted)

        sequence_ids = {item.chunk.chunk_id for item in sequence}
        outsiders = [
            item
            for item in accepted
            if item.chunk.chunk_id not in sequence_ids
            and (item.version_id, _section_root(item.chunk.section_path)) != selected_key
        ][: max(0, max_other_chunks)]
        expanded = [*sequence, *outsiders]
        trace = current_trace()
        if trace is not None:
            trace.annotate(
                decision_details={
                    "procedure_section_expanded": True,
                    "procedure_section_root": root,
                    "procedure_section_chunk_ids": [
                        item.chunk.chunk_id for item in sequence
                    ],
                }
            )
        return expanded

    async def list_available_topics(self, filters: RetrievalFilters, *, limit: int = 3) -> list[str]:
        """Deterministic, sourced fallback-suggestion topics (target design item 5).

        Distinct document titles the caller is actually scoped to see right now, through the
        exact same `scope_predicates` every retrieval branch uses -- so a suggestion can never
        name a topic with no real source (F-16's AMBIGUOUS-document exclusion applies here too,
        for free, via the same predicate). No embeddings, no ranking, not a second retrieval
        pipeline (NFR-14): a plain scoped metadata listing, the same shape `transcript()` already
        uses for `load_scoped_chunks` above.
        """
        # Not an embedding query -- there is no query vector, so the embedding-model-version
        # predicate (which only constrains DocumentChunk/DocumentVersion rows) does not apply.
        filters = replace(filters, embedding_model_version=None)
        filters.validate()
        rows = (
            await self.session.execute(
                select(KnowledgeDocument.title)
                .join(DocumentVersion, DocumentVersion.document_id == KnowledgeDocument.document_id)
                .outerjoin(Project, Project.project_id == KnowledgeDocument.project_id)
                .where(*self.dense_retriever.scope_predicates(filters))
                .distinct()
                .order_by(KnowledgeDocument.title)
                .limit(max(0, limit))
            )
        ).all()
        return [row[0] for row in rows if row[0]]

    async def list_catalog(
        self, filters: RetrievalFilters, *, limit_per_group: int = 20
    ) -> list[CatalogGroup]:
        """Catalog/overview lookup (implementation spec §8): "what documents/policies
        exist" answered from real, ACL-scoped structure, not forced through semantic
        top-K RAG. Extends the same non-embedding metadata pattern `list_available_topics`
        already established -- not a second retrieval pipeline (NFR-14).

        Groups by whichever category field applies to the document's domain
        (`document_category` for PROJECT, `policy_category` for POLICY -- mutually
        exclusive per the `knowledge_domain_category` CHECK constraint). Selecting both
        columns and choosing in Python, rather than a SQL `COALESCE`, avoids a Postgres
        enum-type mismatch between the two distinct enum types.
        """
        filters = replace(filters, embedding_model_version=None)
        filters.validate()
        rows = (
            await self.session.execute(
                select(
                    KnowledgeDocument.document_category,
                    KnowledgeDocument.policy_category,
                    KnowledgeDocument.title,
                )
                .join(DocumentVersion, DocumentVersion.document_id == KnowledgeDocument.document_id)
                .outerjoin(Project, Project.project_id == KnowledgeDocument.project_id)
                .where(*self.dense_retriever.scope_predicates(filters))
                .distinct()
                .order_by(KnowledgeDocument.title)
            )
        ).all()
        grouped: dict[str, list[str]] = {}
        for document_category, policy_category, title in rows:
            if not title:
                continue
            category = (
                document_category.value
                if document_category is not None
                else (policy_category.value if policy_category is not None else "OTHER")
            )
            bucket = grouped.setdefault(category, [])
            if title not in bucket and len(bucket) < limit_per_group:
                bucket.append(title)
        return [
            CatalogGroup(category=category, titles=tuple(titles))
            for category, titles in sorted(grouped.items())
        ]

    async def retrieve(
        self, query: str, *, filters: RetrievalFilters, budget: RequestBudget,
        options: RetrievalOptions | None = None
    ) -> list[RetrievalResult]:
        """Encode once, retrieve both branches in the identical scope, then RRF."""
        if not query.strip():
            raise ValueError("query must not be empty")
        filters = self._with_query_embedding_model(filters)
        filters.validate()
        options = options or RetrievalOptions.from_config()
        options.validate()
        trace = current_trace()
        attempt = trace.next_attempt("retrieval") if trace is not None else 1
        with telemetry_span("retrieval.embedding", attempt=attempt):
            query_vector = await self.query_encoder.embed_query(query, budget)
        self._validate_query_vector(query_vector)
        # F5 audit 2026-08-29, HTTP 500 root cause: everything from here through dense-backfill
        # is our OWN datastore, not an external AI provider (`retrieval.embedding` above already
        # has its own `ExternalServiceFailure` translation and stays outside this block). A
        # `SQLAlchemyError` here is an anticipated, environmental failure -- typed and re-raised
        # as `RetrievalUnavailableError` for `ChatService` to translate into the existing
        # controlled `system_error` fallback. Deliberately NOT a blanket `except Exception`: a
        # real defect in this method's own logic (fusion, ranking) raises something that is not a
        # `SQLAlchemyError` and is left to propagate unchanged, fail-loud, as before.
        try:
            with telemetry_span("retrieval.dense", attempt=attempt):
                dense = await self.dense_retriever.retrieve(
                    query_vector, filters, options.dense_candidate_k
                )
            with telemetry_span("retrieval.bm25", attempt=attempt):
                bm25 = await self.bm25_retriever.retrieve(query, filters, options.bm25_candidate_k)
            with telemetry_span("retrieval.fusion", attempt=attempt):
                bm25_weight = bm25_branch_weight(
                    [candidate.score for candidate in bm25],
                    min_samples=options.bm25_weight_min_samples,
                    spread_floor=options.bm25_weight_spread_floor,
                    spread_ceiling=options.bm25_weight_spread_ceiling,
                )
                fused = ReciprocalRankFusion.fuse(
                    dense, bm25, rrf_k=options.rrf_k, bm25_weight=bm25_weight
                )
            if trace is not None and bm25_weight < 1.0:
                # Annotated only when it actually fired. This is a ranking change the user never
                # sees directly, so without a trace line a mis-calibrated ramp would be invisible
                # -- and "why did retrieval return that?" is exactly the question this whole fix
                # came from. Logged with the inputs so a bad threshold can be diagnosed from one
                # row.
                trace.annotate(
                    decision_details={
                        "bm25_branch_weight": round(bm25_weight, 4),
                        "bm25_candidate_count": len(bm25),
                    }
                )
            with telemetry_span("retrieval.evidence_scope_validation", attempt=attempt):
                allowed = await self._validate_evidence(fused, filters)
            results = [
                replace(result, final_rank=rank)
                for rank, result in enumerate(
                    (result for result in fused if result.chunk.chunk_id in allowed), start=1
                )
            ][: options.final_top_k]
            with telemetry_span("retrieval.dense_backfill", attempt=attempt):
                results = await self._backfill_dense_scores(results, query_vector)
        except SQLAlchemyError as exc:
            raise RetrievalUnavailableError("retrieval.datastore", exc) from exc
        if trace is not None:
            trace.annotate(
                retrieval_attempt_count=attempt,
                candidate_count=len(fused),
                decision_details={
                    "dense_candidate_count": len(dense),
                    "bm25_candidate_count": len(bm25),
                    "final_candidate_count": len(results),
                },
                retrieval_scores=[
                    {
                        "chunk_id": item.chunk.chunk_id,
                        "dense_score": item.dense_score,
                        "dense_rank": item.dense_rank,
                        "bm25_score": item.bm25_score,
                        "bm25_rank": item.bm25_rank,
                        "hybrid_score": item.hybrid_score,
                        "final_rank": item.final_rank,
                    }
                    for item in results
                ],
            )
        return results
