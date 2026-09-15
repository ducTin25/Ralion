"""sync model voi spec moi: systemRole knowledgeDomain firstPR BlockerAttachment ChatSession userId xoa SupportDept SupportRequest AuditLog Notification

Revision ID: 087bc97c54cf
Revises: 092eacb97740
Create Date: 2026-08-11 16:56:27.254084

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '087bc97c54cf'
down_revision: str | Sequence[str] | None = '092eacb97740'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()

    # ---- 1. Bảng mới: BlockerAttachment ----
    op.create_table('blocker_attachments',
    sa.Column('attachment_id', sa.Integer(), nullable=False),
    sa.Column('blocker_id', sa.Integer(), nullable=False),
    sa.Column('storage_key', sa.String(), nullable=False),
    sa.Column('file_name', sa.String(), nullable=False),
    sa.Column('mime_type', sa.String(), nullable=False),
    sa.Column('uploaded_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['blocker_id'], ['blockers.blocker_id'], name=op.f('fk_blocker_attachments_blocker_id_blockers')),
    sa.PrimaryKeyConstraint('attachment_id', name=op.f('pk_blocker_attachments'))
    )

    # ---- 2. Xoá 4 bảng ngoài phạm vi MVP (support_requests trước vì phụ thuộc support_departments) ----
    op.drop_table('support_requests')
    op.drop_table('support_departments')
    op.drop_index(op.f('ix_notifications_user_id_read_at_created_at'), table_name='notifications')
    op.drop_table('notifications')
    op.drop_index(op.f('ix_audit_logs_actor_id_created_at'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_entity_type_entity_id_created_at'), table_name='audit_logs')
    op.drop_table('audit_logs')
    op.execute('DROP TYPE support_type')
    op.execute('DROP TYPE ticket_priority')
    op.execute('DROP TYPE ticket_status')
    op.execute('DROP TYPE notification_type')

    # ---- 3. User.role -> User.system_role (enum user_role đổi tập giá trị: bỏ PM/ENGINEER) ----
    # Phải drop cột + type cũ trước, vì system_role dùng lại tên type "user_role" nhưng giá trị khác.
    op.drop_column('users', 'role')
    op.execute('DROP TYPE user_role')
    user_role_new = postgresql.ENUM('ADMIN', 'HR', name='user_role')
    user_role_new.create(bind, checkfirst=True)
    op.add_column('users', sa.Column('system_role', sa.Enum('ADMIN', 'HR', name='user_role', create_type=False), nullable=True))

    # ---- 4. KnowledgeDocument: scope+category -> knowledge_domain + document_category + policy_category ----
    op.drop_constraint(op.f('ck_knowledge_documents_scope_project_id'), 'knowledge_documents', type_='check')
    op.drop_column('knowledge_documents', 'scope')
    op.drop_column('knowledge_documents', 'category')
    op.execute('DROP TYPE document_scope')
    op.execute('DROP TYPE document_category')

    document_domain_type = postgresql.ENUM('PROJECT', 'POLICY', name='document_domain')
    document_domain_type.create(bind, checkfirst=True)
    document_category_new = postgresql.ENUM(
        'OVERVIEW', 'ARCHITECTURE', 'SETUP', 'ACCESS_SECURITY', 'CODEBASE_GUIDE', 'CONVENTION', 'FIRST_TASK',
        name='document_category',
    )
    document_category_new.create(bind, checkfirst=True)
    policy_category_type = postgresql.ENUM(
        'COMPANY_POLICY', 'HR_POLICY', 'SECURITY_POLICY', 'BENEFIT', 'WORKING_RULE', 'GENERAL',
        name='policy_category',
    )
    policy_category_type.create(bind, checkfirst=True)

    op.add_column('knowledge_documents', sa.Column(
        'knowledge_domain', sa.Enum('PROJECT', 'POLICY', name='document_domain', create_type=False), nullable=False
    ))
    op.add_column('knowledge_documents', sa.Column(
        'document_category',
        sa.Enum('OVERVIEW', 'ARCHITECTURE', 'SETUP', 'ACCESS_SECURITY', 'CODEBASE_GUIDE', 'CONVENTION', 'FIRST_TASK',
                name='document_category', create_type=False),
        nullable=True,
    ))
    op.add_column('knowledge_documents', sa.Column(
        'policy_category',
        sa.Enum('COMPANY_POLICY', 'HR_POLICY', 'SECURITY_POLICY', 'BENEFIT', 'WORKING_RULE', 'GENERAL',
                name='policy_category', create_type=False),
        nullable=True,
    ))
    op.create_check_constraint(
        op.f('ck_knowledge_documents_knowledge_domain_category'),
        'knowledge_documents',
        "(knowledge_domain = 'PROJECT' AND project_id IS NOT NULL AND document_category IS NOT NULL AND policy_category IS NULL) "
        "OR (knowledge_domain = 'POLICY' AND project_id IS NULL AND policy_category IS NOT NULL AND document_category IS NULL)",
    )

    # ---- 5. OnboardingPlan: thêm 3 field First PR ----
    op.add_column('onboarding_plans', sa.Column('first_pr_url', sa.String(), nullable=True))
    op.add_column('onboarding_plans', sa.Column('first_pr_merged_at', sa.DateTime(), nullable=True))
    op.add_column('onboarding_plans', sa.Column('first_pr_confirmed_by_user_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f('fk_onboarding_plans_first_pr_confirmed_by_user_id_users'),
        'onboarding_plans', 'users', ['first_pr_confirmed_by_user_id'], ['user_id'],
    )

    # ---- 6. Project: thêm created_at ----
    op.add_column('projects', sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False))

    # ---- 7. ChatSession: thêm user_id, knowledge_domain, project_id; membership_id -> nullable ----
    op.add_column('chat_sessions', sa.Column('user_id', sa.Integer(), nullable=False))
    op.add_column('chat_sessions', sa.Column(
        'knowledge_domain', sa.Enum('PROJECT', 'POLICY', name='document_domain', create_type=False), nullable=False
    ))
    op.add_column('chat_sessions', sa.Column('project_id', sa.Integer(), nullable=True))
    op.alter_column('chat_sessions', 'membership_id', existing_type=sa.INTEGER(), nullable=True)
    op.create_foreign_key(op.f('fk_chat_sessions_user_id_users'), 'chat_sessions', 'users', ['user_id'], ['user_id'])
    op.create_foreign_key(op.f('fk_chat_sessions_project_id_projects'), 'chat_sessions', 'projects', ['project_id'], ['project_id'])


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()

    # ---- 7 ----
    op.drop_constraint(op.f('fk_chat_sessions_project_id_projects'), 'chat_sessions', type_='foreignkey')
    op.drop_constraint(op.f('fk_chat_sessions_user_id_users'), 'chat_sessions', type_='foreignkey')
    op.alter_column('chat_sessions', 'membership_id', existing_type=sa.INTEGER(), nullable=False)
    op.drop_column('chat_sessions', 'project_id')
    op.drop_column('chat_sessions', 'knowledge_domain')
    op.drop_column('chat_sessions', 'user_id')

    # ---- 6 ----
    op.drop_column('projects', 'created_at')

    # ---- 5 ----
    op.drop_constraint(op.f('fk_onboarding_plans_first_pr_confirmed_by_user_id_users'), 'onboarding_plans', type_='foreignkey')
    op.drop_column('onboarding_plans', 'first_pr_confirmed_by_user_id')
    op.drop_column('onboarding_plans', 'first_pr_merged_at')
    op.drop_column('onboarding_plans', 'first_pr_url')

    # ---- 4 ----
    op.drop_constraint(op.f('ck_knowledge_documents_knowledge_domain_category'), 'knowledge_documents', type_='check')
    op.drop_column('knowledge_documents', 'policy_category')
    op.drop_column('knowledge_documents', 'document_category')
    op.drop_column('knowledge_documents', 'knowledge_domain')
    op.execute('DROP TYPE policy_category')
    op.execute('DROP TYPE document_category')
    op.execute('DROP TYPE document_domain')

    document_scope_old = postgresql.ENUM('ORGANIZATION', 'PROJECT', name='document_scope')
    document_scope_old.create(bind, checkfirst=True)
    document_category_old = postgresql.ENUM(
        'POLICY', 'OVERVIEW', 'ARCHITECTURE', 'SETUP', 'ACCESS_SECURITY', 'CODEBASE_GUIDE', 'CONVENTION',
        'WORKFLOW', 'REFERENCE_PR', name='document_category',
    )
    document_category_old.create(bind, checkfirst=True)
    op.add_column('knowledge_documents', sa.Column(
        'category', sa.Enum('POLICY', 'OVERVIEW', 'ARCHITECTURE', 'SETUP', 'ACCESS_SECURITY', 'CODEBASE_GUIDE',
                             'CONVENTION', 'WORKFLOW', 'REFERENCE_PR', name='document_category', create_type=False),
        nullable=False,
    ))
    op.add_column('knowledge_documents', sa.Column(
        'scope', sa.Enum('ORGANIZATION', 'PROJECT', name='document_scope', create_type=False), nullable=False
    ))
    op.create_check_constraint(
        op.f('ck_knowledge_documents_scope_project_id'),
        'knowledge_documents',
        "(scope = 'PROJECT' AND project_id IS NOT NULL) OR (scope = 'ORGANIZATION' AND project_id IS NULL)",
    )

    # ---- 3 ----
    op.drop_column('users', 'system_role')
    op.execute('DROP TYPE user_role')
    user_role_old = postgresql.ENUM('ADMIN', 'PM', 'ENGINEER', 'HR', name='user_role')
    user_role_old.create(bind, checkfirst=True)
    op.add_column('users', sa.Column(
        'role', sa.Enum('ADMIN', 'PM', 'ENGINEER', 'HR', name='user_role', create_type=False), nullable=False
    ))

    # ---- 2 ----
    op.execute("CREATE TYPE support_type AS ENUM ('HR', 'IT', 'SECURITY', 'PROJECT_OWNER')")
    op.execute("CREATE TYPE ticket_priority AS ENUM ('LOW', 'NORMAL', 'HIGH', 'URGENT')")
    op.execute("CREATE TYPE ticket_status AS ENUM ('OPEN', 'ASSIGNED', 'IN_PROGRESS', 'RESOLVED', 'CLOSED')")
    op.execute("CREATE TYPE notification_type AS ENUM ('DEADLINE', 'BLOCKED', 'TICKET_UPDATE')")
    op.create_table('audit_logs',
    sa.Column('audit_id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('actor_id', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('action', sa.VARCHAR(), autoincrement=False, nullable=False),
    sa.Column('entity_type', sa.VARCHAR(), autoincrement=False, nullable=False),
    sa.Column('entity_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.user_id'], name=op.f('fk_audit_logs_actor_id_users')),
    sa.PrimaryKeyConstraint('audit_id', name=op.f('pk_audit_logs'))
    )
    op.create_index(op.f('ix_audit_logs_entity_type_entity_id_created_at'), 'audit_logs', ['entity_type', 'entity_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_audit_logs_actor_id_created_at'), 'audit_logs', ['actor_id', 'created_at'], unique=False)
    op.create_table('notifications',
    sa.Column('notification_id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('type', postgresql.ENUM('DEADLINE', 'BLOCKED', 'TICKET_UPDATE', name='notification_type'), autoincrement=False, nullable=False),
    sa.Column('title', sa.VARCHAR(), autoincrement=False, nullable=False),
    sa.Column('message', sa.TEXT(), autoincrement=False, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('read_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], name=op.f('fk_notifications_user_id_users')),
    sa.PrimaryKeyConstraint('notification_id', name=op.f('pk_notifications'))
    )
    op.create_index(op.f('ix_notifications_user_id_read_at_created_at'), 'notifications', ['user_id', 'read_at', 'created_at'], unique=False)
    op.create_table('support_departments',
    sa.Column('department_id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('name', sa.VARCHAR(), autoincrement=False, nullable=False),
    sa.Column('support_type', postgresql.ENUM('HR', 'IT', 'SECURITY', 'PROJECT_OWNER', name='support_type'), autoincrement=False, nullable=False),
    sa.Column('response_sla_minutes', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('resolution_sla_minutes', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.CheckConstraint('resolution_sla_minutes > 0', name=op.f('ck_support_departments_resolution_sla_positive')),
    sa.CheckConstraint('response_sla_minutes > 0', name=op.f('ck_support_departments_response_sla_positive')),
    sa.PrimaryKeyConstraint('department_id', name=op.f('pk_support_departments')),
    sa.UniqueConstraint('name', name=op.f('uq_support_departments_name'))
    )
    op.create_table('support_requests',
    sa.Column('request_id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('blocker_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('department_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('priority', postgresql.ENUM('LOW', 'NORMAL', 'HIGH', 'URGENT', name='ticket_priority'), autoincrement=False, nullable=False),
    sa.Column('status', postgresql.ENUM('OPEN', 'ASSIGNED', 'IN_PROGRESS', 'RESOLVED', 'CLOSED', name='ticket_status'), autoincrement=False, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('resolution_due_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.Column('resolved_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.CheckConstraint("(status <> ALL (ARRAY['RESOLVED'::ticket_status, 'CLOSED'::ticket_status])) OR resolved_at IS NOT NULL", name=op.f('ck_support_requests_resolved_requires_resolved_at')),
    sa.ForeignKeyConstraint(['blocker_id'], ['blockers.blocker_id'], name=op.f('fk_support_requests_blocker_id_blockers')),
    sa.ForeignKeyConstraint(['department_id'], ['support_departments.department_id'], name=op.f('fk_support_requests_department_id_support_departments')),
    sa.PrimaryKeyConstraint('request_id', name=op.f('pk_support_requests'))
    )

    # ---- 1 ----
    op.drop_table('blocker_attachments')
