from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from src.model.enums import TemplateVersionStatus
from src.model.template_version import TemplateVersion


class TemplateVersionResponseDTO(BaseModel):
    version_id: int
    template_id: int
    version_no: int
    status: TemplateVersionStatus
    approved_by_user_id: int | None
    approved_at: datetime | None
    created_at: datetime

    @classmethod
    def from_entity(cls, version: TemplateVersion) -> TemplateVersionResponseDTO:
        return cls(
            version_id=version.version_id,
            template_id=version.template_id,
            version_no=version.version_no,
            status=version.status,
            approved_by_user_id=version.approved_by_user_id,
            approved_at=version.approved_at,
            created_at=version.created_at,
        )
