"""Unit tests for `classify_social`/`build_social_reply` (implementation spec §6). Pure function,
no DB, no LLM -- exercises the closed, whole-utterance-anchored regex dictionary directly.

2026-08-23 root-cause fix (CHANGE_LOG.md): "oke" fell through this classifier to a full KNOWLEDGE
pipeline call and eventually an out-of-scope fallback, because only "ok"/"okay" were in the
closed ACKNOWLEDGEMENT alternation. This file pins the (small, enumerated, still-closed) widening
that fixes that -- and pins that the classifier stays narrow: it must NOT match open-ended
feelings/small-talk text (that generalization is the `TurnInterpreter`'s job via `social_intent`,
covered in `tests/test_ai/test_turn_interpreter.py`).
"""

from __future__ import annotations

import pytest

from src.ai.orchestration.social_reply import SocialIntent, build_social_reply, classify_social
from src.model.enums import ResponseTone


@pytest.mark.parametrize(
    "question",
    [
        "hi",
        "Hello",
        "hey",
        "hi there",
        "chào",
        "chào bạn",
        "xin chào",
        "Chào Ralion",
    ],
)
def test_greetings_are_classified(question: str) -> None:
    assert classify_social(question) is SocialIntent.GREETING


@pytest.mark.parametrize(
    "question",
    [
        "thanks",
        "thank you",
        "thanks so much",
        "cảm ơn",
        "cảm ơn bạn",
        "cảm ơn bạn nhiều",
        "cám ơn nhiều lắm",
        "ok cảm ơn",
    ],
)
def test_gratitude_is_classified(question: str) -> None:
    assert classify_social(question) is SocialIntent.GRATITUDE


@pytest.mark.parametrize(
    "question",
    [
        "bye",
        "goodbye",
        "see you",
        "see you later",
        "tạm biệt",
        "hẹn gặp lại",
    ],
)
def test_farewells_are_classified(question: str) -> None:
    assert classify_social(question) is SocialIntent.FAREWELL


@pytest.mark.parametrize(
    "question",
    [
        # Original closed forms -- must keep working.
        "ok",
        "okay",
        "OK",
        "hiểu rồi",
        "đã hiểu rồi",
        "được rồi",
        "got it",
        "understood",
        "noted",
        "sounds good",
        # Root-cause regression: colloquial spelling variants that were previously missed.
        "oke",
        "Oke",
        "oki",
        "ừ",
        "ừm",
        "uhm",
        "um",
        # Trailing particle/punctuation stripping still applies to the widened forms.
        "oke nha",
        "oke.",
        "oke!",
    ],
)
def test_acknowledgements_including_colloquial_variants_are_classified(question: str) -> None:
    assert classify_social(question) is SocialIntent.ACKNOWLEDGEMENT


@pytest.mark.parametrize(
    "question",
    [
        "hỏi cái khác",
        "đổi chủ đề",
        "đổi sang chủ đề khác được không",
        "let's talk about something else",
        "can we talk about something else",
    ],
)
def test_topic_change_is_classified(question: str) -> None:
    assert classify_social(question) is SocialIntent.TOPIC_CHANGE


@pytest.mark.parametrize(
    "question",
    [
        # Open-ended feelings/small talk: outside the closed dictionary by design -- this is what
        # `TurnInterpreter.social_intent` (OTHER) exists to cover, not a regex expansion.
        "I'm really happy",
        "I'm just sharing my feeling",
        "vui quá",
        "hôm nay mình rất vui",
        # Mixed social + knowledge turn must NOT match -- has to fall through to KNOWLEDGE.
        "cảm ơn, còn VPN thì sao?",
        "thanks, but what is our VPN policy?",
        # Language-switch requests: also interpreter-only (`SocialIntent.LANGUAGE_PREFERENCE`),
        # not in the closed regex dictionary either.
        "bạn nói tiếng việt đi, mình không hiểu tiếng anh",
        "please speak Vietnamese, I don't understand English",
        # Onboarding distress: interpreter-only in its entirety since 2026-08-25 -- see
        # `test_distress_is_no_longer_matched_by_the_closed_dictionary` for why the regex that
        # briefly covered part of this space was deleted rather than extended.
        "mới vào project mà thấy ngợp thật",
        "task này khó quá",  # names a subject -> must reach retrieval, never a template
        "mình thấy module auth kém quá",  # ditto: "kém" about a MODULE, not about the user
        "",
        "   ",
    ],
)
def test_non_social_and_mixed_turns_do_not_match(question: str) -> None:
    assert classify_social(question) is None


def test_build_social_reply_covers_the_interpreter_only_other_subtype() -> None:
    """`SocialIntent.OTHER` is never produced by `classify_social` itself (see
    `test_non_social_and_mixed_turns_do_not_match` above) but must still have a renderable
    template for the `TurnInterpreter` path (`turn_interpreter.py`'s `social_intent` field)."""
    assert build_social_reply(SocialIntent.OTHER, "vi")
    assert build_social_reply(SocialIntent.OTHER, "en")


def test_build_social_reply_language_preference_confirms_in_the_target_language() -> None:
    """`SocialIntent.LANGUAGE_PREFERENCE` (2026-08-23 fix, CHANGE_LOG.md): the `language`
    argument is the TARGET language being switched to, not the language the request was phrased
    in -- `build_social_reply` must render the confirmation IN that target language, distinct
    from `OTHER`'s generic filler reply."""
    vi_reply = build_social_reply(SocialIntent.LANGUAGE_PREFERENCE, "vi")
    en_reply = build_social_reply(SocialIntent.LANGUAGE_PREFERENCE, "en")
    assert "Việt" in vi_reply
    assert "English" in en_reply
    assert vi_reply != build_social_reply(SocialIntent.OTHER, "vi")
    assert en_reply != build_social_reply(SocialIntent.OTHER, "en")


def test_build_social_reply_covers_the_buddy_support_subtype() -> None:
    """`SocialIntent.BUDDY_SUPPORT` (2026-08-25) is interpreter-only like `OTHER`, and must
    render distinctly from it: `OTHER`'s "thanks for sharing" was authored for positive affect
    and is the wrong reply to distress -- rendering the same string for both would silently undo
    the split."""
    for language in ("vi", "en"):
        buddy = build_social_reply(SocialIntent.BUDDY_SUPPORT, language)
        assert buddy
        assert buddy != build_social_reply(SocialIntent.OTHER, language)


@pytest.mark.parametrize("language", ["vi", "en"])
def test_buddy_support_reply_never_names_a_project_entity(language: str) -> None:
    """The whole reason this branch can skip retrieval, citation validation, and INV9 is that it
    makes no factual claim. The template offers help as a QUESTION and must never assert a task,
    module, or document exists -- pin the property, since a later copy edit is exactly how it
    would be lost."""
    for tone in ResponseTone:
        reply = build_social_reply(SocialIntent.BUDDY_SUPPORT, language, tone)
        assert "?" in reply  # Assist is phrased as a question, not a claim
        assert "`" not in reply  # no code/entity identifiers
        assert not any(ch.isdigit() for ch in reply)  # no version/ticket/doc numbers


@pytest.mark.parametrize("language", ["vi", "en"])
def test_warm_tones_render_a_distinct_buddy_support_reply(language: str) -> None:
    """Option A' (2026-08-25): personalization on this branch is a static warm/plain lookup, not
    a generated reply. MENTOR/BUDDY -- the two tones whose `TONE_INSTRUCTIONS` already ask the
    grounded path for this register -- must select the warm variant; NEUTRAL/GUIDE must not."""
    plain = build_social_reply(SocialIntent.BUDDY_SUPPORT, language, ResponseTone.NEUTRAL)
    assert build_social_reply(SocialIntent.BUDDY_SUPPORT, language, ResponseTone.GUIDE) == plain
    for warm in (ResponseTone.MENTOR, ResponseTone.BUDDY):
        assert build_social_reply(SocialIntent.BUDDY_SUPPORT, language, warm) != plain


def test_default_tone_is_not_a_regression_for_pre_existing_subtypes() -> None:
    """Every subtype that predates the tone dimension must render byte-identically in every
    tone -- `_WARM_REPLIES` is deliberately sparse, and an accidental entry there would silently
    change shipped copy. Same "default is not a regression" discipline as
    `build_style_instruction`'s `language=None`."""
    for intent in SocialIntent:
        if intent is SocialIntent.BUDDY_SUPPORT:
            continue
        for language in ("vi", "en"):
            baseline = build_social_reply(intent, language)
            for tone in ResponseTone:
                assert build_social_reply(intent, language, tone) == baseline


def test_unknown_language_and_tone_degrade_instead_of_raising() -> None:
    """Terminal, always-answer path: corrupted preference data predating an enum column must
    degrade to a renderable reply, never take chat down."""
    assert build_social_reply(SocialIntent.BUDDY_SUPPORT, "fr") == build_social_reply(
        SocialIntent.BUDDY_SUPPORT, "en"
    )
    assert build_social_reply(SocialIntent.BUDDY_SUPPORT, "vi", "NOT_A_TONE") == build_social_reply(  # type: ignore[arg-type]
        SocialIntent.BUDDY_SUPPORT, "vi", ResponseTone.NEUTRAL
    )


@pytest.mark.parametrize(
    "question",
    [
        # The three turns of the reported transcript, plus the shapes a phrase list would have
        # had to be extended with next.
        "tôi mệt quá",
        "bạn động viên tôi được không ?",
        "bạn có thấy tôi kém không ?",
        "Bạn có thấy mình kém cỏi ko",
        "Mình hỏi là bạn có thấy mình kém không ?",
        "mình có tệ lắm không?",
        "tôi thấy mình kém quá",
        "chán quá đi mất",
        "nói gì đó cho mình đỡ nản đi",
        "mới vào project mà thấy ngợp thật",
        "Do you think I am bad at this?",
        "I feel like I am not good enough",
        "can you cheer me up?",
    ],
)
def test_distress_is_no_longer_matched_by_the_closed_dictionary(question: str) -> None:
    """The deletion of `_SELF_DOUBT`, pinned as a POSITIVE assertion so it cannot be undone by
    reflex.

    A regex briefly covered a subset of these and was removed on 2026-08-25. The reason is in the
    parametrization itself: the first four lines used to match and the rest did not, which is an
    assistant that answers "bạn có thấy mình kém không?" and refuses "tôi mệt quá". Every one of
    these is the same need. A phrase list can only ever cover the shapes someone thought to write
    down, and the repair for each miss is another alternation -- which is how a closed dictionary
    stops being closed.

    These are now the `TurnInterpreter`'s job, selected from `TurnAffect.SUPPORT_NEEDED` rather
    than from wording (see `test_chat_buddy_support.py` for the dispatch side). If a future change
    makes any of these match here again, the phrase-mining approach has come back.
    """
    assert classify_social(question) is None


@pytest.mark.parametrize(
    "question",
    [
        # A subject the user could be ANSWERED about -> must reach retrieval, never a template.
        "mình thấy module auth kém quá",
        "bạn có thấy tài liệu này kém không?",
        "task này khó quá",
        "nản quá, auth module hoạt động thế nào?",
        "mệt thật, VPN của project cấu hình ở đâu?",
        # Affect + a trailing request: the anchor is what stops this, and it must keep stopping it.
        "mình hỏi là bạn có thấy mình kém không, còn VPN thì sao?",
    ],
)
def test_affect_with_a_subject_never_matches_the_closed_dictionary(question: str) -> None:
    """Unchanged property, restated for the mixed turns this redesign is required to preserve. A
    match here would swallow an answerable question behind a template -- a failure mode much
    harder to notice than the cold refusal that motivated the redesign, because it looks like an
    answer. Whole-utterance anchoring is what rules it out for the subtypes that DO have a regex.
    """
    assert classify_social(question) is None


def test_b04_acknowledgement_template_does_not_read_as_agreement() -> None:
    """Audit B-04, defense in depth. This subtype is reachable from a label the interpreter
    GUESSES, on a branch with no validation of any kind, so its template must be incapable of
    confirming anything. "Được rồi!"/"Got it!" read as agreement and, live, confirmed a premise
    ("Tôi đã nói ở trên rằng team dùng Redis đúng không?") that was never in the conversation.

    Asserted as absence of the two agreement openers rather than as an exact string, so rewording
    for tone stays free -- what must not come back is a template that AGREES."""
    for language in ("vi", "en"):
        reply = build_social_reply(SocialIntent.ACKNOWLEDGEMENT, language)
        assert not reply.startswith("Được rồi")
        assert not reply.startswith("Got it")
        # Still a real acknowledgement of an "ok"/"hiểu rồi", not a dead end.
        assert reply.strip().endswith("?")
