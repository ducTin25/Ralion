"""Contract tests for `personalization.TONE_INSTRUCTIONS` (rewritten 2026-08-25).

These pin the PROPERTIES that make a tone preset a behavioural contract rather than a mood word.
They cannot prove the model obeys them -- that is live-eval work -- but they can prove the three
presets stay separable, stay presentation-only, and keep the specific boundary each one needs.
That matters because the failure mode here is silent: a preset that drifts back into adjectives
still renders, still passes every dispatch test, and simply stops changing anything.
"""

from __future__ import annotations

import pytest

from src.ai.orchestration.grounded_answer_prompt_v4 import (
    STRICT_SYSTEM_INSTRUCTIONS,
    SYSTEM_INSTRUCTIONS,
)
from src.ai.orchestration.personalization import (
    LANGUAGE_INSTRUCTIONS,
    LENGTH_INSTRUCTIONS,
    TONE_INSTRUCTIONS,
    AnswerLanguage,
    build_style_instruction,
)
from src.model.enums import ResponseLength, ResponseTone

_SPECIFIED_TONES = (ResponseTone.GUIDE, ResponseTone.MENTOR, ResponseTone.BUDDY)

# The five axes every specified tone must take a position on, in the same order, so the presets
# are diffable side by side (module docstring). A preset that drops an axis is how "GUIDE vs
# MENTOR" quietly collapses back into two synonyms for "be helpful".
_AXES = ("Mở đầu:", "Cấu trúc:", "Thuật ngữ:", "Xưng hô:", "Kết:")


def test_neutral_is_empty_and_stays_empty() -> None:
    """`NEUTRAL` == "" IS its contract: the base prompt's own register. Filling it in would change
    generation for every user who never opened the preferences panel, and would break the
    byte-identical default guarantee `test_answer_generator.py` pins."""
    assert TONE_INSTRUCTIONS[ResponseTone.NEUTRAL] == ""
    assert build_style_instruction(ResponseLength.STANDARD, ResponseTone.NEUTRAL) == ""


@pytest.mark.parametrize("tone", _SPECIFIED_TONES)
def test_every_specified_tone_covers_all_five_axes(tone: ResponseTone) -> None:
    preset = TONE_INSTRUCTIONS[tone]
    for axis in _AXES:
        assert axis in preset, f"{tone.value} does not take a position on {axis}"


@pytest.mark.parametrize("tone", _SPECIFIED_TONES)
def test_every_specified_tone_states_its_own_boundary(tone: ResponseTone) -> None:
    """Each preset carries the ONE failure mode its own axis settings invite -- not a copy of the
    generic invariant, which lives in the versioned prompt (see
    `test_tone_presets_do_not_restate_the_generic_presentation_invariant`)."""
    assert "Ranh giới của riêng phong cách này:" in TONE_INSTRUCTIONS[tone]


def test_the_three_specified_tones_are_pairwise_distinguishable() -> None:
    """Weak as a check, load-bearing as a tripwire: identical or near-identical presets are
    exactly what an "make the tones friendlier" edit produces, and nothing else in the suite
    would notice."""
    presets = [TONE_INSTRUCTIONS[tone] for tone in _SPECIFIED_TONES]
    assert len(set(presets)) == len(presets)
    for tone in _SPECIFIED_TONES:
        assert tone.name in TONE_INSTRUCTIONS[tone]


def test_mentor_never_authorizes_inventing_a_rationale() -> None:
    """The defect this rewrite fixes. The first pass said "giải thích lý do đằng sau quy ước khi
    phù hợp" with NO evidence qualifier -- an open invitation to supply a motive the documents
    never gave, on the one tone whose whole purpose is explanation. The gloss and the rationale
    must both be conditioned on the source."""
    preset = TONE_INSTRUCTIONS[ResponseTone.MENTOR]
    assert "chỉ trình bày lý do khi nguồn có nêu lý do đó" in preset
    assert "không tự suy ra" in preset.lower()
    assert "CHỈ khi nghĩa đó có sẵn trong nguồn" in preset


def test_buddy_reassurance_may_not_assert_a_social_fact() -> None:
    """The other defect this rewrite fixes: the first pass literally scripted "câu này ai mới vào
    cũng hỏi" as an example of good reassurance. That is an uncited claim about the company, made
    by the one tone least likely to be read as making a claim at all. The phrase must now appear
    only as a NEGATIVE example."""
    preset = TONE_INSTRUCTIONS[ResponseTone.BUDDY]
    assert "Không được khẳng định bất cứ điều gì về team, công ty hay người khác" in preset
    assert "đều là claim không có nguồn" in preset
    # Reassurance is scoped to the act of asking, which asserts nothing about the org.
    assert "chỉ được nói về việc HỎI" in preset


def test_tone_presets_do_not_restate_the_generic_presentation_invariant() -> None:
    """`grounded_answer_prompt_v4._PRESENTATION_SECTION` owns "a presentation control may never
    change a factual conclusion / the citation requirement / normative strength". Restating it
    per tone -- as the first pass did, three times -- is how a preset and the prompt drift apart,
    and the prompt module's own docstring names that as the reason presets live here instead.
    """
    for tone in _SPECIFIED_TONES:
        preset = TONE_INSTRUCTIONS[tone]
        assert "trích dẫn" not in preset.lower()
        assert "citation" not in preset.lower()
    for variant in (STRICT_SYSTEM_INSTRUCTIONS, SYSTEM_INSTRUCTIONS):
        assert "Follow it as a presentation control only." in " ".join(variant.split())


def test_precedence_note_appears_only_when_length_and_tone_can_conflict() -> None:
    """`CONCISE` ("Không giải thích thừa") and `MENTOR` (an in-place gloss) are both trusted
    system instructions pulling opposite ways. The precedence line resolves that once, and only
    when both presets are actually present -- a length-only or tone-only turn has no conflict to
    resolve and must stay byte-identical to the preset alone."""
    length_only = build_style_instruction(ResponseLength.CONCISE, ResponseTone.NEUTRAL)
    tone_only = build_style_instruction(ResponseLength.STANDARD, ResponseTone.MENTOR)
    both = build_style_instruction(ResponseLength.CONCISE, ResponseTone.MENTOR)

    assert length_only == LENGTH_INSTRUCTIONS[ResponseLength.CONCISE]
    assert tone_only == TONE_INSTRUCTIONS[ResponseTone.MENTOR]
    assert "độ dài quyết định" in both
    assert "độ dài quyết định" not in length_only
    assert "độ dài quyết định" not in tone_only


def test_language_instruction_still_composes_last() -> None:
    """Ordering is part of the contract: the language line must survive the precedence line being
    inserted ahead of it, and must remain the final instruction the model reads."""
    built = build_style_instruction(
        ResponseLength.CONCISE, ResponseTone.BUDDY, AnswerLanguage.EN
    )
    assert built.endswith(LANGUAGE_INSTRUCTIONS[AnswerLanguage.EN])


def test_unknown_enum_values_degrade_to_the_baseline() -> None:
    """Corrupted preference data predating an enum column must fall back to the empty baseline,
    never raise -- chat is a terminal, always-answer path."""
    assert build_style_instruction("NOT_A_LENGTH", "NOT_A_TONE") == ""  # type: ignore[arg-type]
