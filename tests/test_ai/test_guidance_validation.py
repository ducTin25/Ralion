"""Unit tests for `guidance_validation.validate_guidance` (F5_BOUNDED_GENERAL_KNOWLEDGE_SPEC.md
§8). §8.5's worked-outcomes table IS the test -- each row below is one parametrised case."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.ai.orchestration.answer_generator import GuidanceKind, GuidanceRef
from src.ai.orchestration.guidance_validation import GeneralKnowledgeConfig, validate_guidance
from src.ai.retrieval_engine.retrieval_engine import RetrievalResult
from src.model.enums import DocumentDomain


def _config(**overrides) -> GeneralKnowledgeConfig:
    defaults = dict(
        enabled=True,
        max_guidance_items=6,
        guidance_item_max_chars=600,
        allow_on_partial=True,
        allow_after_insufficient=True,
        generic_token_allowlist=(
            "python3",
            "pip3",
            "s3",
            "x86_64",
            "utf-8",
            "base64",
            "sha256",
            "oauth2",
            "http2",
            "ipv4",
            "ipv6",
        ),
    )
    defaults.update(overrides)
    return GeneralKnowledgeConfig(**defaults)


def _evidence(content: str, *, chunk_id: int = 1) -> RetrievalResult:
    return RetrievalResult(
        chunk=SimpleNamespace(chunk_id=chunk_id, content=content),
        knowledge_domain=DocumentDomain.PROJECT,
        document_id=1,
        version_id=1,
        dense_score=0.9,
        hybrid_score=0.5,
    )


def _guidance(text: str, kind: GuidanceKind = GuidanceKind.INSTRUCTION) -> GuidanceRef:
    return GuidanceRef(text=text, kind=kind)


# §8.5 table: (text, evidence_text, question, expect_allowed, expect_risk_flags)
@pytest.mark.parametrize(
    ("text", "evidence_text", "question", "expect_allowed", "expect_risk_flags"),
    [
        ("python -m venv .venv", "", "how do I create a virtualenv?", True, frozenset()),
        ("python --version", "", "how do I check my python version?", True, frozenset()),
        ("pip install --upgrade pip", "", "how do I upgrade pip?", True, frozenset()),
        (
            "docker-compose up -d",
            "",
            "how do I start the containers?",
            True,
            frozenset({"guidance_novel_identifier"}),
        ),
        ("python3 -m venv .venv", "", "how do I create a virtualenv?", True, frozenset()),
        (
            "install Python 3.11",
            "This repo requires Python 3.11.",
            "how do I install the Python version this repo requires?",
            True,
            frozenset(),
        ),
        (
            "install Python 3.13",
            "This repo requires Python 3.11.",
            "how do I install the Python version this repo requires?",
            False,
            None,
        ),
        (
            "you'll need PostgreSQL 16",
            "This repo uses PostgreSQL.",
            "what database does this repo use?",
            False,
            None,
        ),
        (
            "in this repo, run `alembic upgrade head`",
            "",
            "what's the migration command for this repo?",
            False,
            None,
        ),
        (
            "in projects using Alembic, `alembic upgrade head` applies pending migrations",
            "",
            "what does alembic upgrade head do?",
            True,
            frozenset(),
        ),
        (
            "a virtualenv isolates dependencies per project",
            "",
            "what is a virtualenv?",
            True,
            frozenset(),
        ),
    ],
)
def test_worked_outcomes_table(
    text: str,
    evidence_text: str,
    question: str,
    expect_allowed: bool,
    expect_risk_flags: frozenset[str] | None,
) -> None:
    evidence = [_evidence(evidence_text)] if evidence_text else []
    result = validate_guidance([_guidance(text)], evidence, question, config=_config())

    if expect_allowed:
        assert len(result.items) == 1, result.rejected
        assert result.rejected == ()
        if expect_risk_flags is not None:
            assert result.items[0].risk_flags == expect_risk_flags
    else:
        assert result.items == ()
        assert len(result.rejected) == 1


def test_project_deixis_rejected_r2() -> None:
    result = validate_guidance(
        [_guidance("in this repo, run `alembic upgrade head`")],
        [],
        "what's the migration command?",
        config=_config(),
    )
    assert result.rejected[0].reasons == ("guidance_project_deixis",)


def test_project_deixis_vietnamese_diacritic_insensitive() -> None:
    result = validate_guidance(
        [_guidance("trong dự án này, chạy `alembic upgrade head`")],
        [],
        "lệnh migration của dự án này là gì?",
        config=_config(),
    )
    assert result.rejected[0].reasons == ("guidance_project_deixis",)


def test_unsupported_value_token_reason_code_lists_tokens() -> None:
    result = validate_guidance(
        [_guidance("you'll need PostgreSQL 16")],
        [],
        "what database does this use?",
        config=_config(),
    )
    assert result.rejected[0].reasons[0].startswith("guidance_unsupported_value:")
    assert "16" in result.rejected[0].reasons[0]


def test_empty_text_rejected_r6() -> None:
    result = validate_guidance(
        [SimpleNamespace(text="   ", kind=GuidanceKind.INSTRUCTION)],
        [],
        "q",
        config=_config(),
    )
    assert result.rejected[0].reasons == ("guidance_empty_text",)


def test_too_long_rejected_r5() -> None:
    result = validate_guidance(
        [_guidance("x" * 700)],
        [],
        "q",
        config=_config(guidance_item_max_chars=600),
    )
    assert result.rejected[0].reasons == ("guidance_item_too_long",)


def test_overflow_items_dropped_with_limit_reason_r5() -> None:
    words = ("one", "two", "three", "four", "five", "six", "seven", "eight")
    items = [_guidance(f"step {word}") for word in words]
    result = validate_guidance(items, [], "q", config=_config(max_guidance_items=6))
    assert len(result.items) == 6
    overflow = [r for r in result.rejected if r.reasons == ("guidance_item_limit",)]
    assert len(overflow) == 2
    assert result.had_rejection is True


def test_allowlisted_token_not_flagged_novel() -> None:
    result = validate_guidance(
        [_guidance("run python3 -m venv .venv")],
        [],
        "how do I create a virtualenv?",
        config=_config(),
    )
    assert result.items[0].risk_flags == frozenset()


def test_no_citation_field_exists_on_guidance_ref() -> None:
    """R1, structural: guaranteed by the type, not the validator -- pinned here as documentation."""
    assert "citations" not in GuidanceRef.model_fields
    assert "chunk_id" not in GuidanceRef.model_fields


# Live-observed defect, 2026-08-23 (see CHANGE_LOG.md): step/list numbering and "-bit"
# architecture suffixes are formatting, not factual value assertions -- R3 must not reject a
# genuinely generic, step-by-step guidance item just because it is numbered.
@pytest.mark.parametrize(
    "text",
    [
        "Bước 1: Tải trình cài đặt Python từ trang chủ chính thức.",
        "Bước 2: Chạy trình cài đặt và làm theo hướng dẫn trên màn hình.",
        "Step 3: Verify the installation by running `python --version`.",
        "1. Download the installer from the official website.",
        "2) Run the installer and follow the on-screen prompts.",
        "Chọn bản 64-bit nếu hệ điều hành của bạn hỗ trợ.",
    ],
)
def test_step_markers_and_bit_architecture_are_not_treated_as_values(text: str) -> None:
    result = validate_guidance([_guidance(text)], [], "how do I install Python?", config=_config())
    assert result.items != (), result.rejected
    assert result.rejected == ()


def test_step_marker_does_not_mask_a_real_unsupported_value_elsewhere_in_the_item() -> None:
    """The strip is scoped to the marker itself -- a genuinely ungrounded value elsewhere in the
    same item must still be caught."""
    result = validate_guidance(
        [_guidance("Bước 1: Cài đặt PostgreSQL phiên bản 16.")],
        [],
        "how do I install a database?",
        config=_config(),
    )
    assert result.items == ()
    assert result.rejected[0].reasons[0].startswith("guidance_unsupported_value:")
    assert "16" in result.rejected[0].reasons[0]
