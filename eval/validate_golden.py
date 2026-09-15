"""Deterministic, CI-safe validation of the F5 golden suite (`EVAL_GUIDE.md §16.1`, §17 Step 1).

No LLM call, no database, no network -- this runs on `demo-data/` and the golden JSON alone, so
it is cheap enough to run on every commit and is the gate that must pass before any live
evaluation is worth starting.

What it proves:

- schema validity and stable, unique, correctly-prefixed ids;
- every referenced document exists in the authoritative corpus (`demo-data/`);
- every expected-evidence quote is genuinely verbatim in the document -- and in the named
  section when one is given;
- no expected evidence points at corpus bookkeeping (README/manifest) rather than knowledge;
- unanswerable/adversarial/guardrail cases carry no fabricated evidence;
- no duplicate or near-duplicate questions (paraphrase padding, `EVAL_GUIDE.md §13`);
- the partitions actually cover the behavioral families the guide requires.

Run standalone (`python eval/validate_golden.py`) or under pytest -- `test_golden_suite_v2.py`
wraps the same functions so a failure shows up as a normal test.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval.corpus.demo_corpus import KNOWLEDGE_EXCLUDED, load_corpus  # noqa: E402
from eval.shared.golden_schema import (  # noqa: E402
    ATTACK_FAMILIES,
    GUARDRAIL_INVARIANTS,
    GoldenCase,
    load_suite,
    schema_errors,
)
from eval.shared.reviewed_golden import binding_errors, load_reviewed_rows  # noqa: E402

REPORT_PATH = Path(__file__).resolve().parent / "golden-test" / "f5_v2" / "validation_report.json"

# Coverage the suite must actually have. These are floors, not targets: they exist so a future
# edit cannot quietly delete a whole behavioral partition and still pass CI. They are NOT a case
# quota -- `EVAL_GUIDE.md §13` is explicit that volume without new failure modes is worthless.
REQUIRED_CATEGORIES = {
    "factual_lookup",
    "paraphrase",
    "identifier",
    "deep_document",
    "multi_chunk",
    "cross_document",
    "composite",
    "near_miss",
    "catalog",
    "ambiguous",
    "conflict",
    "unanswerable",
    "false_refusal_probe",
    "scenario",
}
REQUIRED_LANGUAGES = {"vi", "vi_no_diacritics", "en"}
# Families whose absence would leave a real attack class untested. The remaining families in
# ATTACK_FAMILIES are still valid to use; they are simply not mandatory.
REQUIRED_ATTACK_FAMILIES = {
    "direct_instruction_override",
    "system_prompt_extraction",
    "role_persona_override",
    "citation_bypass",
    "grounding_bypass",
    "fabricated_citation_request",
    "pretrained_knowledge_substitution",
    "stored_multi_turn_injection",
    "indirect_document_injection",
    "secret_exfiltration",
    "cross_project_data_request",
    "presentation_as_behavior_control",
}
REQUIRED_GUARDRAIL_INVARIANTS = set(GUARDRAIL_INVARIANTS)
MIN_DOMAIN_CASES = {"POLICY": 40, "PROJECT": 25}

_WORD = re.compile(r"\w+", re.UNICODE)
# Two questions this similar are paraphrase padding unless they deliberately test the same fact
# in different languages/scripts, which the checker allows for explicitly.
NEAR_DUPLICATE_THRESHOLD = 0.85


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(unicodedata.normalize("NFC", text).casefold()))


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def check_schema(cases: list[GoldenCase]) -> list[str]:
    problems: list[str] = []
    for case in cases:
        problems.extend(f"{case.id}: {error}" for error in schema_errors(case))
    return problems


def check_unique_ids(cases: list[GoldenCase]) -> list[str]:
    counts = Counter(case.id for case in cases)
    return [f"duplicate case id {case_id!r} ({count}x)" for case_id, count in counts.items() if count > 1]


def check_evidence(cases: list[GoldenCase]) -> list[str]:
    """Every expected document exists, and every quote is verbatim where the case says it is."""
    corpus = load_corpus()
    problems: list[str] = []
    for case in cases:
        for doc_id in case.expected_documents:
            document = corpus.get(doc_id)
            if document is None:
                problems.append(f"{case.id}: expected document {doc_id!r} is not in demo-data/")
                continue
            if document.path in KNOWLEDGE_EXCLUDED:
                problems.append(
                    f"{case.id}: {doc_id!r} is corpus bookkeeping, not answerable knowledge"
                )
        for quote in case.expected_quotes:
            reason = corpus.verify_quote(quote.doc_id, quote.quote, quote.section)
            if reason:
                problems.append(f"{case.id}: {reason} -- {quote.quote[:70]!r}")
    return problems


def check_absence_claims(cases: list[GoldenCase]) -> list[str]:
    """Fail a declared absence claim when its explicit probe terms are now in the corpus.

    Absence cannot be proven generally by a finite snapshot.  Goldens can opt into a narrow,
    reviewable freshness probe via `freshness_absence_terms`; this catches the common stale-case
    failure without inventing a semantic corpus search in CI.
    """
    corpus_text = "\n".join(document.text.casefold() for document in load_corpus())
    problems: list[str] = []
    for case in cases:
        for term in case.raw.get("freshness_absence_terms", []):
            if str(term).casefold() in corpus_text:
                problems.append(f"{case.id}: absence claim is stale; corpus now contains {term!r}")
    return problems


def check_reviewed_bindings(cases: list[GoldenCase]) -> list[str]:
    return binding_errors(cases, load_reviewed_rows())


def check_no_fabricated_evidence(cases: list[GoldenCase]) -> list[str]:
    problems: list[str] = []
    for case in cases:
        if case.case_type in {"unanswerable", "guardrail", "adversarial"} and (
            case.expected_documents or case.expected_quotes
        ):
            # An adversarial case MAY name the benign document its legitimate half is grounded
            # in; it may never carry evidence for the attack itself. The distinction is recorded
            # explicitly so a reviewer does not have to infer it.
            if not case.raw.get("benign_evidence_ok"):
                problems.append(
                    f"{case.id}: {case.case_type} case carries expected evidence without "
                    "benign_evidence_ok -- refusal/attack cases must not require fabricated evidence"
                )
    return problems


def check_duplicates(cases: list[GoldenCase]) -> list[str]:
    """Exact duplicates always fail; near-duplicates fail unless deliberately paired."""
    problems: list[str] = []
    seen: dict[str, str] = {}
    for case in cases:
        if not case.question:
            continue
        key = unicodedata.normalize("NFC", case.question.strip().casefold())
        if key in seen:
            problems.append(f"{case.id}: identical question to {seen[key]}")
        seen[key] = case.id

    knowledge = [c for c in cases if c.question and c.is_knowledge]
    for index, left in enumerate(knowledge):
        for right in knowledge[index + 1 :]:
            # A deliberate language/script pair tests the SAME fact through a different input
            # form -- that is a distinct failure mode, not padding, so it is exempt.
            if left.language != right.language:
                continue
            if _jaccard(_tokens(left.question), _tokens(right.question)) >= NEAR_DUPLICATE_THRESHOLD:
                problems.append(
                    f"{left.id} and {right.id}: near-duplicate questions in the same language "
                    "(paraphrase padding). Make them test different failure modes or drop one."
                )
    return problems


def check_coverage(cases: list[GoldenCase]) -> list[str]:
    problems: list[str] = []
    categories = {c.category for c in cases}
    missing = REQUIRED_CATEGORIES - categories
    if missing:
        problems.append(f"no case covers categories: {sorted(missing)}")

    languages = {c.language for c in cases if c.is_knowledge}
    missing_languages = REQUIRED_LANGUAGES - languages
    if missing_languages:
        problems.append(f"no knowledge case in languages: {sorted(missing_languages)}")

    for domain, minimum in MIN_DOMAIN_CASES.items():
        count = sum(1 for c in cases if c.domain == domain)
        if count < minimum:
            problems.append(f"domain {domain} has {count} cases, expected at least {minimum}")

    families = {c.attack_family for c in cases if c.case_type == "adversarial"}
    missing_families = REQUIRED_ATTACK_FAMILIES - families
    if missing_families:
        problems.append(f"no adversarial case covers attack families: {sorted(missing_families)}")
    unknown = families - ATTACK_FAMILIES - {None}
    if unknown:
        problems.append(f"unknown attack families: {sorted(unknown)}")

    invariants = {c.guardrail_invariant for c in cases if c.case_type == "guardrail"}
    missing_invariants = REQUIRED_GUARDRAIL_INVARIANTS - invariants
    if missing_invariants:
        problems.append(f"no guardrail case covers invariants: {sorted(missing_invariants)}")

    if not any(c.case_type == "conversation" for c in cases):
        problems.append("suite has no multi-turn conversation cases")
    if not any(c.stability for c in cases):
        problems.append("suite marks no stability subset (EVAL_GUIDE.md §9)")
    return problems


def check_answerability_balance(cases: list[GoldenCase]) -> list[str]:
    """Both halves of the §6 outcome matrix must be measurable."""
    problems: list[str] = []
    answerable = sum(1 for c in cases if c.case_type == "answerable")
    unanswerable = sum(1 for c in cases if c.case_type == "unanswerable")
    partial = sum(1 for c in cases if c.case_type == "partial")
    if unanswerable < 8:
        problems.append(f"only {unanswerable} unanswerable cases -- correct-abstention rate would be noise")
    if partial < 5:
        problems.append(f"only {partial} partial cases -- partial-coverage behavior is undertested")
    if answerable < 40:
        problems.append(f"only {answerable} answerable cases -- false-refusal rate would be noise")
    return problems


CHECKS = (
    ("schema", check_schema),
    ("unique_ids", check_unique_ids),
    ("evidence_verbatim", check_evidence),
    ("absence_freshness", check_absence_claims),
    ("reviewed_bindings", check_reviewed_bindings),
    ("no_fabricated_evidence", check_no_fabricated_evidence),
    ("duplicates", check_duplicates),
    ("coverage", check_coverage),
    ("answerability_balance", check_answerability_balance),
)


def coverage_matrix(cases: list[GoldenCase]) -> dict:
    by_domain: Counter = Counter(c.domain for c in cases)
    by_type: Counter = Counter(c.case_type for c in cases)
    by_category: Counter = Counter(c.category for c in cases)
    by_language: Counter = Counter(c.language for c in cases)
    by_partition: Counter = Counter(c.partition for c in cases)
    by_origin: Counter = Counter(
        str(c.provenance.get("origin", "")).split(":", 1)[0] for c in cases
    )

    documents: dict[str, list[str]] = defaultdict(list)
    for case in cases:
        for doc_id in case.expected_documents:
            documents[doc_id].append(case.id)

    corpus = load_corpus()
    covered = set(documents)
    all_docs = {d.doc_id for d in corpus}
    return {
        "total_cases": len(cases),
        "by_partition": dict(sorted(by_partition.items())),
        "by_domain": dict(sorted(by_domain.items())),
        "by_case_type": dict(sorted(by_type.items())),
        "by_category": dict(sorted(by_category.items())),
        "by_language": dict(sorted(by_language.items())),
        "by_origin": dict(sorted(by_origin.items())),
        "stability_subset": sorted(c.id for c in cases if c.stability),
        "attack_families": sorted({c.attack_family for c in cases if c.attack_family}),
        "guardrail_invariants": sorted({c.guardrail_invariant for c in cases if c.guardrail_invariant}),
        "documents_covered": len(covered),
        "documents_total": len(all_docs),
        "documents_uncovered": sorted(all_docs - covered),
        "cases_per_document": {k: sorted(v) for k, v in sorted(documents.items())},
    }


def validate(cases: list[GoldenCase]) -> dict[str, list[str]]:
    return {name: check(cases) for name, check in CHECKS}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-report", action="store_true", help=f"write {REPORT_PATH.name}")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    cases = load_suite()
    results = validate(cases)
    matrix = coverage_matrix(cases)
    failures = {name: problems for name, problems in results.items() if problems}

    if not args.quiet:
        print(f"golden suite: {len(cases)} cases across {len(matrix['by_partition'])} partitions")
        for key in ("by_partition", "by_domain", "by_case_type", "by_language", "by_origin"):
            print(f"  {key}: {matrix[key]}")
        print(f"  corpus documents referenced: {matrix['documents_covered']}/{matrix['documents_total']}")
        for name, problems in results.items():
            status = "FAIL" if problems else "ok"
            print(f"  [{status:4s}] {name} ({len(problems)} problem(s))")
            for problem in problems:
                print(f"          - {problem}")

    if args.write_report:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            json.dumps(
                {"passed": not failures, "checks": results, "coverage": matrix},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        if not args.quiet:
            print(f"wrote {REPORT_PATH.relative_to(REPO_ROOT)}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
