"""Upload 24 file tài liệu mẫu lên Cloudinary (chạy 1 lần, cần CLOUDINARY_* trong .env),
đồng thời sinh ra file SQL portable (scripts/sql/seed_knowledge_documents.sql) chứa sẵn URL
Cloudinary thật — để người khác trong team CHỈ CẦN chạy file .sql đó (không cần tài khoản
Cloudinary riêng) là có đủ KnowledgeDocument/DocumentVersion/DocumentChunk trên máy họ.

Yêu cầu chạy trước: scripts/seed_dev_data.py (cần sẵn users + projects).

Usage:
    python scripts/upload_sample_docs_to_cloudinary.py            # upload + apply vào DB hiện tại + ghi .sql
    python scripts/upload_sample_docs_to_cloudinary.py --sql-only # chỉ ghi .sql, không upload/không đụng DB
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from src.config import get_settings

BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DOCS_DIR = BASE_DIR / "docs" / "setup-be" / "sample-docs"
OUTPUT_SQL_PATH = BASE_DIR / "scripts" / "sql" / "seed_knowledge_documents.sql"

# (slug, document_category) — title lấy từ dòng "# ..." đầu file.
PROJECT_DOC_FILES = [
    ("overview", "OVERVIEW"),
    ("architecture", "ARCHITECTURE"),
    ("setup", "SETUP"),
    ("access-security", "ACCESS_SECURITY"),
    ("codebase-guide", "CODEBASE_GUIDE"),
    ("convention", "CONVENTION"),
    ("first-task", "FIRST_TASK"),
]
PROJECTS = [
    {"folder": "phoneshop", "key": "PHONESHOP", "pm_email": "pm.phoneshop@onboarding.dev"},
    {"folder": "tourbook", "key": "TOURBOOK", "pm_email": "pm.tourbook@onboarding.dev"},
    {"folder": "furnistore", "key": "FURNISTORE", "pm_email": "pm.furnistore@onboarding.dev"},
]
POLICY_DOC_FILES = [
    ("company-policy", "COMPANY_POLICY"),
    ("hr-policy", "HR_POLICY"),
    ("security-policy", "SECURITY_POLICY"),
]


def sql_str(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def extract_title(content: str, fallback: str) -> str:
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def chunk_markdown(content: str) -> list[tuple[str | None, str]]:
    """Chia file theo heading '## ' — mỗi section = 1 chunk demo (chưa chạy embedding thật)."""
    chunks: list[tuple[str | None, str]] = []
    heading: str | None = None
    buf: list[str] = []
    for line in content.splitlines():
        if line.startswith("## "):
            if buf:
                chunks.append((heading, "\n".join(buf).strip()))
            heading = line[3:].strip()
            buf = []
        else:
            buf.append(line)
    if buf:
        chunks.append((heading, "\n".join(buf).strip()))
    return [(h, c) for h, c in chunks if c]


def upload_file(path: Path, folder: str) -> str:
    import cloudinary.uploader

    result = cloudinary.uploader.upload(
        str(path),
        resource_type="raw",
        folder=f"knowledge-documents/{folder}",
        public_id=path.stem,
        overwrite=True,
    )
    return result["secure_url"]


def configure_cloudinary(settings) -> None:
    import cloudinary

    missing = [
        name
        for name, value in (
            ("CLOUDINARY_CLOUD_NAME", settings.cloudinary_cloud_name),
            ("CLOUDINARY_API_KEY", settings.cloudinary_api_key),
            ("CLOUDINARY_API_SECRET", settings.cloudinary_api_secret),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Cloudinary upload requires these variables in .env: "
            + ", ".join(missing)
            + ". Use --sql-only to generate SQL without uploading."
        )
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
    )


def build_document_sql(
    *, title: str, source_url: str, knowledge_domain: str, document_category: str | None,
    policy_category: str | None, project_key: str | None, created_by_email: str,
    checksum: str, chunks: list[tuple[str | None, str]],
) -> str:
    project_id_expr = (
        f"(SELECT project_id FROM projects WHERE key = {sql_str(project_key)})" if project_key else "NULL"
    )
    document_category_expr = sql_str(document_category) if document_category else "NULL"
    policy_category_expr = sql_str(policy_category) if policy_category else "NULL"

    lines = [
        "WITH doc AS (",
        "  INSERT INTO knowledge_documents",
        "    (project_id, created_by_user_id, knowledge_domain, document_category, policy_category,",
        "     source_key, category_confirmed, category_classification_status,",
        "     title, source_url, status, created_at, updated_at)",
        "  VALUES (",
        f"    {project_id_expr},",
        f"    (SELECT user_id FROM users WHERE email = {sql_str(created_by_email)}),",
        f"    {sql_str(knowledge_domain)}, {document_category_expr}, {policy_category_expr},",
        f"    {sql_str(source_url)}, true, 'CLASSIFIED',",
        f"    {sql_str(title)}, {sql_str(source_url)}, 'ACTIVE', now(), now()",
        "  )",
        "  RETURNING document_id",
        "),",
        "ver AS (",
        "  INSERT INTO document_versions",
        "    (document_id, version_no, revision_no, embedding_model_version,",
        "     storage_uri, checksum, status, created_at)",
        "  SELECT document_id, 1, 1, 'pending', "
        + sql_str(source_url)
        + ", "
        + sql_str(checksum)
        + ", 'ACTIVE', now() FROM doc",
        "  RETURNING version_id",
        ")",
    ]
    if chunks:
        chunk_values = ",\n".join(
            f"    ({sql_str(h) if h else 'NULL'}::text, {sql_str(c)}, {i}, {max(1, len(c.split()))}, "
            f"{sql_str(c)}, {sql_str(hashlib.sha256(c.encode('utf-8')).hexdigest())}, "
            f"'pending', '', {sql_str(c)})"
            for i, (h, c) in enumerate(chunks)
        )
        lines.append(
            "INSERT INTO document_chunks "
            "(version_id, heading, content, chunk_index, token_count, embedding_text, "
            "content_hash, embedding_model_version, lexical_identifiers, lexical_technical)"
        )
        lines.append(
            "SELECT ver.version_id, c.heading, c.content, c.chunk_index, c.token_count, "
            "c.embedding_text, c.content_hash, c.embedding_model_version, "
            "c.lexical_identifiers, c.lexical_technical"
        )
        lines.append("FROM ver, (VALUES")
        lines.append(chunk_values)
        lines.append(
            ") AS c(heading, content, chunk_index, token_count, embedding_text, "
            "content_hash, embedding_model_version, lexical_identifiers, lexical_technical);"
        )
    else:
        lines.append("SELECT 1;")

    return "\n".join(lines)


def main() -> None:
    sql_only = "--sql-only" in sys.argv
    settings = get_settings()

    if not sql_only:
        configure_cloudinary(settings)

    statements: list[str] = [
        "-- Auto-generated bởi scripts/upload_sample_docs_to_cloudinary.py — KHÔNG sửa tay.",
        "-- Chạy SAU khi đã chạy scripts/seed_dev_data.py (cần sẵn users + projects).",
        "-- Không cần tài khoản Cloudinary để chạy file này — URL đã upload sẵn.",
        "BEGIN;",
        "",
    ]

    for proj in PROJECTS:
        folder_path = SAMPLE_DOCS_DIR / proj["folder"]
        for slug, category in PROJECT_DOC_FILES:
            file_path = folder_path / f"{slug}.md"
            content = file_path.read_text(encoding="utf-8")
            title = extract_title(content, slug)
            checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
            if sql_only:
                url = f"https://res.cloudinary.com/{settings.cloudinary_cloud_name or 'CLOUD_NAME'}/raw/upload/knowledge-documents/{proj['folder']}/{slug}"
            else:
                url = upload_file(file_path, proj["folder"])
                print(f"uploaded: {proj['key']}/{slug} -> {url}")
            statements.append(f"-- {proj['key']}: {title}")
            statements.append(
                build_document_sql(
                    title=title,
                    source_url=url,
                    knowledge_domain="PROJECT",
                    document_category=category,
                    policy_category=None,
                    project_key=proj["key"],
                    created_by_email=proj["pm_email"],
                    checksum=checksum,
                    chunks=chunk_markdown(content),
                )
            )
            statements.append("")

    policy_dir = SAMPLE_DOCS_DIR / "policy"
    for slug, category in POLICY_DOC_FILES:
        file_path = policy_dir / f"{slug}.md"
        content = file_path.read_text(encoding="utf-8")
        title = extract_title(content, slug)
        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if sql_only:
            url = f"https://res.cloudinary.com/{settings.cloudinary_cloud_name or 'CLOUD_NAME'}/raw/upload/knowledge-documents/policy/{slug}"
        else:
            url = upload_file(file_path, "policy")
            print(f"uploaded: POLICY/{slug} -> {url}")
        statements.append(f"-- POLICY: {title}")
        statements.append(
            build_document_sql(
                title=title,
                source_url=url,
                knowledge_domain="POLICY",
                document_category=None,
                policy_category=category,
                project_key=None,
                created_by_email="hr@onboarding.dev",
                checksum=checksum,
                chunks=chunk_markdown(content),
            )
        )
        statements.append("")

    statements.append("COMMIT;")

    OUTPUT_SQL_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_SQL_PATH.write_text("\n".join(statements), encoding="utf-8")
    print(f"\nĐã ghi: {OUTPUT_SQL_PATH}")


if __name__ == "__main__":
    main()
