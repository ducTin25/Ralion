from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from src.model.enums import PlanStatus
from src.model.onboarding_plan import OnboardingPlan


class OnboardingPlanResponseDTO(BaseModel):
    """Chỉ dùng để đọc — luồng tạo Plan thật (sinh từ TemplateVersion) thuộc Phase 4,
    chưa build ở đây. Route liên quan: GET /onboarding-plans/pm/by-membership/{id}."""

    plan_id: int
    # Đúng 1 trong 2 có giá trị (CHECK ck_onboarding_plans_owner):
    #   membership_id -> plan đã cấp cho 1 kỹ sư;  project_id -> lộ trình chuẩn của dự án.
    membership_id: int | None
    project_id: int | None
    template_version_id: int
    revision: int
    status: PlanStatus
    approved_by_user_id: int | None
    approved_at: datetime | None
    created_at: datetime
    closed_at: datetime | None
    first_pr_url: str | None
    first_pr_merged_at: datetime | None
    first_pr_confirmed_by_user_id: int | None

    @classmethod
    def from_entity(cls, plan: OnboardingPlan) -> OnboardingPlanResponseDTO:
        return cls(
            plan_id=plan.plan_id,
            membership_id=plan.membership_id,
            project_id=plan.project_id,
            template_version_id=plan.template_version_id,
            revision=plan.revision,
            status=plan.status,
            approved_by_user_id=plan.approved_by_user_id,
            approved_at=plan.approved_at,
            created_at=plan.created_at,
            closed_at=plan.closed_at,
            first_pr_url=plan.first_pr_url,
            first_pr_merged_at=plan.first_pr_merged_at,
            first_pr_confirmed_by_user_id=plan.first_pr_confirmed_by_user_id,
        )
