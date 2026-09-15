"""Test repo_scanner_service — lõi UC-04. Test rule-based classification trực tiếp (không gọi AI
qua mạng, tránh phụ thuộc network/API key trong CI) bằng cách chọn nội dung khớp rule content-based
đã đủ, hoặc monkeypatch get_classifier_llm để test riêng đường lỗi AI."""

import pytest

from src.model.enums import DocumentCategory
from src.services import repo_scanner_service
from src.services.repo_scanner_service import CandidateStatus


def test_is_candidate_file_extension_allowlist():
    assert repo_scanner_service.is_candidate_file("README.md") is True
    assert repo_scanner_service.is_candidate_file("docs/setup.txt") is True
    assert repo_scanner_service.is_candidate_file("app/main.py") is False
    assert repo_scanner_service.is_candidate_file("app/routes.js") is False


def test_is_candidate_file_excludes_directories():
    assert repo_scanner_service.is_candidate_file(".git/HEAD") is False
    assert repo_scanner_service.is_candidate_file("node_modules/fake-pkg/README.md") is False
    assert repo_scanner_service.is_candidate_file("dist/output.md") is False
    assert repo_scanner_service.is_candidate_file("app/__pycache__/notes.md") is False


def test_is_candidate_file_excludes_sensitive_names():
    # .env/.env.example không thuộc đuôi tài liệu (.md/.txt/.pdf/.docx) nên đã bị loại từ bước lọc
    # đuôi file, trước cả khi chạm tới rule tên nhạy cảm — kiểm tra thẳng rule tên nhạy cảm riêng.
    assert repo_scanner_service._is_sensitive_filename(".env") is True
    assert repo_scanner_service._is_sensitive_filename(".env.example") is False
    assert repo_scanner_service.is_candidate_file("secret-keys.txt") is False
    assert repo_scanner_service.is_candidate_file("id_rsa.pem") is False


@pytest.mark.asyncio
async def test_classify_by_path_keyword():
    category, confidence, reason = await repo_scanner_service.classify_candidate(
        "docs/architecture/system-design.md", b"noi dung bat ky"
    )
    assert category == DocumentCategory.ARCHITECTURE
    assert confidence >= 0.9
    assert "duong dan" in reason or "đường dẫn" in reason


@pytest.mark.asyncio
async def test_classify_by_filename_keyword():
    category, _confidence, _reason = await repo_scanner_service.classify_candidate(
        "local-setup.md", b"noi dung bat ky khong lien quan"
    )
    assert category == DocumentCategory.SETUP


@pytest.mark.asyncio
async def test_classify_by_content_keyword_when_path_and_filename_unclear():
    content = b"Cai dat Python, tao virtualenv, pip install -r requirements.txt roi chay uvicorn"
    category, confidence, _reason = await repo_scanner_service.classify_candidate(
        "notes-final.md", content
    )
    assert category == DocumentCategory.SETUP
    assert confidence == pytest.approx(0.6)


@pytest.mark.asyncio
async def test_classify_falls_back_to_unclassified_when_ai_fails(monkeypatch):
    def _boom():
        raise RuntimeError("no network in test")

    monkeypatch.setattr(repo_scanner_service, "get_classifier_llm", _boom)
    category, confidence, reason = await repo_scanner_service.classify_candidate(
        "CONTRIBUTING.md", b"quy tac commit va pull request, khong lien quan toi 5 category"
    )
    assert category is None
    assert confidence == 0.0
    assert "AI" in reason


@pytest.mark.asyncio
async def test_build_coverage_report_marks_missing_categories():
    files = [
        ("README.md", b"Todo API tong quan du an"),
        ("docs/setup/local-setup.md", b"huong dan cai dat"),
    ]
    _session_id, report, _file_bytes = await repo_scanner_service.build_coverage_report(
        files, existing_checksums=set()
    )

    found = {c.suggested_category for c in report.candidates if c.status == CandidateStatus.FOUND}
    assert DocumentCategory.OVERVIEW in found
    assert DocumentCategory.SETUP in found
    assert DocumentCategory.ARCHITECTURE in report.missing_categories
    assert DocumentCategory.ACCESS_SECURITY in report.missing_categories
    assert DocumentCategory.CODEBASE_GUIDE in report.missing_categories


@pytest.mark.asyncio
async def test_build_coverage_report_detects_duplicate_checksum_against_existing():
    content = b"noi dung file setup"
    existing_checksum = repo_scanner_service.hashlib.sha256(content).hexdigest()
    files = [("docs/setup/local-setup.md", content)]

    _session_id, report, _file_bytes = await repo_scanner_service.build_coverage_report(
        files, existing_checksums={existing_checksum}
    )
    assert report.candidates[0].status == CandidateStatus.DUPLICATE_OR_STALE


@pytest.mark.asyncio
async def test_build_coverage_report_detects_duplicate_stem_within_scan():
    files = [
        ("old-setup.md", b"ban setup cu"),
        ("setup.md", b"ban setup moi hon"),
    ]
    _session_id, report, _file_bytes = await repo_scanner_service.build_coverage_report(
        files, existing_checksums=set()
    )
    statuses = {c.relative_path: c.status for c in report.candidates}
    assert statuses["old-setup.md"] == CandidateStatus.DUPLICATE_OR_STALE
    assert statuses["setup.md"] == CandidateStatus.DUPLICATE_OR_STALE


@pytest.mark.asyncio
async def test_build_coverage_report_rejects_too_many_files():
    files = [(f"docs/file-{i}.md", b"x") for i in range(repo_scanner_service.MAX_FILE_COUNT + 1)]
    with pytest.raises(ValueError):
        await repo_scanner_service.build_coverage_report(files, existing_checksums=set())


@pytest.mark.asyncio
async def test_build_coverage_report_rejects_oversized_total():
    big_content = b"x" * (repo_scanner_service.MAX_TOTAL_BYTES + 1)
    files = [("docs/big.md", big_content)]
    with pytest.raises(ValueError):
        await repo_scanner_service.build_coverage_report(files, existing_checksums=set())


@pytest.mark.asyncio
async def test_scan_session_lifecycle():
    files = [("README.md", b"tong quan")]
    scan_session_id, _report, _file_bytes = await repo_scanner_service.build_coverage_report(
        files, existing_checksums=set()
    )
    repo_scanner_service.set_scan_session_project(scan_session_id, project_id=42)

    session = repo_scanner_service.get_scan_session(scan_session_id)
    assert session is not None
    assert session.project_id == 42

    repo_scanner_service.cleanup_scan_session(scan_session_id)
    assert repo_scanner_service.get_scan_session(scan_session_id) is None
