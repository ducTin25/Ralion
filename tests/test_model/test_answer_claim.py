import pytest
from sqlalchemy import ForeignKeyConstraint, select

from src.model.answer_claim import AnswerClaim
from src.model.chat_message import ChatMessage
from src.model.citation import Citation
from src.model.enums import ClaimSupportType, MessageRole


@pytest.mark.asyncio
async def test_message_claims_are_ordered_and_cascade_to_citations(db_session) -> None:
    message = ChatMessage(session_id=1, turn_index=0, role=MessageRole.ASSISTANT, content="answer")
    first = AnswerClaim(
        claim_index=0,
        text="Direct claim",
        support_type=ClaimSupportType.DIRECT,
        verdict="passed",
    )
    second = AnswerClaim(
        claim_index=1,
        text="Inferred claim",
        support_type=ClaimSupportType.INFERRED,
        verdict="passed",
    )
    first.citations.extend(
        [
            Citation(message_id=1, chunk_id=101, quote="first source", relevance_score=0.9),
            Citation(message_id=1, chunk_id=101, quote="second source", relevance_score=0.8),
        ]
    )
    # Append out of display order to prove the relationship's deterministic order is not append order.
    message.answer_claims.extend([second, first])
    db_session.add(message)
    await db_session.flush()

    persisted_claims = list(
        (
            await db_session.scalars(
                select(AnswerClaim)
                .where(AnswerClaim.message_id == message.message_id)
                .order_by(AnswerClaim.claim_index)
            )
        ).all()
    )
    assert [claim.claim_index for claim in persisted_claims] == [0, 1]
    assert first.message is message
    assert [citation.claim_id for citation in first.citations] == [first.claim_id, first.claim_id]
    assert [citation.chunk_id for citation in first.citations] == [101, 101]

    await db_session.delete(message)
    await db_session.flush()

    assert await db_session.scalar(select(AnswerClaim.claim_id)) is None
    assert await db_session.scalar(select(Citation.citation_id)) is None


def test_citation_claim_fk_also_enforces_owning_message() -> None:
    constraint = next(
        item
        for item in Citation.__table__.constraints
        if isinstance(item, ForeignKeyConstraint)
        and {column.name for column in item.columns} == {"claim_id", "message_id"}
    )
    assert [(element.parent.name, element.target_fullname) for element in constraint.elements] == [
        ("claim_id", "answer_claims.claim_id"),
        ("message_id", "answer_claims.message_id"),
    ]
