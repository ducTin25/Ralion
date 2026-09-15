"""Điều phối 6 bước sinh Candidate Plan + cập nhật tiến độ cho FE poll.

Cố ý viết bằng async function tuần tự thay vì LangGraph: 6 bước này có thứ tự CỐ ĐỊNH, không có
nhánh rẽ phụ thuộc quyết định của LLM. Thêm framework orchestration vào đây chỉ làm khó debug và
khó test, không đổi được hành vi (xem `docs/PM/plan-pm.md` mục "Dependency mới cần thêm").
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.model.project import Project
from src.observability import flush_traces, log_step_event, observe_step, tag_project_trace
from src.services import onboarding_plan_service
from src.services.plan_generation import content_llm, steps
from src.services.plan_generation.job_store import GenerationJob, JobStatus


@observe_step("execute_tool load_template")
async def _step_load_template(
    db: AsyncSession, membership_id: int | None, project_id: int | None
) -> steps.GenerationContext:
    if membership_id is not None:
        return await steps.load_template(db, membership_id)
    return await steps.load_template_for_project(db, project_id)


@observe_step("execute_tool merge_company_core")
async def _step_merge_company_core(
    db: AsyncSession, context: steps.GenerationContext
) -> steps.GenerationContext:
    return await steps.merge_company_core(db, context)


@observe_step("execute_tool collect_project_docs")
async def _step_collect_project_docs(
    db: AsyncSession, context: steps.GenerationContext
) -> steps.GenerationContext:
    return await steps.collect_project_docs(db, context)


@observe_step("execute_tool map_task_sources")
async def _step_map_task_sources(context: steps.GenerationContext) -> steps.GenerationContext:
    return steps.map_task_sources(context)


@observe_step("generate_plan_task_content", as_type="generation")
async def _step_generate_content(
    db: AsyncSession,
    context: steps.GenerationContext,
    project_key: str,
    reference_plan_id: int | None,
    progress: Callable[[int, int], None] | None = None,
) -> dict[int, content_llm.TaskContent]:
    """Hai đường rẽ rõ ràng:

    - Cấp plan cho kỹ sư (`reference_plan_id` có giá trị) → SAO CHÉP bản chuẩn, không bao giờ gọi AI.
    - Sinh/tạo lại bản chuẩn của dự án → gọi AI. Đây là chỗ DUY NHẤT còn gọi LLM trong hệ thống.
    """
    if reference_plan_id is not None:
        return await content_llm.load_reference_content(db, reference_plan_id)
    if content_llm.should_use_ai():
        return await content_llm.generate_ai_content(db, context, project_key, progress=progress)
    return content_llm.generate_baseline_content(context)


@observe_step("execute_tool validate_and_persist")
async def _step_validate_and_persist(
    db: AsyncSession,
    context: steps.GenerationContext,
    contents: dict[int, content_llm.TaskContent],
    existing_plan_id: int | None,
    schedule_start_at: datetime | None = None,
):
    warnings = steps.validate_generated(context, dict(contents))
    plan = await onboarding_plan_service.persist_generated_plan(
        db,
        context=context,
        contents=contents,
        existing_plan_id=existing_plan_id,
        schedule_start_at=schedule_start_at,
    )
    return plan, warnings


# Span GỐC bọc cả 6 bước — không có nó thì mỗi bước tự tạo 1 trace riêng lẻ, mất hết quan hệ
# cha-con và không xem được tổng thời gian 1 lần sinh plan trên dashboard.
@observe_step("generate_candidate_plan", as_type="span")
async def run_generation(
    db: AsyncSession,
    job: GenerationJob,
    *,
    existing_plan_id: int | None = None,
    schedule_start_at: datetime | None = None,
) -> None:
    """Chạy đủ 6 bước rồi ghi plan. Mọi lỗi được ghi vào job (FE đọc được), không ném ra ngoài —
    hàm này chạy nền qua BackgroundTasks nên ném ra cũng không ai bắt."""
    started = time.perf_counter()
    log_step_event(
        event="generation_started",
        correlation_id=job.correlation_id,
        job_id=job.job_id,
        membership_id=job.membership_id,
        project_id=job.project_id,
    )

    try:
        job.start_step("load_template")
        context = await _step_load_template(db, job.membership_id, job.project_id)
        duration = job.finish_step("load_template", f"{len(context.template_tasks)} task trong template")
        log_step_event(
            event="step_done",
            step="load_template",
            correlation_id=job.correlation_id,
            duration_ms=duration,
            task_count=len(context.template_tasks),
            template_version_id=context.template_version.version_id,
            project_id=context.project_id,
        )

        job.start_step("merge_company_core")
        context = await _step_merge_company_core(db, context)
        duration = job.finish_step(
            "merge_company_core", f"{len(context.policy_documents)} tài liệu chính sách"
        )
        log_step_event(
            event="step_done",
            step="merge_company_core",
            correlation_id=job.correlation_id,
            duration_ms=duration,
            policy_document_count=len(context.policy_documents),
        )

        job.start_step("collect_project_docs")
        context = await _step_collect_project_docs(db, context)
        duration = job.finish_step(
            "collect_project_docs", f"{len(context.project_documents)} tài liệu dự án"
        )
        log_step_event(
            event="step_done",
            step="collect_project_docs",
            correlation_id=job.correlation_id,
            duration_ms=duration,
            document_count=len(context.project_documents),
        )

        job.start_step("map_task_sources")
        context = await _step_map_task_sources(context)
        mapped = sum(1 for t in context.task_inputs if t.allowed_documents)
        duration = job.finish_step("map_task_sources", f"{mapped}/{len(context.task_inputs)} task có nguồn")
        log_step_event(
            event="step_done",
            step="map_task_sources",
            correlation_id=job.correlation_id,
            duration_ms=duration,
            task_count=len(context.task_inputs),
        )

        project = await db.get(Project, context.project_id)
        project_key = project.key if project else str(context.project_id)

        # Cấp plan cho kỹ sư thì LUÔN sao chép bản chuẩn của dự án (SoT §12: kỹ sư cùng dự án nhận
        # nội dung giống nhau) — không bao giờ gọi AI ở luồng này. Sinh/tạo lại chính bản chuẩn thì
        # `reference_plan_id = None` để rơi vào nhánh gọi AI.
        reference_plan_id: int | None = None
        if context.membership is not None:
            reference_plan = await onboarding_plan_service.find_reference_plan(db, context.project_id)
            if reference_plan is None:
                raise HTTPException(
                    status_code=422,
                    detail="Dự án chưa có lộ trình chuẩn — vào mục Onboarding Plan tạo lộ trình "
                    "chuẩn trước, rồi mới cấp plan cho kỹ sư",
                )
            reference_plan_id = reference_plan.plan_id

        job.start_step("generate_content")
        generation_total = len(context.task_inputs)
        generation_documents = len(context.project_documents) + len(context.policy_documents)
        job.update_step_progress(
            "generate_content",
            done=0,
            total=generation_total,
            document_count=generation_documents,
            detail=(
                f"Đang phân tích {generation_documents} tài liệu để chuẩn bị nội dung cho "
                f"{generation_total} task"
            ),
        )
        # Báo tiến độ ngay trong bước 5: bước này chiếm gần hết thời gian sinh plan, để FE chỉ thấy
        # spinner cho tới lúc xong thì không phân biệt được "đang chạy" với "treo".
        # `tag_project_trace` gắn tag `project:<id>` cho MỌI span/generation tạo trong bước này — đây
        # là bước DUY NHẤT gọi AI thật (LlmUsage) nên chỉ cần tag đúng phạm vi này là đủ để
        # `get_project_ai_cost_usd()` (dashboard PM) lọc đúng cost theo dự án qua Langfuse.
        with tag_project_trace(context.project_id):
            contents = await _step_generate_content(
                db,
                context,
                project_key,
                reference_plan_id,
                lambda done, total: job.update_step_detail(
                    "generate_content", f"{done}/{total} task đã sinh xong"
                ),
            )
        ai_count = sum(1 for c in contents.values() if c.generated_by_ai)
        cloned_count = sum(1 for c in contents.values() if c.cloned)
        if cloned_count:
            detail = f"Sao chép nội dung từ Plan #{reference_plan_id} đã có (không gọi AI)"
        elif ai_count:
            detail = f"{ai_count}/{len(contents)} task do AI viết"
        else:
            detail = "dùng nội dung khung (baseline)"
        duration = job.finish_step("generate_content", detail)
        log_step_event(
            event="step_done",
            step="generate_content",
            correlation_id=job.correlation_id,
            duration_ms=duration,
            task_count=len(contents),
            ai_generated_count=ai_count,
            cloned_from_plan_id=reference_plan_id,
        )

        job.start_step("validate_and_persist")
        plan, warnings = await _step_validate_and_persist(
            db, context, contents, existing_plan_id, schedule_start_at
        )
        source_count = sum(len(c.sources) for c in contents.values())
        duration = job.finish_step(
            "validate_and_persist", f"Đã lưu {len(contents)} task, {source_count} trích dẫn nguồn"
        )
        log_step_event(
            event="step_done",
            step="validate_and_persist",
            correlation_id=job.correlation_id,
            duration_ms=duration,
            plan_id=plan.plan_id,
            source_count=source_count,
            warning_count=len(warnings),
        )

        job.plan_id = plan.plan_id
        job.warnings = warnings
        job.status = JobStatus.DONE
        job.total_duration_ms = int((time.perf_counter() - started) * 1000)
        log_step_event(
            event="generation_done",
            correlation_id=job.correlation_id,
            job_id=job.job_id,
            plan_id=plan.plan_id,
            duration_ms=job.total_duration_ms,
            warning_count=len(warnings),
        )

    except HTTPException as exc:
        await db.rollback()
        _fail(job, str(exc.detail), started, error_type="HTTPException")
    except Exception as exc:  # noqa: BLE001 - job chạy nền, phải nuốt để ghi được lỗi cho FE
        await db.rollback()
        _fail(job, f"Lỗi không mong đợi: {type(exc).__name__}", started, error_type=type(exc).__name__)
    finally:
        # Job nền kết thúc là hết người kích hoạt việc gửi batch -> phải flush thủ công, nếu không
        # trace chạy đúng nhưng không bao giờ xuất hiện trên dashboard.
        flush_traces()


def _fail(job: GenerationJob, message: str, started: float, *, error_type: str) -> None:
    for state in job.steps:
        if state.status.value == "RUNNING":
            job.fail_step(state.key, message)
            break
    job.status = JobStatus.FAILED
    job.error = message
    job.total_duration_ms = int((time.perf_counter() - started) * 1000)
    log_step_event(
        event="generation_failed",
        correlation_id=job.correlation_id,
        job_id=job.job_id,
        duration_ms=job.total_duration_ms,
        error_type=error_type,
    )
