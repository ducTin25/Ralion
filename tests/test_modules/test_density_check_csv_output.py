"""density_check.py must not truncate comment/review bodies when writing the CSV.

F6_RULE_MINING_SPEC.md §1.1: the CSV writer used to hard-cut ``body`` at 500 chars,
losing data at the point of persistence. This pins the fix.
"""

from __future__ import annotations

import csv
import importlib.util
import re
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "density_check.py"


def _load_density_check():
    spec = importlib.util.spec_from_file_location("density_check_under_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_csv_body_column_is_not_truncated(tmp_path, monkeypatch) -> None:
    dc = _load_density_check()

    long_body = "This sentence keeps going and going. " * 20
    assert len(long_body) > 500

    fake_prs = {
        "items": [
            {"number": 1, "title": "Fix bug", "user": {"login": "alice"}, "html_url": "https://x/1"},
        ]
    }
    review_comments = [
        {
            "id": 1, "user": {"login": "alice"}, "body": long_body,
            "html_url": "https://x/1#c1", "created_at": "2024-01-01T00:00:00Z",
            "in_reply_to_id": None,
        },
    ]

    def fake_gh_get(url, token, use_cache=True):
        if "/search/issues" in url:
            return fake_prs
        if "/repos/acme/widgets/pulls/1/comments" in url:
            return review_comments if "page=1" in url else []
        if "/repos/acme/widgets/issues/1/comments" in url:
            return []
        if "/repos/acme/widgets/pulls/1/reviews" in url:
            return []
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(dc, "gh_get", fake_gh_get)
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "density_check.py", "--repo", "acme/widgets", "--since", "2024-01-01",
            "--until", "2024-01-31", "--sample-size", "5", "--out", "out",
        ],
    )

    dc.main()

    with open(tmp_path / "out_comments_sample.csv", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 1
    expected_body = re.sub(r"\s+", " ", long_body).strip()
    assert len(expected_body) > 500
    assert rows[0]["body"] == expected_body
