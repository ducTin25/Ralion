"""F-20/F-21 — the one shared secret scanner: detection, value-only redaction, safety.

Table-driven on purpose: the ruleset is the security boundary, so every shape it must
catch is written down here rather than described in prose somewhere.
"""

from __future__ import annotations

import pytest

from src.core.security.secret_scan import REDACTION_PLACEHOLDER, redact, scan

AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0"
    ".dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
)
GITHUB_TOKEN = "ghp_16C7e42F292c6912E7710c838347Ae178B4a"

POSITIVES = [
    ("aws key", f"Deploy uses aws_access_key_id = {AWS_KEY} for staging.", AWS_KEY),
    ("jwt", f"Call the API with Authorization: Bearer {JWT}", JWT),
    ("github token", f"Set GH_TOKEN={GITHUB_TOKEN} in your shell.", GITHUB_TOKEN),
    ("bare token assignment", "token=supersecretvalue123", "supersecretvalue123"),
    ("api_key colon", "api_key: placeholder-value-9f2b", "placeholder-value-9f2b"),
    ("quoted password", "password = 'Tr0ubad0ur-2026'", "Tr0ubad0ur-2026"),
]

NEGATIVES = [
    "Đừng chia sẻ token cá nhân của bạn với người khác.",
    "The password policy requires a rotation every 90 days.",
    "This document is not secret; publish it on the intranet.",
    "Run cargo test before submitting a pull request.",
]


@pytest.mark.parametrize(("label", "text", "secret"), POSITIVES, ids=[row[0] for row in POSITIVES])
def test_detects_and_redacts_the_value(label: str, text: str, secret: str) -> None:
    result = scan(text)

    assert result.has_findings, label
    assert secret not in result.redacted_content
    assert REDACTION_PLACEHOLDER in result.redacted_content


@pytest.mark.parametrize("text", NEGATIVES)
def test_prose_mentioning_credential_words_is_not_a_finding(text: str) -> None:
    result = scan(text)

    assert not result.has_findings
    assert result.redacted_content == text


def test_redaction_keeps_the_key_and_surrounding_structure() -> None:
    result = scan("## Setup\n- **api_key:** live-key-value-1234\nRun the installer.\n")

    assert "## Setup" in result.redacted_content
    assert "api_key" in result.redacted_content
    assert "Run the installer." in result.redacted_content
    assert "live-key-value-1234" not in result.redacted_content


def test_private_key_block_body_is_removed_not_just_the_header() -> None:
    body = "MIIBOgIBAAJBAKj34GkxFhD90vcNLYLInFEX6Ppy1tPf9Cnzj4p4WGeKLs1Pt8Qu"
    text = f"-----BEGIN RSA PRIVATE KEY-----\n{body}\n-----END RSA PRIVATE KEY-----"

    result = scan(text)

    assert result.has_findings
    assert body not in result.redacted_content


@pytest.mark.parametrize(("label", "text", "secret"), POSITIVES, ids=[row[0] for row in POSITIVES])
def test_scanning_already_redacted_text_finds_nothing_new(label: str, text: str, secret: str) -> None:
    once = scan(text)
    twice = scan(once.redacted_content)

    assert twice.findings == (), label
    assert twice.redacted_content == once.redacted_content


def test_input_is_never_mutated() -> None:
    text = f"token={GITHUB_TOKEN}"

    scan(text)

    assert text == f"token={GITHUB_TOKEN}"


def test_finding_repr_carries_no_secret_value() -> None:
    result = scan(f"aws_secret_access_key = {AWS_KEY}")

    for finding in result.findings:
        assert AWS_KEY not in repr(finding)
        assert finding.rule_id
        assert finding.line_number >= 1


def test_redact_returns_text_and_flag() -> None:
    clean_text, hit = redact("nothing to see here")
    dirty_text, dirty_hit = redact(f"token={GITHUB_TOKEN}")

    assert (clean_text, hit) == ("nothing to see here", False)
    assert dirty_hit and GITHUB_TOKEN not in dirty_text
