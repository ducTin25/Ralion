from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.providers.embeddings import Embedder
from src.api.dependencies import get_embedder
from src.dto.request.policy_ingest_request_dto import PolicyIngestRequestDTO
from src.dto.response.policy_ingest_response_dto import PolicyIngestResponseDTO
from src.model.session import get_db
from src.modules.knowledge.policy_ingestion import PolicyIngestRequest, ingest_policy_document

router = APIRouter(prefix="/policies", tags=["knowledge"])


@router.post("/ingest", response_model=PolicyIngestResponseDTO, status_code=201)
async def ingest_policy(
    dto: PolicyIngestRequestDTO, db: AsyncSession = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
) -> PolicyIngestResponseDTO:
    try:
        document = await ingest_policy_document(
            db,
            PolicyIngestRequest(
                title=dto.title,
                content=dto.content,
                document_code=dto.document_code,
                policy_category=dto.policy_category,
                created_by_user_id=dto.created_by_user_id,
                source_url=dto.source_url,
                purpose_sentence=dto.purpose_sentence,
            ),
            embedder,
        )
    except (ValueError, RuntimeError) as exc:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return PolicyIngestResponseDTO(
        document_id=document.document_id,
        title=document.title,
        policy_category=document.policy_category.value,
        knowledge_domain=document.knowledge_domain.value,
        status=document.status.value,
        updated_at=document.updated_at,
    )
