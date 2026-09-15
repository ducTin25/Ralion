"""Hợp đồng phía POLICY: parse metadata tài liệu và câu truy vấn pgvector dùng chung.

`test_policy_artifact_is_complete_and_valid` từng nằm ở đây đã bị **xoá**: nó kiểm tra
`policy_embeddings.jsonl` — artifact embedding sinh sẵn ngoài hệ thống (Kaggle) để seed dữ liệu
demo. Đó không phải đường ingest vận hành thật: HR upload tài liệu qua
`POST /console/hr/policies` → `hr_policy_service.upload_policy` → `policy_ingestion.py`, nơi
`scan()` redact secret **trước khi** chunk/embed (cùng scanner với GitHub path, invariant #6).
Đường đó đã có test riêng, nên test artifact chỉ ghim lại chất lượng của một file dữ liệu tĩnh
mà không bảo vệ hành vi nào đang chạy.

`scripts/import_policy_embeddings.py` và `src/infrastructure/persistence/policy_embedding_import.py`
vẫn được giữ (còn dùng để seed DB demo), chỉ là không còn bị CI chặn vì nội dung artifact.

Hai test còn lại ở đây kiểm code thật đang chạy:
- `policy_metadata` — chính `policy_ingestion.py` import và dùng khi HR upload;
- câu lệnh pgvector — NFR-14, một RetrievalEngine duy nhất cho mọi domain.
"""

from pathlib import Path

from sqlalchemy.dialects import postgresql

from src.ai.retrieval_engine.retrieval_engine import RetrievalEngine
from src.model.enums import DocumentDomain
from src.modules.knowledge.policy_metadata import (
    normalize_policy_source_key,
    parse_policy_version_metadata,
)

ROOT = Path(__file__).resolve().parents[2]
POLICY_DATA = ROOT / "demo-data" / "company-policy"


def test_policy_metadata_keeps_source_version_and_normalizes_identity() -> None:
    content = (POLICY_DATA / "hr_01_nghi_phep_cham_cong.md").read_text(encoding="utf-8")

    assert normalize_policy_source_key(" hr-pol-001 ") == "HR-POL-001"
    assert parse_policy_version_metadata(content)[0] == "3.2"


def test_policy_retrieval_uses_the_shared_pgvector_statement() -> None:
    statement = RetrievalEngine(session=None)._statement(  # type: ignore[arg-type]
        [0.0] * 1024,
        knowledge_domain=DocumentDomain.POLICY,
        project_id=None,
        limit=10,
    )
    sql = str(statement.compile(dialect=postgresql.dialect()))

    assert "document_chunks" in sql
    assert "document_versions" in sql
    assert "knowledge_documents" in sql
    assert "knowledge_documents.project_id IS NULL" in sql
