"""Pure-function unit tests for the F5 audit remediation helpers in `chat_service.py`.

No DB, no scripted service -- these test the deterministic composition/parsing logic in
isolation, complementing the service-level dispatch tests in `test_chat_buddy_support.py` (A1)
and any end-to-end retrieval tests (B2).
"""

from __future__ import annotations

from src.ai.orchestration.social_reply import SocialIntent
from src.modules.chat.application.chat_service import (
    RelevanceGate,
    _compose_social_intent_with_subject,
    _multi_entity_retrieval_queries,
)

# ------------------------------------------------------------------------------------------------
# A1: affect as a modifier, not a competing route.
# ------------------------------------------------------------------------------------------------


def test_buddy_support_overridden_when_subject_is_answerable() -> None:
    assert (
        _compose_social_intent_with_subject(
            SocialIntent.BUDDY_SUPPORT, has_answerable_subject=True
        )
        is None
    )


def test_buddy_support_kept_when_no_answerable_subject() -> None:
    assert (
        _compose_social_intent_with_subject(
            SocialIntent.BUDDY_SUPPORT, has_answerable_subject=False
        )
        is SocialIntent.BUDDY_SUPPORT
    )


def test_other_social_intents_never_touched_by_the_override() -> None:
    """The override is scoped to BUDDY_SUPPORT specifically -- a closed-form ritual formula like
    GRATITUDE must never be redirected to KNOWLEDGE merely because the message also happens to
    name something (e.g. "cảm ơn bạn đã giúp về VPN" should stay GRATITUDE at this layer; whether
    that turn should have been KNOWLEDGE at all is the model's own route/social_intent judgment,
    not this deterministic composition step's job)."""
    for intent in (
        SocialIntent.GRATITUDE,
        SocialIntent.GREETING,
        SocialIntent.FAREWELL,
        SocialIntent.ACKNOWLEDGEMENT,
        SocialIntent.TOPIC_CHANGE,
        SocialIntent.LANGUAGE_PREFERENCE,
        SocialIntent.OTHER,
        None,
    ):
        assert (
            _compose_social_intent_with_subject(intent, has_answerable_subject=True) is intent
        )
        assert (
            _compose_social_intent_with_subject(intent, has_answerable_subject=False) is intent
        )


# ------------------------------------------------------------------------------------------------
# B2: bounded retrieval fan-out for a clearly-identified multi-entity resolved_question.
# ------------------------------------------------------------------------------------------------


def test_multi_entity_list_is_split_into_bounded_queries() -> None:
    resolved = (
        "Vai trò và cách hoạt động của từng thành phần trong dự án: Sidecar, Store Gateway, "
        "Compactor, Receiver, Ruler, Query Gateway"
    )
    queries = _multi_entity_retrieval_queries(resolved)

    assert queries is not None
    # All six entities reach the bounded fan-out stage.
    assert len(queries) == 6
    assert queries[0] == (
        "Vai trò và cách hoạt động của từng thành phần trong dự án: Sidecar"
    )
    assert queries[1].endswith("Store Gateway")


def test_multi_entity_fanout_still_has_an_explicit_upper_bound() -> None:
    entities = ", ".join(f"Component {number}" for number in range(12))
    queries = _multi_entity_retrieval_queries(f"Role of each component: {entities}")

    assert queries is not None
    assert len(queries) == 8
    assert queries[-1].endswith("Component 7")


def test_evidence_capacity_keeps_factual_default_and_expands_synthesis() -> None:
    gate = RelevanceGate(
        {
            "chat": {
                "max_chunks_per_domain": 5,
                "context_max_tokens": 3200,
                "synthesis_evidence_capacity": {
                    "max_chunks_per_domain": 8,
                    "context_max_tokens": 6000,
                },
            }
        }
    )

    assert gate.evidence_capacity_for("What is cmd/thanos/sidecar.go?") == (5, 3200)
    assert gate.evidence_capacity_for("How do the components interact?") == (8, 6000)
    assert gate.evidence_capacity_for("details", has_multi_entity_fanout=True) == (8, 6000)


def test_english_and_or_conjunction_is_also_split() -> None:
    resolved = "Role of each component: Sidecar and Store Gateway and Compactor"
    queries = _multi_entity_retrieval_queries(resolved)

    assert queries is not None
    assert len(queries) == 3
    assert queries[-1].endswith("Compactor")


def test_two_item_comma_list_is_the_minimum_that_triggers_fanout() -> None:
    resolved = "So sánh hai thành phần: Sidecar, Store Gateway"
    queries = _multi_entity_retrieval_queries(resolved)

    assert queries == [
        "So sánh hai thành phần: Sidecar",
        "So sánh hai thành phần: Store Gateway",
    ]


def test_single_item_after_colon_does_not_trigger_fanout() -> None:
    """A single named entity is not a multi-entity request -- the ordinary single retrieval call
    must run unchanged."""
    assert _multi_entity_retrieval_queries("Vai trò của thành phần: Sidecar") is None


def test_ordinary_sentence_with_a_colon_does_not_trigger_fanout() -> None:
    """Guards against false positives on prose that happens to contain a colon, e.g. an example
    lead-in -- a real entity list is short items, not a sentence fragment."""
    assert (
        _multi_entity_retrieval_queries(
            "Ví dụ: dự án dùng Sidecar để đẩy dữ liệu lên object storage theo lịch định kỳ"
        )
        is None
    )


def test_no_colon_at_all_does_not_trigger_fanout() -> None:
    assert _multi_entity_retrieval_queries("Sidecar là gì?") is None


def test_empty_resolved_question_does_not_trigger_fanout() -> None:
    assert _multi_entity_retrieval_queries("") is None
