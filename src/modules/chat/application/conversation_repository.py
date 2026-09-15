"""Persistence for the chat conversation aggregate.

Kept separate from `ChatService` so the service reads as flow, not SQL. Two rules live here:

* the ownership predicate (`user_id`) is part of *every* conversation lookup — there is no method
  that can load a conversation without it;
* loading a conversation and its sliding window is **one** round trip, so memory costs one query
  per turn rather than two.
"""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.model.answer_claim import AnswerClaim
from src.model.chat_message import ChatMessage
from src.model.chat_session import ChatSession
from src.model.citation import Citation
from src.model.enums import DocumentDomain, MessageRole
from src.model.project_membership import ProjectMembership


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        user_id: int,
        knowledge_domain: DocumentDomain,
        membership: ProjectMembership | None,
    ) -> ChatSession:
        """Scope is written once here and never updated. See `ChatSession` for why."""
        conversation = ChatSession(
            user_id=user_id,
            knowledge_domain=knowledge_domain,
            project_id=membership.project_id if membership else None,
            membership_id=membership.membership_id if membership else None,
        )
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def load_with_window(
        self, *, public_id, user_id: int, limit: int
    ) -> tuple[ChatSession | None, list[ChatMessage]]:
        """One query: the conversation plus its most recent messages, newest first.

        Returns `(None, [])` both when the id does not exist and when it belongs to somebody
        else — the caller must not be able to tell those apart.
        """
        rows = (
            await self.session.execute(
                select(ChatSession, ChatMessage)
                .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.session_id)
                .where(ChatSession.public_id == public_id, ChatSession.user_id == user_id)
                .order_by(ChatMessage.message_id.desc())
                .limit(max(1, limit))
            )
        ).all()
        if not rows:
            return None, []
        conversation = rows[0][0]
        messages = [row[1] for row in rows if row[1] is not None]
        messages.reverse()
        return conversation, messages

    async def load_full_history(
        self, *, public_id, user_id: int
    ) -> tuple[ChatSession | None, list[ChatMessage]]:
        """Full authorized transcript for `AnswerMode.CONVERSATION` -- every message, oldest
        first. Same ownership predicate and same "id doesn't exist vs. belongs to someone else
        are indistinguishable" contract as `load_with_window`; unlike it, not bounded by the
        KNOWLEDGE-mode sliding-window row limit -- `conversation_memory.build_conversation_transcript`
        bounds it afterwards by a token budget instead.
        """
        rows = (
            await self.session.execute(
                select(ChatSession, ChatMessage)
                .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.session_id)
                .where(ChatSession.public_id == public_id, ChatSession.user_id == user_id)
                .order_by(ChatMessage.message_id.asc())
            )
        ).all()
        if not rows:
            return None, []
        conversation = rows[0][0]
        messages = [row[1] for row in rows if row[1] is not None]
        return conversation, messages

    async def next_turn_index(self, *, session_id: int) -> int:
        current = await self.session.scalar(
            select(func.max(ChatMessage.turn_index)).where(ChatMessage.session_id == session_id)
        )
        return 0 if current is None else int(current) + 1

    def append(
        self,
        *,
        session_id: int,
        turn_index: int,
        role: MessageRole,
        content: str,
        trace_id: str,
        grounded: bool = False,
        confidence: float | None = None,
        fallback_reason: str | None = None,
        retrieval_query: str | None = None,
        answer_status: str | None = None,
        validator_outcome: str | None = None,
        conflict: str | None = None,
        general_guidance: list[dict[str, str]] | None = None,
    ) -> ChatMessage:
        """Stages a message. The caller owns the commit boundary — that boundary is the point of
        the design (USER is committed before retrieval), so it is not hidden in here."""
        message = ChatMessage(
            session_id=session_id,
            turn_index=turn_index,
            role=role,
            content=content,
            grounded=grounded,
            confidence=confidence,
            trace_id=trace_id,
            fallback_reason=fallback_reason,
            retrieval_query=retrieval_query,
            answer_status=answer_status,
            validator_outcome=validator_outcome,
            conflict=conflict,
            general_guidance=general_guidance,
        )
        self.session.add(message)
        return message

    async def set_retrieval_query(self, *, session_id: int, turn_index: int, query: str) -> None:
        """Record the query that actually produced the answer, after a Tier-2 rewrite replaced it."""
        await self.session.execute(
            update(ChatMessage)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.turn_index == turn_index,
                ChatMessage.role == MessageRole.USER,
            )
            .values(retrieval_query=query)
        )

    async def citations_for_message(self, message_id: int) -> list[Citation]:
        """Follow-up continuity (target design item 4): the related-evidence chunk ids a prior
        `insufficient_evidence` turn showed but did not claim to answer with (`claim_id IS NULL`,
        see `chat_service.py`'s `_fallback`). A single indexed lookup by FK, same shape as the
        per-message citation load already done in `transcript()` below.
        """
        return list(
            (
                await self.session.scalars(
                    select(Citation)
                    .where(Citation.message_id == message_id)
                    .order_by(Citation.citation_id)
                )
            ).all()
        )

    async def update_presentation_preferences(
        self, *, session_id: int, language: str | None = None, detail: str | None = None
    ) -> None:
        """Apply an explicit, validated conversation-control patch.

        `None` means the field was absent from the patch, not "clear it". The interpreter's
        closed contract currently supports language and response detail; adding another
        presentation preference extends this single state transition instead of adding another
        phrase-specific persistence path.
        """
        values: dict[str, str] = {}
        if language is not None:
            values["preferred_language"] = language
        if detail is not None:
            values["preferred_response_detail"] = detail
        if not values:
            return
        await self.session.execute(
            update(ChatSession)
            .where(ChatSession.session_id == session_id)
            .values(**values)
        )

    async def set_preferred_language(self, *, session_id: int, language: str) -> None:
        """Compatibility wrapper for callers predating the generalized presentation contract."""
        await self.update_presentation_preferences(session_id=session_id, language=language)

    async def update_topic_state(
        self, *, session_id: int, subject: str | None, entities: str | None
    ) -> None:
        """Overwrite the conversation's server-derived topic memory (`TopicState`).

        Unlike `update_presentation_preferences`'s patch semantics, this always writes a full
        replacement state -- the caller (`ChatService._update_topic_state`) already resolved
        whether to keep, narrow, or overwrite the subject before calling this, so there is no
        separate "field absent" case to preserve here.
        """
        await self.session.execute(
            update(ChatSession)
            .where(ChatSession.session_id == session_id)
            .values(topic_subject=subject, topic_entities=entities)
        )

    async def touch(self, *, session_id: int) -> None:
        """Stamp activity from the database clock, so idle TTL never depends on app-server time."""
        await self.session.execute(
            update(ChatSession)
            .where(ChatSession.session_id == session_id)
            .values(last_message_at=func.now())
        )

    async def transcript(
        self, *, public_id, user_id: int
    ) -> tuple[
        ChatSession,
        list[ChatMessage],
        dict[int, list[AnswerClaim]],
        dict[int, list[Citation]],
    ] | None:
        """Full history for a reload. Same ownership predicate as every other lookup."""
        conversation = await self.session.scalar(
            select(ChatSession).where(
                ChatSession.public_id == public_id, ChatSession.user_id == user_id
            )
        )
        if conversation is None:
            return None
        messages = list(
            (
                await self.session.scalars(
                    select(ChatMessage)
                    .where(ChatMessage.session_id == conversation.session_id)
                    .order_by(ChatMessage.turn_index, ChatMessage.message_id)
                )
            ).all()
        )
        citations: dict[int, list[Citation]] = {}
        claims: dict[int, list[AnswerClaim]] = {}
        message_ids = [message.message_id for message in messages]
        if message_ids:
            for claim in (
                await self.session.scalars(
                    select(AnswerClaim)
                    .where(AnswerClaim.message_id.in_(message_ids))
                    .order_by(AnswerClaim.message_id, AnswerClaim.claim_index)
                )
            ).all():
                claims.setdefault(claim.message_id, []).append(claim)
            for citation in (
                await self.session.scalars(
                    select(Citation)
                    .where(Citation.message_id.in_(message_ids))
                    .order_by(Citation.citation_id)
                )
            ).all():
                citations.setdefault(citation.message_id, []).append(citation)
        return conversation, messages, claims, citations
