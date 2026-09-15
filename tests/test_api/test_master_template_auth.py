"""Kiểm thử phân quyền cho các endpoint sửa Master Template (template-tasks/template-versions/
onboarding-templates) — trước đây các endpoint này KHÔNG có auth guard nào (ai gọi cũng được, kể
cả chưa đăng nhập). Test này khoá lại: Admin luôn qua được; template scope GLOBAL chỉ Admin sửa
được; template scope PROJECT thì phải là PM đang có membership ACTIVE đúng project đó.

Chạy trên SQLite in-memory (fixture `db_client`/`db_session`), không cần PostgreSQL.
"""

import pytest

from src.api.dependencies import get_current_user, get_current_user_id
from src.main import app
from src.model.enums import (
    MembershipStatus,
    ProjectRole,
    ProjectStatus,
    TaskCategory,
    TemplateScope,
    TemplateStatus,
    TemplateVersionStatus,
    UserRole,
    UserStatus,
)
from src.model.onboarding_template import OnboardingTemplate
from src.model.project import Project
from src.model.project_membership import ProjectMembership
from src.model.template_task import TemplateTask
from src.model.template_version import TemplateVersion
from src.model.user import User
from src.services.auth_service import hash_password

API = "/api/v1"


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_user_id, None)


def _login_as(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_user_id] = lambda: user.user_id


async def _seed_user(db_session, email: str, role: UserRole | None = None) -> User:
    user = User(
        email=email,
        display_name=email.split("@")[0],
        password_hash=hash_password("password"),
        system_role=role,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _seed_project(db_session, key: str) -> Project:
    creator = await _seed_user(db_session, f"{key.lower()}-creator@onboarding.dev", UserRole.ADMIN)
    project = Project(
        key=key,
        name=key.title(),
        github_repo=f"example/{key.lower()}",
        default_branch="main",
        created_by_admin_id=creator.user_id,
        status=ProjectStatus.ACTIVE,
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


async def _seed_pm_membership(db_session, user: User, project: Project) -> ProjectMembership:
    membership = ProjectMembership(
        project_id=project.project_id,
        user_id=user.user_id,
        project_role=ProjectRole.PM,
        status=MembershipStatus.ACTIVE,
        assigned_by_admin_id=project.created_by_admin_id,
    )
    db_session.add(membership)
    await db_session.commit()
    return membership


async def _seed_template_with_task(
    db_session, *, scope: TemplateScope, project_id: int | None
) -> tuple[OnboardingTemplate, TemplateVersion, TemplateTask]:
    template = OnboardingTemplate(
        project_id=project_id,
        scope=scope,
        name="Test template",
        description="seed",
        status=TemplateStatus.DRAFT,
    )
    db_session.add(template)
    await db_session.flush()
    version = TemplateVersion(template_id=template.template_id, version_no=1, status=TemplateVersionStatus.DRAFT)
    db_session.add(version)
    await db_session.flush()
    task = TemplateTask(
        version_id=version.version_id,
        category=TaskCategory.SETUP,
        title_pattern="Setup task",
        objective="obj",
        instruction_template="do it",
        mandatory=True,
        estimated_minutes=30,
        display_order=1,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(template)
    await db_session.refresh(version)
    await db_session.refresh(task)
    return template, version, task


@pytest.mark.asyncio
async def test_chua_dang_nhap_bi_chan_401(db_client, db_session):
    _, _, task = await _seed_template_with_task(db_session, scope=TemplateScope.GLOBAL, project_id=None)
    response = await db_client.patch(
        f"{API}/template-tasks/pm/{task.template_task_id}", json={"mandatory": False}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_sua_duoc_global_template(db_client, db_session):
    admin = await _seed_user(db_session, "admin@onboarding.dev", UserRole.ADMIN)
    _login_as(admin)
    _, _, task = await _seed_template_with_task(db_session, scope=TemplateScope.GLOBAL, project_id=None)
    response = await db_client.patch(
        f"{API}/template-tasks/pm/{task.template_task_id}", json={"mandatory": False}
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_pm_khong_sua_duoc_global_template(db_client, db_session):
    project = await _seed_project(db_session, "ALP")
    pm = await _seed_user(db_session, "pm@onboarding.dev")
    await _seed_pm_membership(db_session, pm, project)
    _login_as(pm)
    _, _, task = await _seed_template_with_task(db_session, scope=TemplateScope.GLOBAL, project_id=None)
    response = await db_client.patch(
        f"{API}/template-tasks/pm/{task.template_task_id}", json={"mandatory": False}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_pm_sua_duoc_template_dung_project_cua_minh(db_client, db_session):
    project = await _seed_project(db_session, "ALP")
    pm = await _seed_user(db_session, "pm@onboarding.dev")
    await _seed_pm_membership(db_session, pm, project)
    _login_as(pm)
    _, _, task = await _seed_template_with_task(
        db_session, scope=TemplateScope.PROJECT, project_id=project.project_id
    )
    response = await db_client.patch(
        f"{API}/template-tasks/pm/{task.template_task_id}", json={"mandatory": False}
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_pm_khong_sua_duoc_template_project_khac(db_client, db_session):
    owner_project = await _seed_project(db_session, "ALP")
    other_project = await _seed_project(db_session, "BET")
    pm_other = await _seed_user(db_session, "pm-other@onboarding.dev")
    await _seed_pm_membership(db_session, pm_other, other_project)
    _login_as(pm_other)
    _, _, task = await _seed_template_with_task(
        db_session, scope=TemplateScope.PROJECT, project_id=owner_project.project_id
    )
    response = await db_client.patch(
        f"{API}/template-tasks/pm/{task.template_task_id}", json={"mandatory": False}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_reorder_va_create_task_cung_bi_chan_theo_project(db_client, db_session):
    """id cần kiểm tra nằm trong request body (version_id) chứ không phải path — xác nhận nhánh
    inline-check (`authorize_template_scope_for_version`) hoạt động đúng, không chỉ nhánh path."""
    owner_project = await _seed_project(db_session, "ALP")
    other_project = await _seed_project(db_session, "BET")
    pm_other = await _seed_user(db_session, "pm-other@onboarding.dev")
    await _seed_pm_membership(db_session, pm_other, other_project)
    _login_as(pm_other)
    _, version, task = await _seed_template_with_task(
        db_session, scope=TemplateScope.PROJECT, project_id=owner_project.project_id
    )

    reorder_response = await db_client.patch(
        f"{API}/template-tasks/pm/reorder",
        json={"version_id": version.version_id, "ordered_template_task_ids": [task.template_task_id]},
    )
    assert reorder_response.status_code == 403

    create_response = await db_client.post(
        f"{API}/template-tasks/pm",
        json={
            "version_id": version.version_id,
            "category": "SETUP",
            "title_pattern": "New task",
            "objective": "obj",
            "instruction_template": "do it",
            "mandatory": True,
            "estimated_minutes": 20,
        },
    )
    assert create_response.status_code == 403


@pytest.mark.asyncio
async def test_pm_khong_duyet_duoc_version_cua_project_khac(db_client, db_session):
    owner_project = await _seed_project(db_session, "ALP")
    other_project = await _seed_project(db_session, "BET")
    pm_other = await _seed_user(db_session, "pm-other@onboarding.dev")
    await _seed_pm_membership(db_session, pm_other, other_project)
    _login_as(pm_other)
    _, version, _ = await _seed_template_with_task(
        db_session, scope=TemplateScope.PROJECT, project_id=owner_project.project_id
    )
    response = await db_client.patch(f"{API}/template-versions/pm/{version.version_id}/approve")
    assert response.status_code == 403
