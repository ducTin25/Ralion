"""Dọn dữ liệu 1 lần: rút Master Template còn đúng 5 category khớp 5 giá trị đầu của
DocumentCategory (OVERVIEW/ARCHITECTURE/SETUP/ACCESS_SECURITY/CODEBASE_GUIDE) — theo quyết định
sản phẩm rút gọn khỏi 7 category cũ (bỏ CONVENTION/FIRST_TASK/FIRST_PR, coi là mở rộng làm sau).

Chạy trên MỌI TemplateVersion đang có (GLOBAL + 4 project demo, kể cả version đã APPROVED/ARCHIVED)
— chấp nhận sửa thẳng vì đây là dọn cấu trúc category, không phải nghiệp vụ approve/archive bình
thường, và không có API nào cho việc này (đúng chủ đích — PM không tự ý đổi cấu trúc category).

Việc làm:
1. Đổi category: TemplateTask có title_pattern chứa "Architecture" (đang ORIENTATION) -> ARCHITECTURE.
2. Xoá hẳn (hard-delete): TemplateTask có category IN (CONVENTION, FIRST_TASK, FIRST_PR), xoá
   TaskDependency liên quan trước (cả 2 chiều predecessor/successor). BỎ QUA (không xoá) task nào
   đang bị PlanTask tham chiếu (FK) — đây là dữ liệu demo OnboardingPlan/PlanTask của Phase 1 (đã
   seed sẵn từ trước), không được xoá lùi lịch sử Plan đã tạo. Các task này chỉ còn "mồ côi" (không
   hiện ở UI Master Template mới vì category đã ẩn), không ảnh hưởng gì thêm.

Usage: python scripts/reshape_template_task_categories.py
"""
import asyncio
import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import delete, or_, select

from src.model.enums import DEFERRED_TASK_CATEGORIES, TaskCategory
from src.model.plan_task import PlanTask
from src.model.session import AsyncSessionLocal
from src.model.task_dependency import TaskDependency
from src.model.template_task import TemplateTask


async def main() -> None:
    async with AsyncSessionLocal() as db:
        # 1. Đổi category task Architecture (đang nằm nhầm trong ORIENTATION).
        arch_tasks = (
            await db.execute(
                select(TemplateTask).where(
                    TemplateTask.category == TaskCategory.ORIENTATION,
                    TemplateTask.title_pattern.ilike("%Architecture%"),
                )
            )
        ).scalars().all()
        for task in arch_tasks:
            task.category = TaskCategory.ARCHITECTURE
        print(
            f"  ~ Đổi category ARCHITECTURE cho {len(arch_tasks)} task "
            f"(id: {[t.template_task_id for t in arch_tasks]})"
        )
        await db.commit()

        # 2. Xoá hẳn task thuộc 3 category bị rút gọn + dependency liên quan — bỏ qua task đang
        # bị PlanTask tham chiếu (giữ nguyên lịch sử Plan demo đã seed).
        deferred_tasks = (
            await db.execute(select(TemplateTask).where(TemplateTask.category.in_(DEFERRED_TASK_CATEGORIES)))
        ).scalars().all()
        all_ids = [t.template_task_id for t in deferred_tasks]

        referenced_ids: set[int] = set()
        if all_ids:
            referenced_ids = set(
                (
                    await db.execute(
                        select(PlanTask.template_task_id).where(PlanTask.template_task_id.in_(all_ids)).distinct()
                    )
                )
                .scalars()
                .all()
            )

        deletable_ids = [i for i in all_ids if i not in referenced_ids]
        skipped_ids = [i for i in all_ids if i in referenced_ids]

        if skipped_ids:
            print(
                f"  ! Bỏ qua {len(skipped_ids)} task đang bị PlanTask tham chiếu, không xoá "
                f"(id: {skipped_ids})"
            )

        if deletable_ids:
            dep_result = await db.execute(
                delete(TaskDependency).where(
                    or_(
                        TaskDependency.predecessor_task_id.in_(deletable_ids),
                        TaskDependency.successor_task_id.in_(deletable_ids),
                    )
                )
            )
            print(f"  ~ Xoá {dep_result.rowcount} task_dependency liên quan")

            task_result = await db.execute(delete(TemplateTask).where(TemplateTask.template_task_id.in_(deletable_ids)))
            print(f"  ~ Xoá {task_result.rowcount} template_task thuộc CONVENTION/FIRST_TASK/FIRST_PR")
        else:
            print("  = Không có task nào xoá được (tất cả đều bị tham chiếu hoặc không có)")

        await db.commit()
        print("Xong.")


if __name__ == "__main__":
    asyncio.run(main())
