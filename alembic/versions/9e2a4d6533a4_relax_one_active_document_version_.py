"""relax one active document version trigger to allow zero

Trigger gốc (migration a1b2c3d4e5f6_add_sync_fields_and_schema_invariants.py) ép "đúng 1" ACTIVE
version cho mỗi document tại mọi thời điểm commit (kể cả tạm thời) — chặn luôn trạng thái hợp lệ
"document vừa tạo, version còn PROCESSING, chưa có ACTIVE nào" mà thiết kế gốc SoT §14 mô tả (TV3
xử lý PROCESSING -> ACTIVE ở 1 transaction khác, sau này). Sửa lại đúng ý nghĩa INV2 ban đầu: TỐI ĐA
1 ACTIVE (chặn > 1), cho phép 0 (đang PROCESSING hoặc document vừa tạo chưa có version nào).
Quyết định do team xác nhận trực tiếp (Mai Anh phụ trách phần embedding/TV3) — xem
docs/PM/Phase-3/plan-phase3-documents.md Quyết định #1.

Revision ID: 9e2a4d6533a4
Revises: 766d77208fd9
Create Date: 2026-08-13
"""

from collections.abc import Sequence

from alembic import op

revision: str = "9e2a4d6533a4"
down_revision: str | None = "766d77208fd9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_one_active_document_version()
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

            IF v_active_count > 1 THEN
                RAISE EXCEPTION
                    'Document % must have at most one ACTIVE version, found %',
                    v_document_id, v_active_count;
            END IF;
            RETURN NULL;
        END;
        $$;
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_one_active_document_version()
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
