from types import SimpleNamespace

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.elements import TextClause

from src.ai.retrieval_engine.lexical import lexical_identifiers
from src.ai.retrieval_engine.retrieval_engine import (
    ParadeDbBm25Retriever,
    PgvectorDenseRetriever,
    ReciprocalRankFusion,
    RetrievalEngine,
    RetrievalFilters,
    RetrievalOptions,
    RetrievalResult,
    RetrievalUnavailableError,
    _Candidate,
    bm25_branch_weight,
)
from src.model.document_chunk import DocumentChunk
from src.model.document_version import DocumentVersion
from src.model.enums import DocumentCategory, DocumentDomain, DocumentStatus, UserStatus, VersionStatus
from src.model.knowledge_document import KnowledgeDocument
from src.model.project import Project
from src.model.user import User
from src.shared.ai.request_budget import RequestBudget


def _candidate(chunk_id: int, score: float) -> _Candidate:
    return _Candidate(
        chunk=SimpleNamespace(chunk_id=chunk_id),
        knowledge_domain=DocumentDomain.POLICY,
        document_id=1,
        version_id=1,
        score=score,
    )


def test_rrf_merges_by_chunk_id_without_calibrating_branch_scores() -> None:
    results = ReciprocalRankFusion.fuse(
        [_candidate(1, 0.99), _candidate(2, 0.50)],
        [_candidate(2, 42.0), _candidate(3, 5.0)],
        rrf_k=60,
    )

    assert [result.chunk.chunk_id for result in results] == [2, 1, 3]
    assert results[0].dense_rank == 2
    assert results[0].bm25_rank == 1
    assert results[0].dense_score == 0.50
    assert results[0].bm25_score == 42.0


def test_project_scope_requires_project_id() -> None:
    with pytest.raises(ValueError, match="project_id"):
        RetrievalFilters(knowledge_domains=frozenset({DocumentDomain.PROJECT})).validate()


def test_project_id_cannot_be_used_for_policy_only_scope() -> None:
    with pytest.raises(ValueError, match="only valid"):
        RetrievalFilters(knowledge_domains=frozenset({DocumentDomain.POLICY}), project_id=1).validate()


def test_identifier_extraction_preserves_policy_and_code_terms() -> None:
    identifiers = lexical_identifiers("HR-POL-001 uses my_variable in RFC 3502, version 3.2.")
    assert identifiers.splitlines() == ["HR-POL-001", "my_variable", "RFC 3502", "3.2"]


def test_identifier_extraction_matches_vietnamese_script_identifiers() -> None:
    """AUDIT.md finding (F5 diagnostic #4): an ASCII-only letter class produced an empty
    identifier set for any identifier-shaped token written in Vietnamese script, so a
    Vietnamese question referencing a hyphenated document/clause code could never trigger
    RelevanceGate's lexical bypass. A plain Vietnamese sentence with no identifier-shaped token
    still correctly yields no identifiers -- this only widens which SCRIPTS an identifier can be
    written in, not what counts as identifier-shaped."""
    identifiers = lexical_identifiers("Điều-5 quy định về chính-sách-01 và HR-POL-001.")
    assert identifiers.splitlines() == ["Điều-5", "chính-sách-01", "HR-POL-001"]
    assert lexical_identifiers("Thanos la gi va muc tieu chinh cua du an la gi?") == ""


def test_retrieval_options_reject_non_positive_values() -> None:
    with pytest.raises(ValueError):
        RetrievalOptions(dense_candidate_k=0).validate()


def test_dense_and_bm25_scopes_only_select_active_versions() -> None:
    """v1 ARCHIVED and v2 ACTIVE share a document; both branches use v2 only."""
    filters = RetrievalFilters(knowledge_domains=frozenset({DocumentDomain.POLICY}))
    # Both branches derive their SQL from the same scoped base statement.
    for retriever in (PgvectorDenseRetriever(None), ParadeDbBm25Retriever(None)):
        statement = retriever.base_statement(filters)
        version_predicates = [
            clause
            for clause in statement._where_criteria
            if "document_versions.status" in str(clause)
        ]
        assert len(version_predicates) == 1
        assert version_predicates[0].right.value is VersionStatus.ACTIVE
    assert not hasattr(filters, "version_status")


class _CapturingSession:
    """No real DB: only records the statement `ParadeDbBm25Retriever.retrieve()` executes."""

    def __init__(self) -> None:
        self.statement = None
        self.statements: list = []

    async def execute(self, statement):
        self.statement = statement
        self.statements.append(statement)

        class _EmptyResult:
            def all(self) -> list:
                return []

        return _EmptyResult()


@pytest.mark.asyncio
async def test_bm25_query_uses_paradedb_match_not_bare_text() -> None:
    """`column @@@ text` binds to paradedb.search_with_parse, which runs the free-text query
    through Tantivy's query-string parser -- reserved characters ordinary questions contain all
    the time (":" as in "note:", "(" ")" as in "Close()") crash it with an unhandled
    InternalServerError instead of being treated as search terms (verified against pg_operator
    and reproduced live -- see CHANGE_LOG.md). `paradedb.match(field, value)` builds a
    `searchqueryinput` instead, which binds to paradedb.search_with_query_input: tokenized by the
    field's own configured tokenizer, no query-string parsing. This pins the fix at the SQL
    text level since the standard test DB is SQLite (`tests/conftest.py:db_session`), which has
    no ParadeDB extension to catch a regression here at execution time."""
    session = _CapturingSession()
    filters = RetrievalFilters(knowledge_domains=frozenset({DocumentDomain.POLICY}))

    await ParadeDbBm25Retriever(session).retrieve("Close() co the loi: test", filters, 10)

    assert len(session.statements) == 2
    assert str(session.statements[0]) == "SET LOCAL max_parallel_workers_per_gather = 0"
    text_clauses = [c for c in session.statement._where_criteria if isinstance(c, TextClause)]
    assert len(text_clauses) == 1
    bm25_clause = text_clauses[0].text
    assert "paradedb.match('embedding_text', :bm25_query)" in bm25_clause
    assert "embedding_text @@@ :bm25_query" not in bm25_clause


class _StubDenseBackfillSession:
    """No real DB: returns canned (chunk_id, score) rows regardless of the compiled statement,
    so `_backfill_dense_scores`'s merge logic can be pinned without a live pgvector column."""

    def __init__(self, rows: list[tuple[int, float]]) -> None:
        self.rows = rows
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        rows = self.rows

        class _Result:
            def all(self) -> list:
                return rows

        return _Result()


def _result(chunk_id: int, **overrides) -> RetrievalResult:
    defaults = dict(
        chunk=SimpleNamespace(chunk_id=chunk_id),
        knowledge_domain=DocumentDomain.PROJECT,
        document_id=1,
        version_id=1,
    )
    defaults.update(overrides)
    return RetrievalResult(**defaults)


@pytest.mark.asyncio
async def test_backfill_dense_scores_fills_only_bm25_only_candidates() -> None:
    """AUDIT.md F-15: a BM25-only candidate's `dense_score` must be its real cosine, not the
    `None` -> 0.0 coercion `RelevanceGate` used to apply -- that made every BM25-only candidate
    fail `dense_ok` regardless of true similarity. A candidate that already has a dense_score
    (found by the dense branch too) must be left untouched."""
    session = _StubDenseBackfillSession(rows=[(5, 0.71)])
    engine = RetrievalEngine(session)

    already_dense = _result(1, dense_score=0.90, dense_rank=1)
    bm25_only = _result(5, dense_score=None, bm25_score=12.0, bm25_rank=3)

    backfilled = await engine._backfill_dense_scores([already_dense, bm25_only], [0.0] * 1024)

    assert backfilled[0].dense_score == 0.90
    assert backfilled[1].dense_score == 0.71
    assert backfilled[1].bm25_rank == 3  # unrelated fields untouched


@pytest.mark.asyncio
async def test_backfill_dense_scores_is_a_noop_without_bm25_only_candidates() -> None:
    session = _StubDenseBackfillSession(rows=[])
    engine = RetrievalEngine(session)
    already_dense = _result(1, dense_score=0.90)

    backfilled = await engine._backfill_dense_scores([already_dense], [0.0] * 1024)

    assert backfilled == [already_dense]
    assert session.statement is None  # no query issued when nothing is missing


@pytest.mark.asyncio
async def test_list_available_topics_only_returns_sourced_confirmed_documents(db_session) -> None:
    """Target design item 5: fallback-suggestion topics must come from real, in-scope documents.

    Same `scope_predicates` every retrieval branch uses, so an ARCHIVED version and an AMBIGUOUS
    (unconfirmed-category) PROJECT document -- excluded from retrieval by F-16 -- must not appear
    as a suggestion either: nothing here should be an invented or unsourced topic.
    """
    admin = User(email="topics-admin@example.test", display_name="Admin", status=UserStatus.ACTIVE)
    db_session.add(admin)
    await db_session.flush()
    project = Project(
        key="topics-proj", name="Topics", created_by_admin_id=admin.user_id,
        github_repo="topics/proj", default_branch="main",
    )
    db_session.add(project)
    await db_session.flush()

    confirmed = KnowledgeDocument(
        project_id=project.project_id,
        created_by_user_id=admin.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        document_category=DocumentCategory.OVERVIEW,
        title="Architecture Overview",
        source_url="https://example.test/architecture",
        status=DocumentStatus.ACTIVE,
    )
    ambiguous = KnowledgeDocument(
        project_id=project.project_id,
        created_by_user_id=admin.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        document_category=None,
        category_confirmed=False,
        category_classification_status="AMBIGUOUS",
        title="Unclassified Draft",
        source_url="https://example.test/unclassified",
        status=DocumentStatus.ACTIVE,
    )
    archived_version_doc = KnowledgeDocument(
        project_id=project.project_id,
        created_by_user_id=admin.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        document_category=DocumentCategory.SETUP,
        title="Old Setup Guide",
        source_url="https://example.test/old-setup",
        status=DocumentStatus.ACTIVE,
    )
    db_session.add_all([confirmed, ambiguous, archived_version_doc])
    await db_session.flush()
    db_session.add_all(
        [
            DocumentVersion(
                document_id=confirmed.document_id,
                version_no="1",
                embedding_model_version="test-model",
                revision_no=1,
                storage_uri="test/architecture.md",
                checksum="architecture-1",
                status=VersionStatus.ACTIVE,
            ),
            DocumentVersion(
                document_id=ambiguous.document_id,
                version_no="1",
                embedding_model_version="test-model",
                revision_no=1,
                storage_uri="test/unclassified.md",
                checksum="unclassified-1",
                status=VersionStatus.ACTIVE,
            ),
            DocumentVersion(
                document_id=archived_version_doc.document_id,
                version_no="1",
                embedding_model_version="test-model",
                revision_no=1,
                storage_uri="test/old-setup.md",
                checksum="old-setup-1",
                status=VersionStatus.ARCHIVED,
            ),
        ]
    )
    await db_session.commit()

    engine = RetrievalEngine(db_session)
    filters = RetrievalFilters(
        knowledge_domains=frozenset({DocumentDomain.PROJECT}), project_id=project.project_id,
    )

    topics = await engine.list_available_topics(filters, limit=5)

    assert topics == ["Architecture Overview"]


@pytest.mark.asyncio
async def test_expand_numbered_section_loads_missing_middle_steps_without_embedding(db_session) -> None:
    """Production regression: semantic top-k found setup steps 1, 4 and 5 but omitted 2 and 3.

    Structural expansion must load the ordered siblings through the normal ACL scope and must not
    call the query encoder again.
    """
    admin = User(email="section-admin@example.test", display_name="Admin", status=UserStatus.ACTIVE)
    db_session.add(admin)
    await db_session.flush()
    project = Project(
        key="section-proj",
        name="Section expansion",
        created_by_admin_id=admin.user_id,
        github_repo="acme/section",
        default_branch="main",
    )
    db_session.add(project)
    await db_session.flush()
    setup_document = KnowledgeDocument(
        project_id=project.project_id,
        created_by_user_id=admin.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        document_category=DocumentCategory.SETUP,
        title="Local setup",
        source_url="https://example.test/setup",
        status=DocumentStatus.ACTIVE,
    )
    unrelated_document = KnowledgeDocument(
        project_id=project.project_id,
        created_by_user_id=admin.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        document_category=DocumentCategory.CODEBASE_GUIDE,
        title="Code guide",
        source_url="https://example.test/code",
        status=DocumentStatus.ACTIVE,
    )
    db_session.add_all([setup_document, unrelated_document])
    await db_session.flush()
    setup_version = DocumentVersion(
        document_id=setup_document.document_id,
        version_no="1",
        embedding_model_version="test-model",
        revision_no=1,
        storage_uri="test/setup.md",
        checksum="setup-v1",
        status=VersionStatus.ACTIVE,
    )
    unrelated_version = DocumentVersion(
        document_id=unrelated_document.document_id,
        version_no="1",
        embedding_model_version="test-model",
        revision_no=1,
        storage_uri="test/code.md",
        checksum="code-v1",
        status=VersionStatus.ACTIVE,
    )
    db_session.add_all([setup_version, unrelated_version])
    await db_session.flush()

    def chunk(version_id: int, index: int, section_path: str) -> DocumentChunk:
        return DocumentChunk(
            version_id=version_id,
            heading=section_path,
            section_path=section_path,
            content=f"content {index}",
            embedding_text=f"content {index}",
            lexical_identifiers="",
            lexical_technical="",
            anchor=f"section-{index}",
            content_hash=f"hash-{version_id}-{index}",
            embedding_model_version="test-model",
            chunk_index=index,
            token_count=10,
        )

    setup_chunks = [
        chunk(setup_version.version_id, 0, "README > Cài đặt môi trường local"),
        chunk(setup_version.version_id, 1, "README > Cài đặt môi trường local > 1. Yêu cầu"),
        chunk(setup_version.version_id, 2, "README > Cài đặt môi trường local > 2. Clone"),
        chunk(setup_version.version_id, 3, "README > Cài đặt môi trường local > 3. Dependency"),
        chunk(setup_version.version_id, 4, "README > Cài đặt môi trường local > 4. Cấu hình"),
        chunk(setup_version.version_id, 5, "README > Cài đặt môi trường local > 5. Chạy server"),
    ]
    unrelated = chunk(unrelated_version.version_id, 0, "README > Hướng dẫn mã nguồn > 1. Đọc code")
    db_session.add_all([*setup_chunks, unrelated])
    await db_session.commit()

    def result(item: DocumentChunk, document: KnowledgeDocument, version: DocumentVersion, rank: int):
        return RetrievalResult(
            chunk=item,
            knowledge_domain=DocumentDomain.PROJECT,
            document_id=document.document_id,
            version_id=version.version_id,
            document_title=document.title,
            dense_score=0.8,
            hybrid_score=0.5,
            final_rank=rank,
        )

    accepted = [
        result(setup_chunks[0], setup_document, setup_version, 1),
        result(setup_chunks[1], setup_document, setup_version, 2),
        result(setup_chunks[4], setup_document, setup_version, 3),
        result(unrelated, unrelated_document, unrelated_version, 4),
        result(setup_chunks[5], setup_document, setup_version, 5),
    ]
    # Deliberately has no `embed_query`: this test fails if expansion performs inference.
    encoder = SimpleNamespace(model_version="test-model")
    engine = RetrievalEngine(db_session, encoder)
    filters = RetrievalFilters(
        knowledge_domains=frozenset({DocumentDomain.PROJECT}), project_id=project.project_id
    )

    expanded = await engine.expand_numbered_section(
        accepted, filters=filters, max_sequence_chunks=5, max_other_chunks=1
    )

    assert [item.chunk.chunk_id for item in expanded] == [
        setup_chunks[1].chunk_id,
        setup_chunks[2].chunk_id,
        setup_chunks[3].chunk_id,
        setup_chunks[4].chunk_id,
        setup_chunks[5].chunk_id,
        unrelated.chunk_id,
    ]


def test_project_scope_explicitly_excludes_unclassified_documents_and_keeps_empty_set() -> None:
    filters = RetrievalFilters(
        knowledge_domains=frozenset({DocumentDomain.PROJECT}),
        project_id=1,
        document_categories=frozenset(),
    )
    sql = str(PgvectorDenseRetriever(None).base_statement(filters).compile(compile_kwargs={"literal_binds": True}))

    assert "knowledge_documents.document_category IS NOT NULL" in sql
    assert "knowledge_documents.document_category IN (NULL) AND (1 != 1)" in sql


def test_retrieval_scope_filters_chunks_and_versions_to_the_query_model() -> None:
    filters = RetrievalFilters(
        knowledge_domains=frozenset({DocumentDomain.POLICY}),
        embedding_model_version="model-v2",
    )
    sql = str(PgvectorDenseRetriever(None).base_statement(filters).compile(compile_kwargs={"literal_binds": True}))

    assert "document_versions.embedding_model_version = 'model-v2'" in sql
    assert "document_chunks.embedding_model_version = 'model-v2'" in sql


def test_retrieval_rejects_a_filter_model_different_from_the_query_embedder() -> None:
    encoder = type("Encoder", (), {"model_version": "model-v2", "dimension": 1024})()
    engine = RetrievalEngine(None, encoder)

    with pytest.raises(ValueError, match="must match"):
        engine._with_query_embedding_model(
            RetrievalFilters(
                knowledge_domains=frozenset({DocumentDomain.POLICY}),
                embedding_model_version="model-v1",
            )
        )


# ==============================================================================================
# Adaptive BM25 branch weight (2026-08-26).
#
# RRF's premise is that a branch's RANK ORDER is evidence. Live, that premise failed: the
# Vietnamese question "Dự án Thanos được thiết kế theo kiến trúc gì?" has exactly one token the
# English corpus contains -- "Thanos" -- which is in every document, so BM25 returned a ranking of
# "documents mentioning Thanos" carrying no information. RRF scored that noise as rank evidence
# and pushed the correct chunk from DENSE RANK 2 to FUSED RANK 15, below chunks at dense rank 17
# that merely appeared in both lists. The turn answered `insufficient_evidence` while
# `Thanos Architecture Overview` sat unread at dense rank 2.
#
# Measured spreads over 17 real queries against the live corpus:
#   degenerate  0.152, 0.152, 0.152  (identical across three DIFFERENT questions -- same list)
#   healthy     0.316 .. 0.827
# The ramp sits inside that gap. These tests pin the SHAPE of the function and the two
# behaviours that matter: degenerate input loses the branch, healthy input is untouched.
# ==============================================================================================


def _scores(top: float, spread: float, n: int) -> list[float]:
    """A score list with a known relative spread `(max - min) / max`."""
    return [top, top * (1 - spread)] + [top * (1 - spread / 2)] * (n - 2)


def test_a_healthy_lexical_distribution_keeps_full_bm25_weight() -> None:
    """Every healthy query measured (0.316-0.827) must be completely unaffected -- this fix is
    only allowed to change the case it was written for."""
    for spread in (0.316, 0.440, 0.553, 0.713, 0.827):
        weight = bm25_branch_weight(
            _scores(12.0, spread, 30), min_samples=5, spread_floor=0.20, spread_ceiling=0.30
        )
        assert weight == 1.0, f"spread={spread} should be fully trusted"


def test_a_degenerate_flat_distribution_drops_the_bm25_branch() -> None:
    """The measured live failure: three different questions all produced spread=0.152 because
    BM25 returned the same "contains Thanos" list each time."""
    assert (
        bm25_branch_weight(
            _scores(1.82, 0.152, 30), min_samples=5, spread_floor=0.20, spread_ceiling=0.30
        )
        == 0.0
    )


def test_the_weight_ramps_continuously_between_floor_and_ceiling() -> None:
    """Continuous, not a switch: a query near the boundary should shift a little rather than flip
    its whole ranking on a rounding difference. Monotonic so the ramp cannot invert."""
    weights = [
        bm25_branch_weight(
            _scores(10.0, spread, 30), min_samples=5, spread_floor=0.20, spread_ceiling=0.30
        )
        for spread in (0.20, 0.225, 0.25, 0.275, 0.30)
    ]
    assert weights == sorted(weights)
    assert weights[0] == 0.0 and weights[-1] == 1.0
    assert weights[2] == pytest.approx(0.5)


@pytest.mark.parametrize("count", [0, 1, 4])
def test_too_few_hits_keeps_full_weight_because_selectivity_is_not_the_failure(count: int) -> None:
    """Dispersion is a property of a population. Below `min_samples` there is no distribution to
    measure -- and few hits means BM25 was SELECTIVE, the opposite of the failure this guards.
    A naive implementation would compute spread=0 for a single hit and silently discard the
    strongest possible lexical evidence."""
    assert (
        bm25_branch_weight(
            [9.0] * count, min_samples=5, spread_floor=0.20, spread_ceiling=0.30
        )
        == 1.0
    )


def test_non_positive_scores_never_divide_by_zero() -> None:
    assert bm25_branch_weight([0.0] * 30, min_samples=5, spread_floor=0.2, spread_ceiling=0.3) == 1.0


def test_weighting_is_off_by_default_so_untouched_callers_are_identical() -> None:
    """`RetrievalOptions()` built directly (every existing test and caller) must reproduce the
    original un-weighted fusion exactly -- the ceiling defaults to 0.0, which short-circuits."""
    options = RetrievalOptions()
    assert options.bm25_weight_spread_ceiling == 0.0
    assert (
        bm25_branch_weight(
            _scores(1.82, 0.152, 30),
            min_samples=options.bm25_weight_min_samples,
            spread_floor=options.bm25_weight_spread_floor,
            spread_ceiling=options.bm25_weight_spread_ceiling,
        )
        == 1.0
    )


def test_a_zero_weight_leaves_dense_ordering_intact() -> None:
    """The end state of the live failure. With the BM25 arm at zero, a chunk BM25 ranked first
    cannot displace the dense winner -- which is precisely what happened to
    `Thanos Architecture Overview` at dense rank 2."""
    fused = ReciprocalRankFusion.fuse(
        [_candidate(1, 0.99), _candidate(2, 0.50)],
        [_candidate(2, 42.0), _candidate(3, 5.0)],
        rrf_k=60,
        bm25_weight=0.0,
    )

    assert [result.chunk.chunk_id for result in fused] == [1, 2, 3]
    # BM25-only candidates are still CARRIED (they keep their rank/score for downstream
    # backfill), they simply contribute nothing to the ordering.
    assert fused[-1].chunk.chunk_id == 3
    assert fused[-1].bm25_rank == 2


def test_default_weight_reproduces_the_original_fusion_exactly() -> None:
    """The `bm25_weight` parameter defaults to 1.0, so the pre-existing fusion test above and
    this one must agree -- a regression here means every caller silently changed."""
    args = ([_candidate(1, 0.99), _candidate(2, 0.50)], [_candidate(2, 42.0), _candidate(3, 5.0)])
    assert [r.chunk.chunk_id for r in ReciprocalRankFusion.fuse(*args, rrf_k=60)] == [2, 1, 3]
    assert [
        r.chunk.chunk_id for r in ReciprocalRankFusion.fuse(*args, rrf_k=60, bm25_weight=1.0)
    ] == [2, 1, 3]


def test_options_reject_an_inverted_ramp() -> None:
    with pytest.raises(ValueError):
        RetrievalOptions(bm25_weight_spread_floor=0.5, bm25_weight_spread_ceiling=0.2).validate()


def test_shipped_config_ramp_sits_inside_the_measured_gap() -> None:
    """Guards the calibration itself, not just the code. If someone widens the ramp past the
    measured healthy minimum (0.316) they start down-weighting queries BM25 handles well; if they
    drop the floor below the measured degenerate value (0.152) the fix stops firing at all."""
    options = RetrievalOptions.from_config()
    assert options.bm25_weight_min_samples >= 2
    assert 0.152 < options.bm25_weight_spread_floor
    assert options.bm25_weight_spread_ceiling <= 0.316


class _FakeQueryEncoder:
    """Satisfies `QueryEmbeddingPort` without embedding a real vector -- these tests never reach
    a real query encoder's own failure path, only what happens after it succeeds."""

    model_version = "test-embedder-v1"
    dimension = 1024

    async def embed_query(self, _text: str, _budget) -> list[float]:
        return [0.0] * 1024


class _RaisingRetriever:
    def __init__(self, error: BaseException) -> None:
        self.error = error

    async def retrieve(self, *_args, **_kwargs):
        raise self.error


def _budget() -> RequestBudget:
    return RequestBudget(30.0, 0.0, 30.0, 0.0)


@pytest.mark.asyncio
async def test_datastore_error_during_retrieval_becomes_retrieval_unavailable_error() -> None:
    """F5 audit 2026-08-29, HTTP 500 root cause: an unhandled `SQLAlchemyError` from the
    retrieval pipeline's own datastore calls (dense/bm25/fusion/evidence-scope-validation/
    dense-backfill) propagated with no anticipated-failure translation, escaping all the way to
    the transport-level exception middleware as a raw 500. `RetrievalEngine.retrieve()` must now
    translate any `SQLAlchemyError` raised in that segment into `RetrievalUnavailableError` --
    typed the same way `ExternalServiceFailure` types an embedding/LLM outage -- so `ChatService`
    can degrade it into the existing controlled `system_error` fallback instead."""
    engine = RetrievalEngine(session=None, query_encoder=_FakeQueryEncoder())
    engine.dense_retriever = _RaisingRetriever(SQLAlchemyError("connection reset"))

    with pytest.raises(RetrievalUnavailableError):
        await engine.retrieve(
            "query",
            filters=RetrievalFilters(knowledge_domains=frozenset({DocumentDomain.POLICY})),
            budget=_budget(),
        )


@pytest.mark.asyncio
async def test_non_database_error_during_retrieval_is_not_swallowed() -> None:
    """The translation above is deliberately narrow (`SQLAlchemyError` only, never a blanket
    `except Exception`), so a real defect in this module's own logic -- anything that is NOT the
    datastore misbehaving -- must keep propagating unchanged and fail-loud, exactly as it did
    before `RetrievalUnavailableError` existed. This is the other half of the same fix: closing
    the 500 for an anticipated failure must never also hide an unrelated programmer error behind
    a normal-looking fallback."""
    engine = RetrievalEngine(session=None, query_encoder=_FakeQueryEncoder())
    engine.dense_retriever = _RaisingRetriever(RuntimeError("a real bug, not a database problem"))

    with pytest.raises(RuntimeError, match="a real bug"):
        await engine.retrieve(
            "query",
            filters=RetrievalFilters(knowledge_domains=frozenset({DocumentDomain.POLICY})),
            budget=_budget(),
        )
