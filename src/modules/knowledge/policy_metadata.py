"""Canonical parsing and identity helpers for policy source documents."""

from __future__ import annotations

import re
from datetime import date, datetime

VERSION_EFFECTIVE_DATE_RE = re.compile(
    r"(?im)^\s*-\s*\*\*Phiên bản:\*\*\s*(?P<version>[^\r\n]*?)\s*[—-]\s*"
    r"(?:Ngày hiệu lực|Hiệu lực):\s*(?P<effective_date>[^\r\n]+)"
)


def normalize_policy_source_key(document_code: str) -> str:
    """Return the stable, case-insensitive policy identity used by persistence."""
    source_key = document_code.strip().upper()
    if not source_key:
        raise ValueError("document_code must not be empty")
    return source_key


def parse_policy_version_metadata(markdown: str) -> tuple[str, date]:
    """Extract the source version label and effective date from the header."""
    match = VERSION_EFFECTIVE_DATE_RE.search(markdown)
    if not match:
        raise ValueError("Policy source is missing '- **Phiên bản:** ... — Ngày hiệu lực: ...'")
    version = match.group("version").strip()
    raw_date = match.group("effective_date").strip()
    if not version:
        raise ValueError("Policy source version must not be empty")
    try:
        return version, datetime.strptime(raw_date, "%d/%m/%Y").date()
    except ValueError as exc:
        raise ValueError(f"Unsupported effective date: {raw_date!r}; expected DD/MM/YYYY") from exc
