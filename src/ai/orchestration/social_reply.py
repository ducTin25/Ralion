"""Deterministic social-turn detection and reply composition.

F5 Conversation Intelligence spec rev. 2, §6. Closed phrase space (5 subtypes x 2 languages) for
`classify_social`'s regex dictionary, zero LLM calls, zero retrieval -- the same shape
`personalization.py`'s static dict lookup already proves works for closed, high-confidence text.

**What belongs in that dictionary, restated 2026-08-25 after `_SELF_DOUBT` was removed.** A
subtype earns a regex only when its phrase space is genuinely CLOSED and enumerable: greeting,
thanks, farewell, acknowledgement, topic-change. Those are ritual formulas -- a user says one of a
few dozen things and means exactly one thing. Everything else is a semantic judgement and belongs
to `TurnInterpreter`, which is the component built to make one. `BUDDY_SUPPORT` was briefly given
a regex on the theory that its highest-frequency phrasings could be pinned deterministically; the
result was an assistant that answered "bạn thấy mình kém không?" and refused "tôi mệt quá", which
is a worse failure than answering neither, because it looks like a capability. Adding an
alternation is never the fix for a miss in an OPEN phrase space -- see `SocialIntent.BUDDY_SUPPORT`.

Three subtypes (`OTHER`, `LANGUAGE_PREFERENCE`, `BUDDY_SUPPORT`) are interpreter-only -- never
produced by `classify_social` itself, only by `TurnInterpreter`'s semantic judgment (see their
docstrings on `SocialIntent`) -- but still render through this same static `build_social_reply`
lookup, zero LLM calls at render time either way.

`classify_social` is the single source of truth `conversation_intent.classify_intent`
delegates to for the SOCIAL branch (ownership map, spec §13) -- there is exactly one
place in the codebase that decides whether a question is a social turn.

Matching discipline (§6.1): whole-utterance **anchoring**, not a residual-length
heuristic and not `MemoryConfig.followup_max_chars`/`followup_max_words` (those size an
unrelated retrieval-query-expansion window and are a weaker, coupled guarantee -- see the
spec for why that first-pass approach was rejected on review). A match requires the
ENTIRE normalized question to equal one of the closed phrases below: "cam on, con VPN
thi sao?" normalizes to a string that matches no pattern in full, so `classify_social`
returns None and the turn falls through to the CATALOG check, then KNOWLEDGE -- exactly
the desired outcome for a mixed turn.
"""

from __future__ import annotations

import enum
import re

from src.model.enums import ResponseTone


class SocialIntent(enum.StrEnum):
    GRATITUDE = "GRATITUDE"
    GREETING = "GREETING"
    FAREWELL = "FAREWELL"
    ACKNOWLEDGEMENT = "ACKNOWLEDGEMENT"
    TOPIC_CHANGE = "TOPIC_CHANGE"
    # Interpreter-only subtype (never produced by `classify_social`'s closed regex -- see
    # `turn_interpreter._parse`): pure small talk/feelings-sharing with no information request
    # that doesn't fit any of the other closed phrase categories (e.g. "I'm really happy",
    # "I'm just sharing my feeling"). The regex dictionary stays closed and enumerable; this
    # subtype exists so the `TurnInterpreter`'s own semantic SOCIAL judgment -- which already
    # generalizes far beyond the closed phrase list -- has a template to render instead of being
    # silently discarded for lack of one.
    OTHER = "OTHER"
    # Interpreter-only subtype (2026-08-23 fix, CHANGE_LOG.md): a request to switch which
    # language the assistant replies in, with no other new fact ("bạn nói tiếng việt đi", "please
    # speak Vietnamese, I don't understand English"). Split out from `OTHER` because a generic
    # "thanks for sharing" reply is a wrong answer to an actionable request -- the user expects
    # confirmation IN the requested language, not filler. Always paired with the interpreter's
    # own `presentation.language` field, which names the target language `build_social_reply`
    # renders into (never the language the request itself happened to be phrased in).
    LANGUAGE_PREFERENCE = "LANGUAGE_PREFERENCE"
    # Interpreter-only subtype (added 2026-08-25 Option A'; the regex that briefly backed it was
    # REMOVED 2026-08-25, see below): the user's own affect is the whole content of the turn --
    # tiredness, discouragement, feeling overwhelmed or stuck, self-doubt, or an explicit request
    # for encouragement, with no nameable subject to retrieve about. Split out of `OTHER` for
    # exactly the reason `LANGUAGE_PREFERENCE` was: `OTHER`'s "thanks for sharing" filler was
    # authored for POSITIVE affect ("I'm really happy") and is a wrong answer to distress.
    #
    # WHY THERE IS NO REGEX FOR THIS ANY MORE. A `_SELF_DOUBT` pattern used to sit in `_PATTERNS`
    # and short-circuit ahead of `ScopeGate`. It was removed because it was solving the wrong
    # problem: it made "bạn thấy mình kém không?" work while "tôi mệt quá" and "bạn động viên tôi
    # được không?" -- the same need, different words -- were still refused, and the only available
    # repair was another alternation, then another. The real defect was that `ScopeGate`, which
    # runs first on every turn, had no rule saying a new member's own onboarding morale is
    # something this assistant handles; the regex was standing in for that missing rule by routing
    # around the gate. That rule now exists (`scope_gate._SCOPE_SYSTEM`, v4), so affect turns reach
    # the interpreter on their merits and this subtype is selected SEMANTICALLY, from the
    # interpreter's `affect` field (`turn_interpreter.TurnAffect`) rather than from a phrase list.
    # Removing the fast path also means these turns now pass THROUGH the guardrail instead of
    # around it -- strictly safer than the shape it replaced.
    #
    # Boundary, enforced in `turn_interpreter._SYSTEM_INSTRUCTIONS` and restated in `scope_gate`:
    # affect WITH a nameable subject ("nản quá, auth module chạy sao vậy?") is KNOWLEDGE with the
    # affect carried only as a response modifier, and an affect wrapper around a role-change/
    # credential/PII request is OUT_OF_SCOPE at the gate before any route is chosen.
    BUDDY_SUPPORT = "BUDDY_SUPPORT"


_TRAILING_PUNCT = re.compile(r"[.!?…,\s]+$")
_TRAILING_FILLER_WORD = re.compile(r"\s*\b(?:nha|nhé|nhỉ|ạ|à|đi|nào)\b$", re.IGNORECASE)


def _normalize_whole_utterance(text: str) -> str:
    """Strip surrounding whitespace, casefold, strip a closed set of trailing
    punctuation/filler particles -- repeatedly, since a particle can be followed by more
    punctuation ("nha."). Never a length budget (§6.1)."""
    normalized = _TRAILING_PUNCT.sub("", text.strip().casefold())
    while True:
        stripped = _TRAILING_PUNCT.sub("", _TRAILING_FILLER_WORD.sub("", normalized))
        if stripped == normalized:
            return normalized
        normalized = stripped


# Each entry is a whole-utterance-anchored (^...$) pattern for exactly one closed
# subtype. Representative, not exhaustive -- authored against the eval fixture
# (eval/project_knowledge/conversation_intelligence/), extend by adding alternations
# here, never by loosening the anchor.
#
# 2026-08-22 live-probe finding (CHANGE_LOG.md): the first pass under-covered common natural
# phrasing -- "cảm ơn bạn nhiều" (both an addressee AND an intensifier together) fell through
# to KNOWLEDGE and got answered by the full retrieval pipeline instead of a template reply.
# Widened here to accept addressee/intensifier/prefix variants in flexible combination -- still
# a closed, enumerable alternation (adding alternations, not loosening the anchor discipline).
_GRATITUDE = re.compile(
    r"^(?:ok(?:ay)?|oke)?[,\s]*"
    r"(?:"
    r"(?:cảm|cám) ơn(?: (?:bạn|em|anh|chị))?(?: (?:rất )?nhiều)?(?: lắm)?"
    r"|thanks?(?: you)?(?: (?:so much|a lot|very much))?"
    r")$",
    re.IGNORECASE,
)
_GREETING = re.compile(
    r"^(?:xin chào|chào(?: (?:bạn|ralion))?|hi|hello|hey)(?: (?:bạn|there))?$", re.IGNORECASE
)
_FAREWELL = re.compile(
    r"^(?:tạm biệt|hẹn gặp lại|bye(?: bye)?|goodbye|see you(?: later)?)(?: (?:bạn|nhé))?$",
    re.IGNORECASE,
)
_ACKNOWLEDGEMENT = re.compile(
    r"^(?:ừm?\s+)?(?:ok(?:ay)?|oke|oki|ừm?|uhm|um|(?:đã |rõ )?hiểu rồi|được rồi|tốt|got it|"
    r"understood|noted|sounds good)$",
    re.IGNORECASE,
)
_TOPIC_CHANGE = re.compile(
    r"^(?:"
    r"(?:cho (?:mình|tôi) )?hỏi (?:cái|chuyện|điều) khác(?: được không)?"
    r"|đổi (?:sang )?chủ đề(?: khác)?(?: được không)?"
    r"|thôi khỏi"
    r"|let'?s talk about something else"
    r"|can we (?:talk about|discuss) something else"
    r")$",
    re.IGNORECASE,
)
_PATTERNS: tuple[tuple[SocialIntent, re.Pattern[str]], ...] = (
    (SocialIntent.GRATITUDE, _GRATITUDE),
    (SocialIntent.GREETING, _GREETING),
    (SocialIntent.FAREWELL, _FAREWELL),
    (SocialIntent.ACKNOWLEDGEMENT, _ACKNOWLEDGEMENT),
    (SocialIntent.TOPIC_CHANGE, _TOPIC_CHANGE),
)


def classify_social(question: str) -> SocialIntent | None:
    """Pure function of the raw question text. See module docstring for the anchoring
    discipline this depends on -- callers must never substitute a substring/`.search`
    match for this."""
    normalized = _normalize_whole_utterance(question)
    if not normalized:
        return None
    for intent, pattern in _PATTERNS:
        if pattern.match(normalized):
            return intent
    return None


_REPLIES: dict[SocialIntent, dict[str, str]] = {
    SocialIntent.GRATITUDE: {
        "vi": "Không có gì! Rất vui vì đã giúp được bạn. Bạn còn câu hỏi nào khác không?",
        "en": "You're welcome! Happy to help. Is there anything else I can help with?",
    },
    SocialIntent.GREETING: {
        "vi": "Chào bạn! Mình là trợ lý onboarding của Ralion, bạn cần hỏi gì hôm nay?",
        "en": "Hi! I'm Ralion's onboarding assistant. What can I help you with today?",
    },
    SocialIntent.FAREWELL: {
        "vi": "Tạm biệt! Cần gì cứ quay lại hỏi mình nhé.",
        "en": "Goodbye! Feel free to come back anytime you have another question.",
    },
    # Reworded 2026-08-25 (audit B-04). The old copy ("Được rồi!" / "Got it!") READ AS AGREEMENT,
    # and this subtype is reachable from a semantic label the interpreter GUESSES: live, "Tôi đã
    # nói ở trên rằng team dùng Redis đúng không?" was labelled ACKNOWLEDGEMENT and answered
    # "Được rồi!", confirming a premise that was never in the conversation. Routing is fixed at
    # the interpreter (verification questions are CONVERSATION now), so this is defense in depth:
    # a template on a zero-validation path must not be able to assert anything, and the neutral
    # wording below is a correct reply to a genuine "ok"/"hiểu rồi" as well.
    SocialIntent.ACKNOWLEDGEMENT: {
        "vi": "Vâng, bạn còn câu hỏi nào khác không?",
        "en": "Sure — anything else you'd like to ask?",
    },
    SocialIntent.TOPIC_CHANGE: {
        "vi": "Được thôi, bạn muốn hỏi về chủ đề gì?",
        "en": "Sure, what would you like to ask about instead?",
    },
    SocialIntent.OTHER: {
        "vi": "Cảm ơn bạn đã chia sẻ! Mình luôn sẵn sàng nếu bạn có câu hỏi về dự án hoặc chính sách.",
        "en": "Thanks for sharing! I'm here whenever you have a question about the project or policies.",
    },
    # Keyed by the TARGET language being switched to (see `SocialIntent.LANGUAGE_PREFERENCE`'s
    # docstring) -- e.g. a request phrased in English to switch to Vietnamese renders the "vi"
    # entry, confirming in Vietnamese, not the "en" entry confirming in English.
    SocialIntent.LANGUAGE_PREFERENCE: {
        "vi": "Được rồi, mình sẽ trả lời bằng tiếng Việt nhé! Bạn cần hỏi gì?",
        "en": "Sure, I'll reply in English. What would you like to ask?",
    },
    # Recognize -> Reframe -> Assist, with Assist phrased as a QUESTION, never a claim: this
    # template must never name a task, module, document, or any other project entity, because
    # nothing on this path is retrieved, cited, or validated (INV9 governs KNOWLEDGE mode; a
    # SOCIAL reply earns its exemption by making no factual claim at all). It also carries no
    # psychological advice -- severe-distress/crisis handling is an explicit non-goal for this
    # pass (2026-08-25 decision), so the reply stays a technical-help offer with a standing route
    # to a human, which is correct regardless of how serious the user's turn actually is.
    SocialIntent.BUDDY_SUPPORT: {
        "vi": (
            "Mới vào một dự án mà thấy khó là chuyện bình thường. Bạn đang vướng ở đâu? "
            "Cho mình biết task, module hoặc lỗi cụ thể, mình tra tài liệu dự án rồi giải "
            "thích lại cho bạn. Nếu là chuyện ngoài tài liệu, PM của project hoặc đội HR sẽ "
            "hỗ trợ bạn được."
        ),
        "en": (
            "Finding a new project hard at the start is completely normal. Where are you "
            "stuck? Tell me the specific task, module, or error and I'll look it up in the "
            "project's documentation and walk you through it. If it's something the docs "
            "don't cover, your PM or the HR team can help."
        ),
    },
}


# Personalization overlay (2026-08-25, Option A'). Same static, enum-keyed discipline as
# `personalization.py`'s `TONE_INSTRUCTIONS` -- a preference selects a preauthored string, it
# never introduces free-form text -- applied to the one place `ResponseTone` was being dropped on
# the floor: `_answer_social_mode` rendered `_REPLIES[intent][language]` with no tone dimension
# at all, which is the whole reason the SOCIAL branch "didn't personalize". No LLM call is
# involved: the output space of this branch is a closed set of a few sentences, so a lookup is
# the right realizer for it, and a generated one would add a second LLM call, a new failure
# mode, and an unvalidated free-text path on the one route that skips `ScopeGate`.
#
# Sparse on purpose: an intent with no entry here renders `_REPLIES` unchanged, so every
# pre-existing subtype stays byte-identical in every tone and only subtypes that genuinely read
# differently when warm need authoring. Adding one later is a dict entry, not a restructure.
_WARM_REPLIES: dict[SocialIntent, dict[str, str]] = {
    SocialIntent.BUDDY_SUPPORT: {
        "vi": (
            "Mình hiểu cảm giác đó — mới vào dự án ai cũng thấy ngợp một thời gian, không "
            "phải do bạn kém đâu. Bạn đang vướng chỗ nào? Nói mình nghe task, module hay lỗi "
            "cụ thể, mình tra tài liệu dự án rồi cùng bạn gỡ. Nếu là chuyện ngoài tài liệu, "
            "PM của project hoặc đội HR sẽ hỗ trợ bạn được."
        ),
        "en": (
            "I get that — everyone feels swamped for a while when they join a new project, "
            "and it's not a reflection on you. Where are you stuck? Tell me the task, module, "
            "or error and I'll dig through the project's documentation with you. If it's "
            "something the docs don't cover, your PM or the HR team can help."
        ),
    },
}

# Which `ResponseTone` values read as "warm". `MENTOR`/`BUDDY` are the two whose
# `TONE_INSTRUCTIONS` text already asks the grounded-answer path for exactly this register
# ("kiên nhẫn, khích lệ" / "gần gũi, thoải mái... có thể trấn an"), so keying off them here keeps
# one notion of tone across both paths rather than inventing a second, social-only preference.
_WARM_TONES = frozenset({ResponseTone.MENTOR, ResponseTone.BUDDY})


def build_social_reply(
    intent: SocialIntent, language: str, tone: ResponseTone = ResponseTone.NEUTRAL
) -> str:
    """Static dict lookup, same shape as `personalization.py`. `language` follows
    `chat_service._question_language`'s "vi"/"en" convention; any other value falls back
    to English rather than raising, since this is a terminal, always-answer path.

    `tone` defaults to `NEUTRAL` so every pre-existing caller keeps rendering byte-identical
    text (the same "default is not a regression" convention `build_style_instruction`'s
    `language=None` uses). An unrecognized tone -- corrupted data predating the enum column --
    falls into the plain bucket rather than raising, for the same reason.
    """
    templates = _REPLIES[intent]
    if tone in _WARM_TONES:
        templates = _WARM_REPLIES.get(intent, templates)
    return templates.get(language, templates["en"])
