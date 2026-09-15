"""Case schemas shared across eval/{project_knowledge,rule_mining}.

Dataclasses, not Pydantic — the rest of the eval/golden-test tooling in this repo
(`eval/test_golden_set_f5.py`, `scripts/build_f6_eval_fixture.py`) reads JSON straight
into plain dict/dataclass structures rather than a Pydantic model layer, so this module follows
the same convention instead of introducing a new one.

Each domain's `ragas`/`guardrails`/`prompt_injection` case type below defines its own fields —
they are NOT meant to literally subclass a shared base at runtime (the two domains' cases have
almost no fields in common: F5 has questions/citations, F6 has raw_comment_bodies). `EvalCase`
exists only as the structural contract every case dict satisfies: an id and a case-shape
discriminator, which is what `report_format.CaseResult.case_id` keys off of.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CaseType = Literal["answerable", "unanswerable"]


@dataclass(frozen=True)
class EvalCase:
    case_id: str


# ---- project_knowledge -----------------------------------------------------------------


@dataclass(frozen=True)
class RagasCase(EvalCase):
    question: str
    expected_answer_summary: str
    expected_citations: list[str]
    case_type: CaseType
    domain_note: str
    expected_fallback_type: str | None = None  # required when case_type == "unanswerable"


@dataclass(frozen=True)
class GuardrailCase(EvalCase):
    user_message: str
    violation_type: str
    expected_behavior: str


@dataclass(frozen=True)
class InjectionCase(EvalCase):
    source_file: str
    injected_content: str
    injection_location: str
    user_question: str
    expected_behavior: str


# ---- rule_mining ------------------------------------------------------------------------


@dataclass(frozen=True)
class RuleMiningRagasCase(EvalCase):
    evidence_unit_id: str
    raw_comment_bodies: list[str]
    expected_evidence_type: str
    expected_reuse_scope: int
    expected_rule_family_id: str | None
    context_for_ragas: str  # raw_comment_bodies joined — RAGAS "context"


@dataclass(frozen=True)
class RuleMiningGuardrailCase(EvalCase):
    raw_comment_bodies: list[str]
    violation_type: str
    expected_behavior: str


@dataclass(frozen=True)
class RuleMiningInjectionCase(EvalCase):
    raw_comment_bodies: list[str]
    injection_variant: str
    expected_behavior: str
