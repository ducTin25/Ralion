"""Group filtered `raw_pr_comments` rows into evidence units (F6_RULE_MINING_SPEC.md §4.2
step 3's input unit — one LLM call per evidence unit, never per raw comment row).

Heuristic used (documented per CLAUDE.md Phase 5 §2 instruction — do not silently treat
every comment row as its own unit):

- `review(summary)` rows never carry `in_reply_to_id` from GitHub's API and are always a
  standalone PR-level remark (annotation_guide.md mục 2) — each row is its own unit.
- `review_comment(diff)` rows are chained via `in_reply_to_id`: a row replying (directly or
  transitively) to another row in the same PR joins that row's unit; a row whose parent was
  filtered out upstream (noise/bot) or has no `in_reply_to_id` starts a new unit. This mirrors
  annotation_guide.md mục 2's mechanical hint, applied automatically instead of by a human
  reader — still an approximation ("2 người có thể reply lạc đề trong cùng thread" is a risk
  annotation_guide.md itself calls out even for a human; automatic grouping cannot resolve
  topic drift within one reply chain).
- `issue_comment(conversation)` rows carry no reply-chain field at all from GitHub's API
  (confirmed in `GithubClient.fetch_pr_comments` — only review comments get `in_reply_to_id`).
  There is no mechanical signal available to group these without an extra API call or an LLM
  judgment call, both out of scope for this phase. Each row is treated as its own unit — a
  known simplification, not an oversight; a future phase could improve this with an LLM-based
  thread reconstruction pass if measurement shows it matters.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from src.model.raw_pr_comment import RawPrComment


@dataclass(frozen=True)
class EvidenceUnit:
    pr_number: int
    comments: tuple[RawPrComment, ...]  # chronological order

    @property
    def evidence_unit_id(self) -> str:
        # Business key format per RuleEvidence.evidence_unit_id's docstring example
        # ("review_comment(diff):<github id>") — anchored on the earliest/root member.
        root = self.comments[0]
        return f"{root.type}:{root.raw_pr_comment_id}"

    @property
    def distinct_authors(self) -> frozenset[str]:
        return frozenset(c.author for c in self.comments)

    @property
    def bodies(self) -> tuple[str, ...]:
        return tuple(c.body for c in self.comments)


def group_comments_into_evidence_units(comments: Sequence[RawPrComment]) -> list[EvidenceUnit]:
    """comments must already be filtered (noise/bot excluded, secret-scanned) — this function
    only groups, it does not filter."""
    by_pr: dict[int, list[RawPrComment]] = defaultdict(list)
    for comment in comments:
        by_pr[comment.pr_number].append(comment)

    units: list[EvidenceUnit] = []
    for pr_number, pr_comments in by_pr.items():
        review_comments = [c for c in pr_comments if c.type == "review_comment(diff)"]
        by_id = {c.raw_pr_comment_id: c for c in review_comments}

        def root_id_of(comment: RawPrComment) -> int:
            seen: set[int] = set()
            current = comment
            while (
                current.in_reply_to_id is not None
                and current.in_reply_to_id in by_id
                and current.raw_pr_comment_id not in seen
            ):
                seen.add(current.raw_pr_comment_id)
                current = by_id[current.in_reply_to_id]
            return current.raw_pr_comment_id

        chains: dict[int, list[RawPrComment]] = defaultdict(list)
        for comment in review_comments:
            chains[root_id_of(comment)].append(comment)
        for members in chains.values():
            units.append(
                EvidenceUnit(pr_number=pr_number, comments=tuple(sorted(members, key=lambda m: m.created_at)))
            )

        for comment in pr_comments:
            if comment.type in ("review(summary)", "issue_comment(conversation)"):
                units.append(EvidenceUnit(pr_number=pr_number, comments=(comment,)))

    return units
