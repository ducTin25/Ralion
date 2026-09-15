"""F6 Phase 6 — HITL Review Queue API (CLAUDE.md Phase 6). SQLite in-memory qua db_client/
db_session (tests/conftest.py) — dependency_overrides thay cho login thật, đúng convention
`test_admin_management.py`.

Project-ACL note: the PM-facing routes below are `/pm/projects/{project_id}/rule-candidates/...`
— scoped to the project's connected `github_repo`, since `RuleFamily` carries no `project_id`
directly (see `rule_review_service._resolve_family_repos`). `GET /conventions` (no project_id)
stays company-wide on purpose — it is the one endpoint the chat Member Conventions panel reads.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from src.ai.providers.embeddings_fake import FakeEmbedder
from src.api.dependencies import get_current_user, get_embedder
from src.main import app
from src.model.document_chunk import DocumentChunk
from src.model.document_version import DocumentVersion
from src.model.enums import (
    DocumentCategory,
    MembershipStatus,
    ProjectRole,
    ProjectStatus,
    RuleEvidenceType,
    RuleFamilyStatus,
    UserRole,
    UserStatus,
    VersionStatus,
)
from src.model.project import Project
from src.model.project_membership import ProjectMembership
from src.model.raw_pr_comment import RawPrComment
from src.model.rule_candidate import RuleCandidate
from src.model.rule_evidence import RuleEvidence
from src.model.rule_family import RuleFamily
from src.model.user import User
from src.modules.knowledge.mining.convention_ingestion import find_convention_document

API = "/api/v1"
REPO = "acme/widgets"


@pytest.fixture(autouse=True)
def clear_overrides():
    # Phase 10: approving also ingests the rule into the shared retrieval engine, so the
    # endpoint now depends on an embedder. `get_embedder` reads `app.state.ai_resources`,
    # which only the real lifespan populates — override it the same way these tests already
    # override authentication.
    app.dependency_overrides[get_embedder] = lambda: FakeEmbedder()
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_embedder, None)


async def _seed_user(db_session, email: str, **kwargs) -> User:
    user = User(
        email=email,
        display_name=email,
        status=kwargs.pop("status", UserStatus.ACTIVE),
        system_role=kwargs.pop("system_role", None),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _override_current_user(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


async def _seed_project(
    db_session,
    admin: User,
    *,
    key: str,
    repo: str | None = REPO,
    status: ProjectStatus = ProjectStatus.ACTIVE,
) -> Project:
    project = Project(
        key=key,
        name=key,
        created_by_admin_id=admin.user_id,
        github_repo=repo,
        default_branch="main" if repo else None,
        status=status,
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


async def _add_pm(db_session, project: Project, pm: User, admin: User) -> None:
    db_session.add(
        ProjectMembership(
            user_id=pm.user_id,
            project_id=project.project_id,
            project_role=ProjectRole.PM,
            status=MembershipStatus.ACTIVE,
            assigned_by_admin_id=admin.user_id,
        )
    )
    await db_session.commit()


async def _seed_family(db_session, *, repo: str = REPO) -> RuleFamily:
    now = datetime(2025, 8, 1)
    comment1 = RawPrComment(
        repo=repo,
        pr_number=100,
        pr_author="x",
        type="review_comment(diff)",
        author="alice",
        is_bot_comment=False,
        body="avoid X",
        url=f"https://github.com/{repo}/pull/100#discussion_r1",
        created_at=now,
        secret_scanned_at=now,
    )
    comment2 = RawPrComment(
        repo=repo,
        pr_number=200,
        pr_author="y",
        type="review_comment(diff)",
        author="bob",
        is_bot_comment=False,
        body="avoid X too",
        url=f"https://github.com/{repo}/pull/200#discussion_r2",
        created_at=now,
        secret_scanned_at=now,
    )
    db_session.add_all([comment1, comment2])
    await db_session.flush()

    candidate1 = RuleCandidate(
        evidence_type=RuleEvidenceType.CONVENTION, reuse_scope=2, rule_text_draft="Avoid X.", rationale="r"
    )
    candidate2 = RuleCandidate(
        evidence_type=RuleEvidenceType.CONVENTION, reuse_scope=2, rule_text_draft="Avoid X please.", rationale="r"
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
                pr_number=100,
                comment_snippet_snapshot="avoid X",
                original_author="alice",
                evidence_created_at=now,
                cluster_edge_cosine_similarity=None,
            ),
            RuleEvidence(
                rule_candidate_id=candidate2.rule_candidate_id,
                rule_family_id=family.rule_family_id,
                evidence_unit_id=f"review_comment(diff):{comment2.raw_pr_comment_id}",
                pr_number=200,
                comment_snippet_snapshot="avoid X too",
                original_author="bob",
                evidence_created_at=now,
                cluster_edge_cosine_similarity=0.9,
            ),
        ]
    )
    await db_session.commit()
    await db_session.refresh(family)
    return family


@pytest.mark.asyncio
async def test_pending_list_shows_permalink_from_raw_pr_comments_not_reconstructed(db_client, db_session):
    admin = await _seed_user(db_session, "admin@f6.dev", system_role=UserRole.ADMIN)
    project = await _seed_project(db_session, admin, key="P1")
    await _override_current_user(admin)
    family = await _seed_family(db_session)

    response = await db_client.get(f"{API}/pm/projects/{project.project_id}/rule-candidates/pending")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 1
    item = body["items"][0]
    assert item["rule_family_id"] == family.rule_family_id
    assert item["rule_text"] == "Avoid X."
    assert item["family_match_confidence"] == "HIGH"
    permalinks = {e["permalink"] for e in item["evidence"]}
    assert permalinks == {
        f"https://github.com/{REPO}/pull/100#discussion_r1",
        f"https://github.com/{REPO}/pull/200#discussion_r2",
    }


@pytest.mark.asyncio
async def test_plain_member_cannot_approve_or_reject(db_client, db_session):
    admin = await _seed_user(db_session, "admin-plain@f6.dev", system_role=UserRole.ADMIN)
    plain = await _seed_user(db_session, "member@f6.dev")
    project = await _seed_project(db_session, admin, key="P2")
    family = await _seed_family(db_session)

    await _override_current_user(plain)
    approve = await db_client.post(
        f"{API}/pm/projects/{project.project_id}/rule-candidates/{family.rule_family_id}/approve"
    )
    reject = await db_client.post(
        f"{API}/pm/projects/{project.project_id}/rule-candidates/{family.rule_family_id}/reject"
    )
    legacy_list = await db_client.get(f"{API}/conventions")

    assert approve.status_code == 403
    assert reject.status_code == 403
    assert legacy_list.status_code == 403


@pytest.mark.asyncio
async def test_project_pm_can_approve_even_without_system_role(db_client, db_session):
    admin = await _seed_user(db_session, "admin2@f6.dev", system_role=UserRole.ADMIN)
    pm = await _seed_user(db_session, "pm@f6.dev")
    project = await _seed_project(db_session, admin, key="PM1")
    await _add_pm(db_session, project, pm, admin)
    family = await _seed_family(db_session)

    await _override_current_user(pm)
    response = await db_client.post(
        f"{API}/pm/projects/{project.project_id}/rule-candidates/{family.rule_family_id}/approve"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"


@pytest.mark.asyncio
async def test_approve_end_to_end_then_appears_in_conventions(db_client, db_session):
    admin = await _seed_user(db_session, "admin3@f6.dev", system_role=UserRole.ADMIN)
    project = await _seed_project(db_session, admin, key="P3")
    await _override_current_user(admin)
    family = await _seed_family(db_session)

    approve = await db_client.post(
        f"{API}/pm/projects/{project.project_id}/rule-candidates/{family.rule_family_id}/approve"
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "APPROVED"

    pending = await db_client.get(f"{API}/pm/projects/{project.project_id}/rule-candidates/pending")
    assert pending.json()["meta"]["total"] == 0

    project_approved = await db_client.get(f"{API}/pm/projects/{project.project_id}/rule-candidates/approved")
    assert project_approved.json()["meta"]["total"] == 1

    conventions = await db_client.get(f"{API}/conventions")
    assert conventions.json()["meta"]["total"] == 1
    assert conventions.json()["items"][0]["rule_family_id"] == family.rule_family_id


@pytest.mark.asyncio
async def test_reject_never_leaks_to_conventions(db_client, db_session):
    admin = await _seed_user(db_session, "admin4@f6.dev", system_role=UserRole.ADMIN)
    project = await _seed_project(db_session, admin, key="P4")
    await _override_current_user(admin)
    family = await _seed_family(db_session)

    reject = await db_client.post(
        f"{API}/pm/projects/{project.project_id}/rule-candidates/{family.rule_family_id}/reject"
    )
    assert reject.status_code == 200
    assert reject.json()["status"] == "REJECTED"

    pending = await db_client.get(f"{API}/pm/projects/{project.project_id}/rule-candidates/pending")
    assert pending.json()["meta"]["total"] == 0
    conventions = await db_client.get(f"{API}/conventions")
    assert conventions.json()["meta"]["total"] == 0


@pytest.mark.asyncio
async def test_member_conventions_are_project_scoped_and_hide_mining_metadata(db_client, db_session):
    admin = await _seed_user(db_session, "admin-member-conventions@f6.dev", system_role=UserRole.ADMIN)
    engineer = await _seed_user(db_session, "engineer-member-conventions@f6.dev")
    family = await _seed_family(db_session, repo="acme/widgets")
    evidence = await db_session.scalar(
        select(RuleEvidence).where(RuleEvidence.rule_family_id == family.rule_family_id)
    )
    assert evidence is not None
    evidence.comment_snippet_snapshot = "Use the explicit context.\n```go\nctx, cancel := context.WithTimeout(ctx, timeout)\n```"
    project = await _seed_project(db_session, admin, key="ACME-HANDBOOK", repo="acme/widgets")
    other_project = await _seed_project(db_session, admin, key="OTHER-HANDBOOK", repo="acme/other")
    db_session.add(
        ProjectMembership(
            user_id=engineer.user_id,
            project_id=project.project_id,
            project_role=ProjectRole.ENGINEER,
            status=MembershipStatus.ACTIVE,
            assigned_by_admin_id=admin.user_id,
        )
    )
    await db_session.commit()

    await _override_current_user(admin)
    approved = await db_client.post(
        f"{API}/pm/projects/{project.project_id}/rule-candidates/{family.rule_family_id}/approve"
    )
    assert approved.status_code == 200

    await _override_current_user(engineer)
    response = await db_client.get(f"{API}/projects/{project.project_id}/conventions")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 1
    item = body["items"][0]
    assert item["rule_family_id"] == family.rule_family_id
    assert "status" not in item
    assert "family_match_confidence" not in item
    assert "distinct_reviewer_count" not in item
    assert item["evidence"][0]["pr_number"] == 100
    assert item["actual_examples"][0]["code"] == "ctx, cancel := context.WithTimeout(ctx, timeout)"
    assert item["actual_examples"][0]["permalink"].endswith("discussion_r1")
    assert item["evidence"][0]["code_snippet_snapshot"] is None
    assert item["evidence"][0]["code_before_snapshot"] is None
    assert item["evidence"][0]["code_after_snapshot"] is None

    forbidden = await db_client.get(f"{API}/projects/{other_project.project_id}/conventions")
    assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_member_conventions_include_raw_code_snapshots_when_available(db_client, db_session):
    admin = await _seed_user(db_session, "admin-member-code@f6.dev", system_role=UserRole.ADMIN)
    engineer = await _seed_user(db_session, "engineer-member-code@f6.dev")
    family = await _seed_family(db_session)
    source = await db_session.scalar(
        select(RawPrComment).where(RawPrComment.pr_number == 100)
    )
    assert source is not None
    source.code_snippet_snapshot = "return currentUser"
    source.code_before_snapshot = "return user"
    source.code_after_snapshot = "return currentUser"
    project = await _seed_project(db_session, admin, key="CODE-HANDBOOK")
    db_session.add(
        ProjectMembership(
            user_id=engineer.user_id,
            project_id=project.project_id,
            project_role=ProjectRole.ENGINEER,
            status=MembershipStatus.ACTIVE,
            assigned_by_admin_id=admin.user_id,
        )
    )
    await db_session.commit()

    await _override_current_user(admin)
    approved = await db_client.post(
        f"{API}/pm/projects/{project.project_id}/rule-candidates/{family.rule_family_id}/approve"
    )
    assert approved.status_code == 200

    await _override_current_user(engineer)
    response = await db_client.get(f"{API}/projects/{project.project_id}/conventions")

    assert response.status_code == 200
    evidence = response.json()["items"][0]["evidence"][0]
    assert evidence["code_snippet_snapshot"] == "return currentUser"
    assert evidence["code_before_snapshot"] == "return user"
    assert evidence["code_after_snapshot"] == "return currentUser"


@pytest.mark.asyncio
async def test_concurrent_approve_requests_only_one_succeeds_other_gets_409(db_client, db_session):
    admin = await _seed_user(db_session, "admin5@f6.dev", system_role=UserRole.ADMIN)
    project = await _seed_project(db_session, admin, key="P5")
    await _override_current_user(admin)
    family = await _seed_family(db_session)

    url = f"{API}/pm/projects/{project.project_id}/rule-candidates/{family.rule_family_id}/approve"
    first = await db_client.post(url)
    second = await db_client.post(url)

    assert first.status_code == 200
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_approve_nonexistent_rule_candidate_returns_404(db_client, db_session):
    admin = await _seed_user(db_session, "admin6@f6.dev", system_role=UserRole.ADMIN)
    project = await _seed_project(db_session, admin, key="P6")
    await _override_current_user(admin)

    response = await db_client.post(f"{API}/pm/projects/{project.project_id}/rule-candidates/999999/approve")

    assert response.status_code == 404


# ---------------------------------------------------------------------------------------
# Project ACL — the bug this fix closes
# ---------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pm_of_one_project_cannot_see_another_projects_pending_family(db_client, db_session):
    admin = await _seed_user(db_session, "admin-acl@f6.dev", system_role=UserRole.ADMIN)
    pm_b = await _seed_user(db_session, "pm-b@f6.dev")
    project_a = await _seed_project(db_session, admin, key="ACLA", repo="acme/widgets")
    project_b = await _seed_project(db_session, admin, key="ACLB", repo="other/repo")
    await _add_pm(db_session, project_b, pm_b, admin)
    family = await _seed_family(db_session, repo="acme/widgets")  # belongs to project_a's repo

    await _override_current_user(pm_b)
    pending = await db_client.get(f"{API}/pm/projects/{project_b.project_id}/rule-candidates/pending")
    assert pending.status_code == 200
    assert pending.json()["meta"]["total"] == 0

    approve = await db_client.post(
        f"{API}/pm/projects/{project_b.project_id}/rule-candidates/{family.rule_family_id}/approve"
    )
    reject = await db_client.post(
        f"{API}/pm/projects/{project_b.project_id}/rule-candidates/{family.rule_family_id}/reject"
    )
    assert approve.status_code == 404
    assert reject.status_code == 404

    # Confirm it never actually decided the family — the PM of the *right* project still can.
    still_pending = await db_session.get(RuleFamily, family.rule_family_id)
    assert still_pending.status == RuleFamilyStatus.PENDING
    del project_a  # only used to document which project legitimately owns this family


@pytest.mark.asyncio
async def test_pm_can_see_and_approve_their_own_projects_family(db_client, db_session):
    admin = await _seed_user(db_session, "admin-acl2@f6.dev", system_role=UserRole.ADMIN)
    pm_a = await _seed_user(db_session, "pm-a@f6.dev")
    project_a = await _seed_project(db_session, admin, key="ACLC", repo="acme/widgets")
    await _add_pm(db_session, project_a, pm_a, admin)
    family = await _seed_family(db_session, repo="acme/widgets")

    await _override_current_user(pm_a)
    pending = await db_client.get(f"{API}/pm/projects/{project_a.project_id}/rule-candidates/pending")
    assert pending.json()["meta"]["total"] == 1

    approve = await db_client.post(
        f"{API}/pm/projects/{project_a.project_id}/rule-candidates/{family.rule_family_id}/approve"
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "APPROVED"


# ---------------------------------------------------------------------------------------
# Phase 10 — approve also indexes into the shared retrieval engine
# ---------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_indexes_the_rule_into_the_shared_retrieval_engine(db_client, db_session):
    """Exit criterion 1, through the real Phase 6 endpoint: one approval, one indexed chunk."""
    admin = await _seed_user(db_session, "admin@f6.dev", system_role=UserRole.ADMIN)
    await _override_current_user(admin)
    family = await _seed_family(db_session)
    family_id = family.rule_family_id
    # The repository the evidence came from has to map to an ACTIVE project; that mapping is
    # what gives the indexed document its ACL scope, and is also what authorizes the approve
    # call itself under the new project-scoped ACL.
    project = await _seed_project(db_session, admin, key="ACME", repo=REPO)

    response = await db_client.post(
        f"{API}/pm/projects/{project.project_id}/rule-candidates/{family_id}/approve"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"
    assert response.json()["retrieval_indexed"] is True

    document = await find_convention_document(db_session, family_id)
    assert document is not None
    assert document.document_category is DocumentCategory.CONVENTION
    assert document.source_url == f"/conventions/{family_id}"
    version = await db_session.scalar(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document.document_id,
            DocumentVersion.status == VersionStatus.ACTIVE,
        )
    )
    chunks = (
        await db_session.scalars(
            select(DocumentChunk).where(DocumentChunk.version_id == version.version_id)
        )
    ).all()
    assert len(chunks) == 1
    assert chunks[0].content.startswith("[Convention] Avoid X.")


@pytest.mark.asyncio
async def test_failed_index_leaves_the_approval_standing_and_reindex_recovers(db_client, db_session):
    """Exit criterion 5: the human decision does not depend on a technical side effect.

    The authorizing project is ARCHIVED, not simply absent: the new project-scoped ACL only
    needs the repo to match (any status), while `ingest_approved_rule_family`'s own lookup
    requires an ACTIVE project — so approval is authorized but indexing still has nothing to
    attach to, exactly as before this project-ACL change.
    """
    admin = await _seed_user(db_session, "admin@f6.dev", system_role=UserRole.ADMIN)
    await _override_current_user(admin)
    family = await _seed_family(db_session)
    family_id = family.rule_family_id
    project = await _seed_project(db_session, admin, key="ACME", repo=REPO, status=ProjectStatus.ARCHIVED)

    response = await db_client.post(
        f"{API}/pm/projects/{project.project_id}/rule-candidates/{family_id}/approve"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"
    assert response.json()["retrieval_indexed"] is False
    assert await find_convention_document(db_session, family_id) is None

    # The approval is visible in the Conventions list even though retrieval does not have it.
    listing = await db_client.get(f"{API}/conventions")
    assert listing.status_code == 200
    assert [item["rule_family_id"] for item in listing.json()["items"]] == [family_id]

    # Fix the cause, then retry — no re-approval, no data loss.
    project.status = ProjectStatus.ACTIVE
    await db_session.commit()

    retry = await db_client.post(
        f"{API}/pm/projects/{project.project_id}/rule-candidates/{family_id}/reindex"
    )
    assert retry.status_code == 200
    assert retry.json()["retrieval_indexed"] is True
    assert await find_convention_document(db_session, family_id) is not None


@pytest.mark.asyncio
async def test_reindex_refuses_a_family_that_was_never_approved(db_client, db_session):
    admin = await _seed_user(db_session, "admin@f6.dev", system_role=UserRole.ADMIN)
    project = await _seed_project(db_session, admin, key="P7")
    await _override_current_user(admin)
    family = await _seed_family(db_session)

    response = await db_client.post(
        f"{API}/pm/projects/{project.project_id}/rule-candidates/{family.rule_family_id}/reindex"
    )
    assert response.status_code == 409

    missing = await db_client.post(f"{API}/pm/projects/{project.project_id}/rule-candidates/999999/reindex")
    assert missing.status_code == 404
