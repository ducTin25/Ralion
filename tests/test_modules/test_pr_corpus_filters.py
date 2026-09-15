"""is_bot/is_noise — ported unchanged from scripts/density_check.py (F6 gate R-1).

These pin the exact classification rules the annotation script and any future F6
corpus consumer share, so a change here is a deliberate rule change, not drift
between two copies.
"""

from __future__ import annotations

from src.modules.knowledge.ingestion.pr_corpus_filters import is_bot, is_noise


def test_is_bot_matches_github_app_suffix() -> None:
    assert is_bot("renovate[bot]")
    assert is_bot("dependabot[bot]")


def test_is_bot_matches_known_non_suffix_bots_case_insensitively() -> None:
    assert is_bot("bors")
    assert is_bot("RustBot".lower())
    assert is_bot("Copilot")


def test_is_bot_matches_extra_bots_but_not_unlisted_logins() -> None:
    assert is_bot("triage-bot", extra_bots=frozenset({"triage-bot"}))
    assert not is_bot("triage-bot")
    assert not is_bot("alice")


def test_is_noise_rejects_short_and_stock_phrases() -> None:
    assert is_noise("")
    assert is_noise(None)
    assert is_noise("LGTM")
    assert is_noise("nit")
    assert is_noise("\U0001F44D")  # emoji-only


def test_is_noise_accepts_substantive_feedback() -> None:
    body = "This should really avoid double negatives in naming, could we rename it?"
    assert not is_noise(body)


def test_is_noise_requires_at_least_ten_words() -> None:
    assert is_noise("short but not a stock phrase at all")
    assert not is_noise("this one sentence has exactly ten words in it now")
