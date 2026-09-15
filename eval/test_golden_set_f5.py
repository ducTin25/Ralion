"""Structural validation for eval/golden-test/golden_test_f5_70_samples.json.

This is NOT an eval runner — no live retrieval/generation happens here (see
`meta.harness_status` in the JSON itself: no such runner exists in this repo yet, per
CLAUDE.md §4 Phase 3 / AUDIT.md F-25). This suite only guards the *dataset's* structural
and grounding integrity so a future harness has a trustworthy fixture to consume:

- exactly 70 cases, unique ids, correct 40/15/15 composition
- every required field is present per case_type
- every non-empty evidence quote is a real, verbatim (whitespace/markdown-bold
  normalized) substring of the referenced raw-data/company-policy/*.md file
- unanswerable cases never carry fabricated evidence
- injection cases use genuinely distinct attack families
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PATH = REPO_ROOT / "eval" / "golden-test" / "golden_test_f5_70_samples.json"
# The original fixture was authored against the pre-cleanup raw-data layout. Prefer that
# canonical snapshot when present, but keep structural validation runnable against this repo's
# checked-in demo corpus after the source was moved under demo-data/company-policy.
_POLICY_DIR_CANDIDATES = (
    REPO_ROOT / "raw-data" / "company-policy",
    REPO_ROOT / "demo-data" / "company-policy",
)
POLICY_DIR = next((path for path in _POLICY_DIR_CANDIDATES if path.is_dir()), _POLICY_DIR_CANDIDATES[0])

FALLBACK_REASONS = {"no_evidence", "system_error", "validator_fail"}
GUARDRAIL_INVARIANTS = {
    "no_evidence_fallback",
    "insufficient_evidence_no_fill",
    "conflicting_evidence_no_silent_choice",
    "citation_claim_grounding_integrity",
    "unsupported_claim_rejection",
    "outside_policy_scope",
    "secret_credential_refusal",
    "malformed_adversarial_input",
}
COMMON_REQUIRED = ("id", "case_type", "question", "is_answerable", "test_purpose", "evidence")
RAG_REQUIRED = (
    "expected_answer", "expected_source_document", "policy_category",
    "difficulty", "question_type",
)
BEHAVIORAL_REQUIRED = ("expected_behavior", "pass_criteria", "fail_indicators", "related_fallback_reason")

_BOLD = re.compile(r"\*\*")
_WS = re.compile(r"[ \t]+")


def _normalize(text: str) -> str:
    return _WS.sub(" ", _BOLD.sub("", text)).strip()


def _load():
    with open(GOLDEN_PATH, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def golden():
    return _load()


@pytest.fixture(scope="module")
def cases(golden):
    return golden["cases"]


@pytest.fixture(scope="module")
def doc_cache():
    cache: dict[str, str] = {}

    def get(filename: str) -> str | None:
        if filename not in cache:
            path = POLICY_DIR / filename
            cache[filename] = _normalize(path.read_text(encoding="utf-8")) if path.is_file() else None
        return cache[filename]

    return get


def test_file_exists():
    assert GOLDEN_PATH.is_file(), f"missing golden set: {GOLDEN_PATH}"


def test_exactly_70_cases(cases):
    assert len(cases) == 70


def test_unique_stable_ids(cases):
    ids = [c["id"] for c in cases]
    duplicates = {i for i in ids if ids.count(i) > 1}
    assert not duplicates, f"duplicate ids: {duplicates}"
    # stable-id convention
    for c in cases:
        assert re.match(r"^F5-(RAG|GRD|INJ)-\d{3}[a-z]?$", c["id"]), c["id"]


def test_40_15_15_distribution(cases):
    counts = {"policy_rag": 0, "guardrail": 0, "injection": 0}
    for c in cases:
        assert c["case_type"] in counts, f"{c['id']}: unknown case_type {c['case_type']!r}"
        counts[c["case_type"]] += 1
    assert counts == {"policy_rag": 40, "guardrail": 15, "injection": 15}, counts


def test_common_required_fields_present(cases):
    for c in cases:
        for field in COMMON_REQUIRED:
            assert field in c, f"{c['id']}: missing field {field!r}"
        assert c["is_answerable"] in (True, False, "partial"), f"{c['id']}: bad is_answerable {c['is_answerable']!r}"
        assert isinstance(c["evidence"], list)


def test_policy_rag_required_fields(cases):
    for c in cases:
        if c["case_type"] != "policy_rag":
            continue
        for field in RAG_REQUIRED:
            assert field in c, f"{c['id']}: missing field {field!r}"
        assert c["difficulty"] in {"easy", "medium", "hard", "edge"}, c["id"]


def test_guardrail_and_injection_required_fields(cases):
    for c in cases:
        if c["case_type"] not in ("guardrail", "injection"):
            continue
        for field in BEHAVIORAL_REQUIRED:
            assert field in c, f"{c['id']}: missing field {field!r}"
        assert c["pass_criteria"], f"{c['id']}: pass_criteria must be non-empty"
        assert c["fail_indicators"], f"{c['id']}: fail_indicators must be non-empty"
        assert c["related_fallback_reason"] in FALLBACK_REASONS | {None}, c["id"]
        if c["case_type"] == "guardrail":
            assert "guardrail_invariant" in c, f"{c['id']}: missing guardrail_invariant"
            assert c["guardrail_invariant"] in GUARDRAIL_INVARIANTS, (
                f"{c['id']}: unknown guardrail_invariant {c['guardrail_invariant']!r}"
            )
        if c["case_type"] == "injection":
            assert "attack_family" in c, f"{c['id']}: missing attack_family"


def test_injection_attack_families_are_distinct(cases):
    families = [c["attack_family"] for c in cases if c["case_type"] == "injection"]
    assert len(families) == 15
    duplicates = {f for f in families if families.count(f) > 1}
    assert not duplicates, f"injection cases must use distinct attack families, got repeats: {duplicates}"


def test_guardrail_invariants_cover_all_eight(cases):
    seen = {c["guardrail_invariant"] for c in cases if c["case_type"] == "guardrail"}
    assert seen == GUARDRAIL_INVARIANTS, f"missing invariants: {GUARDRAIL_INVARIANTS - seen}"


def test_referenced_policy_sources_exist(cases, doc_cache):
    for c in cases:
        for entry in c["evidence"]:
            for field in ("document", "section", "quote"):
                assert field in entry, f"{c['id']}: evidence entry missing {field!r}"
            assert doc_cache(entry["document"]) is not None, (
                f"{c['id']}: evidence references missing document {entry['document']!r}"
            )


def test_evidence_quotes_are_verbatim(cases, doc_cache):
    for c in cases:
        for entry in c["evidence"]:
            haystack = doc_cache(entry["document"])
            needle = _normalize(entry["quote"])
            assert haystack is not None, (
                f"{c['id']}: evidence references missing document {entry['document']!r}"
            )
            assert needle and needle in haystack, (
                f"{c['id']}: quote not found verbatim in {entry['document']!r}: {entry['quote']!r}"
            )


def test_answerable_rag_cases_have_evidence(cases):
    for c in cases:
        if c["case_type"] == "policy_rag" and c["is_answerable"] is True:
            assert c["evidence"], f"{c['id']}: answerable RAG case must have non-empty evidence"


def test_unanswerable_cases_have_no_fabricated_evidence(cases):
    """is_answerable == False must never carry evidence (nothing to ground a refusal in)."""
    for c in cases:
        if c["is_answerable"] is False:
            assert c["evidence"] == [], (
                f"{c['id']}: is_answerable=False must have empty evidence, got {c['evidence']}"
            )


def test_security_cases_do_not_require_fabricated_evidence(cases):
    """Guardrail/injection cases with no legitimate underlying question must carry no evidence."""
    for c in cases:
        if c["case_type"] in ("guardrail", "injection") and c["is_answerable"] is False:
            assert c["evidence"] == [], f"{c['id']}: refusal-only case must not carry evidence"


def test_indirect_injection_fixture_is_clearly_marked(cases):
    fixture_cases = [c for c in cases if "simulated_retrieved_chunk" in c]
    assert fixture_cases, "expected at least one indirect-injection fixture case"
    for c in fixture_cases:
        assert "fixture_note" in c and c["fixture_note"], f"{c['id']}: fixture case must explain its limitation"
        assert "FIXTURE" in c["simulated_retrieved_chunk"], (
            f"{c['id']}: simulated_retrieved_chunk must be self-labeled as a fixture, not real corpus content"
        )


def test_meta_composition_matches_cases(golden, cases):
    meta = golden["meta"]
    assert meta["total_cases"] == len(cases) == 70
    counts = {"policy_rag": 0, "guardrail": 0, "injection": 0}
    for c in cases:
        counts[c["case_type"]] += 1
    assert meta["composition"] == counts
