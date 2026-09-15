"""Versioned, static system-prompt artifacts for grounded chat generation -- v8.

Supersedes v7 as the *selected* prompt pair, for the same reason v7 did not edit v6: telemetry
rows referencing `grounded-answer-v7` / `grounded-answer-v7-strict` must keep meaning what they
meant when they were written.

Delta over v7, and the whole reason this version exists: `_GENERAL_VS_PROJECT_INSTANCE_SECTION`.
Everything else is v7's sections imported verbatim, in v7's order.

Why (F5 audit, Thread B -- general-intent source selection, 2026-08-30): a GENERAL_ALLOWED turn
whose question asks about a concept/pattern/technology in general (e.g. "Sidecar pattern nói
chung dùng khi nào?") could still retrieve real, on-topic project evidence -- a name collision,
not a retrieval bug -- when this project happens to have its own component with the same name
(this project's own Sidecar). Live trace confirmed `knowledge_policy` was already correctly
`GENERAL_ALLOWED` and retrieval/ESG were already correctly finding SUFFICIENT project evidence;
the gap was entirely downstream, in the generator: nothing told it that evidence describing THIS
project's own instance does not answer a question asking about the pattern in general, so it drew
a claim from it anyway, answering with Thanos-specific detail instead of the general explanation
the question actually asked for.

This reuses the EXISTING `knowledge_policy`/BGK contract exactly as designed -- no new field, no
new gate, no parallel pipeline. `_GENERAL_VS_PROJECT_INSTANCE_SECTION` teaches the generator the
same question-form test `turn_interpreter.py`'s `knowledge_policy` name-collision rule (v16-v18,
CHANGE_LOG.md) already applies one layer up, for the same reason: is the question asking about the
concept itself, or about this project's own instance/location/configuration of it? A name
collision in the RETRIEVED evidence never changes which one the question is; only the generator
was missing this test, because §7.1's original `_GENERAL_GUIDANCE_SECTION` only ever described the
gap between "generic guidance" and "a claim about this project" in the ABSTRACT (no attribution),
never the case where retrieved evidence exists and is on-topic but still describes the wrong
(project) instance of what the question actually asked about (the general concept).
"""

from src.ai.orchestration.grounded_answer_prompt_v7 import (
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

PROMPT_VERSION = "grounded-answer-v8"
STRICT_PROMPT_VERSION = "grounded-answer-v8-strict"


# GENERAL_ALLOWED only: a STRICT_INTERNAL turn has no general_guidance to redirect to, and (§11.1)
# every POLICY turn is STRICT_INTERNAL unconditionally, so this ambiguity cannot arise there.
# Placed next to `_GENERAL_GUIDANCE_SECTION`, the other section that decides claim vs. guidance.
_GENERAL_VS_PROJECT_INSTANCE_SECTION = """
=== WHEN RETRIEVED EVIDENCE DESCRIBES THIS PROJECT'S OWN INSTANCE OF A GENERAL CONCEPT ===

On this GENERAL_ALLOWED turn, some retrieved evidence may describe THIS project's own instance of
a concept, pattern, or technology that shares a name with what the question actually asks about --
a name collision in what was retrieved, not a reason to treat it as relevant. Judge this by what
the QUESTION is asking about, never by whether a chunk happens to use the same word:

- If the question asks about the concept/pattern/technology ITSELF -- what it is, when or why to
  use it, how it compares to alternatives, its general tradeoffs -- and a retrieved chunk only
  describes THIS project's own instance/location/configuration of the same-named thing, that chunk
  does NOT support a claim answering the question. Do not cite it, do not draft a claim from it,
  no matter how topically close it looks. Answer the actual question from general_guidance
  instead, exactly as if no evidence had been retrieved for it.
- If the question instead asks about THIS project's own instance -- where it is implemented, how
  it is configured here, what it does in this codebase -- that same evidence is exactly what a
  claim should cite, as usual.
- A question can genuinely need both ("what is the sidecar pattern, and how does this project use
  it here?"). Answer the general half from general_guidance and the project-specific half as a
  cited claim, each covering only the part of the question it actually supports -- never let one
  half's evidence stand in for the other.

This does not enlarge what a claim may assert and does not change any evidence-sufficiency
result already reached -- it only decides which of an already-retrieved, already-accepted chunk's
facts belong in a claim versus in general_guidance for what THIS question is actually asking.
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
    _GENERAL_VS_PROJECT_INSTANCE_SECTION,
    _AUGMENTED_OUTPUT_CONTRACT,
)
