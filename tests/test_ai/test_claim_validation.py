import inspect
from types import SimpleNamespace

from src.ai.orchestration.answer_generator import CitationRef, ClaimRef, ClaimSupport
from src.ai.orchestration.claim_validation import validate_claims
from src.ai.retrieval_engine.retrieval_engine import RetrievalResult
from src.model.enums import DocumentDomain


def _evidence(chunk_id: int, content: str) -> RetrievalResult:
    return RetrievalResult(
        chunk=SimpleNamespace(chunk_id=chunk_id, content=content),
        knowledge_domain=DocumentDomain.POLICY,
        document_id=1,
        version_id=1,
        dense_score=0.8,
    )


def _claim(
    text: str,
    citations: list[CitationRef],
    support: ClaimSupport = ClaimSupport.DIRECT,
) -> ClaimRef:
    return ClaimRef(text=text, support=support, citations=citations)


def test_fabricated_chunk_id_is_removed_and_causes_zero_coverage() -> None:
    result = validate_claims([_claim("Known", [CitationRef(chunk_id=99, quote="Known")])], [], "?")
    assert result.coverage is False
    assert result.rejected_claims[0].reasons == (
        "citation_outside_accepted_evidence",
        "claim_has_no_anchors",
    )


def test_one_bad_anchor_does_not_remove_claim_with_another_valid_anchor() -> None:
    result = validate_claims(
        [
            _claim(
                "Run cargo test.",
                [CitationRef(chunk_id=1, quote="fabricated"), CitationRef(chunk_id=1, quote="Run cargo test.")],
            )
        ],
        [_evidence(1, "Run cargo test.")],
        "How do I test?",
    )
    assert result.coverage is True
    assert [citation.quote for citation in result.claims[0].citations] == ["Run cargo test."]
    assert result.claims[0].validation_notes == ("citation_anchor_not_found",)


def test_all_bad_anchors_remove_the_claim() -> None:
    result = validate_claims(
        [_claim("Known", [CitationRef(chunk_id=1, quote="fabricated")])],
        [_evidence(1, "Actual evidence")],
        "?",
    )
    assert result.coverage is False
    assert "claim_has_no_anchors" in result.rejected_claims[0].reasons


def test_dangling_lead_in_is_rejected_as_incomplete_even_with_a_valid_anchor() -> None:
    result = validate_claims(
        [_claim("Để chạy dự án, hãy làm theo các bước sau:", [CitationRef(chunk_id=1, quote="chạy dự án")])],
        [_evidence(1, "Hướng dẫn chạy dự án bằng các lệnh được liệt kê bên dưới.")],
        "Làm thế nào để chạy dự án?",
    )

    assert result.coverage is False
    assert result.rejected_claims[0].reasons == ("incomplete_claim_text",)


def test_vague_procedure_promise_is_rejected_when_question_asks_how_to_run() -> None:
    result = validate_claims(
        [
            _claim(
                "Bạn cần cài Python và pip, sau đó thực hiện các bước cài đặt môi trường local.",
                [CitationRef(chunk_id=1, quote="Python và pip")],
            )
        ],
        [_evidence(1, "Cần có Python và pip trước khi chạy các lệnh cài đặt.")],
        "Dự án dùng công nghệ gì và làm thế nào để chạy trên máy local?",
    )

    assert result.coverage is False
    assert result.rejected_claims[0].reasons == ("incomplete_claim_text",)


def test_d3_accepts_number_in_vietnamese_claim_when_english_evidence_has_same_number() -> None:
    result = validate_claims(
        [_claim("Thời gian là 4 giờ.", [CitationRef(chunk_id=1, quote="4 hours.")])],
        [_evidence(1, "The duration is 4 hours.")],
        "How long?",
    )
    assert result.coverage is True


def test_d3_rejects_fabricated_number_but_allows_number_from_user_question() -> None:
    fabricated = validate_claims(
        [_claim("The duration is 9 hours.", [CitationRef(chunk_id=1, quote="4 hours.")])],
        [_evidence(1, "The duration is 4 hours.")],
        "How long?",
    )
    inherited = validate_claims(
        [_claim("You asked about 9 hours.", [CitationRef(chunk_id=1, quote="4 hours.")])],
        [_evidence(1, "The duration is 4 hours.")],
        "Is it 9 hours?",
    )
    assert fabricated.coverage is False
    assert "unsupported_hard_tokens:9" in fabricated.rejected_claims[0].reasons
    assert inherited.coverage is True


def test_numbered_list_ordinal_is_not_a_factual_numeric_token() -> None:
    result = validate_claims(
        [_claim("1. Sidecar uploads blocks.", [CitationRef(chunk_id=1, quote="Sidecar uploads blocks.")])],
        [_evidence(1, "Sidecar uploads blocks.")],
        "List components",
    )

    assert result.coverage is True


def test_genuine_component_quantity_still_requires_evidence() -> None:
    result = validate_claims(
        [_claim("Thanos has 6 components.", [CitationRef(chunk_id=1, quote="Thanos components")])],
        [_evidence(1, "Thanos components include Sidecar and Receiver.")],
        "How many components?",
    )

    assert result.coverage is False
    assert "unsupported_hard_tokens:6" in result.rejected_claims[0].reasons


def test_presentation_quote_wrapper_preserves_canonical_citation_anchor() -> None:
    result = validate_claims(
        [
            _claim(
                "Sidecar uploads blocks.",
                [CitationRef(chunk_id=1, quote='“Sidecar uploads blocks.”')],
            )
        ],
        [_evidence(1, "Sidecar uploads blocks.")],
        "Explain the architecture",
    )

    assert result.coverage is True
    assert result.claims[0].citations[0].chunk_id == 1
    assert result.claims[0].citations[0].quote == "Sidecar uploads blocks."


def test_nonexistent_citation_remains_rejected_after_quote_normalization() -> None:
    result = validate_claims(
        [_claim("Known", [CitationRef(chunk_id=1, quote='"invented"')])],
        [_evidence(1, "Actual evidence")],
        "?",
    )

    assert result.coverage is False
    assert "citation_anchor_not_found" in result.rejected_claims[0].reasons


def test_d3_rejects_fabricated_policy_identifier() -> None:
    result = validate_claims(
        [_claim("See HR-POL-009.", [CitationRef(chunk_id=1, quote="HR-POL-001.")])],
        [_evidence(1, "See HR-POL-001.")],
        "Which policy?",
    )
    assert result.coverage is False
    assert "unsupported_hard_tokens:hr-pol-009" in result.rejected_claims[0].reasons


def test_inferred_claim_keeps_two_chunks_but_downgrades_with_one() -> None:
    two_chunks = validate_claims(
        [
            _claim(
                "Combined conclusion.",
                [CitationRef(chunk_id=1, quote="First"), CitationRef(chunk_id=2, quote="Second")],
                ClaimSupport.INFERRED,
            )
        ],
        [_evidence(1, "First source"), _evidence(2, "Second source")],
        "?",
    )
    one_chunk = validate_claims(
        [
            _claim(
                "Conclusion.",
                [CitationRef(chunk_id=1, quote="First")],
                ClaimSupport.INFERRED,
            )
        ],
        [_evidence(1, "First source")],
        "?",
    )
    assert two_chunks.claims[0].support is ClaimSupport.INFERRED
    assert "inferred_multi_source" in two_chunks.claims[0].risk_flags
    assert one_chunk.claims[0].support is ClaimSupport.DIRECT
    assert one_chunk.had_degradation is True


def test_modality_is_risk_only_and_validator_signature_cannot_retrieve() -> None:
    class ExplodingEvidence:
        chunk = SimpleNamespace(chunk_id=1, content="The procedure is followed.")
        knowledge_domain = DocumentDomain.POLICY
        dense_score = 0.8

        def retrieve(self):  # pragma: no cover - the validator must never call this.
            raise AssertionError("validator attempted retrieval")

    result = validate_claims(
        [_claim("This must always be followed.", [CitationRef(chunk_id=1, quote="followed.")])],
        [ExplodingEvidence()],
        "?",
    )
    parameters = inspect.signature(validate_claims).parameters
    assert result.coverage is True
    assert "absolute_modality" in result.claims[0].risk_flags
    assert {"retrieval_engine", "session", "repository", "membership"}.isdisjoint(parameters)


# ----------------------------------------------------------------------------------------------
# B-07 (audit 2026-08-25). The question is NOT a grounding source for entities.
# ----------------------------------------------------------------------------------------------


def test_b07_entity_named_only_in_the_question_cannot_enter_a_grounded_claim() -> None:
    """The live failure: asked "why not PostgreSQL or MySQL", the answer asserted that those two
    "are not optimized for metric data" as a cited claim, citing a chunk that never mentions
    either. The old subtraction exempted every token appearing in the question, which turned the
    user's own wording into evidence. An entity must come from the cited chunks or not be
    asserted at all."""
    result = validate_claims(
        [
            _claim(
                "PostgreSQL và MySQL không tối ưu cho dữ liệu metric.",
                [CitationRef(chunk_id=1, quote="stores metric data in immutable")],
            )
        ],
        [_evidence(1, "The engine stores metric data in immutable blocks.")],
        "Vì sao không dùng PostgreSQL hay MySQL?",
    )
    assert result.coverage is False
    reasons = result.rejected_claims[0].reasons
    assert any(reason.startswith("unsupported_hard_tokens:") for reason in reasons)
    assert "mysql" in reasons[-1] and "postgresql" in reasons[-1]


def test_b07_negating_a_user_claim_is_not_a_way_to_smuggle_the_entity_in() -> None:
    """Chosen behaviour (a), Tech Lead decision 2026-08-25: an unsupported NEGATION is still an
    unsupported claim about that entity. The correct answer shape is to assert the supported fact
    instead -- `grounded_answer_prompt_v5._USER_CLAIM_SECTION` is what asks for that; this test
    pins that the validator does not quietly allow the negation form."""
    result = validate_claims(
        [
            _claim(
                "Cơ sở dữ liệu của Thanos không phải là MongoDB.",
                [CitationRef(chunk_id=1, quote="keeps metric data in object")],
            )
        ],
        [_evidence(1, "Thanos keeps metric data in object storage.")],
        "Vậy database của Thanos là MongoDB đúng không?",
    )
    assert result.coverage is False
    assert "unsupported_hard_tokens:mongodb" in result.rejected_claims[0].reasons


def test_b07_entity_present_in_the_evidence_is_still_accepted() -> None:
    """Anti-over-fix. The rule is about entities the EVIDENCE is silent on -- an answer naming
    something its own cited chunk names must keep working, or every normal answer regresses."""
    result = validate_claims(
        [
            _claim(
                "Dự án dùng PostgreSQL làm cơ sở dữ liệu chính.",
                [CitationRef(chunk_id=1, quote="The primary database is PostgreSQL.")],
            )
        ],
        [_evidence(1, "The primary database is PostgreSQL.")],
        "Dự án dùng database gì?",
    )
    assert result.coverage is True


def test_b07_numeric_exemption_from_the_question_is_deliberately_kept() -> None:
    """The counterpart to the tightening above, kept explicit so a future "tidy-up" cannot delete
    it by symmetry: a user routinely quotes a number back in their own question ("is it really 9
    hours?"), and an answer restating it is normal. `test_d3_...` covers the same contract from
    the number side; this one states WHY the two classes are treated differently."""
    result = validate_claims(
        [_claim("Bạn hỏi về mốc 9 giờ.", [CitationRef(chunk_id=1, quote="4 hours.")])],
        [_evidence(1, "The duration is 4 hours.")],
        "Có phải 9 giờ không?",
    )
    assert result.coverage is True
