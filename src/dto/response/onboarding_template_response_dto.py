from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from src.model.enums import TemplateScope, TemplateStatus
from src.model.onboarding_template import OnboardingTemplate


class OnboardingTemplateResponseDTO(BaseModel):
    template_id: int
    project_id: int | None
    source_template_id: int | None
    scope: TemplateScope
    name: str
    description: str
    status: TemplateStatus
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, template: OnboardingTemplate) -> OnboardingTemplateResponseDTO:
        return cls(
            template_id=template.template_id,
            project_id=template.project_id,
            source_template_id=template.source_template_id,
            scope=template.scope,
            name=template.name,
            description=template.description,
            status=template.status,
            created_at=template.created_at,
            updated_at=template.updated_at,
        )
