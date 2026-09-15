"""CI-safe validation of the F5 golden suite v2 (`EVAL_GUIDE.md §16.1`).

This is the pytest face of `eval/validate_golden.py` -- same checks, one test per check so a
failure names the thing that broke instead of collapsing into a single assertion. No LLM call,
no database, no network: it runs on `demo-data/` and the golden JSON alone.

It replaces `eval/test_golden_set_f5.py`, which validated the superseded 70-case POLICY set
against `raw-data/` (a directory that no longer exists). See `eval/golden-test/LEGACY.md` for
what happened to those files and why they are kept.
"""

from __future__ import annotations

import pytest

from eval.corpus.demo_corpus import load_corpus
from eval.shared.golden_schema import load_suite
from eval.validate_golden import (
    check_answerability_balance,
    check_coverage,
    check_duplicates,
    check_evidence,
    check_no_fabricated_evidence,
    check_schema,
    check_unique_ids,
    coverage_matrix,
)


@pytest.fixture(scope="module")
def cases():
    loaded = load_suite()
    assert loaded, "golden suite is empty -- eval/golden-test/f5_v2/*.json did not load"
    return loaded


def _assert_clean(problems: list[str], label: str) -> None:
    assert not problems, f"{label}:\n" + "\n".join(f"  - {problem}" for problem in problems)


def test_corpus_loads():
    """The authoritative corpus must be present and indexable before anything else matters."""
    corpus = load_corpus()
    # Floors, not exact counts: adding a document to demo-data/ is a corpus change, not a test
    # failure, but LOSING documents silently would invalidate every quote check below.
    assert len(corpus.documents("POLICY")) >= 39, "POLICY corpus shrank below the 39 demo documents"
    assert len(corpus.documents("PROJECT")) >= 35, "PROJECT corpus shrank below the 35 demo documents"


def test_schema(cases):
    _assert_clean(check_schema(cases), "schema errors")


def test_unique_ids(cases):
    _assert_clean(check_unique_ids(cases), "duplicate case ids")


def test_evidence_is_verbatim(cases):
    """Every expected quote must exist word for word in the document -- and in the named section.

    This is the check that keeps the suite honest: a golden 'fact' that is not in the corpus is
    a GOLDEN_DATA_ERROR (EVAL_GUIDE.md §19), and it would otherwise be discovered only as a
    mysterious model failure during a live run.
    """
    _assert_clean(check_evidence(cases), "non-verbatim or unresolvable evidence")


def test_no_fabricated_evidence(cases):
    _assert_clean(check_no_fabricated_evidence(cases), "refusal cases carrying evidence")


def test_no_duplicate_or_near_duplicate_questions(cases):
    _assert_clean(check_duplicates(cases), "duplicate questions (paraphrase padding)")


def test_behavioral_coverage(cases):
    _assert_clean(check_coverage(cases), "missing behavioral coverage")


def test_answerability_balance(cases):
    _assert_clean(check_answerability_balance(cases), "answerability balance")


def test_stability_subset_is_declared(cases):
    subset = [case for case in cases if case.stability]
    assert subset, "no case is marked for the stability subset"


def test_every_case_records_provenance(cases):
    """A reviewer must be able to tell whether a case is new, reused or rewritten, and from what."""
    missing = [case.id for case in cases if not case.provenance.get("origin")]
    _assert_clean(missing, "cases without provenance.origin")


def test_coverage_matrix_builds(cases):
    matrix = coverage_matrix(cases)
    assert matrix["total_cases"] == len(cases)
    assert matrix["documents_covered"] > 0


# ------------------------------------------------------------------------------------------------
# `Corpus.resolve_citation` / `run_suite._resolve_documents` (2026-08-30 full-eval measurement
# fix): a full golden-suite run showed 24/37 PROJECT cases resolving ZERO corpus documents despite
# the chatbot returning real, resolvable, grounded citations -- confirmed live on `F5V2-PRJ-004`,
# whose citation carried `source_url=None` (withheld by `ChatService._citation_source_url` for
# every ordinary citation -- see that function's docstring) and
# `source_title="test_upload/thanos_environment_setup.md"`, the document's raw ingest key/path
# rather than its human title ("Thanos Development Environment Setup"). The old fallback only
# ever compared `source_title` against `Document.title`, so this citation resolved to nothing and
# was scored as a retrieval miss it never was.
# ------------------------------------------------------------------------------------------------


def test_resolve_citation_matches_title_when_source_url_is_withheld():
    """The common case: `ChatService` never populates `source_url` for an ordinary citation
    (only for the internal Conventions route), so title must resolve alone."""
    corpus = load_corpus()
    document = next(iter(corpus.documents("PROJECT")))
    resolved = corpus.resolve_citation(None, document.title)
    assert resolved is document


def test_resolve_citation_matches_raw_doc_id_used_as_title():
    """Live-observed shape (F5V2-PRJ-004): a document whose runtime title is its own raw
    ingest key/path, not the human title this corpus module derives from its heading."""
    corpus = load_corpus()
    document = corpus.get("test_upload/thanos_environment_setup.md")
    assert document is not None, "fixture document missing from demo-data/ -- update this test"
    assert document.title != document.doc_id  # the whole point: title and doc_id genuinely differ

    resolved = corpus.resolve_citation(None, document.doc_id)
    assert resolved is document


def test_resolve_citation_matches_policy_path_used_as_title():
    corpus = load_corpus()
    document = next(iter(corpus.documents("POLICY")))
    resolved = corpus.resolve_citation(None, document.path)
    assert resolved is document


def test_resolve_citation_prefers_source_url_when_present():
    corpus = load_corpus()
    document = next(iter(corpus.documents("PROJECT")))
    # A deliberately wrong title must not win over a correct, resolvable source_url.
    resolved = corpus.resolve_citation(document.source_url, "not a real title")
    assert resolved is document


def test_resolve_citation_never_fabricates_a_match():
    """Strictness guard: a citation for a document this corpus genuinely does not have must
    still resolve to `None`, not the nearest-looking document."""
    corpus = load_corpus()
    assert corpus.resolve_citation(None, "completely unrelated title that matches nothing") is None
    assert corpus.resolve_citation("https://example.test/not-in-corpus.md", None) is None
    assert corpus.resolve_citation(None, None) is None
    assert corpus.resolve_citation("", "") is None


def test_resolve_documents_recovers_the_prj_004_citation_shape():
    """Integration-level regression for the exact citation payload shape observed live on
    `F5V2-PRJ-004`: `source_url=None`, `source_title` equal to the document's raw doc_id."""
    from eval.run_suite import _resolve_documents

    corpus = load_corpus()
    document = corpus.get("test_upload/thanos_environment_setup.md")
    assert document is not None, "fixture document missing from demo-data/ -- update this test"
    citations = [{"source_url": None, "source_title": document.doc_id}]

    assert _resolve_documents(corpus, citations) == [document.doc_id]


def test_resolve_documents_still_deduplicates_and_preserves_order():
    from eval.run_suite import _resolve_documents

    corpus = load_corpus()
    first, second = list(corpus.documents("PROJECT"))[:2]
    citations = [
        {"source_url": None, "source_title": first.doc_id},
        {"source_url": None, "source_title": "unrelated, resolves to nothing"},
        {"source_url": None, "source_title": second.title},
        {"source_url": None, "source_title": first.title},  # same document again
    ]

    assert _resolve_documents(corpus, citations) == [first.doc_id, second.doc_id]
