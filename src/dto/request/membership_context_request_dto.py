from pydantic import BaseModel, Field


class ActiveMembershipRequestDTO(BaseModel):
    membership_id: int = Field(..., gt=0)
