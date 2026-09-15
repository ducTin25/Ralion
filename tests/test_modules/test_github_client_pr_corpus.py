"""GithubClient's PR/review/comment corpus methods — the F6 prerequisite.

Uses the injectable ``transport`` seam (not real HTTP) so these stay fast, offline
unit tests. The same seam is what lets ``scripts/density_check.py`` reuse this
client's endpoint/shaping logic while keeping its own disk-cache + rate-limit
transport unchanged.
"""

from __future__ import annotations

import base64
from datetime import date, datetime

import pytest

from src.modules.knowledge.ingestion.github_client import GithubClient


def test_constructor_requires_token_when_no_transport_injected() -> None:
    with pytest.raises(ValueError):
        GithubClient("")


def test_constructor_allows_empty_token_when_transport_injected() -> None:
    GithubClient("", transport=lambda url: {})  # must not raise


class _FakeTransport:
    """Routes fake URLs to canned responses, recording every call made."""

    def __init__(self, responses: dict[str, object]) -> None:
        self._responses = responses
        self.urls: list[str] = []

    def __call__(self, url: str):
        self.urls.append(url)
        for prefix, response in self._responses.items():
            if url.startswith(prefix):
                return response
        raise AssertionError(f"unexpected URL: {url}")


def test_list_merged_prs_paginates_search_api_and_dedupes_by_number() -> None:
    page1 = {
        "items": [
            {"number": 1, "title": "Fix bug", "user": {"login": "alice"}, "html_url": "https://x/1"},
            {"number": 2, "title": "Bump dep", "user": {"login": "renovate[bot]"}, "html_url": "https://x/2"},
        ]
    }
    transport = _FakeTransport({
        "https://api.github.com/search/issues": page1,
    })
    client = GithubClient("tok", transport=transport)

    prs = client.list_merged_prs("acme/widgets", date(2024, 1, 1), date(2024, 1, 31))

    assert {p.number for p in prs} == {1, 2}
    assert next(p for p in prs if p.number == 1).author == "alice"
    # one month window -> exactly one query, one page (< 100 results stops pagination)
    assert len(transport.urls) == 1


def test_get_repository_created_at_parses_and_caches_utc_timestamp() -> None:
    transport = _FakeTransport({
        "https://api.github.com/repos/acme/widgets": {"created_at": "2024-01-02T03:04:05Z"},
    })
    client = GithubClient("tok", transport=transport)

    assert client.get_repository_created_at("acme/widgets") == datetime(2024, 1, 2, 3, 4, 5)
    assert client.get_repository_created_at("acme/widgets") == datetime(2024, 1, 2, 3, 4, 5)
    assert len(transport.urls) == 1


def test_fetch_pr_comments_combines_review_and_issue_comments() -> None:
    review_comments = [
        {"id": 101, "user": {"login": "alice"}, "body": "please rename this", "html_url": "https://x/c1",
         "created_at": "2024-01-01T00:00:00Z", "in_reply_to_id": 42,
         "path": "src/naming.py", "side": "RIGHT",
         "diff_hunk": "@@ -8,3 +8,3 @@ def enabled():\n def enabled():\n-    return not disabled\n+    return is_enabled"},
    ]
    issue_comments = [
        {"id": 202, "user": {"login": "bob"}, "body": "LGTM", "html_url": "https://x/c2", "created_at": "2024-01-02T00:00:00Z"},
    ]
    transport = _FakeTransport({
        "https://api.github.com/repos/acme/widgets/pulls/7/comments": review_comments,
        "https://api.github.com/repos/acme/widgets/issues/7/comments": issue_comments,
    })
    client = GithubClient("tok", transport=transport)

    comments = client.fetch_pr_comments("acme/widgets", 7)

    kinds = {c.kind for c in comments}
    assert kinds == {"review_comment(diff)", "issue_comment(conversation)"}
    diff_comment = next(c for c in comments if c.kind == "review_comment(diff)")
    assert diff_comment.id == 101
    assert diff_comment.author == "alice"
    assert diff_comment.in_reply_to_id == 42
    assert diff_comment.code_snippet_snapshot == "def enabled():\n    return is_enabled"
    assert diff_comment.code_path_snapshot == "src/naming.py"
    issue_comment = next(c for c in comments if c.kind == "issue_comment(conversation)")
    assert issue_comment.code_snippet_snapshot is None
    assert issue_comment.code_path_snapshot is None


def test_fetch_pr_comments_uses_left_side_for_removed_code_and_rejects_malformed_hunks() -> None:
    review_comments = [
        {
            "id": 101,
            "user": {"login": "alice"},
            "body": "this is the violation",
            "html_url": "https://x/c1",
            "created_at": "2024-01-01T00:00:00Z",
            "path": "src/naming.py",
            "side": "LEFT",
            "diff_hunk": "@@ -8,3 +8,3 @@\n stable()\n-old_pattern()\n+new_pattern()",
        },
        {
            "id": 102,
            "user": {"login": "bob"},
            "body": "no reliable code context",
            "html_url": "https://x/c2",
            "created_at": "2024-01-02T00:00:00Z",
            "path": "src/other.py",
            "side": "RIGHT",
            "diff_hunk": "not a unified diff",
        },
    ]
    client = GithubClient(
        "tok",
        transport=_FakeTransport(
            {
                "https://api.github.com/repos/acme/widgets/pulls/7/comments": review_comments,
                "https://api.github.com/repos/acme/widgets/issues/7/comments": [],
            }
        ),
    )

    comments = client.fetch_pr_comments("acme/widgets", 7)

    assert comments[0].code_snippet_snapshot == "stable()\nold_pattern()"
    assert comments[0].code_path_snapshot == "src/naming.py"
    assert comments[1].code_snippet_snapshot is None
    assert comments[1].code_path_snapshot is None


def test_fetch_pr_comments_resolves_grounded_before_after_from_base_and_comment_commits() -> None:
    before_source = "package store\n\nfunc open() {\n\tlegacyCall()\n}\n"
    after_source = "package store\n\nfunc open() {\n\tsafeCall()\n}\n"
    review_comments = [
        {
            "id": 103,
            "user": {"login": "alice"},
            "body": "use the safe helper",
            "html_url": "https://x/c3",
            "created_at": "2024-01-03T00:00:00Z",
            "path": "pkg/store/open.go",
            "side": "RIGHT",
            "commit_id": "reviewed-sha",
            "original_line": 4,
            "line": 4,
            "diff_hunk": "@@ -3,3 +3,3 @@ func open() {\n func open() {\n-\tlegacyCall()\n+\tsafeCall()",
        }
    ]
    transport = _FakeTransport(
        {
            "https://api.github.com/repos/acme/widgets/pulls/7/comments": review_comments,
            "https://api.github.com/repos/acme/widgets/issues/7/comments": [],
            "https://api.github.com/repos/acme/widgets/pulls/7": {"base": {"sha": "base-sha"}},
            "https://api.github.com/repos/acme/widgets/contents/pkg/store/open.go?ref=base-sha": {
                "encoding": "base64",
                "content": base64.b64encode(before_source.encode()).decode(),
            },
            "https://api.github.com/repos/acme/widgets/contents/pkg/store/open.go?ref=reviewed-sha": {
                "encoding": "base64",
                "content": base64.b64encode(after_source.encode()).decode(),
            },
        }
    )

    comment = GithubClient("tok", transport=transport).fetch_pr_comments("acme/widgets", 7)[0]

    assert comment.code_before_snapshot == before_source.strip()
    assert comment.code_after_snapshot == after_source.strip()
    assert comment.code_snippet_snapshot == "func open() {\n\tsafeCall()"
    assert any(url.endswith("/pulls/7") for url in transport.urls)
    assert any("ref=base-sha" in url for url in transport.urls)
    assert any("ref=reviewed-sha" in url for url in transport.urls)


def test_fetch_pr_comments_falls_back_to_diff_when_commit_source_is_unavailable() -> None:
    review_comments = [
        {
            "id": 104,
            "user": {"login": "alice"},
            "body": "keep this grounded in the diff",
            "html_url": "https://x/c4",
            "created_at": "2024-01-04T00:00:00Z",
            "path": "src/widget.py",
            "side": "RIGHT",
            "commit_id": "missing-sha",
            "diff_hunk": "@@ -1 +1 @@\n-old_call()\n+new_call()",
        }
    ]
    transport = _FakeTransport(
        {
            "https://api.github.com/repos/acme/widgets/pulls/7/comments": review_comments,
            "https://api.github.com/repos/acme/widgets/issues/7/comments": [],
            "https://api.github.com/repos/acme/widgets/pulls/7": {"base": {"sha": "base-sha"}},
            "https://api.github.com/repos/acme/widgets/contents/src/widget.py?ref=base-sha": {
                "encoding": "none",
                "content": "unavailable",
            },
        }
    )

    comment = GithubClient("tok", transport=transport).fetch_pr_comments("acme/widgets", 7)[0]

    assert comment.code_before_snapshot is None
    assert comment.code_after_snapshot is None
    assert comment.code_snippet_snapshot == "new_call()"
    assert comment.code_path_snapshot == "src/widget.py"


def test_fetch_pr_reviews_excludes_pending_state() -> None:
    reviews = [
        {"id": 301, "user": {"login": "carol"}, "body": "we usually avoid this pattern", "html_url": "https://x/r1",
         "submitted_at": "2024-01-03T00:00:00Z", "state": "COMMENTED"},
        {"id": 302, "user": {"login": "dave"}, "body": "", "html_url": "https://x/r2", "submitted_at": None, "state": "PENDING"},
    ]
    transport = _FakeTransport({
        "https://api.github.com/repos/acme/widgets/pulls/7/reviews": reviews,
    })
    client = GithubClient("tok", transport=transport)

    result = client.fetch_pr_reviews("acme/widgets", 7)

    assert len(result) == 1
    assert result[0].author == "carol"
    assert result[0].state == "COMMENTED"


def test_pr_touches_path_checks_changed_file_prefixes() -> None:
    files = [{"filename": "pkg/store/inmemory.go"}, {"filename": "docs/README.md"}]
    transport = _FakeTransport({
        "https://api.github.com/repos/acme/widgets/pulls/7/files": files,
    })
    client = GithubClient("tok", transport=transport)

    assert client.pr_touches_path("acme/widgets", 7, "pkg/store/")
    assert not client.pr_touches_path("acme/widgets", 7, "pkg/query/")
