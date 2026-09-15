from pydantic import BaseModel, Field

from src.model.enums import PolicyCategory


class PolicyIngestRequestDTO(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1)
    document_code: str = Field(min_length=1, max_length=100)
    policy_category: PolicyCategory
    created_by_user_id: int = Field(gt=0)
    source_url: str = Field(min_length=1, max_length=1000)
    purpose_sentence: str = ""
