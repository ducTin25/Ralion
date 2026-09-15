"""Versioned, static system-prompt artifacts for grounded chat generation -- v7.

Supersedes v6 as the *selected* prompt pair, for the same reason v6 did not edit v5: telemetry
rows referencing `grounded-answer-v6` / `grounded-answer-v6-strict` must keep meaning what they
meant when they were written.

Delta over v6, and the whole reason this version exists: `_MULTI_ENTITY_CLAIM_SECTION`.
Everything else is v6's sections imported verbatim, in v6's order.

Why (F5 audit remediation, B2 follow-up, 2026-08-29): `chat_service.py`'s bounded multi-entity
retrieval fan-out (`_multi_entity_retrieval_queries`) gives a "list every component" question one
citable evidence chunk PER named entity instead of one broad chunk covering all of them. Live
result: `validator_fail` on exactly this shape ("liệt kê đầy đủ các thành phần của Thanos"), even
though each entity individually had grounding. Root cause is upstream of the validator: nothing
told the generator that evidence had become entity-scoped, so it kept drafting the way it always
had for a broad multi-item answer -- one sentence spanning two or three components, citing
whichever single chunk happened to be nearest. `claim_validation._entity_tokens` (B-07, unchanged)
then correctly rejects that claim: the sentence names entities the cited chunk never mentions. The
validator's behaviour is exactly right here -- a claim citing one chunk must not smuggle facts
about a different entity's chunk under the same citation. The fix belongs in what the generator
drafts, not in what the validator accepts: `_MULTI_ENTITY_CLAIM_SECTION` states the drafting rule
directly -- one claim, one named entity, one citation -- so claim granularity matches the
citation granularity the retrieval layer now actually provides. Generalizes to any evidence set
that is entity-scoped, not just this Thanos example.
"""

from src.ai.orchestration.grounded_answer_prompt_v6 import (
    _ANSWER_QUALITY_SECTION,
    _AUGMENTED_OUTPUT_CONTRACT,
    _EVIDENCE_LIMITS_SECTION,
    _GENERAL_GUIDANCE_SECTION,
    _PRESENTATION_SECTION,
    _STRICT_OUTPUT_CONTRACT,
    _TERMINOLOGY_SECTION,
    _TRUST_SECTION,
    _USER_CLAIM_SECTION,
    _V2_PREAMBLE,
    _compose,
)

PROMPT_VERSION = "grounded-answer-v7"
STRICT_PROMPT_VERSION = "grounded-answer-v7-strict"


# Placed immediately after `_TERMINOLOGY_SECTION`: both sections keep a claim's assertion aligned
# with what its OWN citation actually contains, just for a different mismatch -- wording there,
# entity scope here.
_MULTI_ENTITY_CLAIM_SECTION = """
=== WHEN EVIDENCE COVERS SEVERAL NAMED ITEMS (components, services, policies, steps) ===

When the question asks about multiple named items (e.g. "list every component and what it does"),
the evidence you were given may be organized per item -- one distinct citable chunk per named
item, not one chunk covering all of them together. Draft claims to match that: each claim states
a fact about exactly ONE named item and cites only the chunk(s) that actually discuss that item.
Never combine facts about two different named items into a single claim on the strength of one
citation -- if a sentence names item A and item B but only cites a chunk about A, split it into
separate claims, or drop the part about B if no chunk supports it. A claim's citation must fully
cover everything the claim asserts, not just the part that happens to be true.

If a named item has no supporting evidence at all, say so for that item specifically (per the
evidence-limits rule above) rather than folding it into a neighboring item's claim to avoid
mentioning the gap.
"""


STRICT_SYSTEM_INSTRUCTIONS = _compose(
    _V2_PREAMBLE,
    _TRUST_SECTION,
    _ANSWER_QUALITY_SECTION,
    _EVIDENCE_LIMITS_SECTION,
    _USER_CLAIM_SECTION,
    _TERMINOLOGY_SECTION,
    _MULTI_ENTITY_CLAIM_SECTION,
    _PRESENTATION_SECTION,
    _STRICT_OUTPUT_CONTRACT,
)

SYSTEM_INSTRUCTIONS = _compose(
    _V2_PREAMBLE,
    _TRUST_SECTION,
    _ANSWER_QUALITY_SECTION,
    _EVIDENCE_LIMITS_SECTION,
    _USER_CLAIM_SECTION,
    _TERMINOLOGY_SECTION,
    _MULTI_ENTITY_CLAIM_SECTION,
    _PRESENTATION_SECTION,
    _GENERAL_GUIDANCE_SECTION,
    _AUGMENTED_OUTPUT_CONTRACT,
)
