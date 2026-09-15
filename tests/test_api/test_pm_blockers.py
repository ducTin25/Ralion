import pytest
import pytest_asyncio

from src.model.blocker import Blocker
from src.model.enums import (
    BlockerCategory,
    BlockerStatus,
    MembershipStatus,
    PlanStatus,
    ProjectRole,
    ProjectStatus,
    SyncStatus,
    TaskCategory,
    TaskStatus,
    TemplateScope,
    TemplateStatus,
    TemplateVersionStatus,
    UserStatus,
)
from src.model.onboarding_plan import OnboardingPlan
from src.model.onboarding_template import OnboardingTemplate
from src.model.plan_task import PlanTask
from src.model.project import Project
from src.model.project_membership import ProjectMembership
from src.model.template_task import TemplateTask
from src.model.template_version import TemplateVersion
from src.model.user import User
from src.services import blocker_service


@pytest_asyncio.fixture
async def blocker_fixture(db_session):
    admin = User(
        user_id=1,
        email="admin.pm-blocker@test.local",
        display_name="Admin",
        password_hash=None,
        status=UserStatus.ACTIVE,
    )
    pm = User(
        user_id=2,
        email="pm.pm-blocker@test.local",
        display_name="Project Manager",
        password_hash=None,
        status=UserStatus.ACTIVE,
    )
    engineer = User(
        user_id=3,
        email="engineer.pm-blocker@test.local",
        display_name="Engineer",
        password_hash=None,
        status=UserStatus.ACTIVE,
    )
    project = Project(
        project_id=10,
        key="BLOCKER",
        name="Blocker Project",
        github_repo="example/blocker",
        default_branch="main",
        created_by_admin_id=admin.user_id,
        status=ProjectStatus.ACTIVE,
        sync_status=SyncStatus.SUCCESS,
    )
    pm_membership = ProjectMembership(
        membership_id=11,
        user_id=pm.user_id,
        project_id=project.project_id,
        project_role=ProjectRole.PM,
        status=MembershipStatus.ACTIVE,
        assigned_by_admin_id=admin.user_id,
    )
    engineer_membership = ProjectMembership(
        membership_id=12,
        user_id=engineer.user_id,
        project_id=project.project_id,
        project_role=ProjectRole.ENGINEER,
        status=MembershipStatus.ACTIVE,
        assigned_by_admin_id=admin.user_id,
    )
    template = OnboardingTemplate(
        template_id=20,
        project_id=project.project_id,
        scope=TemplateScope.PROJECT,
        name="Blocker Template",
        description="Test template",
        status=TemplateStatus.APPROVED,
    )
    version = TemplateVersion(
        version_id=21,
        template_id=template.template_id,
        version_no=1,
        status=TemplateVersionStatus.APPROVED,
    )
    template_task = TemplateTask(
        template_task_id=22,
        version_id=version.version_id,
        category=TaskCategory.SETUP,
        title_pattern="Run the service",
        objective="Run the service locally",
        instruction_template="Run the service locally",
        display_order=1,
        estimated_minutes=30,
    )
    plan = OnboardingPlan(
        plan_id=30,
        membership_id=engineer_membership.membership_id,
        template_version_id=version.version_id,
        status=PlanStatus.ACTIVE,
    )
    task = PlanTask(
        plan_task_id=31,
        plan_id=plan.plan_id,
        template_task_id=template_task.template_task_id,
        title="Run the service",
        instruction="Run the service locally",
        display_order=1,
        status=TaskStatus.IN_PROGRESS,
    )
    blocker = Blocker(
        blocker_id=40,
        plan_task_id=task.plan_task_id,
        reported_by_membership_id=engineer_membership.membership_id,
        category=BlockerCategory.TECHNICAL,
        reason="The local service cannot connect to the database.",
        status=BlockerStatus.OPEN,
    )
    db_session.add_all(
        [
            admin,
            pm,
            engineer,
            project,
            pm_membership,
            engineer_membership,
            template,
            version,
            template_task,
            plan,
            task,
            blocker,
        ]
    )
    await db_session.commit()
    return db_session, project, blocker


@pytest.mark.asyncio
async def test_pm_can_list_and_resolve_engineer_blocker(blocker_fixture):
    db_session, project, blocker = blocker_fixture

    listed = await blocker_service.list_for_pm(db_session, project.project_id)
    assert len(listed) == 1
    assert listed[0].engineer_name == "Engineer"
    assert listed[0].status == BlockerStatus.OPEN

    resolved = await blocker_service.resolve_for_pm(
        db_session, project.project_id, blocker.blocker_id
    )
    assert resolved.status == BlockerStatus.RESOLVED
    assert resolved.resolved_at is not None

    listed_again = await blocker_service.list_for_pm(db_session, project.project_id)
    assert listed_again[0].status == BlockerStatus.RESOLVED


@pytest.mark.asyncio
async def test_pm_cannot_resolve_blocker_from_another_project(blocker_fixture):
    db_session, _project, blocker = blocker_fixture

    with pytest.raises(blocker_service.PmBlockerError) as error:
        await blocker_service.resolve_for_pm(db_session, 999, blocker.blocker_id)

    assert error.value.status_code == 404
