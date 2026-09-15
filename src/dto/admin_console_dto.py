from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from src.model.enums import (
    AccessGrantStatus,
    AccessResourceType,
    DocumentStatus,
    MembershipStatus,
    PolicyCategory,
    ProjectRole,
    ProjectStatus,
    SyncStatus,
    UserRole,
    UserStatus,
    VersionStatus,
)


class PageMetaDTO(BaseModel):
    page: int
    page_size: int
    total: int


class AdminUserListItemDTO(BaseModel):
    user_id: int
    display_name: str
    email: str
    system_role: UserRole | None
    status: UserStatus
    project_count: int
    created_at: datetime
    created_by_name: str | None
    # Ngày bắt đầu làm việc; None với tài khoản tạo trước khi có cột này.
    start_date: date | None = None
    # True khi mật khẩu hiện tại do admin đặt và người dùng chưa tự đổi.
    must_change_password: bool = False
    # Số quyền truy cập đang chờ admin cấp, tính trên các membership còn hoạt động.
    pending_access_count: int = 0



class AdminUserListDTO(BaseModel):
    items: list[AdminUserListItemDTO]
    meta: PageMetaDTO


class AdminUserMembershipDTO(BaseModel):
    """One project a user belongs to, as shown in the user detail drawer."""

    membership_id: int
    project_id: int
    project_name: str
    project_key: str
    project_role: ProjectRole
    status: MembershipStatus
    project_status: ProjectStatus
    joined_at: datetime


class AdminUserDetailDTO(AdminUserListItemDTO):
    active_project_count: int
    memberships: list[AdminUserMembershipDTO]


class AdminUserCreateDTO(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    temporary_password: str = Field(min_length=8, max_length=256)
    system_role: UserRole | None = None
    status: UserStatus = UserStatus.ACTIVE
    start_date: date | None = None



class UserImportRowDTO(BaseModel):
    """Một dòng CSV sau khi kiểm tra, dùng cho màn hình xem trước."""

    line: int
    display_name: str
    email: str
    system_role: UserRole | None = None
    start_date: date | None = None
    # None nghĩa là dòng hợp lệ; khác None là lý do sẽ bị bỏ qua.
    error: str | None = None


class UserImportPreviewDTO(BaseModel):
    rows: list[UserImportRowDTO]
    valid_count: int
    invalid_count: int


class UserImportCreatedDTO(BaseModel):
    user_id: int
    display_name: str
    email: str
    # Chỉ trả về đúng một lần, không lưu ở đâu. Admin phải gửi cho từng người ngay.
    temporary_password: str


class UserImportResultDTO(BaseModel):
    created: list[UserImportCreatedDTO]
    skipped: list[UserImportRowDTO]


class AdminProjectListItemDTO(BaseModel):
    project_id: int
    name: str
    key: str
    status: ProjectStatus
    primary_pm_name: str | None
    member_count: int
    created_at: datetime
    created_by_name: str | None
    # member_count counts every membership ever created; active_member_count is the
    # number that can actually open the workspace today.
    active_member_count: int = 0
    # Số quyền truy cập đang chờ cấp trong dự án này. Quyền cấp theo dự án, nên đây là
    # góc nhìn tự nhiên hơn cả bảng người dùng.
    pending_access_count: int = 0


class AdminProjectListDTO(BaseModel):
    items: list[AdminProjectListItemDTO]
    meta: PageMetaDTO


class AdminProjectMemberDTO(BaseModel):
    membership_id: int
    user_id: int
    display_name: str
    email: str
    project_role: ProjectRole
    status: MembershipStatus
    joined_at: datetime
    is_primary_pm: bool


class AdminProjectDetailDTO(AdminProjectListItemDTO):
    # Toạ độ GitHub của dự án. `pending/<key>` là giá trị giả gán lúc tạo project — giao
    # diện phải coi đó là "chưa cấu hình", không phải tên repo thật.
    github_repo: str | None = None
    default_branch: str | None = None
    primary_pm_email: str | None
    primary_pm_membership_id: int | None
    active_pm_count: int
    sync_status: SyncStatus
    last_synced_at: datetime | None
    members: list[AdminProjectMemberDTO]


class AdminPrimaryPmDTO(BaseModel):
    """Point a project at the membership that owns it; null clears the assignment."""

    membership_id: int | None = None


class AdminProjectCreateDTO(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    key: str = Field(min_length=2, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")


class AdminProjectUpdateDTO(BaseModel):
    """Sửa hồ sơ dự án. Trường bỏ trống nghĩa là giữ nguyên.

    Không có cờ `clear_*` như bên tài khoản vì cả hai trường đều bắt buộc — dự án không
    thể không có tên hoặc không có mã.
    """

    name: str | None = Field(default=None, min_length=1, max_length=200)
    key: str | None = Field(
        default=None, min_length=2, max_length=80, pattern=r"^[A-Za-z0-9_-]+$"
    )


class AdminProjectStatusDTO(BaseModel):
    status: ProjectStatus
    # Archiving a project normally leaves its memberships ACTIVE, which the overview
    # then reports as stale access. Opt in to closing them out in the same request.
    deactivate_memberships: bool = False


class AdminUserStatusDTO(BaseModel):
    status: UserStatus


class AdminUserUpdateDTO(BaseModel):
    """Sửa hồ sơ tài khoản. Trường bỏ trống nghĩa là giữ nguyên.

    `system_role` dùng kiểu bọc để phân biệt "không đổi" (không gửi trường) với
    "gỡ quyền hệ thống" (gửi null) — hai ý nghĩa khác nhau mà `None` không tách được.
    """

    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: str | None = Field(default=None, min_length=3, max_length=320)
    system_role: UserRole | None = None
    clear_system_role: bool = False
    start_date: date | None = None
    # Cùng lý do với `clear_system_role`: None nghĩa là "không đổi", nên cần cờ riêng
    # để xoá ngày đã đặt nhầm.
    clear_start_date: bool = False


class AdminUserPasswordDTO(BaseModel):
    new_password: str = Field(min_length=8, max_length=256)


class ChangePasswordDTO(BaseModel):
    current_password: str = Field(min_length=8, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


AccessState = Literal["ACTIVE", "SUSPENDED", "BLOCKED_USER", "BLOCKED_PROJECT"]


class AdminMembershipListItemDTO(BaseModel):
    membership_id: int
    user_id: int
    user_name: str
    user_email: str
    project_id: int
    project_name: str
    project_key: str
    project_role: ProjectRole
    status: MembershipStatus
    assigned_by_name: str | None
    joined_at: datetime
    # Context that explains whether the membership actually grants workspace access.
    user_system_role: UserRole | None = None
    user_status: UserStatus = UserStatus.ACTIVE
    # Membership là đơn vị gắn quyền truy cập, nên đây là chỗ tự nhiên nhất để đếm.
    granted_access_count: int = 0
    pending_access_count: int = 0
    project_status: ProjectStatus = ProjectStatus.ACTIVE
    is_primary_pm: bool = False
    access_state: AccessState = "ACTIVE"


class AdminMembershipListDTO(BaseModel):
    items: list[AdminMembershipListItemDTO]
    meta: PageMetaDTO


class AdminMembershipSummaryDTO(BaseModel):
    """Counts across every membership, independent of the current page or filters."""

    total: int
    active: int
    suspended: int
    blocked: int


class AdminMembershipCreateDTO(BaseModel):
    user_id: int
    project_id: int
    project_role: ProjectRole
    status: MembershipStatus = MembershipStatus.ACTIVE


class AdminMembershipBulkCreateDTO(BaseModel):
    project_id: int
    project_role: ProjectRole
    user_ids: list[int] = Field(min_length=1, max_length=100)


class AdminMembershipSkippedDTO(BaseModel):
    user_id: int
    display_name: str | None
    reason: str


class AdminMembershipBulkResultDTO(BaseModel):
    created: list[AdminMembershipListItemDTO]
    skipped: list[AdminMembershipSkippedDTO]


class AdminMembershipUpdateDTO(BaseModel):
    project_role: ProjectRole | None = None
    status: MembershipStatus | None = None


class PolicyListItemDTO(BaseModel):
    document_id: int
    title: str
    policy_category: PolicyCategory
    source_key: str | None = None
    # Nhãn phiên bản do người soạn chính sách đặt (ví dụ "3.2"), KHÔNG phải số đếm
    # của hệ thống. Số đếm nội bộ nằm ở revision_no và mới là thứ dùng để sắp xếp.
    version_no: str | None
    revision_no: int | None = None
    effective_date: date | None = None
    version_status: VersionStatus | None
    created_by_name: str | None
    status: str
    created_at: datetime
    # Có bắt người dùng xác nhận đã đọc hay không. Trả kèm ở đây để HR bật/tắt được
    # ngay trong thư viện — nếu chỉ có ở màn hình tỷ lệ xác nhận thì không có đường
    # bật lần đầu, vì màn hình đó chỉ liệt kê tài liệu đã bật cờ.
    requires_acknowledgement: bool = False


class PolicyListDTO(BaseModel):
    items: list[PolicyListItemDTO]
    meta: PageMetaDTO


class PolicyDetailDTO(PolicyListItemDTO):
    source_url: str
    summary: str | None = None


class PolicyInspectResultDTO(BaseModel):
    """Kết quả đọc file trước khi ingest — phục vụ màn hình HR review."""

    detected_title: str | None
    detected_document_code: str | None
    detected_version: str | None
    detected_effective_date: date | None
    markdown_preview: str
    warnings: list[str]
    # Khác None nghĩa là mã tài liệu đã tồn tại → đây sẽ là phiên bản mới, không phải tài liệu mới.
    existing_document_id: int | None = None
    existing_document_title: str | None = None


class PolicyArchiveDTO(BaseModel):
    status: DocumentStatus = DocumentStatus.ARCHIVED


# ---------------------------------------------------------------- xác nhận đã đọc


class AckUserDTO(BaseModel):
    user_id: int
    display_name: str
    email: str
    # None ở danh sách "chưa xác nhận".
    acknowledged_at: datetime | None = None


class PolicyCoverageDTO(BaseModel):
    document_id: int
    title: str
    policy_category: PolicyCategory
    version_no: str | None
    effective_date: date | None
    acknowledged_count: int
    required_count: int
    # Tính sẵn ở server để mọi màn hình hiển thị cùng một con số.
    coverage_percent: float


class PolicyCoverageListDTO(BaseModel):
    items: list[PolicyCoverageDTO]


class PolicyCoverageDetailDTO(BaseModel):
    document_id: int
    title: str
    version_no: str | None
    requires_acknowledgement: bool
    acknowledged: list[AckUserDTO]
    pending: list[AckUserDTO]


class PolicyRequireAckDTO(BaseModel):
    required: bool


class PendingPolicyDTO(BaseModel):
    document_id: int
    title: str
    policy_category: PolicyCategory
    version_no: str | None
    effective_date: date | None
    # True = người dùng đã xác nhận một phiên bản CŨ HƠN của chính tài liệu này.
    # UI cần phân biệt: người ta phản ứng khác nhau với "chính sách mới" và
    # "chính sách bạn đã đọc vừa thay đổi".
    is_new_version: bool


class PendingPolicyListDTO(BaseModel):
    items: list[PendingPolicyDTO]


class PolicyAckDTO(BaseModel):
    document_id: int
    version_id: int
    acknowledged_at: datetime
    # True khi người dùng đã xác nhận từ trước — API idempotent, không tạo bản ghi thứ hai.
    already_acknowledged: bool


class PolicyContentDTO(BaseModel):
    document_id: int
    title: str
    policy_category: PolicyCategory
    version_no: str
    effective_date: date | None
    content: str
    source_url: str


class AdminOverviewDTO(BaseModel):
    active_users: int
    active_projects: int
    active_memberships: int
    unassigned_active_users: int
    # Totals give each KPI a denominator so the console can show "x / y" context.
    total_users: int = 0
    total_projects: int = 0
    total_memberships: int = 0
    # Number of open items surfaced by /admin/risk-items.
    risk_count: int = 0


class AdminPriorityUserDTO(BaseModel):
    user_id: int
    display_name: str
    email: str
    created_at: datetime


class AdminPriorityDTO(BaseModel):
    items: list[AdminPriorityUserDTO]


RiskKind = Literal[
    "INACTIVE_USER_IN_PROJECT",
    "PROJECT_WITHOUT_PM",
    "ACTIVE_USER_NO_MEMBERSHIP",
    # Hai loại thuộc miền HR: tài liệu quá hạn rà soát và tài liệu không có ngày hiệu lực.
    "STALE_POLICY",
    "POLICY_MISSING_EFFECTIVE_DATE",
    # Yêu cầu cấp quyền để quá lâu — người mới đang ngồi chờ, không làm được gì.
    "PENDING_ACCESS_OVERDUE",
]


class AdminRiskItemDTO(BaseModel):
    """A single actionable inconsistency between accounts, projects and memberships."""

    risk_id: str
    kind: RiskKind
    severity: Literal["HIGH", "MEDIUM"]
    title: str
    message: str
    action_label: str
    user_id: int | None = None
    user_email: str | None = None
    membership_id: int | None = None
    project_id: int | None = None
    project_name: str | None = None
    project_key: str | None = None
    # Chỉ có ở risk thuộc miền chính sách, để UI điều hướng tới đúng tài liệu.
    document_id: int | None = None


class AdminRiskListDTO(BaseModel):
    items: list[AdminRiskItemDTO]
    total: int


class AdminUnassignedUserDTO(BaseModel):
    user_id: int
    display_name: str
    email: str
    system_role: UserRole | None
    created_at: datetime
    inactive_membership_count: int = 0


class AdminUnassignedListDTO(BaseModel):
    items: list[AdminUnassignedUserDTO]
    meta: PageMetaDTO


class MembershipEligibleUserDTO(BaseModel):
    user_id: int
    display_name: str
    email: str


class MembershipEligibleProjectDTO(BaseModel):
    project_id: int
    name: str
    key: str


class MembershipEligibilityDTO(BaseModel):
    users: list[MembershipEligibleUserDTO]
    projects: list[MembershipEligibleProjectDTO]


# --------------------------------------------------------------- Cấp quyền truy cập


class AccessGrantDTO(BaseModel):
    """Một quyền truy cập của một người trong một dự án."""

    grant_id: int
    membership_id: int
    resource_type: AccessResourceType
    # Nhãn tiếng Việt tính sẵn ở server: nếu để client tự map enum sang chữ thì màn hình
    # admin và màn hình kỹ sư sẽ trôi ra hai bộ nhãn khác nhau.
    resource_label: str
    resource_note: str | None
    status: AccessGrantStatus
    requested_at: datetime
    granted_at: datetime | None
    revoked_at: datetime | None
    granted_by_name: str | None
    user_id: int | None
    user_name: str | None
    user_email: str | None
    project_id: int | None
    project_name: str | None
    project_key: str | None
    # Repo GitHub của dự án, dùng để điền sẵn ghi chú khi cấp quyền REPOSITORY.
    # None khi dự án chưa cấu hình repo thật.
    project_repo: str | None = None
    project_role: ProjectRole | None
    membership_status: MembershipStatus | None
    is_overdue: bool
    # Chỉ có giá trị với yêu cầu chưa xử lý; quyền đã cấp thì thời gian chờ vô nghĩa.
    waiting_hours: float | None


class AccessGrantListDTO(BaseModel):
    items: list[AccessGrantDTO]


class AccessQueueSummaryDTO(BaseModel):
    pending: int
    overdue: int
    granted: int
    revoked: int


class AccessGrantActionDTO(BaseModel):
    resource_note: str | None = Field(default=None, max_length=500)


class AccessGrantCreateDTO(BaseModel):
    membership_id: int
    resource_type: AccessResourceType
    resource_note: str | None = Field(default=None, max_length=500)


class AccessResourceOptionDTO(BaseModel):
    value: AccessResourceType
    label: str


class OffboardingAccessDTO(BaseModel):
    grant_id: int
    resource_type: AccessResourceType
    resource_label: str
    resource_note: str | None
    project_name: str | None


class OffboardingProjectDTO(BaseModel):
    project_id: int
    project_name: str
    project_key: str


class OffboardingMembershipDTO(OffboardingProjectDTO):
    membership_id: int
    project_role: ProjectRole


class UserDeactivationPreviewDTO(BaseModel):
    """Hậu quả của việc khoá tài khoản, tính trước khi bấm.

    Tồn tại vì nút khoá tài khoản trước đây không hỏi gì cả — admin bấm xong không biết
    vừa cắt đứt những gì.
    """

    user_id: int
    display_name: str
    email: str
    is_primary_pm_of: list[OffboardingProjectDTO]
    memberships: list[OffboardingMembershipDTO]
    granted_access: list[OffboardingAccessDTO]
    will_revoke_sessions: bool


class MembershipOffboardingPreviewDTO(BaseModel):
    membership_id: int
    user_id: int
    display_name: str
    project_id: int
    project_name: str
    project_key: str
    is_primary_pm: bool
    granted_access: list[OffboardingAccessDTO]
