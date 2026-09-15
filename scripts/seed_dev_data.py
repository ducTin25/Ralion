"""Seed dữ liệu mẫu đầy đủ cho 3 project demo (PHONESHOP, TOURBOOK, FURNISTORE):
users, projects, memberships, onboarding template (GLOBAL) + version + tasks + dependencies,
onboarding plan + plan tasks (materialize từ template) cho từng engineer, và 1 blocker demo.

KnowledgeDocument/DocumentVersion/DocumentChunk/ChatSession/Citation được tạo riêng ở
scripts/upload_sample_docs_to_cloudinary.py (chạy SAU script này), vì cần project/user đã tồn tại.

Usage: python scripts/seed_dev_data.py
"""
import asyncio
import sys
from datetime import datetime

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.model.blocker import Blocker
from src.model.blocker_attachment import BlockerAttachment
from src.model.enums import (
    BlockerCategory,
    BlockerStatus,
    PlanStatus,
    ProjectRole,
    ProjectStatus,
    SyncStatus,
    TaskCategory,
    TaskStatus,
    TemplateScope,
    TemplateStatus,
    TemplateVersionStatus,
    UserRole,
    UserStatus,
)
from src.model.onboarding_plan import OnboardingPlan
from src.model.onboarding_template import OnboardingTemplate
from src.model.plan_task import PlanTask
from src.model.project import Project
from src.model.project_membership import ProjectMembership
from src.model.session import AsyncSessionLocal
from src.model.task_dependency import TaskDependency
from src.model.template_task import TemplateTask
from src.model.template_version import TemplateVersion
from src.model.user import User
from src.services.auth_service import hash_password

PROJECTS = [
    {"key": "PHONESHOP", "name": "PhoneShop API", "github_repo": "manh/group-project", "default_branch": "master"},
    {"key": "TOURBOOK", "name": "TourBooking Service", "github_repo": "manh/group-project", "default_branch": "master"},
    {"key": "FURNISTORE", "name": "FurniStore", "github_repo": "manh/group-project", "default_branch": "master"},
]

# (category, title_pattern, objective, instruction_template, estimated_minutes, mandatory)
TEMPLATE_TASKS = [
    (
        TaskCategory.ORIENTATION,
        "Đọc tài liệu Overview dự án",
        "Hiểu bối cảnh kinh doanh, mục tiêu, và trạng thái vận hành hiện tại của dự án trước khi bắt đầu bất kỳ công việc kỹ thuật nào.",
        "Mở tài liệu 'Overview' của dự án (mục Project Knowledge trong hệ thống). Đọc kỹ các phần: bối cảnh kinh doanh, số liệu vận hành hiện tại, người dùng chính, phạm vi hiện tại, và đặc biệt là mục 'Sự cố đáng chú ý gần đây' — đây là bài học quan trọng giúp bạn tránh lặp lại lỗi đã xảy ra. Ghi lại 2-3 câu hỏi nếu có phần chưa rõ, hỏi PM hoặc Tech Lead trong buổi 1-1 đầu tiên.",
        30,
        True,
    ),
    (
        TaskCategory.ARCHITECTURE,
        "Đọc tài liệu Architecture để hiểu hệ thống tổng thể",
        "Nắm được bức tranh kiến trúc tổng thể: tech stack, các module/service chính, và luồng dữ liệu quan trọng nhất.",
        "Đọc tài liệu 'Architecture'. Chú ý sơ đồ luồng chính và bảng tech stack. Không cần hiểu sâu ngay từng chi tiết — mục tiêu là nắm được các thành phần chính tên gì, vai trò gì, để khi đọc code không bị lạc.",
        45,
        True,
    ),
    (
        TaskCategory.ACCESS,
        "Xin quyền truy cập GitHub repo",
        "Có quyền truy cập source code để bắt đầu setup môi trường dev.",
        "Nhắn PM hoặc Tech Lead trên Slack xin được thêm vào GitHub team tương ứng của dự án (xem tên team cụ thể trong tài liệu Access & Security). Sau khi được thêm, clone repo về máy và xác nhận truy cập được.",
        20,
        True,
    ),
    (
        TaskCategory.ACCESS,
        "Xin quyền truy cập môi trường dev/staging",
        "Có đủ credential cần thiết (database staging, VPN nếu cần, dashboard giám sát) để làm việc và debug khi cần.",
        "Theo đúng bảng 'Xin quyền truy cập' trong tài liệu Access & Security, xin lần lượt: quyền xem database staging (read-only), VPN nội bộ nếu dự án yêu cầu, và tài khoản các công cụ giám sát. Lưu credential vào password manager công ty, KHÔNG lưu trong file text trên máy.",
        60,
        True,
    ),
    (
        TaskCategory.SETUP,
        "Cài đặt công cụ phát triển theo đúng tech stack",
        "Có đầy đủ công cụ (ngôn ngữ, package manager, Docker...) đúng phiên bản dự án yêu cầu.",
        "Làm theo đúng mục 'Yêu cầu hệ thống' trong tài liệu Setup của dự án. Cài đúng phiên bản ngôn ngữ (dùng version manager thay vì cài global để tránh xung đột với dự án khác trên máy). Cài Docker Desktop nếu chưa có.",
        90,
        True,
    ),
    (
        TaskCategory.SETUP,
        "Chạy được service ở local, xác nhận health check",
        "Có môi trường dev chạy được hoàn chỉnh trên máy cá nhân, sẵn sàng để code và debug.",
        "Làm theo đúng thứ tự các bước trong mục 'Các bước setup từ đầu' của tài liệu Setup. Sau khi chạy xong, thực hiện đủ các bước ở mục 'Kiểm tra chạy đúng'. Nếu gặp lỗi, tra trước trong bảng 'Lỗi thường gặp' — phần lớn vấn đề đã có sẵn cách fix.",
        120,
        True,
    ),
    (
        TaskCategory.CODEBASE,
        "Đọc Codebase Guide, xác định các module chính",
        "Hiểu cấu trúc thư mục, nguyên tắc kiến trúc, và biết những file nào quan trọng nhất cần đọc kỹ trước khi sửa code.",
        "Đọc tài liệu Codebase Guide, đặc biệt mục 'File quan trọng cần đọc trước khi code'. Mở từng file được liệt kê, đọc lướt để có khái niệm, chưa cần hiểu 100% chi tiết logic ngay. Ghi chú lại vai trò từng module chính để tra cứu sau này.",
        90,
        True,
    ),
]
# CONVENTION/FIRST_TASK/FIRST_PR đã bỏ khỏi Master Template chuẩn (mở rộng làm sau — theo quyết
# định rút gọn còn đúng 5 category khớp 5 giá trị đầu của DocumentCategory: OVERVIEW/ARCHITECTURE/
# SETUP/ACCESS_SECURITY/CODEBASE_GUIDE). Task cũ ở các nhóm này đã bị xoá khỏi DB thật qua
# scripts/reshape_template_task_categories.py — không seed lại ở đây để lần seed tiếp theo (DB mới
# từ đầu) ra đúng cấu trúc 5 category ngay, không cần chạy thêm script dọn dẹp.


async def get_or_create_user(db: AsyncSession, email: str, display_name: str, system_role: UserRole | None) -> User:
    user = await db.scalar(select(User).where(User.email == email))
    if user:
        # Seed là idempotent nhưng vẫn phải reconcile tên demo để UI không phụ thuộc
        # vào snapshot database cũ.
        if user.display_name != display_name:
            user.display_name = display_name
            await db.flush()
        if not user.password_hash:
            user.password_hash = hash_password("ralionralion")
        return user
    user = User(email=email, display_name=display_name, system_role=system_role, status=UserStatus.ACTIVE, password_hash=hash_password("ralionralion"))
    db.add(user)
    await db.flush()
    print(f"  + user: {email}")
    return user


async def get_or_create_project(
    db: AsyncSession, key: str, name: str, admin_id: int, github_repo: str, default_branch: str
) -> Project:
    project = await db.scalar(select(Project).where(Project.key == key))
    if project:
        project.github_repo = github_repo
        project.default_branch = default_branch
        return project
    project = Project(
        key=key,
        name=name,
        created_by_admin_id=admin_id,
        status=ProjectStatus.ACTIVE,
        github_repo=github_repo,
        default_branch=default_branch,
    )
    db.add(project)
    await db.flush()
    print(f"  + project: {key}")
    return project


async def get_or_create_membership(
    db: AsyncSession, user_id: int, project_id: int, role: ProjectRole, assigned_by_admin_id: int
) -> ProjectMembership:
    membership = await db.scalar(
        select(ProjectMembership).where(
            ProjectMembership.user_id == user_id, ProjectMembership.project_id == project_id
        )
    )
    if membership:
        return membership
    membership = ProjectMembership(
        user_id=user_id,
        project_id=project_id,
        project_role=role,
        assigned_by_admin_id=assigned_by_admin_id,
    )
    db.add(membership)
    await db.flush()
    print(f"    + membership: user={user_id} project={project_id} role={role.value}")
    return membership


async def seed_global_template(db: AsyncSession, admin: User) -> TemplateVersion:
    template = await db.scalar(
        select(OnboardingTemplate).where(
            OnboardingTemplate.scope == TemplateScope.GLOBAL, OnboardingTemplate.name == "Standard Engineer Onboarding"
        )
    )
    if template is None:
        template = OnboardingTemplate(
            scope=TemplateScope.GLOBAL,
            name="Standard Engineer Onboarding",
            description="Checklist onboarding chuẩn cho engineer mới, áp dụng chung cho mọi dự án.",
            status=TemplateStatus.APPROVED,
        )
        db.add(template)
        await db.flush()
        print(f"  + onboarding_template: {template.name}")

    version = await db.scalar(
        select(TemplateVersion).where(
            TemplateVersion.template_id == template.template_id, TemplateVersion.version_no == 1
        )
    )
    if version:
        return version

    version = TemplateVersion(
        template_id=template.template_id,
        version_no=1,
        status=TemplateVersionStatus.APPROVED,
        approved_by_user_id=admin.user_id,
        approved_at=datetime.utcnow(),
    )
    db.add(version)
    await db.flush()
    print(f"  + template_version: v1 (template_id={template.template_id})")

    tasks: list[TemplateTask] = []
    for order, (category, title_pattern, objective, instruction, minutes, mandatory) in enumerate(
        TEMPLATE_TASKS, start=1
    ):
        task = TemplateTask(
            version_id=version.version_id,
            category=category,
            title_pattern=title_pattern,
            objective=objective,
            instruction_template=instruction,
            display_order=order,
            mandatory=mandatory,
            estimated_minutes=minutes,
        )
        db.add(task)
        tasks.append(task)
    await db.flush()
    print(f"    + {len(tasks)} template_tasks")

    for predecessor, successor in zip(tasks, tasks[1:]):
        db.add(
            TaskDependency(
                predecessor_task_id=predecessor.template_task_id,
                successor_task_id=successor.template_task_id,
            )
        )
    await db.flush()
    print(f"    + {len(tasks) - 1} task_dependencies (chuỗi tuần tự)")

    return version


async def seed_plan_for_engineer(
    db: AsyncSession, membership: ProjectMembership, template_version: TemplateVersion, demo_statuses: list[TaskStatus]
) -> None:
    existing_plan = await db.scalar(
        select(OnboardingPlan).where(OnboardingPlan.membership_id == membership.membership_id)
    )
    if existing_plan:
        return

    plan = OnboardingPlan(
        membership_id=membership.membership_id,
        template_version_id=template_version.version_id,
        status=PlanStatus.ACTIVE,
    )
    db.add(plan)
    await db.flush()
    print(f"  + onboarding_plan: membership={membership.membership_id}")

    template_tasks_result = await db.execute(
        select(TemplateTask)
        .where(TemplateTask.version_id == template_version.version_id)
        .order_by(TemplateTask.display_order)
    )
    template_tasks = list(template_tasks_result.scalars().all())

    for template_task, status in zip(template_tasks, demo_statuses):
        completed_at = datetime.utcnow() if status == TaskStatus.DONE else None
        started_at = datetime.utcnow() if status in (TaskStatus.IN_PROGRESS, TaskStatus.DONE) else None
        db.add(
            PlanTask(
                plan_id=plan.plan_id,
                template_task_id=template_task.template_task_id,
                title=template_task.title_pattern,
                instruction=template_task.instruction_template,
                display_order=template_task.display_order,
                mandatory=template_task.mandatory,
                status=status,
                started_at=started_at,
                completed_at=completed_at,
            )
        )
    await db.flush()
    print(f"    + {len(template_tasks)} plan_tasks")


async def seed_demo_blocker(db: AsyncSession, membership: ProjectMembership) -> None:
    target_task = await db.scalar(
        select(PlanTask)
        .join(OnboardingPlan, PlanTask.plan_id == OnboardingPlan.plan_id)
        .where(
            OnboardingPlan.membership_id == membership.membership_id,
            PlanTask.status != TaskStatus.DONE,
        )
        .order_by(PlanTask.display_order)
        .limit(1)
    )
    if target_task is None:
        return

    existing = await db.scalar(
        select(Blocker)
        .join(PlanTask, Blocker.plan_task_id == PlanTask.plan_task_id)
        .join(OnboardingPlan, PlanTask.plan_id == OnboardingPlan.plan_id)
        .where(OnboardingPlan.membership_id == membership.membership_id)
        .order_by(Blocker.blocker_id)
        .limit(1)
    )
    if existing:
        # Dữ liệu seed cũ từng gắn blocker OPEN vào task DONE. Chuyển đúng record
        # demo sang task chưa hoàn thành thay vì tạo blocker trùng.
        if existing.plan_task_id != target_task.plan_task_id:
            existing.plan_task_id = target_task.plan_task_id
            await db.flush()
            print(f"    ~ blocker demo: chuyển sang plan_task={target_task.plan_task_id}")
        return

    blocker = Blocker(
        plan_task_id=target_task.plan_task_id,
        reported_by_membership_id=membership.membership_id,
        category=BlockerCategory.ACCESS,
        reason="Chưa được cấp quyền truy cập GitHub team, không clone được repo.",
        status=BlockerStatus.OPEN,
    )
    db.add(blocker)
    await db.flush()
    print(f"  + blocker: plan_task={target_task.plan_task_id}")

    db.add(
        BlockerAttachment(
            blocker_id=blocker.blocker_id,
            storage_key="demo/screenshots/github-access-denied.png",
            file_name="github-access-denied.png",
            mime_type="image/png",
        )
    )
    await db.flush()
    print("    + blocker_attachment demo")


async def main() -> None:
    async with AsyncSessionLocal() as db:
        admin = await get_or_create_user(db, "admin@onboarding.dev", "Admin Root", UserRole.ADMIN)
        await get_or_create_user(db, "hr@onboarding.dev", "Le Van HR", UserRole.HR)
        demo_user = await get_or_create_user(db, "an.nguyen@onboarding.dev", "An Nguyen", None)
        await db.commit()

        template_version = await seed_global_template(db, admin)
        await db.commit()

        # Khớp thứ tự 12 TEMPLATE_TASKS: đã xong orientation+access+setup, đang đọc codebase guide,
        # còn lại (convention, 2 first-task, PR, 1-1) chưa bắt đầu — mô phỏng 1 engineer đang ở ngày 2-3 onboarding.
        demo_statuses = [
            TaskStatus.DONE,
            TaskStatus.DONE,
            TaskStatus.DONE,
            TaskStatus.DONE,
            TaskStatus.DONE,
            TaskStatus.IN_PROGRESS,
            TaskStatus.NOT_STARTED,
            TaskStatus.NOT_STARTED,
            TaskStatus.NOT_STARTED,
            TaskStatus.NOT_STARTED,
            TaskStatus.NOT_STARTED,
            TaskStatus.NOT_STARTED,
        ]

        seeded_projects: list[Project] = []
        demo_engineer: User | None = None

        for index, proj in enumerate(PROJECTS):
            slug = proj["key"].lower()
            project = await get_or_create_project(
                db,
                proj["key"],
                proj["name"],
                admin.user_id,
                proj["github_repo"],
                proj["default_branch"],
            )
            if project.sync_status == SyncStatus.NOT_STARTED:
                project.sync_status = (
                    SyncStatus.FAILED if proj["key"] == "FURNISTORE" else SyncStatus.SUCCESS
                )
                project.last_synced_at = datetime.utcnow()
            await db.commit()

            pm_user = await get_or_create_user(db, f"pm.{slug}@onboarding.dev", f"PM {proj['name']}", None)
            engineer_display_name = "Nguyễn Văn A" if index == 0 else f"Engineer {proj['name']}"
            engineer_user = await get_or_create_user(
                db, f"engineer.{slug}@onboarding.dev", engineer_display_name, None
            )
            if index == 0:
                demo_engineer = engineer_user
            seeded_projects.append(project)
            await db.commit()

            pm_membership = await get_or_create_membership(
                db, pm_user.user_id, project.project_id, ProjectRole.PM, admin.user_id
            )
            engineer_membership = await get_or_create_membership(
                db, engineer_user.user_id, project.project_id, ProjectRole.ENGINEER, admin.user_id
            )
            demo_role = ProjectRole.PM if proj["key"] == "PHONESHOP" else ProjectRole.ENGINEER
            demo_membership = await get_or_create_membership(
                db, demo_user.user_id, project.project_id, demo_role, admin.user_id
            )
            await db.commit()

            if project.primary_pm_membership_id is None:
                project.primary_pm_membership_id = pm_membership.membership_id
                await db.commit()
                print(f"    ~ project {proj['key']}: gán primary_pm_membership_id={pm_membership.membership_id}")

            await seed_plan_for_engineer(db, engineer_membership, template_version, demo_statuses)
            await seed_plan_for_engineer(db, demo_membership, template_version, demo_statuses)
            await db.commit()

            await seed_demo_blocker(db, engineer_membership)
            if proj["key"] == "TOURBOOK":
                await seed_demo_blocker(db, demo_membership)
            await db.commit()

        # Engineer demo có hai Project Membership để project switcher chạy bằng
        # dữ liệu thật. Đây vẫn là quan hệ hợp lệ: một project có một PM và nhiều
        # engineer; INV1 chỉ cấm user có system_role tham gia project.
        if demo_engineer is not None and len(seeded_projects) >= 2:
            second_membership = await get_or_create_membership(
                db,
                demo_engineer.user_id,
                seeded_projects[1].project_id,
                ProjectRole.ENGINEER,
                admin.user_id,
            )
            await db.commit()
            await seed_plan_for_engineer(db, second_membership, template_version, demo_statuses)
            await db.commit()

        print("\nSeed xong. Chạy tiếp: python scripts/upload_sample_docs_to_cloudinary.py")


if __name__ == "__main__":
    asyncio.run(main())
