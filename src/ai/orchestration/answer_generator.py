"""Grounded answer generation with untrusted-context and citation guardrails."""

from __future__ import annotations

import json
import secrets
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from src.ai.orchestration.conversation_memory import HistoryTurn
from src.ai.orchestration.grounded_answer_prompt_v10 import (
    PROMPT_VERSION as GENERAL_PROMPT_VERSION,
)
from src.ai.orchestration.grounded_answer_prompt_v10 import (
    STRICT_PROMPT_VERSION,
    STRICT_SYSTEM_INSTRUCTIONS,
)
from src.ai.orchestration.grounded_answer_prompt_v10 import (
    SYSTEM_INSTRUCTIONS as GENERAL_SYSTEM_INSTRUCTIONS,
)
from src.ai.orchestration.personalization import AnswerLanguage, build_style_instruction
from src.ai.orchestration.turn_interpreter import KnowledgePolicy
from src.ai.retrieval_engine.chunking_config import load_chunking_config
from src.ai.retrieval_engine.retrieval_engine import RetrievalResult
from src.core.security.secret_scan import record_secret_findings, scan
from src.core.telemetry import current_trace, telemetry_span
from src.model.enums import DocumentDomain, MessageRole, ResponseLength, ResponseTone
from src.shared.ai.external_failures import ExternalServiceFailure
from src.shared.ai.ports import ChatCompletionPort
from src.shared.ai.request_budget import RequestBudget

if TYPE_CHECKING:
    from src.ai.orchestration.claim_validation import ClaimValidationResult
    from src.ai.orchestration.guidance_validation import GuidanceValidationResult

# F5_BOUNDED_GENERAL_KNOWLEDGE_SPEC.md §4: the literal sentinel `_messages` substitutes for an
# empty evidence context on a GENERAL_ALLOWED turn (§10.1/§10.2) -- v3's rule 6 keys off this
# exact string to force claims=[] (belt-and-braces; `validate_claims` already rejects every claim
# when there is no accepted evidence regardless of what the model does).
NO_EVIDENCE_SENTINEL = "NO PROJECT EVIDENCE WAS RETRIEVED FOR THIS TURN"


class CitationRef(BaseModel):
    chunk_id: int
    quote: str = Field(min_length=1)

    @field_validator("quote")
    @classmethod
    def normalize_transport_quote(cls, value: str) -> str:
        """Remove presentation-only quote delimiters before anchor lookup.

        The accepted-evidence identity remains the exact integer ``chunk_id``.  This only removes
        one balanced wrapper that a structured-output provider may add around an otherwise exact
        source span; it never fuzzy-matches or substitutes an anchor.
        """
        value = value.strip()
        wrappers = {"\"": "\"", "'": "'", "“": "”", "‘": "’", "`": "`"}
        if len(value) >= 3 and wrappers.get(value[0]) == value[-1]:
            value = value[1:-1].strip()
        if not value:
            raise ValueError("citation quote must not be empty")
        return value


class ClaimSupport(StrEnum):
    DIRECT = "direct"
    INFERRED = "inferred"


class ClaimRef(BaseModel):
    text: str = Field(min_length=1)
    support: ClaimSupport
    citations: list[CitationRef] = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def text_must_not_be_whitespace(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("claim text must not be empty")
        return value


class GroundedAnswer(BaseModel):
    claims: list[ClaimRef] = Field(min_length=1)
    conflict: str | None = None


class GuidanceKind(StrEnum):
    INSTRUCTION = "instruction"  # an actionable generic step
    EXPLANATION = "explanation"  # what a generic tool/command/concept does


class GuidanceRef(BaseModel):
    text: str = Field(min_length=1)
    kind: GuidanceKind
    # NOTE: there is deliberately NO citation field on this type, and none may ever be added.
    # This is the structural half of INV9's preservation (F5_BOUNDED_GENERAL_KNOWLEDGE_SPEC.md
    # §3.4): a type with no citation field cannot carry one, cannot be mistaken for a claim by
    # any consumer, and cannot reach the `Citation` insert loop.

    @field_validator("text")
    @classmethod
    def text_must_not_be_whitespace(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("guidance text must not be empty")
        return value


class AugmentedAnswer(BaseModel):
    """GENERAL_ALLOWED turns only (§5.3). `GroundedAnswer` stays the STRICT_INTERNAL model,
    byte-identical to before this spec."""

    claims: list[ClaimRef] = Field(default_factory=list)
    general_guidance: list[GuidanceRef] = Field(default_factory=list)
    conflict: str | None = None

    @model_validator(mode="after")
    def at_least_one_section(self) -> AugmentedAnswer:
        if not self.claims and not self.general_guidance:
            raise ValueError("response must contain at least one claim or one guidance item")
        return self


@dataclass(frozen=True)
class VerifiedCitation:
    chunk_id: int
    quote: str
    relevance_score: float
    knowledge_domain: DocumentDomain


@dataclass(frozen=True)
class VerifiedClaim:
    text: str
    support: ClaimSupport
    citations: tuple[VerifiedCitation, ...]


@dataclass(frozen=True)
class VerifiedGuidance:
    text: str
    kind: GuidanceKind
    risk_flags: frozenset[str] = frozenset()


def assemble_answer(claims: Sequence[VerifiedClaim]) -> str:
    """Create outbound prose from validated claims in their model-supplied order."""
    return "\n\n".join(claim.text for claim in claims)


@dataclass(frozen=True)
class GenerationSuccess:
    claims: tuple[VerifiedClaim, ...]
    retry_count: int
    answer_status: Literal["verified", "partially_verified"] = "verified"
    validator_outcome: Literal["passed", "degraded"] = "passed"
    conflict: str | None = None
    guidance: tuple[VerifiedGuidance, ...] = ()  # default () => every existing caller unchanged
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    model: str | None = None
    # Indicates a validated but incomplete non-procedural response.
    task_incomplete: bool = False

    @property
    def answer(self) -> str:
        """Compatibility view; claims remain the sole generated source of truth."""
        return assemble_answer(self.claims)

    @property
    def citations(self) -> tuple[VerifiedCitation, ...]:
        """Compatibility view for the existing answer-level persistence path (Task 3 only)."""
        return tuple(citation for claim in self.claims for citation in claim.citations)


@dataclass(frozen=True)
class GenerationFailure:
    reason: str  # system_error | validator_fail
    retry_count: int


@dataclass(frozen=True)
class _RedactedChunkView:
    """Read-only view of a chunk whose ``content`` has been redacted.

    A view rather than a mutation: the ORM chunk stays untouched, so nothing this
    boundary does can be flushed back into the corpus. Every other attribute is
    delegated, so callers downstream (validation, citation anchoring) keep working
    against the same chunk identity.
    """

    chunk: object
    content: str

    def __getattr__(self, name: str) -> Any:
        return getattr(self.chunk, name)


def _redacted_candidates(candidates: list[RetrievalResult]) -> list[RetrievalResult]:
    """Redact retrieved content before it leaves the trust boundary (F-21).

    Ingestion already redacts, so this is defense-in-depth for content that predates
    that control. The redacted text is also what claim validation sees: the model can
    only quote what it was shown, so validating against the raw chunk would reject
    quotes that legitimately span a redacted span.
    """
    redacted: list[RetrievalResult] = []
    for item in candidates:
        result = scan(item.chunk.content)
        if not result.has_findings:
            redacted.append(item)
            continue
        record_secret_findings(
            result,
            boundary="egress.chat_llm",
            document_reference=f"chunk:{item.chunk.chunk_id}",
        )
        redacted.append(
            replace(item, chunk=_RedactedChunkView(item.chunk, result.redacted_content))
        )
    return redacted


def _redacted_user_text(value: str, *, reference: str) -> str:
    """Redact user-authored prompt material immediately before provider egress."""
    result = scan(value)
    record_secret_findings(
        result,
        boundary="egress.chat_llm.user_input",
        document_reference=reference,
    )
    return result.redacted_content


def _redacted_history(history: Sequence[HistoryTurn]) -> tuple[HistoryTurn, ...]:
    """Keep server-authored turns intact while redacting every prior user turn."""
    return tuple(
        replace(
            turn,
            content=_redacted_user_text(
                turn.content, reference=f"history_turn:{index}"
            ),
        )
        if turn.role is MessageRole.USER
        else turn
        for index, turn in enumerate(history)
    )


def _wrap(delimiter: str, label: str, body: str) -> str:
    return f"--- {delimiter} START ({label}) ---\n{body}\n--- {delimiter} END ---"


def _encoding():
    """Use the tokenizer already used by the corpus chunkers."""
    import tiktoken

    return tiktoken.get_encoding("cl100k_base")


def _truncate_tokens(value: str, limit: int) -> str:
    if limit <= 0:
        return ""
    encoded = _encoding().encode(value)
    if len(encoded) <= limit:
        return value
    return _encoding().decode(encoded[:limit]).rstrip() + "\n[truncated]"


def _build_evidence_context(
    candidates: Sequence[RetrievalResult], *, max_tokens: int, per_chunk_tokens: int
) -> str:
    """Bound evidence deterministically; scope and ordering remain retrieval concerns."""
    blocks: list[str] = []
    used = 0
    encoding = _encoding()
    for item in candidates:
        header = "\n".join(
            [
                f"chunk_id: {item.chunk.chunk_id}",
                f"domain: {item.knowledge_domain.value}",
                f"source: {item.document_title or item.document_id}",
                f"source_url: {item.source_url or 'unavailable'}",
                f"effective_date: {item.effective_date.isoformat() if item.effective_date else 'unavailable'}",
                f"section: {item.chunk.section_path or item.chunk.heading or 'untitled'}",
                "content:",
            ]
        )
        remaining = max_tokens - used - len(encoding.encode(header))
        if remaining <= 0:
            break
        block = f"{header}\n{_truncate_tokens(item.chunk.content, min(per_chunk_tokens, remaining))}"
        cost = len(encoding.encode(block))
        if cost > max_tokens - used:
            break
        blocks.append(block)
        used += cost
    return "\n\n".join(blocks)


class AnswerGenerator:
    """Calls an LLM without tools and accepts only source-verifiable citations."""

    def __init__(
        self,
        provider: ChatCompletionPort,
        *,
        max_attempts: int | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        # Semantic repair is separate from transport retry and remains bounded to one attempt.
        self.config = config or load_chunking_config()
        settings = self.config["chat"]
        self.provider = provider
        self.max_attempts = (
            1 + int(settings["max_regeneration_attempts"]) if max_attempts is None else max_attempts
        )
        # Imported lazily to avoid the same module-import cycle `generate()` already avoids for
        # `claim_validation` (guidance_validation imports GuidanceRef/GuidanceKind from this
        # module).
        from src.ai.orchestration.guidance_validation import GeneralKnowledgeConfig

        self.general_knowledge_config = GeneralKnowledgeConfig.from_config(self.config)

    @staticmethod
    def _messages(
        question: str,
        candidates: list[RetrievalResult],
        *,
        history: Sequence[HistoryTurn] = (),
        repair_feedback: Sequence[str] = (),
        current_date: date | None = None,
        config: dict[str, Any] | None = None,
        response_length: ResponseLength = ResponseLength.STANDARD,
        response_tone: ResponseTone = ResponseTone.NEUTRAL,
        answer_language: AnswerLanguage | None = None,
        knowledge_policy: KnowledgePolicy = KnowledgePolicy.STRICT_INTERNAL,
        context_max_tokens: int | None = None,
    ) -> list[tuple[str, str]]:
        """system (static) → [style] → history turns → context block → question last.

        History arrives as real turns, not concatenated text, and every user-authored string —
        historical or current — is wrapped in the same untrusted-input delimiter (F-11/F-23).
        Assistant history is server-authored: already redacted and citation-verified before it
        was persisted, so there is no path for client text to occupy the assistant role.

        The style message (F5 personalization, PERSONALIZE_CHATBOT_SPEC.md §3) is appended only
        when non-empty: `STANDARD`/`NEUTRAL` — the column defaults — resolve to "", so the
        default case produces byte-identical output to before this parameter existed.

        `answer_language` (F5 Semantic Turn Interpreter rev. 2 §7.2(b)): `None` by default, so
        this parameter alone never changes output; only `ChatService`'s Phase 2 dispatcher passes
        a concrete value (a turn-local `presentation.language` override, or the detected question
        language — never null once the dispatcher computes it, per rev. 2 §7.2(a)'s formula).

        `knowledge_policy` (F5_BOUNDED_GENERAL_KNOWLEDGE_SPEC.md §5.3/§7): `STRICT_INTERNAL` by
        default, so every existing call site produces a byte-identical prompt to before this
        parameter existed. `GENERAL_ALLOWED` selects the v3 system prompt (adds the GENERAL
        GUIDANCE section) and, when `candidates` is empty, substitutes `NO_EVIDENCE_SENTINEL` for
        the (otherwise blank) context block -- `STRICT_INTERNAL` never reaches `generate()` with
        an empty candidate list (the caller already returns a `no_evidence` fallback before that),
        so this substitution never fires on the unchanged path either.
        """
        nonce = secrets.token_urlsafe(18)
        context_delimiter = f"CONTEXT_{nonce}"
        question_delimiter = f"QUESTION_{nonce}"
        chat_config = (config or load_chunking_config())["chat"]
        context = (
            _build_evidence_context(
                candidates,
                max_tokens=int(context_max_tokens or chat_config["context_max_tokens"]),
                per_chunk_tokens=int(chat_config["context_per_chunk_max_tokens"]),
            )
            if candidates
            else NO_EVIDENCE_SENTINEL
        )
        runtime_date = current_date or datetime.now(UTC).date()
        system_instructions = (
            STRICT_SYSTEM_INSTRUCTIONS
            if knowledge_policy is KnowledgePolicy.STRICT_INTERNAL
            else GENERAL_SYSTEM_INSTRUCTIONS
        )
        messages: list[tuple[str, str]] = [
            ("system", system_instructions),
            ("system", f"Runtime current_date: {runtime_date.isoformat()}"),
        ]
        style_instruction = build_style_instruction(response_length, response_tone, answer_language)
        if style_instruction:
            messages.append(("system", style_instruction))
        for turn in history:
            if turn.role is MessageRole.USER:
                messages.append(
                    ("user", _wrap(question_delimiter, "UNTRUSTED USER INPUT", turn.content))
                )
            else:
                messages.append(("assistant", turn.content))
        _repair_intro = (
            "Your previous response failed validation. Repair the listed issues, use "
            "only the same retrieved context, and return the complete claims JSON again:\n"
            if knowledge_policy is KnowledgePolicy.STRICT_INTERNAL
            else "Your previous response failed validation. Repair the listed issues and return "
            "the complete claims/general_guidance JSON again, using only the same retrieved "
            "context (or the NO PROJECT EVIDENCE sentinel, unchanged):\n"
        )
        final = "\n".join(
            [
                *(
                    [_repair_intro + "\n".join(f"- {item}" for item in repair_feedback)]
                    if repair_feedback
                    else []
                ),
                _wrap(context_delimiter, "UNTRUSTED REFERENCE DATA", context),
                _wrap(question_delimiter, "UNTRUSTED USER INPUT", question),
            ]
        )
        messages.append(("user", final))
        return messages

    @staticmethod
    def _parse(
        response: Any, *, knowledge_policy: KnowledgePolicy = KnowledgePolicy.STRICT_INTERNAL
    ) -> GroundedAnswer | AugmentedAnswer:
        """`STRICT_INTERNAL` parses into the unchanged `GroundedAnswer` model -- same class, same
        validation, byte-identical failure behaviour. `GENERAL_ALLOWED` parses into
        `AugmentedAnswer`, whose `at_least_one_section` validator is the AugmentedAnswer-only
        equivalent of `GroundedAnswer.claims`'s `min_length=1`.

        F5 audit 2026-08-30 (Thread C, BGK structured-output reliability): strips a leading
        ```/```json markdown fence before parsing -- the same defensive normalization
        `turn_interpreter.py`/`evidence_sufficiency_gate.py` already apply to their own JSON
        verdicts, extended here rather than left as the one JSON-parsing call site in this
        module without it. A fenced response used to raise `ValueError` immediately, burning
        this stage's one bounded repair attempt (`generate()`'s F-14 cap) on a response that was
        never actually malformed content -- just wrapped. `generate()`'s existing repair loop is
        unchanged; this only shrinks how often it has to fire for a purely cosmetic reason.
        """
        content = getattr(response, "content", response)
        if not isinstance(content, str):
            raise ValueError("LLM response content is not text")
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        model = GroundedAnswer if knowledge_policy is KnowledgePolicy.STRICT_INTERNAL else AugmentedAnswer
        try:
            return model.model_validate(json.loads(text))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ValueError("LLM response is not valid grounded JSON") from exc

    @staticmethod
    def _usage(response: Any) -> tuple[int | None, int | None, str | None]:
        metadata = getattr(response, "response_metadata", {}) or {}
        usage = metadata.get("token_usage", {}) or getattr(response, "usage_metadata", {}) or {}
        return (
            usage.get("prompt_tokens") or usage.get("input_tokens"),
            usage.get("completion_tokens") or usage.get("output_tokens"),
            metadata.get("model_name") or metadata.get("model"),
        )

    @staticmethod
    def _repair_feedback(
        validation: ClaimValidationResult,
        guidance_result: GuidanceValidationResult | None = None,
        *,
        guidance_item_max_chars: int | None = None,
    ) -> tuple[str, ...]:
        feedback: list[str] = []
        for rejected in validation.rejected_claims:
            claim_number = rejected.claim_index + 1
            unsupported = next(
                (
                    reason.partition(":")[2]
                    for reason in rejected.reasons
                    if reason.startswith("unsupported_hard_tokens:")
                ),
                None,
            )
            if unsupported:
                feedback.append(
                    f"claim {claim_number} introduced unsupported hard token(s): {unsupported}"
                )
            elif "incomplete_claim_text" in rejected.reasons:
                feedback.append(
                    f"claim {claim_number} was an incomplete procedural lead-in; include the "
                    "promised steps or commands as complete standalone claims. Do not replace "
                    "commands with a summary or a promise of later steps."
                )
            elif "citation_anchor_not_found" in rejected.reasons:
                # The quote differs materially from the source after normalization.
                feedback.append(
                    f"claim {claim_number}'s citation quote is not an exact "
                    "character-for-character substring of the cited source chunk. Copy the quote "
                    "directly from the source text -- do not paraphrase, summarize, translate, "
                    "reorder, or add/remove words."
                )
            elif "claim_has_no_anchors" in rejected.reasons:
                feedback.append(f"claim {claim_number} lost all evidence anchors")
            else:
                feedback.append(
                    f"claim {claim_number} failed validation: {', '.join(rejected.reasons)}"
                )
        # F5_BOUNDED_GENERAL_KNOWLEDGE_SPEC.md §7.3/§8 R3: a rejected guidance item is surfaced
        # whenever a repair is already happening (triggered by `not has_claims and not
        # has_guidance` in `generate()` -- which fires when guidance was the ONLY content offered
        # and it was rejected, not only when claims failed). `guidance_unsupported_value` gets an
        # actionable rewrite instruction, not just the bare reason code: naming an ungrounded
        # version/count/date in otherwise-correct generic guidance is the single most common way
        # a real model trips this rule (observed live, 2026-08-23 -- see CHANGE_LOG.md), and the
        # fix is always the same move (drop the value, describe the step generically), so state it
        # once here rather than hoping the model infers it from the bare code.
        if guidance_result is not None:
            for rejected_item in guidance_result.rejected:
                value_reason = next(
                    (
                        reason.partition(":")[2]
                        for reason in rejected_item.reasons
                        if reason.startswith("guidance_unsupported_value:")
                    ),
                    None,
                )
                if value_reason:
                    feedback.append(
                        f"general_guidance item {rejected_item.item_index + 1} named a specific "
                        f"value ({value_reason}) that is not grounded in the question or the "
                        "retrieved context -- rewrite this item WITHOUT that value, describing "
                        "the step generically instead (e.g. \"the latest stable release\" rather "
                        "than a version number)"
                    )
                elif "guidance_project_deixis" in rejected_item.reasons:
                    feedback.append(
                        f"general_guidance item {rejected_item.item_index + 1} referred to this "
                        "project/company directly -- rewrite it in a fully generic frame with no "
                        "project reference, or move the project-specific part into a cited claim"
                    )
                elif "guidance_item_too_long" in rejected_item.reasons:
                    # F5 audit 2026-08-30 (Thread C, live-trace-confirmed dominant BGK failure
                    # for a genuinely detailed comparison question, e.g. "Kafka khác RabbitMQ
                    # như thế nào?"): the bare reason code gave the model no actionable
                    # instruction, so the SAME single over-long item recurred on repair and
                    # burned the one bounded attempt. Same actionable-rewrite pattern as
                    # `guidance_unsupported_value` above: name the actual limit and the two ways
                    # to satisfy it, since the model does not know `guidance_item_max_chars`.
                    limit_note = (
                        f" (limit: {guidance_item_max_chars} characters)"
                        if guidance_item_max_chars is not None
                        else ""
                    )
                    feedback.append(
                        f"general_guidance item {rejected_item.item_index + 1} was too long{limit_note} "
                        "-- split it into multiple shorter general_guidance items (one per step or "
                        "sub-point) instead of one long item, or shorten it to the most essential "
                        "steps only. Do not drop the answer itself; restructure it into items that "
                        "each fit the limit."
                    )
                else:
                    feedback.append(
                        f"general_guidance item {rejected_item.item_index + 1} failed validation: "
                        f"{', '.join(rejected_item.reasons)}"
                    )
        return tuple(feedback) or ("the response contained no grounded claims",)

    async def generate(
        self,
        question: str,
        candidates: list[RetrievalResult],
        *,
        history: Sequence[HistoryTurn] = (),
        budget: RequestBudget | None = None,
        response_length: ResponseLength = ResponseLength.STANDARD,
        response_tone: ResponseTone = ResponseTone.NEUTRAL,
        answer_language: AnswerLanguage | None = None,
        response_length_source: str = "user",
        answer_language_source: str = "user",
        knowledge_policy: KnowledgePolicy = KnowledgePolicy.STRICT_INTERNAL,
        context_max_tokens: int | None = None,
    ) -> GenerationSuccess | GenerationFailure:
        # Import lazily to keep the contract types importable by the standalone validator without
        # creating a module-import cycle. Validation itself remains synchronous and retrieval-free.
        from src.ai.orchestration.claim_validation import is_procedure_question, validate_claims
        from src.ai.orchestration.guidance_validation import validate_guidance
        from src.core.security.secret_scan import SecretScanUnavailableError
        budget = budget or RequestBudget(60.0, 0.0, 60.0)

        # Fail closed: an unavailable scanner must not become "send it raw".
        #
        # `prompt_candidates` (not `candidates`) is what goes to the LLM — it must never see a
        # raw secret, regardless of how it got into the corpus. Claim validation below still uses
        # the original `candidates`: it only checks whether a citation is grounded in real
        # evidence, and running that check against the redacted view rejects a truthfully-grounded
        # claim whenever its quote falls inside a redacted span (a real secret that predates F-20
        # ingest-time redaction, since `_redacted_candidates` is explicitly a defense-in-depth net
        # for pre-existing content, not the primary control). That false rejection used to burn an
        # extra repair attempt for a claim that was going to be accepted either way — output-side
        # redaction (`ChatService._redact_observed`/`_redact_chunk_content`) already scrubs the
        # persisted/returned answer, claim text, and citation quote independently of this step, so
        # nothing unredacted reaches the DB or the API response either way.
        try:
            with telemetry_span("egress.secret_scan"):
                prompt_candidates = _redacted_candidates(candidates)
                question = _redacted_user_text(question, reference="current_question")
                history = _redacted_history(history)
        except SecretScanUnavailableError:
            trace = current_trace()
            if trace is not None:
                trace.annotate(
                    error_stage="egress.secret_scan", error_code="secret_scan_unavailable"
                )
            return GenerationFailure(reason="system_error", retry_count=0)

        # The configured regeneration budget remains authoritative, but the approved F-14 policy
        # permits at most one bounded repair attempt for this generation stage.
        attempts = 1 + min(1, max(0, self.max_attempts - 1))
        repair_feedback: tuple[str, ...] = ()
        salvage_success: GenerationSuccess | None = None
        total_prompt_tokens = 0
        total_completion_tokens = 0
        trace = current_trace()
        if trace is not None:
            trace.annotate(
                # §14: "already annotated; now genuinely varies per turn" -- both variants of the
                # v5 artifact, one per knowledge policy (grounded_answer_prompt_v5.py's docstring).
                prompt_version=(
                    STRICT_PROMPT_VERSION
                    if knowledge_policy is KnowledgePolicy.STRICT_INTERNAL
                    else GENERAL_PROMPT_VERSION
                ),
                retrieval_config_version=self.config["retrieval"].get("config_version", "legacy"),
                generation_config={
                    "context_max_tokens": context_max_tokens
                    or self.config["chat"]["context_max_tokens"],
                    "context_per_chunk_max_tokens": self.config["chat"]["context_per_chunk_max_tokens"],
                    "response_length": response_length.value,
                    "response_tone": response_tone.value,
                    # F5 Semantic Turn Interpreter rev. 2 §7.2(b): which source actually won —
                    # a turn-local presentation override, or the persisted `User` preference.
                    "response_length_source": response_length_source,
                    "answer_language": answer_language.value if answer_language is not None else None,
                    "answer_language_source": answer_language_source,
                },
            )
        for retry_count in range(attempts):
            messages = self._messages(
                question,
                prompt_candidates,
                history=history,
                repair_feedback=repair_feedback,
                context_max_tokens=context_max_tokens,
                config=self.config,
                response_length=response_length,
                response_tone=response_tone,
                answer_language=answer_language,
                knowledge_policy=knowledge_policy,
            )
            prompt_characters = sum(len(content) for _, content in messages)
            try:
                with telemetry_span("generation.provider", attempt=retry_count + 1):
                    response = await self.provider.complete(
                        messages,
                        budget,
                        "answer" if retry_count == 0 else "repair",
                    )
            except ExternalServiceFailure as exc:
                trace = current_trace()
                if retry_count > 0 and salvage_success is not None:
                    if trace is not None:
                        trace.annotate(
                            external_service=exc.service,
                            external_failure_code=exc.code.value,
                            provider_retry_count=max(0, exc.attempts - 1),
                            timeout_scope=exc.timeout_scope,
                            external_operation="repair",
                            remaining_budget_ms=round(budget.remaining_total() * 1000),
                            repair_retry_count=retry_count,
                            decision_details={
                                "repair_failed_degraded_to_verified_claims": True,
                                "repair_failure_code": exc.code.value,
                            },
                        )
                    return replace(salvage_success, retry_count=retry_count)
                if trace is not None:
                    trace.annotate(
                        error_stage="generation.provider",
                        error_code="provider_timeout" if exc.code.value == "timeout" else "provider_error",
                        external_service=exc.service,
                        external_failure_code=exc.code.value,
                        provider_retry_count=max(0, exc.attempts - 1),
                        timeout_scope=exc.timeout_scope,
                        external_operation="answer" if retry_count == 0 else "repair",
                        remaining_budget_ms=round(budget.remaining_total() * 1000),
                        repair_retry_count=retry_count,
                        provider_exception_type=exc.provider_exception_type,
                        provider_status_code=exc.provider_status_code,
                        provider_error_message=exc.provider_error_message,
                        provider_request_id=exc.provider_request_id,
                        provider_endpoint=exc.provider_endpoint,
                        provider_prompt_message_count=len(messages),
                        provider_prompt_characters=prompt_characters,
                        # An explicitly-labelled diagnostic estimate: failed OpenAI responses do
                        # not carry usage, and logging prompt content would violate telemetry rules.
                        provider_prompt_token_estimate=(prompt_characters + 3) // 4,
                    )
                return GenerationFailure(reason="system_error", retry_count=retry_count)
            prompt_tokens, completion_tokens, model = self._usage(response)
            total_prompt_tokens += prompt_tokens or 0
            total_completion_tokens += completion_tokens or 0
            trace = current_trace()
            if trace is not None:
                trace.increment("prompt_tokens", prompt_tokens)
                trace.increment("completion_tokens", completion_tokens)
                trace.annotate(
                    provider=type(self.provider).__name__,
                    model=model,
                )
            try:
                parsed = self._parse(response, knowledge_policy=knowledge_policy)
                with telemetry_span("claim_verification", attempt=retry_count + 1):
                    validation = validate_claims(parsed.claims, candidates, question)
                # F5_BOUNDED_GENERAL_KNOWLEDGE_SPEC.md §8: guidance is validated only under
                # GENERAL_ALLOWED -- a STRICT_INTERNAL turn parses `GroundedAnswer`, which has no
                # `general_guidance` attribute at all, so `guidance_result` stays `None` and every
                # BGK branch below is inert on the unchanged path.
                guidance_result: GuidanceValidationResult | None = None
                if knowledge_policy is KnowledgePolicy.GENERAL_ALLOWED:
                    with telemetry_span("guidance_verification", attempt=retry_count + 1):
                        guidance_result = validate_guidance(
                            parsed.general_guidance,
                            candidates,
                            question,
                            config=self.general_knowledge_config,
                        )
                trace = current_trace()
                if trace is not None:
                    reason_codes = sorted(
                        {
                            reason.partition(":")[0]
                            for rejected in validation.rejected_claims
                            for reason in rejected.reasons
                        }
                    )
                    decision_details: dict[str, object] = {
                        "validator_reason_codes": reason_codes,
                        "accepted_claim_count": len(validation.claims),
                        "rejected_claim_count": len(validation.rejected_claims),
                        # 2026-08-25: the same lesson the guidance side already learned below,
                        # applied to claims. `validator_reason_codes` keeps only the prefix, so
                        # `unsupported_hard_tokens:mysql,postgresql` logs as
                        # `unsupported_hard_tokens` -- the tokens, i.e. the only part that says
                        # WHICH rule fired on WHAT, were thrown away. That gap is why the question
                        # "did the B-07 entity rule cause this validator_fail?" had to be answered
                        # by reasoning instead of by reading the trace. Full strings, bounded and
                        # deduped, exactly like `guidance_rejected_reasons`.
                        "validator_rejected_reasons": sorted(
                            {
                                reason
                                for rejected in validation.rejected_claims
                                for reason in rejected.reasons
                            }
                        )[:20],
                    }
                    if guidance_result is not None:
                        decision_details["guidance_reason_codes"] = sorted(
                            {
                                reason.partition(":")[0]
                                for rejected_item in guidance_result.rejected
                                for reason in rejected_item.reasons
                            }
                        )
                        # Diagnostic only (2026-08-23, see CHANGE_LOG.md): the bare reason
                        # prefix above throws away exactly the detail needed to tell a real R3
                        # catch from a false positive (e.g. `guidance_unsupported_value:1.21` vs
                        # `:16`) -- the FULL reason strings are logged too, bounded, so the next
                        # occurrence is diagnosable from telemetry alone, no live repro needed.
                        decision_details["guidance_rejected_reasons"] = sorted(
                            {
                                reason
                                for rejected_item in guidance_result.rejected
                                for reason in rejected_item.reasons
                            }
                        )[:20]
                        decision_details["guidance_risk_flags"] = sorted(
                            {flag for item in guidance_result.items for flag in item.risk_flags}
                        )
                        decision_details["guidance_item_count"] = len(guidance_result.items)
                        decision_details["guidance_rejected_count"] = len(guidance_result.rejected)
                    trace.annotate(repair_retry_count=retry_count, decision_details=decision_details)
                # Under GENERAL_ALLOWED, either section surviving is enough to stop retrying --
                # an empty `claims[]` is the CORRECT model output on a guidance_only turn (§7.1
                # rule 6), not a failure to repair. §10.3's "both empty" terminal case still falls
                # through to `GenerationFailure(reason="validator_fail")` below exactly as today;
                # `ChatService` remaps that reason back to the original branch's fallback reason.
                has_claims = bool(validation.claims)
                has_guidance = bool(guidance_result.items) if guidance_result is not None else False
                has_incomplete_claim = any(
                    "incomplete_claim_text" in rejected.reasons
                    for rejected in validation.rejected_claims
                )
                verified_claims = tuple(
                    VerifiedClaim(
                        text=claim.text,
                        support=claim.support,
                        citations=claim.citations,
                    )
                    for claim in validation.claims
                )
                verified_guidance = tuple(
                    VerifiedGuidance(text=item.text, kind=item.kind, risk_flags=item.risk_flags)
                    for item in (guidance_result.items if guidance_result is not None else ())
                )
                degraded = validation.had_degradation
                candidate_success = GenerationSuccess(
                    claims=verified_claims,
                    retry_count=retry_count,
                    answer_status="partially_verified" if degraded else "verified",
                    validator_outcome="degraded" if degraded else "passed",
                    conflict=parsed.conflict,
                    guidance=verified_guidance,
                    prompt_tokens=total_prompt_tokens or None,
                    completion_tokens=total_completion_tokens or None,
                    model=model,
                )
                # Ordinary partial degradation remains cheap: one bad citation does not discard
                # other grounded claims.  A dangling lead-in is different because it explicitly
                # promises omitted content, so spend the single bounded repair while available.
                if has_incomplete_claim:
                    # Salvage only a final, non-procedural attempt with other validated claims.
                    is_final_attempt = retry_count == attempts - 1
                    if is_final_attempt and has_claims and not is_procedure_question(question):
                        return replace(candidate_success, task_incomplete=True)
                    salvage_success = None
                    repair_feedback = self._repair_feedback(
                        validation,
                        guidance_result,
                        guidance_item_max_chars=self.general_knowledge_config.guidance_item_max_chars,
                    )
                    continue
                if not has_claims and not has_guidance:
                    repair_feedback = self._repair_feedback(
                        validation,
                        guidance_result,
                        guidance_item_max_chars=self.general_knowledge_config.guidance_item_max_chars,
                    )
                    continue
                return candidate_success
            except ValueError:
                trace = current_trace()
                if trace is not None:
                    trace.annotate(
                        repair_retry_count=retry_count,
                        decision_details={"validator_reason_codes": ["invalid_json"]},
                    )
                # F5 audit 2026-08-30 (Thread C): policy-aware, matching `_repair_intro`'s own
                # framing just above -- the prior "claims JSON" wording on a GENERAL_ALLOWED turn
                # named only half of the two-section schema the model actually needs to return.
                repair_feedback = (
                    "the response was not valid claims JSON"
                    if knowledge_policy is KnowledgePolicy.STRICT_INTERNAL
                    else "the response was not valid claims/general_guidance JSON",
                )
                continue
        trace = current_trace()
        if trace is not None:
            trace.annotate(
                error_stage="claim_verification",
                error_code="validator_fail",
                repair_retry_count=attempts - 1,
            )
        return GenerationFailure(reason="validator_fail", retry_count=attempts - 1)
