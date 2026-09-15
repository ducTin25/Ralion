"""Deterministic, auditable category classification for PROJECT documents.

The classifier deliberately has no fallback category.  A document without
enough unambiguous evidence must be reviewed instead of becoming OVERVIEW.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath

from src.model.enums import DocumentCategory

CLASSIFIER_VERSION = "project-category-rules-v1"
MIN_SCORE = 3
MIN_MARGIN = 2


class ClassificationStatus(StrEnum):
    CLASSIFIED = "CLASSIFIED"
    AMBIGUOUS = "AMBIGUOUS"

_SIGNALS: dict[DocumentCategory, tuple[str, ...]] = {
    DocumentCategory.SETUP: (
        "setup",
        "install",
        "installation",
        "getting started",
        "prerequisites",
        "local development",
        "bootstrap",
        "build locally",
    ),
    DocumentCategory.ACCESS_SECURITY: (
        "security",
        "access",
        "permission",
        "authentication",
        "authorization",
        "credential",
        "secret",
        "rbac",
    ),
    DocumentCategory.ARCHITECTURE: (
        "architecture",
        "design",
        "system design",
        "architectural decision",
        "adr",
    ),
    DocumentCategory.CODEBASE_GUIDE: (
        "codebase",
        "repository structure",
        "directory structure",
        "module",
        "package",
        "internals",
        "source layout",
    ),
    DocumentCategory.CONVENTION: (
        "convention",
        "coding style",
        "style guide",
        "naming",
        "contribution guideline",
        "testing convention",
        "commit convention",
    ),
    DocumentCategory.FIRST_TASK: (
        "first task",
        "first contribution",
        "first issue",
        "beginner task",
        "good first issue",
        "starter task",
    ),
    DocumentCategory.OVERVIEW: (
        "overview",
        "introduction",
        "about",
        "project overview",
        "repository root readme",
    ),
}


@dataclass(frozen=True)
class CategoryClassification:
    category: DocumentCategory | None
    confidence: float
    matched_signals: tuple[str, ...]
    status: ClassificationStatus
    classifier_version: str = CLASSIFIER_VERSION

    @property
    def review_reason(self) -> str:
        signals = ", ".join(self.matched_signals) or "no matching signals"
        return f"{self.status.lower()} by {self.classifier_version}: {signals}"


def _normalise(value: str) -> str:
    value = value.replace("\\", "/").lower()
    value = "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    )
    return re.sub(r"\s+", " ", re.sub(r"[-_]", " ", value)).strip()


def _match(value: str, keyword: str) -> bool:
    if " " in keyword:
        return keyword in value
    return re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", value) is not None


def _heading_tree(markdown: str) -> tuple[str, ...]:
    return tuple(
        match.group(1).strip()
        for match in re.finditer(r"^#{1,2}\s+(.+?)\s*$", markdown, re.MULTILINE)
    )


def classify_project_document(*, source_path: str, title: str, content: str) -> CategoryClassification:
    """Classify using only path, title, headings and document text.

    Weights are deliberately fixed and versioned: title/filename=3,
    path=2, H1/H2 headings=2, body=1.
    """
    source_path = _normalise(source_path)
    path = PurePosixPath(source_path)
    filename = _normalise(path.name)
    parent = _normalise(str(path.parent)) if str(path.parent) != "." else ""
    title = _normalise(title)
    headings = tuple(_normalise(heading) for heading in _heading_tree(content))
    body = _normalise(content)
    scores = {category: 0 for category in DocumentCategory}
    matched: dict[DocumentCategory, list[str]] = {category: [] for category in DocumentCategory}

    for category, keywords in _SIGNALS.items():
        for label, value, weight in (
            ("title", title, 3),
            ("filename", filename, 3),
            ("path", parent, 2),
        ):
            keyword = next((item for item in keywords if _match(value, item)), None)
            if keyword:
                scores[category] += weight
                matched[category].append(f"{label}:{keyword}")
        for heading in headings:
            keyword = next((item for item in keywords if _match(heading, item)), None)
            if keyword:
                scores[category] += 2
                matched[category].append(f"heading:{keyword}")
        keyword = next((item for item in keywords if _match(body, item)), None)
        if keyword:
            scores[category] += 1
            matched[category].append(f"body:{keyword}")

    if path.parent == PurePosixPath(".") and filename in {"readme", "readme.md"}:
        scores[DocumentCategory.OVERVIEW] += 3
        matched[DocumentCategory.OVERVIEW].append("filename:repository root readme")

    ranked = sorted(DocumentCategory, key=lambda category: (-scores[category], category.value))
    best, runner_up = ranked[0], ranked[1]
    best_score, runner_up_score = scores[best], scores[runner_up]
    confidence = 0.0 if best_score == 0 else min(
        0.99, round(0.5 + 0.08 * best_score + 0.03 * (best_score - runner_up_score), 2)
    )
    if best_score < MIN_SCORE or best_score - runner_up_score < MIN_MARGIN:
        signals = tuple(matched[best] + matched[runner_up])
        return CategoryClassification(None, confidence, signals, ClassificationStatus.AMBIGUOUS)
    return CategoryClassification(best, confidence, tuple(matched[best]), ClassificationStatus.CLASSIFIED)
