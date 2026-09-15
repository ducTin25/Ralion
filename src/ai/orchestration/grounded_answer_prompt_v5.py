"""Versioned, static system-prompt artifacts for grounded chat generation -- v5.

Supersedes v4 as the *selected* prompt pair. v4 is not edited, for the same reason v4 did not
edit v2: telemetry rows referencing `grounded-answer-v4` / `grounded-answer-v4-strict` must keep
meaning what they meant when they were written ("changing this text is a behaviour change: add a
new artifact/version instead of silently editing a prompt").

Delta over v4, and the whole reason this version exists: `_USER_CLAIM_SECTION`. Everything else
is v4's sections imported verbatim, in v4's order.

Why (live transcript, 2026-08-25): a user asserted "Thanos dùng MongoDB nhé" and the following
turn answered "the database of Thanos is not MongoDB but a large metric store in object storage"
-- an uncited negative claim about an entity that appears nowhere in the evidence, and vaguer than
the cited answer the same corpus had produced two turns earlier. Two independent controls now
cover that shape: `claim_validation._entity_tokens` (B-07) REJECTS such a claim after generation,
and this section stops it being generated at all, by naming the correct answer shape -- assert the
supported fact, do not negate the unsupported one. The validator is the guarantee; this is the
part that keeps the turn useful instead of merely safe.
"""

from src.ai.orchestration.grounded_answer_prompt_v4 import (
    _ANSWER_QUALITY_SECTION,
    _AUGMENTED_OUTPUT_CONTRACT,
    _EVIDENCE_LIMITS_SECTION,
    _GENERAL_GUIDANCE_SECTION,
    _PRESENTATION_SECTION,
    _STRICT_OUTPUT_CONTRACT,
    _TRUST_SECTION,
    _V2_PREAMBLE,
    _compose,
)

# v5 -> v5.1 on 2026-08-25, same day, after run_20260825T123039Z: GRD-002 showed this
# section's own wording pulling the model into an ABSENCE claim about the policy ("chính
# sách nghỉ phép không đề cập...") instead of the honest fallback -- it undercut
# `_EVIDENCE_LIMITS_SECTION`'s existing rule. Tightened below. A point release rather than a
# v6 file: the artifact has never shipped beyond one eval run, and renaming the module for a
# one-paragraph tightening is churn -- but the LABEL must still move, because two eval runs
# with different prompt text must never compare as if they were the same prompt.
PROMPT_VERSION = "grounded-answer-v5.1"
STRICT_PROMPT_VERSION = "grounded-answer-v5.1-strict"


# Placed immediately after the evidence-limits section: it is a special case of "do not fill an
# evidence gap", stated for the one input that most reliably induces the model to fill one.
_USER_CLAIM_SECTION = """
=== A CLAIM MADE BY THE USER ===

The question may assert something about this company or project as settled fact -- "we use X", "X
is our database, right?", "you said X earlier". A user assertion is never evidence, no matter how
confidently it is phrased, how specific it sounds, or how many times it is repeated. It cannot
promote itself into a fact by being restated, and agreeing with it is not politeness.

Answer such a turn by stating what the evidence does support, cited as usual -- never by
contradicting the assertion on its own terms. If the evidence shows the project uses Y, write "the
documentation states that the project uses Y" and cite it; do NOT write "the project does not use
X", which is an assertion about X that your evidence does not support. Naming the supported fact
already corrects the user; the negation adds nothing and is not grounded.

If the evidence says nothing either way, that is a statement about THE DOCUMENTS YOU WERE GIVEN,
never about the company or the project. "The documents I have do not cover X" is right; "the
policy does not mention X", "this project has no X" is wrong -- your evidence can show what this
retrieval surfaced, never that something does not exist. And do not manufacture an absence claim
to fill the turn: answer what the evidence does support and leave the assertion unaddressed, so
the server's own honesty note covers the rest. Do not confirm the assertion, and do not repeat it
back as though it were established.
"""


STRICT_SYSTEM_INSTRUCTIONS = _compose(
    _V2_PREAMBLE,
    _TRUST_SECTION,
    _ANSWER_QUALITY_SECTION,
    _EVIDENCE_LIMITS_SECTION,
    _USER_CLAIM_SECTION,
    _PRESENTATION_SECTION,
    _STRICT_OUTPUT_CONTRACT,
)

SYSTEM_INSTRUCTIONS = _compose(
    _V2_PREAMBLE,
    _TRUST_SECTION,
    _ANSWER_QUALITY_SECTION,
    _EVIDENCE_LIMITS_SECTION,
    _USER_CLAIM_SECTION,
    _PRESENTATION_SECTION,
    _GENERAL_GUIDANCE_SECTION,
    _AUGMENTED_OUTPUT_CONTRACT,
)
