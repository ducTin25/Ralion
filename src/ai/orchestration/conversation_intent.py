"""Conversation-intent routing (weakness #4, CHANGE_LOG.md 2026-08-21).

Root cause: every question — including one about the conversation itself, e.g. "câu đầu tiên
tôi hỏi về gì?" — was forced through the knowledge-RAG pipeline. INV9 requires factual claims to
be grounded in retrieved PROJECT/POLICY evidence, but a meta-question about the dialogue has no
such evidence to retrieve: it fails with `insufficient_evidence`/`no_evidence` no matter how the
sliding-window size or `query_condenser` heuristics are tuned, because those only affect what
retrieval sees, not whether retrieval is the right tool at all.

This module decides, from the raw question alone and BEFORE `query_condenser`/retrieval ever
run, whether a turn is:

* `KNOWLEDGE` — needs PROJECT/POLICY evidence and citation validation (INV9, unchanged); or
* `CONVERSATION` — needs only this conversation's own persisted, authorized history (see
  `conversation_answer.py` and the CONVERSATION_GROUNDED addendum in ARCHITECTURE.md).

Deterministic on purpose (CLAUDE.md §7's audit-before-LLM discipline): the target phrase space —
self-reference to this dialogue, its turns, or "what was asked/said" — is narrow and closed
enough that a small marker-based classifier (same shape as `query_condenser`'s follow-up
markers) reaches usable precision without an extra LLM round trip on every turn. If eval data
later shows this classifier missing real meta-questions or over-firing on real domain questions,
the fix is to calibrate it against a fixture the same way `scope_gate`/`evidence_sufficiency_gate`
were calibrated — not to hand-tune it against the examples in this file.

Precision over recall, and the reverse trade-off from `query_condenser`'s markers: there, a
false-positive follow-up only *expands* a retrieval query and `RelevanceGate` still scores the
original question, so over-triggering is cheap. Here, a false CONVERSATION verdict skips
retrieval entirely — a real knowledge question routed here would silently lose its evidence and
get answered from chit-chat history instead. When a question is ambiguous, this classifier
resolves to `KNOWLEDGE`, and normal domain follow-ups (coreference, "what about X") must keep
going through `KNOWLEDGE` exactly as before.
"""

from __future__ import annotations

import enum
import re

from src.ai.orchestration.social_reply import classify_social


class AnswerMode(enum.StrEnum):
    KNOWLEDGE = "KNOWLEDGE"
    CONVERSATION = "CONVERSATION"
    SOCIAL = "SOCIAL"
    CATALOG = "CATALOG"


# Each pattern is an independent, fairly narrow semantic category (see module docstring for why
# precision is favoured over recall). A question matches CONVERSATION if ANY pattern fires.
_META_PATTERNS: tuple[str, ...] = (
    # An explicit noun naming the dialogue/session itself as the thing being asked about.
    r"\bcuộc trò chuyện\b",
    r"\bcuộc hội thoại\b",
    r"\bđoạn (?:hội thoại|chat|trò chuyện)\b",
    r"\bbuổi (?:trò chuyện|chat)\b",
    r"\bthis conversation\b",
    r"\bour conversation\b",
    r"\bthis chat\b",
    r"\bour chat\b",
    r"\bthis discussion\b",
    r"\bour discussion\b",
    r"\bthis thread\b",
    r"\bour thread\b",
    # Ordinal/temporal reference to one's own earlier turn ("câu hỏi đầu tiên", "first question").
    r"\bcâu (?:hỏi )?(?:đầu tiên|đầu|trước đó|trước|gần đây nhất|vừa rồi)\b",
    r"\b(?:first|previous|earlier|last)\s+question\b",
    # Asking what was asked/said — by either party, in either language, in either word order.
    r"\btôi (?:đã |vừa |mới )?hỏi (?:gì|những gì|về (?:gì|những gì))\b",
    r"\b(?:những gì|điều gì) (?:tôi|mình|chúng ta) (?:đã |vừa )?(?:hỏi|nói)\b",
    r"\bchúng ta (?:vừa |mới )?(?:nói|hỏi|trao đổi|thảo luận) (?:về )?(?:gì|những gì)\b",
    r"\bbạn (?:vừa |mới )?(?:nói|trả lời) (?:gì|những gì)\b",
    r"\bwhat (?:did|have) (?:i|we) ask(?:ed)?\b",
    r"\bwhat did (?:we|you) (?:talk|discuss)(?:ed)?\b",
    r"\bwhat did you (?:just )?say\b",
    # Compare/revisit something said earlier — requires an explicit speaker (tôi/chúng ta/bạn/
    # I/we/you) immediately driving the talk-verb, so a domain follow-up like "chính sách đã nói
    # trước đó có thay đổi không" (no personal-pronoun subject) stays KNOWLEDGE, not CONVERSATION.
    r"\b(?:tôi|mình|chúng ta|bạn) (?:đã |vừa |mới )?(?:nói|hỏi|trao đổi|thảo luận|đề cập)\b.{0,20}\btrước đó\b",
    r"\b(?:i|we|you)\b(?:\s+\w+){0,2}\s+(?:say|said|ask|asked|mention|mentioned|talk|talked|discuss|discussed)\b.{0,20}\b(?:earlier|previously|before)\b",
    # Summarize/synthesize the conversation, or what was discussed/exchanged within it.
    r"\btóm tắt (?:cuộc trò chuyện|đoạn (?:hội thoại|chat)|buổi (?:trò chuyện|chat))\b",
    r"\b(?:tổng hợp|tóm tắt|liệt kê|nhắc lại)\b.{0,25}\b(?:kiến thức|điểm|nội dung|thông tin)\b.{0,25}\b(?:đã |vừa )?(?:trao đổi|nói|thảo luận|đề cập)\b",
    r"\bsummarize (?:this|our) (?:conversation|chat|discussion)\b",
    r"\brecap (?:this|our) (?:conversation|chat|discussion)\b",
)
_COMPILED_META_PATTERNS = tuple(re.compile(pattern, re.IGNORECASE) for pattern in _META_PATTERNS)


# Implementation spec §5.3/§8.3: same whole-utterance anchoring discipline as SOCIAL
# (§6.1) -- normalize (strip/casefold/strip a closed set of trailing punctuation/filler),
# then full-string match. A ~3-line normalize step, kept local to this module rather than
# shared with `social_reply.py` (spec §5: "cheap enough to keep local to each module
# rather than extract into a shared utility").
_CATALOG_TRAILING_PUNCT = re.compile(r"[.!?…,\s]+$")
_CATALOG_TRAILING_FILLER_WORD = re.compile(r"\s*\b(?:nha|nhé|nhỉ|ạ|à|đi|nào)\b$", re.IGNORECASE)


def _normalize_catalog_utterance(text: str) -> str:
    normalized = _CATALOG_TRAILING_PUNCT.sub("", text.strip().casefold())
    while True:
        stripped = _CATALOG_TRAILING_PUNCT.sub("", _CATALOG_TRAILING_FILLER_WORD.sub("", normalized))
        if stripped == normalized:
            return normalized
        normalized = stripped


# "What documents/policies exist" -- resolves F-C8. Deliberately narrow: a trailing
# clause naming a specific fact ("... đặc biệt là điều khoản nghỉ phép") breaks the
# anchor and falls through to KNOWLEDGE, handled by the evidence-sufficiency verdict
# instead of the catalog path (spec §8.3).
_CATALOG_PATTERNS: tuple[str, ...] = (
    r"^(project|dự án) này có (?:những )?tài liệu (?:gì|nào)$",
    r"^có (?:những )?tài liệu (?:gì|nào)(?: trong (?:project|dự án) này)?$",
    r"^danh sách (?:các )?tài liệu(?: (?:của|trong) (?:project|dự án)(?: này)?)?$",
    r"^chính sách(?: công ty)? gồm(?: có)? những (?:gì|cái gì)$",
    r"^có những chính sách (?:gì|nào)$",
    r"^liệt kê (?:các )?(?:tài liệu|chính sách)(?: (?:hiện có|đang có))?$",
    r"^what documents (?:are|do you have) available$",
    r"^what policies (?:are there|exist|do you have)$",
    r"^list (?:all )?(?:the )?(?:documents|policies)$",
    r"^show me (?:all )?(?:the )?(?:documents|policies)$",
)
_COMPILED_CATALOG_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE) for pattern in _CATALOG_PATTERNS
)


def _matches_catalog(text: str) -> bool:
    normalized = _normalize_catalog_utterance(text)
    if not normalized:
        return False
    return any(pattern.match(normalized) for pattern in _COMPILED_CATALOG_PATTERNS)


def classify_intent(question: str) -> AnswerMode:
    """Pure function of the raw question text. No history, no DB, no LLM.

    Must run before `query_condenser.condense()`/retrieval so a meta-question never turns into a
    noisy standalone or expanded retrieval query (root cause #1 in CHANGE_LOG.md's weakness #4
    entry): a CONVERSATION verdict here means the caller skips condensation and retrieval
    entirely, not just that it later fails to find evidence.

    Fixed precedence (implementation spec §5): CONVERSATION (unchanged) -> SOCIAL (new,
    delegates to `social_reply.classify_social`) -> CATALOG (new, local anchoring) ->
    KNOWLEDGE (default), stopping at the first match.
    """
    text = question.strip()
    if not text:
        return AnswerMode.KNOWLEDGE
    if any(pattern.search(text) for pattern in _COMPILED_META_PATTERNS):
        return AnswerMode.CONVERSATION
    if classify_social(text) is not None:
        return AnswerMode.SOCIAL
    if _matches_catalog(text):
        return AnswerMode.CATALOG
    return AnswerMode.KNOWLEDGE
