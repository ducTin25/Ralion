"""F2 Sub-flow B ingestion worker (F6 rule mining prerequisite).

Uses a real SQLite-backed AsyncSession (tests/conftest.py::db_session) so the
persistence path is genuinely exercised, and a real GithubClient with a fake
transport (no real HTTP) so the fetch/shape path is genuinely exercised too —
only the network boundary is faked.
"""

from __future__ import annotations

import base64
from datetime import date

import pytest
from sqlalchemy import select

from src.model.raw_pr_comment import RawPrComment
from src.modules.knowledge.ingestion.github_client import GithubClient
from src.modules.knowledge.ingestion.pr_corpus_ingestion import ingest_pr_corpus

REPO = "acme/widgets"


class _FakeTransport:
    def __init__(self, responses: dict[str, object]) -> None:
        self._responses = responses

    def __call__(self, url: str):
        for prefix, response in self._responses.items():
            if url.startswith(prefix):
                return response
        raise AssertionError(f"unexpected URL: {url}")


def _client(responses: dict[str, object]) -> GithubClient:
    return GithubClient("tok", transport=_FakeTransport(responses))


@pytest.mark.asyncio
async def test_ingests_all_three_sources_for_one_human_pr(db_session) -> None:
    responses = {
        "https://api.github.com/search/issues": {
            "items": [
                {"number": 1, "title": "Fix bug", "user": {"login": "alice"}, "html_url": "https://x/1"},
            ]
        },
        "https://api.github.com/repos/acme/widgets/pulls/1/comments": [
            {"id": 10, "user": {"login": "bob"}, "body": "please rename this to avoid double negatives",
             "html_url": "https://x/c10", "created_at": "2025-08-05T00:00:00Z", "in_reply_to_id": None},
        ],
        "https://api.github.com/repos/acme/widgets/issues/1/comments": [
            {"id": 20, "user": {"login": "carol"}, "body": "LGTM", "html_url": "https://x/c20",
             "created_at": "2025-08-06T00:00:00Z"},
        ],
        "https://api.github.com/repos/acme/widgets/pulls/1/reviews": [
            {"id": 30, "user": {"login": "dave"}, "body": "we usually avoid this pattern here",
             "html_url": "https://x/r30", "submitted_at": "2025-08-07T00:00:00Z", "state": "COMMENTED"},
        ],
    }
    client = _client(responses)

    summary = await ingest_pr_corpus(
        db_session, client, repo=REPO, since=date(2025, 8, 1), until=date(2025, 8, 31)
    )

    assert summary.prs_total == 1
    assert summary.prs_ingested == 1
    assert summary.prs_bot_excluded == 0
    assert summary.rows_by_type == {
        "review_comment(diff)": 1,
        "issue_comment(conversation)": 1,
        "review(summary)": 1,
    }

    rows = (await db_session.scalars(select(RawPrComment))).all()
    assert len(rows) == 3
    assert {r.type for r in rows} == {
        "review_comment(diff)", "issue_comment(conversation)", "review(summary)",
    }
    review_row = next(r for r in rows if r.type == "review(summary)")
    assert review_row.review_state == "COMMENTED"
    assert review_row.author == "dave"


@pytest.mark.asyncio
async def test_bot_authored_pr_is_excluded_and_never_fetched(db_session) -> None:
    responses = {
        "https://api.github.com/search/issues": {
            "items": [
                {"number": 2, "title": "Bump dep", "user": {"login": "renovate[bot]"}, "html_url": "https://x/2"},
            ]
        },
        # No entry for pulls/2/comments etc. — the fake raises AssertionError if
        # the worker ever tries to fetch them, proving the exclusion happens
        # before any comment/review fetch for this PR.
    }
    client = _client(responses)

    summary = await ingest_pr_corpus(
        db_session, client, repo=REPO, since=date(2025, 8, 1), until=date(2025, 8, 31)
    )

    assert summary.prs_total == 1
    assert summary.prs_bot_excluded == 1
    assert summary.prs_ingested == 0
    rows = (await db_session.scalars(select(RawPrComment))).all()
    assert rows == []


@pytest.mark.asyncio
async def test_body_over_500_chars_is_not_truncated(db_session) -> None:
    long_body = "This sentence keeps going and going. " * 20
    assert len(long_body) > 500
    responses = {
        "https://api.github.com/search/issues": {
            "items": [{"number": 3, "title": "x", "user": {"login": "alice"}, "html_url": "https://x/3"}]
        },
        "https://api.github.com/repos/acme/widgets/pulls/3/comments": [
            {"id": 1, "user": {"login": "alice"}, "body": long_body, "html_url": "https://x/c1",
             "created_at": "2025-08-05T00:00:00Z", "in_reply_to_id": None},
        ],
        "https://api.github.com/repos/acme/widgets/issues/3/comments": [],
        "https://api.github.com/repos/acme/widgets/pulls/3/reviews": [],
    }
    client = _client(responses)

    await ingest_pr_corpus(db_session, client, repo=REPO, since=date(2025, 8, 1), until=date(2025, 8, 31))

    row = (await db_session.scalars(select(RawPrComment))).one()
    assert row.body == long_body
    assert len(row.body) > 500


@pytest.mark.asyncio
async def test_secret_is_redacted_before_persist_and_scanned_at_is_set(db_session) -> None:
    secret_body = "please rotate this key: access_key = AKIAIOSFODNN7EXAMPLE right away"
    responses = {
        "https://api.github.com/search/issues": {
            "items": [{"number": 4, "title": "x", "user": {"login": "alice"}, "html_url": "https://x/4"}]
        },
        "https://api.github.com/repos/acme/widgets/pulls/4/comments": [
            {"id": 1, "user": {"login": "alice"}, "body": secret_body, "html_url": "https://x/c1",
             "created_at": "2025-08-05T00:00:00Z", "in_reply_to_id": None},
        ],
        "https://api.github.com/repos/acme/widgets/issues/4/comments": [],
        "https://api.github.com/repos/acme/widgets/pulls/4/reviews": [],
    }
    client = _client(responses)

    summary = await ingest_pr_corpus(db_session, client, repo=REPO, since=date(2025, 8, 1), until=date(2025, 8, 31))

    assert summary.secret_findings >= 1
    row = (await db_session.scalars(select(RawPrComment))).one()
    assert "AKIAIOSFODNN7EXAMPLE" not in row.body
    assert "[REDACTED]" in row.body
    assert row.secret_scanned_at is not None


@pytest.mark.asyncio
async def test_diff_code_is_normalized_and_secret_redacted_before_persist(db_session) -> None:
    before_source = "access_key = 'AKIAIOSFODNN7EXAMPLE'\nold_call()\n"
    after_source = "access_key = 'AKIAIOSFODNN7EXAMPLE'\nnew_call()\n"
    responses = {
        "https://api.github.com/search/issues": {
            "items": [{"number": 6, "title": "x", "user": {"login": "alice"}, "html_url": "https://x/6"}]
        },
        "https://api.github.com/repos/acme/widgets/pulls/6/comments": [
            {
                "id": 61,
                "user": {"login": "bob"},
                "body": "do not commit credentials",
                "html_url": "https://x/c61",
                "created_at": "2025-08-05T00:00:00Z",
                "in_reply_to_id": None,
                "path": "src/config.py",
                "side": "RIGHT",
                "commit_id": "reviewed-sha",
                "diff_hunk": (
                    "@@ -1,2 +1,2 @@\n-old_key = None\n"
                    "+access_key = 'AKIAIOSFODNN7EXAMPLE'"
                ),
            }
        ],
        "https://api.github.com/repos/acme/widgets/issues/6/comments": [],
        "https://api.github.com/repos/acme/widgets/pulls/6/reviews": [],
        "https://api.github.com/repos/acme/widgets/pulls/6": {"base": {"sha": "base-sha"}},
        "https://api.github.com/repos/acme/widgets/contents/src/config.py?ref=base-sha": {
            "encoding": "base64",
            "content": base64.b64encode(before_source.encode()).decode(),
        },
        "https://api.github.com/repos/acme/widgets/contents/src/config.py?ref=reviewed-sha": {
            "encoding": "base64",
            "content": base64.b64encode(after_source.encode()).decode(),
        },
    }

    summary = await ingest_pr_corpus(
        db_session,
        _client(responses),
        repo=REPO,
        since=date(2025, 8, 1),
        until=date(2025, 8, 31),
    )

    row = (await db_session.scalars(select(RawPrComment))).one()
    assert row.code_path_snapshot == "src/config.py"
    assert "AKIAIOSFODNN7EXAMPLE" not in row.code_snippet_snapshot
    assert "[REDACTED]" in row.code_snippet_snapshot
    assert "AKIAIOSFODNN7EXAMPLE" not in row.code_before_snapshot
    assert "AKIAIOSFODNN7EXAMPLE" not in row.code_after_snapshot
    assert "[REDACTED]" in row.code_before_snapshot
    assert "[REDACTED]" in row.code_after_snapshot
    assert row.secret_scanned_at is not None
    assert summary.secret_findings >= 1


@pytest.mark.asyncio
async def test_every_persisted_row_has_secret_scanned_at_set(db_session) -> None:
    responses = {
        "https://api.github.com/search/issues": {
            "items": [{"number": 5, "title": "x", "user": {"login": "alice"}, "html_url": "https://x/5"}]
        },
        "https://api.github.com/repos/acme/widgets/pulls/5/comments": [
            {"id": 1, "user": {"login": "alice"}, "body": "a perfectly ordinary review comment right here",
             "html_url": "https://x/c1", "created_at": "2025-08-05T00:00:00Z", "in_reply_to_id": None},
        ],
        "https://api.github.com/repos/acme/widgets/issues/5/comments": [],
        "https://api.github.com/repos/acme/widgets/pulls/5/reviews": [],
    }
    client = _client(responses)

    await ingest_pr_corpus(db_session, client, repo=REPO, since=date(2025, 8, 1), until=date(2025, 8, 31))

    unscanned = (
        await db_session.scalars(select(RawPrComment).where(RawPrComment.secret_scanned_at.is_(None)))
    ).all()
    assert unscanned == []
