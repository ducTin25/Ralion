"""Sliding-window conversation memory: pure turn assembly, budgeting and truncation.

No DB access and no LLM here — everything in this module is deterministic and unit-testable.
The window serves two different consumers with two different rules:

* ``prompt_turns`` — only *complete, grounded* turns. A fallback turn ("Tôi không tìm thấy
  nguồn…") carries no information, costs tokens and teaches the model the wrong voice.
* ``anchor_questions`` — the recent USER questions *regardless* of outcome, because the user's
  own question is the topical anchor for coreference whether or not that turn found evidence.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from src.ai.orchestration.turn_outcome import describe_turn_outcome
from src.ai.retrieval_engine.chunking_config import load_chunking_config
from src.model.enums import MessageRole

_ELLIPSIS = " …"


class MemoryMessage(Protocol):
    """The subset of `ChatMessage` this module reads. Keeps the window testable without the ORM."""

    turn_index: int
    role: MessageRole
    content: str
    grounded: bool
    fallback_reason: str | None
    # ASSISTANT rows: `"answered" | "general_guidance" | "fallback" | None`. Read only by
    # `build_conversation_transcript`, together with `grounded`/`fallback_reason`, to derive the
    # trusted outcome phrase on `HistoryTurn.outcome` -- see `turn_outcome.describe_turn_outcome`,
    # which is the SINGLE place that triple is turned into words.
    answer_status: str | None
    created_at: datetime | None
    # USER rows only, and only once that turn actually ran retrieval: the server-derived query
    # `ChatService` persisted for it. Read by `build_window` for `anchor_questions` -- see there.
    retrieval_query: str | None


@dataclass(frozen=True)
class HistoryTurn:
    """One prior message, passed to the generator as a distinct turn — never concatenated."""

    role: MessageRole
    content: str
    # ASSISTANT turns only, and only in `AnswerMode.CONVERSATION`'s transcript: the trusted,
    # server-derived phrase for how that turn ENDED (`turn_outcome.describe_turn_outcome`) --
    # answered from internal sources, withheld for no evidence, withheld because the draft could
    # not be quote-anchored, and so on. It is what lets a meta turn answer "sao lại không có
    # nguồn?" from the record instead of guessing, and what stops CONVERSATION mode from
    # re-asserting a prior withheld claim as though it had been verified. Server-authored, so it
    # is delivered to the model OUTSIDE the untrusted wrapper; `None` for USER turns and for
    # `build_window`'s `prompt_turns`, which carry no outcome.
    outcome: str | None = None


@dataclass(frozen=True)
class ConversationWindow:
    prompt_turns: tuple[HistoryTurn, ...] = ()
    anchor_questions: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not self.prompt_turns and not self.anchor_questions


@dataclass(frozen=True)
class TopicState:
    """Trusted, server-derived topic memory for resolving later references."""

    subject: str | None = None
    entities: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not self.subject and not self.entities


# Store the bounded entity list in one nullable column using an unambiguous delimiter.
_ENTITY_SEPARATOR = "\x1f"


def encode_topic_entities(entities: Sequence[str]) -> str | None:
    joined = _ENTITY_SEPARATOR.join(entity for entity in entities if entity)
    return joined or None


def decode_topic_entities(text: str | None) -> tuple[str, ...]:
    if not text:
        return ()
    return tuple(part for part in text.split(_ENTITY_SEPARATOR) if part)


@dataclass(frozen=True)
class MemoryConfig:
    max_turn_pairs: int = 3
    history_max_chars: int = 4800
    per_message_max_chars: int = 1600
    history_max_age_minutes: int = 120
    followup_max_words: int = 6
    followup_max_chars: int = 40
    expansion_max_anchors: int = 2
    expansion_max_chars: int = 400
    llm_rewrite_enabled: bool = False
    llm_rewrite_timeout_seconds: float = 1.5
    llm_rewrite_max_output_chars: int = 300
    # Conversation mode uses a token budget rather than the normal history window.
    conversation_mode_max_tokens: int = 6000
    # Topic memory remains small and predictable for query expansion.
    topic_subject_max_chars: int = 160
    topic_entities_max: int = 6

    @classmethod
    def from_config(cls, config: dict[str, Any] | None = None) -> MemoryConfig:
        settings = (config or load_chunking_config())["chat"]["conversation_memory"]
        rewrite = settings.get("llm_query_rewrite") or {}
        topic_state = settings.get("topic_state") or {}
        return cls(
            max_turn_pairs=int(settings["max_turn_pairs"]),
            history_max_chars=int(settings["history_max_chars"]),
            per_message_max_chars=int(settings["per_message_max_chars"]),
            history_max_age_minutes=int(settings["history_max_age_minutes"]),
            followup_max_words=int(settings["followup_max_words"]),
            followup_max_chars=int(settings["followup_max_chars"]),
            expansion_max_anchors=int(settings["expansion_max_anchors"]),
            expansion_max_chars=int(settings["expansion_max_chars"]),
            llm_rewrite_enabled=bool(rewrite.get("enabled", False)),
            llm_rewrite_timeout_seconds=float(rewrite.get("timeout_seconds", 1.5)),
            llm_rewrite_max_output_chars=int(rewrite.get("max_output_chars", 300)),
            conversation_mode_max_tokens=int(settings["conversation_mode_max_tokens"]),
            topic_subject_max_chars=int(topic_state.get("subject_max_chars", 160)),
            topic_entities_max=int(topic_state.get("entities_max", 6)),
        )

    def message_limit(self) -> int:
        """How many rows to read. Two per pair, plus one spare pair for dropped/unpaired turns."""
        return max(0, self.max_turn_pairs + 1) * 2


def truncate(content: str, limit: int) -> str:
    """Deterministic tail truncation, preferring the last sentence boundary near the limit."""
    text = content.strip()
    if limit <= 0 or len(text) <= limit:
        return text
    head = text[:limit]
    boundary = max(head.rfind(". "), head.rfind("! "), head.rfind("? "), head.rfind("\n"))
    if boundary >= int(limit * 0.6):
        return head[: boundary + 1].rstrip() + _ELLIPSIS
    return head.rstrip() + _ELLIPSIS


@dataclass(frozen=True)
class _Turn:
    index: int
    question: str
    answer: str | None
    grounded: bool
    retrieval_query: str | None = None


def _group_turns(messages: Iterable[MemoryMessage]) -> list[_Turn]:
    questions: dict[int, str] = {}
    queries: dict[int, str | None] = {}
    answers: dict[int, tuple[str, bool]] = {}
    for message in messages:
        if message.role is MessageRole.USER:
            questions.setdefault(message.turn_index, message.content)
            queries.setdefault(message.turn_index, message.retrieval_query)
        elif message.role is MessageRole.ASSISTANT:
            grounded = bool(message.grounded) and message.fallback_reason is None
            answers.setdefault(message.turn_index, (message.content, grounded))
    turns: list[_Turn] = []
    for index in sorted(questions):
        answer = answers.get(index)
        turns.append(
            _Turn(
                index=index,
                question=questions[index],
                answer=answer[0] if answer else None,
                grounded=bool(answer and answer[1]),
                retrieval_query=queries.get(index),
            )
        )
    return turns


def _within_age(messages: Sequence[MemoryMessage], config: MemoryConfig) -> list[MemoryMessage]:
    if config.history_max_age_minutes <= 0:
        return list(messages)
    stamps = [message.created_at for message in messages if message.created_at is not None]
    if not stamps:
        return list(messages)
    # `created_at` is written by the database clock into a timezone-naive column, which the whole
    # codebase reads as UTC (Postgres `now()` under a UTC server, SQLite CURRENT_TIMESTAMP). The
    # app clock must therefore be normalised to UTC too — comparing against local time silently
    # deleted every message on a UTC+7 machine.
    # `max` with the newest row additionally neutralises forward skew: if the two clocks disagree,
    # the window degrades to "span since the last message" (history kept a little too long) rather
    # than dropping all history, which is the failure mode that would look like memory not working.
    reference = max(max(stamps), datetime.now(UTC).replace(tzinfo=None))
    cutoff = reference - timedelta(minutes=config.history_max_age_minutes)
    return [
        message
        for message in messages
        if message.created_at is None or message.created_at >= cutoff
    ]


def build_window(
    messages: Sequence[MemoryMessage], config: MemoryConfig | None = None
) -> ConversationWindow:
    """Assemble the sliding window from the most recent messages of one conversation."""
    config = config or MemoryConfig.from_config()
    if config.max_turn_pairs <= 0 or not messages:
        return ConversationWindow()

    turns = _group_turns(_within_age(messages, config))
    recent = turns[-config.max_turn_pairs :]

    # B-05 (CHANGE_LOG.md 2026-08-25): the anchor for a turn is the SERVER-DERIVED retrieval query
    # it actually ran, falling back to the raw question only for a turn that never retrieved.
    #
    # Previously this was always `turn.question` -- the raw user text -- which made every user
    # utterance an input to the next turn's retrieval, whether or not it was a question at all.
    # Live transcript: "Thanos dùng MongoDB nhé" (an assertion, answered with a fallback) became a
    # Tier-1 expansion prefix and pulled the following turns off the chunk that had answered the
    # same question correctly two turns earlier. A user assertion must never steer retrieval; a
    # query the server itself composed is safe by construction, and `_previous_retrieval_query`
    # already established this exact precedent for the REUSE path's R4 degrade.
    #
    # Scope of the guarantee, stated precisely: this makes the anchor SERVER-COMPOSED, it does not
    # by itself neutralise an assertion. `retrieval_query` is the interpreter's
    # `resolved_question`, so the assertion is only rewritten into a neutral question because the
    # interpreter contract requires it ("a user assertion resolves to the corresponding QUESTION",
    # turn_interpreter._SYSTEM_INSTRUCTIONS). Deterministic here, semantic there -- both are
    # needed, and `test_user_claim_does_not_pollute_next_query` pins the pair end to end.
    #
    # Note the fallback is deliberately NOT "drop the turn": a turn that legitimately never
    # retrieved (SOCIAL/CATALOG/CONVERSATION/REUSE) still carries topical signal for coreference,
    # which is what `anchor_questions` exists for.
    anchors = tuple(
        (turn.retrieval_query or turn.question).strip()
        for turn in reversed(recent)
        if (turn.retrieval_query or turn.question).strip()
    )

    prompt_turns: list[HistoryTurn] = []
    budget = config.history_max_chars
    # Newest first so that when the budget runs out it is the oldest turn that is dropped.
    for turn in reversed(recent):
        if turn.answer is None or not turn.grounded:
            continue
        question = truncate(turn.question, config.per_message_max_chars)
        answer = truncate(turn.answer, config.per_message_max_chars)
        cost = len(question) + len(answer)
        if cost > budget:
            break
        budget -= cost
        prompt_turns.append(HistoryTurn(MessageRole.ASSISTANT, answer))
        prompt_turns.append(HistoryTurn(MessageRole.USER, question))

    return ConversationWindow(prompt_turns=tuple(reversed(prompt_turns)), anchor_questions=anchors)


def informational_anchor_questions(
    messages: Sequence[MemoryMessage], config: MemoryConfig | None = None
) -> tuple[str, ...]:
    """Anchors for SCOPE classification only (`ScopeGate`, via the `scope_text` `condense()` call
    in `chat_service.py`) -- narrower than `build_window`'s `anchor_questions` above, which also
    feeds retrieval-query expansion and is deliberately lenient (any recent turn, whatever route,
    carries SOME topical signal for coreference there).

    F5 audit 2026-08-30 root cause #2 (confirmed by reproduction): a turn with no persisted
    `retrieval_query` never retrieved real evidence -- a SOCIAL presentation-control ack,
    CONVERSATION, or CATALOG reply. Its own raw text is a presentation instruction or a
    transcript/document-listing remark, never a project subject, so `build_window`'s fallback to
    that raw text is exactly right for keeping retrieval coreference lenient but is noise for a
    scope classifier: "từ giờ hãy trả lời bằng tiếng Việt nhé" (a SOCIAL ack) glued onto the very
    next, unrelated, standalone "dự án có kiến trúc như thế nào?" confused the judge into a false
    OUT_OF_SCOPE, while the near-identical rephrasing asked right after it succeeded only because
    ITS anchor was, by then, the earlier turn's real resolved_question. A REUSE turn is NOT
    silently dropped here despite also sometimes reaching this fallback in `build_window` -- every
    REUSE path that actually answers persists its own `retrieval_query` (`_answer_reuse_route`), so
    it already carries a real anchor and only a REUSE turn that never got that far (no real
    subject to reuse) is excluded, which is the correct outcome for scope classification too.
    """
    config = config or MemoryConfig.from_config()
    if config.max_turn_pairs <= 0 or not messages:
        return ()
    turns = _group_turns(_within_age(messages, config))
    recent = turns[-config.max_turn_pairs :]
    return tuple(
        turn.retrieval_query.strip()
        for turn in reversed(recent)
        if turn.retrieval_query and turn.retrieval_query.strip()
    )


def _encoding():
    """Use the tokenizer already used by the corpus chunkers/`AnswerGenerator`."""
    import tiktoken

    return tiktoken.get_encoding("cl100k_base")


@dataclass(frozen=True)
class ConversationTranscriptWindow:
    """`AnswerMode.CONVERSATION`'s history, distinct from `ConversationWindow` above."""

    turns: tuple[HistoryTurn, ...] = ()
    # True when the full transcript did not fit `conversation_mode_max_tokens` and the oldest
    # turns had to be dropped -- the caller surfaces this to the model (see
    # `conversation_answer.py`) so a long conversation degrades to an honest "I don't have that
    # far back" instead of silently answering as if the dropped turns never happened.
    truncated: bool = False


def build_conversation_transcript(
    messages: Sequence[MemoryMessage], config: MemoryConfig | None = None
) -> ConversationTranscriptWindow:
    """Full authorized transcript for `AnswerMode.CONVERSATION`, bounded by a TOKEN budget.

    Deliberately different from `build_window` above in every axis that matters for a
    conversation-meta question:

    * every USER/ASSISTANT row is kept, including fallback turns -- "what did I ask first?" is
      about what was asked, not whether that turn found evidence, unlike `build_window`'s
      grounded-only `prompt_turns`;
    * no `max_turn_pairs`/no idle-TTL age cutoff -- "summarize this conversation" means the whole
      authorized conversation (subject only to the token budget below), not the last N turns or
      only the last two hours of it;
    * bounded by an actual token count (`conversation_mode_max_tokens`), not the char
      approximation `build_window` uses, because this budget can be asked to cover a much longer
      span of the conversation in one prompt.

    When the transcript does not fit, the OLDEST turns are dropped first -- recency bias matches
    how people actually ask "what did we just discuss", and matches `build_window`'s own
    drop-oldest-first policy for the char budget.

    Every ASSISTANT turn additionally carries `HistoryTurn.outcome`: the trusted, server-derived
    phrase for how that turn ended, from the SAME `describe_turn_outcome` the router's `PriorTurn`
    uses, so the transcript and the router can never disagree about what happened on a turn. Its
    token cost is charged against the same budget as the content it annotates.
    """
    config = config or MemoryConfig.from_config()
    ordered = [
        message for message in messages if message.role in (MessageRole.USER, MessageRole.ASSISTANT)
    ]
    if not ordered:
        return ConversationTranscriptWindow()

    encoding = _encoding()
    budget = max(0, config.conversation_mode_max_tokens)
    kept: list[HistoryTurn] = []
    used = 0
    # Newest first so that when the budget runs out it is the oldest turn that is dropped.
    for message in reversed(ordered):
        outcome = (
            describe_turn_outcome(
                grounded=bool(message.grounded),
                fallback_reason=message.fallback_reason,
                answer_status=getattr(message, "answer_status", None),
            )
            if message.role is MessageRole.ASSISTANT
            else None
        )
        cost = len(encoding.encode(message.content)) + (
            len(encoding.encode(outcome)) if outcome else 0
        )
        if used + cost > budget:
            break
        used += cost
        kept.append(HistoryTurn(message.role, message.content, outcome=outcome))

    kept.reverse()
    return ConversationTranscriptWindow(turns=tuple(kept), truncated=len(kept) < len(ordered))
