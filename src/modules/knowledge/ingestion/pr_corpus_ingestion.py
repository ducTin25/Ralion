"""F2 Sub-flow B — PR/comment corpus ingestion for F6 rule mining.

Pulls review comments, issue comments, and review summaries for every non-bot
merged PR in a fixed [since, until] window on one repo, secret-scans each body
before persisting, and writes into raw_pr_comments — full body, never truncated.

Idempotent via `github_id`: each row is inserted with
`ON CONFLICT (repo, type, github_id) DO NOTHING` against
`uq_raw_pr_comments_repo_type_github_id`, so calling this repeatedly over an
overlapping/rerun [since, until] window (F6 Scheduled Incremental Convention
Discovery) never duplicates a row — the DB constraint is the dedup source of
truth, not the caller's window bookkeeping.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security.secret_scan import record_secret_findings
from src.core.security.secret_scan import scan as secret_scan_and_redact
from src.model.raw_pr_comment import RawPrComment
from src.modules.knowledge.ingestion.github_client import GithubClient, PrComment, PrReview
from src.modules.knowledge.ingestion.pr_corpus_filters import is_bot

_SECRET_SCAN_BOUNDARY = "f6_pr_corpus_ingestion"


@dataclass
class IngestSummary:
    repo: str
    prs_total: int = 0
    prs_bot_excluded: int = 0
    prs_ingested: int = 0
    rows_by_type: dict[str, int] = field(default_factory=dict)
    rows_inserted: int = 0
    secret_findings: int = 0


def _parse_github_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC).replace(tzinfo=None)


def _insert(session: AsyncSession):
    """Dialect-aware ON CONFLICT builder — production runs on Postgres, tests run on
    the in-memory SQLite engine (tests/conftest.py::db_session); both dialects support
    `.on_conflict_do_nothing(index_elements=...)`, just from different modules.
    """
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        return postgresql.insert(RawPrComment)
    if dialect == "sqlite":
        return sqlite.insert(RawPrComment)
    raise NotImplementedError(f"unsupported dialect for idempotent PR-corpus insert: {dialect}")


def _row_from_comment(repo: str, pr_author: str, item: PrComment) -> RawPrComment:
    return RawPrComment(
        repo=repo,
        github_id=item.id,
        pr_number=item.pr_number,
        pr_author=pr_author,
        type=item.kind,
        author=item.author,
        is_bot_comment=is_bot(item.author),
        body=item.body,
        code_snippet_snapshot=item.code_snippet_snapshot,
        code_path_snapshot=item.code_path_snapshot,
        code_before_snapshot=item.code_before_snapshot,
        code_after_snapshot=item.code_after_snapshot,
        review_state=None,
        in_reply_to_id=item.in_reply_to_id,
        url=item.html_url,
        created_at=_parse_github_timestamp(item.created_at),
    )


def _row_from_review(repo: str, pr_author: str, item: PrReview) -> RawPrComment:
    return RawPrComment(
        repo=repo,
        github_id=item.id,
        pr_number=item.pr_number,
        pr_author=pr_author,
        type="review(summary)",
        author=item.author,
        is_bot_comment=is_bot(item.author),
        body=item.body,
        review_state=item.state,
        in_reply_to_id=None,
        url=item.html_url,
        created_at=_parse_github_timestamp(item.submitted_at),
    )


async def ingest_pr_corpus(
    session: AsyncSession,
    client: GithubClient,
    *,
    repo: str,
    since: date,
    until: date,
) -> IngestSummary:
    """One full pull. PR-level bot exclusion mirrors density_check.py / the annotated
    ground truth (F6_RULE_MINING_SPEC.md §4.5: F2 targets ``population_human_prs``,
    not the full merged-PR count) — bot-authored PRs never get their comments fetched.
    """
    summary = IngestSummary(repo=repo)
    # GithubClient intentionally uses urllib and blocking retry sleeps. Run it off the asyncio
    # event loop; otherwise a background scan stalls every unrelated HTTP request in this worker.
    prs = await asyncio.to_thread(client.list_merged_prs, repo, since, until)
    summary.prs_total = len(prs)

    for pr in prs:
        if is_bot(pr.author):
            summary.prs_bot_excluded += 1
            continue

        comments = await asyncio.to_thread(client.fetch_pr_comments, repo, pr.number)
        reviews = await asyncio.to_thread(client.fetch_pr_reviews, repo, pr.number)
        rows = [
            *(_row_from_comment(repo, pr.author, c) for c in comments),
            *(_row_from_review(repo, pr.author, r) for r in reviews),
        ]
        for row in rows:
            # secret_scan_and_redact() takes/returns a plain string — the PR-corpus
            # shape (body/author/pr_number/created_at/type) needs no adapter, it just
            # feeds `row.body` in directly (confirmed in the Phase 0 audit).
            redaction = secret_scan_and_redact(row.body)
            row.body = redaction.redacted_content
            record_secret_findings(redaction, boundary=_SECRET_SCAN_BOUNDARY, document_reference=row.url)
            if redaction.has_findings:
                summary.secret_findings += len(redaction.findings)

            for field_name in (
                "code_snippet_snapshot",
                "code_before_snapshot",
                "code_after_snapshot",
            ):
                code = getattr(row, field_name)
                if code is None:
                    continue
                code_redaction = secret_scan_and_redact(code)
                setattr(row, field_name, code_redaction.redacted_content)
                record_secret_findings(
                    code_redaction,
                    boundary=_SECRET_SCAN_BOUNDARY,
                    document_reference=row.url,
                )
                if code_redaction.has_findings:
                    summary.secret_findings += len(code_redaction.findings)

            # This marker covers every persisted content field above, not only the comment body.
            row.secret_scanned_at = datetime.now(UTC).replace(tzinfo=None)

            stmt = (
                _insert(session)
                .values(
                    repo=row.repo,
                    github_id=row.github_id,
                    pr_number=row.pr_number,
                    pr_author=row.pr_author,
                    type=row.type,
                    author=row.author,
                    is_bot_comment=row.is_bot_comment,
                    body=row.body,
                    code_snippet_snapshot=row.code_snippet_snapshot,
                    code_path_snapshot=row.code_path_snapshot,
                    code_before_snapshot=row.code_before_snapshot,
                    code_after_snapshot=row.code_after_snapshot,
                    review_state=row.review_state,
                    in_reply_to_id=row.in_reply_to_id,
                    url=row.url,
                    created_at=row.created_at,
                    secret_scanned_at=row.secret_scanned_at,
                )
                .on_conflict_do_nothing(index_elements=["repo", "type", "github_id"])
                .returning(RawPrComment.raw_pr_comment_id)
            )
            result = await session.execute(stmt)
            if result.first() is not None:
                summary.rows_by_type[row.type] = summary.rows_by_type.get(row.type, 0) + 1
                summary.rows_inserted += 1

        summary.prs_ingested += 1
        await session.commit()

    return summary
