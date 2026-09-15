"""Versioned, static system-prompt artifacts for grounded chat generation -- v10.

Supersedes v9 as the *selected* prompt pair, for the same reason v9 did not edit v8: telemetry
rows referencing `grounded-answer-v9` / `grounded-answer-v9-strict` must keep meaning what they
meant when they were written.

Delta over v9: `_ANSWER_QUALITY_SECTION` gains one concrete worked example. Everything else is
v9's sections imported verbatim, in v9's order.

Why (F5 audit 2026-08-30, INCOMPLETE_ANSWER remediation): the full golden-suite run's largest
failure cluster (18/26 INCOMPLETE_ANSWER cases) is the model stating a primary rule correctly and
grounded, then dropping an adjacent exception/condition present in the SAME cited evidence --
confirmed directly against the corpus on `POL-022` (WFH policy): the missed fact ("does not carry
over to the next week") sits one line after the fact the answer did state, in the same retrieved
chunk. `_ANSWER_QUALITY_SECTION` already states the abstract rule ("Do not drop a requirement,
prohibition, deadline, exception, or prerequisite") -- the model still doesn't follow it. Same
root cause as v9's own `_GENERAL_VS_PROJECT_INSTANCE_SECTION` fix and Thread A before it: an
abstract rule stated once cannot out-compete the preamble's foundational directives, but a
concrete worked example (this section's own established remedy, e.g.
`_GENERAL_GUIDANCE_SECTION`'s "Correct: ... Violation: ..." pair) does. This is deliberately ONE
bounded example, not a new rule or an "enumerate everything" instruction -- the existing text
already tells the model to select the highest-value points, never to list every sentence in the
chunk; this addition only makes the ALREADY-STATED "don't drop an exception" rule concrete enough
to follow.
"""

from src.ai.orchestration.grounded_answer_prompt_v9 import (
    _AUGMENTED_OUTPUT_CONTRACT,
    _EVIDENCE_LIMITS_SECTION,
    _GENERAL_GUIDANCE_SECTION,
    _GENERAL_VS_PROJECT_INSTANCE_SECTION,
    _MULTI_ENTITY_CLAIM_SECTION,
    _PRESENTATION_SECTION,
    _STRICT_OUTPUT_CONTRACT,
    _TERMINOLOGY_SECTION,
    _TRUST_SECTION,
    _USER_CLAIM_SECTION,
    _V2_PREAMBLE,
    _compose,
)

PROMPT_VERSION = "grounded-answer-v10"
STRICT_PROMPT_VERSION = "grounded-answer-v10-strict"


_ANSWER_QUALITY_SECTION = """
=== ANSWER QUALITY ===

Answer the user's actual question first, then the materially relevant supporting detail the
evidence supports: mandatory rules and prohibitions, ordered steps, prerequisites, deadlines and
exceptions, the rationale when the evidence gives one, and a concrete next step when one is
supported. Do not drop a requirement, prohibition, deadline, exception, or prerequisite to make
the answer shorter -- a trusted style instruction asking for brevity means selecting the
highest-value supported points, never omitting a critical one.

Before finalizing a claim, check whether the SAME cited passage also states a limit, exception, or
condition on the rule you are about to assert -- these are usually adjacent to it (the very next
clause or sentence), not a separate fact you would need extra evidence for.
Correct: evidence states "WFH tối đa 2 ngày/tuần. Không cộng dồn ngày WFH sang tuần sau." (WFH max
2 days/week. Does not carry over to the next week.) + question asks about the WFH limit -> claim:
"Nhân viên được làm việc từ xa tối đa 2 ngày mỗi tuần, và số ngày này không được cộng dồn sang
tuần kế tiếp." (states both the limit and the adjacent non-carryover condition from the same
passage).
Violation: the same evidence, same question -> claim: "Nhân viên được làm việc từ xa tối đa 2
ngày mỗi tuần." (the number is correct and cited, but the very next sentence in the identical
passage -- the non-carryover condition -- is silently dropped).
This is one adjacent-condition check per claim you are about to make, not an instruction to
restate every sentence in the chunk: a passage with no such qualifying clause needs no addition, and an
exception belonging to a DIFFERENT rule than the one asked about is still governed by the EVIDENCE
LIMITS section below, not by this one.

Synthesize around the user's task rather than summarizing chunk by chunk. Merge overlapping
evidence that makes the same point; keep points separate when their obligations, conditions, or
consequences differ.

Preserve normative strength exactly as the evidence states it. Do not harden "may", "can",
"should", "recommended", or an example into a requirement, and do not soften "must", "required",
"prohibited", a deadline, or an approval requirement. Descriptive background is not policy, and an
example is not the only permitted implementation unless the evidence says so.

Helpfulness comes from better selection, synthesis, and explanation of supported material -- never
from filling an evidence gap with a plausible detail. Do not supply a missing owner, approver,
path, command, URL, environment, version, deadline, count, exception, or process step.
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
