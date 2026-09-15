import enum


# ---- Identity & Access ----
class UserRole(enum.StrEnum):
    ADMIN = "ADMIN"
    HR = "HR"


class UserStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


# F5 personalization (presentation-layer only — see PERSONALIZE_CHATBOT_SPEC.md §1/§3).
class ResponseLength(enum.StrEnum):
    CONCISE = "CONCISE"
    STANDARD = "STANDARD"
    DETAILED = "DETAILED"


class ResponseTone(enum.StrEnum):
    NEUTRAL = "NEUTRAL"
    GUIDE = "GUIDE"
    MENTOR = "MENTOR"
    BUDDY = "BUDDY"


class ProjectRole(enum.StrEnum):
    PM = "PM"
    ENGINEER = "ENGINEER"


class ProjectStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class SyncStatus(enum.StrEnum):
    NOT_STARTED = "NOT_STARTED"
    SYNCING = "SYNCING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


# Per-project GitHub PAT (project_github_credentials.validation_status) — see
# github_credential_provider.py. UNVALIDATED never actually persists today (connect_github_repo
# validates synchronously before storing), kept only as the honest default for the column.
class GithubCredentialValidationStatus(enum.StrEnum):
    UNVALIDATED = "UNVALIDATED"
    VALID = "VALID"
    INVALID = "INVALID"


class MembershipStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class AccessResourceType(enum.StrEnum):
    """Loại tài nguyên cần cấp quyền cho người mới.

    Cố ý là enum đóng, không phải chuỗi tự do: hàng đợi cấp quyền chỉ hữu ích khi
    admin gom nhóm và lọc được. Cho gõ tự do thì sẽ có "repo", "Repo", "GitHub" và
    "github repo" cùng tồn tại, và không đếm được gì nữa.
    """

    REPOSITORY = "REPOSITORY"
    ISSUE_TRACKER = "ISSUE_TRACKER"
    CI_CD = "CI_CD"
    DATABASE = "DATABASE"
    SECRETS = "SECRETS"
    VPN = "VPN"
    OTHER = "OTHER"


class AccessGrantStatus(enum.StrEnum):
    """Vòng đời một quyền truy cập.

    Không có trạng thái DENIED: từ chối cấp quyền là quyết định của con người diễn ra
    ngoài hệ thống, và nếu admin quyết định không cấp thì bản ghi nên biến mất khỏi
    hàng đợi bằng REVOKED chứ không nằm lại làm nhiễu.
    """

    REQUESTED = "REQUESTED"
    GRANTED = "GRANTED"
    REVOKED = "REVOKED"


# ---- Project Knowledge ----
class DocumentDomain(enum.StrEnum):
    PROJECT = "PROJECT"
    POLICY = "POLICY"


class DocumentCategory(enum.StrEnum):
    """Chỉ dùng khi KnowledgeDocument.knowledge_domain = PROJECT."""

    OVERVIEW = "OVERVIEW"
    ARCHITECTURE = "ARCHITECTURE"
    SETUP = "SETUP"
    ACCESS_SECURITY = "ACCESS_SECURITY"
    CODEBASE_GUIDE = "CODEBASE_GUIDE"
    CONVENTION = "CONVENTION"
    FIRST_TASK = "FIRST_TASK"


class PolicyCategory(enum.StrEnum):
    """Chỉ dùng khi KnowledgeDocument.knowledge_domain = POLICY."""

    COMPANY_POLICY = "COMPANY_POLICY"
    HR_POLICY = "HR_POLICY"
    SECURITY_POLICY = "SECURITY_POLICY"
    BENEFIT = "BENEFIT"
    WORKING_RULE = "WORKING_RULE"
    GENERAL = "GENERAL"


class DocumentStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class VersionStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


# ---- Template & Plan ----
class TemplateScope(enum.StrEnum):
    GLOBAL = "GLOBAL"
    PROJECT = "PROJECT"


class TemplateStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    ARCHIVED = "ARCHIVED"


class TemplateVersionStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    ARCHIVED = "ARCHIVED"


class TaskCategory(enum.StrEnum):
    # Đọc chính sách công ty (KnowledgeDocument domain POLICY) — nhóm DUY NHẤT không đọc tài liệu
    # riêng của dự án, nên 1 lộ trình chuẩn = 1 phần công ty + 5 phần dự án.
    COMPANY = "COMPANY"
    ORIENTATION = "ORIENTATION"
    ARCHITECTURE = "ARCHITECTURE"
    ACCESS = "ACCESS"
    SETUP = "SETUP"
    CODEBASE = "CODEBASE"
    CONVENTION = "CONVENTION"
    FIRST_TASK = "FIRST_TASK"
    FIRST_PR = "FIRST_PR"


# Master Template chuẩn dùng COMPANY + 5 category dự án (khớp 5 giá trị đầu của DocumentCategory:
# OVERVIEW/ARCHITECTURE/SETUP/ACCESS_SECURITY/CODEBASE_GUIDE) — 3 category dưới đây là phần mở rộng
# làm sau (quyết định sản phẩm), KHÔNG xoá khỏi enum vì Postgres không hỗ trợ xoá giá trị enum và
# 1 số TemplateTask cũ ở GLOBAL vẫn còn bị PlanTask demo tham chiếu (không xoá được). Fork/clone
# template phải lọc bỏ 3 category này để project mới không kế thừa lại.
DEFERRED_TASK_CATEGORIES = (TaskCategory.CONVENTION, TaskCategory.FIRST_TASK, TaskCategory.FIRST_PR)


class PlanStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    PROJECT_READY = "PROJECT_READY"
    ONBOARDING_CLOSED = "ONBOARDING_CLOSED"


class TaskStatus(enum.StrEnum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    BLOCKED = "BLOCKED"


# ---- RAG & Support ----
class MessageRole(enum.StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


class ClaimSupportType(enum.StrEnum):
    DIRECT = "direct"
    INFERRED = "inferred"


class BlockerCategory(enum.StrEnum):
    ACCESS = "ACCESS"
    SETUP = "SETUP"
    DOCUMENT = "DOCUMENT"
    TECHNICAL = "TECHNICAL"
    OTHER = "OTHER"


class BlockerStatus(enum.StrEnum):
    OPEN = "OPEN"
    ROUTED = "ROUTED"
    RESOLVED = "RESOLVED"


# ---- F6 Rule Mining ----
class RuleEvidenceType(enum.StrEnum):
    """LLM-extraction classification of one PR comment/review body.

    Chỉ REUSABLE_CORRECTION và CONVENTION đủ điều kiện cluster thành RuleFamily
    (F6_RULE_MINING_SPEC.md §2.1/§5.3) — 4 giá trị còn lại dừng lại ở RuleCandidate,
    không bao giờ có RuleEvidence tương ứng.
    """

    REUSABLE_CORRECTION = "REUSABLE_CORRECTION"
    CONVENTION = "CONVENTION"
    LOCAL_CORRECTION = "LOCAL_CORRECTION"
    RATIONALE = "RATIONALE"
    QUESTION_DISCUSSION = "QUESTION_DISCUSSION"
    NOISE_OTHER = "NOISE_OTHER"


class RuleFamilyStatus(enum.StrEnum):
    """HITL Review Queue workflow state for a RuleFamily (CLAUDE.md Phase 6). No versioning,
    no multi-approver — one PM/Admin decision per family, forward-only from PENDING."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


# ---- F6 Scheduled Incremental Convention Discovery ----
class DiscoveryMode(enum.StrEnum):
    """Per-project convention-discovery cadence. No raw cron is ever accepted from a PM —
    these 4 modes are the entire surface."""

    MANUAL_ONLY = "MANUAL_ONLY"
    EVERY_N_HOURS = "EVERY_N_HOURS"
    DAILY_AT = "DAILY_AT"
    WEEKLY_AT = "WEEKLY_AT"


class IngestionJobType(enum.StrEnum):
    """Discriminator on IngestionJob — a single generic run-tracking table, not a per-feature
    one (NFR-14 applied to job tracking). Only one value exists today; other future job kinds
    (F1/F2 doc sync, digest) can reuse the same table by adding a value here, not a new table."""

    RULE_MINING = "RULE_MINING"
    GITHUB_SYNC = "GITHUB_SYNC"
    DOCUMENT_IMPORT = "DOCUMENT_IMPORT"


class IngestionJobTriggerType(enum.StrEnum):
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED"


class IngestionJobStatus(enum.StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
