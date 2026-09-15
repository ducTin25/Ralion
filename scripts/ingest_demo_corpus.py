"""Load the authoritative demo/deployment corpus under `demo-data/` into the database.

`demo-data/` is the source of truth for the deployment knowledge corpus (POLICY =
`demo-data/company-policy/`, PROJECT = `demo-data/thanos-io_project-knowledge/`), and it is
what `eval/`'s golden suite is written against. This script makes the database match it, using
the SAME production ingest cores the application uses -- `ingest_policy_document()` for POLICY
and `ingest_or_update()` for PROJECT -- so every document goes through the real secret scan,
the real chunker and the real embedder. No second ingest path is introduced (CLAUDE.md §2.6).

## Why the pre-enrichment relabel exists

`ingest_policy_document()` refuses to overwrite an existing `DocumentVersion` whose
`version_no` + `embedding_model_version` match but whose checksum differs -- a deliberate guard
against silently rewriting a published policy version. The enriched `demo-data/company-policy/`
documents keep the SAME declared `**Phiên bản:**` string as the pre-enrichment corpus already
sitting in this database while carrying materially different (roughly 2x longer) content, so
that guard fires for every previously-ingested document.

Deleting the stale rows is not an option: `citations`, `plan_task_citations`,
`plan_task_sources` and `policy_acknowledgements` all reference their chunks, so a delete would
destroy real chat and onboarding-plan history. Instead `--relabel-superseded` renames the stale
version's `version_no` to `<version>-pre-enrichment`, which is an accurate description of what
that row now is. The row, its chunks and everything citing them survive; the normal ingest then
archives it and activates the enriched version. Retrieval only ever reads
`DocumentVersion.status == ACTIVE` (`RetrievalEngine.scope_predicates`), so archived
pre-enrichment chunks can never reach an answer.

## Usage

    python scripts/ingest_demo_corpus.py                      # dry run, reports the plan only
    python scripts/ingest_demo_corpus.py --apply              # policy + project
    python scripts/ingest_demo_corpus.py --apply --policy     # policy only
    python scripts/ingest_demo_corpus.py --apply --project    # project only

Re-running after a successful apply is a no-op: identical content resolves to the same
checksum, and both ingest cores return early rather than creating a duplicate version.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from src.config import get_settings  # noqa: E402
from src.core.security.secret_scan import scan  # noqa: E402
from src.infrastructure.ai.resources import create_ai_resources  # noqa: E402
from src.model.document_version import DocumentVersion  # noqa: E402
from src.model.enums import DocumentCategory, DocumentDomain, PolicyCategory  # noqa: E402
from src.model.knowledge_document import KnowledgeDocument  # noqa: E402
from src.model.session import AsyncSessionLocal  # noqa: E402
from src.modules.knowledge.ingestion.versioning import ProjectIngestRequest, ingest_or_update  # noqa: E402
from src.modules.knowledge.policy_ingestion import (  # noqa: E402
    PolicyIngestRequest,
    ingest_policy_document,
)
from src.modules.knowledge.policy_metadata import (  # noqa: E402
    normalize_policy_source_key,
    parse_policy_version_metadata,
)

POLICY_DIR = REPO_ROOT / "demo-data" / "company-policy"
PROJECT_DIR = REPO_ROOT / "demo-data" / "thanos-io_project-knowledge"

# `README.md` in the policy corpus is corpus documentation (design notes for the seed set), not
# a policy: it carries no `**Mã tài liệu:**` and must not become answerable knowledge.
POLICY_SKIP = {"README.md"}

THANOS_PROJECT_ID = 19
# The user every existing POLICY document in this database is already attributed to.
DEFAULT_INGEST_USER_ID = 2

# Categories for the 18 documents already labelled in `policy_category_labels.json` are kept
# byte-identical to what that file assigned, so re-ingest never silently reclassifies a
# document. The v2 documents (README.md "Mở rộng domain — v2") are mapped by their domain
# prefix; `policy_category` is descriptive metadata only -- it is NOT part of
# `RetrievalEngine.scope_predicates`, so a debatable label cannot change retrieval eligibility.
POLICY_CATEGORY_BY_FILE = {
    "hr_01_nghi_phep_cham_cong.md": PolicyCategory.WORKING_RULE,
    "hr_02_luong_thuong_phuc_loi.md": PolicyCategory.BENEFIT,
    "hr_03_onboarding_offboarding.md": PolicyCategory.HR_POLICY,
    "hr_04_dao_tao_phat_trien.md": PolicyCategory.HR_POLICY,
    "hr_05_ky_luat_khieu_nai.md": PolicyCategory.HR_POLICY,
    "it_01_cap_phat_thiet_bi.md": PolicyCategory.COMPANY_POLICY,
    "it_02_tai_khoan_mat_khau.md": PolicyCategory.SECURITY_POLICY,
    "it_03_vpn_remote_access.md": PolicyCategory.SECURITY_POLICY,
    "it_04_phan_mem_license.md": PolicyCategory.COMPANY_POLICY,
    "it_05_su_co_ha_tang.md": PolicyCategory.COMPANY_POLICY,
    "policy_hr.md": PolicyCategory.HR_POLICY,
    "policy_it.md": PolicyCategory.COMPANY_POLICY,
    "policy_security.md": PolicyCategory.SECURITY_POLICY,
    "sec_01_phan_quyen_truy_cap.md": PolicyCategory.SECURITY_POLICY,
    "sec_02_phan_loai_bao_ve_du_lieu.md": PolicyCategory.SECURITY_POLICY,
    "sec_03_quan_ly_secret.md": PolicyCategory.SECURITY_POLICY,
    "sec_04_ung_pho_su_co.md": PolicyCategory.SECURITY_POLICY,
    "sec_05_su_dung_ai_dich_vu_ngoai.md": PolicyCategory.SECURITY_POLICY,
    # v2 expansion
    "hr_06_lam_viec_linh_hoat_wfh.md": PolicyCategory.WORKING_RULE,
    "hr_07_quan_ly_hieu_suat_thang_tien.md": PolicyCategory.HR_POLICY,
    "it_06_quan_ly_thay_doi.md": PolicyCategory.COMPANY_POLICY,
    "it_07_mang_ha_tang_van_phong.md": PolicyCategory.COMPANY_POLICY,
    "it_08_backup_khoi_phuc_du_lieu.md": PolicyCategory.COMPANY_POLICY,
    "sec_06_an_ninh_vat_ly_van_phong.md": PolicyCategory.SECURITY_POLICY,
    "bcp_01_lien_tuc_kinh_doanh_khung_hoang.md": PolicyCategory.COMPANY_POLICY,
    "corp_01_quy_tac_ung_xu_dao_duc.md": PolicyCategory.COMPANY_POLICY,
    "corp_02_xung_dot_loi_ich_qua_tang_chong_hoi_lo.md": PolicyCategory.COMPANY_POLICY,
    "corp_03_truyen_thong_mang_xa_hoi.md": PolicyCategory.COMPANY_POLICY,
    "cust_01_truy_cap_du_lieu_khach_hang_ho_tro.md": PolicyCategory.SECURITY_POLICY,
    "eng_01_secure_sdlc.md": PolicyCategory.SECURITY_POLICY,
    "eng_02_quan_ly_lo_hong_va_va_loi.md": PolicyCategory.SECURITY_POLICY,
    "eng_03_quan_tri_repo_release_open_source.md": PolicyCategory.COMPANY_POLICY,
    "esg_01_moi_truong_va_van_hanh_ben_vung.md": PolicyCategory.COMPANY_POLICY,
    "fin_01_cong_tac_phi_hoan_ung.md": PolicyCategory.COMPANY_POLICY,
    "fin_02_mua_sam_phe_duyet_chi_tieu.md": PolicyCategory.COMPANY_POLICY,
    "gov_01_quan_ly_ho_so_luu_tru_legal_hold.md": PolicyCategory.COMPANY_POLICY,
    "leg_01_so_huu_tri_tue_bao_mat.md": PolicyCategory.COMPANY_POLICY,
    "leg_02_quan_ly_hop_dong_tham_quyen_ky.md": PolicyCategory.COMPANY_POLICY,
    "tprm_01_quan_ly_rui_ro_nha_cung_cap.md": PolicyCategory.SECURITY_POLICY,
}

# `demo-data/thanos-io_project-knowledge/test_upload/` holds the five Ralion-authored onboarding
# documents of the demo PROJECT corpus. Unlike the repository snapshot next to them they are not
# GitHub files, so they carry no upstream commit `source_ref`; the constant below records that
# provenance honestly instead of inventing a commit SHA. `document_category` follows each
# document's own "Ralion category" header line.
TEST_UPLOAD_SOURCE_REF = "demo-data-test-upload-2026-08-24"
TEST_UPLOAD_CATEGORIES = {
    "ARCHITECTURE.md": DocumentCategory.ARCHITECTURE,
    "component.md": DocumentCategory.ARCHITECTURE,
    "thanos_access_security.md": DocumentCategory.ACCESS_SECURITY,
    "thanos_codebase_guide.md": DocumentCategory.CODEBASE_GUIDE,
    "thanos_environment_setup.md": DocumentCategory.SETUP,
}
TEST_UPLOAD_TITLES = {
    "ARCHITECTURE.md": "Thanos Architecture Overview",
    "component.md": "Thanos Components and Getting Started",
    "thanos_access_security.md": "Thanos Access and Security Guide",
    "thanos_codebase_guide.md": "Thanos Codebase Guide",
    "thanos_environment_setup.md": "Thanos Development Environment Setup",
}

_DOC_CODE = re.compile(r"^[-*]\s+\*\*Mã tài liệu:\*\*\s*(.+?)\s*$", re.MULTILINE)
_H1 = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_PURPOSE_HEADING = re.compile(r"^##\s+1\.\s*Mục đích\s*$", re.MULTILINE)


@dataclass(frozen=True)
class PolicyDoc:
    path: Path
    document_code: str
    title: str
    policy_category: PolicyCategory
    content: str
    purpose_sentence: str

    @property
    def source_version(self) -> str:
        return parse_policy_version_metadata(self.content)[0]

    @property
    def redacted_checksum(self) -> str:
        """The checksum `ingest_policy_document` will compute -- taken over the POST-scan text,
        exactly as that function does, so a comparison here means the same thing it does there."""
        return hashlib.sha256(scan(self.content).redacted_content.encode("utf-8")).hexdigest()


def _purpose_sentence(content: str) -> str:
    """First sentence under the '## 1. Mục đích' heading, used as the chunk-level purpose hint.

    Returns "" when the document has no such section; `ingest_policy_document` then falls back
    to the `**Mục đích:**` header bullet on its own.
    """
    match = _PURPOSE_HEADING.search(content)
    if match is None:
        return ""
    tail = content[match.end() :].lstrip()
    for line in tail.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return ""


def load_policy_docs() -> list[PolicyDoc]:
    docs: list[PolicyDoc] = []
    for path in sorted(POLICY_DIR.glob("*.md")):
        if path.name in POLICY_SKIP:
            continue
        content = path.read_text(encoding="utf-8")
        code_match = _DOC_CODE.search(content)
        if code_match is None:
            raise ValueError(f"{path.name}: no '**Mã tài liệu:**' header -- cannot ingest as a policy")
        category = POLICY_CATEGORY_BY_FILE.get(path.name)
        if category is None:
            raise ValueError(
                f"{path.name}: no policy_category mapping. Add one to POLICY_CATEGORY_BY_FILE "
                "rather than defaulting -- an unreviewed label is worse than a loud failure."
            )
        title_match = _H1.search(content)
        docs.append(
            PolicyDoc(
                path=path,
                document_code=code_match.group(1),
                title=title_match.group(1) if title_match else path.stem,
                policy_category=category,
                content=content,
                purpose_sentence=_purpose_sentence(content),
            )
        )
    return docs


async def _superseded_versions(session: AsyncSession, docs: list[PolicyDoc], model_version: str):
    """Existing rows that would make `ingest_policy_document` raise on a checksum conflict."""
    conflicts = []
    for doc in docs:
        source_key = normalize_policy_source_key(doc.document_code)
        document = await session.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.knowledge_domain == DocumentDomain.POLICY,
                KnowledgeDocument.source_key == source_key,
            )
        )
        if document is None:
            continue
        version = await session.scalar(
            select(DocumentVersion).where(
                DocumentVersion.document_id == document.document_id,
                DocumentVersion.version_no == doc.source_version,
                DocumentVersion.embedding_model_version == model_version,
            )
        )
        if version is not None and version.checksum != doc.redacted_checksum:
            conflicts.append((doc, version))
    return conflicts


async def run_policy(session: AsyncSession, embedder, *, apply: bool, user_id: int) -> None:
    docs = load_policy_docs()
    print(f"[policy] {len(docs)} document(s) in {POLICY_DIR.relative_to(REPO_ROOT)}")

    conflicts = await _superseded_versions(session, docs, embedder.model_version)
    if conflicts:
        print(f"[policy] {len(conflicts)} stale version(s) to relabel as '-pre-enrichment':")
        for doc, version in conflicts:
            print(f"           {doc.path.name}: version_no {version.version_no!r} (revision {version.revision_no})")
    if apply and conflicts:
        for _doc, version in conflicts:
            version.version_no = f"{version.version_no}-pre-enrichment"
        await session.commit()
        print(f"[policy] relabelled {len(conflicts)} stale version(s)")

    if not apply:
        print("[policy] dry run -- no ingest performed. Re-run with --apply.")
        return

    for doc in docs:
        request = PolicyIngestRequest(
            title=doc.title,
            content=doc.content,
            document_code=doc.document_code,
            policy_category=doc.policy_category,
            created_by_user_id=user_id,
            # Provenance points at the authoritative corpus file, not at a fabricated URL.
            source_url=f"demo-data/company-policy/{doc.path.name}",
            purpose_sentence=doc.purpose_sentence,
        )
        try:
            document = await ingest_policy_document(session, request, embedder)
        except Exception as exc:  # noqa: BLE001 - report per document, never abort the batch
            await session.rollback()
            print(f"[policy] FAIL {doc.path.name}: {type(exc).__name__}: {exc}")
            continue
        print(f"[policy] ok   {doc.path.name} -> document_id={document.document_id} v{doc.source_version}")


async def run_project(session: AsyncSession, embedder, *, apply: bool, user_id: int) -> None:
    upload_dir = PROJECT_DIR / "test_upload"
    paths = sorted(upload_dir.glob("*.md"))
    print(f"[project] {len(paths)} document(s) in {upload_dir.relative_to(REPO_ROOT)}")
    if not apply:
        for path in paths:
            print(f"[project] would ingest {path.name} as {TEST_UPLOAD_CATEGORIES[path.name].value}")
        print("[project] dry run -- no ingest performed. Re-run with --apply.")
        return

    for path in paths:
        category = TEST_UPLOAD_CATEGORIES.get(path.name)
        if category is None:
            print(f"[project] SKIP {path.name}: no document_category mapping")
            continue
        relative = f"test_upload/{path.name}"
        request = ProjectIngestRequest(
            project_id=THANOS_PROJECT_ID,
            created_by_user_id=user_id,
            source_key=f"demo-data:{relative}",
            source_url=f"demo-data/thanos-io_project-knowledge/{relative}",
            source_repo="demo-data/thanos-io_project-knowledge",
            source_path=relative,
            document_category=category,
            raw_content=path.read_text(encoding="utf-8"),
            source_ref=TEST_UPLOAD_SOURCE_REF,
            title=TEST_UPLOAD_TITLES[path.name],
            # These five are Ralion-authored onboarding documents, hand-categorised above rather
            # than classifier output -- `category_confirmed=True` is what makes them visible to
            # PROJECT retrieval at all (`scope_predicates` requires a non-null category).
            category_confirmed=True,
        )
        try:
            document = await ingest_or_update(session, request, embedder)
            await session.commit()
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            print(f"[project] FAIL {path.name}: {type(exc).__name__}: {exc}")
            continue
        print(f"[project] ok   {path.name} -> document_id={document.document_id} ({category.value})")


async def main_async(args: argparse.Namespace) -> None:
    settings = get_settings()
    resources = create_ai_resources(settings)
    try:
        async with AsyncSessionLocal() as session:
            embedder = resources.ingestion_embedding
            print(f"embedder model_version: {embedder.model_version}")
            if args.policy:
                await run_policy(session, embedder, apply=args.apply, user_id=args.user_id)
            if args.project:
                await run_project(session, embedder, apply=args.apply, user_id=args.user_id)
    finally:
        await resources.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="actually write to the database")
    parser.add_argument("--policy", action="store_true", help="only the POLICY corpus")
    parser.add_argument("--project", action="store_true", help="only the PROJECT corpus")
    parser.add_argument("--user-id", type=int, default=DEFAULT_INGEST_USER_ID)
    args = parser.parse_args()
    if not args.policy and not args.project:
        args.policy = args.project = True
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
