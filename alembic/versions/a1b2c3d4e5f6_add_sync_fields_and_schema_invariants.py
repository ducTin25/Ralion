"""Add project sync state and enforce architecture invariants.

Revision ID: a1b2c3d4e5f6
Revises: 087bc97c54cf
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "087bc97c54cf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    sync_status = postgresql.ENUM(
        "NOT_STARTED",
        "SYNCING",
        "SUCCESS",
        "PARTIAL",
        "FAILED",
        name="sync_status",
    )
    sync_status.create(bind, checkfirst=True)
    op.add_column(
        "projects",
        sa.Column(
            "sync_status",
            sa.Enum("NOT_STARTED", "SYNCING", "SUCCESS", "PARTIAL", "FAILED", name="sync_status", create_type=False),
            nullable=False,
            server_default="NOT_STARTED",
        ),
    )
    op.add_column("projects", sa.Column("last_synced_at", sa.DateTime(), nullable=True))

    # INV1: a company-scoped user cannot have project memberships, and vice versa.
    op.execute(
        """
        CREATE FUNCTION enforce_user_membership_role_exclusivity()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_TABLE_NAME = 'project_memberships' THEN
                IF EXISTS (
                    SELECT 1 FROM users
                    WHERE user_id = NEW.user_id AND system_role IS NOT NULL
                ) THEN
                    RAISE EXCEPTION
                        'User % with system_role cannot have a project membership', NEW.user_id;
                END IF;
            ELSIF NEW.system_role IS NOT NULL AND EXISTS (
                SELECT 1 FROM project_memberships WHERE user_id = NEW.user_id
            ) THEN
                RAISE EXCEPTION
                    'User % with project memberships cannot have a system_role', NEW.user_id;
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_project_memberships_role_exclusivity
        BEFORE INSERT OR UPDATE OF user_id ON project_memberships
        FOR EACH ROW EXECUTE FUNCTION enforce_user_membership_role_exclusivity();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_users_role_exclusivity
        BEFORE UPDATE OF system_role ON users
        FOR EACH ROW EXECUTE FUNCTION enforce_user_membership_role_exclusivity();
        """
    )

    # INV2: every persisted document has exactly one ACTIVE version.
    op.execute(
        """
        CREATE FUNCTION enforce_one_active_document_version()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            v_document_id integer;
            v_active_count integer;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                v_document_id := OLD.document_id;
            ELSE
                v_document_id := NEW.document_id;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM knowledge_documents WHERE document_id = v_document_id
            ) THEN
                RETURN NULL;
            END IF;

            SELECT count(*) INTO v_active_count
            FROM document_versions
            WHERE document_id = v_document_id AND status = 'ACTIVE';

            IF v_active_count <> 1 THEN
                RAISE EXCEPTION
                    'Document % must have exactly one ACTIVE version, found %',
                    v_document_id, v_active_count;
            END IF;
            RETURN NULL;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_document_versions_one_active
        AFTER INSERT OR UPDATE OR DELETE ON document_versions
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION enforce_one_active_document_version();
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_knowledge_documents_one_active
        AFTER INSERT OR DELETE ON knowledge_documents
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION enforce_one_active_document_version();
        """
    )

    # INV7: onboarding plans may only move forward through their lifecycle.
    op.execute(
        """
        CREATE FUNCTION enforce_onboarding_plan_forward_status()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            v_old_rank integer;
            v_new_rank integer;
        BEGIN
            IF NEW.status = OLD.status THEN
                RETURN NEW;
            END IF;

            v_old_rank := CASE OLD.status::text
                WHEN 'DRAFT' THEN 1
                WHEN 'APPROVED' THEN 2
                WHEN 'ACTIVE' THEN 3
                WHEN 'PROJECT_READY' THEN 4
                WHEN 'ONBOARDING_CLOSED' THEN 5
            END;
            v_new_rank := CASE NEW.status::text
                WHEN 'DRAFT' THEN 1
                WHEN 'APPROVED' THEN 2
                WHEN 'ACTIVE' THEN 3
                WHEN 'PROJECT_READY' THEN 4
                WHEN 'ONBOARDING_CLOSED' THEN 5
            END;

            IF v_new_rank < v_old_rank THEN
                RAISE EXCEPTION
                    'Onboarding plan status cannot move backward from % to %',
                    OLD.status, NEW.status;
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_onboarding_plans_forward_status
        BEFORE UPDATE OF status ON onboarding_plans
        FOR EACH ROW EXECUTE FUNCTION enforce_onboarding_plan_forward_status();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_onboarding_plans_forward_status ON onboarding_plans")
    op.execute("DROP FUNCTION IF EXISTS enforce_onboarding_plan_forward_status()")
    op.execute("DROP TRIGGER IF EXISTS trg_knowledge_documents_one_active ON knowledge_documents")
    op.execute("DROP TRIGGER IF EXISTS trg_document_versions_one_active ON document_versions")
    op.execute("DROP FUNCTION IF EXISTS enforce_one_active_document_version()")
    op.execute("DROP TRIGGER IF EXISTS trg_users_role_exclusivity ON users")
    op.execute("DROP TRIGGER IF EXISTS trg_project_memberships_role_exclusivity ON project_memberships")
    op.execute("DROP FUNCTION IF EXISTS enforce_user_membership_role_exclusivity()")
    op.drop_column("projects", "last_synced_at")
    op.drop_column("projects", "sync_status")
    op.execute("DROP TYPE IF EXISTS sync_status")
