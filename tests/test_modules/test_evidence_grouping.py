from __future__ import annotations

from datetime import datetime

from src.model.raw_pr_comment import RawPrComment
from src.modules.knowledge.mining.evidence_grouping import group_comments_into_evidence_units


def _row(
    comment_id: int,
    pr_number: int,
    kind: str,
    *,
    author: str = "alice",
    body: str = "some review comment body here",
    in_reply_to_id: int | None = None,
) -> RawPrComment:
    return RawPrComment(
        raw_pr_comment_id=comment_id,
        repo="acme/widgets",
        pr_number=pr_number,
        pr_author="pr-author",
        type=kind,
        author=author,
        is_bot_comment=False,
        body=body,
        review_state=None,
        in_reply_to_id=in_reply_to_id,
        url=f"https://x/{comment_id}",
        created_at=datetime(2025, 8, 1, 0, 0, comment_id % 60),
        secret_scanned_at=datetime(2025, 8, 1),
    )


def test_review_comment_chain_merges_into_one_unit() -> None:
    root = _row(1, 100, "review_comment(diff)", body="root comment")
    reply = _row(2, 100, "review_comment(diff)", body="reply comment", in_reply_to_id=1)
    transitive_reply = _row(3, 100, "review_comment(diff)", body="transitive reply", in_reply_to_id=2)

    units = group_comments_into_evidence_units([root, reply, transitive_reply])

    assert len(units) == 1
    assert [c.raw_pr_comment_id for c in units[0].comments] == [1, 2, 3]


def test_unrelated_review_comments_in_same_pr_are_separate_units() -> None:
    a = _row(1, 100, "review_comment(diff)", body="topic A")
    b = _row(2, 100, "review_comment(diff)", body="topic B")

    units = group_comments_into_evidence_units([a, b])

    assert len(units) == 2
    assert {u.comments[0].raw_pr_comment_id for u in units} == {1, 2}


def test_reply_to_filtered_out_parent_starts_a_new_unit() -> None:
    # Parent (id=1) was excluded upstream (noise/bot) — only the reply is passed in here.
    orphaned_reply = _row(2, 100, "review_comment(diff)", body="orphaned reply", in_reply_to_id=1)

    units = group_comments_into_evidence_units([orphaned_reply])

    assert len(units) == 1
    assert units[0].comments == (orphaned_reply,)


def test_review_summary_rows_are_always_their_own_unit() -> None:
    a = _row(1, 100, "review(summary)", body="we usually avoid this pattern")
    b = _row(2, 100, "review(summary)", body="please follow the style guide")

    units = group_comments_into_evidence_units([a, b])

    assert len(units) == 2


def test_issue_comment_rows_are_each_their_own_unit() -> None:
    a = _row(1, 100, "issue_comment(conversation)", body="first remark")
    b = _row(2, 100, "issue_comment(conversation)", body="second remark")

    units = group_comments_into_evidence_units([a, b])

    assert len(units) == 2
    assert all(len(u.comments) == 1 for u in units)


def test_units_are_scoped_per_pr() -> None:
    a = _row(1, 100, "review_comment(diff)", body="pr 100 root")
    b = _row(2, 200, "review_comment(diff)", body="pr 200 root", in_reply_to_id=1)

    units = group_comments_into_evidence_units([a, b])

    # in_reply_to_id=1 must not leak across PRs even though the id exists in another PR.
    assert len(units) == 2
    assert {u.pr_number for u in units} == {100, 200}


def test_evidence_unit_id_format() -> None:
    row = _row(42, 100, "review_comment(diff)")
    units = group_comments_into_evidence_units([row])
    assert units[0].evidence_unit_id == "review_comment(diff):42"


def test_distinct_authors() -> None:
    a = _row(1, 100, "review_comment(diff)", author="alice", body="root")
    b = _row(2, 100, "review_comment(diff)", author="bob", body="reply", in_reply_to_id=1)
    units = group_comments_into_evidence_units([a, b])
    assert units[0].distinct_authors == frozenset({"alice", "bob"})
