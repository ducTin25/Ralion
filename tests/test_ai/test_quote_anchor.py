import random
import re
import time
from types import SimpleNamespace

import pytest

import src.ai.orchestration.claim_validation as claim_validation
from src.ai.orchestration.answer_generator import (
    CitationRef,
    ClaimRef,
    ClaimSupport,
    GroundedAnswer,
)
from src.ai.orchestration.claim_validation import validate_claims
from src.ai.orchestration.quote_anchor import build_index, find_source_span
from src.ai.retrieval_engine.retrieval_engine import RetrievalResult
from src.model.enums import DocumentDomain


def _find(content: str, quote: str) -> str | None:
    return find_source_span(build_index(content), quote)


@pytest.mark.parametrize(
    ("content", "quote", "expected"),
    [
        ("Run cargo test now", "Run cargo test now", "Run cargo test now"),
        ("Run cargo test now", "Run cargo", "Run cargo"),
        ("Before run cargo test after", "run cargo test", "run cargo test"),
        ("Before run cargo test", "cargo test", "cargo test"),
        ("Run cargo test", "fabricated quote", None),
        ("Run   cargo\ttest", "Run cargo test", "Run   cargo\ttest"),
        ("Run\ncargo\ttest", "Run cargo test", "Run\ncargo\ttest"),
        ("Run\u00a0cargo test", "run cargo test", "Run\u00a0cargo test"),
        ("Run Cargo Test", "run cargo test", "Run Cargo Test"),
        ("cargo test", "cargo tes", None),
        ("repeat quote; repeat quote", "repeat quote", "repeat quote"),
        ("Caf\u00e9 policy", "Cafe\u0301 policy", "Caf\u00e9 policy"),
        ("Runner cargo test", "Run\u200bner cargo\u2060 test", "Runner cargo test"),
    ],
)
def test_find_source_span_cases(content: str, quote: str, expected: str | None) -> None:
    assert _find(content, quote) == expected


def test_returned_anchor_is_a_true_source_substring_with_original_whitespace() -> None:
    content = "Prefix  Run\n cargo\ttest  Suffix"
    anchor = _find(content, "run cargo test")
    assert anchor == "Run\n cargo\ttest"
    assert anchor in content


def _old_normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _old_verified_substring(quote: str, content: str) -> str | None:
    normalised_quote = _old_normalise(quote)
    if not normalised_quote:
        return None
    words = re.findall(r"\S+", content)
    for start in range(len(words)):
        for end in range(start + 1, len(words) + 1):
            candidate = " ".join(words[start:end])
            if _old_normalise(candidate) == normalised_quote:
                return candidate
    return None


def test_ascii_whitespace_acceptance_matches_previous_verifier() -> None:
    randomizer = random.Random(20260818)
    separators = (" ", "  ", "\n", "\t", "\u00a0")
    vocabulary = ("alpha", "beta", "gamma", "delta", "v1.2", "word,")
    for _ in range(100):
        words = [randomizer.choice(vocabulary) for _ in range(randomizer.randint(1, 12))]
        content = "".join(
            word + (randomizer.choice(separators) if index < len(words) - 1 else "")
            for index, word in enumerate(words)
        )
        start = randomizer.randrange(len(words))
        end = randomizer.randrange(start + 1, len(words) + 1)
        quote = " ".join(words[start:end]) if randomizer.random() < 0.75 else "fabricated token"
        assert (_old_verified_substring(quote, content) is None) is (_find(content, quote) is None)


def _candidate(content: str) -> RetrievalResult:
    return RetrievalResult(
        chunk=SimpleNamespace(chunk_id=11, content=content, section_path="Tests", heading=None),
        knowledge_domain=DocumentDomain.PROJECT,
        document_id=1,
        version_id=1,
        dense_score=0.44,
        hybrid_score=0.03,
    )


@pytest.mark.parametrize("word_count", [70, 171, 500, 700])
def test_linear_verifier_representative_chunk_sizes(word_count: int) -> None:
    content = " ".join(f"token{index}" for index in range(word_count))
    started = time.perf_counter()
    assert _find(content, f"token{word_count - 3} token{word_count - 2} token{word_count - 1}")
    assert time.perf_counter() - started < 0.025


def test_validation_reuses_one_index_for_five_citations_under_25ms() -> None:
    content = " ".join(f"token{index}" for index in range(1000))
    answer = GroundedAnswer(
        claims=[
            ClaimRef(
                text="Grounded answer",
                support=ClaimSupport.DIRECT,
                citations=[
                    CitationRef(chunk_id=11, quote=f"token{index} token{index + 1}")
                    for index in (100, 300, 500, 700, 900)
                ],
            )
        ],
    )
    started = time.perf_counter()
    verified = validate_claims(answer.claims, [_candidate(content)], "")
    elapsed = time.perf_counter() - started
    assert len(verified.claims) == 1
    assert elapsed < 0.025


def test_validation_builds_the_chunk_index_once_for_repeated_citations(monkeypatch: pytest.MonkeyPatch) -> None:
    content = "one two three four"
    answer = GroundedAnswer(
        claims=[
            ClaimRef(
                text="Grounded answer",
                support=ClaimSupport.DIRECT,
                citations=[
                    CitationRef(chunk_id=11, quote="one two"),
                    CitationRef(chunk_id=11, quote="three four"),
                ],
            )
        ],
    )
    calls = 0
    real_build_index = claim_validation.build_index

    def counted_build_index(value: str):
        nonlocal calls
        calls += 1
        return real_build_index(value)

    monkeypatch.setattr(claim_validation, "build_index", counted_build_index)
    validate_claims(answer.claims, [_candidate(content)], "")
    assert calls == 1


# POL-010 (2026-08-30): a legitimate, exact quote that correctly stops before a separator glued
# straight onto the source's last word (no space) used to be rejected outright, because the
# quote's end landed inside that fused token instead of on a registered boundary.
@pytest.mark.parametrize(
    ("content", "quote"),
    [
        (
            "HR tạo yêu cầu cấp thiết bị **trước ngày vào ít nhất 3 ngày làm việc**, ghi rõ vị trí.",
            "HR tạo yêu cầu cấp thiết bị **trước ngày vào ít nhất 3 ngày làm việc**",
        ),
        ("Run cargo test, then deploy", "Run cargo test"),
        ("See the config; it is required", "See the config"),
        ("Ask the owner: they approve", "Ask the owner"),
        ("Is this ready? Confirm now", "Is this ready"),
        ("Stop now! Then continue", "Stop now"),
    ],
)
def test_accepts_exact_quote_ending_before_punctuation_glued_to_the_source_word(
    content: str, quote: str
) -> None:
    anchor = _find(content, quote)
    assert anchor is not None
    assert anchor in content


def test_glued_punctuation_tolerance_does_not_accept_a_mid_word_cut() -> None:
    # "wor" is a real prefix of "word," but is not itself a token boundary anywhere in the
    # source -- the relaxation must never let a partial word through.
    assert _find("This is a word, not wor", "This is a word, not wor") == (
        "This is a word, not wor"
    )
    assert _find("This is a word, trailing text", "This is a wor") is None


def test_glued_punctuation_tolerance_does_not_accept_a_different_trailing_word() -> None:
    # The token after stripping punctuation must match exactly -- this must never turn into a
    # fuzzy/edit-distance match against a similarly-spelled neighboring word.
    assert _find("Approved by the manager, not the lead", "Approved by the manage") is None
