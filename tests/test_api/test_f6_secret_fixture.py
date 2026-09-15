"""F6 Phase 8 (F6_RULE_MINING_PLAN.md §6 / CLAUDE.md Phase 8) — secret fixture, 2 independent
defense layers per the task:

1. Ingestion (F2 Phase 3): a secret in a PR comment body must be redacted BEFORE the row is
   persisted into `raw_pr_comments`. Already has coverage for the AWS-key format in
   `tests/test_modules/test_pr_corpus_ingestion.py`; this file adds 2 more formats the same
   `detect-secrets` plugin set (`src/core/security/secret_scan.py::_PLUGIN_NAMES`) is
   configured to catch — a GitHub token (line-based) and a PEM private-key block (its own,
   separate code path: `_redact_private_key_blocks`) — so the layer isn't only proven against
   one plugin.

2. Review Queue display (Phase 6): even if a secret slipped through layer 1 for some reason,
   the `/rule-candidates/pending` and `/conventions` endpoints must not return it verbatim in
   `comment_snippet_snapshot`. This is a genuinely separate assertion from layer 1 — it must
   hold even assuming layer 1 already failed, which is why the fixture below constructs the
   leaked-secret state directly in the DB rather than by exercising ingestion.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import select

from src.ai.providers.embeddings_fake import FakeEmbedder
from src.api.dependencies import get_current_user, get_embedder
from src.core.security.secret_scan import REDACTION_PLACEHOLDER
from src.main import app
from src.model.enums import RuleEvidenceType, RuleFamilyStatus, UserRole, UserStatus
from src.model.project import Project
from src.model.raw_pr_comment import RawPrComment
from src.model.rule_candidate import RuleCandidate
from src.model.rule_evidence import RuleEvidence
from src.model.rule_family import RuleFamily
from src.model.user import User
from src.modules.knowledge.ingestion.github_client import GithubClient
from src.modules.knowledge.ingestion.pr_corpus_ingestion import ingest_pr_corpus

API = "/api/v1"
REPO = "acme/widgets"

# Distinct formats/detectors from the AKIA case already covered in test_pr_corpus_ingestion.py
# — proves redaction is not accidentally keyed to one specific plugin.
GITHUB_TOKEN_SECRET = "ghp_16C7e42F292c6912E7710c838347Ae178B4a"
PRIVATE_KEY_BLOCK = (
    "-----BEGIN RSA PRIVATE KEY-----\n"
    "MIIBOgIBAAJBAKj34GkxFhD91aFTAO3sHnbsn9GnJhZ2NcpMr8sTbXzJXjXjXjXj\n"
    "-----END RSA PRIVATE KEY-----"
)


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


# --------------------------------------------------------------- Layer 1: ingestion redaction


@pytest.mark.asyncio
async def test_github_token_is_redacted_before_persist(db_session) -> None:
    body = f"please rotate this token right away: {GITHUB_TOKEN_SECRET}"
    responses = {
        "https://api.github.com/search/issues": {
            "items": [{"number": 10, "title": "x", "user": {"login": "alice"}, "html_url": "https://x/10"}]
        },
        "https://api.github.com/repos/acme/widgets/pulls/10/comments": [
            {"id": 1, "user": {"login": "alice"}, "body": body, "html_url": "https://x/c1",
             "created_at": "2025-08-05T00:00:00Z", "in_reply_to_id": None},
        ],
        "https://api.github.com/repos/acme/widgets/issues/10/comments": [],
        "https://api.github.com/repos/acme/widgets/pulls/10/reviews": [],
    }

    summary = await ingest_pr_corpus(
        db_session, _client(responses), repo=REPO, since=date(2025, 8, 1), until=date(2025, 8, 31)
    )

    assert summary.secret_findings >= 1
    row = (await db_session.scalars(select(RawPrComment))).one()
    assert GITHUB_TOKEN_SECRET not in row.body
    assert REDACTION_PLACEHOLDER in row.body
    assert row.secret_scanned_at is not None


@pytest.mark.asyncio
async def test_private_key_block_is_redacted_before_persist(db_session) -> None:
    body = f"found this checked in by mistake:\n\n{PRIVATE_KEY_BLOCK}\n\nplease rotate it."
    responses = {
        "https://api.github.com/search/issues": {
            "items": [{"number": 11, "title": "x", "user": {"login": "alice"}, "html_url": "https://x/11"}]
        },
        "https://api.github.com/repos/acme/widgets/pulls/11/comments": [
            {"id": 1, "user": {"login": "alice"}, "body": body, "html_url": "https://x/c1",
             "created_at": "2025-08-05T00:00:00Z", "in_reply_to_id": None},
        ],
        "https://api.github.com/repos/acme/widgets/issues/11/comments": [],
        "https://api.github.com/repos/acme/widgets/pulls/11/reviews": [],
    }

    summary = await ingest_pr_corpus(
        db_session, _client(responses), repo=REPO, since=date(2025, 8, 1), until=date(2025, 8, 31)
    )

    assert summary.secret_findings >= 1
    row = (await db_session.scalars(select(RawPrComment))).one()
    assert "BEGIN RSA PRIVATE KEY" not in row.body
    assert "MIIBOgIBAAJBAKj34GkxFhD91aFTAO3sHnbsn9GnJhZ2NcpMr8sTbXzJXjXjXjXj" not in row.body
    assert REDACTION_PLACEHOLDER in row.body


# ---------------------------------------------------- Layer 2: Review Queue display redaction


@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides[get_embedder] = lambda: FakeEmbedder()
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_embedder, None)


async def _seed_admin(db_session) -> User:
    admin = User(
        email="admin@f6-secret.dev",
        display_name="admin",
        status=UserStatus.ACTIVE,
        system_role=UserRole.ADMIN,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


async def _seed_family_with_leaked_secret(db_session, secret_body: str) -> RuleFamily:
    """Simulates the failure mode this layer exists for: a secret that, for whatever reason,
    slipped through the Phase 3 ingestion scan and ended up verbatim in a RuleEvidence
    snapshot. This constructs that DB state directly (bypassing `ingest_pr_corpus`'s own
    redaction entirely, and never calling it), so the test genuinely exercises the *second*,
    independent layer — not an accidental re-test of the first one."""
    now = datetime(2025, 8, 1)
    comment1 = RawPrComment(
        repo=REPO, pr_number=300, pr_author="x", type="review_comment(diff)", author="alice",
        is_bot_comment=False, body="placeholder", url="https://github.com/acme/widgets/pull/300#discussion_r1",
        created_at=now, secret_scanned_at=now,
    )
    comment2 = RawPrComment(
        repo=REPO, pr_number=400, pr_author="y", type="review_comment(diff)", author="bob",
        is_bot_comment=False, body="placeholder", url="https://github.com/acme/widgets/pull/400#discussion_r2",
        created_at=now, secret_scanned_at=now,
    )
    db_session.add_all([comment1, comment2])
    await db_session.flush()

    candidate1 = RuleCandidate(
        evidence_type=RuleEvidenceType.CONVENTION, reuse_scope=2, rule_text_draft="Avoid X.", rationale="r"
    )
    candidate2 = RuleCandidate(
        evidence_type=RuleEvidenceType.CONVENTION, reuse_scope=2, rule_text_draft="Avoid X too.", rationale="r"
    )
    db_session.add_all([candidate1, candidate2])
    await db_session.flush()

    family = RuleFamily(distinct_reviewer_count=2, status=RuleFamilyStatus.PENDING)
    db_session.add(family)
    await db_session.flush()

    db_session.add_all(
        [
            RuleEvidence(
                rule_candidate_id=candidate1.rule_candidate_id,
                rule_family_id=family.rule_family_id,
                evidence_unit_id=f"review_comment(diff):{comment1.raw_pr_comment_id}",
                pr_number=300,
                comment_snippet_snapshot=secret_body,
                original_author="alice",
                evidence_created_at=now,
                cluster_edge_cosine_similarity=None,
            ),
            RuleEvidence(
                rule_candidate_id=candidate2.rule_candidate_id,
                rule_family_id=family.rule_family_id,
                evidence_unit_id=f"review_comment(diff):{comment2.raw_pr_comment_id}",
                pr_number=400,
                comment_snippet_snapshot="avoid X too, an ordinary comment",
                original_author="bob",
                evidence_created_at=now,
                cluster_edge_cosine_similarity=0.9,
            ),
        ]
    )
    await db_session.commit()
    await db_session.refresh(family)
    return family


async def _seed_project(db_session, admin: User) -> Project:
    project = Project(
        key="F6SECRET", name="F6 Secret", created_by_admin_id=admin.user_id,
        github_repo=REPO, default_branch="main",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest.mark.asyncio
async def test_review_queue_pending_list_never_returns_a_leaked_secret_verbatim(db_client, db_session) -> None:
    admin = await _seed_admin(db_session)
    app.dependency_overrides[get_current_user] = lambda: admin
    project = await _seed_project(db_session, admin)
    leaked_secret = "AKIAIOSFODNN7EXAMPLE"
    await _seed_family_with_leaked_secret(db_session, f"rotate this key: access_key = {leaked_secret}")

    response = await db_client.get(f"{API}/pm/projects/{project.project_id}/rule-candidates/pending")

    assert response.status_code == 200
    body = response.json()
    snippets = [e["comment_snippet_snapshot"] for item in body["items"] for e in item["evidence"]]
    assert not any(leaked_secret in snippet for snippet in snippets)
    assert any(REDACTION_PLACEHOLDER in snippet for snippet in snippets)


@pytest.mark.asyncio
async def test_review_queue_conventions_list_never_returns_a_leaked_secret_verbatim(db_client, db_session) -> None:
    """Same layer, the APPROVED/Conventions read path (Member-facing, `list_approved`) — the
    guard lives in the shared `_build_items()`, so both list endpoints must be covered
    separately, not just the PM-facing pending queue."""
    admin = await _seed_admin(db_session)
    app.dependency_overrides[get_current_user] = lambda: admin
    project = await _seed_project(db_session, admin)
    leaked_secret = GITHUB_TOKEN_SECRET
    family = await _seed_family_with_leaked_secret(db_session, f"token leaked here: {leaked_secret}")

    approve = await db_client.post(
        f"{API}/pm/projects/{project.project_id}/rule-candidates/{family.rule_family_id}/approve"
    )
    assert approve.status_code == 200

    response = await db_client.get(f"{API}/conventions")

    assert response.status_code == 200
    body = response.json()
    snippets = [e["comment_snippet_snapshot"] for item in body["items"] for e in item["evidence"]]
    assert not any(leaked_secret in snippet for snippet in snippets)
    assert any(REDACTION_PLACEHOLDER in snippet for snippet in snippets)
