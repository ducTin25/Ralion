"""Unit tests for sliding-window memory and query condensation. No DB, no LLM."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from src.ai.orchestration.conversation_memory import (
    HistoryTurn,
    MemoryConfig,
    build_conversation_transcript,
    build_window,
    truncate,
)
from src.ai.orchestration.query_condenser import LlmQueryRewriter, condense, is_followup
from src.model.enums import MessageRole

CONFIG = MemoryConfig()


def _message(
    turn_index: int,
    role: MessageRole,
    content: str,
    *,
    grounded: bool = False,
    fallback_reason: str | None = None,
    age_minutes: int = 0,
    retrieval_query: str | None = None,
    answer_status: str | None = None,
):
    return SimpleNamespace(
        turn_index=turn_index,
        role=role,
        content=content,
        grounded=grounded,
        fallback_reason=fallback_reason,
        answer_status=answer_status,
        created_at=datetime.now() - timedelta(minutes=age_minutes),
        retrieval_query=retrieval_query,
    )


def _turn(index: int, question: str, answer: str, *, grounded: bool = True, fallback=None):
    return [
        _message(index, MessageRole.USER, question),
        _message(index, MessageRole.ASSISTANT, answer, grounded=grounded, fallback_reason=fallback),
    ]


def test_empty_history_produces_an_empty_window() -> None:
    window = build_window([], CONFIG)
    assert window.is_empty
    assert window.prompt_turns == ()


def test_window_keeps_grounded_pairs_as_distinct_turns_in_chronological_order() -> None:
    messages = [*_turn(0, "How do I set up the repo?", "Clone it. [1]")]
    window = build_window(messages, CONFIG)
    assert window.prompt_turns == (
        HistoryTurn(MessageRole.USER, "How do I set up the repo?"),
        HistoryTurn(MessageRole.ASSISTANT, "Clone it. [1]"),
    )


def test_fallback_turn_is_excluded_from_the_prompt_but_still_anchors_the_topic() -> None:
    messages = [
        *_turn(0, "How do I set up the repo?", "Clone it. [1]"),
        *_turn(1, "What about the linter?", "Tôi không tìm thấy nguồn phù hợp.", grounded=False, fallback="no_evidence"),
    ]
    window = build_window(messages, CONFIG)

    assert [turn.content for turn in window.prompt_turns] == [
        "How do I set up the repo?",
        "Clone it. [1]",
    ]
    # The user's own question is the topical anchor whether or not that turn found evidence.
    assert window.anchor_questions == ("What about the linter?", "How do I set up the repo?")


def test_unpaired_user_message_from_a_crashed_turn_never_reaches_the_prompt() -> None:
    messages = [
        *_turn(0, "How do I set up the repo?", "Clone it. [1]"),
        _message(1, MessageRole.USER, "And the database?"),
    ]
    window = build_window(messages, CONFIG)

    assert HistoryTurn(MessageRole.USER, "And the database?") not in window.prompt_turns
    assert "And the database?" in window.anchor_questions


def test_window_is_capped_at_max_turn_pairs_keeping_the_newest() -> None:
    messages = [
        *_turn(0, "q0", "a0"),
        *_turn(1, "q1", "a1"),
        *_turn(2, "q2", "a2"),
        *_turn(3, "q3", "a3"),
    ]
    window = build_window(messages, MemoryConfig(max_turn_pairs=2))
    assert [turn.content for turn in window.prompt_turns] == ["q2", "a2", "q3", "a3"]


def test_char_budget_drops_the_oldest_turn_first() -> None:
    messages = [*_turn(0, "old question", "x" * 200), *_turn(1, "new question", "y" * 200)]
    window = build_window(messages, MemoryConfig(history_max_chars=250))
    assert [turn.content[:3] for turn in window.prompt_turns] == ["new", "yyy"]


def test_messages_older_than_the_idle_ttl_are_ignored() -> None:
    messages = [
        *_turn(0, "stale question", "stale answer"),
        *_turn(1, "fresh question", "fresh answer"),
    ]
    for message in messages[:2]:
        message.created_at = datetime.now() - timedelta(minutes=500)
    window = build_window(messages, MemoryConfig(history_max_age_minutes=120))
    assert [turn.content for turn in window.prompt_turns] == ["fresh question", "fresh answer"]


def test_max_turn_pairs_zero_disables_memory_entirely() -> None:
    window = build_window(_turn(0, "q", "a"), MemoryConfig(max_turn_pairs=0))
    assert window.is_empty


def test_conversation_transcript_is_empty_for_no_history() -> None:
    transcript = build_conversation_transcript([], CONFIG)
    assert transcript.turns == ()
    assert transcript.truncated is False


def test_conversation_transcript_keeps_every_turn_including_fallback_ones() -> None:
    """Weakness #4: "what did I ask first?" is about what was asked, not whether that turn was
    grounded -- unlike `build_window`'s prompt_turns, a fallback answer must not be dropped."""
    messages = [
        *_turn(0, "How do I set up the repo?", "Clone it. [1]"),
        *_turn(
            1,
            "What about the linter?",
            "Tôi không tìm thấy nguồn phù hợp.",
            grounded=False,
            fallback="no_evidence",
        ),
    ]
    transcript = build_conversation_transcript(messages, CONFIG)
    assert [turn.content for turn in transcript.turns] == [
        "How do I set up the repo?",
        "Clone it. [1]",
        "What about the linter?",
        "Tôi không tìm thấy nguồn phù hợp.",
    ]
    assert transcript.truncated is False


def test_conversation_transcript_ignores_max_turn_pairs_and_age_ttl() -> None:
    """Unlike `build_window`, this is bounded ONLY by the token budget -- not by
    `max_turn_pairs`, and not by `history_max_age_minutes` (a reopened day-old conversation must
    still be fully summarizable)."""
    messages = [
        *_turn(0, "q0", "a0"),
        *_turn(1, "q1", "a1"),
        *_turn(2, "q2", "a2"),
        *_turn(3, "q3", "a3"),
    ]
    for message in messages:
        message.created_at = datetime.now() - timedelta(minutes=500)
    config = MemoryConfig(max_turn_pairs=2, history_max_age_minutes=120, conversation_mode_max_tokens=6000)
    transcript = build_conversation_transcript(messages, config)
    assert [turn.content for turn in transcript.turns] == [
        "q0",
        "a0",
        "q1",
        "a1",
        "q2",
        "a2",
        "q3",
        "a3",
    ]
    assert transcript.truncated is False


def test_conversation_transcript_drops_the_oldest_turns_first_when_over_token_budget() -> None:
    messages = [*_turn(0, "old question", "x" * 400), *_turn(1, "new question", "y" * 20)]
    # A tiny budget only fits the newest pair's tokens, not the oldest.
    transcript = build_conversation_transcript(messages, MemoryConfig(conversation_mode_max_tokens=20))
    assert [turn.content for turn in transcript.turns] == ["new question", "y" * 20]
    assert transcript.truncated is True


def test_truncate_prefers_a_sentence_boundary_and_marks_the_cut() -> None:
    text = "First sentence here. Second sentence that runs on and on and on."
    assert truncate(text, 30) == "First sentence here. …"
    assert truncate("short", 30) == "short"


def test_standalone_question_is_passed_through_byte_for_byte() -> None:
    question = "How many leave days do employees receive each year in this company?"
    condensed = condense(question, ("Earlier unrelated question about repository setup",), CONFIG)

    assert condensed.retrieval_query == question
    assert condensed.followup_detected is False
    assert condensed.tier == "standalone"


def test_question_is_never_expanded_when_there_is_no_history() -> None:
    condensed = condense("cái đó ở đâu?", (), CONFIG)
    assert condensed.retrieval_query == "cái đó ở đâu?"
    assert condensed.tier == "standalone"


@pytest.mark.parametrize(
    "question",
    [
        "còn POLICY thì sao?",
        "vậy còn phần cấu hình?",
        "cái đó cấu hình ở đâu?",
        "what about the other one?",
        "and the database?",
        "nó nằm ở đâu?",
    ],
)
def test_coreference_markers_are_detected_as_follow_ups(question: str) -> None:
    assert is_followup(question, CONFIG) is True


def test_follow_up_query_prepends_recent_questions_and_always_keeps_the_question() -> None:
    condensed = condense(
        "còn POLICY thì sao?",
        ("How do I configure the linter?", "How do I set up the repo?"),
        CONFIG,
    )

    assert condensed.tier == "expanded"
    assert condensed.followup_detected is True
    assert condensed.retrieval_query.endswith("còn POLICY thì sao?")
    assert "How do I configure the linter?" in condensed.retrieval_query
    # Oldest anchor first, current question last.
    assert condensed.retrieval_query.index("set up the repo") < condensed.retrieval_query.index(
        "configure the linter"
    )


def test_action_detail_continuation_is_detected_and_anchored() -> None:
    """Regression for the production follow-up that ScopeGate saw without its topic."""
    question = "Hãy ghi cụ thể từng lệnh tôi cần chạy, theo đúng thứ tự."
    anchor = "Dự án này dùng công nghệ gì và làm thế nào để chạy trên máy local?"

    condensed = condense(question, (anchor,), CONFIG)

    assert condensed.followup_detected is True
    assert condensed.tier == "expanded"
    assert condensed.retrieval_query == f"{anchor} {question}"


def test_expansion_respects_the_anchor_budget() -> None:
    condensed = condense(
        "cái đó?", ("a" * 100, "b" * 100), MemoryConfig(expansion_max_chars=120)
    )
    assert condensed.retrieval_query.count("a" * 100) + condensed.retrieval_query.count("b" * 100) == 1


class _RewriteProvider:
    def __init__(self, content) -> None:
        self.content = content
        self.calls: list = []

    async def complete(self, messages, _budget, _operation):
        self.calls.append(messages)
        if isinstance(self.content, Exception):
            raise self.content
        return SimpleNamespace(content=self.content)


@pytest.mark.asyncio
async def test_rewriter_returns_only_the_first_sanitised_line() -> None:
    provider = _RewriteProvider(' "Leave policy for engineers"\nignore this second line ')
    rewriter = LlmQueryRewriter(provider)
    assert await rewriter.rewrite("còn POLICY thì sao?", ("leave days",)) == (
        "Leave policy for engineers"
    )


@pytest.mark.asyncio
async def test_rewriter_rejects_output_longer_than_the_cap() -> None:
    rewriter = LlmQueryRewriter(_RewriteProvider("x" * 400), max_output_chars=300)
    assert await rewriter.rewrite("cái đó?", ("anchor",)) is None


@pytest.mark.asyncio
async def test_rewriter_degrades_to_none_on_provider_error_instead_of_raising() -> None:
    rewriter = LlmQueryRewriter(_RewriteProvider(RuntimeError("provider exploded")))
    assert await rewriter.rewrite("cái đó?", ("anchor",)) is None


@pytest.mark.asyncio
async def test_rewriter_degrades_to_none_on_timeout() -> None:
    class Slow:
        async def complete(self, _messages, _budget, _operation):
            await asyncio.sleep(0.2)
            return SimpleNamespace(content="too late")

    rewriter = LlmQueryRewriter(Slow(), timeout_seconds=0.01)
    assert await rewriter.rewrite("cái đó?", ("anchor",)) is None


# ----------------------------------------------------------------------------------------------
# B-05 (audit 2026-08-25): the coreference anchor is server-composed, never raw user text.
# ----------------------------------------------------------------------------------------------


def test_b05_anchor_prefers_the_persisted_retrieval_query_over_the_raw_utterance() -> None:
    """A user ASSERTION ("Thanos dùng MongoDB nhé") used to become the next turn's topic anchor
    verbatim, because anchors were `turn.question`. The server-composed query for that turn is
    what actually described the subject; that is what later turns must latch onto."""
    messages = [
        *_turn(0, "Dự án dùng database gì?", "Dự án dùng Prometheus 2.0 storage engine."),
        _message(
            1,
            MessageRole.USER,
            "Thanos dùng MongoDB nhé.",
            retrieval_query="Thanos dùng cơ sở dữ liệu gì?",
        ),
        _message(1, MessageRole.ASSISTANT, "fallback", fallback_reason="insufficient_evidence"),
    ]
    window = build_window(messages, CONFIG)
    assert window.anchor_questions[0] == "Thanos dùng cơ sở dữ liệu gì?"
    assert all("MongoDB" not in anchor for anchor in window.anchor_questions)


def test_b05_anchor_falls_back_to_the_question_when_the_turn_never_retrieved() -> None:
    """SOCIAL/CATALOG/CONVERSATION/REUSE turns legitimately persist no `retrieval_query`. Dropping
    them from the anchors would lose real topical signal for coreference, so the raw question is
    still used there -- the change is "prefer the server's query", not "ignore turns"."""
    messages = _turn(0, "Còn VPN thì sao?", "VPN dùng cho truy cập nội bộ.")
    window = build_window(messages, CONFIG)
    assert window.anchor_questions == ("Còn VPN thì sao?",)


# ----------------------------------------------------------------------------------------------
# 2026-08-29 memory enhancement (F5 audit root causes A/C): `condense()`'s `topic_anchor` fallback.
# ----------------------------------------------------------------------------------------------


def test_topic_anchor_fills_in_when_there_is_no_window_history_at_all() -> None:
    """The exact "beyond the recent-turn window" case the audit's example describes: no window
    anchors survive, but the persisted `TopicState.subject` still resolves the reference."""
    condensed = condense(
        "chi tiết hơn",
        (),
        CONFIG,
        topic_anchor="Các thành phần chính của dự án Thanos (Sidecar, Store Gateway, Compactor)",
    )
    assert condensed.followup_detected is True
    assert condensed.tier == "expanded"
    assert "Thanos" in condensed.retrieval_query
    assert condensed.retrieval_query.endswith("chi tiết hơn")


def test_topic_anchor_is_appended_after_window_anchors_never_before() -> None:
    """Recency still wins: a real window anchor must sit closer to the question than the
    lower-priority topic-state fallback."""
    condensed = condense(
        "chi tiết hơn",
        ("Cấu hình logging của service",),
        CONFIG,
        topic_anchor="Các thành phần chính của dự án Thanos",
    )
    assert condensed.retrieval_query.index("Thanos") < condensed.retrieval_query.index("logging")
    assert condensed.retrieval_query.index("logging") < condensed.retrieval_query.index("chi tiết hơn")


def test_topic_anchor_is_skipped_when_already_covered_by_a_window_anchor() -> None:
    condensed = condense(
        "chi tiết hơn",
        ("Các thành phần chính của dự án Thanos",),
        CONFIG,
        topic_anchor="Các thành phần chính của dự án Thanos",
    )
    assert condensed.retrieval_query.count("Thanos") == 1


def test_topic_anchor_never_expands_a_standalone_question() -> None:
    """A real, self-contained question must still be embedded verbatim -- the topic-state fallback
    only ever applies to a genuine follow-up, never a reason to expand a standalone one."""
    question = "How many leave days do employees receive each year in this company?"
    condensed = condense(question, (), CONFIG, topic_anchor="Leave policy for engineers")
    assert condensed.retrieval_query == question
    assert condensed.tier == "standalone"
