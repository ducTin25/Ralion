"""Structured logging cho pipeline sinh Candidate Plan.

Nguyên tắc (SoT §19 "không log token, password, secrets hoặc nội dung nhạy cảm"): chỉ log SỐ ĐO và
ID, tuyệt đối không log nội dung tài liệu / nội dung task sinh ra. Muốn xem nội dung thì mở plan
trong UI hoặc xem trace Langfuse (nơi có kiểm soát truy cập), không phải đọc file log.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("plan_generation")

# Field được phép log. Whitelist chứ không blacklist — thêm field mới phải khai báo có ý thức,
# tránh vô tình log nhầm nội dung tài liệu khi ai đó thêm tham số sau này.
_ALLOWED_FIELDS = frozenset(
    {
        "event",
        "correlation_id",
        "job_id",
        "plan_id",
        "membership_id",
        "project_id",
        "template_version_id",
        "step",
        "status",
        "duration_ms",
        "task_count",
        "document_count",
        "policy_document_count",
        "chunk_count",
        "source_count",
        "warning_count",
        "ai_generated_count",
        "cloned_from_plan_id",
        "error_type",
    }
)


def log_step_event(**fields: Any) -> None:
    """Ghi 1 dòng JSON. Field lạ bị bỏ im lặng — an toàn hơn là log ra rồi mới phát hiện rò rỉ."""
    safe = {key: value for key, value in fields.items() if key in _ALLOWED_FIELDS and value is not None}
    logger.info(json.dumps(safe, ensure_ascii=False, sort_keys=True))
