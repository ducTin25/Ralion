"""F6_RULE_MINING_SPEC.md §4.2 step 3 — one LLM call per evidence unit, no tool-calling
(mining pipeline invariant §0), structured {rule_text_draft, rationale, evidence_type,
reuse_scope} output. Uses the exact same evidence_type/reuse_scope taxonomy annotators used
by hand (annotation_guide.md §3.1/§3.2), so the fixture (Phase 4) is a fair comparison.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass

from langchain_openai import ChatOpenAI

from src.infrastructure.observability.langfuse import get_langchain_callbacks
from src.model.enums import RuleEvidenceType
from src.modules.knowledge.mining.evidence_grouping import EvidenceUnit

logger = logging.getLogger(__name__)

# Bounded fan-out for evidence-unit extraction calls — same asyncio.Semaphore idiom as
# src.services.plan_generation.content_llm's MAX_CONCURRENT_LLM_CALLS, defined locally rather
# than imported from there: that constant governs an unrelated feature's LLM budget, and
# importing it would create an accidental coupling between two independent features.
MAX_CONCURRENT_LLM_CALLS = 4
EXTRACTION_TIMEOUT_SECONDS = 60.0
EXTRACTION_BATCH_SIZE = 20

ELIGIBLE_EVIDENCE_TYPES = frozenset({RuleEvidenceType.REUSABLE_CORRECTION, RuleEvidenceType.CONVENTION})

# Fixed string per CLAUDE.md Phase 5 §2 (invariant-equivalent) — never let the model invent a
# rationale when the evidence text states none explicitly.
NO_EXPLICIT_RATIONALE = "Chưa tìm thấy lý do tường minh"

_VALID_TYPES = ", ".join(t.value for t in RuleEvidenceType)

_SYSTEM_PROMPT = f"""You classify one PR review evidence unit from a GitHub repository for F6 Rule Mining.

Output STRICT JSON with exactly these 4 keys, no others:
{{
  "evidence_type": one of {_VALID_TYPES},
  "reuse_scope": integer 0, 1, or 2,
  "rule_text_draft": string,
  "rationale": string
}}

evidence_type definitions:
- REUSABLE_CORRECTION: reviewer points out a mistake/anti-pattern and the correction generalizes to
  other code beyond the spot being fixed (test: "would this comment apply again 6 months from now on
  unrelated code written the old way?"). If the reason is tied to this function's specific business
  logic, it is LOCAL_CORRECTION instead, even if the wording sounds general.
- CONVENTION: reviewer states an existing project convention/pattern (style, naming, structure, error
  handling...) the PR violates or should follow, not tied to one specific bug.
- LOCAL_CORRECTION: correction only valid at this specific spot, tied to this function's business logic,
  does not generalize.
- RATIONALE: explains WHY a design decision was made; not a correction, not a convention.
- QUESTION_DISCUSSION: pure question or inconclusive discussion.
- NOISE_OTHER: none of the above (administrative, CI status, thanks/LGTM, filter artifact).
When genuinely unsure between REUSABLE_CORRECTION/CONVENTION and a weaker label, prefer the weaker
label (precision over recall — the same discipline a human annotator follows here).

reuse_scope definitions (only meaningful when evidence_type is REUSABLE_CORRECTION or CONVENTION):
- 0: only true for the exact case being fixed.
- 1: applies to a specific subsystem/API/pattern, not the whole codebase. Most real conventions land
  here — do not default to 2 just because something "sounds important".
- 2: applies project-wide (style guide, error handling pattern, naming convention, etc.).

rule_text_draft: ONE normalized sentence stating the rule, independent of this specific function's
business logic (so two syntactically different comments that express the same underlying rule produce
similar sentences). Empty string if evidence_type is not REUSABLE_CORRECTION or CONVENTION.

rationale: the explicit reason stated in the evidence text (look for "because", "since", "to avoid", "so
that", etc.), copied/paraphrased from the text. If no explicit reason is stated in the text, output
exactly this string, unchanged: "{NO_EXPLICIT_RATIONALE}". Do not invent or infer a reason that is not
stated in the text — this rule is absolute, even if a reason seems obvious from context.

Respond with the JSON object only, no markdown fences, no commentary."""


@dataclass(frozen=True)
class RuleCandidateExtraction:
    unit: EvidenceUnit
    evidence_type: RuleEvidenceType
    reuse_scope: int
    rule_text_draft: str
    rationale: str
    prompt_tokens: int | None
    completion_tokens: int | None
    model: str | None
    latency_ms: int
    error: str | None = None

    @property
    def eligible(self) -> bool:
        return self.error is None and self.evidence_type in ELIGIBLE_EVIDENCE_TYPES and self.reuse_scope >= 1


def _user_message(unit: EvidenceUnit) -> str:
    return "Evidence unit comments (in order):\n\n" + "\n\n---\n\n".join(unit.bodies)


async def extract_rule_candidate(llm: ChatOpenAI, unit: EvidenceUnit) -> RuleCandidateExtraction:
    """Never raises — a malformed/failed call degrades to an ineligible (NOISE_OTHER, error-set)
    result so the caller's step-4 filter naturally drops it, matching the worker-path discipline
    of not crashing a whole mining run over one bad LLM response (CLAUDE.md §3, F-07 lesson)."""
    started = time.monotonic()
    try:
        async with asyncio.timeout(EXTRACTION_TIMEOUT_SECONDS):
            response = await llm.ainvoke(
                [("system", _SYSTEM_PROMPT), ("user", _user_message(unit))],
                config={"callbacks": get_langchain_callbacks()},
            )
        latency_ms = round((time.monotonic() - started) * 1000)
        content = response.content if isinstance(response.content, str) else None
        if content is None:
            raise ValueError("LLM response content is not text")
        parsed = json.loads(content)
        evidence_type = RuleEvidenceType(parsed["evidence_type"])
        reuse_scope = int(parsed["reuse_scope"])
        rule_text_draft = str(parsed.get("rule_text_draft") or "")
        rationale = str(parsed.get("rationale") or NO_EXPLICIT_RATIONALE)
        usage = getattr(response, "usage_metadata", None) or {}
        metadata = getattr(response, "response_metadata", {}) or {}
        return RuleCandidateExtraction(
            unit=unit,
            evidence_type=evidence_type,
            reuse_scope=reuse_scope,
            rule_text_draft=rule_text_draft,
            rationale=rationale,
            prompt_tokens=usage.get("input_tokens"),
            completion_tokens=usage.get("output_tokens"),
            model=metadata.get("model_name") or metadata.get("model"),
            latency_ms=latency_ms,
        )
    except Exception as exc:  # noqa: BLE001 - worker path: one bad unit must not abort the run
        logger.warning("rule_mining_extraction_failed unit=%s error=%s", unit.evidence_unit_id, exc)
        return RuleCandidateExtraction(
            unit=unit,
            evidence_type=RuleEvidenceType.NOISE_OTHER,
            reuse_scope=0,
            rule_text_draft="",
            rationale=NO_EXPLICIT_RATIONALE,
            prompt_tokens=None,
            completion_tokens=None,
            model=None,
            latency_ms=round((time.monotonic() - started) * 1000),
            error=str(exc),
        )


async def extract_rule_candidates(
    llm: ChatOpenAI, units: Sequence[EvidenceUnit]
) -> list[RuleCandidateExtraction]:
    """Bounded-concurrency fan-out over extract_rule_candidate() (CLAUDE.md Phase 7). Each
    evidence unit's LLM call is independent — extract_rule_candidate() touches no shared state
    and no DB — so running up to MAX_CONCURRENT_LLM_CALLS of them at once is safe.

    asyncio.gather preserves the *input* order of `units` in its result list regardless of
    which call actually finishes first, and every result also self-describes its own
    evidence_unit_id via `.unit` — so no caller ever needs to trust completion order, only this
    list's positional/embedded correspondence to `units`.

    extract_rule_candidate() never raises (a failed call degrades to a result with `.error`
    set), and gather invokes each unit exactly once — no risk of duplicate results from this
    fan-out itself. Per-call retry for transient provider errors (429/5xx/timeout) already
    happens inside the ChatOpenAI client (`max_retries=2`, set in get_rule_mining_llm()), not
    here — this function adds scheduling only, no new retry policy.
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM_CALLS)

    async def _bounded(unit: EvidenceUnit) -> RuleCandidateExtraction:
        async with semaphore:
            return await extract_rule_candidate(llm, unit)

    results: list[RuleCandidateExtraction] = []
    for start in range(0, len(units), EXTRACTION_BATCH_SIZE):
        batch = units[start : start + EXTRACTION_BATCH_SIZE]
        results.extend(await asyncio.gather(*(_bounded(unit) for unit in batch)))
    return results
