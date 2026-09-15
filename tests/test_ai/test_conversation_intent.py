"""Unit tests for AnswerMode routing (weakness #4). Pure function, no DB, no LLM."""

from __future__ import annotations

import pytest

from src.ai.orchestration.conversation_intent import AnswerMode, classify_intent


@pytest.mark.parametrize(
    "question",
    [
        # First/previous-turn reference.
        "câu đầu tiên tôi hỏi về gì?",
        "Câu hỏi trước của tôi là gì?",
        "what was my first question?",
        "what's the previous question I asked?",
        # What did I/we/you ask or say.
        "chúng ta vừa nói về gì?",
        "tôi đã hỏi những gì về remote work?",
        "bạn vừa nói gì vậy?",
        "what did I ask?",
        "what did we discuss?",
        "what did you just say?",
        # Summarize/synthesize the conversation.
        "tóm tắt cuộc trò chuyện này",
        "tổng hợp các kiến thức quan trọng trong cuộc trò chuyện",
        "tổng hợp các điểm quan trọng đã trao đổi",
        "summarize this conversation",
        "can you recap our chat?",
        # Compare/revisit something said earlier by a named speaker.
        "so sánh với những gì tôi hỏi trước đó",
        "chúng ta đã nói trước đó là gì?",
        "what did we say earlier?",
    ],
)
def test_conversation_meta_questions_route_to_conversation_mode(question: str) -> None:
    assert classify_intent(question) is AnswerMode.CONVERSATION


@pytest.mark.parametrize(
    "question",
    [
        # Real domain/knowledge questions.
        "How many leave days do employees receive each year?",
        "Chính sách làm việc từ xa của công ty là gì?",
        "What is the remote work policy?",
        "nếu vi phạm chính sách thì sao?",
        "dịch câu trả lời trên sang tiếng Anh",
        "does this project support SSO login?",
        # Ordinary coreference follow-ups (F-01), must stay KNOWLEDGE.
        "còn POLICY thì sao?",
        "cái đó áp dụng từ khi nào?",
        "what about the other one?",
        # A domain follow-up that happens to say "trước đó" but has no personal-pronoun subject.
        "chính sách đã nói trước đó có thay đổi không?",
        "quy định trước đó về nghỉ phép là gì?",
        # Mentions "chat"/"conversation" as a project feature, not as this dialogue.
        "how do I set up live chat for customer support?",
        "does the app log conversation history in the database?",
        "",
        "   ",
    ],
)
def test_domain_and_ambiguous_questions_stay_knowledge_mode(question: str) -> None:
    assert classify_intent(question) is AnswerMode.KNOWLEDGE
