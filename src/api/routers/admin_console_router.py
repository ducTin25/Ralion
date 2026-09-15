from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import (
    get_embedder,
    get_policy_ingestor,
    require_admin,
    require_hr_or_admin,
)
from src.config import get_settings
from src.dto.admin_console_dto import (
    AccessGrantActionDTO,
    AccessGrantCreateDTO,
    AccessGrantDTO,
    AccessGrantListDTO,
    AccessQueueSummaryDTO,
    AccessResourceOptionDTO,
    AdminMembershipBulkCreateDTO,
    AdminMembershipBulkResultDTO,
    AdminMembershipCreateDTO,
    AdminMembershipListDTO,
    AdminMembershipSummaryDTO,
    AdminMembershipUpdateDTO,
    AdminOverviewDTO,
    AdminPrimaryPmDTO,
    AdminPriorityDTO,
    AdminProjectCreateDTO,
    AdminProjectDetailDTO,
    AdminProjectListDTO,
    AdminProjectStatusDTO,
    AdminProjectUpdateDTO,
    AdminRiskListDTO,
    AdminUnassignedListDTO,
    AdminUserCreateDTO,
    AdminUserDetailDTO,
    AdminUserListDTO,
    AdminUserListItemDTO,
    AdminUserPasswordDTO,
    AdminUserStatusDTO,
    AdminUserUpdateDTO,
    MembershipEligibilityDTO,
    MembershipOffboardingPreviewDTO,
    PageMetaDTO,
    PolicyContentDTO,
    PolicyCoverageDetailDTO,
    PolicyCoverageListDTO,
    PolicyDetailDTO,
    PolicyInspectResultDTO,
    PolicyListDTO,
    PolicyRequireAckDTO,
    UserDeactivationPreviewDTO,
    UserImportCreatedDTO,
    UserImportPreviewDTO,
    UserImportResultDTO,
    UserImportRowDTO,
)
from src.dto.response.onboarding_template_response_dto import OnboardingTemplateResponseDTO
from src.model.enums import (
    AccessGrantStatus,
    MembershipStatus,
    PolicyCategory,
    ProjectRole,
    ProjectStatus,
    UserStatus,
)
from src.model.session import get_db
from src.model.user import User
from src.services import (
    access_grant_service,
    admin_console_service,
    document_conversion_service,
    hr_policy_service,
    onboarding_template_service,
    policy_acknowledgement_service,
    user_import_service,
)

router = APIRouter(prefix="/console", tags=["admin hr console"])


def page_meta(page: int, page_size: int, total: int) -> PageMetaDTO:
    return PageMetaDTO(page=page, page_size=page_size, total=total)


@router.get("/admin/master-template", response_model=OnboardingTemplateResponseDTO)
async def admin_master_template(
    _: Annotated[User, Depends(require_admin)], db: Annotated[AsyncSession, Depends(get_db)]
) -> OnboardingTemplateResponseDTO:
    """Global Master Template áp dụng cho mọi project — mỗi project mới tự fork từ đây (SoT §11.16).
    Khác `GET /onboarding-templates/pm/by-project/{project_id}` (PM xem template CỦA 1 project),
    endpoint này trả về đúng bản GLOBAL, chỉ Admin xem/sửa được."""
    template = await onboarding_template_service.get_global_template(db)
    if template is None:
        raise HTTPException(status_code=404, detail="Chưa có Global Master Template nào")
    return OnboardingTemplateResponseDTO.from_entity(template)


@router.get("/admin/overview", response_model=AdminOverviewDTO)
async def admin_overview(
    _: Annotated[User, Depends(require_admin)], db: Annotated[AsyncSession, Depends(get_db)]
) -> AdminOverviewDTO:
    return AdminOverviewDTO(**(await admin_console_service.overview(db)))


@router.get("/admin/priority-users", response_model=AdminPriorityDTO)
async def admin_priority_users(
    _: Annotated[User, Depends(require_admin)], db: Annotated[AsyncSession, Depends(get_db)]
) -> AdminPriorityDTO:
    return AdminPriorityDTO(items=await admin_console_service.priority_users(db))


@router.get("/admin/risk-items", response_model=AdminRiskListDTO)
async def admin_risk_items(
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> AdminRiskListDTO:
    items, total = await admin_console_service.risk_items(db, limit=limit)
    return AdminRiskListDTO(items=items, total=total)


@router.get("/admin/unassigned-users", response_model=AdminUnassignedListDTO)
async def admin_unassigned_users(
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 5,
    query: str | None = None,
) -> AdminUnassignedListDTO:
    items, total = await admin_console_service.list_unassigned_users(
        db, page=page, page_size=page_size, query=query
    )
    return AdminUnassignedListDTO(items=items, meta=page_meta(page, page_size, total))


@router.get("/admin/users", response_model=AdminUserListDTO)
async def admin_users(
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 6,
    query: str | None = None,
    system_role: str | None = Query(default=None, pattern="^(ADMIN|HR|NONE)$"),
    account_status: UserStatus | None = None,
    start_status: str | None = Query(default=None, pattern="^(UPCOMING|STARTED)$"),
    # PENDING = mật khẩu hiện tại do admin đặt, người dùng chưa tự đổi. Đây là nhóm tài
    # khoản rủi ro nhất nên phải lọc ra được.
    password_state: str | None = Query(default=None, pattern="^(PENDING|SET)$"),
) -> AdminUserListDTO:
    items, total = await admin_console_service.list_users(
        db,
        page=page,
        page_size=page_size,
        query=query,
        system_role=system_role,
        account_status=account_status,
        start_status=start_status,
        password_state=password_state,
    )
    return AdminUserListDTO(items=items, meta=page_meta(page, page_size, total))


@router.post("/admin/users", response_model=AdminUserListItemDTO, status_code=201)
async def admin_create_user(
    dto: AdminUserCreateDTO,
    actor: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserListItemDTO:
    return await admin_console_service.create_user(db, actor, dto)


@router.post("/admin/users/import/preview", response_model=UserImportPreviewDTO)
async def admin_preview_user_import(
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: Annotated[UploadFile, File()],
) -> UserImportPreviewDTO:
    """Đọc file và trả bảng xem trước. KHÔNG ghi gì vào database.

    Có bước này vì import là thao tác hàng loạt không hoàn tác được: tạo nhầm 20 tài
    khoản thì phải xoá tay 20 lần.
    """
    preview = await user_import_service.annotate_existing_emails(
        db, user_import_service.parse_csv(await file.read())
    )
    rows = [UserImportRowDTO(**vars(row)) for row in preview.rows]
    return UserImportPreviewDTO(
        rows=rows,
        valid_count=sum(row.error is None for row in rows),
        invalid_count=sum(row.error is not None for row in rows),
    )


@router.post("/admin/users/import", response_model=UserImportResultDTO, status_code=201)
async def admin_import_users(
    actor: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: Annotated[UploadFile, File()],
) -> UserImportResultDTO:
    """Tạo tài khoản thật. Dòng hỏng bị bỏ qua kèm lý do, dòng tốt vẫn được tạo."""
    created, skipped = await user_import_service.import_users(db, actor, await file.read())
    return UserImportResultDTO(
        created=[
            UserImportCreatedDTO(
                user_id=user.user_id,
                display_name=user.display_name,
                email=user.email,
                temporary_password=password,
            )
            for user, password in created
        ],
        skipped=[UserImportRowDTO(**vars(row)) for row in skipped],
    )


@router.get("/admin/users/{user_id}", response_model=AdminUserDetailDTO)
async def admin_user_detail(
    user_id: int,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserDetailDTO:
    return await admin_console_service.get_user_detail(db, user_id)


@router.patch("/admin/users/{user_id}", response_model=AdminUserDetailDTO)
async def admin_update_user(
    user_id: int,
    dto: AdminUserUpdateDTO,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserDetailDTO:
    return await admin_console_service.update_user(db, user_id, dto)


@router.patch("/admin/users/{user_id}/password", response_model=AdminUserListItemDTO)
async def admin_reset_user_password(
    user_id: int,
    body: AdminUserPasswordDTO,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserListItemDTO:
    return await admin_console_service.reset_user_password(db, user_id, body.new_password)


@router.patch("/admin/users/{user_id}/status", response_model=AdminUserListItemDTO)
async def admin_change_user_status(
    user_id: int,
    body: AdminUserStatusDTO,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserListItemDTO:
    return await admin_console_service.change_user_status(db, user_id, body.status)


@router.get("/admin/projects", response_model=AdminProjectListDTO)
async def admin_projects(
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 6,
    project_status: ProjectStatus | None = None,
    query: str | None = None,
    # MISSING = dự án chưa có PM phụ trách. Đây là vấn đề nghiêm trọng nhất của một dự
    # án và đang được đếm ở trang tổng quan, nên phải lọc ra được.
    pm_state: str | None = Query(default=None, pattern="^(MISSING|ASSIGNED)$"),
) -> AdminProjectListDTO:
    items, total = await admin_console_service.list_projects(
        db,
        page=page,
        page_size=page_size,
        account_status=project_status,
        query=query,
        pm_state=pm_state,
    )
    return AdminProjectListDTO(items=items, meta=page_meta(page, page_size, total))


@router.get("/admin/projects/{project_id}", response_model=AdminProjectDetailDTO)
async def admin_project_detail(
    project_id: int,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminProjectDetailDTO:
    return await admin_console_service.get_project_detail(db, project_id)


@router.patch("/admin/projects/{project_id}", response_model=AdminProjectDetailDTO)
async def admin_update_project(
    project_id: int,
    body: AdminProjectUpdateDTO,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminProjectDetailDTO:
    """Sửa tên và mã dự án.

    Trước đây không có endpoint nào làm việc này: gõ sai tên lúc tạo là sai vĩnh viễn.
    """
    return await admin_console_service.update_project(db, project_id, body)


@router.patch("/admin/projects/{project_id}/primary-pm", response_model=AdminProjectDetailDTO)
async def admin_set_primary_pm(
    project_id: int,
    body: AdminPrimaryPmDTO,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminProjectDetailDTO:
    return await admin_console_service.set_primary_pm(db, project_id, body.membership_id)


@router.post("/admin/projects", status_code=201)
async def admin_create_project(
    dto: AdminProjectCreateDTO,
    actor: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await admin_console_service.create_project(db, actor, dto)


@router.patch("/admin/projects/{project_id}/status", response_model=AdminProjectDetailDTO)
async def admin_change_project_status(
    project_id: int,
    body: AdminProjectStatusDTO,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminProjectDetailDTO:
    return await admin_console_service.change_project_status(
        db, project_id, body.status, body.deactivate_memberships
    )


@router.get("/admin/memberships", response_model=AdminMembershipListDTO)
async def admin_memberships(
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 6,
    query: str | None = None,
    membership_status: MembershipStatus | None = None,
    project_id: int | None = None,
    project_role: ProjectRole | None = None,
    state: str | None = Query(default=None, pattern="^(ACTIVE|SUSPENDED|BLOCKED_USER|BLOCKED_PROJECT)$"),
) -> AdminMembershipListDTO:
    items, total = await admin_console_service.list_memberships(
        db,
        page=page,
        page_size=page_size,
        query=query,
        membership_status=membership_status,
        project_id=project_id,
        project_role=project_role,
        state=state,
    )
    return AdminMembershipListDTO(items=items, meta=page_meta(page, page_size, total))


@router.get("/admin/memberships/summary", response_model=AdminMembershipSummaryDTO)
async def admin_membership_summary(
    _: Annotated[User, Depends(require_admin)], db: Annotated[AsyncSession, Depends(get_db)]
) -> AdminMembershipSummaryDTO:
    return AdminMembershipSummaryDTO(**(await admin_console_service.membership_summary(db)))


@router.post("/admin/memberships/bulk", response_model=AdminMembershipBulkResultDTO, status_code=201)
async def admin_create_memberships_bulk(
    dto: AdminMembershipBulkCreateDTO,
    actor: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminMembershipBulkResultDTO:
    return await admin_console_service.create_memberships_bulk(db, actor, dto)


@router.get("/admin/memberships/eligibility", response_model=MembershipEligibilityDTO)
async def admin_membership_eligibility(
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    project_id: int | None = None,
) -> MembershipEligibilityDTO:
    return await admin_console_service.membership_eligibility(db, project_id)


@router.post("/admin/memberships", status_code=201)
async def admin_create_membership(
    dto: AdminMembershipCreateDTO,
    actor: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await admin_console_service.create_membership(db, actor, dto)


@router.patch("/admin/memberships/{membership_id}")
async def admin_update_membership(
    membership_id: int,
    dto: AdminMembershipUpdateDTO,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await admin_console_service.update_membership(db, membership_id, dto.project_role, dto.status)


# ------------------------------------------------------------- Hàng đợi cấp quyền (A)
#
# Đường dẫn tĩnh khai TRƯỚC đường dẫn có tham số: `/admin/access-grants/summary` mà nằm
# sau `/admin/access-grants/{grant_id}` thì "summary" sẽ bị nuốt làm grant_id và trả 422.
# Đây đúng là lỗi đã gặp một lần với `/hr/policies/coverage`.


@router.get("/admin/access-grants/summary", response_model=AccessQueueSummaryDTO)
async def admin_access_queue_summary(
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccessQueueSummaryDTO:
    return AccessQueueSummaryDTO(**await access_grant_service.queue_summary(db))


@router.get("/admin/access-grants/resource-types", response_model=list[AccessResourceOptionDTO])
async def admin_access_resource_types(
    _: Annotated[User, Depends(require_admin)],
) -> list[AccessResourceOptionDTO]:
    """Danh sách loại tài nguyên kèm nhãn tiếng Việt.

    Server là nguồn sự thật cho cặp enum–nhãn: hardcode lại ở frontend là cách chắc chắn
    để một ngày nào đó thêm loại mới ở backend mà giao diện không hiện.
    """
    return [
        AccessResourceOptionDTO(value=value, label=label)
        for value, label in access_grant_service.RESOURCE_LABELS.items()
    ]


@router.get("/admin/access-grants", response_model=AccessGrantListDTO)
async def admin_access_grants(
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Annotated[AccessGrantStatus | None, Query()] = AccessGrantStatus.REQUESTED,
    project_id: Annotated[int | None, Query()] = None,
) -> AccessGrantListDTO:
    """Hàng đợi cấp quyền. Mặc định chỉ yêu cầu chưa xử lý, cũ nhất lên trước."""
    return AccessGrantListDTO(
        items=await access_grant_service.list_queue(db, status=status, project_id=project_id)
    )


@router.post("/admin/access-grants", response_model=AccessGrantDTO, status_code=201)
async def admin_add_access_grant(
    body: AccessGrantCreateDTO,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccessGrantDTO:
    """Thêm một quyền ngoài bộ chuẩn (VPN, hệ thống nội bộ khác...)."""
    grant = await access_grant_service.add_grant(
        db, body.membership_id, body.resource_type, resource_note=body.resource_note
    )
    rows = await access_grant_service.list_for_membership(db, grant.membership_id)
    return AccessGrantDTO(**next(row for row in rows if row["grant_id"] == grant.grant_id))


@router.patch("/admin/access-grants/{grant_id}/grant", response_model=AccessGrantDTO)
async def admin_grant_access(
    grant_id: int,
    body: AccessGrantActionDTO,
    actor: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccessGrantDTO:
    """Xác nhận đã cấp quyền thật ở hệ thống bên ngoài.

    Hệ thống KHÔNG tự gọi API GitHub/Jira để cấp quyền — nó ghi nhận việc admin đã làm
    bằng tay. Tự động hoá phần đó là một tích hợp riêng, không thuộc phạm vi BO-06.
    """
    grant = await access_grant_service.grant_access(
        db, actor, grant_id, resource_note=body.resource_note
    )
    rows = await access_grant_service.list_for_membership(db, grant.membership_id)
    return AccessGrantDTO(**next(row for row in rows if row["grant_id"] == grant_id))


@router.patch("/admin/access-grants/{grant_id}/revoke", response_model=AccessGrantDTO)
async def admin_revoke_access(
    grant_id: int,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccessGrantDTO:
    grant = await access_grant_service.revoke_access(db, grant_id)
    rows = await access_grant_service.list_for_membership(db, grant.membership_id)
    return AccessGrantDTO(**next(row for row in rows if row["grant_id"] == grant_id))


@router.get("/admin/memberships/{membership_id}/access-grants", response_model=AccessGrantListDTO)
async def admin_membership_access_grants(
    membership_id: int,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccessGrantListDTO:
    return AccessGrantListDTO(
        items=await access_grant_service.list_for_membership(db, membership_id)
    )


# --------------------------------------------------- Thu hồi khi rời dự án / nghỉ (D)


@router.get(
    "/admin/users/{user_id}/deactivation-preview", response_model=UserDeactivationPreviewDTO
)
async def admin_deactivation_preview(
    user_id: int,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserDeactivationPreviewDTO:
    """Hậu quả của việc khoá tài khoản, xem TRƯỚC khi bấm.

    GET và không có tác dụng phụ: gọi bao nhiêu lần cũng không đổi gì trong DB.
    """
    return UserDeactivationPreviewDTO(**await access_grant_service.deactivation_preview(db, user_id))


@router.get(
    "/admin/memberships/{membership_id}/offboarding-preview",
    response_model=MembershipOffboardingPreviewDTO,
)
async def admin_membership_offboarding_preview(
    membership_id: int,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MembershipOffboardingPreviewDTO:
    return MembershipOffboardingPreviewDTO(
        **await access_grant_service.membership_offboarding_preview(db, membership_id)
    )


@router.post(
    "/admin/memberships/{membership_id}/revoke-access", response_model=AccessGrantListDTO
)
async def admin_revoke_membership_access(
    membership_id: int,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccessGrantListDTO:
    """Tick toàn bộ checklist thu hồi một lượt.

    Cố ý KHÔNG chạy tự động khi ngừng membership: hệ thống không gỡ được quyền thật trên
    GitHub/Jira/VPN, nên tự đánh dấu REVOKED sẽ tạo ra một danh sách sạch sẽ nói dối
    rằng mọi thứ đã được gỡ. Admin phải chủ động bấm, sau khi đã gỡ tay.
    """
    await access_grant_service.revoke_all_for_membership(db, membership_id)
    return AccessGrantListDTO(
        items=await access_grant_service.list_for_membership(db, membership_id)
    )


@router.get("/hr/policies", response_model=PolicyListDTO)
async def hr_policies(
    _: Annotated[User, Depends(require_hr_or_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 6,
    query: str | None = None,
) -> PolicyListDTO:
    items, total = await admin_console_service.list_policies(db, page=page, page_size=page_size, query=query)
    return PolicyListDTO(items=items, meta=page_meta(page, page_size, total))


@router.get("/hr/policies/coverage", response_model=PolicyCoverageListDTO)
async def hr_policy_coverage(
    _: Annotated[User, Depends(require_hr_or_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PolicyCoverageListDTO:
    """Tỷ lệ xác nhận của từng chính sách bắt buộc đọc."""
    items = await policy_acknowledgement_service.coverage_summary(db)
    return PolicyCoverageListDTO(items=items)


@router.get("/hr/policies/{document_id}", response_model=PolicyDetailDTO)
async def hr_policy_detail(
    document_id: int,
    _: Annotated[User, Depends(require_hr_or_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PolicyDetailDTO:
    return await admin_console_service.get_policy_detail(db, document_id)


@router.post("/hr/policies/inspect", response_model=PolicyInspectResultDTO)
async def hr_inspect_policy_file(
    _: Annotated[User, Depends(require_hr_or_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: Annotated[UploadFile, File()],
) -> PolicyInspectResultDTO:
    """Bước 1: đọc file, trả metadata gợi ý cho HR xác nhận. KHÔNG ghi gì vào database.

    Tách thành bước riêng để HR sửa được mã tài liệu / danh mục / số phiên bản trước khi
    tốn công chunk và embedding.
    """
    settings = get_settings()
    content = await file.read()
    converted = await hr_policy_service.inspect_upload(
        content, file.filename or "", max_mb=settings.max_policy_upload_mb
    )

    existing = None
    if converted.detected_document_code:
        existing = await hr_policy_service.find_existing_document(
            db, converted.detected_document_code
        )

    return PolicyInspectResultDTO(
        detected_title=converted.detected_title,
        detected_document_code=converted.detected_document_code,
        detected_version=converted.detected_version,
        detected_effective_date=converted.detected_effective_date,
        markdown_preview=document_conversion_service.preview(converted.markdown),
        warnings=converted.warnings,
        existing_document_id=existing.document_id if existing else None,
        existing_document_title=existing.title if existing else None,
    )


@router.post("/hr/policies/upload", response_model=PolicyDetailDTO, status_code=201)
async def hr_upload_policy(
    actor: Annotated[User, Depends(require_hr_or_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    embedder: Annotated[object, Depends(get_embedder)],
    ingest: Annotated[object, Depends(get_policy_ingestor)],
    file: Annotated[UploadFile, File()],
    document_code: Annotated[str, Form()],
    title: Annotated[str, Form()],
    policy_category: Annotated[PolicyCategory, Form()],
    version: Annotated[str | None, Form()] = None,
    effective_date: Annotated[date | None, Form()] = None,
) -> PolicyDetailDTO:
    """Bước 2: ingest thật.

    Tạo mới hay thêm phiên bản đều dùng chung endpoint này — `ingest_policy_document()`
    của TV3 tự phân biệt dựa trên `document_code`.
    """
    settings = get_settings()
    content = await file.read()
    return await hr_policy_service.upload_policy(
        db,
        actor,
        content=content,
        filename=file.filename or "",
        document_code=document_code,
        title=title,
        policy_category=policy_category,
        version=version,
        effective_date=effective_date,
        embedder=embedder,
        ingest=ingest,
        max_mb=settings.max_policy_upload_mb,
    )


@router.patch("/hr/policies/{document_id}/archive", response_model=PolicyDetailDTO)
async def hr_archive_policy(
    document_id: int,
    _: Annotated[User, Depends(require_hr_or_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PolicyDetailDTO:
    return await admin_console_service.archive_policy(db, document_id)


@router.patch("/hr/policies/{document_id}/restore", response_model=PolicyDetailDTO)
async def hr_restore_policy(
    document_id: int,
    _: Annotated[User, Depends(require_hr_or_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PolicyDetailDTO:
    return await admin_console_service.restore_policy(db, document_id)


# ---------------------------------------------------------------- xác nhận đã đọc


@router.get("/hr/policies/{document_id}/coverage", response_model=PolicyCoverageDetailDTO)
async def hr_policy_coverage_detail(
    document_id: int,
    _: Annotated[User, Depends(require_hr_or_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PolicyCoverageDetailDTO:
    """Ai đã xác nhận và ai chưa. Danh sách thứ hai mới là thứ HR cần để đi nhắc."""
    return await policy_acknowledgement_service.coverage_detail(db, document_id)


@router.patch(
    "/hr/policies/{document_id}/acknowledgement-required",
    response_model=PolicyCoverageDetailDTO,
)
async def hr_set_acknowledgement_required(
    document_id: int,
    dto: PolicyRequireAckDTO,
    _: Annotated[User, Depends(require_hr_or_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PolicyCoverageDetailDTO:
    return await policy_acknowledgement_service.set_requires_acknowledgement(
        db, document_id, required=dto.required
    )

@router.get("/hr/policies/{document_id}/content", response_model=PolicyContentDTO)
async def hr_policy_content(
    document_id: int,
    _: Annotated[User, Depends(require_hr_or_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PolicyContentDTO:
    """Nội dung đã chuyển đổi, để HR xem ngay trong ứng dụng.

    Dùng chung service với endpoint phía kỹ sư: HR và nhân viên phải nhìn thấy đúng một
    nội dung, nếu không thì tỷ lệ xác nhận nói về một tài liệu khác với thứ HR đã duyệt.
    """
    return await policy_acknowledgement_service.get_policy_content_for_hr(db, document_id)
