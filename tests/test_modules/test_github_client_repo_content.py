"""Regression coverage for GithubClient's pre-existing dict-shaped endpoints.

These existed before F6 prep touched ``_get``/``_fetch`` (split to support the new
list-shaped PR/review/comment endpoints) but had no test coverage at all. Added
here as a safety net for that refactor, not as new F6 scope.
"""

from __future__ import annotations

import base64

import pytest

from src.modules.knowledge.ingestion.github_client import GithubClient


class _FakeTransport:
    def __init__(self, responses: dict[str, object]) -> None:
        self._responses = responses

    def __call__(self, url: str):
        for prefix, response in self._responses.items():
            if url.startswith(prefix):
                return response
        raise AssertionError(f"unexpected URL: {url}")


def test_get_branch_head_sha() -> None:
    transport = _FakeTransport({
        "https://api.github.com/repos/acme/widgets/git/ref/heads/main": {"object": {"sha": "abc123"}},
    })
    client = GithubClient("tok", transport=transport)

    assert client.get_branch_head_sha("acme/widgets", "main") == "abc123"


def test_get_file_content_decodes_base64() -> None:
    encoded = base64.b64encode(b"hello world").decode("ascii")
    transport = _FakeTransport({
        "https://api.github.com/repos/acme/widgets/contents/README.md": {
            "content": encoded, "encoding": "base64",
        },
    })
    client = GithubClient("tok", transport=transport)

    assert client.get_file_content("acme/widgets", "README.md", ref="abc123") == "hello world"


def test_list_files_filters_by_glob_and_exclude() -> None:
    tree = {
        "truncated": False,
        "tree": [
            {"type": "blob", "path": "docs/a.md"},
            {"type": "blob", "path": "docs/skip/b.md"},
            {"type": "tree", "path": "docs/dir"},
            {"type": "blob", "path": "src/main.py"},
        ],
    }
    transport = _FakeTransport({
        "https://api.github.com/repos/acme/widgets/git/trees/abc123": tree,
    })
    client = GithubClient("tok", transport=transport)

    files = client.list_files("acme/widgets", "docs/**", ("docs/skip/**",), ref="abc123")

    assert [f.path for f in files] == ["docs/a.md"]


def test_get_raises_on_non_dict_payload() -> None:
    transport = _FakeTransport({
        "https://api.github.com/repos/acme/widgets/git/ref/heads/main": ["not", "a", "dict"],
    })
    client = GithubClient("tok", transport=transport)

    with pytest.raises(RuntimeError):
        client.get_branch_head_sha("acme/widgets", "main")
