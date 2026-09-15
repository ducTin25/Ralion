"""`turn_outcome.describe_turn_outcome` — the single derivation of "how did a prior turn end".

Pinned deliberately at the level of DISTINCTIONS rather than exact strings: what matters for the
reported failure ("sao lại không có nguồn?") is that `validator_fail` is never described as
"no source found", and that `system_error` never implies anything about whether a source exists.
"""

from __future__ import annotations

from src.ai.orchestration.turn_outcome import describe_turn_outcome


def _fallback(reason: str) -> str:
    return describe_turn_outcome(grounded=False, fallback_reason=reason, answer_status="fallback")


def test_fallback_reason_wins_over_every_other_column() -> None:
    """`_fallback` always sets both columns; the reason is the thing the user asks about."""
    assert _fallback("no_evidence") == describe_turn_outcome(
        grounded=True, fallback_reason="no_evidence", answer_status="answered"
    )


def test_validator_fail_is_not_described_as_a_missing_source() -> None:
    """Root cause F: sources WERE found -- only the quote anchoring failed. Conflating the two is
    what made the reported follow-up unanswerable."""
    described = _fallback("validator_fail")
    assert "were found" in described
    assert "no internal source" not in described
    assert described != _fallback("no_evidence")


def test_no_evidence_and_insufficient_evidence_stay_distinct() -> None:
    assert _fallback("no_evidence") != _fallback("insufficient_evidence")
    assert "no internal source" in _fallback("no_evidence")
    assert "did not cover enough" in _fallback("insufficient_evidence")


def test_system_error_says_nothing_about_whether_a_source_exists() -> None:
    """Invariant 8, carried into the description layer: an outage is not a knowledge gap."""
    described = _fallback("system_error")
    assert "dependency failed" in described
    assert "says nothing about whether such a source exists" in described


def test_unknown_fallback_reason_degrades_instead_of_being_described_wrongly() -> None:
    described = _fallback("some_reason_added_later")
    assert described == "withheld: no answer was shown for that turn"


def test_out_of_scope_is_declined_not_withheld() -> None:
    assert _fallback("out_of_scope").startswith("declined:")


def test_general_guidance_is_reported_as_non_internal() -> None:
    """A guidance-only turn persists `grounded=False`; it must not be reported as "answered
    without needing internal sources", which would hide that its content was general knowledge."""
    described = describe_turn_outcome(
        grounded=False, fallback_reason=None, answer_status="general_guidance"
    )
    assert "general technical guidance" in described
    assert "not drawn from internal documents" in described


def test_grounded_and_plain_answers_are_distinguished() -> None:
    grounded = describe_turn_outcome(grounded=True, fallback_reason=None, answer_status="answered")
    plain = describe_turn_outcome(grounded=False, fallback_reason=None, answer_status="answered")
    assert "with citations" in grounded
    assert grounded != plain
