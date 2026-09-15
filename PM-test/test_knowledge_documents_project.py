"""Test Phase 3 — CRUD tài liệu dự án thật (PROJECT domain): upload đơn lẻ, quét folder (UC-04) +
Coverage Report, import từ kết quả quét. Version ACTIVE ngay sau upload (TV3 đã nối chunk+activate
vào luồng import — xem docs/PM/Phase-4/plan-fix-onboarding-plan-quality.md mục 0/3.1).

Mọi endpoint /knowledge-documents/pm/... giờ yêu cầu đăng nhập (`get_current_user` +
`require_project_member`) — dùng header `X-User-Id` với 1 admin thật (`admin_id` fixture) vì admin
bỏ qua hẳn bước kiểm tra membership dự án (xem `src/api/dependencies.py::require_project_member`)."""

import uuid
from pathlib import Path

import pytest
from sqlalchemy import func, select

from src.model.document_chunk import DocumentChunk
from src.model.session import AsyncSessionLocal

SAMPLE_REPO_DIR = Path(__file__).resolve().parent.parent / "docs" / "PM" / "Phase-3" / "sample-repo"


def _unique_key() -> str:
    return f"TEST{uuid.uuid4().hex[:8].upper()}"


async def _create_project(client, test_data, admin_id: int) -> int:
    response = await client.post(
        "/api/v1/projects/pm",
        json={"key": _unique_key(), "name": "Phase3 Doc Test Project", "created_by_admin_id": admin_id},
    )
    assert response.status_code == 201
    project_id = response.json()["project_id"]
    test_data.project_ids.append(project_id)
    return project_id


@pytest.mark.asyncio
async def test_upload_single_document_creates_active_version(client, test_data, admin_id):
    project_id = await _create_project(client, test_data, admin_id)

    response = await client.post(
        f"/api/v1/knowledge-documents/pm/projects/{project_id}/upload",
        headers={"X-User-Id": str(admin_id)},
        data={"category": "OVERVIEW", "title": "README.md"},
        files={"file": ("README.md", b"# Tong quan du an test", "text/markdown")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["document_category"] == "OVERVIEW"
    assert body["title"] == "README.md"
    assert body["latest_version"]["status"] == "ACTIVE"
    assert body["latest_version"]["revision_no"] == 1
    # `version_no` do lõi ingest chung đặt = `source_ref` (GitHub sync dùng commit SHA; nguồn tải
    # tay dùng "upload:<checksum>") — không còn là số đếm như bản tự dựng version trước đây.
    assert body["latest_version"]["version_no"].startswith("upload:")

    # Điểm mấu chốt của việc dùng chung lõi ingest: tài liệu tải tay giờ CÓ chunk thật, nên
    # `bm25_search()` của pipeline sinh plan mới tìm được nguồn (trước đây luôn 0 chunk -> "thiếu
    # nguồn" ở mọi task).
    async with AsyncSessionLocal() as db:
        chunk_count = await db.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.version_id == body["latest_version"]["version_id"])
        )
    assert chunk_count >= 1


@pytest.mark.asyncio
async def test_upload_second_version_archives_previous(client, test_data, admin_id):
    """Version mới ACTIVE ngay, version cũ tự ARCHIVED (INV2: tối đa 1 ACTIVE/document) — khác hành
    vi PROCESSING-mãi-mãi trước đây, xem `document_version_service.activate_version`."""
    project_id = await _create_project(client, test_data, admin_id)
    headers = {"X-User-Id": str(admin_id)}

    first = await client.post(
        f"/api/v1/knowledge-documents/pm/projects/{project_id}/upload",
        headers=headers,
        data={"category": "SETUP", "title": "docs/setup/local-setup.md"},
        files={"file": ("local-setup.md", b"huong dan cai dat ban 1", "text/markdown")},
    )
    assert first.status_code == 201
    document_id = first.json()["document_id"]
    assert first.json()["latest_version"]["status"] == "ACTIVE"

    second = await client.post(
        f"/api/v1/knowledge-documents/pm/projects/{project_id}/upload",
        headers=headers,
        data={"category": "SETUP", "title": "docs/setup/local-setup.md"},
        files={"file": ("local-setup.md", b"huong dan cai dat ban 2 khac noi dung", "text/markdown")},
    )
    assert second.status_code == 201
    assert second.json()["document_id"] == document_id
    assert second.json()["latest_version"]["revision_no"] == 2
    assert second.json()["latest_version"]["status"] == "ACTIVE"

    listing = await client.get(
        f"/api/v1/knowledge-documents/pm/projects/{project_id}", headers=headers
    )
    assert listing.status_code == 200
    docs = listing.json()
    assert len(docs) == 1
    assert docs[0]["latest_version"]["revision_no"] == 2
    assert docs[0]["latest_version"]["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_upload_different_title_same_category_creates_new_document(client, test_data, admin_id):
    """1 category có thể chứa NHIỀU document (khớp pattern Master Template) — file mới khác title
    trong cùng category phải tạo document RIÊNG, không gộp/ghi đè vào document cũ."""
    project_id = await _create_project(client, test_data, admin_id)
    headers = {"X-User-Id": str(admin_id)}

    first = await client.post(
        f"/api/v1/knowledge-documents/pm/projects/{project_id}/upload",
        headers=headers,
        data={"category": "SETUP", "title": "old-setup.md"},
        files={"file": ("old-setup.md", b"noi dung ban dau", "text/markdown")},
    )
    assert first.status_code == 201
    document_id = first.json()["document_id"]

    second = await client.post(
        f"/api/v1/knowledge-documents/pm/projects/{project_id}/upload",
        headers=headers,
        data={"category": "SETUP", "title": "docs/setup/local-setup.md"},
        files={"file": ("local-setup.md", b"noi dung khac han", "text/markdown")},
    )
    assert second.status_code == 201
    assert second.json()["document_id"] != document_id
    assert second.json()["title"] == "docs/setup/local-setup.md"
    assert second.json()["latest_version"]["revision_no"] == 1

    listing = await client.get(
        f"/api/v1/knowledge-documents/pm/projects/{project_id}", headers=headers
    )
    docs = listing.json()
    assert len(docs) == 2
    titles = {d["title"] for d in docs}
    assert titles == {"old-setup.md", "docs/setup/local-setup.md"}
    assert all(d["document_category"] == "SETUP" for d in docs)


@pytest.mark.asyncio
async def test_upload_same_title_same_category_reuses_document_new_version(client, test_data, admin_id):
    """Title trùng trong cùng category vẫn phải tái sử dụng đúng document cũ, chỉ tạo version mới
    (hành vi 'sửa/thêm bản mới của cùng tài liệu' — khác với title khác ở test phía trên)."""
    project_id = await _create_project(client, test_data, admin_id)
    headers = {"X-User-Id": str(admin_id)}

    first = await client.post(
        f"/api/v1/knowledge-documents/pm/projects/{project_id}/upload",
        headers=headers,
        data={"category": "SETUP", "title": "local-setup.md"},
        files={"file": ("local-setup.md", b"ban 1", "text/markdown")},
    )
    assert first.status_code == 201
    document_id = first.json()["document_id"]

    second = await client.post(
        f"/api/v1/knowledge-documents/pm/projects/{project_id}/upload",
        headers=headers,
        data={"category": "SETUP", "title": "local-setup.md"},
        files={"file": ("local-setup.md", b"ban 2 noi dung khac", "text/markdown")},
    )
    assert second.status_code == 201
    assert second.json()["document_id"] == document_id
    assert second.json()["latest_version"]["revision_no"] == 2

    listing = await client.get(
        f"/api/v1/knowledge-documents/pm/projects/{project_id}", headers=headers
    )
    docs = listing.json()
    assert len(docs) == 1
    assert docs[0]["latest_version"]["revision_no"] == 2


@pytest.mark.asyncio
async def test_scan_sample_repo_excludes_junk_and_builds_coverage(client, test_data, admin_id):
    assert SAMPLE_REPO_DIR.exists(), "Cần có docs/PM/Phase-3/sample-repo/ (fixture Phase 3)"
    project_id = await _create_project(client, test_data, admin_id)
    headers = {"X-User-Id": str(admin_id)}

    candidate_paths = [
        "README.md",
        "docs/architecture/system-design.md",
        "docs/setup/local-setup.md",
        "docs/access/security-guide.md",
        "docs/codebase-guide.md",
        "notes-final.md",
        ".env",
        ".env.example",
        "app/main.py",
        "node_modules/fake-pkg/index.js",
    ]
    files = []
    for relative_path in candidate_paths:
        full_path = SAMPLE_REPO_DIR / relative_path
        assert full_path.exists(), f"Fixture thiếu file {relative_path}"
        files.append(("files", (relative_path, full_path.read_bytes(), "application/octet-stream")))

    response = await client.post(
        f"/api/v1/knowledge-documents/pm/projects/{project_id}/scan", headers=headers, files=files
    )
    assert response.status_code == 200
    report = response.json()

    candidate_paths_in_report = {c["relative_path"] for c in report["candidates"]}
    # Loại đúng: code (.py), node_modules/*, .env, .env.example (không thuộc đuôi tài liệu).
    assert "app/main.py" not in candidate_paths_in_report
    assert "node_modules/fake-pkg/index.js" not in candidate_paths_in_report
    assert ".env" not in candidate_paths_in_report
    assert ".env.example" not in candidate_paths_in_report

    # Giữ đúng: 5 tài liệu chuẩn + đúng 1 case biên (notes-final.md — tên sai convention).
    assert "README.md" in candidate_paths_in_report
    assert "docs/architecture/system-design.md" in candidate_paths_in_report
    assert "notes-final.md" in candidate_paths_in_report

    statuses = {c["relative_path"]: c["status"] for c in report["candidates"]}
    categories = {c["relative_path"]: c["suggested_category"] for c in report["candidates"]}
    assert statuses["README.md"] == "FOUND"
    assert statuses["docs/architecture/system-design.md"] == "FOUND"
    # notes-final.md tên không nói lên gì, nhưng nội dung khớp SETUP -> vẫn phải nhận diện được
    # đúng bằng content-based classification (không cần AI, xem repo_scanner_service._classify_by_content).
    assert statuses["notes-final.md"] == "FOUND"
    assert categories["notes-final.md"] == "SETUP"

    assert report["missing_categories"] == []

    scan_session_id = report["scan_session_id"]

    def _candidate_id(relative_path: str) -> str:
        return next(c["candidate_id"] for c in report["candidates"] if c["relative_path"] == relative_path)

    import_response = await client.post(
        f"/api/v1/knowledge-documents/pm/projects/{project_id}/scan/{scan_session_id}/import",
        headers=headers,
        json={
            "selections": [
                {
                    "candidate_id": _candidate_id("README.md"),
                    "include": True,
                    "category": "OVERVIEW",
                },
                {
                    "candidate_id": _candidate_id("docs/architecture/system-design.md"),
                    "include": True,
                    "category": "ARCHITECTURE",
                },
                {
                    "candidate_id": _candidate_id("notes-final.md"),
                    "include": True,
                    "category": "SETUP",
                },
            ],
        },
    )
    assert import_response.status_code == 200
    imported = import_response.json()
    assert len(imported) == 3
    imported_categories = {d["document_category"] for d in imported}
    assert imported_categories == {"OVERVIEW", "ARCHITECTURE", "SETUP"}
    for doc in imported:
        assert doc["latest_version"]["status"] == "ACTIVE"

    listing = await client.get(
        f"/api/v1/knowledge-documents/pm/projects/{project_id}", headers=headers
    )
    assert listing.status_code == 200
    assert len(listing.json()) == 3
