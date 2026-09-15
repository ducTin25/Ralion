"""Deterministic, server-authored description of how a prior turn ended.

Pure: no I/O, no LLM, no ORM import. `ChatMessage` already persists everything needed
(`grounded`, `fallback_reason`, `answer_status`) -- this module is the SINGLE place that turns
that persisted triple into a phrase, so the interpreter's `PriorTurn` and
`AnswerMode.CONVERSATION`'s transcript can never disagree about what happened on a turn.

Why this exists at all: the reported failures "sao lại không có nguồn?" / "vậy tại sao trước đó
bạn bảo không có nguồn" are questions about a prior turn's OUTCOME. The outcome was in the
database the whole time and reached neither the router nor the transcript, so the router could
not recognise the question and CONVERSATION mode could not answer it truthfully.

These strings are TRUSTED server text (never user- or model-authored) and are delivered to the
model unwrapped, per F5_SEMANTIC_TURN_INTERPRETER_REVIEW.md §5.1. They are not user-visible copy
and they are NOT a new `fallback_reason` vocabulary (rev. 2 §8: the user-visible reason set does
not grow) -- they are a description of an existing persisted reason.
"""

from __future__ import annotations

# Keyed by the persisted `ChatMessage.fallback_reason`. Any reason absent from this map degrades
# to `_UNKNOWN_FALLBACK` rather than being described wrongly.
_FALLBACK_DESCRIPTIONS: dict[str, str] = {
    "no_evidence": (
        "withheld: retrieval surfaced no internal source relevant to the question"
    ),
    "insufficient_evidence": (
        "withheld: internal sources were found and shown, but did not cover enough of the "
        "question to answer it"
    ),
    "validator_fail": (
        "withheld: internal sources were found, but the drafted answer could not be anchored to "
        "an exact quote from them, so it was not shown"
    ),
    "ambiguous_question": "withheld: the question had more than one plausible reading",
    "system_error": (
        "withheld: an internal dependency failed, so the internal sources could not be consulted "
        "at all -- this says nothing about whether such a source exists"
    ),
    "out_of_scope": "declined: judged outside what this assistant covers",
}

_UNKNOWN_FALLBACK = "withheld: no answer was shown for that turn"

_GROUNDED = "answered from internal sources, with citations"
_GENERAL_GUIDANCE = (
    "answered with general technical guidance only, explicitly marked as not drawn from internal "
    "documents"
)
_PLAIN = "answered without needing internal sources"


def describe_turn_outcome(
    *,
    grounded: bool,
    fallback_reason: str | None,
    answer_status: str | None,
) -> str:
    """One trusted phrase for a prior ASSISTANT turn, from its persisted columns only.

    Precedence is deliberate: `fallback_reason` wins over everything, because a fallback row is
    the case the user is most likely to be asking about, and `_fallback` always sets both
    `fallback_reason` and `answer_status="fallback"`.
    """
    if fallback_reason is not None:
        return _FALLBACK_DESCRIPTIONS.get(fallback_reason, _UNKNOWN_FALLBACK)
    if answer_status == "general_guidance":
        return _GENERAL_GUIDANCE
    if grounded:
        return _GROUNDED
    return _PLAIN
