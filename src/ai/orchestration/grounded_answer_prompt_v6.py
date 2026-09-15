"""Versioned, static system-prompt artifacts for grounded chat generation -- v6.

Supersedes v5 as the *selected* prompt pair, for the same reason v5 did not edit v4: telemetry
rows referencing `grounded-answer-v5.1` / `grounded-answer-v5.1-strict` must keep meaning what
they meant when they were written.

Delta over v5, and the whole reason this version exists: `_TERMINOLOGY_SECTION`. Everything else
is v5's sections imported verbatim, in v5's order.

Why (F5 audit remediation, B1, 2026-08-29 live transcript): "remote wipe là gì?" and "công ty có
sử dụng remote wipe không?" both hit `validator_fail`, twice, even though retrieval found and
cited the right material -- the equipment-loss policy that DOES cover remotely locking/disabling a
lost device, just in Vietnamese ("khóa thiết bị từ xa"), not the English term the user asked with.
Retrieval was not the problem (it found the chunk both times); the draft answer asserted "remote
wipe" as a claim, and `claim_validation._entity_tokens` (B-07) correctly rejected an entity token
the cited evidence never contains -- that check is not being loosened here, for the same reason
B-07 exists at all. The actual fix is upstream of it: `_TERMINOLOGY_SECTION` tells the generator to
draft its citable claims in the EVIDENCE's own wording when the question's term differs, and use
the user's term only as a gloss alongside a citation, never as the asserted fact itself. This is a
semantic instruction, not a hard-coded synonym table -- it generalizes to any term mismatch the
model can recognize as the same underlying fact, not a fixed VI/EN dictionary entry.
"""

from src.ai.orchestration.grounded_answer_prompt_v5 import (
    _ANSWER_QUALITY_SECTION,
    _AUGMENTED_OUTPUT_CONTRACT,
    _EVIDENCE_LIMITS_SECTION,
    _GENERAL_GUIDANCE_SECTION,
    _PRESENTATION_SECTION,
    _STRICT_OUTPUT_CONTRACT,
    _TRUST_SECTION,
    _USER_CLAIM_SECTION,
    _V2_PREAMBLE,
    _compose,
)

PROMPT_VERSION = "grounded-answer-v6"
STRICT_PROMPT_VERSION = "grounded-answer-v6-strict"


# Placed immediately after `_USER_CLAIM_SECTION`: both sections address the same discipline (draft
# only what the evidence itself supports, never what the question's own wording suggests), just
# for a different input -- an assertion there, a differing term here.
_TERMINOLOGY_SECTION = """
=== WHEN YOUR TERM DIFFERS FROM THE EVIDENCE'S TERM ===

The question may use a term, abbreviation, or translation for something the evidence describes
with different wording -- e.g. the user asks about "remote wipe" while the retrieved policy says
"khoa thiet bi tu xa" (remotely lock/disable the device). If the evidence clearly describes the
same thing the user is asking about, write the citable claim using the EVIDENCE's own wording, cited
as usual -- never restate the user's term as though it were the document's own language, and never
treat the user's term itself as a fact to be confirmed. You may gloss the user's term alongside the
cited wording (e.g. "the policy requires the device to be remotely locked/disabled [cited] -- this
is what covers a lost device"), but the asserted, citable claim must use words the evidence actually
contains, never words borrowed from the question. If the evidence does not describe the same thing
at all, say so honestly per the evidence-limits rule above -- do not force a connection between two
different things merely because their names are similar.
"""


STRICT_SYSTEM_INSTRUCTIONS = _compose(
    _V2_PREAMBLE,
    _TRUST_SECTION,
    _ANSWER_QUALITY_SECTION,
    _EVIDENCE_LIMITS_SECTION,
    _USER_CLAIM_SECTION,
    _TERMINOLOGY_SECTION,
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
    _PRESENTATION_SECTION,
    _GENERAL_GUIDANCE_SECTION,
    _AUGMENTED_OUTPUT_CONTRACT,
)
