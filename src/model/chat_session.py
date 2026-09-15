import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base
from src.model.enums import DocumentDomain


class ChatSession(Base):
    """Một conversation (nhiều turn), không phải một turn.

    Scope (`user_id`/`knowledge_domain`/`project_id`/`membership_id`) được ghi một lần lúc tạo và
    **immutable**: history vì thế không thể đi xuyên domain hay xuyên project. Authorization vẫn
    luôn được tính lại từ `ProjectMembership` mỗi turn (`ChatService._scope`) — các cột dưới đây
    chỉ để *đối chiếu*, không bao giờ là nguồn của quyền truy cập.
    """

    __tablename__ = "chat_sessions"
    __table_args__ = (
        # Biến "POLICY là company-wide, PROJECT phải có membership" từ convention trong _scope
        # thành ràng buộc ở tầng schema.
        CheckConstraint(
            "(knowledge_domain = 'POLICY' AND project_id IS NULL AND membership_id IS NULL)"
            " OR (knowledge_domain = 'PROJECT' AND project_id IS NOT NULL"
            " AND membership_id IS NOT NULL)",
            name="scope_matches_domain",
        ),
        Index("ix_chat_sessions_user_id_last_message_at", "user_id", "last_message_at"),
    )

    session_id: Mapped[int] = mapped_column(primary_key=True)
    # Handle duy nhất mà client được thấy. PK tuần tự không bao giờ ra khỏi server nên không
    # có bề mặt enumeration; ACL thật vẫn là điều kiện user_id khi load.
    public_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), nullable=False, unique=True, default=uuid.uuid4
    )
    # Bắt buộc để ADMIN/HR/PM không có ProjectMembership vẫn dùng được chatbot.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    knowledge_domain: Mapped[DocumentDomain] = mapped_column(
        Enum(DocumentDomain, name="document_domain"), nullable=False
    )
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.project_id"), nullable=True)
    # Nullable: chat về POLICY (không gắn dự án cụ thể) thì không có membership.
    membership_id: Mapped[int | None] = mapped_column(
        ForeignKey("project_memberships.membership_id"), nullable=True
    )
    context_plan_task_id: Mapped[int | None] = mapped_column(
        ForeignKey("plan_tasks.plan_task_id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    # Idle TTL của sliding-window: quá tuổi thì history bị bỏ qua, row vẫn giữ để audit.
    last_message_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # "vi" | "en" | NULL. Set only when a turn's `TurnInterpreter` verdict carries an EXPLICIT
    # `presentation.language` (the user asked to switch language this turn, in any route shape --
    # not inferred from script/tone). Conversation-scoped, not `User`-scoped: PATCH /auth/me
    # remains the only way to change the durable cross-conversation preference
    # (PERSONALIZE_CHATBOT_SPEC.md §0.4); this column is the missing middle tier between "this
    # turn only" and "every conversation forever" -- CHANGE_LOG.md 2026-08-23 stateful diagnostic,
    # item 2 ("Vietnamese preference not carrying across subsequent turns").
    preferred_language: Mapped[str | None] = mapped_column(nullable=True)
    # Same conversation-scoped presentation state for an explicit standing verbosity request.
    # Values mirror TurnInterpreter's closed presentation enum: "concise" | "detailed" | NULL.
    preferred_response_detail: Mapped[str | None] = mapped_column(nullable=True)
    # `TopicState` (2026-08-29 memory enhancement, F5 audit root causes A/C):
    # `conversation_memory.py`'s server-derived topic memory, conversation-scoped like the two
    # columns above. `topic_subject` is always a previously-computed `resolved_question` --
    # NEVER raw user text -- and `topic_entities` is a bounded, delimiter-joined list of
    # document/chunk titles already surfaced as citations for the turn that set it. Written only
    # by `ChatService._update_topic_state`, only for a turn whose scope/route already cleared
    # every guardrail. Conversation resolution only: never read by retrieval or the citation
    # validator, never treated as evidence for a company/project claim.
    topic_subject: Mapped[str | None] = mapped_column(nullable=True)
    topic_entities: Mapped[str | None] = mapped_column(nullable=True)
