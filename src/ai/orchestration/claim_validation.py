"""Deterministic, retrieval-free validation of generated answer claims.

This module consumes only the evidence accepted by RelevanceGate. It deliberately has no
database, retrieval-engine, or LLM dependency so it cannot widen the evidence boundary.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from src.ai.orchestration.answer_generator import ClaimRef, ClaimSupport, VerifiedCitation
from src.ai.orchestration.quote_anchor import QuoteAnchorIndex, build_index, find_source_span, fold
from src.ai.retrieval_engine.lexical import lexical_identifiers
from src.ai.retrieval_engine.retrieval_engine import RetrievalResult

_DATE = re.compile(r"\b\d{1,4}[/-]\d{1,2}[/-]\d{1,4}\b")
_NUMBER = re.compile(r"(?<![\w.-])\d+(?:[.,]\d+)?%?(?!\w)")
_LIST_ORDINAL = re.compile(r"^\s*(\d+)[.)](?=\s+\S)")
_VERSION = re.compile(r"\bv?\d+(?:\.\d+){1,}\b", re.IGNORECASE)
_NOVEL_IDENTIFIER = re.compile(r"\b[A-Z]{2,}(?:[-_][A-Z0-9]+)*\b")
_ABSOLUTE_MODALITY = re.compile(r"\b(?:always|must|mandatory|mọi|luôn|bắt buộc)\b", re.IGNORECASE)
_PROCEDURE_QUESTION = re.compile(
    r"(?:"
    r"\b(?:từng|các)\s+(?:bước|lệnh)\b|"
    r"\b(?:làm thế nào|làm sao|như thế nào|cách|hướng dẫn)\s+"
    r"(?:để\s+|cách\s+)?(?:chạy|cài|thiết lập|kiểm tra|test)\b|"
    r"\b(?:how\s+(?:do|can|should|to)|exact\s+commands?|steps?|commands?)\b"
    r")",
    re.IGNORECASE,
)
_VAGUE_PROCEDURE_END = re.compile(
    r"(?:"
    r"(?:sau đó\s+)?(?:thực hiện|làm theo)\s+(?:các|những)\s+bước(?:\s+[^.!?;:]+)?|"
    r"(?:then\s+)?(?:follow|perform|complete)\s+(?:the\s+)?"
    r"(?:(?:remaining|following|next)\s+)?(?:setup\s+)?steps?(?:\s+[^.!?;:]+)?"
    r")[.!?]?\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ValidatedClaim:
    claim_index: int
    text: str
    support: ClaimSupport
    citations: tuple[VerifiedCitation, ...]
    risk_flags: frozenset[str]
    validation_notes: tuple[str, ...]


@dataclass(frozen=True)
class RejectedClaim:
    claim_index: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ClaimValidationResult:
    claims: tuple[ValidatedClaim, ...]
    rejected_claims: tuple[RejectedClaim, ...]
    coverage: bool
    had_degradation: bool


def _fold_all(tokens: set[str]) -> frozenset[str]:
    return frozenset(fold(token) for token in tokens if fold(token))


def _numeric_tokens(text: str) -> frozenset[str]:
    """Dates, plain numbers and version strings -- the tokens a user routinely quotes back inside
    their own question ("is the limit really 30 days?"), so an answer echoing them is normal."""
    tokens = set(_DATE.findall(text))
    tokens.update(_NUMBER.findall(text))
    tokens.update(_VERSION.findall(text))
    # A leading ``1.``/``2)`` is list formatting, not an asserted numeric fact.  Keep every
    # other numeric shape (versions, ports, quantities, dates) subject to normal validation.
    if ordinal := _LIST_ORDINAL.match(text):
        tokens.discard(ordinal.group(1))
    return _fold_all(tokens)


# A token with a capital letter that is NOT its first character: MySQL, PostgreSQL, MongoDB,
# GitHub, ChatService. Deliberately NOT "any capitalised word" -- that would fire on every
# sentence-initial word and every Vietnamese proper noun, and the cost of a false positive here is
# a rejected claim (a fallback shown to a user), so this stays the narrowest shape that covers the
# observed failure family. Defined here rather than in `lexical.py`: that module's output is a
# persisted BM25 index field, and widening it would silently change retrieval.
#
# Known, accepted limit: a single-capital product name (Redis, Kafka, Python) is NOT matched, so
# an unsupported assertion about one is not caught deterministically by this validator. That
# residue is covered only by `grounded_answer_prompt_v5._USER_CLAIM_SECTION` (generation-side) and
# is one of the cases a real claim-entailment check (AUDIT F-14) would close. Do not "fix" it by
# matching bare capitalised words.
_CAMEL_ENTITY = re.compile(r"\b[^\W\d_][^\W_]*[A-Z][^\W_]*\b")


def _entity_tokens(text: str) -> frozenset[str]:
    """Identifiers and named entities (product/tool/module names, symbols).

    Split out of `_hard_tokens` on 2026-08-25 (B-07). The old single set was subtracted against
    `evidence | question`, which made the question a *grounding source*: any entity the user
    happened to name became assertable in a cited claim even when no evidence mentioned it. Live
    transcript: asked "why not PostgreSQL or MySQL", the answer asserted "PostgreSQL/MySQL are not
    optimized for metric data" as a claim citing a chunk that never mentions either -- pretrained
    knowledge wearing a citation. The numeric exemption above is kept because the failure mode
    there is the opposite (a legitimate answer restating the asked-about number); an entity has
    no such benign echo when the evidence is silent about it.
    """
    tokens = set(lexical_identifiers(text).splitlines())
    tokens.update(_CAMEL_ENTITY.findall(text))
    return _fold_all(tokens)


def _hard_tokens(text: str) -> frozenset[str]:
    """Both classes together. Kept for callers that need the whole set (see `_risk_flags`)."""
    return _numeric_tokens(text) | _entity_tokens(text)


def _risk_flags(text: str, support: ClaimSupport, distinct_chunk_count: int) -> frozenset[str]:
    flags: set[str] = set()
    if _ABSOLUTE_MODALITY.search(text):
        flags.add("absolute_modality")
    if support is ClaimSupport.INFERRED and distinct_chunk_count >= 2:
        flags.add("inferred_multi_source")
    # Uppercase identifiers without a numeric/version shape are intentionally risk-only: they may
    # be valid acronyms, but deterministic containment is not strong enough to reject on its own.
    if _NOVEL_IDENTIFIER.search(text):
        flags.add("novel_identifier")
    return frozenset(flags)


def is_procedure_question(question: str) -> bool:
    """Whether `question` asks for exact executable steps/commands (§ generation §14, F5 audit
    failure 3). Exported so `AnswerGenerator` can reuse this exact, single-source decision to
    decide whether an incomplete-claim salvage is safe -- a partial sequence of steps/commands is
    unsafe to return truncated, but a partial LIST of ordinary knowledge items is not. Never
    duplicate this regex at a second call site.
    """
    return bool(_PROCEDURE_QUESTION.search(question))


def _is_incomplete_claim(text: str, question: str) -> bool:
    if text.endswith((":", "：")):
        return True
    return is_procedure_question(question) and bool(_VAGUE_PROCEDURE_END.search(text))


def validate_claims(
    claims: Sequence[ClaimRef],
    accepted_evidence: Sequence[RetrievalResult],
    question: str,
) -> ClaimValidationResult:
    """Validate claim anchors and hard tokens against an immutable accepted evidence set.

    Invalid citations and claims are recorded locally rather than raised. The caller decides any
    retry/degradation policy from the structured result; this function never retrieves evidence.
    """
    evidence_by_chunk_id = {item.chunk.chunk_id: item for item in accepted_evidence}
    indexes: dict[int, QuoteAnchorIndex] = {}
    accepted_claims: list[ValidatedClaim] = []
    rejected_claims: list[RejectedClaim] = []
    had_degradation = False

    for claim_index, claim in enumerate(claims):
        text = claim.text.strip()
        reasons: list[str] = []
        if not text:
            rejected_claims.append(RejectedClaim(claim_index, ("empty_claim_text",)))
            continue
        # Claims are rendered as standalone paragraphs. A trailing colon or, for a procedural
        # question, a vague promise to perform/follow unspecified steps certifies an incomplete
        # answer even when the small lead-in itself has a valid citation.
        if _is_incomplete_claim(text, question):
            had_degradation = True
            rejected_claims.append(RejectedClaim(claim_index, ("incomplete_claim_text",)))
            continue
        if not claim.citations:
            rejected_claims.append(RejectedClaim(claim_index, ("claim_has_no_citations",)))
            continue

        verified_citations: list[VerifiedCitation] = []
        for citation in claim.citations:
            evidence = evidence_by_chunk_id.get(citation.chunk_id)
            if evidence is None:
                reasons.append("citation_outside_accepted_evidence")
                had_degradation = True
                continue
            index = indexes.get(citation.chunk_id)
            if index is None:
                index = build_index(evidence.chunk.content)
                indexes[citation.chunk_id] = index
            source_quote = find_source_span(index, citation.quote)
            if source_quote is None:
                reasons.append("citation_anchor_not_found")
                had_degradation = True
                continue
            verified_citations.append(
                VerifiedCitation(
                    chunk_id=citation.chunk_id,
                    quote=source_quote,
                    relevance_score=evidence.dense_score or 0.0,
                    knowledge_domain=evidence.knowledge_domain,
                )
            )

        if not verified_citations:
            had_degradation = True
            rejected_claims.append(
                RejectedClaim(claim_index, tuple(dict.fromkeys([*reasons, "claim_has_no_anchors"])))
            )
            continue

        # Multiple quotes may anchor into the same chunk. Scan each server-owned
        # chunk once for hard tokens instead of multiplying work by citation count.
        cited_chunk_ids = dict.fromkeys(citation.chunk_id for citation in verified_citations)
        evidence_text = "\n".join(
            evidence_by_chunk_id[chunk_id].chunk.content for chunk_id in cited_chunk_ids
        )
        # B-07: the question exempts NUMERIC tokens only. An entity named solely in the question,
        # absent from the cited evidence, can never enter a grounded claim -- the claim is
        # rejected and the turn degrades honestly instead of asserting an uncited fact about it.
        unsupported_tokens = (
            _numeric_tokens(text) - (_numeric_tokens(evidence_text) | _numeric_tokens(question))
        ) | (_entity_tokens(text) - _entity_tokens(evidence_text))
        if unsupported_tokens:
            had_degradation = True
            rejected_claims.append(
                RejectedClaim(
                    claim_index,
                    tuple(
                        dict.fromkeys(
                            [*reasons, f"unsupported_hard_tokens:{','.join(sorted(unsupported_tokens))}"]
                        )
                    ),
                )
            )
            continue

        distinct_chunk_count = len({citation.chunk_id for citation in verified_citations})
        support = claim.support
        if support is ClaimSupport.INFERRED and distinct_chunk_count == 1:
            support = ClaimSupport.DIRECT
            reasons.append("inferred_downgraded_to_direct")
            had_degradation = True
        accepted_claims.append(
            ValidatedClaim(
                claim_index=claim_index,
                text=text,
                support=support,
                citations=tuple(verified_citations),
                risk_flags=_risk_flags(text, support, distinct_chunk_count),
                validation_notes=tuple(dict.fromkeys(reasons)),
            )
        )

    return ClaimValidationResult(
        claims=tuple(accepted_claims),
        rejected_claims=tuple(rejected_claims),
        coverage=bool(accepted_claims),
        had_degradation=had_degradation,
    )
