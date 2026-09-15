"""Backfill Master Template cho các project được tạo TRƯỚC KHI Phase 2 tồn tại (PHONESHOP,
TOURBOOK, FURNISTORE tạo bởi scripts/seed_dev_data.py; GADGETHUB tạo qua API trước khi
project_service.create_project được sửa để tự materialize template) — các project này không đi
qua đường tạo project mới nên chưa có OnboardingTemplate scope=PROJECT nào.

Idempotent: project nào đã có template thì bỏ qua, không tạo trùng (chặn thêm bởi
UniqueConstraint("project_id") ở tầng DB nếu cố tạo lại).

Usage: python scripts/backfill_project_templates.py
"""
import asyncio
import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import select

from src.model.project import Project
from src.model.session import AsyncSessionLocal
from src.services import onboarding_template_service


async def main() -> None:
    async with AsyncSessionLocal() as db:
        global_template = await onboarding_template_service.get_approved_global_template(db)
        if global_template is None:
            print("Chưa có Global Master Template đã duyệt — chạy scripts/seed_dev_data.py trước.")
            return

        projects = list((await db.execute(select(Project).order_by(Project.project_id))).scalars().all())
        for project in projects:
            existing = await onboarding_template_service.get_by_project(db, project.project_id)
            if existing is not None:
                print(f"  = {project.key}: đã có template (id={existing.template_id}), bỏ qua")
                continue

            template = await onboarding_template_service.materialize_project_template(db, project, global_template)
            await db.commit()
            print(f"  + {project.key}: tạo template mới (id={template.template_id})")

        print("Backfill xong.")


if __name__ == "__main__":
    asyncio.run(main())
