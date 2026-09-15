"""Lõi UC-04 — quét folder dự án PM chọn (đã lọc sẵn ở client theo đúng bộ lọc dưới đây, server lọc
lại lần nữa vì không tin tưởng tuyệt đối client), phân loại từng file ứng viên vào 1 trong 5
DocumentCategory (khớp Master Template), phát hiện thiếu/trùng lặp, build Coverage Report.

Không có bước "giải nén ZIP" — PM chọn thẳng folder qua <input webkitdirectory>, mỗi file gửi lên
kèm đường dẫn tương đối (xem docs/PM/Phase-3/plan-phase3-documents.md mục B2).
"""

from __future__ import annotations

import asyncio
import enum
import hashlib
import json
import logging
import math
import re
import time
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path

from src.config import get_settings
from src.infrastructure.ai.langchain_llm import get_classifier_llm
from src.model.enums import DocumentCategory

logger = logging.getLogger(__name__)

CANDIDATE_EXTENSIONS = {".md", ".txt", ".pdf", ".docx"}
EXCLUDED_DIR_NAMES = {".git", "node_modules", "dist", "build", ".next", "__pycache__", ".venv"}
SENSITIVE_NAME_KEYWORDS = ("secret", "token", "password")
SENSITIVE_EXTENSIONS = {".pem", ".key"}

MAX_TOTAL_BYTES = 100 * 1024 * 1024
MAX_FILE_COUNT = 500
MAX_SINGLE_FILE_BYTES = 25 * 1024 * 1024
CONTENT_PEEK_CHARS = 2000
SCAN_SESSION_TTL_SECONDS = 30 * 60

REQUIRED_CATEGORIES: list[DocumentCategory] = [
    DocumentCategory.OVERVIEW,
    DocumentCategory.ARCHITECTURE,
    DocumentCategory.SETUP,
    DocumentCategory.ACCESS_SECURITY,
    DocumentCategory.CODEBASE_GUIDE,
]

_CATEGORY_KEYWORDS: dict[DocumentCategory, list[str]] = {
    DocumentCategory.OVERVIEW: ["overview", "readme", "gioi thieu", "tong quan", "introduction"],
    DocumentCategory.ARCHITECTURE: [
        "architecture", "system design", "system-design", "kien truc", "thiet ke he thong",
    ],
    DocumentCategory.SETUP: [
        "setup", "install", "installation", "getting started", "quickstart", "local-setup",
        "cai dat", "chay local", "pip install", "virtualenv", "uvicorn",
    ],
    DocumentCategory.ACCESS_SECURITY: [
        "access", "security", "secret", "permission", "quyen truy cap", "bao mat", "quyen han",
    ],
    DocumentCategory.CODEBASE_GUIDE: [
        "codebase", "code guide", "structure", "entry point", "huong dan ma nguon",
        "cau truc thu muc", "codebase-guide",
    ],
}

_STALE_STEM_WORDS = {"old", "new", "final", "draft", "copy", "backup", "bak", "tmp", "v1", "v2"}


class CandidateStatus(enum.StrEnum):
    FOUND = "FOUND"
    UNCLASSIFIED = "UNCLASSIFIED"
    DUPLICATE_OR_STALE = "DUPLICATE_OR_STALE"


@dataclass
class ScanCandidate:
    candidate_id: str
    relative_path: str
    filename: str
    size_bytes: int
    checksum: str
    suggested_category: DocumentCategory | None
    confidence: float
    reason: str
    status: CandidateStatus


@dataclass
class CoverageReport:
    candidates: list[ScanCandidate]
    missing_categories: list[DocumentCategory]


@dataclass
class ScanSession:
    scan_session_id: str
    project_id: int
    created_at: float
    candidates: dict[str, ScanCandidate]
    file_bytes: dict[str, bytes]


_SCAN_SESSIONS: dict[str, ScanSession] = {}


def _normalize_text(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without_marks.lower()


def _is_excluded_path(relative_path: str) -> bool:
    parts = Path(relative_path).parts
    return any(part in EXCLUDED_DIR_NAMES for part in parts[:-1])


def _is_sensitive_filename(filename: str) -> bool:
    lower = filename.lower()
    if lower == ".env":
        return True
    if lower == ".env.example":
        return False
    if Path(lower).suffix in SENSITIVE_EXTENSIONS:
        return True
    return any(keyword in lower for keyword in SENSITIVE_NAME_KEYWORDS)


def is_candidate_file(relative_path: str) -> bool:
    """Đúng bộ lọc dùng ở cả client (JS, trước khi upload) lẫn server (double-check) — xem plan."""
    filename = Path(relative_path).name
    extension = Path(filename).suffix.lower()
    if extension not in CANDIDATE_EXTENSIONS:
        return False
    if _is_excluded_path(relative_path):
        return False
    if _is_sensitive_filename(filename):
        return False
    return True


def _normalized_stem(filename: str) -> str:
    stem = Path(filename).stem.lower()
    parts = re.split(r"[-_\s]+", stem)
    kept = [p for p in parts if p not in _STALE_STEM_WORDS and not p.isdigit()]
    return "-".join(kept) if kept else stem


def _match_keywords(text: str, keywords: list[str]) -> str | None:
    normalized = _normalize_text(text)
    for keyword in keywords:
        if keyword in normalized:
            return keyword
    return None


def _classify_by_path_or_filename(relative_path: str) -> tuple[DocumentCategory, float, str] | None:
    path_without_filename = str(Path(relative_path).parent)
    for category in REQUIRED_CATEGORIES:
        keyword = _match_keywords(path_without_filename, _CATEGORY_KEYWORDS[category])
        if keyword:
            return category, 0.95, f"đường dẫn chứa từ khoá '{keyword}'"
    filename_stem = Path(relative_path).stem
    for category in REQUIRED_CATEGORIES:
        keyword = _match_keywords(filename_stem, _CATEGORY_KEYWORDS[category])
        if keyword:
            return category, 0.85, f"tên file chứa từ khoá '{keyword}'"
    return None


def _classify_by_content(content_head: str) -> tuple[DocumentCategory, float, str] | None:
    normalized = _normalize_text(content_head)
    scores: dict[DocumentCategory, int] = {}
    for category, keywords in _CATEGORY_KEYWORDS.items():
        count = sum(normalized.count(keyword) for keyword in keywords)
        if count > 0:
            scores[category] = count
    if not scores:
        return None
    best_category = max(scores, key=lambda c: scores[c])
    return best_category, 0.6, "nội dung chứa từ khoá liên quan"


def _parse_ai_classification(text: str) -> tuple[DocumentCategory | None, float, str]:
    category_str, separator, confidence_str = text.strip().partition("|")
    if not separator or not confidence_str.strip():
        raise ValueError("missing CATEGORY|confidence separator")
    category_str = category_str.strip().upper()
    if category_str == "UNCLASSIFIED":
        return None, 0.0, "AI (DeepSeek) không xác định được category"
    valid_categories = {category.value for category in REQUIRED_CATEGORIES}
    if category_str not in valid_categories:
        raise ValueError("unknown category")
    confidence = float(confidence_str.strip())
    if not math.isfinite(confidence):
        raise ValueError("confidence must be finite")
    return (
        DocumentCategory(category_str),
        min(1.0, max(0.0, confidence)),
        "AI (DeepSeek) phân loại",
    )


async def _classify_by_ai(
    filename: str,
    content_head: str,
    semaphore: asyncio.Semaphore,
) -> tuple[DocumentCategory | None, float, str]:
    options = ", ".join(c.value for c in REQUIRED_CATEGORIES)
    prompt = (
        "Bạn là bộ phân loại tài liệu dự án phần mềm. Chỉ trả lời đúng 1 dòng theo định dạng "
        "'CATEGORY|confidence' (confidence là số 0.0-1.0), CATEGORY là 1 trong: "
        f"{options}, UNCLASSIFIED nếu không chắc.\n\n"
        f"Tên file: {filename}\nNội dung (đoạn đầu):\n{content_head[:CONTENT_PEEK_CHARS]}"
    )
    try:
        async with semaphore:
            response = await get_classifier_llm().ainvoke(prompt)
        return _parse_ai_classification(str(response.content))
    except ValueError:
        logger.warning(
            json.dumps(
                {
                    "event": "repo_scanner.deepseek_invalid_response",
                    "filename_fingerprint": hashlib.sha256(filename.encode("utf-8")).hexdigest()[:12],
                },
                sort_keys=True,
            )
        )
        return None, 0.0, "AI (DeepSeek) trả về không hợp lệ, để PM tự chọn"
    except Exception as exc:  # noqa: BLE001 — AI lỗi/timeout không được chặn luồng quét
        logger.warning(
            json.dumps(
                {
                    "event": "repo_scanner.deepseek_failed",
                    "error_type": type(exc).__name__,
                    "filename_fingerprint": hashlib.sha256(filename.encode("utf-8")).hexdigest()[:12],
                },
                sort_keys=True,
            )
        )
        return None, 0.0, "AI (DeepSeek) lỗi/timeout, để PM tự chọn"


async def classify_candidate(
    relative_path: str,
    content: bytes,
    semaphore: asyncio.Semaphore | None = None,
) -> tuple[DocumentCategory | None, float, str]:
    matched = _classify_by_path_or_filename(relative_path)
    if matched:
        return matched

    extension = Path(relative_path).suffix.lower()
    if extension in (".md", ".txt"):
        try:
            text_head = content[:CONTENT_PEEK_CHARS].decode("utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            text_head = ""
        matched = _classify_by_content(text_head)
        if matched:
            return matched
        limiter = semaphore or asyncio.Semaphore(get_settings().deepseek_classifier_max_concurrency)
        return await _classify_by_ai(Path(relative_path).name, text_head, limiter)

    # .pdf/.docx: MVP không extract text nhị phân để phân loại theo nội dung (thuộc phạm vi TV3
    # extract text sau này) — chỉ dựa path/filename ở trên, không có thì để PM tự chọn.
    return None, 0.0, "Không đọc được nội dung nhị phân, để PM tự chọn category"


async def build_coverage_report(
    files: list[tuple[str, bytes]], existing_checksums: set[str]
) -> tuple[str, CoverageReport, dict[str, bytes]]:
    """files: [(relative_path, content_bytes), ...] đã được lọc bởi is_candidate_file() ở caller.
    Trả về (scan_session_id, CoverageReport, {candidate_id: content_bytes})."""
    if len(files) > MAX_FILE_COUNT:
        raise ValueError(f"Quá nhiều file ứng viên ({len(files)} > {MAX_FILE_COUNT})")
    total_bytes = sum(len(content) for _, content in files)
    if total_bytes > MAX_TOTAL_BYTES:
        raise ValueError(f"Tổng dung lượng file ứng viên quá lớn ({total_bytes} > {MAX_TOTAL_BYTES})")
    for relative_path, content in files:
        if len(content) > MAX_SINGLE_FILE_BYTES:
            raise ValueError(f"File '{relative_path}' vượt quá {MAX_SINGLE_FILE_BYTES} bytes")

    settings = get_settings()
    semaphore = asyncio.Semaphore(settings.deepseek_classifier_max_concurrency)
    # Bound the complete interactive scan, not only each provider call. Queued AI fallbacks can
    # otherwise multiply the per-call timeout and outlive the frontend proxy. Deterministic
    # path/content matches still finish immediately; candidates left after the deadline remain
    # available for the PM to classify manually.
    tasks = [
        asyncio.create_task(classify_candidate(relative_path, content, semaphore))
        for relative_path, content in files
    ]
    done, pending = await asyncio.wait(
        tasks, timeout=settings.deepseek_classifier_timeout_seconds
    )
    if pending:
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

    classifications: list[tuple[DocumentCategory | None, float, str]] = []
    for task in tasks:
        if task in done and not task.cancelled():
            classifications.append(task.result())
        else:
            classifications.append(
                (None, 0.0, "AI (DeepSeek) quá thời gian, để PM tự chọn category")
            )

    candidates: list[ScanCandidate] = []
    file_bytes: dict[str, bytes] = {}
    checksum_to_candidate_ids: dict[str, list[str]] = {}
    stem_to_candidate_ids: dict[str, list[str]] = {}

    for (relative_path, content), (category, confidence, reason) in zip(
        files, classifications, strict=True
    ):
        candidate_id = hashlib.sha1(relative_path.encode("utf-8")).hexdigest()[:12]
        checksum = hashlib.sha256(content).hexdigest()
        status = CandidateStatus.FOUND if category else CandidateStatus.UNCLASSIFIED

        if checksum in existing_checksums:
            status = CandidateStatus.DUPLICATE_OR_STALE
            reason = "checksum trùng với tài liệu đã có trong dự án"

        candidate = ScanCandidate(
            candidate_id=candidate_id,
            relative_path=relative_path,
            filename=Path(relative_path).name,
            size_bytes=len(content),
            checksum=checksum,
            suggested_category=category,
            confidence=confidence,
            reason=reason,
            status=status,
        )
        candidates.append(candidate)
        file_bytes[candidate_id] = content
        checksum_to_candidate_ids.setdefault(checksum, []).append(candidate_id)
        stem = _normalized_stem(candidate.filename)
        stem_to_candidate_ids.setdefault(stem, []).append(candidate_id)

    candidate_by_id = {c.candidate_id: c for c in candidates}
    for ids in checksum_to_candidate_ids.values():
        if len(ids) > 1:
            for candidate_id in ids:
                candidate_by_id[candidate_id].status = CandidateStatus.DUPLICATE_OR_STALE
                candidate_by_id[candidate_id].reason = "trùng nội dung (checksum) với file khác trong lượt quét"
    for ids in stem_to_candidate_ids.values():
        if len(ids) > 1:
            for candidate_id in ids:
                if candidate_by_id[candidate_id].status == CandidateStatus.FOUND:
                    candidate_by_id[candidate_id].status = CandidateStatus.DUPLICATE_OR_STALE
                    candidate_by_id[candidate_id].reason = (
                        "tên file gần giống file khác trong lượt quét, có thể là bản trùng/cũ"
                    )

    found_categories = {c.suggested_category for c in candidates if c.status == CandidateStatus.FOUND}
    missing_categories = [c for c in REQUIRED_CATEGORIES if c not in found_categories]

    scan_session_id = uuid.uuid4().hex
    _SCAN_SESSIONS[scan_session_id] = ScanSession(
        scan_session_id=scan_session_id,
        project_id=0,
        created_at=time.time(),
        candidates=candidate_by_id,
        file_bytes=file_bytes,
    )
    return scan_session_id, CoverageReport(candidates=candidates, missing_categories=missing_categories), file_bytes


def _prune_expired_sessions() -> None:
    now = time.time()
    expired = [
        sid for sid, session in _SCAN_SESSIONS.items()
        if now - session.created_at > SCAN_SESSION_TTL_SECONDS
    ]
    for sid in expired:
        del _SCAN_SESSIONS[sid]


def set_scan_session_project(scan_session_id: str, project_id: int) -> None:
    session = _SCAN_SESSIONS.get(scan_session_id)
    if session:
        session.project_id = project_id


def get_scan_session(scan_session_id: str) -> ScanSession | None:
    _prune_expired_sessions()
    return _SCAN_SESSIONS.get(scan_session_id)


def cleanup_scan_session(scan_session_id: str) -> None:
    _SCAN_SESSIONS.pop(scan_session_id, None)
