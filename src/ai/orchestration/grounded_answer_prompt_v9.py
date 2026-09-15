"""Versioned, static system-prompt artifacts for grounded chat generation -- v9.

Supersedes v8 as the *selected* prompt pair, for the same reason v8 did not edit v7: telemetry
rows referencing `grounded-answer-v8` / `grounded-answer-v8-strict` must keep meaning what they
meant when they were written -- including the negative live result that motivated this version.

Delta over v8: `_GENERAL_VS_PROJECT_INSTANCE_SECTION` is rewritten and repositioned. Everything
else is v8's sections imported verbatim, in v8's order.

Why (F5 audit, Thread B, live re-verify after v8): a live check of the v8 fix against the exact
regression questions showed NO measurable change -- "Sidecar pattern nói chung dùng khi nào?"
still answered `answer_shape=internal_only` from this project's own Sidecar chunk
("Sidecar pattern được sử dụng để kết nối với các máy chủ Prometheus..."), and the two questions
phrased as "Sidecar ... là gì?/hoạt động thế nào?" came back `mixed` but still LED with
project-specific framing. Root cause, by direct analogy to Thread A's v20-v23 sequence
(CHANGE_LOG.md): the v2 preamble's very first sentence -- "Answer only from the retrieved
context" -- is read before anything else and is a strong, foundational directive to use whatever
evidence was provided; v8's rule, an abstract paragraph placed near the END of the prompt (after
`_GENERAL_GUIDANCE_SECTION`), could not out-compete it. The preamble itself is not editable
(§7.1 rule 8, pinned by `test_v8_both_variants_carry_the_v2_preamble_verbatim`) -- exactly like
Thread A, the fix is not more abstract restatement but a concrete worked example, matching the
one section in this same prompt already confirmed load-bearing in live testing
(`_GENERAL_GUIDANCE_SECTION`'s own "Correct: ... Violation: ..." pair) -- and moved to right after
`_TRUST_SECTION`, the earliest point after the preamble a GENERAL_ALLOWED-only rule can appear.
"""

from src.ai.orchestration.grounded_answer_prompt_v8 import (
    _ANSWER_QUALITY_SECTION,
    _AUGMENTED_OUTPUT_CONTRACT,
    _EVIDENCE_LIMITS_SECTION,
    _GENERAL_GUIDANCE_SECTION,
    _MULTI_ENTITY_CLAIM_SECTION,
    _PRESENTATION_SECTION,
    _STRICT_OUTPUT_CONTRACT,
    _TERMINOLOGY_SECTION,
    _TRUST_SECTION,
    _USER_CLAIM_SECTION,
    _V2_PREAMBLE,
    _compose,
)

PROMPT_VERSION = "grounded-answer-v9"
STRICT_PROMPT_VERSION = "grounded-answer-v9-strict"


# GENERAL_ALLOWED only (same reasoning as v8): a STRICT_INTERNAL turn has no general_guidance to
# redirect a name-collision claim into, and (§11.1) every POLICY turn is STRICT_INTERNAL
# unconditionally. Positioned right after `_TRUST_SECTION` -- the earliest point after the
# (non-editable) v2 preamble a GENERAL_ALLOWED-only rule can appear -- rather than near the end,
# after `_GENERAL_GUIDANCE_SECTION` where v8 placed it and measured no live effect.
_GENERAL_VS_PROJECT_INSTANCE_SECTION = """
=== A RETRIEVED CHUNK ABOUT THIS PROJECT IS NOT EVIDENCE FOR A GENERAL QUESTION ===

Some retrieved evidence may describe THIS project's own instance of a concept, pattern, or
technology that shares a name with what the question actually asks about -- a name collision in
what was retrieved, not evidence you should use. A chunk being ABOUT something with a matching
name does not make it evidence FOR the question; only a chunk that actually answers the question
you were asked belongs in a claim, regardless of how topically close it looks.

Correct: question = "Sidecar pattern nói chung dùng khi nào?" (asks about the PATTERN in
general) + the only retrieved chunk describes this project's own Sidecar component -> claims: [],
general_guidance: [the general pattern explanation, from your own knowledge, exactly as if that
chunk had never been retrieved].
Violation: drafting a claim like "Sidecar pattern được sử dụng để kết nối với các máy chủ
Prometheus và sao lưu dữ liệu" (citing the project's own chunk) as the answer to that same
question -- every word of the claim is true and properly cited, but it answers a different,
narrower question (what THIS project's Sidecar does) than the one actually asked (when to use the
pattern in general).

If the question instead asks about THIS project's own instance -- where it is implemented, how it
is configured here, what it does in this codebase -- that same chunk is exactly the right
citation, as usual. A question can ask both ("what is the sidecar pattern, and how does this
project use it here?"); answer each half only from the source that actually supports it, and
never let one half's evidence stand in for the other.
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
    _GENERAL_VS_PROJECT_INSTANCE_SECTION,
    _ANSWER_QUALITY_SECTION,
    _EVIDENCE_LIMITS_SECTION,
    _USER_CLAIM_SECTION,
    _TERMINOLOGY_SECTION,
    _MULTI_ENTITY_CLAIM_SECTION,
    _PRESENTATION_SECTION,
    _GENERAL_GUIDANCE_SECTION,
    _AUGMENTED_OUTPUT_CONTRACT,
)
