"""F6 Scheduled Incremental Convention Discovery — mine_new_evidence() (incremental mining) and
run_discovery() (the one application service both the scheduler and "Run now" call).

Same real-SQLite/FakeEmbedder/stub-LLM style as test_rule_mining_worker.py — mine_new_evidence()
reuses every primitive mine_rules() already uses, so these tests focus on what's actually new:
skip-already-processed, orphan reuse across runs, existing-family reinforcement, APPROVED
families frozen from auto-reinforcement, and run_discovery()'s job/watermark/overlap-lock
semantics.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from src.ai.providers.embeddings_fake import FakeEmbedder
from src.model.enums import (
    IngestionJobStatus,
    IngestionJobTriggerType,
    RuleFamilyStatus,
)
from src.model.ingestion_job import IngestionJob
from src.model.project import Project
from src.model.raw_pr_comment import RawPrComment
from src.model.rule_candidate import RuleCandidate
from src.model.rule_evidence import RuleEvidence
from src.model.rule_family import RuleFamily
from src.modules.knowledge.ingestion.github_client import GithubClient
from src.modules.knowledge.mining.convention_discovery import (
    AlreadyRunningError,
    _discovery_since,
    _safe_error_summary,
    run_discovery,
)
from src.modules.knowledge.mining.rule_mining_worker import mine_new_evidence

REPO = "acme/widgets"


@dataclass
class _StubResponse:
    content: str
    response_metadata: dict = field(default_factory=dict)
    usage_metadata: dict = field(default_factory=dict)


class _KeywordLLM:
    def __init__(self, rules: list[tuple[str, dict]]) -> None:
        self._rules = rules

    async def ainvoke(self, messages, config=None):
        user_content = messages[1][1]
        for keyword, payload in self._rules:
            if keyword in user_content:
                return _StubResponse(json.dumps(payload), response_metadata={"model_name": "stub"})
        raise AssertionError(f"no stub rule matched user content: {user_content!r} (unexpected re-extraction?)")


class _FailingKeywordLLM(_KeywordLLM):
    def __init__(self, rules: list[tuple[str, dict]], *, fail_keyword: str) -> None:
        super().__init__(rules)
        self._fail_keyword = fail_keyword

    async def ainvoke(self, messages, config=None):
        if self._fail_keyword in messages[1][1]:
            raise RuntimeError("provider timeout")
        return await super().ainvoke(messages)


def _row(comment_id: int, pr_number: int, author: str, body: str, *, created_at: datetime) -> RawPrComment:
    return RawPrComment(
        raw_pr_comment_id=comment_id,
        repo=REPO,
        pr_number=pr_number,
        pr_author="pr-author",
        type="review_comment(diff)",
        author=author,
        is_bot_comment=False,
        body=body,
        review_state=None,
        in_reply_to_id=None,
        url=f"https://x/{comment_id}",
        created_at=created_at,
        secret_scanned_at=datetime(2025, 8, 1),
    )


CONVENTION_PAYLOAD = {
    "evidence_type": "CONVENTION",
    "reuse_scope": 2,
    "rule_text_draft": "Avoid duplicated resource cleanup.",
    "rationale": "x",
}


# ============================================================== mine_new_evidence()


@pytest.mark.asyncio
async def test_already_processed_unit_is_never_re_extracted(db_session) -> None:
    processed = _row(1, 100, "alice", "avoid duplicated cleanup already processed here today in this particular module", created_at=datetime(2025, 8, 1))
    processed.mining_processed_at = datetime(2025, 8, 2)
    db_session.add(processed)
    db_session.add(_row(2, 200, "bob", "avoid duplicated cleanup brand new unit right now in this particular module", created_at=datetime(2025, 8, 3)))
    await db_session.commit()

    llm = _KeywordLLM([("brand new unit", CONVENTION_PAYLOAD)])
    summary = await mine_new_evidence(db_session, llm, FakeEmbedder(), repo=REPO)

    assert summary.evidence_units_total == 1  # only the unprocessed one


@pytest.mark.asyncio
async def test_rerun_with_no_new_data_is_a_no_op(db_session) -> None:
    db_session.add(_row(1, 100, "alice", "avoid duplicated cleanup rerun scenario here today in this particular module", created_at=datetime(2025, 8, 1)))
    await db_session.commit()
    llm = _KeywordLLM([("rerun scenario", CONVENTION_PAYLOAD)])

    first = await mine_new_evidence(db_session, llm, FakeEmbedder(), repo=REPO)
    assert first.evidence_units_total == 1

    # Second call: the LLM stub has no rule for a re-extraction of the same unit — if
    # mining_processed_at were not honored, this would raise AssertionError from the stub.
    second = await mine_new_evidence(db_session, llm, FakeEmbedder(), repo=REPO)
    assert second.evidence_units_total == 0
    assert second.evidence_units_eligible == 0

    candidates = (await db_session.scalars(select(RuleCandidate))).all()
    assert len(candidates) == 1  # not duplicated


@pytest.mark.asyncio
async def test_provider_failure_stays_retryable_across_runs(db_session) -> None:
    db_session.add(_row(1, 100, "alice", "avoid duplicated cleanup outage scenario here today in this particular module", created_at=datetime(2025, 8, 1)))
    await db_session.commit()

    failing_llm = _FailingKeywordLLM([], fail_keyword="outage scenario")
    first = await mine_new_evidence(db_session, failing_llm, FakeEmbedder(), repo=REPO)
    assert first.evidence_units_extraction_failed == ["review_comment(diff):1"]
    assert first.evidence_units_filtered_out == {}  # never silently counted as noise

    root = await db_session.get(RawPrComment, 1)
    assert root.mining_processed_at is None  # left unmarked so the next run retries it

    working_llm = _KeywordLLM([("outage scenario", CONVENTION_PAYLOAD)])
    second = await mine_new_evidence(db_session, working_llm, FakeEmbedder(), repo=REPO)
    assert second.evidence_units_total == 1
    assert second.evidence_units_eligible == 1
    await db_session.refresh(root)
    assert root.mining_processed_at is not None


@pytest.mark.asyncio
async def test_single_new_unit_with_no_partner_becomes_an_orphan_candidate(db_session) -> None:
    db_session.add(_row(1, 100, "alice", "avoid duplicated cleanup lonely unit here today in this particular module", created_at=datetime(2025, 8, 1)))
    await db_session.commit()
    llm = _KeywordLLM([("lonely unit", CONVENTION_PAYLOAD)])

    summary = await mine_new_evidence(db_session, llm, FakeEmbedder(), repo=REPO)

    assert summary.families_created == 0
    candidates = (await db_session.scalars(select(RuleCandidate))).all()
    assert len(candidates) == 1
    assert candidates[0].embedding is not None
    assert candidates[0].evidence_unit_id == "review_comment(diff):1"
    assert (await db_session.scalars(select(RuleEvidence))).all() == []


@pytest.mark.asyncio
async def test_orphan_candidate_is_reused_to_form_a_family_in_a_later_run(db_session) -> None:
    db_session.add(_row(1, 100, "alice", "avoid duplicated cleanup reuse scenario one here in this particular module", created_at=datetime(2025, 8, 1)))
    await db_session.commit()
    llm = _KeywordLLM([("reuse scenario one", CONVENTION_PAYLOAD)])
    first = await mine_new_evidence(db_session, llm, FakeEmbedder(), repo=REPO)
    assert first.families_created == 0
    orphan = (await db_session.scalars(select(RuleCandidate))).one()

    db_session.add(_row(2, 200, "bob", "avoid duplicated cleanup reuse scenario two here in this particular module", created_at=datetime(2025, 8, 2)))
    await db_session.commit()
    llm2 = _KeywordLLM([("reuse scenario two", CONVENTION_PAYLOAD)])  # identical rule_text_draft -> FakeEmbedder cosine=1.0

    second = await mine_new_evidence(db_session, llm2, FakeEmbedder(), repo=REPO)

    assert second.families_created == 1
    families = (await db_session.scalars(select(RuleFamily))).all()
    assert len(families) == 1
    evidences = (await db_session.scalars(select(RuleEvidence))).all()
    assert len(evidences) == 2
    assert {e.pr_number for e in evidences} == {100, 200}
    # The orphan's evidence row carries its ORIGINAL provenance, not re-derived.
    orphan_evidence = next(e for e in evidences if e.rule_candidate_id == orphan.rule_candidate_id)
    assert orphan_evidence.pr_number == 100
    assert orphan_evidence.original_author == "alice"


@pytest.mark.asyncio
async def test_new_evidence_reinforces_an_existing_pending_family_not_a_duplicate(db_session) -> None:
    db_session.add(_row(1, 100, "alice", "avoid duplicated cleanup family seed one here in this particular module", created_at=datetime(2025, 8, 1)))
    db_session.add(_row(2, 200, "bob", "avoid duplicated cleanup family seed two here in this particular module", created_at=datetime(2025, 8, 2)))
    await db_session.commit()
    llm = _KeywordLLM(
        [("family seed one", CONVENTION_PAYLOAD), ("family seed two", CONVENTION_PAYLOAD)]
    )
    first = await mine_new_evidence(db_session, llm, FakeEmbedder(), repo=REPO)
    assert first.families_created == 1
    family = (await db_session.scalars(select(RuleFamily))).one()

    db_session.add(_row(3, 300, "carol", "avoid duplicated cleanup family seed three here in this particular module", created_at=datetime(2025, 8, 3)))
    await db_session.commit()
    llm2 = _KeywordLLM([("family seed three", CONVENTION_PAYLOAD)])

    second = await mine_new_evidence(db_session, llm2, FakeEmbedder(), repo=REPO)

    assert second.families_created == 0
    assert second.families_reinforced == 1
    families = (await db_session.scalars(select(RuleFamily))).all()
    assert len(families) == 1  # not duplicated
    assert families[0].rule_family_id == family.rule_family_id
    assert families[0].distinct_reviewer_count == 3  # recomputed
    evidences = (await db_session.scalars(select(RuleEvidence).where(RuleEvidence.rule_family_id == family.rule_family_id))).all()
    assert len(evidences) == 3
    assert {e.pr_number for e in evidences} == {100, 200, 300}


@pytest.mark.asyncio
async def test_approved_family_is_never_auto_reinforced(db_session) -> None:
    db_session.add(_row(1, 100, "alice", "avoid duplicated cleanup approved seed one here in this particular module", created_at=datetime(2025, 8, 1)))
    db_session.add(_row(2, 200, "bob", "avoid duplicated cleanup approved seed two here in this particular module", created_at=datetime(2025, 8, 2)))
    await db_session.commit()
    llm = _KeywordLLM(
        [("approved seed one", CONVENTION_PAYLOAD), ("approved seed two", CONVENTION_PAYLOAD)]
    )
    first = await mine_new_evidence(db_session, llm, FakeEmbedder(), repo=REPO)
    assert first.families_created == 1
    family = (await db_session.scalars(select(RuleFamily))).one()
    family.status = RuleFamilyStatus.APPROVED
    family.approved_by = 1
    family.approved_at = datetime(2025, 8, 4)
    await db_session.commit()
    evidence_count_before = len(
        (await db_session.scalars(select(RuleEvidence).where(RuleEvidence.rule_family_id == family.rule_family_id))).all()
    )

    db_session.add(_row(3, 300, "carol", "avoid duplicated cleanup approved seed three here in this particular module", created_at=datetime(2025, 8, 5)))
    await db_session.commit()
    llm2 = _KeywordLLM([("approved seed three", CONVENTION_PAYLOAD)])

    second = await mine_new_evidence(db_session, llm2, FakeEmbedder(), repo=REPO)

    assert second.families_reinforced == 0
    assert second.families_created == 0  # lone new unit, no PENDING partner available -> orphan
    evidence_count_after = len(
        (await db_session.scalars(select(RuleEvidence).where(RuleEvidence.rule_family_id == family.rule_family_id))).all()
    )
    assert evidence_count_after == evidence_count_before  # approved family untouched


# ============================================================== run_discovery()


class _FakeTransport:
    def __init__(self, responses: dict[str, object]) -> None:
        self._responses = responses

    def __call__(self, url: str):
        for prefix, response in self._responses.items():
            if url.startswith(prefix):
                return response
        raise AssertionError(f"unexpected URL: {url}")


def _github_client(responses: dict[str, object]) -> GithubClient:
    # Every cold start now verifies the repository's actual creation time before
    # querying PR history. Append the broad repo prefix after specific endpoint
    # fixtures so the fake transport still resolves those paths first.
    responses = dict(responses)
    responses.setdefault(f"https://api.github.com/repos/{REPO}", {"created_at": "2020-01-01T00:00:00Z"})
    return GithubClient("tok", transport=_FakeTransport(responses))


def _one_pr_responses(pr_number: int, comment_id: int, body: str) -> dict[str, object]:
    return {
        "https://api.github.com/search/issues": {
            "items": [
                {"number": pr_number, "title": "t", "user": {"login": "alice"}, "html_url": f"https://x/{pr_number}"}
            ]
        },
        f"https://api.github.com/repos/{REPO}/pulls/{pr_number}/comments": [
            {
                "id": comment_id,
                "user": {"login": "alice"},
                "body": body,
                "html_url": f"https://x/c{comment_id}",
                "created_at": "2025-08-05T00:00:00Z",
                "in_reply_to_id": None,
            }
        ],
        f"https://api.github.com/repos/{REPO}/issues/{pr_number}/comments": [],
        f"https://api.github.com/repos/{REPO}/pulls/{pr_number}/reviews": [],
        # Keep this generic prefix last: _FakeTransport routes with startswith(), while
        # the PR endpoints above are more specific paths under the same repo prefix.
        f"https://api.github.com/repos/{REPO}": {"created_at": "2020-01-01T00:00:00Z"},
    }


async def _make_project(db_session, *, github_repo: str | None = REPO) -> Project:
    project = Project(
        key="DISC1",
        name="Discovery Project",
        created_by_admin_id=1,
        github_repo=github_repo,
        default_branch="main" if github_repo else None,
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


def test_cold_start_uses_lookback_for_an_old_repository_not_ralion_project_created_at() -> None:
    now = datetime(2026, 8, 28, 15, 10, 49)
    assert _discovery_since(
        watermark=None,
        repo_created_at=datetime(2014, 3, 4, 23, 20, 42),
        now=now,
        overlap_buffer=timedelta(days=3),
        cold_start_lookback=timedelta(days=365),
    ) == datetime(2025, 8, 28, 15, 10, 49)


def test_cold_start_uses_available_history_for_a_young_repository() -> None:
    repo_created_at = datetime(2026, 6, 1, 12, 0)
    assert _discovery_since(
        watermark=None,
        repo_created_at=repo_created_at,
        now=datetime(2026, 8, 28, 15, 10, 49),
        overlap_buffer=timedelta(days=3),
        cold_start_lookback=timedelta(days=365),
    ) == repo_created_at


def test_existing_watermark_still_wins_over_repository_creation_time() -> None:
    watermark = datetime(2026, 8, 20, 9, 0)
    assert _discovery_since(
        watermark=watermark,
        repo_created_at=None,
        now=datetime(2026, 8, 28, 15, 10, 49),
        overlap_buffer=timedelta(days=3),
        cold_start_lookback=timedelta(days=365),
    ) == datetime(2026, 8, 17, 9, 0)


@pytest.mark.asyncio
async def test_run_discovery_happy_path_advances_watermark_and_succeeds(db_session) -> None:
    project = await _make_project(db_session)
    llm = _KeywordLLM([("lonely convention", CONVENTION_PAYLOAD)])
    client = _github_client(_one_pr_responses(1, 10, "avoid duplicated cleanup lonely convention right here in this particular module"))

    job = await run_discovery(
        db_session,
        project.project_id,
        trigger_type=IngestionJobTriggerType.MANUAL,
        triggered_by_user_id=1,
        github_client=client,
        llm=llm,
        embedder=FakeEmbedder(),
    )

    assert job.status == IngestionJobStatus.SUCCEEDED
    assert job.new_raw_evidence_count == 1
    assert job.eligible_count == 1
    await db_session.refresh(project)
    assert project.discovery_pr_corpus_watermark_at is not None


@pytest.mark.asyncio
async def test_run_discovery_rerun_same_window_ingests_zero_new_rows(db_session) -> None:
    project = await _make_project(db_session)
    llm = _KeywordLLM([("idempotent convention", CONVENTION_PAYLOAD)])
    client = _github_client(_one_pr_responses(1, 10, "avoid duplicated cleanup idempotent convention right here in this particular module"))

    await run_discovery(
        db_session, project.project_id,
        trigger_type=IngestionJobTriggerType.MANUAL, triggered_by_user_id=1,
        github_client=client, llm=llm, embedder=FakeEmbedder(),
    )
    second_job = await run_discovery(
        db_session, project.project_id,
        trigger_type=IngestionJobTriggerType.MANUAL, triggered_by_user_id=1,
        github_client=client, llm=llm, embedder=FakeEmbedder(),
    )

    assert second_job.status == IngestionJobStatus.SUCCEEDED
    assert second_job.new_raw_evidence_count == 0  # ON CONFLICT DO NOTHING — not a duplicate
    rows = (await db_session.scalars(select(RawPrComment))).all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_run_discovery_rejects_a_second_concurrent_run_for_the_same_project(db_session) -> None:
    project = await _make_project(db_session)
    db_session.add(IngestionJob(project_id=project.project_id, job_type="RULE_MINING", trigger_type="MANUAL", status="RUNNING"))
    await db_session.commit()

    with pytest.raises(AlreadyRunningError):
        await run_discovery(
            db_session, project.project_id,
            trigger_type=IngestionJobTriggerType.MANUAL, triggered_by_user_id=1,
            github_client=_github_client({}), llm=_KeywordLLM([]), embedder=FakeEmbedder(),
        )


@pytest.mark.asyncio
async def test_run_discovery_ingestion_failure_leaves_watermark_untouched_and_job_failed(db_session) -> None:
    project = await _make_project(db_session)

    class _BrokenClient:
        def list_merged_prs(self, repo, since, until):
            raise RuntimeError("github api down")

    job = await run_discovery(
        db_session, project.project_id,
        trigger_type=IngestionJobTriggerType.SCHEDULED, triggered_by_user_id=None,
        github_client=_BrokenClient(), llm=_KeywordLLM([]), embedder=FakeEmbedder(),
    )

    assert job.status == IngestionJobStatus.FAILED
    assert job.error_summary is not None
    await db_session.refresh(project)
    assert project.discovery_pr_corpus_watermark_at is None


@pytest.mark.asyncio
async def test_run_discovery_without_a_github_repo_fails_cleanly(db_session) -> None:
    project = await _make_project(db_session, github_repo=None)

    job = await run_discovery(
        db_session, project.project_id,
        trigger_type=IngestionJobTriggerType.MANUAL, triggered_by_user_id=1,
        github_client=_github_client({}), llm=_KeywordLLM([]), embedder=FakeEmbedder(),
    )

    assert job.status == IngestionJobStatus.FAILED


# ============================================================== error_summary sanitization


class _FakeOrigError(Exception):
    """Stand-in for the DBAPI-level exception `IntegrityError.orig` wraps — short and free of
    the SQL/bind-parameter dump SQLAlchemy's own `StatementError.__str__` appends."""


def test_safe_error_summary_strips_sql_and_bound_parameters_from_a_statement_error() -> None:
    from sqlalchemy.exc import IntegrityError

    orig = _FakeOrigError(
        'duplicate key value violates unique constraint "uq_rule_evidences_evidence_unit_id"\n'
        "DETAIL:  Key (evidence_unit_id)=(review_comment(diff):681) already exists."
    )
    exc = IntegrityError(
        statement="INSERT INTO rule_evidences (...) VALUES (...)",
        params={"comment_snippet_snapshot": "a real reviewer's PR comment body, verbatim"},
        orig=orig,
    )

    summary = _safe_error_summary(exc)

    assert "IntegrityError" in summary
    assert "already exists" in summary  # operator-useful detail is kept
    assert "INSERT INTO" not in summary  # raw SQL is not
    assert "a real reviewer's PR comment body" not in summary  # bound params are not


def test_safe_error_summary_falls_back_to_str_for_a_non_statement_exception() -> None:
    summary = _safe_error_summary(ValueError("Project 5945 has no configured GitHub repository"))
    assert summary == "ValueError: Project 5945 has no configured GitHub repository"


@pytest.mark.asyncio
async def test_run_discovery_reproduces_the_evidence_collision_bug_without_leaking_sql(db_session) -> None:
    """End-to-end reproduction of the exact crash the manual E2E session hit against
    thanos-io/thanos: a repo whose evidence was already mined (here, seeded directly — the
    older mine_rules() left mining_processed_at unset) crashes mine_new_evidence() on
    uq_rule_evidences_evidence_unit_id if it isn't skipped. Confirms both halves of the fix:
    the run no longer crashes (job reaches a terminal status, not an unhandled exception out of
    run_discovery), and if it ever did fail, the recorded error would carry no raw SQL/PR body.
    """
    project = await _make_project(db_session)

    comment = _row(1, 100, "alice", "please avoid double negative boolean naming here, it makes the return value confusing", created_at=datetime(2025, 8, 1))
    db_session.add(comment)
    await db_session.flush()
    candidate = RuleCandidate(
        evidence_type="REUSABLE_CORRECTION", reuse_scope=2,
        rule_text_draft="Avoid double-negative boolean naming.", rationale="x",
        evidence_unit_id=f"review_comment(diff):{comment.raw_pr_comment_id}",
        pr_number=100, comment_snippet_snapshot=comment.body, original_author="alice",
        evidence_created_at=comment.created_at,
    )
    db_session.add(candidate)
    await db_session.flush()
    family = RuleFamily(distinct_reviewer_count=1)
    db_session.add(family)
    await db_session.flush()
    db_session.add(
        RuleEvidence(
            rule_candidate_id=candidate.rule_candidate_id, rule_family_id=family.rule_family_id,
            evidence_unit_id=candidate.evidence_unit_id, pr_number=100,
            comment_snippet_snapshot=comment.body, original_author="alice",
            evidence_created_at=comment.created_at, cluster_edge_cosine_similarity=None,
        )
    )
    await db_session.commit()
    assert comment.mining_processed_at is None  # the pre-fix legacy state

    responses = {
        "https://api.github.com/search/issues": {"items": []},  # no new PRs to ingest this run
    }
    job = await run_discovery(
        db_session, project.project_id,
        trigger_type=IngestionJobTriggerType.MANUAL, triggered_by_user_id=1,
        github_client=_github_client(responses),
        llm=_KeywordLLM([("double negative", CONVENTION_PAYLOAD)]),
        embedder=FakeEmbedder(),
    )

    assert job.status == IngestionJobStatus.SUCCEEDED
    assert job.error_summary is None
    evidences = (await db_session.scalars(select(RuleEvidence))).all()
    assert len(evidences) == 1  # unchanged — the legacy row was never re-inserted
