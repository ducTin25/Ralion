"""Small read-only GitHub REST adapter used by the F2 worker and the F6 PR corpus."""

from __future__ import annotations

import base64
import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from fnmatch import fnmatchcase
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class GithubFile:
    path: str


@dataclass(frozen=True)
class PrSummary:
    number: int
    title: str
    author: str
    html_url: str


@dataclass(frozen=True)
class PrComment:
    """One review-comment(diff) or issue-comment(conversation) row.

    ``id`` is GitHub's own id for this comment — stable and unique within its kind,
    the natural key a future evidence-snapshot consumer needs to identify this exact
    comment without re-fetching it.
    """

    id: int
    pr_number: int
    kind: str  # "review_comment(diff)" | "issue_comment(conversation)"
    author: str
    body: str
    html_url: str
    created_at: str
    in_reply_to_id: int | None = None
    # Provider-neutral, immutable display context derived from GitHub's diff_hunk.
    # Raw diff syntax deliberately stops at this integration boundary.
    code_snippet_snapshot: str | None = None
    code_path_snapshot: str | None = None
    # Clean source snapshots resolved from real PR commits. Both stay absent unless
    # GitHub can ground the complete pair; downstream then uses code_snippet_snapshot.
    code_before_snapshot: str | None = None
    code_after_snapshot: str | None = None


@dataclass(frozen=True)
class PrReview:
    """One submitted review — the third comment source (Open Question #4)."""

    id: int
    pr_number: int
    author: str
    body: str
    html_url: str
    submitted_at: str
    state: str


def _month_chunks(since: date, until: date):
    """Split [since, until] into calendar months.

    The Search API caps any single query at 1000 results; chunking by month keeps
    each query's result count far under that cap for realistic PR volumes.
    """
    cur = since
    while cur <= until:
        month_end = (cur.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        end = min(month_end, until)
        yield cur, end
        cur = end + timedelta(days=1)


class GithubClient:
    def __init__(
        self,
        token: str,
        *,
        timeout_seconds: float = 30.0,
        sleep: Callable[[float], None] = time.sleep,
        transport: Callable[[str], dict | list] | None = None,
    ) -> None:
        # A caller that injects its own transport (e.g. a caching/rate-limit-aware
        # one) owns authentication itself, so the token requirement only applies to
        # this client's own built-in transport.
        if not token and transport is None:
            raise ValueError("A GitHub token is required")
        self._token = token
        self._timeout_seconds = timeout_seconds
        self._sleep = sleep
        self._transport = transport
        self._tree_cache: dict[tuple[str, str], list[dict]] = {}
        self._file_content_cache: dict[tuple[str, str, str], str] = {}
        self._pr_base_sha_cache: dict[tuple[str, int], str] = {}
        self._repo_created_at_cache: dict[str, datetime] = {}

    def _fetch(self, endpoint: str) -> dict | list:
        url = f"https://api.github.com{endpoint}"
        if self._transport is not None:
            return self._transport(url)
        request = Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        for attempt, delay in enumerate((0.0, 1.0, 3.0, 9.0)):
            if delay:
                self._sleep(delay)
            try:
                with urlopen(request, timeout=self._timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                if exc.code not in {429, 500, 502, 503, 504} or attempt == 3:
                    raise RuntimeError(f"GitHub GET {endpoint} failed with HTTP {exc.code}") from exc
            except URLError as exc:
                if attempt == 3:
                    raise RuntimeError(f"GitHub GET {endpoint} failed") from exc
            except TimeoutError as exc:
                # A socket read can time out only after ``urlopen`` has successfully connected.
                # It is therefore not wrapped in URLError, but it is just as transient as the
                # connection failures above and must use the same bounded retry/backoff policy.
                if attempt == 3:
                    raise RuntimeError(f"GitHub GET {endpoint} timed out") from exc
        raise AssertionError("unreachable")

    def _get(self, endpoint: str) -> dict:
        payload = self._fetch(endpoint)
        if not isinstance(payload, dict):
            raise RuntimeError("GitHub returned an unexpected response")
        return payload

    def _paginate(self, endpoint: str, *, per_page: int = 100, max_pages: int = 20) -> list[dict]:
        results: list[dict] = []
        sep = "&" if "?" in endpoint else "?"
        for page in range(1, max_pages + 1):
            data = self._fetch(f"{endpoint}{sep}per_page={per_page}&page={page}")
            if not isinstance(data, list):
                raise RuntimeError(f"GitHub returned a non-list page for {endpoint}")
            if not data:
                break
            results.extend(data)
            if len(data) < per_page:
                break
        return results

    def get_branch_head_sha(self, repo: str, branch: str) -> str:
        payload = self._get(f"/repos/{repo}/git/ref/heads/{quote(branch, safe='')}")
        sha = payload.get("object", {}).get("sha")
        if not isinstance(sha, str) or not sha:
            raise RuntimeError(f"GitHub returned no branch head SHA for {repo}@{branch}")
        return sha

    def get_repository_created_at(self, repo: str) -> datetime:
        """Return the repository creation timestamp as a naive UTC datetime.

        Discovery uses this only for its first historical window: a Ralion project's
        creation time says nothing about how much GitHub history the repository has.
        """
        cached = self._repo_created_at_cache.get(repo)
        if cached is not None:
            return cached
        payload = self._get(f"/repos/{repo}")
        raw_created_at = payload.get("created_at")
        if not isinstance(raw_created_at, str) or not raw_created_at:
            raise RuntimeError(f"GitHub returned no creation timestamp for {repo}")
        try:
            created_at = datetime.fromisoformat(raw_created_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise RuntimeError(f"GitHub returned an invalid creation timestamp for {repo}") from exc
        if created_at.tzinfo is None:
            raise RuntimeError(f"GitHub returned a timezone-less creation timestamp for {repo}")
        normalized = created_at.astimezone(UTC).replace(tzinfo=None)
        self._repo_created_at_cache[repo] = normalized
        return normalized

    def list_files(self, repo: str, pattern: str, exclude: tuple[str, ...], *, ref: str) -> list[GithubFile]:
        cache_key = (repo, ref)
        tree = self._tree_cache.get(cache_key)
        if tree is None:
            payload = self._get(f"/repos/{repo}/git/trees/{quote(ref, safe='')}?recursive=1")
            tree = payload.get("tree")
            if payload.get("truncated") is True:
                raise RuntimeError(f"Git tree response for {repo} was truncated")
            if not isinstance(tree, list):
                raise RuntimeError(f"GitHub returned no file tree for {repo}")
            self._tree_cache[cache_key] = tree
        return [
            GithubFile(path=item["path"])
            for item in tree
            if item.get("type") == "blob"
            and isinstance(item.get("path"), str)
            and _matches_glob(item["path"], pattern)
            and not any(_matches_glob(item["path"], ignored) for ignored in exclude)
        ]

    def get_file_content(self, repo: str, path: str, *, ref: str) -> str:
        cache_key = (repo, path, ref)
        cached = self._file_content_cache.get(cache_key)
        if cached is not None:
            return cached
        payload = self._get(f"/repos/{repo}/contents/{quote(path, safe='/')}?ref={quote(ref, safe='')}")
        encoded = payload.get("content")
        encoding = payload.get("encoding")
        if not isinstance(encoded, str) or encoding != "base64":
            raise RuntimeError(f"GitHub returned unsupported content for {repo}:{path}")
        try:
            content = base64.b64decode(encoded).decode("utf-8")
        except (UnicodeDecodeError, ValueError) as exc:
            raise RuntimeError(f"GitHub file {repo}:{path} is not UTF-8 text") from exc
        self._file_content_cache[cache_key] = content
        return content

    def list_merged_prs(self, repo: str, since: date, until: date) -> list[PrSummary]:
        """Enumerate merged PRs in [since, until] via the Search API, chunked by month."""
        all_items: dict[int, PrSummary] = {}
        for start, end in _month_chunks(since, until):
            query = f"repo:{repo}+is:pr+is:merged+merged:{start.isoformat()}..{end.isoformat()}"
            for page in range(1, 11):  # 10*100 = 1000, the Search API's hard cap per query
                data = self._get(f"/search/issues?q={query}&per_page=100&page={page}")
                items = data.get("items", [])
                if not items:
                    break
                for item in items:
                    all_items[item["number"]] = PrSummary(
                        number=item["number"],
                        title=item["title"],
                        author=item["user"]["login"],
                        html_url=item["html_url"],
                    )
                if len(items) < 100:
                    break
        return list(all_items.values())

    def pr_touches_path(self, repo: str, number: int, path_prefix: str) -> bool:
        files = self._paginate(f"/repos/{repo}/pulls/{number}/files", max_pages=5)
        return any(f["filename"].startswith(path_prefix) for f in files)

    def fetch_pr_comments(self, repo: str, number: int) -> list[PrComment]:
        """Review comments (pinned to a diff line) + issue comments (conversation-level)."""
        review_comments = self._paginate(f"/repos/{repo}/pulls/{number}/comments", max_pages=5)
        issue_comments = self._paginate(f"/repos/{repo}/issues/{number}/comments", max_pages=5)
        comments: list[PrComment] = []
        for c in review_comments:
            snippet = _normalize_diff_hunk(c.get("diff_hunk"), c.get("side"))
            path = c.get("path") if isinstance(c.get("path"), str) else None
            before, after = self._fetch_review_source_context(repo, number, c)
            comments.append(
                PrComment(
                    id=c["id"],
                    pr_number=number,
                    kind="review_comment(diff)",
                    author=c["user"]["login"],
                    body=c["body"] or "",
                    html_url=c["html_url"],
                    created_at=c["created_at"],
                    in_reply_to_id=c.get("in_reply_to_id"),
                    code_snippet_snapshot=snippet,
                    code_path_snapshot=path if snippet is not None or before is not None else None,
                    code_before_snapshot=before,
                    code_after_snapshot=after,
                )
            )
        comments.extend(
            PrComment(
                id=c["id"],
                pr_number=number,
                kind="issue_comment(conversation)",
                author=c["user"]["login"],
                body=c["body"] or "",
                html_url=c["html_url"],
                created_at=c["created_at"],
            )
            for c in issue_comments
        )
        return comments

    def _fetch_review_source_context(
        self, repo: str, number: int, comment: dict
    ) -> tuple[str | None, str | None]:
        """Resolve a clean before/after pair from immutable GitHub commit content.

        A partial pair is intentionally discarded: the normalized diff hunk remains the
        trustworthy fallback and no downstream layer has to reason about GitHub failures.
        """
        path = comment.get("path")
        commit_sha = comment.get("commit_id")
        ranges = _parse_diff_hunk_ranges(comment.get("diff_hunk"))
        if not isinstance(path, str) or not isinstance(commit_sha, str) or ranges is None:
            return None, None

        old_start, old_count, new_start, new_count = ranges
        if old_count < 1 or new_count < 1:
            return None, None
        try:
            cache_key = (repo, number)
            base_sha = self._pr_base_sha_cache.get(cache_key)
            if base_sha is None:
                payload = self._get(f"/repos/{repo}/pulls/{number}")
                base_sha = payload.get("base", {}).get("sha")
                if not isinstance(base_sha, str) or not base_sha:
                    raise RuntimeError(f"GitHub returned no base SHA for {repo}#{number}")
                self._pr_base_sha_cache[cache_key] = base_sha

            before_source = self.get_file_content(repo, path, ref=base_sha)
            after_source = self.get_file_content(repo, path, ref=commit_sha)
            before = _slice_source_context(
                before_source, old_start, old_count, focus=comment.get("original_line")
            )
            after = _slice_source_context(
                after_source, new_start, new_count, focus=comment.get("line")
            )
            if before is None or after is None:
                return None, None
            return before, after
        except RuntimeError:
            # Source endpoints may fail for renamed/binary/deleted files or expired commits.
            # A review comment remains valid evidence through its persisted diff snapshot.
            return None, None

    def fetch_pr_reviews(self, repo: str, number: int) -> list[PrReview]:
        """The third comment source: a review's summary body (not a diff/issue comment).

        This is typically where convention-style feedback ("we usually...", "please
        follow...") appears. PENDING reviews are excluded — they aren't submitted, so
        they have no publicly visible content yet.
        """
        reviews = self._paginate(f"/repos/{repo}/pulls/{number}/reviews", max_pages=5)
        return [
            PrReview(
                id=r["id"],
                pr_number=number,
                author=r["user"]["login"],
                body=r["body"] or "",
                html_url=r["html_url"],
                submitted_at=r.get("submitted_at") or "",
                state=r.get("state", ""),
            )
            for r in reviews
            if r.get("state") != "PENDING"
        ]


def _matches_glob(path: str, pattern: str) -> bool:
    """Match GitHub paths with globstar accepting zero or more directories."""
    return fnmatchcase(path, pattern) or ("**/" in pattern and fnmatchcase(path, pattern.replace("**/", "")))


def _normalize_diff_hunk(diff_hunk: object, side: object) -> str | None:
    """Return plain source context for the side of the diff the review comment targets.

    GitHub's unified-diff markers are provider details. Keeping only context plus the
    selected side's changed lines gives downstream layers renderable code without teaching
    them GitHub diff semantics. Unusable hunks stay absent rather than being guessed.
    """
    if not isinstance(diff_hunk, str) or not diff_hunk or side not in {"LEFT", "RIGHT"}:
        return None

    selected_prefix = "-" if side == "LEFT" else "+"
    opposite_prefix = "+" if side == "LEFT" else "-"
    code_lines: list[str] = []
    for line in diff_hunk.splitlines():
        if line.startswith("@@") or line == r"\ No newline at end of file":
            continue
        if line.startswith(opposite_prefix):
            continue
        if line.startswith((" ", selected_prefix)):
            code_lines.append(line[1:])
            continue
        # A malformed/non-unified hunk is not reliable provenance.
        return None

    if not any(line.strip() for line in code_lines):
        return None
    return "\n".join(code_lines).strip("\n")


_DIFF_HUNK_HEADER = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@"
)


def _parse_diff_hunk_ranges(diff_hunk: object) -> tuple[int, int, int, int] | None:
    if not isinstance(diff_hunk, str):
        return None
    header = diff_hunk.splitlines()[0] if diff_hunk else ""
    match = _DIFF_HUNK_HEADER.match(header)
    if match is None:
        return None
    return (
        int(match.group("old_start")),
        int(match.group("old_count") or 1),
        int(match.group("new_start")),
        int(match.group("new_count") or 1),
    )


def _slice_source_context(
    source: str,
    start_line: int,
    changed_line_count: int,
    *,
    focus: object,
    margin: int = 3,
    max_lines: int = 40,
) -> str | None:
    """Take a bounded, line-number-free source window around the real changed region."""
    lines = source.splitlines()
    if not lines or start_line < 1 or start_line > len(lines):
        return None

    region_start = max(1, start_line - margin)
    region_end = min(len(lines), start_line + changed_line_count - 1 + margin)
    if region_end - region_start + 1 > max_lines:
        focus_line = focus if isinstance(focus, int) and focus > 0 else start_line
        focus_line = min(max(focus_line, region_start), region_end)
        half = max_lines // 2
        region_start = max(region_start, focus_line - half)
        region_end = min(region_end, region_start + max_lines - 1)
        region_start = max(1, region_end - max_lines + 1)

    snippet = "\n".join(lines[region_start - 1 : region_end])
    return snippet if snippet.strip() else None
