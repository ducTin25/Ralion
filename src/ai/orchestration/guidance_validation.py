"""Deterministic, retrieval-free validation of generated general-guidance items.

F5_BOUNDED_GENERAL_KNOWLEDGE_SPEC.md §8. Same discipline as `claim_validation.py`: no DB, no
retrieval-engine, or LLM dependency, so it cannot widen the evidence boundary. Pure function;
the caller (`AnswerGenerator.generate`) decides policy from the structured result.

§8.1 explains why `claim_validation._hard_tokens` is *not* reused wholesale as an absolute
containment rule here: it both over-rejects (`lexical_identifiers` flags perfectly generic
compound tokens like `docker-compose`) and under-rejects (the canonical `alembic upgrade head`
failure case produces zero hard tokens at all). Instead, value tokens (date/number/version --
always a factual assertion) are rejected when ungrounded (R3), while plain identifier tokens are
only risk-flagged (R4) -- the same "deterministic containment is not strong enough to reject on
its own" reasoning `claim_validation._risk_flags` already applies to `_NOVEL_IDENTIFIER`, reused
here with more force since generic guidance *must* be able to name common tools.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from src.ai.orchestration.answer_generator import GuidanceKind, GuidanceRef
from src.ai.orchestration.claim_validation import _DATE, _NUMBER, _VERSION
from src.ai.orchestration.quote_anchor import fold
from src.ai.retrieval_engine.chunking_config import load_chunking_config
from src.ai.retrieval_engine.lexical import lexical_identifiers
from src.ai.retrieval_engine.retrieval_engine import RetrievalResult

_VALUE_TOKEN_PATTERNS = (_DATE, _NUMBER, _VERSION)  # imported, not copied -- §8.2 R3
_COMBINING = re.compile(r"[̀-ͯ]")  # Unicode combining diacritical marks block


def _diacritic_folded(text: str) -> str:
    """Case- and diacritic-insensitive comparison key (§8.2 R2). `fold()` in `quote_anchor.py`
    is NFC + casefold only (punctuation/whitespace tolerant, diacritic-*preserving*) -- deixis
    matching needs actual diacritic stripping, which is a different, narrower normalization."""
    text = text.casefold().replace("đ", "d").replace("Đ", "d")
    return _COMBINING.sub("", unicodedata.normalize("NFD", text))


# §8.2 R2: whole-word, closed, case- and diacritic-insensitive bilingual marker list. Catches
# attributive framing ("in this repo, run X"); a bare imperative implicitly about this project
# is NOT caught here -- that residual is a documented, bounded gap (see module docstring §8.2).
_PROJECT_DEIXIS_MARKERS: tuple[str, ...] = (
    # en
    "this repo",
    "this repository",
    "this project",
    "our project",
    "our repo",
    "our repository",
    "our team",
    "our codebase",
    "the project's",
    "we use",
    "we require",
    "you must use",
    # vi
    "repo nay",
    "du an nay",
    "project nay",
    "cua chung ta",
    "cua team",
    "team minh",
    "minh dang dung",
)


def _contains_project_deixis(text: str) -> bool:
    folded = _diacritic_folded(text)
    return any(
        re.search(r"(?<!\w)" + re.escape(marker) + r"(?!\w)", folded)
        for marker in _PROJECT_DEIXIS_MARKERS
    )


def _value_tokens(text: str) -> frozenset[str]:
    tokens: set[str] = set()
    for pattern in _VALUE_TOKEN_PATTERNS:
        tokens.update(pattern.findall(text))
    return frozenset(fold(token) for token in tokens if fold(token))


# Live-observed defect, 2026-08-23 (see CHANGE_LOG.md): a step-by-step guidance item numbered
# "Bước 2: ..." / "Step 2: ..." / a leading "2. " list marker contains a bare digit that
# `_NUMBER` (imported unchanged from claim_validation -- §8.2 R3) matches exactly like a real
# factual value ("PostgreSQL 16"). That digit is formatting, not an assertion about anything, but
# R3 rejected the whole item for it -- in practice destroying almost every multi-step answer, the
# flagship use case this spec exists to serve. Stripped from a GUIDANCE ITEM'S OWN text only,
# immediately before R3's value-token check -- never applied to `question`/evidence text (the
# grounding vocabulary itself is unaffected), and `_DATE`/`_NUMBER`/`_VERSION` themselves are not
# touched, so claim_validation's behaviour for actual claims is untouched.
_STEP_MARKER = re.compile(
    r"\b(?:bước|buoc|step)\s+\d+\s*[:.\)]?|^\s*\d+\s*[.\):]\s+",
    re.IGNORECASE | re.MULTILINE,
)
_BIT_ARCHITECTURE = re.compile(r"\b\d+-bit\b", re.IGNORECASE)


def _strip_structural_numbers(text: str) -> str:
    text = _STEP_MARKER.sub(" ", text)
    return _BIT_ARCHITECTURE.sub(" ", text)


def _identifier_tokens(text: str) -> frozenset[str]:
    return frozenset(fold(token) for token in lexical_identifiers(text).splitlines() if fold(token))


class GeneralKnowledgeConfig:
    """`chat.general_knowledge` in chunking_params.yaml (§5.6). `enabled=False` (default) is the
    master switch -- every BGK code path stays inert regardless of what the interpreter proposes,
    the one-line rollback with no code change."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        max_guidance_items: int = 6,
        guidance_item_max_chars: int = 1200,
        allow_on_partial: bool = True,
        allow_after_insufficient: bool = True,
        generic_token_allowlist: Sequence[str] = (),
    ) -> None:
        self.enabled = enabled
        self.max_guidance_items = max_guidance_items
        self.guidance_item_max_chars = guidance_item_max_chars
        self.allow_on_partial = allow_on_partial
        self.allow_after_insufficient = allow_after_insufficient
        self.generic_token_allowlist = frozenset(
            fold(token) for token in generic_token_allowlist if fold(token)
        )

    @classmethod
    def from_config(cls, config: dict[str, Any] | None = None) -> GeneralKnowledgeConfig:
        resolved = config or load_chunking_config()
        settings = resolved["chat"].get("general_knowledge") or {}
        return cls(
            enabled=bool(settings.get("enabled", False)),
            max_guidance_items=int(settings.get("max_guidance_items", 6)),
            guidance_item_max_chars=int(settings.get("guidance_item_max_chars", 1200)),
            allow_on_partial=bool(settings.get("allow_on_partial", True)),
            allow_after_insufficient=bool(settings.get("allow_after_insufficient", True)),
            generic_token_allowlist=tuple(settings.get("generic_token_allowlist", []) or []),
        )


@dataclass(frozen=True)
class ValidatedGuidance:
    item_index: int
    text: str
    kind: GuidanceKind
    risk_flags: frozenset[str]


@dataclass(frozen=True)
class RejectedGuidance:
    item_index: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class GuidanceValidationResult:
    items: tuple[ValidatedGuidance, ...]
    rejected: tuple[RejectedGuidance, ...]
    had_rejection: bool


def validate_guidance(
    guidance: Sequence[GuidanceRef],
    accepted_evidence: Sequence[RetrievalResult],
    question: str,
    *,
    config: GeneralKnowledgeConfig,
) -> GuidanceValidationResult:
    """Validate each `general_guidance[]` item against §8.2's rules R2-R6. R1 (no citation field
    exists on `GuidanceRef` at all) is structural, guaranteed by the type -- nothing to enforce
    here.

    `accepted_evidence` must be the SAME set passed to generation for this turn (§10.2: dropped
    to `()` on the INSUFFICIENT-recovery branch, making the grounding vocabulary question-only,
    deliberately conservative).
    """
    evidence_text = "\n".join(item.chunk.content for item in accepted_evidence)
    grounding_vocabulary = (
        _value_tokens(question) | _value_tokens(evidence_text) | config.generic_token_allowlist
    )

    bounded = list(guidance)[: config.max_guidance_items]
    overflow = len(guidance) - len(bounded)

    validated: list[ValidatedGuidance] = []
    rejected: list[RejectedGuidance] = []
    had_rejection = False

    for item_index, item in enumerate(bounded):
        text = item.text.strip()
        if not text:
            rejected.append(RejectedGuidance(item_index, ("guidance_empty_text",)))
            had_rejection = True
            continue
        if len(text) > config.guidance_item_max_chars:
            rejected.append(RejectedGuidance(item_index, ("guidance_item_too_long",)))
            had_rejection = True
            continue
        if _contains_project_deixis(text):
            rejected.append(RejectedGuidance(item_index, ("guidance_project_deixis",)))
            had_rejection = True
            continue
        unsupported_values = _value_tokens(_strip_structural_numbers(text)) - grounding_vocabulary
        if unsupported_values:
            rejected.append(
                RejectedGuidance(
                    item_index,
                    (f"guidance_unsupported_value:{','.join(sorted(unsupported_values))}",),
                )
            )
            had_rejection = True
            continue
        risk_flags: set[str] = set()
        if _identifier_tokens(text) - grounding_vocabulary:
            risk_flags.add("guidance_novel_identifier")
        validated.append(
            ValidatedGuidance(
                item_index=item_index, text=text, kind=item.kind, risk_flags=frozenset(risk_flags)
            )
        )

    if overflow > 0:
        had_rejection = True
        for offset in range(overflow):
            rejected.append(RejectedGuidance(len(bounded) + offset, ("guidance_item_limit",)))

    return GuidanceValidationResult(
        items=tuple(validated), rejected=tuple(rejected), had_rejection=had_rejection
    )
