"""F5 application flow: server-side scope, conversation memory, gate, generation, persistence."""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, replace

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.orchestration.answer_generator import (
    AnswerGenerator,
    ClaimSupport,
    GenerationFailure,
    GenerationSuccess,
    VerifiedCitation,
    VerifiedClaim,
)
from src.ai.orchestration.conversation_answer import (
    ConversationAnswerFailure,
    ConversationAnswerGenerator,
)
from src.ai.orchestration.conversation_intent import AnswerMode, classify_intent
from src.ai.orchestration.conversation_memory import (
    ConversationWindow,
    MemoryConfig,
    TopicState,
    build_conversation_transcript,
    build_window,
    decode_topic_entities,
    encode_topic_entities,
    informational_anchor_questions,
    truncate,
)
from src.ai.orchestration.evidence_sufficiency_gate import (
    EvidenceSufficiencyGate,
    EvidenceSufficiencyResult,
    EvidenceSufficiencyVerdict,
)
from src.ai.orchestration.general_guidance_policy import PolicySource, narrow_policy
from src.ai.orchestration.guidance_validation import GeneralKnowledgeConfig
from src.ai.orchestration.personalization import AnswerLanguage
from src.ai.orchestration.query_condenser import (
    CondensedQuery,
    LlmQueryRewriter,
    classify_elaboration,
    condense,
)
from src.ai.orchestration.scope_gate import ScopeGate
from src.ai.orchestration.social_reply import SocialIntent, build_social_reply, classify_social
from src.ai.orchestration.support_reply import SupportReplyGenerator
from src.ai.orchestration.turn_interpreter import (
    ConversationControl,
    ConversationControlApplication,
    ConversationControlKind,
    InterpreterContext,
    InterpreterRoute,
    InterpreterScope,
    InterpreterVerdict,
    KnowledgePolicy,
    PresentationOverlay,
    PriorTurn,
    TurnAffect,
    TurnInterpreter,
)
from src.ai.orchestration.turn_outcome import describe_turn_outcome
from src.ai.retrieval_engine.chunking_config import load_chunking_config
from src.ai.retrieval_engine.lexical import lexical_identifiers
from src.ai.retrieval_engine.retrieval_engine import (
    CatalogGroup,
    RetrievalFilters,
    RetrievalResult,
    RetrievalUnavailableError,
)
from src.core.security.secret_scan import redact
from src.core.telemetry import (
    NullTelemetrySink,
    TelemetrySink,
    TraceRecorder,
    bind_trace,
    current_trace,
    record_duration,
    telemetry_span,
)
from src.model.answer_claim import AnswerClaim
from src.model.chat_message import ChatMessage
from src.model.citation import Citation
from src.model.enums import (
    ClaimSupportType,
    DocumentCategory,
    DocumentDomain,
    MembershipStatus,
    MessageRole,
    PlanStatus,
    ResponseLength,
    ResponseTone,
)
from src.model.onboarding_plan import OnboardingPlan
from src.model.project import Project
from src.model.project_membership import ProjectMembership
from src.modules.chat.application.chat_budget_guard import (
    ChatBudgetConfig,
    ChatBudgetExceededError,
    ChatBudgetGuard,
)
from src.modules.chat.application.conversation_repository import ConversationRepository
from src.modules.knowledge.mining.convention_ingestion import is_conventions_route
from src.shared.ai.external_failures import ExternalServiceFailure
from src.shared.ai.request_budget import RequestBudgetConfig

FALLBACKS = {
    "no_evidence": "Tôi không tìm thấy nguồn phù hợp trong kho tri thức hiện có.",
    "system_error": "Hệ thống đang gặp sự cố khi tạo câu trả lời. Vui lòng thử lại.",
    "validator_fail": "Ralion có tìm thấy tài liệu liên quan, nhưng chưa đối chiếu được câu trả lời với đúng câu chữ trong tài liệu đó, nên không hiển thị câu trả lời để tránh nói sai. Bạn thử hỏi cụ thể hơn về một điểm nhé.",
    "out_of_scope": "Mình chỉ hỗ trợ được các câu hỏi về dự án này và chính sách công ty, nên câu này mình chưa giúp được. Nếu bạn đang vướng ở task, module hay tài liệu nào thì cứ nói với mình nhé.",
    "insufficient_evidence": "Tôi tìm thấy tài liệu liên quan đến chủ đề này, nhưng nội dung đó không trả lời trực tiếp câu hỏi của bạn, nên tôi không thể đưa ra câu trả lời chắc chắn.",
    "ambiguous_question": "Ralion tìm thấy nhiều nội dung liên quan đến câu hỏi của bạn, nhưng chưa xác định chắc chắn bạn đang hỏi về khía cạnh cụ thể nào.",
    "general_knowledge_not_available": (
        "Câu hỏi này cần đến kiến thức chung ngoài chính sách nội bộ của công ty. Trong khung "
        "Chính sách, Ralion chỉ trả lời dựa trên tài liệu nội bộ và không dùng kiến thức chung bên "
        "ngoài, nên mình chưa thể trả lời câu này ở đây."
    ),
}

FALLBACKS_EN = {
    "no_evidence": "I couldn't find a suitable source in the available knowledge base.",
    "system_error": "The system ran into a problem while generating the answer. Please try again.",
    "validator_fail": (
        "Ralion did find related material, but couldn't match the drafted answer to the exact "
        "wording in it, so the answer isn't being shown rather than risk stating something wrong. "
        "Try asking about one specific point."
    ),
    "out_of_scope": (
        "I can only help with questions about this project and company policies. If you're "
        "stuck on a task, module, or document, tell me what it is and I'll help."
    ),
    "insufficient_evidence": (
        "I found material related to this topic, but it doesn't directly answer your question, "
        "so I can't give a reliable answer."
    ),
    "ambiguous_question": (
        "Ralion found several items related to your question, but I can't yet determine which "
        "specific aspect you mean."
    ),
    "general_knowledge_not_available": (
        "This question needs general knowledge outside the company's own policies. In Policy "
        "chat, Ralion only answers from the company's internal documents and does not draw on "
        "outside general knowledge, so I can't answer this one here."
    ),
}

# Target design item 5: only a genuine knowledge gap gets a domain-aware human referral --
# `system_error`/`validator_fail`/`out_of_scope` stay exactly `FALLBACKS[reason]` (invariant 8:
# an infra fault or an off-topic question is not "we don't have this knowledge", and must not be
# reworded as one). `general_knowledge_not_available` (below) joins that same list: it is a scope
# boundary, not a knowledge gap either.
_KNOWLEDGE_GAP_REASONS = frozenset({"no_evidence", "insufficient_evidence"})
_SUGGESTION_ELIGIBLE_REASONS = _KNOWLEDGE_GAP_REASONS | frozenset(
    {"ambiguous_question", "general_knowledge_not_available"}
)

# Structural section expansion is deliberately limited to questions that ask for an ordered
# procedure.  The retrieval engine still requires multiple accepted hits from one numbered
# section, so these phrases alone can never widen evidence into an unrelated document.
_PROCEDURE_QUERY = re.compile(
    r"(?:"
    r"\b(?:từng|các)\s+(?:bước|lệnh)\b|"
    r"\b(?:làm thế nào|làm sao|như thế nào|cách|hướng dẫn)\s+"
    r"(?:để\s+|cách\s+)?(?:chạy|cài|thiết lập|kiểm tra|test|clone)\b|"
    r"\b(?:clone|how\s+(?:do|can|should|to)|exact\s+commands?|steps?|commands?)\b"
    r")",
    re.IGNORECASE,
)
_CLONE_QUERY = re.compile(r"\bclone\b", re.IGNORECASE)
_NUMBERED_SECTION_COMPONENT = re.compile(
    r"(?:^|>)\s*(?:(?:bước|step)\s*)?\d+\s*(?:[.):\-–—]|\s)",
    re.IGNORECASE,
)
_TEST_FOCUSED_QUERY = re.compile(
    r"(?:\b(?:test|tests|testing|pytest|unittest)\b|kiểm\s+thử)",
    re.IGNORECASE,
)


def _deterministic_procedure_generation(
    question: str,
    evidence: Sequence[RetrievalResult],
) -> GenerationSuccess | None:
    """Render a complete numbered procedure directly from server-scoped source chunks.

    Once structural expansion has proven that the ordered sibling set is complete, asking an
    LLM to restate those exact steps can only omit or alter them.  Preserve each source block
    verbatim, add its server-owned section heading, and attach the full source block as the quote.
    The ordinary persistence boundary still redacts the answer, claims, quotes and source text.
    """
    # Only run after structural expansion has established a complete ordered procedure. Test
    # questions retain their dedicated, narrower renderer below. A clone request is an action
    # within a larger setup guide, so retain only evidence whose section itself names that action.
    if _TEST_FOCUSED_QUERY.search(question):
        return None

    selected = list(evidence)
    if _CLONE_QUERY.search(question):
        clone_sections = [
            item
            for item in evidence
            if _CLONE_QUERY.search(item.chunk.section_path or item.chunk.heading or "")
        ]
        if clone_sections:
            selected = clone_sections

    background: list[RetrievalResult] = []
    steps: list[RetrievalResult] = []
    for item in selected:
        path = item.chunk.section_path or item.chunk.heading or ""
        (steps if _NUMBERED_SECTION_COMPONENT.search(path) else background).append(item)

    claims: list[VerifiedClaim] = []
    for item in [*background, *steps]:
        content = item.chunk.content.strip()
        if not content:
            continue
        path = item.chunk.section_path or item.chunk.heading or ""
        heading = path.rsplit(">", 1)[-1].strip()
        is_numbered_step = _NUMBERED_SECTION_COMPONENT.search(path) is not None
        text = f"{heading}\n\n{content}" if is_numbered_step and heading else content
        claims.append(
            VerifiedClaim(
                text=text,
                support=ClaimSupport.DIRECT,
                citations=(
                    VerifiedCitation(
                        chunk_id=item.chunk.chunk_id,
                        quote=content,
                        relevance_score=item.dense_score or 0.0,
                        knowledge_domain=item.knowledge_domain,
                    ),
                ),
            )
        )
    if not claims:
        return None
    return GenerationSuccess(
        claims=tuple(claims),
        retry_count=0,
        answer_status="verified",
        validator_outcome="passed",
        model="deterministic-procedure-v1",
    )


def _deterministic_test_procedure_generation(
    question: str,
    evidence: Sequence[RetrievalResult],
) -> GenerationSuccess | None:
    """Return only the numbered test section for an explicit run-test procedure question."""
    if _PROCEDURE_QUERY.search(question) is None or _TEST_FOCUSED_QUERY.search(question) is None:
        return None
    targeted = [
        item
        for item in evidence
        if _TEST_FOCUSED_QUERY.search(item.chunk.section_path or item.chunk.heading or "")
    ]
    if not targeted:
        return None

    claims: list[VerifiedClaim] = []
    for item in targeted:
        content = item.chunk.content.strip()
        if not content:
            continue
        path = item.chunk.section_path or item.chunk.heading or ""
        heading = path.rsplit(">", 1)[-1].strip()
        claims.append(
            VerifiedClaim(
                text=f"{heading}\n\n{content}" if heading else content,
                support=ClaimSupport.DIRECT,
                citations=(
                    VerifiedCitation(
                        chunk_id=item.chunk.chunk_id,
                        quote=content,
                        relevance_score=item.dense_score or 0.0,
                        knowledge_domain=item.knowledge_domain,
                    ),
                ),
            )
        )
    if not claims:
        return None
    return GenerationSuccess(
        claims=tuple(claims),
        retry_count=0,
        answer_status="verified",
        validator_outcome="passed",
        model="deterministic-test-procedure-v1",
    )


def _referral_target(
    domain: DocumentDomain, language: AnswerLanguage = AnswerLanguage.VI
) -> str:
    if language is AnswerLanguage.EN:
        return "the project's PM" if domain is DocumentDomain.PROJECT else "the HR team"
    return "PM của project" if domain is DocumentDomain.PROJECT else "đội HR"


# 2026-08-27, user concern 4, revised the same day for RC-1 (decision 2a). Appended to the fallback
# of a turn whose INTERPRETATION degraded (interpreter timeout / unparseable output).
#
# The first version of this note existed because such a turn was still processed as a KNOWLEDGE
# question built from the raw utterance, so a message that was really about the dialogue ("sao lại
# không có nguồn?") produced a confident "no source found" about a question the user never asked.
# That fail-open is gone: a degraded interpretation now stops before retrieval, so the note no
# longer describes a standalone-question fallback. It says the one true thing (Ralion could not read
# this turn) and asks for the one input that reliably recovers it -- a self-contained restatement.
# It still does not guess what the turn meant; guessing is what a second brittle classifier would
# do. Static, server-composed, appended after the normal fallback text so `fallback_reason` and its
# wording stay unchanged.
_DEGRADED_INTERPRETATION_NOTE: dict[AnswerLanguage, str] = {
    AnswerLanguage.VI: (
        "Lưu ý: Ralion chưa đọc được câu này nên chưa xử lý, chứ không phải là không có thông tin. "
        "Bạn nhắc lại giúp Ralion trong một câu đầy đủ ý nhé (nếu đang nói tiếp về câu trả lời phía "
        "trên thì nói rõ luôn phần đó)."
    ),
    AnswerLanguage.EN: (
        "Note: Ralion could not read this message, so it was not processed -- this is not a lack "
        "of information. Please restate it in one self-contained sentence (if you were continuing "
        "from an earlier reply, say which part)."
    ),
}

# `system_error` is the reason a degraded-interpretation turn now stops on (decision 2a, 2026-08-27)
# -- an LLM dependency failed, which is exactly what `system_error` means, and invariant 8 keeps it
# distinct from a knowledge gap. The two knowledge-gap reasons stay listed because degradation can
# also arrive from a LATER stage that does not stop the turn (a sanitized verdict, a degraded
# knowledge policy): those turns still reach retrieval, and their wording still makes a CLAIM ABOUT
# THE CORPUS ("no source was found" / "not enough information") that a partly-misread turn would
# turn into a falsehood. `out_of_scope` claims nothing about evidence, and `validator_fail`
# describes something that provably happened, so adding either would be noise.
_DEGRADED_NOTE_REASONS = frozenset({"no_evidence", "insufficient_evidence", "system_error"})


def _fallback_answer_text(
    reason: str,
    domain: DocumentDomain,
    suggestions: Sequence[str],
    language: AnswerLanguage = AnswerLanguage.VI,
) -> str:
    """Human-friendly, domain-aware fallback copy (target design item 5).

    `suggestions` must already be sourced from real, in-scope knowledge (see
    `_suggestions_from_evidence`/`RetrievalEngine.list_available_topics`) -- this function only
    formats what the caller found, it never invents a topic.
    """
    base = (FALLBACKS if language is AnswerLanguage.VI else FALLBACKS_EN)[reason]
    if reason not in _SUGGESTION_ELIGIBLE_REASONS:
        return base
    parts = (
        [base, f"Bạn có thể xác nhận thêm với {_referral_target(domain, language)}."]
        if language is AnswerLanguage.VI
        else [base, f"You can confirm this with {_referral_target(domain, language)}."]
    )
    if suggestions:
        prefix = (
            "Trong kiến thức hiện có, mình có thể giúp bạn về: "
            if language is AnswerLanguage.VI
            else "Within the available knowledge, I can help with: "
        )
        parts.append(prefix + ", ".join(suggestions) + ".")
    return " ".join(parts)


# 2026-08-25, the mixed-turn half of the affect redesign (`turn_interpreter.TurnAffect`).
# "Tôi nản quá, giải thích auth module cho tôi được ko?" must stay a KNOWLEDGE turn -- retrieved,
# grounded, cited, validated, exactly as if the opener were not there -- while still not reading
# as though nobody heard the first half. This is the entire mechanism for that: one static,
# server-composed sentence prepended to the assembled answer.
#
# Server-composed and static for the same reason `_general_guidance_marker` and
# `_partial_coverage_note` are, and the reason matters more here than for either of them: this
# text rides in front of a citation-validated answer, so if the MODEL wrote it, it would be
# unvalidated prose inside a validated turn. It is not passed to `build_style_instruction`
# either -- asking the generator to open warmly would put the acknowledgement inside a
# `claim.text`, where `claim_validation` would (correctly) reject it as unsupported, and repair
# loops would burn tokens re-deriving that. A prefix outside the claims structure touches INV9
# nowhere: it asserts nothing about the company, the project, the team, or the user's ability --
# deliberately not "ai cũng thấy thế" or any other social fact about the company, which is the
# same boundary `personalization.TONE_INSTRUCTIONS[BUDDY]` already draws for itself.
#
# It is deliberately NOT tone-varied: an acknowledgement that changes register with a preference
# panel setting is a nicety pretending to be a personality. Tone still shapes the answer BELOW
# this line, through the normal `build_style_instruction` path.
_AFFECT_ACKNOWLEDGEMENT: dict[AnswerLanguage, str] = {
    AnswerLanguage.VI: "Mình hiểu là bạn đang thấy khá vất vả. Về câu hỏi của bạn:",
    AnswerLanguage.EN: "I hear that this is wearing you down. On your question:",
}


def _affect_acknowledgement(language: AnswerLanguage) -> str:
    return _AFFECT_ACKNOWLEDGEMENT.get(language, _AFFECT_ACKNOWLEDGEMENT[AnswerLanguage.EN])


def _with_affect_acknowledgement(answer: str, turn: _Turn) -> str:
    """Single application point, shared by the generated-answer tail and every fallback, so a
    distressed user gets the same acknowledgement whether their question was answered or not --
    the cold `insufficient_evidence` reply in the reported transcript is exactly the case a
    success-path-only version would still get wrong."""
    if not turn.affect_support_needed:
        return answer
    return f"{_affect_acknowledgement(turn.affect_language)}\n\n{answer}"


def _compose_social_intent_with_subject(
    social_intent: SocialIntent | None, *, has_answerable_subject: bool
) -> SocialIntent | None:
    """A1 remediation (F5 audit): deterministic composition of `affect` and `route`, not another
    worked example. `has_answerable_subject` is asked independently of the model's own SOCIAL/
    BUDDY_SUPPORT judgment (`turn_interpreter.InterpreterVerdict.has_answerable_subject`) -- when
    it disagrees with a BUDDY_SUPPORT verdict, the subject wins: the caller falls through to
    `route=InterpreterRoute.KNOWLEDGE` (see the SOCIAL branch above), and `turn.affect_support_
    needed` still drives `_with_affect_acknowledgement` on that KNOWLEDGE answer, so the feeling
    is acknowledged AND the question is answered. Every other `social_intent` is returned
    unchanged -- this only ever redirects BUDDY_SUPPORT, never any other subtype."""
    if social_intent is SocialIntent.BUDDY_SUPPORT and has_answerable_subject:
        return None
    return social_intent


def _partial_coverage_note(
    domain: DocumentDomain, language: AnswerLanguage = AnswerLanguage.VI
) -> str:
    """Implementation spec §9.3 [REV2]: server-composed, appended after assembly for a `PARTIAL`
    evidence-sufficiency verdict. States a fact about THIS retrieval attempt ("chưa tìm đủ thông
    tin" -- haven't found enough *yet*), never a fact about the corpus's completeness -- a
    retrieval miss proves only that this turn's retrieval didn't surface a chunk, not that the
    corpus lacks one. Reuses the same referral-target voice as `_fallback_answer_text`.
    """
    if language is AnswerLanguage.EN:
        return (
            "This is what Ralion found that directly relates to your question. I haven't found "
            "enough information for the rest yet; you can ask more specifically or confirm with "
            f"{_referral_target(domain, language)}."
        )
    return (
        "Đây là những gì Ralion tìm thấy liên quan trực tiếp đến câu hỏi của bạn. Với phần còn "
        "lại, Ralion hiện chưa tìm đủ thông tin để trả lời chắc chắn — bạn có thể hỏi cụ thể hơn, "
        f"hoặc xác nhận thêm với {_referral_target(domain)}."
    )


def _partial_coverage_with_guidance_note(
    domain: DocumentDomain, language: AnswerLanguage = AnswerLanguage.VI
) -> str:
    """F5_BOUNDED_GENERAL_KNOWLEDGE_SPEC.md §9.2/§12.1: the `PARTIAL` honesty note for a mixed
    (claims + guidance) turn -- distinct from `_partial_coverage_note` because that wording would
    otherwise imply Ralion found nothing for the remainder, when general guidance did in fact
    cover the generic part. Keeps the same "this retrieval attempt, not the corpus" framing.
    """
    if language is AnswerLanguage.EN:
        return (
            "This is what Ralion found that directly relates to your question, together with "
            "general technical guidance for the remainder. For project-specific configuration "
            "or policy that Ralion could not verify, ask more specifically or confirm with "
            f"{_referral_target(domain, language)}."
        )
    return (
        "Đây là những gì Ralion tìm thấy liên quan trực tiếp đến câu hỏi của bạn, cùng với hướng "
        "dẫn kỹ thuật phổ thông cho phần còn lại. Với phần thuộc quy định/cấu hình riêng của dự "
        "án mà Ralion chưa tìm đủ thông tin, bạn có thể hỏi cụ thể hơn, hoặc xác nhận thêm với "
        f"{_referral_target(domain)}."
    )


# 2026-08-27, user concern 2 ("degraded mode must preserve the same boundary"): the disclosure for
# a turn where retrieval could not run AT ALL because a dependency (embedding provider, vector
# store) failed. Deliberately distinct wording from `_partial_coverage_note` and from the
# `no_evidence`/`insufficient_evidence` fallbacks, because the fact being reported is different in
# kind: those say "this attempt did not surface enough", this says "the attempt did not happen".
# Conflating the two is exactly what invariant 8 (`no_evidence` vs `system_error` never merged)
# exists to prevent, and it is the difference between "the project may not document this" and "we
# could not look". Server-composed and static, never model-authored, never tone-softened; reuses
# `_referral_target`, no second referral vocabulary.
def _internal_lookup_failed_note(
    domain: DocumentDomain, language: AnswerLanguage = AnswerLanguage.VI
) -> str:
    if language is AnswerLanguage.EN:
        return (
            "Note on the project-specific part of your question: Ralion could not consult the "
            "internal documents for this answer at all, because an internal dependency failed — "
            "not because no such document exists. Nothing above is verified against this project's "
            f"own documents. Please retry shortly, or confirm with {_referral_target(domain, language)}."
        )
    return (
        "Lưu ý về phần riêng của dự án trong câu hỏi của bạn: Ralion hoàn toàn không tra cứu được "
        "tài liệu nội bộ cho câu trả lời này vì một thành phần phụ thuộc đang gặp sự cố — không "
        "phải vì tài liệu đó không tồn tại. Những nội dung ở trên chưa được đối chiếu với tài liệu "
        f"của dự án. Bạn hãy thử lại sau ít phút, hoặc xác nhận với {_referral_target(domain)}."
    )


# F5 audit 2026-08-29, failure 3: task-completeness disclosure, distinct in kind from
# `_partial_coverage_note` (that one reports EVIDENCE coverage -- this retrieval attempt did not
# surface enough) and from `answer_status="partially_verified"` (that reports CLAIM correctness --
# every returned claim is individually grounded). This note reports the third, separate fact: the
# model's own attempt to answer the FULL request did not fully survive validation, so completeness
# of the returned set relative to what was asked is unconfirmed, even though every item shown IS
# grounded. Appended unconditionally whenever `AnswerGenerator` signals `task_incomplete` --
# structural, driven by that flag alone, never by scanning the question for words like "đầy đủ"/
# "complete": the disclosure must be honest regardless of whether the user's own phrasing happened
# to ask for an exhaustive list. Server-composed and static, same voice as the notes above.
def _task_incomplete_note(
    domain: DocumentDomain, language: AnswerLanguage = AnswerLanguage.VI
) -> str:
    if language is AnswerLanguage.EN:
        return (
            "These are the items Ralion could verify from the available evidence. Ralion could "
            "not confirm this is the complete list — you can ask more specifically, or confirm "
            f"with {_referral_target(domain, language)}."
        )
    return (
        "Đây là những nội dung Ralion có thể xác thực từ tài liệu hiện có. Ralion chưa thể xác "
        "nhận đây đã là danh sách đầy đủ — bạn có thể hỏi cụ thể hơn, hoặc xác nhận thêm với "
        f"{_referral_target(domain)}."
    )


# F5_BOUNDED_GENERAL_KNOWLEDGE_SPEC.md §9.2: server-composed and static, keyed by
# `AnswerLanguage` -- never model-authored, never tone/length-adjusted (a "buddy" tone must not
# soften a provenance disclosure), never omitted when guidance is present. `{referral_target}`
# reuses `_referral_target` -- no second referral vocabulary.
_GENERAL_GUIDANCE_MARKER: dict[AnswerLanguage, str] = {
    AnswerLanguage.VI: (
        "Phần dưới đây là hướng dẫn kỹ thuật phổ thông từ kiến thức chung, không trích từ tài "
        "liệu của dự án. Với những gì thuộc quy định/cấu hình riêng của dự án, hãy xác nhận với "
        "{referral_target}."
    ),
    AnswerLanguage.EN: (
        "The section below is general technical guidance from common knowledge, not drawn from "
        "the project's own documents. For anything specific to this project's own configuration "
        "or policy, please confirm with {referral_target}."
    ),
}


def _general_guidance_marker(domain: DocumentDomain, language: AnswerLanguage) -> str:
    template = _GENERAL_GUIDANCE_MARKER.get(language, _GENERAL_GUIDANCE_MARKER[AnswerLanguage.EN])
    return template.format(referral_target=_referral_target(domain, language))


def _catalog_answer_text(
    groups: Sequence[CatalogGroup], language: AnswerLanguage = AnswerLanguage.VI
) -> str:
    """Deterministic composition for `AnswerMode.CATALOG` (spec §8.3): document titles are
    metadata, not quoted chunk evidence, so this is plain string formatting, never an LLM call."""
    if not groups:
        return (
            "Hiện chưa có tài liệu nào trong phạm vi bạn được xem."
            if language is AnswerLanguage.VI
            else "There are currently no documents available within your access scope."
        )
    lines = [
        "Đây là các tài liệu bạn có thể xem:"
        if language is AnswerLanguage.VI
        else "These are the documents available to you:"
    ]
    for group in groups:
        lines.append(f"- {group.category}: " + ", ".join(group.titles))
    return "\n".join(lines)


def _merge_candidate_sets(*groups: Sequence[RetrievalResult]) -> list[RetrievalResult]:
    """Dedupe candidates from independent retrieval calls by `chunk_id`, keeping whichever
    occurrence has the higher `dense_score` -- the one similarity metric that is a real,
    query-embedding-comparable value (unlike `hybrid_score`, whose RRF rank is call-local) --
    so a chunk gets credit for its best showing across calls, not whichever call happened to
    surface it first. Used to fix over-bias from Tier-1 query expansion (2026-08-22 live-probe
    finding): see the caller in `_ask_traced` for why this is additive, not a threshold change.
    """
    best: dict[int, RetrievalResult] = {}
    for group in groups:
        for candidate in group:
            chunk_id = candidate.chunk.chunk_id
            existing = best.get(chunk_id)
            if existing is None or (candidate.dense_score or -1.0) > (existing.dense_score or -1.0):
                best[chunk_id] = candidate
    return list(best.values())


_MULTI_ENTITY_LIST = re.compile(r":\s*([^:]+)$")
_MULTI_ENTITY_SPLIT = re.compile(r",\s*|\s+(?:và|and)\s+")
_MULTI_ENTITY_FANOUT_MAX = int(
    load_chunking_config()["chat"].get("multi_entity_fanout_max", 8)
)
_SYNTHESIS_REQUEST = re.compile(
    r"\b(?:architecture|overview|components?|interact(?:ion|ions)?|compare|comparison|"
    r"kiến\s*trúc|tổng\s*quan|thành\s*phần|tương\s*tác|so\s*sánh|liệt\s*kê|"
    r"giải\s*thích)\b",
    re.IGNORECASE,
)


def _multi_entity_retrieval_queries(resolved_question: str) -> list[str] | None:
    """B2 remediation (F5 audit): bounded retrieval fan-out for a clearly-identified multi-entity
    `resolved_question` -- the exact enumerated-list shape `turn_interpreter`'s own KNOWLEDGE-vs-
    REUSE worked example teaches the model to produce for a "explain each component in depth"
    request (e.g. "Vai trò và cách hoạt động của từng thành phần trong dự án: Sidecar, Store "
    "Gateway, Compactor, Receiver, Ruler, Query Gateway"). One broad retrieval call spreads its
    top-k thin across every named entity; claim-level validation already lets whichever entities
    got real evidence survive independently (`claim_validation.validate_claims` is unchanged), so
    the missing piece was giving each entity its own retrieval pass at all.

    Returns `None` -- meaning "do the single ordinary retrieval call, byte-identical to before
    this existed" -- unless `resolved_question` ends in a colon followed by >=2 short,
    comma/"và"/"and"-separated items. A narrow, deterministic shape match on the interpreter's own
    documented output format, never a general-purpose query planner: an ordinary sentence that
    happens to contain a colon (e.g. "Ví dụ: ...") does not match, because a real enumerated
    entity list is short items, not sentence fragments. Bounded to `_MULTI_ENTITY_FANOUT_MAX`
    retrieval calls so a long list still costs a fixed, small multiple of one call's latency.
    """
    match = _MULTI_ENTITY_LIST.search(resolved_question)
    if not match:
        return None
    tail = match.group(1).strip().rstrip(".")
    entities = [part.strip() for part in _MULTI_ENTITY_SPLIT.split(tail) if part.strip()]
    if len(entities) < 2 or any(len(entity) > 40 or len(entity.split()) > 5 for entity in entities):
        return None
    prefix = resolved_question[: match.start()].strip()
    entities = entities[:_MULTI_ENTITY_FANOUT_MAX]
    return [f"{prefix}: {entity}" if prefix else entity for entity in entities]


def _redact_observed(value: str) -> tuple[str, bool]:
    started = time.monotonic_ns()
    try:
        return redact(value)
    finally:
        record_duration("secret_scan", started)


def _redact_chunk_content(
    chunk_id: int, content: str, memo: dict[int, tuple[str, bool]]
) -> tuple[str, bool]:
    """Scan one chunk's content at most once per turn.

    The same chunk can back several claims, and chunk bodies are the largest strings on
    the output path — detect-secrets over the same text N times buys nothing.
    """
    if chunk_id not in memo:
        memo[chunk_id] = _redact_observed(content)
    return memo[chunk_id]


class ConversationNotFoundError(LookupError):
    """Unknown conversation, or one owned by another user. The two must be indistinguishable."""


class ConversationScopeMismatchError(Exception):
    """The request's scope differs from the scope frozen into the conversation at creation."""


@dataclass(frozen=True)
class ChatResult:
    answer: str
    citations: tuple[dict[str, object], ...]
    fallback: bool
    fallback_reason: str | None
    trace_id: str
    conversation_id: uuid.UUID
    answer_status: str = "verified"
    validator_outcome: str | None = None
    claims: tuple[dict[str, object], ...] = ()
    conflict: str | None = None
    # F5_BOUNDED_GENERAL_KNOWLEDGE_SPEC.md §5.4: additive, defaulted -- no existing client or
    # test breaks. `general_guidance` is `{"text": str, "kind": str}` per item.
    general_guidance: tuple[dict[str, object], ...] = ()
    answer_shape: str = "internal_only"  # internal_only | mixed | guidance_only
    # Mirrors the trace error code for callers without database access.
    error_code: str | None = None
    # Metadata for incomplete responses; the answer contains the user-facing disclosure.
    task_incomplete: bool = False


def _question_language(question: str) -> str:
    # This is only a config-key selector. The fixture sweep replaces bootstrap values.
    return "vi" if any("À" <= char <= "ỹ" for char in question) else "en"


@dataclass(frozen=True)
class ConversationPresentationPreferences:
    """Trusted conversation-scoped presentation state.

    This is state, not language detection. It changes only through a validated
    `ConversationControl` patch and therefore safely outranks surface cues from later turns.
    """

    language: str | None = None
    detail: str | None = None

    def apply(self, control: ConversationControl) -> ConversationPresentationPreferences:
        if not control.updates_presentation:
            return self
        patch = control.presentation
        return ConversationPresentationPreferences(
            language=patch.language if patch.language is not None else self.language,
            detail=patch.detail if patch.detail is not None else self.detail,
        )


def _effective_response_length(
    control_detail: str | None,
    conversation_detail: str | None,
    turn_detail: str | None,
    persisted: ResponseLength,
) -> ResponseLength:
    detail = control_detail or conversation_detail or turn_detail
    if detail == "concise":
        return ResponseLength.CONCISE
    if detail == "detailed":
        return ResponseLength.DETAILED
    return persisted


def _effective_answer_language(
    control_language: str | None,
    conversation_preferred: str | None,
    turn_language: str | None,
    question: str,
) -> AnswerLanguage:
    """Resolve control state before any fallible surface-language signal.

    A validated explicit update wins immediately; otherwise the established conversation state
    wins over the model's turn overlay and script detection. This is the key invariant that stops
    an English knowledge question from silently undoing an earlier Vietnamese preference.
    """
    language = control_language or conversation_preferred or turn_language
    if language == "vi":
        return AnswerLanguage.VI
    if language == "en":
        return AnswerLanguage.EN
    return AnswerLanguage.VI if _question_language(question) == "vi" else AnswerLanguage.EN


def _presentation_control_ack(
    control: ConversationControl, language: AnswerLanguage
) -> str:
    """Acknowledge a validated control patch without consulting transcript or retrieval."""
    patch = control.presentation
    if patch.language is not None and patch.detail is None:
        return build_social_reply(SocialIntent.LANGUAGE_PREFERENCE, patch.language)
    if language is AnswerLanguage.VI:
        changes: list[str] = []
        if patch.language == "vi":
            changes.append("trả lời bằng tiếng Việt")
        elif patch.language == "en":
            changes.append("trả lời bằng tiếng Anh")
        if patch.detail == "concise":
            changes.append("trả lời ngắn gọn")
        elif patch.detail == "detailed":
            changes.append("trả lời chi tiết")
        return "Được rồi, từ giờ mình sẽ " + " và ".join(changes) + "."
    changes = []
    if patch.language == "vi":
        changes.append("reply in Vietnamese")
    elif patch.language == "en":
        changes.append("reply in English")
    if patch.detail == "concise":
        changes.append("keep replies concise")
    elif patch.detail == "detailed":
        changes.append("give detailed replies")
    return "Understood. From now on, I'll " + " and ".join(changes) + "."


_EXPLICIT_LANGUAGE_CONTROL = re.compile(
    r"\b(?P<language>ti[eế]ng\s+anh|english|ti[eế]ng\s+vi[eệ]t|vietnamese)\b", re.IGNORECASE
)
_LANGUAGE_REANSWER_MARKERS = re.compile(
    r"(?:trả lời|nói lại|nhắc lại|answer|repeat|say that again)", re.IGNORECASE
)
_LANGUAGE_EXPLICIT_PREVIOUS_MARKERS = re.compile(
    r"(?:câu trên|phần.*trước|nói lại|nhắc lại|repeat|that answer|answer that|say that again)",
    re.IGNORECASE,
)
_LANGUAGE_PERSIST_MARKERS = re.compile(
    r"(?:từ giờ|về sau|luôn|cứ dùng|from now on|afterwards|keep using|always)", re.IGNORECASE
)


def _explicit_language_control(question: str) -> tuple[str, bool, bool] | None:
    """Recognise an unambiguous presentation-only language command deterministically.

    This is deliberately narrower than natural-language routing: it only handles a message that
    explicitly names a supported target language and contains only presentation verbs/markers.
    It prevents a stochastic interpreter response from losing a durable user preference, while
    leaving mixed factual questions and ordinary social language to the interpreter.
    """
    match = _EXPLICIT_LANGUAGE_CONTROL.search(question)
    if match is None:
        return None
    normalized = question.casefold()
    language = "en" if match.group("language").casefold() in {"english", "tiếng anh"} else "vi"
    persist_future = bool(_LANGUAGE_PERSIST_MARKERS.search(normalized))
    apply_now = bool(_LANGUAGE_REANSWER_MARKERS.search(normalized)) and (
        not persist_future or bool(_LANGUAGE_EXPLICIT_PREVIOUS_MARKERS.search(normalized))
    )
    # A bare "use Vietnamese" is a preference even without a re-answer verb.  Conversely, an
    # explicit re-answer without a standing marker applies only to the immediately prior answer.
    if not (persist_future or apply_now or "dùng" in normalized or "use " in normalized):
        return None
    return language, apply_now, persist_future


def _phase_categories(status: PlanStatus | None) -> frozenset[DocumentCategory]:
    """Pure PROJECT retrieval policy; approved conventions are phase-independent.

    SoT (BO_06_CLAUDE_PROJECT_SOURCE_OF_TRUTH.md line 344): "Chỉ plan APPROVED/ACTIVE được
    phát cho Engineer" -- APPROVED already grants the engineer full plan access, so it must
    grant the same base document categories as ACTIVE. There is no code path that ever moves
    a plan APPROVED -> ACTIVE (that's the unbuilt "engineer starts onboarding" step), so gating
    on ACTIVE alone permanently locked chat for every plan created through the app.

    `CONVENTION` is intentionally outside the onboarding-phase policy: an approved convention
    is already project-scoped and human-reviewed at ingestion time. The caller has separately
    established an active membership before reaching this function, so this only makes that
    approved project knowledge retrievable; it does not change authorization or answer logic.
    """
    base = frozenset(
        {
            DocumentCategory.OVERVIEW,
            DocumentCategory.ARCHITECTURE,
            DocumentCategory.SETUP,
            DocumentCategory.ACCESS_SECURITY,
            DocumentCategory.CODEBASE_GUIDE,
        }
    )
    phase_categories = {
        PlanStatus.APPROVED: base,
        PlanStatus.ACTIVE: base,
        PlanStatus.PROJECT_READY: frozenset(DocumentCategory),
    }.get(status, frozenset())
    return phase_categories | frozenset({DocumentCategory.CONVENTION})


class RelevanceGate:
    def __init__(self, config: dict | None = None) -> None:
        self.settings = (config or load_chunking_config())["chat"]

    def evidence_capacity_for(
        self, question: str, *, has_multi_entity_fanout: bool = False
    ) -> tuple[int, int]:
        """Select a configured evidence envelope without changing relevance acceptance.

        The signal is the already-resolved question plus the existing structured fan-out shape;
        it is deliberately only a capacity choice, not another route/LLM classifier.
        """
        default_chunks = int(self.settings["max_chunks_per_domain"])
        default_tokens = int(self.settings["context_max_tokens"])
        if not (has_multi_entity_fanout or _SYNTHESIS_REQUEST.search(question)):
            return default_chunks, default_tokens
        synthesis = self.settings.get("synthesis_evidence_capacity", {})
        return (
            int(synthesis.get("max_chunks_per_domain", default_chunks)),
            int(synthesis.get("context_max_tokens", default_tokens)),
        )

    def accept(
        self,
        question: str,
        candidates: list[RetrievalResult],
        *,
        max_chunks_per_domain: int | None = None,
    ) -> list[RetrievalResult]:
        trace = current_trace()
        attempt = trace.next_attempt("gate") if trace is not None else 1
        diagnostics: list[dict[str, object]] = []
        with telemetry_span("gate", attempt=attempt):
            language = _question_language(question)
            query_identifiers = {
                item.casefold() for item in lexical_identifiers(question).splitlines()
            }
            accepted: list[RetrievalResult] = []
            for candidate in candidates:
                domain = candidate.knowledge_domain.value.lower()
                threshold = self.settings["relevance_gate"][domain].get(
                    language, self.settings["relevance_gate"][domain]["en"]
                )
                dense_ok = (candidate.dense_score or 0.0) >= float(
                    threshold["min_dense_cosine"]
                )
                chunk_identifiers = {
                    item.casefold()
                    for item in candidate.chunk.lexical_identifiers.splitlines()
                }
                lexical_ok = (
                    bool(query_identifiers & chunk_identifiers)
                    and (candidate.bm25_score or 0.0) >= float(threshold["min_lexical_score"])
                )
                diagnostics.append(
                    {
                        "chunk_id": candidate.chunk.chunk_id,
                        "dense_pass": dense_ok,
                        "lexical_pass": lexical_ok,
                    }
                )
                if dense_ok or lexical_ok:
                    accepted.append(candidate)
            accepted.sort(key=lambda item: (-item.hybrid_score, item.chunk.chunk_id))
            per_domain = max_chunks_per_domain or int(self.settings["max_chunks_per_domain"])
            counts: dict[DocumentDomain, int] = {}
            bounded: list[RetrievalResult] = []
            for item in accepted:
                if counts.get(item.knowledge_domain, 0) < per_domain:
                    bounded.append(item)
                    counts[item.knowledge_domain] = counts.get(item.knowledge_domain, 0) + 1
        if trace is not None:
            trace.annotate(
                accepted_count=len(bounded),
                selected_chunk_ids=[item.chunk.chunk_id for item in bounded],
                gate_decision="accepted" if bounded else "rejected",
                decision_details={
                    "gate_candidates": diagnostics,
                    "max_chunks_per_domain": per_domain,
                },
            )
        return bounded


@dataclass(frozen=True)
class TranscriptTurn:
    turn_index: int
    question: str
    answer: str | None
    fallback: bool
    fallback_reason: str | None
    trace_id: str | None
    citations: tuple[dict[str, object], ...]
    answer_status: str | None = None
    validator_outcome: str | None = None
    claims: tuple[dict[str, object], ...] = ()
    conflict: str | None = None
    general_guidance: tuple[dict[str, object], ...] = ()
    answer_shape: str = "internal_only"


@dataclass(frozen=True)
class ConversationTranscript:
    conversation_id: uuid.UUID
    knowledge_domain: DocumentDomain
    membership_id: int | None
    turns: tuple[TranscriptTurn, ...]


@dataclass
class _Turn:
    """Everything the current turn needs to finish, whichever branch it exits through."""

    conversation_id: uuid.UUID
    session_id: int
    index: int
    trace_id: str
    window: ConversationWindow
    condensed: CondensedQuery
    answer_mode: AnswerMode = AnswerMode.KNOWLEDGE
    # AnswerMode.CONVERSATION only: the raw messages `_begin_turn` loaded, before `build_window`'s
    # KNOWLEDGE-specific bounding. Empty/unused for AnswerMode.KNOWLEDGE turns.
    raw_history: tuple[ChatMessage, ...] = ()
    presentation_preferences: ConversationPresentationPreferences = (
        ConversationPresentationPreferences()
    )

    topic_state: TopicState = TopicState()
    # Resolved once for the turn and consumed by every terminal renderer, including fallbacks.
    answer_language: AnswerLanguage = AnswerLanguage.EN
    effective_response_length: ResponseLength = ResponseLength.STANDARD
    affect_support_needed: bool = False
    affect_language: AnswerLanguage = AnswerLanguage.VI
    interpretation_degraded: bool = False

    @property
    def preferred_language(self) -> str | None:
        """Compatibility view for the existing SOCIAL renderer."""
        return self.presentation_preferences.language


@dataclass(frozen=True)
class _HistoryTurn:
    """One prior turn grouped from `_Turn.raw_history`, keeping the ASSISTANT row's
    `message_id` (unlike `conversation_memory._group_turns`, which only the interpreter's
    evidence-title lookup and the REUSE contract's citation walk need)."""

    index: int
    question: str
    answer: str | None
    grounded: bool
    assistant_message_id: int | None
    # Trusted, server-derived phrase for how the turn ENDED (`turn_outcome.describe_turn_outcome`),
    # from the persisted `fallback_reason`/`answer_status`/`grounded` triple. `None` when the turn
    # has no assistant row yet. Consumed by `_interpreter_context` (so the router can recognise a
    # question ABOUT a prior outcome) and by `_answer_conversation_mode` (so it can answer one).
    outcome: str | None = None


def _group_history_turns(messages: Sequence[ChatMessage]) -> list[_HistoryTurn]:
    questions: dict[int, str] = {}
    answers: dict[int, tuple[str, bool, int, str]] = {}
    for message in messages:
        if message.role is MessageRole.USER:
            questions.setdefault(message.turn_index, message.content)
        elif message.role is MessageRole.ASSISTANT:
            grounded = bool(message.grounded) and message.fallback_reason is None
            answers.setdefault(
                message.turn_index,
                (
                    message.content,
                    grounded,
                    message.message_id,
                    describe_turn_outcome(
                        grounded=bool(message.grounded),
                        fallback_reason=message.fallback_reason,
                        answer_status=message.answer_status,
                    ),
                ),
            )
    turns: list[_HistoryTurn] = []
    for index in sorted(questions):
        answer = answers.get(index)
        turns.append(
            _HistoryTurn(
                index=index,
                question=questions[index],
                answer=answer[0] if answer else None,
                grounded=bool(answer and answer[1]),
                assistant_message_id=answer[2] if answer else None,
                outcome=answer[3] if answer else None,
            )
        )
    return turns


@dataclass(frozen=True)
class _ReuseAttempt:
    """R2/R3 result: the reloaded (ACL/version-revalidated) evidence plus how many chunk ids the
    source turn originally cited -- `0 < len(reloaded) < original_count` is R4's partial-survival
    case."""

    reloaded: list[RetrievalResult]
    original_count: int


def _citation_source_url(evidence: RetrievalResult) -> str | None:
    return evidence.source_url if is_conventions_route(evidence.source_url) else None


def _related_citation_payload(
    item: RetrievalResult, memo: dict[int, tuple[str, bool]]
) -> dict[str, object]:
    """Citation for `insufficient_evidence` evidence (target design item 3): the model never
    claimed this chunk answers the question -- there is no model-authored quote to anchor -- so
    `quote` holds a deterministic content preview instead. Shown, not asserted: the client must
    not render this the way it renders a claim's verified citation.
    """
    source_content, content_redacted = _redact_chunk_content(item.chunk.chunk_id, item.chunk.content, memo)
    preview = source_content[:320].rstrip()
    if len(source_content) > 320:
        preview += "…"
    return {
        "chunk_id": item.chunk.chunk_id,
        "quote": preview,
        "knowledge_domain": item.knowledge_domain.value,
        "relevance_score": item.dense_score if item.dense_score is not None else (item.bm25_score or 0.0),
        "redacted": content_redacted,
        "document_id": item.document_id,
        "version_id": item.version_id,
        "source_title": item.document_title,
        "source_url": _citation_source_url(item),
        "section_heading": item.chunk.section_path or item.chunk.heading,
        "anchor": item.chunk.anchor,
        "source_content": source_content,
    }


def _transcript_citation(citation: Citation, evidence: RetrievalResult | None) -> dict[str, object]:
    """The stored quote always survives; source metadata only if the chunk is still in scope."""
    quote, quote_redacted = _redact_observed(citation.quote)
    quote_redacted = quote_redacted or "[REDACTED]" in quote
    if evidence is None:
        return {
            "chunk_id": citation.chunk_id,
            "quote": quote,
            "knowledge_domain": "",
            "relevance_score": citation.relevance_score,
            "redacted": quote_redacted,
        }
    source_content, content_redacted = _redact_observed(evidence.chunk.content)
    return {
        "chunk_id": citation.chunk_id,
        "quote": quote,
        "knowledge_domain": evidence.knowledge_domain.value,
        "relevance_score": citation.relevance_score,
        "redacted": quote_redacted or content_redacted,
        "document_id": evidence.document_id,
        "version_id": evidence.version_id,
        "source_title": evidence.document_title,
        # Same rule as the live answer path: metadata yes, raw artifact link no.
        "source_url": _citation_source_url(evidence),
        "section_heading": evidence.chunk.section_path or evidence.chunk.heading,
        "anchor": evidence.chunk.anchor,
        "source_content": source_content,
    }


class ChatService:
    def __init__(
        self,
        session: AsyncSession,
        retrieval_engine,
        answer_generator: AnswerGenerator,
        *,
        query_rewriter: LlmQueryRewriter | None = None,
        scope_gate: ScopeGate | None = None,
        evidence_sufficiency_gate: EvidenceSufficiencyGate | None = None,
        turn_interpreter: TurnInterpreter | None = None,
        memory_config: MemoryConfig | None = None,
        telemetry_sink: TelemetrySink | None = None,
        budget_config: RequestBudgetConfig | None = None,
        chat_budget_guard: ChatBudgetGuard | None = None,
        conversation_answer_generator: ConversationAnswerGenerator | None = None,
        general_knowledge_config: GeneralKnowledgeConfig | None = None,
        support_reply: SupportReplyGenerator | None = None,
    ) -> None:
        self.session = session
        self.retrieval_engine = retrieval_engine
        self.answer_generator = answer_generator
        # Weakness #4: reuses `answer_generator`'s own LLM provider by default, so production
        # wiring (chat_router.py) needs no separate change -- pass this explicitly only in tests
        # that need to observe/control the conversation-mode call independently.
        self.conversation_answer_generator = conversation_answer_generator or (
            ConversationAnswerGenerator(answer_generator.provider)
            if hasattr(answer_generator, "provider")
            else None
        )
        self.gate = RelevanceGate()
        self.conversations = ConversationRepository(session)
        self.query_rewriter = query_rewriter
        self.scope_gate = scope_gate
        self.evidence_sufficiency_gate = evidence_sufficiency_gate
        self.turn_interpreter = turn_interpreter
        # `None` (the default) keeps `_answer_social_mode` a pure template lookup, so every test
        # and caller that constructs ChatService directly is byte-identical to before this
        # collaborator existed -- production wires it in chat_router.py. Same "default is not a
        # regression" convention as `conversation_answer_generator` above.
        self.support_reply = support_reply
        self.memory = memory_config or MemoryConfig.from_config()
        self.telemetry_sink = telemetry_sink or NullTelemetrySink()
        self.budget_config = budget_config or RequestBudgetConfig(25.0, 3.0, 20.0, 1.0)
        # Disabled by default (all-zero caps, generous window) so existing callers that
        # construct ChatService directly are unaffected; production wires the real singleton.
        self.chat_budget_guard = chat_budget_guard or ChatBudgetGuard(
            ChatBudgetConfig(0, 60.0, 0, 0.0, 0.0)
        )
        self.general_knowledge_config = general_knowledge_config or GeneralKnowledgeConfig()

    async def _scope(
        self, *, user_id: int, knowledge_domain: DocumentDomain, membership_id: int | None
    ) -> tuple[ProjectMembership | None, frozenset[DocumentCategory]]:
        if knowledge_domain is DocumentDomain.POLICY:
            if membership_id is not None:
                raise ValueError("membership_id must be omitted for POLICY chat")
            return None, frozenset()
        if membership_id is None:
            raise ValueError("membership_id is required for PROJECT chat")
        membership = await self.session.scalar(
            select(ProjectMembership).where(
                ProjectMembership.membership_id == membership_id,
                ProjectMembership.user_id == user_id,
                ProjectMembership.status == MembershipStatus.ACTIVE,
            )
        )
        if membership is None:
            raise PermissionError("active membership for the authenticated user is required")
        plan_status = await self.session.scalar(
            select(OnboardingPlan.status)
            .where(OnboardingPlan.membership_id == membership_id)
            .order_by(desc(OnboardingPlan.created_at))
            .limit(1)
        )
        return membership, _phase_categories(plan_status)

    @staticmethod
    def _assert_conversation_scope(
        conversation, knowledge_domain: DocumentDomain, membership: ProjectMembership | None
    ) -> None:
        """The conversation is never an authorization source — `_scope` already decided that.

        This only refuses to *reuse* a container whose frozen scope differs from the scope the
        server just derived, which is what keeps history from crossing a domain or a project.
        """
        expected_project = membership.project_id if membership else None
        expected_membership = membership.membership_id if membership else None
        if (
            conversation.knowledge_domain != knowledge_domain
            or conversation.project_id != expected_project
            or conversation.membership_id != expected_membership
        ):
            raise ConversationScopeMismatchError(
                "conversation scope does not match the requested chat scope"
            )

    async def _begin_turn(
        self,
        *,
        question: str,
        user_id: int,
        knowledge_domain: DocumentDomain,
        membership: ProjectMembership | None,
        conversation_id: uuid.UUID | None,
        trace_id: str,
        answer_mode: AnswerMode,
    ) -> _Turn:
        """Resolve the conversation, build the window, condense, then commit the USER message.

        The commit is the point: the audit trail of what was asked survives a crash anywhere
        downstream, and the window was read *before* this insert so it cannot contain the
        question being asked right now.

        `answer_mode` picks which history load runs (weakness #4): `KNOWLEDGE` reads the existing
        bounded sliding window (`load_with_window`, unchanged, still `self.memory.message_limit()`
        rows) and condenses the question for retrieval exactly as before; `CONVERSATION` reads the
        FULL authorized transcript (`load_full_history`, no row limit -- bounded later by a token
        budget in `build_conversation_transcript`) and never condenses, so a meta-question can
        never leak into `query_condenser`/retrieval as a noisy query (root cause #1, CHANGE_LOG.md
        2026-08-21).
        """
        with telemetry_span("conversation_context"):
            if conversation_id is None:
                conversation = await self.conversations.create(
                    user_id=user_id, knowledge_domain=knowledge_domain, membership=membership
                )
                history_messages: list[ChatMessage] = []
            else:
                if answer_mode is AnswerMode.CONVERSATION:
                    conversation, history_messages = await self.conversations.load_full_history(
                        public_id=conversation_id, user_id=user_id
                    )
                else:
                    conversation, history_messages = await self.conversations.load_with_window(
                        public_id=conversation_id, user_id=user_id, limit=self.memory.message_limit()
                    )
                if conversation is None:
                    raise ConversationNotFoundError("conversation not found")
                self._assert_conversation_scope(conversation, knowledge_domain, membership)

            if answer_mode is AnswerMode.CONVERSATION:
                window = ConversationWindow()
                condensed = CondensedQuery(question, followup_detected=False, tier="standalone")
            else:
                window = build_window(history_messages, self.memory)
                condensed = condense(question, window.anchor_questions, self.memory)
        turn_index = (
            max((message.turn_index for message in history_messages), default=-1) + 1
        )
        turn = _Turn(
            conversation_id=conversation.public_id,
            session_id=conversation.session_id,
            index=turn_index,
            trace_id=trace_id,
            window=window,
            condensed=condensed,
            answer_mode=answer_mode,
            raw_history=tuple(history_messages),
            presentation_preferences=ConversationPresentationPreferences(
                language=conversation.preferred_language,
                detail=conversation.preferred_response_detail,
            ),
            answer_language=_effective_answer_language(
                None, conversation.preferred_language, None, question
            ),
        )
        with telemetry_span("persistence.user"):
            self.conversations.append(
                session_id=turn.session_id,
                turn_index=turn.index,
                role=MessageRole.USER,
                content=question,
                trace_id=trace_id,
                # No retrieval ran for a CONVERSATION turn, so there is no retrieval query to
                # record -- leaving this NULL is itself an honest signal, not a placeholder.
                retrieval_query=(
                    condensed.retrieval_query if answer_mode is AnswerMode.KNOWLEDGE else None
                ),
            )
            await self.conversations.touch(session_id=turn.session_id)
            await self.session.commit()
        trace = current_trace()
        if trace is not None:
            trace.annotate(conversation_id=turn.conversation_id, turn_index=turn.index)
        return turn

    async def _fallback(
        self,
        turn: _Turn,
        *,
        reason: str,
        gate: str,
        validator: str | None = None,
        retry_count: int = 0,
        knowledge_domain: DocumentDomain = DocumentDomain.POLICY,
        related_evidence: Sequence[RetrievalResult] = (),
        suggestions: Sequence[str] = (),
    ) -> ChatResult:

        fallback_language = (
            turn.answer_language
            if turn.presentation_preferences.language is not None
            else AnswerLanguage.VI
        )
        answer = _with_affect_acknowledgement(
            _fallback_answer_text(
                reason, knowledge_domain, suggestions, language=fallback_language
            ),
            turn,
        )
        degraded_note = turn.interpretation_degraded and reason in _DEGRADED_NOTE_REASONS
        if degraded_note:
            answer = f"{answer}\n\n{_DEGRADED_INTERPRETATION_NOTE[fallback_language]}"
        citation_payloads: list[dict[str, object]] = []
        with telemetry_span("persistence.answer"):
            message = self.conversations.append(
                session_id=turn.session_id,
                turn_index=turn.index,
                role=MessageRole.ASSISTANT,
                content=answer,
                trace_id=turn.trace_id,
                grounded=False,
                fallback_reason=reason,
                answer_status="fallback",
                validator_outcome=validator,
            )
            if related_evidence:
                await self.session.flush()
                memo: dict[int, tuple[str, bool]] = {}
                for item in related_evidence:
                    payload = _related_citation_payload(item, memo)
                    citation_payloads.append(payload)
                    self.session.add(
                        Citation(
                            message_id=message.message_id,
                            claim_id=None,
                            chunk_id=item.chunk.chunk_id,
                            quote=payload["quote"],
                            relevance_score=payload["relevance_score"],
                        )
                    )
            await self.conversations.touch(session_id=turn.session_id)
            await self.session.commit()
        trace = current_trace()
        if trace is not None:
            if reason == "system_error" and not trace.has_attribute("error_code"):
                trace.annotate(error_stage="generation.provider", error_code="provider_error")
            trace.annotate(
                outcome="fallback",
                gate_decision=gate,
                validator_outcome=validator,
                fallback_reason=reason,
                repair_retry_count=retry_count,
                **(
                    {"decision_details": {"suggested_topics": list(suggestions)}}
                    if suggestions
                    else {}
                ),
            )
            if turn.interpretation_degraded:
                trace.annotate(
                    decision_details={
                        "interpretation_degraded_fallback": reason,
                        "degraded_reask_note": degraded_note,
                    }
                )
        return ChatResult(
            answer,
            tuple(citation_payloads),
            True,
            reason,
            turn.trace_id,
            turn.conversation_id,
            answer_status="fallback",
            validator_outcome=validator,
            error_code=trace.attribute("error_code") if trace is not None else None,
        )

    @staticmethod
    def _suggestions_from_evidence(
        evidence: Sequence[RetrievalResult], *, limit: int = 3
    ) -> tuple[str, ...]:
        """Target design item 5: suggestions for an `insufficient_evidence` turn come only from
        evidence already retrieved in THIS request -- no extra round trip, never invented."""
        seen: list[str] = []
        for item in evidence:
            title = item.document_title
            if title and title not in seen:
                seen.append(title)
            if len(seen) >= limit:
                break
        return tuple(seen)

    async def _find_reusable_evidence(
        self, turn: _Turn, *, filters: RetrievalFilters
    ) -> _ReuseAttempt | None:
        """F5 Semantic Turn Interpreter rev. 2 §6 R2/R3 (fixes a live bug, §7.4 item 1).

        Walks `turn.raw_history` **backwards** for the most recent ASSISTANT message that has
        >=1 `Citation` row -- i.e. was not a SOCIAL/CATALOG/CONVERSATION terminal reply, all three
        of which persist zero citations, so "has citations" is exactly the R2 predicate without
        needing to thread the original `AnswerMode` through history. Bounded by the existing
        memory window (`turn.raw_history`), so still no extra query to find the candidate turn.

        Previously required strict `turn_index == turn.index - 1` adjacency: since
        `_answer_social_mode` persists a citation-less assistant row, the sequence
        `question -> cảm ơn -> giải thích lại chi tiết hơn` found a citation-less previous turn,
        returned `None`, and fell through to fresh retrieval on a bare elaboration phrase --
        which would `no_evidence`. Fixed by walking further back past any citation-less reply.

        The chunk ids themselves are re-read via `load_scoped_chunks` (R3), which re-applies the
        CURRENT scope predicates, so a chunk archived, re-categorised, moved out of scope, or
        embedded with a different model since the original turn simply does not come back --
        this satisfies "reused evidence must be revalidated for ACL/version" on its own.
        """
        for message in reversed(turn.raw_history):
            if message.role is not MessageRole.ASSISTANT:
                continue
            citations = await self.conversations.citations_for_message(message.message_id)
            chunk_ids = list(dict.fromkeys(citation.chunk_id for citation in citations))
            if not chunk_ids:
                continue
            reloaded = await self.retrieval_engine.load_scoped_chunks(chunk_ids, filters=filters)
            return _ReuseAttempt(reloaded=reloaded, original_count=len(chunk_ids))
        return None

    async def _reused_related_evidence(
        self, turn: _Turn, *, question: str, filters: RetrievalFilters
    ) -> list[RetrievalResult] | None:
        """Legacy (pre-interpreter) reuse path. Target design item 4, narrowed by implementation
        spec §7 [REV2]. Returns `None` when there is nothing to reuse (the normal case); the
        caller then runs the retrieval pipeline exactly as before -- this is a pure optimization
        over the existing path, never a stricter gate.

        Eligible only when `classify_elaboration(question)` is true (§7.1) -- a narrow, closed,
        whole-utterance-anchored classifier for *pure* elaboration/rephrase/example requests,
        deliberately replacing the old broad `turn.condensed.followup_detected` gate: that marker
        set is tuned for query *expansion* (a false positive there only costs retrieval breadth),
        wrong for gating a whole LLM sufficiency-check call against possibly-stale evidence. A
        plain topic-switch follow-up ("còn VPN thì sao?") now never attempts reuse at all -- it
        goes straight to fresh retrieval below, spending zero `EvidenceSufficiencyGate` calls on
        evidence that was never going to answer it.

        Source selection is `_find_reusable_evidence` (R2/R3) -- shared with the interpreter-
        driven REUSE route below, which differs only in not gating on `classify_elaboration`
        (the interpreter's `route` already carries that decision, per rev. 2 R1).
        """
        if not classify_elaboration(question):
            return None
        attempt = await self._find_reusable_evidence(turn, filters=filters)
        if attempt is None:
            return None
        return attempt.reloaded or None

    async def _retrieve(self, query: str, filters: RetrievalFilters, budget) -> list[RetrievalResult]:
        return await self.retrieval_engine.retrieve(query, filters=filters, budget=budget)

    async def _expand_procedure_evidence(
        self,
        question: str,
        accepted: Sequence[RetrievalResult],
        *,
        filters: RetrievalFilters,
    ) -> list[RetrievalResult]:
        """Complete an ordered section without another model request or embedding call."""
        settings = self.gate.settings.get("procedure_section_expansion", {})
        expand = getattr(self.retrieval_engine, "expand_numbered_section", None)
        if (
            not settings.get("enabled", False)
            or len(accepted) < 2
            or _PROCEDURE_QUERY.search(question) is None
            or _TEST_FOCUSED_QUERY.search(question) is not None
            or expand is None
        ):
            return list(accepted)
        try:
            with telemetry_span("retrieval.procedure_section_expansion"):
                return await expand(
                    accepted,
                    filters=filters,
                    max_sequence_chunks=int(settings.get("max_sequence_chunks", 6)),
                    max_other_chunks=int(settings.get("max_other_chunks", 1)),
                )
        except Exception as exc:  # noqa: BLE001 - additive quality pass must fail open
            trace = current_trace()
            if trace is not None:
                trace.annotate(
                    decision_details={
                        "procedure_section_expanded": False,
                        "procedure_section_expansion_error": type(exc).__name__,
                    }
                )
            return list(accepted)

    async def _rewrite_and_retry(
        self, turn: _Turn, *, question: str, filters: RetrievalFilters, budget
    ) -> tuple[list[RetrievalResult], str | None]:
        """Tier 2. Only reached when the gate already returned nothing.

        Cost on a successful turn is therefore zero: this converts a certain `no_evidence` into
        one more attempt, and can never slow down an answer that was already going to work.

        Returns `(accepted, rewritten_query)`: `rewritten_query` is the string that actually
        produced `accepted` (non-empty) -- implementation spec §4/§9.1's `resolved_query` thread
        updates in place only when this Tier-2 rewrite is the one that won, never on a rewrite
        that itself found nothing.
        """
        if (
            self.query_rewriter is None
            or not self.memory.llm_rewrite_enabled
            or not turn.condensed.followup_detected
            or not turn.window.anchor_questions
        ):
            return [], None
        with telemetry_span("query_rewrite"):
            rewritten = await self.query_rewriter.rewrite(question, turn.window.anchor_questions, budget)
        trace = current_trace()
        if trace is not None:
            trace.annotate(
                decision_details={
                    "query_rewrite_outcome": "used"
                    if rewritten and rewritten != turn.condensed.retrieval_query
                    else "unusable"
                }
            )
        if not rewritten or rewritten == turn.condensed.retrieval_query:
            return [], None
        candidates = await self._retrieve(rewritten, filters, budget)
        accepted = self.gate.accept(question, candidates)
        if not accepted:
            return [], None
        # The query that produced the answer is the one worth reproducing later; the fact that
        # a rewrite happened is in `llm_call_logs` with stage='query_rewrite'.
        await self.conversations.set_retrieval_query(
            session_id=turn.session_id, turn_index=turn.index, query=rewritten
        )
        return accepted, rewritten

    async def _answer_conversation_mode(self, turn: _Turn, *, question: str, budget) -> ChatResult:
        """AnswerMode.CONVERSATION terminal branch (weakness #4, CHANGE_LOG.md 2026-08-21).

        Grounds in `turn.raw_history` only -- this conversation's own persisted, authorized
        messages, already scoped to the caller by `_begin_turn`'s ownership-checked load. No
        retrieval, no PROJECT/POLICY evidence, no citation validator: see the
        CONVERSATION_GROUNDED addendum in ARCHITECTURE.md for why INV9 does not apply here.
        """
        transcript = build_conversation_transcript(turn.raw_history, self.memory)
        if self.conversation_answer_generator is None:
            return await self._fallback(turn, reason="system_error", gate="conversation_mode")
        generated = await self.conversation_answer_generator.generate(
            question,
            transcript.turns,
            truncated=transcript.truncated,
            answer_language=turn.answer_language,
            budget=budget,
        )
        trace = current_trace()
        if trace is not None:
            trace.annotate(
                decision_details={
                    "answer_mode": AnswerMode.CONVERSATION.value,
                    "conversation_history_turns": len(transcript.turns),
                    "conversation_history_truncated": transcript.truncated,
                }
            )
        if isinstance(generated, ConversationAnswerFailure):
            return await self._fallback(turn, reason=generated.reason, gate="conversation_mode")

        answer, _answer_redacted = _redact_observed(generated.answer)
        self.conversations.append(
            session_id=turn.session_id,
            turn_index=turn.index,
            role=MessageRole.ASSISTANT,
            content=answer,
            trace_id=turn.trace_id,
            grounded=True,
            answer_status="verified",
        )
        await self.conversations.touch(session_id=turn.session_id)
        await self.session.commit()
        trace = current_trace()
        if trace is not None:
            if not trace.has_attribute("prompt_tokens"):
                trace.annotate(prompt_tokens=generated.prompt_tokens)
            if not trace.has_attribute("completion_tokens"):
                trace.annotate(completion_tokens=generated.completion_tokens)
            if not trace.has_attribute("model"):
                trace.annotate(model=generated.model)
            trace.annotate(gate_decision="conversation_mode")
        return ChatResult(
            answer,
            (),
            False,
            None,
            turn.trace_id,
            turn.conversation_id,
            answer_status="verified",
            validator_outcome=None,
            claims=(),
            conflict=None,
        )

    async def _answer_social_mode(
        self,
        turn: _Turn,
        *,
        question: str,
        budget,
        intent: SocialIntent | None = None,
        target_language: str | None = None,
        response_tone: ResponseTone = ResponseTone.NEUTRAL,
    ) -> ChatResult:
        """AnswerMode.SOCIAL terminal branch (implementation spec §6.3). Deterministic template
        lookup, zero LLM calls, zero retrieval -- same precedent `_answer_conversation_mode`
        already established for a terminal, always-grounded, evidence-free answer.

        `intent` lets a caller that already resolved a subtype (the interpreter path's own
        `verdict.social_intent`, including the interpreter-only `SocialIntent.OTHER`/
        `LANGUAGE_PREFERENCE`) pass it straight through. When omitted, `classify_social` is
        cheap, pure, deterministic regex, so recomputing it here costs nothing -- used by the two
        callers (legacy `AnswerMode.SOCIAL` and the pre-interpreter fast path) that only ever
        reach this branch because it already matched.

        `target_language` overrides both `turn.preferred_language` and `_question_language`'s
        heuristic (Vietnamese vs. English guessed from the CURRENT message's own script) --
        required for `SocialIntent.LANGUAGE_PREFERENCE`, where the reply must confirm IN the
        language the user just asked to SWITCH TO, not the language they happened to phrase that
        request in (e.g. an English "please answer in Vietnamese" must render the Vietnamese
        confirmation). Absent that, `turn.preferred_language` (CHANGE_LOG.md 2026-08-23 item 2 --
        an earlier turn's explicit switch, persisted on `ChatSession`) wins over the per-message
        script heuristic, so e.g. a bare "okay" after "please speak Vietnamese" still answers in
        Vietnamese instead of silently reverting to English.

        `response_tone` (2026-08-25, Option A') is the caller's persisted personalization
        preference, applied here through `build_social_reply`'s static warm/plain lookup -- the
        one place this branch was dropping it before, which is why the SOCIAL path alone did not
        personalize while `AnswerGenerator` already did via `build_style_instruction`. Still zero
        LLM calls: `social_reply.py` explains why a lookup, not a generated reply, is the right
        realizer for this closed output space.
        """
        resolved_intent = intent or classify_social(question)
        assert resolved_intent is not None  # only routes here when a subtype is already known
        reply_language = target_language or turn.preferred_language or _question_language(question)
        answer = build_social_reply(resolved_intent, reply_language, response_tone)

        support_outcome: str | None = None
        if resolved_intent is SocialIntent.BUDDY_SUPPORT and self.support_reply is not None:
            with telemetry_span("support_reply"):
                generated_support = await self.support_reply.generate(
                    utterance=question, language=reply_language, budget=budget
                )
            support_outcome = generated_support.outcome.value
            if generated_support.text is not None:
                answer = generated_support.text

        self.conversations.append(
            session_id=turn.session_id,
            turn_index=turn.index,
            role=MessageRole.ASSISTANT,
            content=answer,
            trace_id=turn.trace_id,
            grounded=True,
            answer_status="verified",
        )
        await self.conversations.touch(session_id=turn.session_id)
        await self.session.commit()
        trace = current_trace()
        if trace is not None:
            trace.annotate(
                gate_decision="social_mode",
                decision_details={
                    "answer_mode": AnswerMode.SOCIAL.value,
                    "social_intent": resolved_intent.value,
                    "social_reply_language_source": (
                        "turn" if target_language else "conversation" if turn.preferred_language else "detected"
                    ),
                    # Present only on a BUDDY_SUPPORT turn. Makes "how often does generation land,
                    # and when it does not, which validator rejected it" answerable from
                    # `llm_call_logs` -- the fallback is silent by design, so without this the
                    # feature could be failing closed 100% of the time and look identical.
                    **({"support_reply_outcome": support_outcome} if support_outcome else {}),
                },
            )
        return ChatResult(
            answer,
            (),
            False,
            None,
            turn.trace_id,
            turn.conversation_id,
            answer_status="verified",
            validator_outcome=None,
            claims=(),
            conflict=None,
        )

    async def _answer_presentation_control(
        self, turn: _Turn, *, control: ConversationControl
    ) -> ChatResult:
        """Terminal ACK for a pure presentation-control turn.

        The state patch has already been staged by the dispatcher. This renderer is shared by
        language and detail controls and deliberately performs no retrieval or generation.
        """
        answer = _presentation_control_ack(control, turn.answer_language)
        self.conversations.append(
            session_id=turn.session_id,
            turn_index=turn.index,
            role=MessageRole.ASSISTANT,
            content=answer,
            trace_id=turn.trace_id,
            grounded=True,
            answer_status="verified",
        )
        await self.conversations.touch(session_id=turn.session_id)
        await self.session.commit()
        trace = current_trace()
        if trace is not None:
            trace.annotate(
                gate_decision="conversation_control",
                decision_details={
                    "answer_mode": AnswerMode.SOCIAL.value,
                    "conversation_control": control.kind.value,
                    # This is a terminal acknowledgement path. Record the fact explicitly so
                    # conversation evals can assert that a standing preference update did not
                    # accidentally trigger retrieval (rather than inferring it from no citations).
                    "retrieval_call_count": 0,
                    "presentation_language": control.presentation.language,
                    "presentation_detail": control.presentation.detail,
                },
            )
        return ChatResult(
            answer,
            (),
            False,
            None,
            turn.trace_id,
            turn.conversation_id,
            answer_status="verified",
            validator_outcome=None,
            claims=(),
            conflict=None,
        )

    async def _answer_catalog_mode(
        self, turn: _Turn, *, filters: RetrievalFilters
    ) -> ChatResult:
        """Terminal ACK for a pure catalog-mode turn."""
        groups = await self.retrieval_engine.list_catalog(filters)
        answer = _catalog_answer_text(groups, turn.answer_language)
        self.conversations.append(
            session_id=turn.session_id,
            turn_index=turn.index,
            role=MessageRole.ASSISTANT,
            content=answer,
            trace_id=turn.trace_id,
            grounded=True,
            answer_status="verified",
        )
        await self.conversations.touch(session_id=turn.session_id)
        await self.session.commit()
        trace = current_trace()
        if trace is not None:
            trace.annotate(
                gate_decision="catalog_mode",
                decision_details={
                    "answer_mode": AnswerMode.CATALOG.value,
                    "catalog_group_count": len(groups),
                },
            )
        return ChatResult(
            answer,
            (),
            False,
            None,
            turn.trace_id,
            turn.conversation_id,
            answer_status="verified",
            validator_outcome=None,
            claims=(),
            conflict=None,
        )

    # ------------------------------------------------------------------------------------------
    # F5 Semantic Turn Interpreter (rev. 2). Phase 1 (shadow) and Phase 2 (authoritative routing).
    # Config: `chat.turn_interpreter` in chunking_params.yaml. Both phases share the context
    # builder below; only `_ask_with_interpreter` (Phase 2) acts on the verdict.
    # ------------------------------------------------------------------------------------------

    async def _evidence_titles(
        self, message_id: int, filters: RetrievalFilters
    ) -> tuple[str, ...]:
        """Rev. 2 §5.2: document titles only, never chunk content -- the interpreter's input
        contract deliberately excludes retrieved text (large, no routing benefit, doubles the
        untrusted surface). Sourced through `load_scoped_chunks`, the same current-scope reload
        every reuse/transcript path already uses -- no second predicate set."""
        config = self.turn_interpreter.config
        citations = await self.conversations.citations_for_message(message_id)
        chunk_ids = list(dict.fromkeys(citation.chunk_id for citation in citations))
        if not chunk_ids:
            return ()
        results = await self.retrieval_engine.load_scoped_chunks(chunk_ids, filters=filters)
        titles: list[str] = []
        seen: set[str] = set()
        for item in results:
            title = item.document_title
            if not title or title in seen:
                continue
            seen.add(title)
            titles.append(truncate(title, config.evidence_title_max_chars))
            if len(titles) >= config.evidence_titles_max:
                break
        return tuple(titles)

    async def _interpreter_context(
        self,
        turn: _Turn,
        *,
        question: str,
        knowledge_domain: DocumentDomain,
        project_name: str | None,
        filters: RetrievalFilters,
    ) -> InterpreterContext:
        """Rev. 2 §5's exact input contract, built from `turn.raw_history` (prior turns only --
        the current turn's own USER row is never in there, see `_begin_turn`/
        `_begin_interpreted_turn`). Depth is `chat.turn_interpreter.turn_pairs`, a config key
        separate from `conversation_memory.max_turn_pairs` (§5.2)."""
        config = self.turn_interpreter.config
        history_turns = _group_history_turns(turn.raw_history)
        recent = history_turns[-config.turn_pairs :] if config.turn_pairs > 0 else []

        def _to_prior(item: _HistoryTurn) -> PriorTurn:
            return PriorTurn(
                question=truncate(item.question, config.prev_question_max_chars),
                grounded=item.grounded,
                answer_summary=truncate(item.answer, config.prev_answer_max_chars) if item.answer else "",
                outcome=item.outcome,
            )

        previous_turn = _to_prior(recent[-1]) if recent else None
        turn_before_that = _to_prior(recent[-2]) if len(recent) > 1 else None
        evidence_titles: tuple[str, ...] = ()
        if recent and recent[-1].grounded and recent[-1].assistant_message_id is not None:
            evidence_titles = await self._evidence_titles(recent[-1].assistant_message_id, filters)
        return InterpreterContext(
            knowledge_domain=knowledge_domain,
            current_utterance=question,
            project_name=project_name,
            previous_turn=previous_turn,
            turn_before_that=turn_before_that,
            evidence_titles=evidence_titles,
            presentation_preferences=PresentationOverlay(
                language=turn.presentation_preferences.language,
                detail=turn.presentation_preferences.detail,
            ),
            topic_state=turn.topic_state,
        )

    async def _run_shadow_interpreter(
        self,
        turn: _Turn,
        *,
        question: str,
        knowledge_domain: DocumentDomain,
        project_name: str | None,
        filters: RetrievalFilters,
        budget,
        legacy_answer_mode: AnswerMode,
    ) -> None:
        """Phase 1: runs and logs, changes nothing. Any failure here -- including one the
        interpreter itself does not already fail open on -- must never affect the real answer."""
        try:
            context = await self._interpreter_context(
                turn,
                question=question,
                knowledge_domain=knowledge_domain,
                project_name=project_name,
                filters=filters,
            )
            verdict = await self.turn_interpreter.interpret(context, budget)
        except Exception:  # noqa: BLE001 - shadow mode is strictly additive, never load-bearing
            return
        trace = current_trace()
        if trace is not None:
            trace.annotate(
                decision_details={
                    "shadow_interpreter_route": verdict.route.value,
                    "shadow_interpreter_scope": verdict.scope.value,
                    "shadow_interpreter_resolved_question": verdict.resolved_question,
                    "shadow_interpreter_agrees_with_legacy": verdict.route.value
                    == legacy_answer_mode.value,
                }
            )

    async def _begin_interpreted_turn(
        self,
        *,
        question: str,
        user_id: int,
        knowledge_domain: DocumentDomain,
        membership: ProjectMembership | None,
        conversation_id: uuid.UUID | None,
        trace_id: str,
    ) -> _Turn:
        """Phase 2's `_begin_turn` sibling. Unlike the legacy path, the history load can no
        longer be chosen by `AnswerMode` -- that decision now belongs to the interpreter, which
        needs the history loaded *before* it can run. Always loads the FULL authorized transcript
        (same ownership-checked `load_full_history` `AnswerMode.CONVERSATION` already uses) and
        derives every bounded view on top of it in Python: `build_window` for KNOWLEDGE/REUSE
        generation, and `_interpreter_context`'s own `turn_pairs` truncation for the interpreter
        itself. `_Turn.condensed`/`answer_mode` are unused placeholders on this path -- routing
        comes entirely from the interpreter's verdict.
        """
        with telemetry_span("conversation_context"):
            if conversation_id is None:
                conversation = await self.conversations.create(
                    user_id=user_id, knowledge_domain=knowledge_domain, membership=membership
                )
                history_messages: list[ChatMessage] = []
            else:
                conversation, history_messages = await self.conversations.load_full_history(
                    public_id=conversation_id, user_id=user_id
                )
                if conversation is None:
                    raise ConversationNotFoundError("conversation not found")
                self._assert_conversation_scope(conversation, knowledge_domain, membership)
            window = build_window(history_messages, self.memory)
        turn_index = (
            max((message.turn_index for message in history_messages), default=-1) + 1
        )
        turn = _Turn(
            conversation_id=conversation.public_id,
            session_id=conversation.session_id,
            index=turn_index,
            trace_id=trace_id,
            window=window,
            condensed=CondensedQuery(question, followup_detected=False, tier="standalone"),
            answer_mode=AnswerMode.KNOWLEDGE,
            raw_history=tuple(history_messages),
            presentation_preferences=ConversationPresentationPreferences(
                language=conversation.preferred_language,
                detail=conversation.preferred_response_detail,
            ),
            topic_state=TopicState(
                subject=conversation.topic_subject,
                entities=decode_topic_entities(conversation.topic_entities),
            ),
            answer_language=_effective_answer_language(
                None, conversation.preferred_language, None, question
            ),
        )
        with telemetry_span("persistence.user"):
            self.conversations.append(
                session_id=turn.session_id,
                turn_index=turn.index,
                role=MessageRole.USER,
                content=question,
                trace_id=trace_id,
                retrieval_query=None,
            )
            await self.conversations.touch(session_id=turn.session_id)
            await self.session.commit()
        trace = current_trace()
        if trace is not None:
            trace.annotate(conversation_id=turn.conversation_id, turn_index=turn.index)
        return turn

    @staticmethod
    def _previous_retrieval_query(turn: _Turn) -> str | None:
        """R4: the previous USER row's persisted `retrieval_query`, walking back past any turn
        that legitimately has none (a REUSE turn that never retrieved, a CONVERSATION/SOCIAL/
        CATALOG turn) to the last turn that actually ran retrieval."""
        for message in reversed(turn.raw_history):
            if message.role is MessageRole.USER and message.retrieval_query:
                return message.retrieval_query
        return None

    def _budget_allows_recovery(self, budget) -> bool:
        """R5 bound: the recovery costs one more `EvidenceSufficiencyGate` call plus generation --
        skip it rather than spend the request's last LLM budget on a call likely to be cut off.

        Reads the gate's configured timeout defensively (`getattr`, not an attribute access) --
        the collaborator is only required to satisfy `EvidenceSufficiencyGate`'s `check()` shape
        (any test double honoring that duck type is valid), not its concrete `config` attribute.
        """
        config = getattr(self.evidence_sufficiency_gate, "config", None)
        esg_timeout = getattr(config, "timeout_seconds", 3.0)
        return budget.remaining_llm() > esg_timeout

    async def _pre_route_scope_check(
        self,
        raw_utterance: str,
        *,
        project_name: str | None,
        knowledge_domain: DocumentDomain,
        budget,
        has_prior_turn: bool = False,
    ) -> bool:
        if self.scope_gate is None:
            return True
        with telemetry_span("scope_gate"):
            return await self.scope_gate.is_in_scope(
                raw_utterance,
                budget,
                subject_name=project_name,
                knowledge_domain=knowledge_domain,
                has_prior_turn=has_prior_turn,
            )

    @staticmethod
    def _annotate_retrieval_layer_failure(
        failure: ExternalServiceFailure | RetrievalUnavailableError, budget
    ) -> None:
        """Both exception types mean the same thing to a caller of `_retrieve`: evidence could
        not be fetched for an environmental reason, never a grounding/content judgement. Kept as
        one annotation point (previously three near-duplicate inline blocks) so the two anticipated
        failure classes -- an embedding/LLM provider outage (`ExternalServiceFailure`) and our own
        datastore misbehaving (`RetrievalUnavailableError`, F5 audit 2026-08-29 HTTP 500 fix) --
        stay symmetric at every call site instead of drifting."""
        trace = current_trace()
        if trace is None:
            return
        if isinstance(failure, ExternalServiceFailure):
            trace.annotate(
                error_stage="retrieval.embedding",
                error_code="embedding_unavailable",
                external_service=failure.service,
                external_failure_code=failure.code.value,
                provider_retry_count=max(0, failure.attempts - 1),
                timeout_scope=failure.timeout_scope,
                external_operation="embedding",
                remaining_budget_ms=round(budget.remaining_total() * 1000),
            )
        else:
            trace.annotate(
                error_stage=failure.stage,
                error_code="retrieval_unavailable",
                remaining_budget_ms=round(budget.remaining_total() * 1000),
            )

    async def _recover_retrieval_datastore_failure(
        self, failure: ExternalServiceFailure | RetrievalUnavailableError
    ) -> None:
        """Reset the request session before persistence after a datastore retrieval failure.

        Retrieval shares the request session. PostgreSQL marks its transaction aborted after the
        ParadeDB error, while the USER message is already committed by `_begin_turn`.
        """
        if not isinstance(failure, RetrievalUnavailableError):
            return
        await self.session.rollback()
        trace = current_trace()
        if trace is not None:
            trace.annotate(decision_details={"retrieval_session_rolled_back": True})

    async def _generate_and_persist(
        self,
        turn: _Turn,
        *,
        question: str,
        accepted: list[RetrievalResult],
        partial_coverage: bool,
        knowledge_domain: DocumentDomain,
        budget,
        response_length: ResponseLength,
        response_tone: ResponseTone,
        answer_language: AnswerLanguage,
        response_length_source: str,
        answer_language_source: str,
        knowledge_policy: KnowledgePolicy = KnowledgePolicy.STRICT_INTERNAL,
        policy_source: PolicySource = PolicySource.INTERPRETER,
        related_evidence: Sequence[RetrievalResult] = (),
        original_fallback_reason: str | None = None,
        internal_lookup_failed: bool = False,
        procedure_evidence_complete: bool = False,
        evidence_context_max_tokens: int | None = None,
    ) -> ChatResult:
        """Phase 2's generation tail -- shared by the KNOWLEDGE and REUSE routes. Mirrors the
        legacy `_ask_traced` tail exactly (same claim/citation persistence, same redaction, same
        trace annotations); kept as a separate method rather than a shared refactor of the legacy
        path so that path -- exercised by every existing test -- stays byte-for-byte unchanged
        while the interpreter is being rolled out behind its config flag.

        F5_BOUNDED_GENERAL_KNOWLEDGE_SPEC.md (BGK) [BGK]-tagged parameters below default to
        exactly today's behaviour: `knowledge_policy=STRICT_INTERNAL` produces a byte-identical
        prompt/parse/persist path. `related_evidence` (§10.2) is the ESG-dropped set for an
        INSUFFICIENT-then-guidance turn -- persisted as `Citation` rows with `claim_id=NULL`
        ("shown, not asserted"), the same mechanism `_fallback`'s own `related_evidence` already
        uses, on BOTH the success path here and the failure path below.
        `original_fallback_reason` (§10.3) is the reason that would have applied without BGK --
        substituted back in when generation produces nothing usable at all, so BGK never invents a
        new user-visible fallback reason (§10.4).

        `internal_lookup_failed` (2026-08-27) marks the one case where `accepted` is empty because
        retrieval could not RUN, not because it found nothing: it appends
        `_internal_lookup_failed_note` so the answer states which part could not be verified and
        why. It changes no gate, no policy, and no `fallback_reason` -- if generation yields nothing
        usable, `original_fallback_reason="system_error"` still produces the same terminal
        `system_error` this path produced before.
        """
        generated = _deterministic_test_procedure_generation(question, accepted)
        if generated is None and procedure_evidence_complete:
            generated = _deterministic_procedure_generation(question, accepted)
        if generated is None:
            generation_kwargs = dict(
                history=turn.window.prompt_turns,
                budget=budget,
                response_length=response_length,
                response_tone=response_tone,
                answer_language=answer_language,
                response_length_source=response_length_source,
                answer_language_source=answer_language_source,
                knowledge_policy=knowledge_policy,
            )
            # Production owns context packing; keep older test doubles on their existing port.
            if isinstance(self.answer_generator, AnswerGenerator):
                generation_kwargs["context_max_tokens"] = evidence_context_max_tokens
            generated = await self.answer_generator.generate(question, accepted, **generation_kwargs)
        else:
            trace = current_trace()
            if trace is not None:
                trace.annotate(
                    provider="deterministic",
                    model=generated.model,
                    repair_retry_count=0,
                    decision_details={
                        "generation_strategy": (
                            "source_faithful_test_procedure"
                            if generated.model == "deterministic-test-procedure-v1"
                            else "source_faithful_numbered_procedure"
                        ),
                        "accepted_claim_count": len(generated.claims),
                        "rejected_claim_count": 0,
                    },
                )
        if isinstance(generated, GenerationFailure):
            trace = current_trace()
            if trace is not None and generated.reason == "validator_fail":
                trace.annotate(error_stage="claim_verification", error_code="validator_fail")
            reason = generated.reason
            fallback_related_evidence: Sequence[RetrievalResult] = ()
            fallback_suggestions: Sequence[str] = ()
            if (
                knowledge_policy is KnowledgePolicy.GENERAL_ALLOWED
                and reason == "validator_fail"
                and original_fallback_reason is not None
            ):
                # §10.3: nothing usable survived (both claims and guidance empty) -- fall back to
                # the reason that would have applied without BGK, never a new reason (§10.4).
                if trace is not None:
                    trace.annotate(decision_details={"bgk_guidance_empty": True})
                reason = original_fallback_reason
                if reason == "insufficient_evidence":
                    fallback_related_evidence = related_evidence
                    fallback_suggestions = self._suggestions_from_evidence(related_evidence)
            return await self._fallback(
                turn,
                reason=reason,
                gate="accepted",
                validator="failed",
                retry_count=generated.retry_count,
                knowledge_domain=knowledge_domain,
                related_evidence=fallback_related_evidence,
                suggestions=fallback_suggestions,
            )

        has_claims = bool(generated.claims)
        has_guidance = bool(generated.guidance)
        answer_shape = (
            "guidance_only" if not has_claims else ("mixed" if has_guidance else "internal_only")
        )

        persistence_started = time.monotonic_ns()
        claims_prose, _claims_redacted = _redact_observed(generated.answer)
        guidance_payload: list[dict[str, object]] = []
        guidance_prose_parts: list[str] = []
        for item in generated.guidance:
            text, _guidance_redacted = _redact_observed(item.text)
            guidance_prose_parts.append(text)
            guidance_payload.append({"text": text, "kind": item.kind.value})

        answer_parts: list[str] = []
        if claims_prose:
            answer_parts.append(claims_prose)
        if has_guidance:
            answer_parts.append(_general_guidance_marker(knowledge_domain, answer_language))
            answer_parts.append("\n\n".join(guidance_prose_parts))
        answer = _with_affect_acknowledgement("\n\n".join(answer_parts), turn)
        if partial_coverage:
            note = (
                _partial_coverage_with_guidance_note(
                    knowledge_domain,
                    answer_language
                    if turn.presentation_preferences.language is not None
                    else AnswerLanguage.VI,
                )
                if has_guidance
                else _partial_coverage_note(
                    knowledge_domain,
                    answer_language
                    if turn.presentation_preferences.language is not None
                    else AnswerLanguage.VI,
                )
            )
            answer = f"{answer}\n\n{note}"

        # Dependency-scoped degradation disclosure. Appended AFTER assembly, like the PARTIAL note,
        # and unconditionally when the flag is set -- a turn that answered the company-independent
        # part while the internal corpus was unreachable must say so, or it reads as a complete
        # answer. `partial_coverage` is always False on this path (ESG never ran), so the two notes
        # cannot both appear.
        if internal_lookup_failed:
            answer = (
                f"{answer}\n\n"
                f"{_internal_lookup_failed_note(knowledge_domain, answer_language)}"
            )

        if generated.task_incomplete:
            answer = (
                f"{answer}\n\n"
                f"{_task_incomplete_note(knowledge_domain, answer_language)}"
            )

        conflict, _conflict_redacted = (
            _redact_observed(generated.conflict) if generated.conflict is not None else (None, False)
        )
        if answer_shape == "guidance_only":
            answer_status = "general_guidance"
            grounded = False
        else:
            answer_status = "conflict" if conflict is not None else generated.answer_status
            grounded = True

        evidence_by_chunk_id = {item.chunk.chunk_id: item for item in accepted}
        chunk_redaction_memo: dict[int, tuple[str, bool]] = {}
        citations: list[dict[str, object]] = []
        claims: list[dict[str, object]] = []
        message = self.conversations.append(
            session_id=turn.session_id,
            turn_index=turn.index,
            role=MessageRole.ASSISTANT,
            content=answer,
            trace_id=turn.trace_id,
            grounded=grounded,
            confidence=max(
                (
                    citation.relevance_score
                    for claim in generated.claims
                    for citation in claim.citations
                ),
                default=None,
            ),
            answer_status=answer_status,
            validator_outcome=generated.validator_outcome,
            conflict=conflict,
            general_guidance=guidance_payload,
        )
        await self.session.flush()
        stored_claims: list[tuple[AnswerClaim, VerifiedClaim, bool]] = []
        for claim_index, claim in enumerate(generated.claims):
            claim_text, claim_redacted = _redact_observed(claim.text)
            stored_claim = AnswerClaim(
                message_id=message.message_id,
                claim_index=claim_index,
                text=claim_text,
                support_type=ClaimSupportType(claim.support.value),
                verdict="passed",
                redacted=claim_redacted,
            )
            self.session.add(stored_claim)
            stored_claims.append((stored_claim, claim, claim_redacted))
        await self.session.flush()

        for stored_claim, claim, claim_redacted in stored_claims:
            claim_citations: list[dict[str, object]] = []
            for item in claim.citations:
                evidence = evidence_by_chunk_id[item.chunk_id]
                quote, quote_redacted = _redact_observed(item.quote)
                source_content, content_redacted = _redact_chunk_content(
                    item.chunk_id, evidence.chunk.content, chunk_redaction_memo
                )
                citation_payload = {
                    "chunk_id": item.chunk_id,
                    "quote": quote,
                    "knowledge_domain": item.knowledge_domain.value,
                    "relevance_score": item.relevance_score,
                    "redacted": quote_redacted or content_redacted,
                    "document_id": evidence.document_id,
                    "version_id": evidence.version_id,
                    "source_title": evidence.document_title,
                    "source_url": _citation_source_url(evidence),
                    "section_heading": evidence.chunk.section_path or evidence.chunk.heading,
                    "anchor": evidence.chunk.anchor,
                    "source_content": source_content,
                }
                citations.append(citation_payload)
                claim_citations.append(citation_payload)
                self.session.add(
                    Citation(
                        message_id=message.message_id,
                        claim_id=stored_claim.claim_id,
                        chunk_id=item.chunk_id,
                        quote=quote,
                        relevance_score=item.relevance_score,
                    )
                )
            claims.append(
                {
                    "claim_index": stored_claim.claim_index,
                    "text": stored_claim.text,
                    "support_type": stored_claim.support_type.value,
                    "verdict": stored_claim.verdict,
                    "redacted": claim_redacted,
                    "citations": claim_citations,
                }
            )

        if related_evidence:
            # §10.2: the ESG-dropped evidence set, shown but not asserted -- `claim_id=NULL`,
            # reusing `_fallback`'s own `_related_citation_payload` mechanism rather than
            # duplicating it.
            for item in related_evidence:
                payload = _related_citation_payload(item, chunk_redaction_memo)
                citations.append(payload)
                self.session.add(
                    Citation(
                        message_id=message.message_id,
                        claim_id=None,
                        chunk_id=item.chunk.chunk_id,
                        quote=payload["quote"],
                        relevance_score=payload["relevance_score"],
                    )
                )

        await self.conversations.touch(session_id=turn.session_id)
        await self.session.commit()
        record_duration("persistence.answer", persistence_started)
        trace = current_trace()
        if trace is not None:
            if not trace.has_attribute("prompt_tokens"):
                trace.annotate(prompt_tokens=generated.prompt_tokens)
            if not trace.has_attribute("completion_tokens"):
                trace.annotate(completion_tokens=generated.completion_tokens)
            if not trace.has_attribute("model"):
                trace.annotate(model=generated.model)
            if original_fallback_reason == "no_evidence":
                guidance_evidence_state = "none_retrieved"
            elif original_fallback_reason == "insufficient_evidence":
                guidance_evidence_state = "insufficient_dropped"
            elif accepted:
                guidance_evidence_state = "partial" if partial_coverage else "sufficient"
            else:
                guidance_evidence_state = None
            trace.annotate(
                gate_decision="accepted",
                validator_outcome=generated.validator_outcome,
                repair_retry_count=generated.retry_count,
                decision_details={
                    "knowledge_policy_effective": knowledge_policy.value,
                    "knowledge_policy_source": policy_source.value,
                    "answer_shape": answer_shape,
                    "guidance_evidence_state": guidance_evidence_state,
                    "guidance_item_count": len(generated.guidance),
                    "task_incomplete": generated.task_incomplete,
                },
            )
        return ChatResult(
            answer,
            tuple(citations),
            False,
            None,
            turn.trace_id,
            turn.conversation_id,
            answer_status=answer_status,
            validator_outcome=generated.validator_outcome,
            claims=tuple(claims),
            conflict=conflict,
            general_guidance=tuple(guidance_payload),
            answer_shape=answer_shape,
            task_incomplete=generated.task_incomplete,
        )

    async def _answer_knowledge_route(
        self,
        turn: _Turn,
        *,
        question: str,
        resolved_question: str,
        filters: RetrievalFilters,
        knowledge_domain: DocumentDomain,
        budget,
        response_length: ResponseLength,
        response_tone: ResponseTone,
        answer_language: AnswerLanguage,
        response_length_source: str,
        answer_language_source: str,
        retrieval_query_override: str | None = None,
        knowledge_policy: KnowledgePolicy = KnowledgePolicy.STRICT_INTERNAL,
        policy_source: PolicySource = PolicySource.INTERPRETER,
        general_knowledge_blocked_by_domain: bool = False,
    ) -> ChatResult:
        """Phase 2 KNOWLEDGE route (rev. 2 §3 step 6's `KNOWLEDGE` branch): retrieve ->
        RelevanceGate -> EvidenceSufficiencyGate -> AnswerGenerator -> claim_validation
        (unchanged, inside `_generate_and_persist`/`AnswerGenerator.generate`).

        Also the R4 degrade-to-KNOWLEDGE landing point for an ineligible/empty REUSE attempt --
        `retrieval_query_override` is the previous turn's persisted `retrieval_query` in that
        case (never `resolved_question`, per the flow diagram's explicit "no extra field" note).

        Deliberately scores `RelevanceGate`/`EvidenceSufficiencyGate` against `resolved_question`,
        not the raw `question` the legacy path uses: `resolved_question` is the one thing rev. 2
        §2.2 identifies as missing today -- a single, coherent, context-resolved representation of
        what the turn asks, replacing the three-different-representations problem the legacy path
        still has. `AnswerGenerator` still only ever sees the raw `question` (§4.1: resolved_
        question is retrieval/ESG-subject text ONLY, never prompt instructions).

        `knowledge_policy`/`policy_source` (BGK §4/§6.2) default to `STRICT_INTERNAL`, producing
        byte-identical behaviour to before this spec. When `GENERAL_ALLOWED`, an empty accepted
        set (§10.1) or a genuine `INSUFFICIENT` verdict (§10.2, gated on `allow_after_insufficient`)
        generate a guidance_only answer instead of a terminal fallback -- retrieval and the gates
        themselves are completely unchanged either way.

        `general_knowledge_blocked_by_domain` (F5 audit 2026-08-29, POLICY fallback UX): True only
        when the interpreter's OWN raw verdict was `GENERAL_ALLOWED` and `narrow_policy` forced it
        to `STRICT_INTERNAL` purely because `policy_source is PolicySource.FORCED_DOMAIN` --
        `policy_source` alone can't distinguish that from an ordinary internal POLICY question
        (FORCED_DOMAIN fires for both), so the caller computes this from the pre-narrowing verdict
        and passes it through. Changes ONLY which `FALLBACKS` key a knowledge-gap miss below
        renders (`general_knowledge_not_available` instead of `no_evidence`/`insufficient_
        evidence`) -- never retrieval, the gates, or `narrow_policy`'s STRICT_INTERNAL/FORCED_
        DOMAIN verdict itself, which stays exactly as it was.
        """
        retrieval_text = retrieval_query_override or resolved_question
        # B2 remediation: only a fresh KNOWLEDGE-route resolved_question is eligible for fan-out --
        # `retrieval_query_override` (the R4 REUSE-degrade landing path, using the previous turn's
        # already-persisted query) is left untouched, keeping this change scoped to the one path
        # the audit finding was about.
        entity_queries = (
            _multi_entity_retrieval_queries(retrieval_text)
            if retrieval_query_override is None
            else None
        )
        max_chunks_per_domain, evidence_context_max_tokens = self.gate.evidence_capacity_for(
            resolved_question, has_multi_entity_fanout=bool(entity_queries)
        )
        try:
            if entity_queries:
                candidate_groups = [
                    await self._retrieve(entity_query, filters, budget)
                    for entity_query in entity_queries
                ]
                candidates = _merge_candidate_sets(*candidate_groups)
                trace = current_trace()
                if trace is not None:
                    trace.annotate(
                        decision_details={
                            "multi_entity_fanout_count": len(entity_queries),
                            "multi_entity_fanout_candidate_count": len(candidates),
                        }
                    )
            else:
                candidates = await self._retrieve(retrieval_text, filters, budget)
        except (ExternalServiceFailure, RetrievalUnavailableError) as failure:
            self._annotate_retrieval_layer_failure(failure, budget)
            await self._recover_retrieval_datastore_failure(failure)
            # 2026-08-27, user concern 2 / root cause E: an embedding or vector-store outage used
            # to collapse EVERY capability of the turn -- including the parts that never depended
            # on internal evidence. A dependency failure must only degrade what actually depends on
            # that dependency, so when the interpreter has already judged at least one sub-need
            # company-independent (`GENERAL_ALLOWED`, narrowed by `narrow_policy`), answer that part
            # as explicitly-marked general guidance and DISCLOSE that the project-specific part
            # could not be verified because the lookup did not happen. F5 audit 2026-08-29 (HTTP
            # 500 fix): `RetrievalUnavailableError` -- our own datastore misbehaving -- is the same
            # class of "could not look" dependency failure as an embedding/LLM outage, so it is
            # caught and degraded identically rather than only being handled for the AI-provider
            # case.
            #
            # What this deliberately does NOT do:
            # * it does not weaken grounding -- `accepted=[]` means the generator has no evidence,
            #   so it can only produce guidance items (each carrying `_GENERAL_GUIDANCE_MARKER`);
            #   a company-specific claim still cannot be made, because a claim needs a validated
            #   quote (INV9) and there is nothing to quote;
            # * it does not conflate outage with insufficiency -- the trace still carries the
            #   `embedding_unavailable`/`retrieval_unavailable` error code from
            #   `_annotate_retrieval_layer_failure` above, the disclosure note says "could not
            #   look", not "did not find", and if generation yields nothing usable the reason
            #   substituted back in is `system_error`, never `insufficient_evidence` (invariant 8);
            # * it changes nothing for `STRICT_INTERNAL`, where every sub-need is company-specific:
            #   that keeps the terminal `system_error` fallback, unchanged.
            if knowledge_policy is KnowledgePolicy.GENERAL_ALLOWED:
                trace = current_trace()
                if trace is not None:
                    trace.annotate(decision_details={"retrieval_outage_guidance": True})
                return await self._generate_and_persist(
                    turn,
                    question=question,
                    accepted=[],
                    partial_coverage=False,
                    knowledge_domain=knowledge_domain,
                    budget=budget,
                    response_length=response_length,
                    response_tone=response_tone,
                    answer_language=answer_language,
                    response_length_source=response_length_source,
                    answer_language_source=answer_language_source,
                    knowledge_policy=knowledge_policy,
                    policy_source=policy_source,
                    original_fallback_reason="system_error",
                    internal_lookup_failed=True,
                )
            return await self._fallback(turn, reason="system_error", gate="error")
        accepted = self.gate.accept(
            resolved_question, candidates, max_chunks_per_domain=max_chunks_per_domain
        )
        if not accepted:
            if knowledge_policy is KnowledgePolicy.GENERAL_ALLOWED:
                # §10.1: skip `list_available_topics` -- the model attempts a guidance_only
                # answer directly against the `NO PROJECT EVIDENCE` sentinel. ESG is not called
                # (unchanged: it is only ever called on a non-empty accepted set).
                return await self._generate_and_persist(
                    turn,
                    question=question,
                    accepted=[],
                    partial_coverage=False,
                    knowledge_domain=knowledge_domain,
                    budget=budget,
                    response_length=response_length,
                    response_tone=response_tone,
                    answer_language=answer_language,
                    response_length_source=response_length_source,
                    answer_language_source=answer_language_source,
                    knowledge_policy=knowledge_policy,
                    policy_source=policy_source,
                    original_fallback_reason="no_evidence",
                )
            suggestions = await self.retrieval_engine.list_available_topics(filters)
            return await self._fallback(
                turn,
                reason=(
                    "general_knowledge_not_available"
                    if general_knowledge_blocked_by_domain
                    else "no_evidence"
                ),
                gate="rejected",
                knowledge_domain=knowledge_domain,
                suggestions=suggestions,
            )

        ranked_chunk_ids = tuple(item.chunk.chunk_id for item in accepted)
        accepted = await self._expand_procedure_evidence(
            resolved_question, accepted, filters=filters
        )
        procedure_structure_completed = tuple(
            item.chunk.chunk_id for item in accepted
        ) != ranked_chunk_ids
        targeted_test_procedure_available = (
            _deterministic_test_procedure_generation(question, accepted) is not None
        )

        # §7.4 item 2 / R4: every KNOWLEDGE turn persists the query that actually produced its
        # answer, not only after a Tier-2 rewrite -- a prerequisite for the next turn's reuse
        # degradation to have something real to fall back to.
        await self.conversations.set_retrieval_query(
            session_id=turn.session_id, turn_index=turn.index, query=retrieval_text
        )
        await self.session.commit()

        partial_coverage = False
        if (
            self.evidence_sufficiency_gate is not None
            and not procedure_structure_completed
            and not targeted_test_procedure_available
        ):
            with telemetry_span("evidence_sufficiency_gate"):
                if isinstance(self.evidence_sufficiency_gate, EvidenceSufficiencyGate):
                    sufficiency = await self.evidence_sufficiency_gate.check(
                        resolved_question,
                        accepted,
                        budget,
                        max_evidence_tokens=evidence_context_max_tokens,
                    )
                else:
                    sufficiency = await self.evidence_sufficiency_gate.check(
                        resolved_question, accepted, budget
                    )
            trace = current_trace()
            if trace is not None:
                trace.annotate(
                    decision_details={
                        "evidence_sufficiency_gate_verdict": sufficiency.verdict.value,
                        "evidence_source": "fresh",
                    }
                )
            if sufficiency.verdict is EvidenceSufficiencyVerdict.AMBIGUOUS:
                return await self._fallback(
                    turn,
                    reason="ambiguous_question",
                    gate="ambiguous_question",
                    knowledge_domain=knowledge_domain,
                    suggestions=self._suggestions_from_evidence(accepted),
                )
            if not sufficiency.sufficient:
                errored = sufficiency.errored
                if (
                    not errored
                    and knowledge_policy is KnowledgePolicy.GENERAL_ALLOWED
                    and self.general_knowledge_config.allow_after_insufficient
                ):
                    # §10.2: the accepted evidence is DROPPED from generation (structurally
                    # guidance-only), but still persisted as shown-not-asserted citations. An
                    # `errored` (fail-closed, infra fault) verdict is never rescued by BGK -- ESG's
                    # fail-closed contract is unchanged.
                    return await self._generate_and_persist(
                        turn,
                        question=question,
                        accepted=[],
                        partial_coverage=False,
                        knowledge_domain=knowledge_domain,
                        budget=budget,
                        response_length=response_length,
                        response_tone=response_tone,
                        answer_language=answer_language,
                        response_length_source=response_length_source,
                        answer_language_source=answer_language_source,
                        knowledge_policy=knowledge_policy,
                        policy_source=policy_source,
                        related_evidence=accepted,
                        original_fallback_reason="insufficient_evidence",
                    )
                insufficient_reason = (
                    "general_knowledge_not_available"
                    if general_knowledge_blocked_by_domain
                    else "insufficient_evidence"
                )
                return await self._fallback(
                    turn,
                    reason="system_error" if errored else insufficient_reason,
                    gate="error" if errored else "insufficient_evidence",
                    knowledge_domain=knowledge_domain,
                    related_evidence=() if errored else accepted,
                    suggestions=() if errored else self._suggestions_from_evidence(accepted),
                )
            partial_coverage = sufficiency.verdict is EvidenceSufficiencyVerdict.PARTIAL
        elif procedure_structure_completed or targeted_test_procedure_available:
            trace = current_trace()
            if trace is not None:
                trace.annotate(
                    decision_details={
                        "evidence_sufficiency_gate_skipped": (
                            "targeted_test_procedure"
                            if targeted_test_procedure_available
                            else "complete_numbered_procedure"
                        ),
                        "evidence_source": "fresh",
                    }
                )

        # §12.1: PARTIAL + GENERAL_ALLOWED is gated on `allow_on_partial` -- when off, this turn's
        # generation call is forced STRICT_INTERNAL (claims only, v2 prompt), even though the
        # interpreter proposed GENERAL_ALLOWED. SUFFICIENT is never gated this way.
        generation_policy = knowledge_policy
        if (
            partial_coverage
            and knowledge_policy is KnowledgePolicy.GENERAL_ALLOWED
            and not self.general_knowledge_config.allow_on_partial
        ):
            generation_policy = KnowledgePolicy.STRICT_INTERNAL

        return await self._generate_and_persist(
            turn,
            question=question,
            accepted=accepted,
            partial_coverage=partial_coverage,
            knowledge_domain=knowledge_domain,
            budget=budget,
            response_length=response_length,
            response_tone=response_tone,
            answer_language=answer_language,
            response_length_source=response_length_source,
            answer_language_source=answer_language_source,
            knowledge_policy=generation_policy,
            policy_source=policy_source,
            original_fallback_reason="validator_fail",
            procedure_evidence_complete=procedure_structure_completed,
            evidence_context_max_tokens=evidence_context_max_tokens,
        )

    async def _answer_reuse_route(
        self,
        turn: _Turn,
        *,
        question: str,
        resolved_question: str,
        filters: RetrievalFilters,
        knowledge_domain: DocumentDomain,
        budget,
        response_length: ResponseLength,
        response_tone: ResponseTone,
        answer_language: AnswerLanguage,
        response_length_source: str,
        answer_language_source: str,
        knowledge_policy: KnowledgePolicy = KnowledgePolicy.STRICT_INTERNAL,
        policy_source: PolicySource = PolicySource.INTERPRETER,
    ) -> ChatResult | None:
        """Rev. 2 §6, R1/R4/R5/R6. Returns a terminal `ChatResult`, or `None` to signal R4's
        "degrade to KNOWLEDGE using the previous turn's persisted retrieval_query" -- the caller
        (`_ask_with_interpreter`) then falls through to `_answer_knowledge_route`.

        `knowledge_policy` (BGK §12.2) is always `STRICT_INTERNAL` in practice on this route --
        `general_guidance_policy.narrow_policy` forces it via `FORCED_ROUTE` before this method is
        ever called, since REUSE means "re-present an already-given answer", never "introduce new
        generic content". Threaded through only so `_generate_and_persist`'s telemetry reports the
        real `policy_source`, and so this call site never drifts from `_answer_knowledge_route`'s.
        """
        trace = current_trace()
        attempt = await self._find_reusable_evidence(turn, filters=filters)
        if attempt is None or not attempt.reloaded:
            if trace is not None:
                trace.annotate(
                    decision_details={
                        "reuse_unavailable": attempt is None,
                        "reuse_stale": attempt is not None and not attempt.reloaded,
                    }
                )
            return None
        if trace is not None and 0 < len(attempt.reloaded) < attempt.original_count:
            trace.annotate(
                decision_details={
                    "reuse_partial": True,
                    "reuse_original_count": attempt.original_count,
                    "reuse_reloaded_count": len(attempt.reloaded),
                }
            )

        if self.evidence_sufficiency_gate is None:
            # R1 cannot be proved without the gate -- degrade rather than generate unvalidated.
            return None

        # R1/R5: judged against `resolved_question`, never `previous_turn.question` (§4.4).
        with telemetry_span("evidence_sufficiency_gate"):
            sufficiency = await self.evidence_sufficiency_gate.check(
                resolved_question, attempt.reloaded, budget
            )
        if trace is not None:
            trace.annotate(
                decision_details={
                    "evidence_sufficiency_gate_verdict": sufficiency.verdict.value,
                    "evidence_source": "reused",
                }
            )

        if sufficiency.verdict is EvidenceSufficiencyVerdict.AMBIGUOUS:
            return await self._fallback(
                turn,
                reason="ambiguous_question",
                gate="ambiguous_question",
                knowledge_domain=knowledge_domain,
                suggestions=self._suggestions_from_evidence(attempt.reloaded),
            )

        if sufficiency.sufficient:
            partial_coverage = sufficiency.verdict is EvidenceSufficiencyVerdict.PARTIAL
            # Persist the server-resolved subject as this reuse turn's retrieval anchor.
            await self.conversations.set_retrieval_query(
                session_id=turn.session_id, turn_index=turn.index, query=resolved_question
            )
            await self.session.commit()
            return await self._generate_and_persist(
                turn,
                question=question,
                accepted=attempt.reloaded,
                partial_coverage=partial_coverage,
                knowledge_domain=knowledge_domain,
                budget=budget,
                response_length=response_length,
                response_tone=response_tone,
                answer_language=answer_language,
                response_length_source=response_length_source,
                answer_language_source=answer_language_source,
                knowledge_policy=knowledge_policy,
                policy_source=policy_source,
            )

        if sufficiency.errored:
            # A judge fault is not a coverage signal -- no recovery, ESG's fail-closed contract.
            return await self._fallback(turn, reason="system_error", gate="error")

        # R5: genuine INSUFFICIENT (errored=False) -> exactly one bounded, budget-gated recovery.
        if not self._budget_allows_recovery(budget):
            return await self._fallback(
                turn,
                reason="insufficient_evidence",
                gate="insufficient_evidence",
                knowledge_domain=knowledge_domain,
                related_evidence=attempt.reloaded,
                suggestions=self._suggestions_from_evidence(attempt.reloaded),
            )
        try:
            fresh_candidates = await self._retrieve(resolved_question, filters, budget)
        except (ExternalServiceFailure, RetrievalUnavailableError) as failure:
            self._annotate_retrieval_layer_failure(failure, budget)
            await self._recover_retrieval_datastore_failure(failure)
            return await self._fallback(turn, reason="system_error", gate="error")
        fresh_accepted = self.gate.accept(resolved_question, fresh_candidates)
        if not fresh_accepted:
            suggestions = await self.retrieval_engine.list_available_topics(filters)
            return await self._fallback(
                turn,
                reason="no_evidence",
                gate="rejected",
                knowledge_domain=knowledge_domain,
                suggestions=suggestions,
            )
        fresh_ranked_chunk_ids = tuple(item.chunk.chunk_id for item in fresh_accepted)
        fresh_accepted = await self._expand_procedure_evidence(
            resolved_question, fresh_accepted, filters=filters
        )
        fresh_procedure_structure_completed = tuple(
            item.chunk.chunk_id for item in fresh_accepted
        ) != fresh_ranked_chunk_ids
        fresh_targeted_test_procedure_available = (
            _deterministic_test_procedure_generation(question, fresh_accepted) is not None
        )
        if fresh_procedure_structure_completed or fresh_targeted_test_procedure_available:
            sufficiency2 = EvidenceSufficiencyResult(
                verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False
            )
        else:
            with telemetry_span("evidence_sufficiency_gate", attempt=2):
                sufficiency2 = await self.evidence_sufficiency_gate.check(
                    resolved_question, fresh_accepted, budget
                )
        if trace is not None:
            trace.annotate(
                decision_details={
                    "reuse_insufficient_recovered": True,
                    **(
                        {
                            "evidence_sufficiency_gate_skipped": (
                                "targeted_test_procedure"
                                if fresh_targeted_test_procedure_available
                                else "complete_numbered_procedure"
                            )
                        }
                        if (
                            fresh_procedure_structure_completed
                            or fresh_targeted_test_procedure_available
                        )
                        else {"evidence_sufficiency_gate_verdict": sufficiency2.verdict.value}
                    ),
                    "evidence_source": "reused_then_fresh",
                }
            )
        if sufficiency2.verdict is EvidenceSufficiencyVerdict.AMBIGUOUS:
            return await self._fallback(
                turn,
                reason="ambiguous_question",
                gate="ambiguous_question",
                knowledge_domain=knowledge_domain,
                suggestions=self._suggestions_from_evidence(fresh_accepted),
            )
        if not sufficiency2.sufficient:
            # Second INSUFFICIENT (or a judge fault) is terminal -- no further recovery.
            errored = sufficiency2.errored
            return await self._fallback(
                turn,
                reason="system_error" if errored else "insufficient_evidence",
                gate="error" if errored else "insufficient_evidence",
                knowledge_domain=knowledge_domain,
                related_evidence=() if errored else fresh_accepted,
                suggestions=() if errored else self._suggestions_from_evidence(fresh_accepted),
            )
        partial_coverage = sufficiency2.verdict is EvidenceSufficiencyVerdict.PARTIAL
        # Fresh retrieval also establishes this turn's resolved anchor.
        await self.conversations.set_retrieval_query(
            session_id=turn.session_id, turn_index=turn.index, query=resolved_question
        )
        await self.session.commit()
        return await self._generate_and_persist(
            turn,
            question=question,
            accepted=fresh_accepted,
            partial_coverage=partial_coverage,
            knowledge_domain=knowledge_domain,
            budget=budget,
            response_length=response_length,
            response_tone=response_tone,
            answer_language=answer_language,
            response_length_source=response_length_source,
            answer_language_source=answer_language_source,
            knowledge_policy=knowledge_policy,
            policy_source=policy_source,
        )

    # These outcomes do not establish a trustworthy topic.
    _TOPIC_STATE_SKIP_REASONS = frozenset({"out_of_scope", "system_error", "ambiguous_question"})

    async def _update_topic_state(
        self, turn: _Turn, *, resolved_question: str, result: ChatResult
    ) -> None:
        """Maintain trusted topic memory from what the answer actually GROUNDED, not from the
        question text or the documents it happened to come from.

        F5 audit 2026-08-30 (TopicState remediation, confirmed via live trace): the previous
        version set `subject` to the resolved_question (an interrogative -- "Các thành phần của
        Thanos là gì?", never a description of what was found) and `entities` to cited
        `source_title`s (document filenames -- "test_upload/component.md", never the component
        names a listing answer actually named). `turn_interpreter.py`'s own resolved_question
        worked example assumes `active_topic_state.subject` can read like "Các thành phần chính
        của dự án Thanos (Sidecar, Store Gateway, Compactor, ...)" -- an enumeration of the
        answer's content -- which the old fields could never produce, and a live trace confirmed
        the interpreter substituting the wrong "entities" (document titles) into a deepening
        follow-up's resolved_question, corrupting retrieval for it.

        Fix reuses data already computed for THIS turn's citation/claim persistence -- no new LLM
        call, no new retrieval:
        * `subject` is the turn's own GROUNDED claim text (`result.claims[*]["text"]`, already
          citation-verified before this point) -- what the answer actually stated, not what was
          asked. Falls back to `resolved_question` only when there is no claim to draw from AND
          no prior topic exists (the very first turn of a conversation starting on a
          guidance_only/BGK answer, which asserts nothing internal to name as a subject).
        * `entities` are the cited chunks' own SECTION HEADINGS (`citation["section_heading"]`,
          already built by `_generate_and_persist`'s citation payload from
          `chunk.section_path or chunk.heading` for display) rather than document titles -- a
          heading like "Sidecar" or "Store Gateway" is the actual component name a listing answer
          cites section-by-section; a document filename like "component.md" never is.
        Both stay bounded exactly as before (`topic_subject_max_chars`/`topic_entities_max`).

        CNV-008 (2026-08-30): a non-fallback, zero-claim turn (a `GENERAL_ALLOWED` guidance-only
        tangent, e.g. "Kafka vs RabbitMQ nói chung" asked mid-conversation about a project) used to
        fall through to `resolved_question` unconditionally, silently overwriting an already
        established project topic ("Sidecar") with the tangent's own question text -- confirmed via
        live replay to erase the topic a later "quay lại Sidecar..." follow-up needed. Such a turn
        grounds nothing, so it must leave existing topic memory alone instead of replacing it.
        """
        if result.fallback and result.fallback_reason in self._TOPIC_STATE_SKIP_REASONS:
            return
        subject = truncate(resolved_question, self.memory.topic_subject_max_chars)
        entities: tuple[str, ...] = ()
        if not result.fallback:
            claim_texts = [str(claim["text"]) for claim in result.claims if claim.get("text")]
            if claim_texts:
                subject = truncate(" ".join(claim_texts), self.memory.topic_subject_max_chars)
                headings: list[str] = []
                for citation in result.citations:
                    heading = citation.get("section_heading")
                    if heading and heading not in headings:
                        headings.append(str(heading))
                    if len(headings) >= self.memory.topic_entities_max:
                        break
                entities = tuple(headings)
            elif not turn.topic_state.is_empty:
                # Guidance-only/zero-claim tangent with an established topic already in play:
                # nothing grounded to replace it with, so keep it rather than overwrite it with
                # the tangent's own resolved_question.
                subject = turn.topic_state.subject
                entities = turn.topic_state.entities
            # else: no claim and no prior topic (first turn) -- fall through to resolved_question.
        else:
            subject = turn.topic_state.subject or subject
            entities = turn.topic_state.entities
        if subject == turn.topic_state.subject and entities == turn.topic_state.entities:
            return
        await self.conversations.update_topic_state(
            session_id=turn.session_id,
            subject=subject,
            entities=encode_topic_entities(entities),
        )
        await self.session.commit()

    async def _ask_with_interpreter(
        self,
        *,
        question: str,
        user_id: int,
        knowledge_domain: DocumentDomain,
        membership: ProjectMembership | None,
        filters: RetrievalFilters,
        project_name: str | None,
        conversation_id: uuid.UUID | None,
        trace_id: str,
        budget,
        response_length: ResponseLength,
        response_tone: ResponseTone,
    ) -> ChatResult:
        """Phase 2: the interpreter is authoritative for `route`/`resolved_question`/
        `presentation`. `ScopeGate` still runs as its own call (rev. 2 §7.1's Phase 2 shape --
        merging it into the interpreter is Phase 3, gated on the guardrail fixture).

        Ordering changed 2026-08-25 (B-01): the gate now runs on the RAW utterance BEFORE the
        interpreter, for every route rather than only KNOWLEDGE/REUSE. The previous
        "skipped for every route that doesn't need it" shape assumed the route label was
        trustworthy input to a security decision; it is the interpreter's output, so it is not.
        See `_pre_route_scope_check`.
        """
        turn = await self._begin_interpreted_turn(
            question=question,
            user_id=user_id,
            knowledge_domain=knowledge_domain,
            membership=membership,
            conversation_id=conversation_id,
            trace_id=trace_id,
        )

        # Rev. 2 §3 step 3: the ONE surviving regex, checked before the interpreter is ever
        # called -- a whole-utterance-anchored template match costs 0 LLM calls, exactly as today.
        if classify_social(question) is not None:
            return await self._answer_social_mode(
                turn, question=question, budget=budget, response_tone=response_tone
            )

        # B-01: guardrail first, for every remaining route. See `_pre_route_scope_check` for why
        # this moved ahead of the interpreter.
        #
        # The text handed over is the RAW utterance, Tier 0/1-condensed against the conversation's
        # anchors. `condense` only ever PREPENDS topic anchors and always keeps the question
        # verbatim (query_condenser.py's module contract), so this adds topical signal without
        # removing a single character of what the user actually typed -- the imperative the old
        # `resolved_question` path deleted survives intact. Without the condensation a contentless
        # follow-up ("Bạn hãy trả lời giúp tôi") would reach the gate as a standalone fragment and
        # risk the false reject seen live on 2026-08-24 (session_id=768); the previous code
        # applied that same repair, but only on the interpreter-errored path.
        # F5 audit 2026-08-30 root cause #2: scope classification uses its OWN, narrower anchor
        # list -- `informational_anchor_questions` (unlike `turn.window.anchor_questions`) drops a
        # turn with no persisted `retrieval_query` (a SOCIAL ack, CONVERSATION, or CATALOG reply),
        # so a bare presentation-control instruction never gets glued onto the next, unrelated
        # standalone question before `ScopeGate` ever sees it. See that function's own docstring.
        scope_text = condense(
            question,
            informational_anchor_questions(turn.raw_history, self.memory),
            self.memory,
            topic_anchor=turn.topic_state.subject,
        ).retrieval_query

        # Built BEFORE the concurrent block below, deliberately: this reads history and evidence
        # titles through the request's single `AsyncSession`, which must never be used from two
        # coroutines at once. Only the two LLM calls are made concurrent.
        context = await self._interpreter_context(
            turn,
            question=question,
            knowledge_domain=knowledge_domain,
            project_name=project_name,
            filters=filters,
        )

        # 2026-08-26: the guardrail and the interpreter run CONCURRENTLY. `_pre_route_scope_check`
        # already anticipated this in its own docstring -- since B-01 it judges the raw utterance
        # and no longer consumes anything the interpreter produces, so the only thing that ever
        # forced these to be sequential was that they used to be data-dependent.
        #
        # THE SECURITY PROPERTY IS UNCHANGED, and this is the line that matters: what B-01
        # requires is that the gate decides before any route is ACTED ON -- not that the
        # interpreter is prevented from THINKING. The `if not in_scope` below is still the first
        # thing that happens after the block, still before every branch, so an OUT_OF_SCOPE turn
        # still reaches no route, no retrieval and no generation. A rejected turn now pays for an
        # interpreter verdict that is computed and then discarded; that is the entire cost.
        #
        # `budget.concurrent` is not incidental bookkeeping -- without it these two calls would
        # charge the sum of their own elapsed times against the LLM budget instead of the block's
        # wall time, and the stage that ran next would be starved of the difference. That is
        # exactly the failure shape of trace 72e4e5ed, and parallelising without it would have
        # bought latency with a fresh correctness bug.
        #
        # `return_exceptions=True` although both collaborators document that they never raise:
        # inside `gather` an escaping exception leaves the sibling call running unobserved, so the
        # contract is re-asserted here rather than trusted. Each degrades to the SAME value its
        # own documented failure path already uses -- the gate fails OPEN (`scope_gate.py`: "this
        # gate only ever skips work, never blocks it on its own failure"), the interpreter to an
        # `errored` verdict (rev. 2 §8's timeout row) -- so a fault degrades identically whether
        # it was caught inside the collaborator or here.
        with telemetry_span("scope_and_interpret"), budget.concurrent("llm"):
            scope_result, interpreter_result = await asyncio.gather(
                self._pre_route_scope_check(
                    scope_text,
                    project_name=project_name,
                    knowledge_domain=knowledge_domain,
                    budget=budget,
                    has_prior_turn=turn.index > 0,
                ),
                self.turn_interpreter.interpret(context, budget),
                return_exceptions=True,
            )
        in_scope = True if isinstance(scope_result, BaseException) else scope_result
        verdict = (
            InterpreterVerdict(
                scope=InterpreterScope.IN_SCOPE,
                route=InterpreterRoute.KNOWLEDGE,
                resolved_question=question,
                presentation=PresentationOverlay(),
                errored=True,
            )
            if isinstance(interpreter_result, BaseException)
            else interpreter_result
        )

        # Concern 4: recorded on the turn BEFORE any terminal branch can be taken, so every exit --
        # fallback, generated answer, social template -- sees the same value. See
        # `_Turn.interpretation_degraded` for why this is the whole behaviour change.
        turn.interpretation_degraded = verdict.errored or verdict.malformed

        # RC-5 (2026-08-27, telemetry consistency): ONE definition of "the knowledge-policy decision
        # was degraded", computed here and used by BOTH the trace annotation below and
        # `narrow_policy` further down. It used to be annotated from `verdict.knowledge_policy_
        # degraded` alone (an interpreter-internal flag: "the model's knowledge_policy field was
        # unusable") while `narrow_policy` received the wider condition -- so trace1984 turn 1 logged
        # the self-contradicting pair `knowledge_policy_source="degraded"` +
        # `knowledge_policy_degraded=false`, which is unreadable for anyone auditing why a turn lost
        # BGK. The narrower interpreter-internal signal is not lost: it is annotated separately as
        # `interpreter_knowledge_policy_malformed`.
        policy_degraded = (
            verdict.malformed
            or verdict.errored
            or verdict.sanitized
            or verdict.knowledge_policy_degraded
        )

        # A pure, explicit language command is a control-plane state transition, not a corpus
        # question. This deterministic extraction is a SAFETY NET for when the interpreter's own
        # verdict fails to surface a usable presentation control at all (a stochastic miss) --
        # it fills the gap in `language`/`apply_now`/`persist_future`, it does not re-decide
        # anything the interpreter already reasoned about.
        #
        # 2026-08-30 fix: this used to fire unconditionally and also force `route=SOCIAL`, which
        # made it a second router rather than a presentation-control correction. Two concrete
        # breakages traced to that: (1) it clobbered an ALREADY-CORRECT interpreter verdict --
        # `test_language_reanswer_reuses_grounded_evidence_and_keeps_the_preference`'s interpreter
        # already returns `application=BOTH`, but this code recomputed a cruder
        # `PREVIOUS_RESPONSE` from regex markers alone and overwrote it, so the language
        # preference was never persisted; (2) forcing `route=SOCIAL` overrode a real KNOWLEDGE/
        # REUSE verdict, which is exactly what `test_scope_rejection_still_ends_a_knowledge_turn_
        # even_when_it_carried_a_control` exists to catch, and matches the live CNV-001 route
        # mismatch (interpreter correctly said REUSE; this code overwrote it with SOCIAL).
        # `route` is deliberately never touched here: `pure_presentation_control` (below) already
        # dispatches the zero-retrieval ack path from `control_application` alone, independent of
        # route, and `wants_previous_reanswer` (below) already promotes the LOCAL `route` to
        # REUSE when a re-answer is wanted -- both existing mechanisms make a route override here
        # both redundant and unsafe. Route/resolved-subject stay the interpreter's decision.
        explicit_language = _explicit_language_control(question)
        interpreter_control_is_healthy = verdict.conversation_control.updates_presentation and not (
            verdict.errored or verdict.malformed or verdict.sanitized
        )
        if explicit_language is not None and not interpreter_control_is_healthy:
            target_language, apply_now, persist_future = explicit_language
            application = (
                ConversationControlApplication.BOTH
                if apply_now and persist_future
                else ConversationControlApplication.PREVIOUS_RESPONSE
                if apply_now
                else ConversationControlApplication.FUTURE_TURNS
            )
            verdict = replace(
                verdict,
                presentation=PresentationOverlay(language=target_language),
                conversation_control=ConversationControl(
                    kind=ConversationControlKind.UPDATE_PRESENTATION,
                    presentation=PresentationOverlay(language=target_language),
                    application=application,
                ),
                social_intent=SocialIntent.LANGUAGE_PREFERENCE,
                apply_now=apply_now,
                persist_future=persist_future,
            )

        # Backward-compatible semantic bridge for pre-v10/scripted verdicts: the old closed
        # LANGUAGE_PREFERENCE intent was already an explicit control signal, unlike a bare
        # `presentation.language`. New verdicts carry the generalized discriminator directly.
        control = verdict.conversation_control
        if (
            not control.updates_presentation
            and verdict.route is InterpreterRoute.SOCIAL
            and verdict.social_intent is SocialIntent.LANGUAGE_PREFERENCE
            and verdict.presentation.language is not None
        ):
            control = ConversationControl(
                kind=ConversationControlKind.UPDATE_PRESENTATION,
                presentation=PresentationOverlay(language=verdict.presentation.language),
            )
        # F5 audit 2026-08-29, failure 1: which turn(s) this control governs is read directly from
        # `control.application` (populated by the model via `apply_now`/`persist_future`, v15)
        # instead of inferred from `verdict.route` -- `route` alone was not a robust signal here (a
        # pure FUTURE_TURNS-only control can legitimately come back with `route=REUSE` when the
        # model has no separate subject to name).
        # 2026-08-29 remediation (audit finding #1): re-rendering the previous answer is now
        # strictly OPT-IN. A missing/partial signal (`None` -- a pre-v15 payload/fixture, or a v15
        # verdict where neither `apply_now` nor `persist_future` parsed as an explicit boolean)
        # used to bridge through `route`, and defaulted a `REUSE` verdict to `BOTH` -- silently
        # re-rendering the previous answer even though nothing confirmed the user asked for that.
        # It now always defaults to FUTURE_TURNS-only: the control is still acknowledged and
        # persisted, but a re-render only ever happens when the model explicitly said `apply_now`.
        has_presentation_control = control.updates_presentation
        control_application = control.application
        if has_presentation_control and control_application is None:
            control_application = ConversationControlApplication.FUTURE_TURNS
        wants_previous_reanswer = (
            has_presentation_control
            and control_application
            in (
                ConversationControlApplication.PREVIOUS_RESPONSE,
                ConversationControlApplication.BOTH,
            )
            # Case A/C require a REAL previous turn to re-render. On turn 0 there is none, so this
            # degrades to a pure control ack below -- there is nothing to reanswer either way.
            and turn.index > 0
        )
        persists_presentation = has_presentation_control and control_application in (
            ConversationControlApplication.FUTURE_TURNS,
            ConversationControlApplication.BOTH,
        )
        # Ack-only, zero-retrieval terminal branch: every control that does NOT need the previous
        # answer re-rendered, whether because it never asked to (FUTURE_TURNS) or because there is
        # nothing to re-render (PREVIOUS_RESPONSE/BOTH on turn 0).
        pure_presentation_control = has_presentation_control and not wants_previous_reanswer

        # An explicit, healthy UPDATE_PRESENTATION verdict is trusted conversation state, not
        # corpus access. Persist it before the topical gate can terminate the turn: this lets a
        # user say "reply in Vietnamese" alongside an off-topic/unsafe request without allowing
        # that request to reach retrieval. The gate still controls every knowledge-bearing route.
        # Gated on `persists_presentation`, not the bare control, so a PREVIOUS_RESPONSE-only
        # control (case A: re-answer this once, no standing change) never writes a durable
        # preference -- `turn.presentation_preferences`/`control_language` below still apply it
        # to THIS turn's rendering regardless of whether it is persisted.
        if not verdict.errored and not verdict.malformed and persists_presentation:
            await self.conversations.update_presentation_preferences(
                session_id=turn.session_id,
                language=control.presentation.language,
                detail=control.presentation.detail,
            )
            turn.presentation_preferences = turn.presentation_preferences.apply(control)

        # A positive semantic control verdict is a narrow recovery from a ScopeGate false reject:
        # it can only authorize the control-plane SOCIAL branch, never KNOWLEDGE/retrieval. Mixed
        # or unsafe turns still require the gate exactly as before.
        #
        # Deliberately NOT `pure_presentation_control` (which, since the application-based
        # dispatch above, can also be true for a non-SOCIAL route, e.g. a REUSE verdict demoted
        # to KNOWLEDGE by the echo-guard with application=FUTURE_TURNS): a control attached to a
        # route the scope gate actually rejected must never smuggle that route's own content past
        # the gate merely by also carrying a presentation update -- see
        # `test_scope_rejection_still_ends_a_knowledge_turn_even_when_it_carried_a_control`. The
        # control itself still gets persisted above regardless of `in_scope`; only the BYPASS is
        # restricted to the one route (SOCIAL) that never reaches retrieval either way.
        control_is_bare_ack = verdict.route is InterpreterRoute.SOCIAL and control.updates_presentation
        #
        # 2026-08-27, second recovery, same shape and same reasoning: `_pre_route_scope_check`
        # judges the raw utterance with NO conversation context (B-01), so it cannot tell a
        # question about the company from a question about THIS DIALOGUE -- "sao lại không có
        # nguồn?" carries no project subject and gets rejected as off-topic. The context-aware
        # interpreter can tell, and CONVERSATION is the one informational route that consults no
        # corpus: no retrieval call, no chunk access, no citations minted, transcript-only, already
        # ACL-scoped to this user by `load_full_history`'s ownership predicate. So a topical
        # rejection of a turn the interpreter independently reads as CONVERSATION withholds
        # nothing the user has not already received, while rejecting it makes the assistant unable
        # to discuss its own answers. KNOWLEDGE/REUSE/CATALOG -- every route that can surface
        # corpus content -- stay gated exactly as before.
        conversation_recovery = (
            verdict.route is InterpreterRoute.CONVERSATION
            and verdict.scope is InterpreterScope.IN_SCOPE
            and not verdict.errored
            and not verdict.malformed
            and turn.index > 0
        )
        # 2026-08-27, third recovery (RC-3, authorised decision): `_pre_route_scope_check` judges
        # TOPIC only -- "is this about this company/project?" -- and it is right to reject a question
        # about installing Prometheus on Windows on that question. But the interpreter, judging the
        # same utterance with conversation context, independently answers a DIFFERENT question:
        # "does answering this need internal evidence at all?" On trace1984 turn 4 those two verdicts
        # were OUT_OF_SCOPE and GENERAL_ALLOWED, and the topical one won before the policy could ever
        # be applied -- so a turn the system had already decided was answerable from general
        # technical knowledge was refused. That combination occurs in 44 logged turns.
        #
        # A turn recovered here gets NO corpus access: it is dispatched straight into
        # `_generate_and_persist` with `accepted=[]` (below, after `narrow_policy`), so retrieval is
        # never called, no chunk is read, and no `Claim`/`Citation` can be minted -- a claim requires
        # a validated quote (INV9) and there is nothing to quote. The reply is guidance_only, carrying
        # `_general_guidance_marker`'s explicit non-internal provenance, and if the generator produces
        # nothing usable the user sees the unchanged `out_of_scope` refusal (§10.3/§10.4: no new
        # user-visible reason). ACL is untouched -- nothing is read that ACL would scope.
        #
        # Restricted to `route is KNOWLEDGE` deliberately: CATALOG and REUSE both surface corpus
        # content, and CONVERSATION has its own recovery above. Restricted to a healthy verdict for
        # the same reason both recoveries above are -- a degraded verdict is not a judgement.
        off_topic_guidance = (
            verdict.route is InterpreterRoute.KNOWLEDGE
            and verdict.scope is InterpreterScope.IN_SCOPE
            and not verdict.errored
            and not verdict.malformed
            and verdict.knowledge_policy is KnowledgePolicy.GENERAL_ALLOWED
        )
        if not in_scope and (
            control_is_bare_ack or conversation_recovery or off_topic_guidance
        ):
            trace = current_trace()
            if trace is not None:
                trace.annotate(
                    decision_details={
                        "scope_recovered_by": (
                            "presentation_control"
                            if control_is_bare_ack
                            else "conversation"
                            if conversation_recovery
                            else "general_knowledge"
                        )
                    }
                )
        elif not in_scope:
            return await self._fallback(turn, reason="out_of_scope", gate="scope_rejected")
        else:
            # Only a turn the topical gate REJECTED is recovered into guidance_only. An in-scope
            # turn keeps the full pipeline (retrieval, gates, citations) exactly as before.
            off_topic_guidance = False
        trace = current_trace()
        if trace is not None:
            trace.annotate(
                decision_details={
                    "interpreter_route": verdict.route.value,
                    "interpreter_scope": verdict.scope.value,
                    "interpreter_malformed": verdict.malformed,
                    "interpreter_error": verdict.errored,
                    "interpreter_sanitized": verdict.sanitized,
                    # Logged for EVERY route, deliberately: the eval question this field has to
                    # answer is "how often is affect detected on a turn that stays KNOWLEDGE?",
                    # which a SOCIAL-only annotation could not answer at all.
                    "interpreter_affect": verdict.affect.value,
                    "scope_check_skipped": verdict.errored,
                    "knowledge_policy": verdict.knowledge_policy.value,
                    "knowledge_policy_degraded": policy_degraded,
                    # RC-5: the narrow interpreter-internal signal, kept as its own field so
                    # "the model's knowledge_policy field was unusable" and "this turn's policy
                    # decision was degraded for any reason" are separately answerable.
                    "interpreter_knowledge_policy_malformed": verdict.knowledge_policy_degraded,
                }
            )

        # A degraded interpretation stops HERE, before any route is
        # acted on. The interpreter's local error representation remains IN_SCOPE / KNOWLEDGE /
        # resolved_question=raw so it never raises, but that shape is diagnostic only. Previously it
        # was indistinguishable from a real verdict downstream, so a timeout converted whatever the
        # user said into a knowledge query. On trace1984 turn 1 that turned "từ giờ hãy trả lời tôi
        # bằng tiếng Việt" (a presentation control) into a retrieval query and answered it with
        # "I found no information about this", and the language preference it carried was never
        # persisted -- `chat_sessions.preferred_language` is still NULL for that session.
        #
        # `system_error` and not a knowledge-gap reason, deliberately: an LLM dependency failed, which
        # is exactly what `system_error` means, and invariant 8 requires that an outage never be
        # reported as an absence of knowledge. It is an EXISTING reason, so no new user-visible
        # fallback reason is introduced (rev. 2 §8). `error_stage`/`error_code` are annotated here
        # rather than left to `_fallback`'s default, which would mislabel this as
        # `generation.provider`/`provider_error` -- generation was never reached.
        #
        # Ordering: the `out_of_scope` return above still comes first. Both recoveries there already
        # require a healthy verdict, so a degraded turn the guardrail rejected is refused as
        # off-topic exactly as before -- a failed interpretation cannot talk its way past the gate.
        if turn.interpretation_degraded:
            if trace is not None:
                trace.annotate(
                    error_stage="turn_interpreter", error_code="interpretation_degraded"
                )
            return await self._fallback(
                turn, reason="system_error", gate="interpretation_degraded"
            )

        control_language = control.presentation.language if control.updates_presentation else None
        control_detail = control.presentation.detail if control.updates_presentation else None
        turn.answer_language = _effective_answer_language(
            control_language,
            turn.presentation_preferences.language,
            verdict.presentation.language,
            question,
        )
        turn.effective_response_length = _effective_response_length(
            control_detail,
            turn.presentation_preferences.detail,
            verdict.presentation.detail,
            response_length,
        )

        route = verdict.route
        resolved_question = verdict.resolved_question

        # Re-answer uses the trusted topic subject when the model did not resolve one.
        if wants_previous_reanswer:
            if route is not InterpreterRoute.REUSE or verdict.sanitized:
                resolved_question = turn.topic_state.subject or resolved_question
            route = InterpreterRoute.REUSE

        if turn.index == 0 and route in (InterpreterRoute.REUSE, InterpreterRoute.CONVERSATION):
            route = InterpreterRoute.KNOWLEDGE

        # F5 audit 2026-08-30 (observability remediation): the dispatcher-level, post-default,
        # post-override values -- distinct from `turn_interpreter.py`'s own
        # `turn_interpreter_control_application`/`turn_interpreter_route` annotations, which
        # show the model's RAW verdict before this method's `wants_previous_reanswer`/turn-0
        # overrides run. Comparing the two directly answers "did the model misclassify, or did
        # a dispatcher override change the outcome" without re-deriving either from the other
        # fields already on the trace.
        if trace is not None:
            trace.annotate(
                decision_details={
                    "control_application_effective": (
                        control_application.value if control_application is not None else None
                    ),
                    "wants_previous_reanswer": wants_previous_reanswer,
                    "pure_presentation_control": pure_presentation_control,
                    "route_effective": route.value,
                    "resolved_question_effective": resolved_question,
                }
            )

        if pure_presentation_control:
            return await self._answer_presentation_control(turn, control=control)

        if route is InterpreterRoute.SOCIAL:
            fast_path_intent = classify_social(question)
            social_intent = fast_path_intent or verdict.social_intent
            if fast_path_intent is None and verdict.affect is TurnAffect.SUPPORT_NEEDED:
                social_intent = SocialIntent.BUDDY_SUPPORT
            # A1 remediation (F5 audit): affect is a MODIFIER, not a competing route -- a turn
            # that names an answerable subject must compose as KNOWLEDGE + an affect
            # acknowledgement, never collapse into a contentless BUDDY_SUPPORT reply, no matter
            # how the model's own holistic route/social_intent choice came out. This is a
            # deterministic override on top of the model's judgment, not another worked example:
            # it fires purely from `has_answerable_subject`, so it generalizes to any phrasing.
            social_intent = _compose_social_intent_with_subject(
                social_intent, has_answerable_subject=verdict.has_answerable_subject
            )
            if social_intent is not None:
                # A presentation overlay is not evidence of intent. Persistent controls were
                # already handled above through the discriminator-bearing `ConversationControl`;
                # promoting OTHER from a bare language field recreates the exact inference bug
                # this contract removes.
                target_language = (
                    verdict.presentation.language
                    if social_intent is SocialIntent.LANGUAGE_PREFERENCE
                    else None
                )
                return await self._answer_social_mode(
                    turn,
                    question=question,
                    budget=budget,
                    intent=social_intent,
                    target_language=target_language,
                    response_tone=response_tone,
                )
            route = InterpreterRoute.KNOWLEDGE

        if route is InterpreterRoute.CATALOG:
            return await self._answer_catalog_mode(turn, filters=filters)

        if route is InterpreterRoute.CONVERSATION:
            return await self._answer_conversation_mode(turn, question=question, budget=budget)

        effective_length = turn.effective_response_length
        effective_language = turn.answer_language
        length_source = (
            "control"
            if control_detail
            else "conversation"
            if turn.presentation_preferences.detail
            else "turn"
            if verdict.presentation.detail
            else "user"
        )
        language_source = (
            "control"
            if control_language
            else "conversation"
            if turn.presentation_preferences.language
            else "turn"
            if verdict.presentation.language
            else "detected"
        )

        # The mixed-turn half of the affect design (`_with_affect_acknowledgement`). Set only
        # here, i.e. only for KNOWLEDGE/REUSE: SOCIAL already returned above with BUDDY_SUPPORT's
        # own template and must not receive both, and CATALOG/CONVERSATION are transcript/listing
        # replies where an emotional opener would be noise rather than warmth.
        #
        # Note what this does NOT do: it does not touch `route`, retrieval, `resolved_question`,
        # the evidence-sufficiency verdict, the generator prompt, claim validation, or citations.
        # A turn with `affect=SUPPORT_NEEDED` runs the identical pipeline to the same turn without
        # it and produces the identical claims -- the only difference is one static server-authored
        # sentence in front of the assembled text. That containment is what makes exclusion (1) in
        # the interpreter prompt safe to rely on: even a wrong SUPPORT_NEEDED costs a misplaced
        # nicety, never an ungrounded answer.
        #
        # Nothing sets this on an `out_of_scope` fallback: `_pre_route_scope_check` returns before
        # the interpreter is ever called, so no `affect` exists for a turn the guardrail rejected.
        # That is the correct outcome, not an oversight -- a refusal is not a place to sound warm
        # about a request that was refused.
        turn.affect_support_needed = verdict.affect is TurnAffect.SUPPORT_NEEDED
        turn.affect_language = effective_language

        effective_policy, policy_source = narrow_policy(
            verdict.knowledge_policy,
            route=route,
            knowledge_domain=knowledge_domain,
            question=question,
            resolved_question=resolved_question,
            degraded=policy_degraded,
            config=self.general_knowledge_config,
        )
        if trace is not None:
            trace.annotate(
                decision_details={
                    "knowledge_policy_effective": effective_policy.value,
                    "knowledge_policy_source": policy_source.value,
                }
            )

        general_knowledge_blocked_by_domain = (
            policy_source is PolicySource.FORCED_DOMAIN
            and verdict.knowledge_policy is KnowledgePolicy.GENERAL_ALLOWED
        )

        if off_topic_guidance:
            if effective_policy is not KnowledgePolicy.GENERAL_ALLOWED:
                if trace is not None:
                    trace.annotate(
                        decision_details={"off_topic_guidance_narrowed": policy_source.value}
                    )
                return await self._fallback(turn, reason="out_of_scope", gate="scope_rejected")
            if trace is not None:
                trace.annotate(decision_details={"off_topic_guidance": True})
            # `accepted=[]` with no retrieval call at all: the corpus is not consulted for a turn the
            # topical guardrail rejected. `original_fallback_reason="out_of_scope"` keeps the original
            # refusal as the user-visible outcome if the generator yields nothing usable (§10.3/§10.4).
            # `internal_lookup_failed` stays False -- nothing failed here, the lookup was deliberately
            # not attempted, and that note would claim an outage that did not happen.
            off_topic_result = await self._generate_and_persist(
                turn,
                question=question,
                accepted=[],
                partial_coverage=False,
                knowledge_domain=knowledge_domain,
                budget=budget,
                response_length=effective_length,
                response_tone=response_tone,
                answer_language=effective_language,
                response_length_source=length_source,
                answer_language_source=language_source,
                knowledge_policy=effective_policy,
                policy_source=policy_source,
                original_fallback_reason="out_of_scope",
            )
            await self._update_topic_state(
                turn, resolved_question=resolved_question, result=off_topic_result
            )
            return off_topic_result

        if route is InterpreterRoute.REUSE:
            result = await self._answer_reuse_route(
                turn,
                question=question,
                resolved_question=resolved_question,
                filters=filters,
                knowledge_domain=knowledge_domain,
                budget=budget,
                response_length=effective_length,
                response_tone=response_tone,
                answer_language=effective_language,
                response_length_source=length_source,
                answer_language_source=language_source,
                knowledge_policy=effective_policy,
                policy_source=policy_source,
            )
            if result is not None:
                await self._update_topic_state(
                    turn, resolved_question=resolved_question, result=result
                )
                return result

            degraded_policy, degraded_policy_source = narrow_policy(
                verdict.knowledge_policy,
                route=InterpreterRoute.KNOWLEDGE,
                knowledge_domain=knowledge_domain,
                question=question,
                resolved_question=resolved_question,
                degraded=policy_degraded,
                config=self.general_knowledge_config,
            )
            if trace is not None:
                trace.annotate(
                    decision_details={
                        "reuse_degraded_to_knowledge": True,
                        "knowledge_policy_effective": degraded_policy.value,
                        "knowledge_policy_source": degraded_policy_source.value,
                    }
                )
            degraded_result = await self._answer_knowledge_route(
                turn,
                question=question,
                resolved_question=resolved_question,
                filters=filters,
                knowledge_domain=knowledge_domain,
                budget=budget,
                response_length=effective_length,
                response_tone=response_tone,
                answer_language=effective_language,
                response_length_source=length_source,
                answer_language_source=language_source,
                retrieval_query_override=self._previous_retrieval_query(turn),
                knowledge_policy=degraded_policy,
                policy_source=degraded_policy_source,
                general_knowledge_blocked_by_domain=(
                    degraded_policy_source is PolicySource.FORCED_DOMAIN
                    and verdict.knowledge_policy is KnowledgePolicy.GENERAL_ALLOWED
                ),
            )
            await self._update_topic_state(
                turn, resolved_question=resolved_question, result=degraded_result
            )
            return degraded_result

        knowledge_result = await self._answer_knowledge_route(
            turn,
            question=question,
            resolved_question=resolved_question,
            filters=filters,
            knowledge_domain=knowledge_domain,
            budget=budget,
            response_length=effective_length,
            response_tone=response_tone,
            answer_language=effective_language,
            response_length_source=length_source,
            answer_language_source=language_source,
            knowledge_policy=effective_policy,
            policy_source=policy_source,
            general_knowledge_blocked_by_domain=general_knowledge_blocked_by_domain,
        )
        await self._update_topic_state(
            turn, resolved_question=resolved_question, result=knowledge_result
        )
        return knowledge_result

    async def transcript(
        self, *, user_id: int, conversation_id: uuid.UUID
    ) -> ConversationTranscript:
        """Rehydrate a stored conversation for a client that reloaded.

        Authorization is re-derived exactly as it is for `ask`, from the conversation's own frozen
        scope: a membership revoked since the conversation started raises `PermissionError` here
        rather than replaying project answers to somebody who lost access.
        """
        loaded = await self.conversations.transcript(public_id=conversation_id, user_id=user_id)
        if loaded is None:
            raise ConversationNotFoundError("conversation not found")
        conversation, messages, claims_by_message, citations_by_message = loaded
        membership, categories = await self._scope(
            user_id=user_id,
            knowledge_domain=conversation.knowledge_domain,
            membership_id=conversation.membership_id,
        )
        chunk_ids = sorted(
            {citation.chunk_id for group in citations_by_message.values() for citation in group}
        )
        evidence: dict[int, RetrievalResult] = {}
        if chunk_ids:
            filters = RetrievalFilters(
                knowledge_domains=frozenset({conversation.knowledge_domain}),
                project_id=membership.project_id if membership else None,
                document_categories=categories,
            )
            evidence = {
                result.chunk.chunk_id: result
                for result in await self.retrieval_engine.load_scoped_chunks(
                    chunk_ids, filters=filters
                )
            }

        questions: dict[int, str] = {}
        answers: dict[int, ChatMessage] = {}
        for message in messages:
            if message.role is MessageRole.USER:
                questions.setdefault(message.turn_index, message.content)
            elif message.role is MessageRole.ASSISTANT:
                answers.setdefault(message.turn_index, message)

        turns: list[TranscriptTurn] = []
        for index in sorted(questions):
            answer = answers.get(index)
            citations: list[dict[str, object]] = []
            claims: list[dict[str, object]] = []
            general_guidance: list[dict[str, object]] = []
            if answer is not None:
                message_citations = citations_by_message.get(answer.message_id, [])
                for citation in message_citations:
                    citations.append(
                        _transcript_citation(citation, evidence.get(citation.chunk_id))
                    )
                for claim in claims_by_message.get(answer.message_id, []):
                    claim_citations = [
                        _transcript_citation(citation, evidence.get(citation.chunk_id))
                        for citation in message_citations
                        if citation.claim_id == claim.claim_id
                    ]
                    claim_text, claim_redacted = _redact_observed(claim.text)
                    claims.append(
                        {
                            "claim_index": claim.claim_index,
                            "text": claim_text,
                            "support_type": claim.support_type.value,
                            "verdict": claim.verdict,
                            "redacted": claim.redacted or claim_redacted,
                            "citations": claim_citations,
                        }
                    )
                for item in answer.general_guidance or []:
                    if not isinstance(item, dict):
                        continue
                    raw_text = item.get("text")
                    if not isinstance(raw_text, str) or not raw_text.strip():
                        continue
                    guidance_text, _guidance_redacted = _redact_observed(raw_text)
                    raw_kind = item.get("kind")
                    guidance_kind = raw_kind if isinstance(raw_kind, str) and raw_kind else "explanation"
                    general_guidance.append({"text": guidance_text, "kind": guidance_kind})
            answer_shape = (
                "guidance_only"
                if answer is not None and answer.answer_status == "general_guidance" and not claims
                else "mixed"
                if claims and general_guidance
                else "internal_only"
            )
            turns.append(
                TranscriptTurn(
                    turn_index=index,
                    question=questions[index],
                    answer=answer.content if answer else None,
                    fallback=bool(answer and answer.fallback_reason),
                    fallback_reason=answer.fallback_reason if answer else None,
                    trace_id=answer.trace_id if answer else None,
                    citations=tuple(citations),
                    answer_status=answer.answer_status if answer else None,
                    validator_outcome=answer.validator_outcome if answer else None,
                    claims=tuple(claims),
                    conflict=answer.conflict if answer else None,
                    general_guidance=tuple(general_guidance),
                    answer_shape=answer_shape,
                )
            )
        return ConversationTranscript(
            conversation_id=conversation.public_id,
            knowledge_domain=conversation.knowledge_domain,
            membership_id=conversation.membership_id,
            turns=tuple(turns),
        )

    async def ask(
        self,
        *,
        question: str,
        user_id: int,
        knowledge_domain: DocumentDomain = DocumentDomain.PROJECT,
        membership_id: int | None = None,
        conversation_id: uuid.UUID | None = None,
        trace_id: str | None = None,
        question_fingerprint: str | None = None,
        response_length: ResponseLength = ResponseLength.STANDARD,
        response_tone: ResponseTone = ResponseTone.NEUTRAL,
    ) -> ChatResult:
        trace_id = trace_id or uuid.uuid4().hex
        trace = TraceRecorder(trace_id)
        trace.annotate(
            user_id=user_id,
            membership_id=membership_id,
            knowledge_domain=knowledge_domain.value,
            question_fingerprint=question_fingerprint,
        )
        try:
            with bind_trace(trace):
                result = await self._ask_traced(
                    question=question,
                    user_id=user_id,
                    knowledge_domain=knowledge_domain,
                    membership_id=membership_id,
                    conversation_id=conversation_id,
                    trace_id=trace_id,
                    response_length=response_length,
                    response_tone=response_tone,
                )
                if not result.fallback:
                    trace.annotate(outcome="success", fallback_reason=None)
                return result
        except (PermissionError, ValueError, ConversationNotFoundError, ConversationScopeMismatchError):
            trace.annotate(outcome="error", error_stage="scope", error_code="request_rejected")
            raise
        except ChatBudgetExceededError as exc:
            trace.annotate(outcome="error", error_stage="budget_guard", error_code=exc.reason)
            raise
        except Exception:
            trace.annotate(outcome="error", error_code="unexpected_error")
            raise
        finally:
            try:
                await self.telemetry_sink.submit(trace.snapshot())
            except Exception:
                # Even a broken custom/test adapter must not alter chat semantics.
                pass

    async def _ask_traced(
        self,
        *,
        question: str,
        user_id: int,
        knowledge_domain: DocumentDomain,
        membership_id: int | None,
        conversation_id: uuid.UUID | None,
        trace_id: str,
        response_length: ResponseLength = ResponseLength.STANDARD,
        response_tone: ResponseTone = ResponseTone.NEUTRAL,
    ) -> ChatResult:
        budget = self.budget_config.start()
        if not question.strip():
            raise ValueError("question must not be empty")
        # Authorization first, and recomputed on every turn: a forged membership_id or a revoked
        # membership fails here, before any conversation row is created or read.
        with telemetry_span("scope"):
            membership, categories = await self._scope(
                user_id=user_id, knowledge_domain=knowledge_domain, membership_id=membership_id
            )
        trace = current_trace()
        if trace is not None:
            trace.annotate(project_id=membership.project_id if membership else None)
        # Budget guard runs after ACL (never leak whether a project exists to an unauthorized
        # caller via a 429) but before any conversation row is created, retrieval, or LLM call —
        # a rejected request must never reach an expensive path or leave partial state behind.
        await self.chat_budget_guard.check(
            self.session,
            user_id=user_id,
            project_id=membership.project_id if membership else None,
        )
        # Built from `_scope` only. Neither history nor a condensed/resolved question can reach
        # this. Moved up front (harmless, no I/O) so both the Phase 2 interpreter path and the
        # legacy path below can share it, and so a shadow-mode interpreter call can use it too.
        filters = RetrievalFilters(
            knowledge_domains=frozenset({knowledge_domain}),
            project_id=membership.project_id if membership else None,
            document_categories=categories,
        )
        project_name: str | None = None
        if knowledge_domain is DocumentDomain.PROJECT and membership is not None:
            # 2026-08-22 live-probe finding (scope_gate.py): the judge needs the project's own
            # name to anchor a bare proper noun/document title to "this project". Fetched once
            # here and reused by both ScopeGate and the interpreter, instead of twice.
            project = await self.session.get(Project, membership.project_id)
            project_name = project.name if project is not None else None

        if self.turn_interpreter is not None and self.turn_interpreter.config.enabled:
            return await self._ask_with_interpreter(
                question=question,
                user_id=user_id,
                knowledge_domain=knowledge_domain,
                membership=membership,
                filters=filters,
                project_name=project_name,
                conversation_id=conversation_id,
                trace_id=trace_id,
                budget=budget,
                response_length=response_length,
                response_tone=response_tone,
            )

        # ---- Legacy (pre-interpreter) regex-routed flow. Unchanged behaviour. -------------------
        # Weakness #4 (CHANGE_LOG.md 2026-08-21): routed BEFORE query_condenser/retrieval, from
        # the raw question alone, so a conversation-meta question ("what did I ask first?") never
        # becomes a noisy retrieval query and never needs PROJECT/POLICY evidence to answer.
        answer_mode = classify_intent(question)
        trace = current_trace()
        if trace is not None:
            trace.annotate(decision_details={"answer_mode": answer_mode.value})
        turn = await self._begin_turn(
            question=question,
            user_id=user_id,
            knowledge_domain=knowledge_domain,
            membership=membership,
            conversation_id=conversation_id,
            trace_id=trace_id,
            answer_mode=answer_mode,
        )
        if self.turn_interpreter is not None and self.turn_interpreter.config.shadow:
            # Phase 1: runs and logs alongside the regex routing below; changes nothing.
            await self._run_shadow_interpreter(
                turn,
                question=question,
                knowledge_domain=knowledge_domain,
                project_name=project_name,
                filters=filters,
                budget=budget,
                legacy_answer_mode=answer_mode,
            )
        if answer_mode is AnswerMode.CONVERSATION:
            # Terminal branch: no ScopeGate (it classifies KNOWLEDGE topicality and would
            # wrongly reject a meta-question), no RetrievalEngine call, no citation validator --
            # see ARCHITECTURE.md's CONVERSATION_GROUNDED addendum for why none of those apply.
            return await self._answer_conversation_mode(turn, question=question, budget=budget)
        if answer_mode is AnswerMode.SOCIAL:
            # Terminal branch (spec §6.3): deterministic template, zero ScopeGate, zero
            # RetrievalEngine call, zero citation validator -- same rationale as CONVERSATION.
            return await self._answer_social_mode(
                turn, question=question, budget=budget, response_tone=response_tone
            )
        if answer_mode is AnswerMode.CATALOG:
            # Terminal branch (spec §8): metadata-only lookup, zero ScopeGate, zero embedding,
            # zero RelevanceGate/EvidenceSufficiencyGate, zero citation validator.
            return await self._answer_catalog_mode(turn, filters=filters)
        # Scope/intent gate (weakness #3): a cheap pre-retrieval decision, deliberately separate
        # from RelevanceGate — this rejects the QUESTION's intent (off-topic, role-hijack, PII/
        # secret extraction), never the retrieved CONTENT's relevance. Runs on the condensed
        # query so a short legitimate follow-up ("trả lời bằng tiếng việt") is judged with the
        # same context retrieval itself uses, not in isolation. Fails open (see ScopeGate
        # docstring) — never blocks a turn on its own failure.
        if self.scope_gate is not None:
            # 2026-08-22 live-probe finding: without the project's own name, the judge has
            # nothing to anchor a bare proper noun/document title to "this project" and falls
            # back to its own world-knowledge prior (e.g. "Thanos" the Marvel character) --
            # false-rejecting genuinely in-scope questions. `knowledge_domain` is also passed
            # through so POLICY turns get `_POLICY_CONTEXT` (second live-probe finding: "how does
            # annual leave work?" false-rejected -- see scope_gate.py for the diagnosis).
            # `project_name` was already fetched once, up front in `_ask_traced`.
            with telemetry_span("scope_gate"):
                in_scope = await self.scope_gate.is_in_scope(
                    turn.condensed.retrieval_query,
                    budget,
                    subject_name=project_name,
                    knowledge_domain=knowledge_domain,
                    has_prior_turn=turn.index > 0,
                )
            if not in_scope:
                return await self._fallback(turn, reason="out_of_scope", gate="scope_rejected")
        # Resolved conversational question (spec §9.1): what `EvidenceSufficiencyGate` judges the
        # evidence against. Starts as Tier-0/1's output and is updated in place only if Tier-2's
        # LLM rewrite is the one that actually produced the accepted evidence below -- never a
        # fourth text representation, just this local variable threaded through.
        resolved_query = turn.condensed.retrieval_query
        # Follow-up continuity (target design item 4, narrowed by spec §7 [REV2]): a PURE
        # elaboration/rephrase/example follow-up (`classify_elaboration`, whole-utterance-
        # anchored -- deliberately narrower than `followup_detected`) right after a turn that
        # left evidence behind (an `insufficient_evidence` verdict OR a successful grounded turn)
        # reuses that evidence instead of repeating retrieval. A topic-switch follow-up ("còn VPN
        # thì sao?") never attempts reuse at all, so it never spends a wasted
        # `EvidenceSufficiencyGate` call on evidence that was never going to answer it -- it goes
        # straight to fresh retrieval below, exactly as if no prior turn existed. Re-validated
        # against the CURRENT scope via `load_scoped_chunks` -- never a raw replay of stored ids.
        accepted = await self._reused_related_evidence(turn, question=question, filters=filters)
        reused = accepted is not None
        trace = current_trace()
        if trace is not None:
            trace.annotate(
                decision_details={
                    "related_evidence_reused": reused,
                    "reuse_attempted": classify_elaboration(question),
                }
            )
        if not reused:
            try:
                candidates = await self._retrieve(resolved_query, filters, budget)
                if turn.condensed.tier == "expanded":
                    # Tier-1's anchor prefix helps a genuinely deictic follow-up ("what about
                    # it?") but can bias a follow-up that already names its OWN new topic away
                    # from the right document -- the anchor's longer, richer text can dominate
                    # the expanded query's embedding (2026-08-22 live-probe finding: "còn cách
                    # chạy test thì sao?" retrieved the prior turn's "Coding Style Guide" chunk
                    # instead of "Contributing"'s actual test-running instructions). Additive fix,
                    # not a replacement: also retrieve on the bare, un-expanded question and merge
                    # -- the expanded-query retrieval above still runs and still contributes, and
                    # RelevanceGate below still scores everything against the ORIGINAL question,
                    # completely unchanged. This never fires for a standalone question (no
                    # history) or a pure-elaboration reuse turn (handled above, never reaches
                    # here).
                    standalone_candidates = await self._retrieve(question, filters, budget)
                    candidates = _merge_candidate_sets(candidates, standalone_candidates)
            except (ExternalServiceFailure, RetrievalUnavailableError) as failure:
                self._annotate_retrieval_layer_failure(failure, budget)
                await self._recover_retrieval_datastore_failure(failure)
                return await self._fallback(turn, reason="system_error", gate="error")
            # The gate always scores the ORIGINAL question: expansion widens retrieval, never the gate.
            accepted = self.gate.accept(question, candidates)
            if not accepted:
                try:
                    accepted, rewritten = await self._rewrite_and_retry(
                        turn, question=question, filters=filters, budget=budget
                    )
                    if rewritten:
                        resolved_query = rewritten
                except (ExternalServiceFailure, RetrievalUnavailableError) as failure:
                    self._annotate_retrieval_layer_failure(failure, budget)
                    await self._recover_retrieval_datastore_failure(failure)
                    return await self._fallback(turn, reason="system_error", gate="error")
            if not accepted:
                suggestions = await self.retrieval_engine.list_available_topics(filters)
                return await self._fallback(
                    turn,
                    reason="no_evidence",
                    gate="rejected",
                    knowledge_domain=knowledge_domain,
                    suggestions=suggestions,
                )

        ranked_chunk_ids = tuple(item.chunk.chunk_id for item in accepted)
        accepted = await self._expand_procedure_evidence(
            resolved_query, accepted, filters=filters
        )
        procedure_structure_completed = tuple(
            item.chunk.chunk_id for item in accepted
        ) != ranked_chunk_ids

        # Weakness #2 remainder: RelevanceGate accepted per-candidate similarity, but similarity
        # to the question is not the same as answering it (CHANGE_LOG.md 2026-08-21). This judges
        # the accepted set as a whole, once, right before generation -- see
        # evidence_sufficiency_gate.py module docstring for why it fails CLOSED, unlike scope_gate.
        # Judged against `resolved_query` (spec §9.1), never the raw original question and never
        # the prior turn's question -- so a genuine "present that document" follow-up passes even
        # though the original question alone did not.
        partial_coverage = False
        if self.evidence_sufficiency_gate is not None and not procedure_structure_completed:
            with telemetry_span("evidence_sufficiency_gate"):
                sufficiency = await self.evidence_sufficiency_gate.check(resolved_query, accepted, budget)
            trace = current_trace()
            if trace is not None:
                # Coverage verdict vs. claim-validation quality (spec §9.4): logged here, in
                # trace/telemetry only -- this never touches `answer_status`, set independently
                # below from `generated.answer_status`.
                trace.annotate(
                    decision_details={"evidence_sufficiency_gate_verdict": sufficiency.verdict.value}
                )
            if sufficiency.verdict is EvidenceSufficiencyVerdict.AMBIGUOUS:
                return await self._fallback(
                    turn,
                    reason="ambiguous_question",
                    gate="ambiguous_question",
                    knowledge_domain=knowledge_domain,
                    suggestions=self._suggestions_from_evidence(accepted),
                )
            if not sufficiency.sufficient:
                errored = sufficiency.errored
                return await self._fallback(
                    turn,
                    reason="system_error" if errored else "insufficient_evidence",
                    gate="error" if errored else "insufficient_evidence",
                    knowledge_domain=knowledge_domain,
                    related_evidence=() if errored else accepted,
                    suggestions=() if errored else self._suggestions_from_evidence(accepted),
                )
            partial_coverage = sufficiency.verdict is EvidenceSufficiencyVerdict.PARTIAL
        elif procedure_structure_completed:
            trace = current_trace()
            if trace is not None:
                trace.annotate(
                    decision_details={
                        "evidence_sufficiency_gate_skipped": "complete_numbered_procedure"
                    }
                )

        generated = await self.answer_generator.generate(
            question,
            accepted,
            history=turn.window.prompt_turns,
            budget=budget,
            response_length=response_length,
            response_tone=response_tone,
        )
        if isinstance(generated, GenerationFailure):
            trace = current_trace()
            if trace is not None and generated.reason == "validator_fail":
                trace.annotate(
                    error_stage="claim_verification", error_code="validator_fail"
                )
            return await self._fallback(
                turn,
                reason=generated.reason,
                gate="accepted",
                validator="failed",
                retry_count=generated.retry_count,
            )

        persistence_started = time.monotonic_ns()
        answer, _answer_redacted = _redact_observed(generated.answer)
        if partial_coverage:
            # Spec §9.3/§9.5: appended after assembly, deterministic, server-composed -- never
            # generated by the model. §9.4: `answer_status` below is untouched by this, and stays
            # exactly `generated.answer_status` (claim-validation quality only).
            note_language = (
                turn.answer_language
                if turn.presentation_preferences.language is not None
                else AnswerLanguage.VI
            )
            answer = f"{answer}\n\n{_partial_coverage_note(knowledge_domain, note_language)}"
        conflict, _conflict_redacted = (
            _redact_observed(generated.conflict) if generated.conflict is not None else (None, False)
        )
        answer_status = "conflict" if conflict is not None else generated.answer_status
        evidence_by_chunk_id = {item.chunk.chunk_id: item for item in accepted}
        chunk_redaction_memo: dict[int, tuple[str, bool]] = {}
        citations: list[dict[str, object]] = []
        claims: list[dict[str, object]] = []
        message = self.conversations.append(
            session_id=turn.session_id,
            turn_index=turn.index,
            role=MessageRole.ASSISTANT,
            content=answer,
            trace_id=turn.trace_id,
            grounded=True,
            confidence=max(
                (
                    citation.relevance_score
                    for claim in generated.claims
                    for citation in claim.citations
                ),
                default=None,
            ),
            answer_status=answer_status,
            validator_outcome=generated.validator_outcome,
            conflict=conflict,
        )
        await self.session.flush()
        stored_claims: list[tuple[AnswerClaim, VerifiedClaim, bool]] = []
        for claim_index, claim in enumerate(generated.claims):
            claim_text, claim_redacted = _redact_observed(claim.text)
            stored_claim = AnswerClaim(
                message_id=message.message_id,
                claim_index=claim_index,
                text=claim_text,
                support_type=ClaimSupportType(claim.support.value),
                verdict="passed",
                redacted=claim_redacted,
            )
            self.session.add(stored_claim)
            stored_claims.append((stored_claim, claim, claim_redacted))
        await self.session.flush()

        for stored_claim, claim, claim_redacted in stored_claims:
            claim_citations: list[dict[str, object]] = []
            for item in claim.citations:
                # ``item`` comes only from deterministic validation; the lookup cannot expand the
                # immutable accepted set and a missing id is therefore a programming error.
                evidence = evidence_by_chunk_id[item.chunk_id]
                quote, quote_redacted = _redact_observed(item.quote)
                source_content, content_redacted = _redact_chunk_content(
                    item.chunk_id, evidence.chunk.content, chunk_redaction_memo
                )
                citation_payload = {
                    "chunk_id": item.chunk_id,
                    "quote": quote,
                    "knowledge_domain": item.knowledge_domain.value,
                    "relevance_score": item.relevance_score,
                    "redacted": quote_redacted or content_redacted,
                    "document_id": evidence.document_id,
                    "version_id": evidence.version_id,
                    "source_title": evidence.document_title,
                    # No raw artifact URL: the original upload is unredacted, and a citation
                    # link to it would hand back exactly what this boundary just removed
                    # (F-21 §8). Title/section/anchor keep the citation usable.
                    "source_url": _citation_source_url(evidence),
                    "section_heading": evidence.chunk.section_path or evidence.chunk.heading,
                    "anchor": evidence.chunk.anchor,
                    "source_content": source_content,
                }
                citations.append(citation_payload)
                claim_citations.append(citation_payload)
                self.session.add(
                    Citation(
                        message_id=message.message_id,
                        claim_id=stored_claim.claim_id,
                        chunk_id=item.chunk_id,
                        quote=quote,
                        relevance_score=item.relevance_score,
                    )
                )
            claims.append(
                {
                    "claim_index": stored_claim.claim_index,
                    "text": stored_claim.text,
                    "support_type": stored_claim.support_type.value,
                    "verdict": stored_claim.verdict,
                    "redacted": claim_redacted,
                    "citations": claim_citations,
                }
            )
        await self.conversations.touch(session_id=turn.session_id)
        await self.session.commit()
        record_duration("persistence.answer", persistence_started)
        trace = current_trace()
        if trace is not None:
            if not trace.has_attribute("prompt_tokens"):
                trace.annotate(prompt_tokens=generated.prompt_tokens)
            if not trace.has_attribute("completion_tokens"):
                trace.annotate(completion_tokens=generated.completion_tokens)
            if not trace.has_attribute("model"):
                trace.annotate(model=generated.model)
            trace.annotate(
                gate_decision="accepted",
                validator_outcome=generated.validator_outcome,
                repair_retry_count=generated.retry_count,
            )
        return ChatResult(
            answer,
            tuple(citations),
            False,
            None,
            turn.trace_id,
            turn.conversation_id,
            answer_status=answer_status,
            validator_outcome=generated.validator_outcome,
            claims=tuple(claims),
            conflict=conflict,
        )
