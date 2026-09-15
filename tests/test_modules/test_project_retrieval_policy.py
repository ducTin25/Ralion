import pytest

from src.model.enums import DocumentCategory, PlanStatus
from src.modules.chat.application.chat_service import _phase_categories

_BASE_CATEGORIES = frozenset(
    {
        DocumentCategory.OVERVIEW,
        DocumentCategory.ARCHITECTURE,
        DocumentCategory.SETUP,
        DocumentCategory.ACCESS_SECURITY,
        DocumentCategory.CODEBASE_GUIDE,
    }
)


@pytest.mark.parametrize("status", [None, PlanStatus.DRAFT, PlanStatus.ONBOARDING_CLOSED])
def test_conventions_are_retrievable_without_an_onboarding_plan_or_in_restricted_phases(status) -> None:
    # `None` is the _scope() value when the membership has no onboarding plan.
    # Only approved, project-scoped conventions bypass the onboarding-phase document gate.
    assert _phase_categories(status) == frozenset({DocumentCategory.CONVENTION})


@pytest.mark.parametrize("status", [PlanStatus.APPROVED, PlanStatus.ACTIVE])
def test_approved_and_active_phases_share_the_same_base_category_set(status) -> None:
    # SoT line 344: "Chỉ plan APPROVED/ACTIVE được phát cho Engineer" -- APPROVED already
    # grants full plan access, so it must unlock the same base documents as ACTIVE. There is
    # no code path that ever moves a plan APPROVED -> ACTIVE, so gating on ACTIVE alone would
    # permanently lock chat for every plan created through the app.
    assert _phase_categories(status) == _BASE_CATEGORIES | {DocumentCategory.CONVENTION}


def test_project_ready_phase_can_retrieve_every_confirmed_project_category() -> None:
    assert _phase_categories(PlanStatus.PROJECT_READY) == frozenset(DocumentCategory)
