"""Schema, loader and structural validation for the F5 golden suite v2.

The suite lives in `eval/golden-test/f5_v2/*.json`, one file per behavioral partition
(`EVAL_GUIDE.md §13`: organise by partition, not by arbitrary case count). Every file has the
same shape:

    {"partition": "policy_rag", "cases": [ {...}, ... ]}

This module owns the *contract*; `eval/validate_golden.py` owns the CI-safe checks that run it
against the corpus. Field set follows `EVAL_GUIDE.md §14` with its own closing instruction
applied -- "Do not add unused schema purely for completeness": every field below is read by
either the validator, a runner, or the scorecard.

## Case kinds

`case_type` selects which extra fields are required and how a runner grades the case:

    answerable    the corpus answers it; graded on retrieval + claims + aspects
    partial       the corpus covers the topic but not the specific thing asked; the system must
                  say what it has and refuse to invent the rest (PARTIAL / insufficient_evidence)
    unanswerable  the corpus does not answer it; the system must abstain
    guardrail     direct-user-input safety; graded on execution-path invariants
    adversarial   prompt injection / attack families (`EVAL_GUIDE.md §8.2`)
    conversation  multi-turn; graded on route + resolved question per turn

`expected_evidence` is required for `answerable`/`partial` and must be EMPTY for
`unanswerable` -- an abstention case that carries evidence is a contradiction, and pinning
fabricated evidence to it is exactly the "golden data error" class in `EVAL_GUIDE.md §19`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SUITE_DIR = Path(__file__).resolve().parents[1] / "golden-test" / "f5_v2"

DOMAINS = frozenset({"POLICY", "PROJECT"})
LANGUAGES = frozenset({"vi", "vi_no_diacritics", "en"})

CASE_TYPES = frozenset(
    {"answerable", "partial", "unanswerable", "guardrail", "adversarial", "conversation"}
)
KNOWLEDGE_CASE_TYPES = frozenset({"answerable", "partial", "unanswerable"})
EVIDENCE_BEARING = frozenset({"answerable", "partial"})

# Retrieval/answer-quality partitions (EVAL_GUIDE.md §13.1). Each names a genuinely different
# failure mode -- two cases sharing a category must still differ in what can break them.
CATEGORIES = frozenset(
    {
        "factual_lookup",
        "paraphrase",
        "identifier",  # exact commands, versions, config keys, document codes
        "deep_document",  # answer-bearing text far inside a long document
        "multi_chunk",  # several chunks of ONE document
        "cross_document",  # synthesis across documents
        "composite",  # one question, several distinct aspects
        "near_miss",  # a topically similar document must NOT win
        "catalog",  # what documents/policies exist
        "ambiguous",  # answerable but under-specified
        "conflict",  # sources disagree or precedence must be applied
        "unanswerable",
        "false_refusal_probe",  # answerable but phrased the way gating tends to over-reject
        "scenario",  # situational decision spanning policy rules
        "general_guidance",  # bounded general knowledge, when enabled
        "memory_continuity",
    }
)

# `InterpreterRoute` in src/ai/orchestration/turn_interpreter.py. Kept as a literal set rather
# than imported so the deterministic validator never needs the application package importable.
ROUTES = frozenset({"KNOWLEDGE", "REUSE", "CONVERSATION", "SOCIAL", "CATALOG", "CLARIFY"})

# `FALLBACKS` in src/modules/chat/application/chat_service.py.
FALLBACK_REASONS = frozenset(
    {
        "no_evidence",
        "insufficient_evidence",
        "out_of_scope",
        "ambiguous_question",
        "validator_fail",
        "system_error",
    }
)

ATTACK_FAMILIES = frozenset(
    {
        "direct_instruction_override",
        "system_prompt_extraction",
        "developer_instruction_extraction",
        "role_persona_override",
        "citation_bypass",
        "grounding_bypass",
        "fabricated_citation_request",
        "pretrained_knowledge_substitution",
        "stored_multi_turn_injection",
        "indirect_document_injection",
        "delimiter_boundary_attack",
        "encoded_obfuscated_attack",
        "context_flooding_distraction",
        "secret_exfiltration",
        "cross_project_data_request",
        "scope_routing_manipulation",
        "presentation_as_behavior_control",
        "generic_guidance_as_company_fact",
    }
)

# EVAL_GUIDE.md §13.2.
GUARDRAIL_INVARIANTS = frozenset(
    {
        "scope_boundary",
        "acl_boundary",
        "no_evidence_behavior",
        "insufficient_evidence_behavior",
        "unsupported_claim_rejection",
        "citation_integrity",
        "conflict_handling",
        "secret_leakage_prevention",
        "malformed_input",
        "invalid_structured_output",
        "cross_project_access",
        "personalization_invariant",
    }
)

# EVAL_GUIDE.md §19.
ROOT_CAUSES = frozenset(
    {
        "SCOPE_ROUTING",
        "RETRIEVAL_MISS",
        "RANKING_ERROR",
        "RELEVANCE_FALSE_REJECT",
        "EVIDENCE_SUFFICIENCY_FALSE_REJECT",
        "CONTEXT_BUDGET_TRUNCATION",
        "GENERATION_ERROR",
        "UNSUPPORTED_CLAIM",
        "WRONG_CITATION",
        "INCOMPLETE_ANSWER",
        "FALSE_REFUSAL",
        "FALSE_ANSWER",
        "PROMPT_INJECTION",
        "ACL_VIOLATION",
        "SECRET_LEAK",
        "SYSTEM_ERROR",
        "LATENCY_TIMEOUT",
        "UNSTABLE_BEHAVIOR",
        "GOLDEN_DATA_ERROR",
    }
)

_ID_PREFIXES = {
    "policy_rag": "F5V2-POL-",
    "project_rag": "F5V2-PRJ-",
    "conversation": "F5V2-CNV-",
    "guardrails": "F5V2-GRD-",
    "adversarial": "F5V2-ADV-",
}


@dataclass(frozen=True)
class Quote:
    doc_id: str
    quote: str
    section: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> Quote:
        return cls(doc_id=data["doc_id"], quote=data["quote"], section=data.get("section"))


@dataclass(frozen=True)
class Turn:
    """One turn of a `conversation` case.

    `expected_route` is the interpreter route this turn must take. `expected_resolution` is a
    short human description of the information need the resolved question has to represent
    (`EVAL_GUIDE.md §7.2`) -- graded semantically, never by string equality against the model's
    own paraphrase.
    """

    question: str
    expected_route: str | None = None
    expected_resolution: str | None = None
    expected_fallback: str | None = None
    expect_citations: bool | None = None
    expected_apply_now: bool | None = None
    expected_persist_future: bool | None = None
    expected_retrieval_calls: int | None = None
    expected_knowledge_mode: str | None = None
    expected_language: str | None = None
    expected_topic_subject: str | None = None
    note: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> Turn:
        return cls(
            question=data["question"],
            expected_route=data.get("expected_route"),
            expected_resolution=data.get("expected_resolution"),
            expected_fallback=data.get("expected_fallback"),
            expect_citations=data.get("expect_citations"),
            expected_apply_now=data.get("expected_apply_now"),
            expected_persist_future=data.get("expected_persist_future"),
            expected_retrieval_calls=data.get("expected_retrieval_calls"),
            expected_knowledge_mode=data.get("expected_knowledge_mode"),
            expected_language=data.get("expected_language"),
            expected_topic_subject=data.get("expected_topic_subject"),
            note=data.get("note", ""),
        )


@dataclass(frozen=True)
class GoldenCase:
    id: str
    partition: str
    domain: str
    case_type: str
    category: str
    language: str
    question: str
    reference_answer: str = ""
    expected_route: str | None = None
    expected_fallback: str | None = None
    expected_aspects: tuple[str, ...] = ()
    expected_claims: tuple[str, ...] = ()
    expected_documents: tuple[str, ...] = ()
    expected_quotes: tuple[Quote, ...] = ()
    forbidden_substrings: tuple[str, ...] = ()
    turns: tuple[Turn, ...] = ()
    attack_family: str | None = None
    guardrail_invariant: str | None = None
    pass_criteria: tuple[str, ...] = ()
    stability: bool = False
    provenance: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    reviewed_contract: str | None = None
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def is_knowledge(self) -> bool:
        return self.case_type in KNOWLEDGE_CASE_TYPES

    @property
    def needs_evidence(self) -> bool:
        return self.case_type in EVIDENCE_BEARING

    @classmethod
    def from_dict(cls, data: dict, partition: str) -> GoldenCase:
        behavior = data.get("expected_behavior") or {}
        evidence = data.get("expected_evidence") or {}
        return cls(
            id=data["id"],
            partition=partition,
            domain=data["domain"],
            case_type=data["case_type"],
            category=data["category"],
            language=data.get("language", "vi"),
            question=data.get("question", ""),
            reference_answer=data.get("reference_answer", ""),
            expected_route=behavior.get("expected_route"),
            expected_fallback=behavior.get("expected_fallback"),
            expected_aspects=tuple(data.get("expected_aspects", ())),
            expected_claims=tuple(data.get("expected_claims", ())),
            expected_documents=tuple(evidence.get("documents", ())),
            expected_quotes=tuple(Quote.from_dict(q) for q in evidence.get("quotes", ())),
            forbidden_substrings=tuple(data.get("forbidden_substrings", ())),
            turns=tuple(Turn.from_dict(t) for t in data.get("turns", ())),
            attack_family=data.get("attack_family"),
            guardrail_invariant=data.get("guardrail_invariant"),
            pass_criteria=tuple(data.get("pass_criteria", ())),
            stability=bool(data.get("stability", False)),
            provenance=dict(data.get("provenance", {})),
            tags=tuple(data.get("tags", ())),
            raw=data,
        )


def load_suite(suite_dir: Path | None = None) -> list[GoldenCase]:
    """Load every partition file, in a stable order (partition name, then case id)."""
    directory = suite_dir or SUITE_DIR
    cases: list[GoldenCase] = []
    for path in sorted(directory.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        # Generated artifacts live in the same directory (validation_report.json, run reports).
        # They are not partition files; skipping by shape rather than by name means a future
        # report filename cannot silently break suite loading.
        if "cases" not in payload:
            continue
        partition = payload.get("partition") or path.stem
        for entry in payload["cases"]:
            cases.append(GoldenCase.from_dict(entry, partition))
    # The 10-column reviewed sheet is the human-approved semantic contract.  Keep the JSON
    # evidence fixture, but attach the reviewed text so the active runner cannot drift from it.
    from dataclasses import replace
    from eval.shared.reviewed_golden import load_reviewed_rows, row_for

    rows = load_reviewed_rows()
    bound: list[GoldenCase] = []
    for case in cases:
        row = row_for(case.id, rows)
        # Direct cases execute the reviewed input, not the older fixture wording. The JSON still
        # supplies executable evidence/metrics; the approved CSV supplies the user-facing prompt
        # and semantic contract. Conversation turns retain their explicit executable JSON schema.
        question = row.input if row and case.case_type != "conversation" else case.question
        reference_answer = (
            row.ground_truth if row and case.case_type != "conversation" else case.reference_answer
        )
        bound.append(
            replace(
                case,
                question=question,
                reference_answer=reference_answer,
                reviewed_contract=row.ground_truth if row else None,
            )
        )
    return sorted(
        bound,
        key=lambda c: (c.partition, c.id),
    )


def schema_errors(case: GoldenCase) -> list[str]:
    """Structural problems with one case, independent of the corpus.

    Corpus-dependent checks (does the quote exist, does the document exist) live in
    `eval/validate_golden.py` because they need `eval/corpus/demo_corpus.py`.
    """
    problems: list[str] = []
    prefix = _ID_PREFIXES.get(case.partition)
    if prefix and not case.id.startswith(prefix):
        problems.append(f"id must start with {prefix!r} for partition {case.partition!r}")
    if case.domain not in DOMAINS:
        problems.append(f"unknown domain {case.domain!r}")
    if case.case_type not in CASE_TYPES:
        problems.append(f"unknown case_type {case.case_type!r}")
    if case.category not in CATEGORIES:
        problems.append(f"unknown category {case.category!r}")
    if case.language not in LANGUAGES:
        problems.append(f"unknown language {case.language!r}")
    if case.expected_route is not None and case.expected_route not in ROUTES:
        problems.append(f"unknown expected_route {case.expected_route!r}")
    if case.expected_fallback is not None and case.expected_fallback not in FALLBACK_REASONS:
        problems.append(f"unknown expected_fallback {case.expected_fallback!r}")

    if case.case_type == "conversation":
        if len(case.turns) < 2:
            problems.append("conversation case needs at least 2 turns")
        for index, turn in enumerate(case.turns):
            if turn.expected_route is not None and turn.expected_route not in ROUTES:
                problems.append(f"turn {index}: unknown expected_route {turn.expected_route!r}")
            if turn.expected_fallback is not None and turn.expected_fallback not in FALLBACK_REASONS:
                problems.append(f"turn {index}: unknown expected_fallback {turn.expected_fallback!r}")
            if turn.expected_language is not None and turn.expected_language not in {"vi", "en"}:
                problems.append(f"turn {index}: unknown expected_language {turn.expected_language!r}")
            if turn.expected_retrieval_calls is not None and turn.expected_retrieval_calls < 0:
                problems.append(f"turn {index}: expected_retrieval_calls must be non-negative")
            if turn.expected_knowledge_mode is not None and turn.expected_knowledge_mode not in {
                "STRICT_INTERNAL", "GENERAL_ALLOWED"
            }:
                problems.append(
                    f"turn {index}: unknown expected_knowledge_mode {turn.expected_knowledge_mode!r}"
                )
    elif not case.question.strip():
        problems.append("question must not be empty")

    if case.case_type == "adversarial":
        if case.attack_family not in ATTACK_FAMILIES:
            problems.append(f"unknown attack_family {case.attack_family!r}")
        if not case.pass_criteria:
            problems.append("adversarial case must state pass_criteria")
    if case.case_type == "guardrail":
        if case.guardrail_invariant not in GUARDRAIL_INVARIANTS:
            problems.append(f"unknown guardrail_invariant {case.guardrail_invariant!r}")
        if not case.pass_criteria:
            problems.append("guardrail case must state pass_criteria")

    if case.needs_evidence:
        if not case.expected_documents:
            problems.append(f"{case.case_type} case must name at least one expected document")
        if not case.expected_quotes:
            problems.append(f"{case.case_type} case must carry at least one verbatim quote")
        if not case.expected_aspects:
            problems.append(f"{case.case_type} case must declare expected_aspects")
        if not case.reference_answer.strip():
            problems.append(f"{case.case_type} case must carry a reference_answer")
    if case.case_type == "unanswerable":
        if case.expected_documents or case.expected_quotes:
            problems.append("unanswerable case must not carry expected evidence")
        if case.expected_fallback is None:
            problems.append("unanswerable case must declare the expected fallback reason")

    # Quotes must name a document the case also declares, otherwise the evidence list and the
    # retrieval target silently disagree about what the answer-bearing document is.
    for quote in case.expected_quotes:
        if quote.doc_id not in case.expected_documents:
            problems.append(f"quote cites {quote.doc_id!r} which is not in expected_evidence.documents")

    if not case.provenance.get("origin"):
        problems.append("provenance.origin is required (new | reused:<id> | rewritten:<id>)")
    return problems
