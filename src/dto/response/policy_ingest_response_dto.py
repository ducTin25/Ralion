from datetime import datetime

from pydantic import BaseModel


class PolicyIngestResponseDTO(BaseModel):
    document_id: int
    title: str
    policy_category: str
    knowledge_domain: str
    status: str
    updated_at: datetime
