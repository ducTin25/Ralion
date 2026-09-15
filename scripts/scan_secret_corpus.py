"""One-off maintenance scan of the persisted chunk corpus (F-20 legacy remediation).

Ingestion now redacts before chunk/embed/persist, but chunks written before that control
existed can still carry secrets.  This script answers "is the retrievable corpus clean?"
and, when it is not, names exactly what has to be re-ingested.

It never rewrites ``DocumentChunk.content``: the stored vector was computed from the text
as it stands, so patching text in place would leave a chunk whose embedding no longer
matches its content.  Remediation is re-ingest through the safe pipeline:

* PROJECT — re-run ``scripts/run_github_sync.py`` for the affected project.  The source of
  truth is the repository, and the ingest core now redacts.
* POLICY — HR re-uploads the document; ``ingest_policy_document`` redacts and versions it.

Usage::

    python -m scripts.scan_secret_corpus            # summary only
    python -m scripts.scan_secret_corpus --verbose  # per-document chunk ids

Rule ids and identifiers are printed; secret values never are.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict

from sqlalchemy import select

from src.core.security.secret_scan import scan
from src.model.document_chunk import DocumentChunk
from src.model.document_version import DocumentVersion
from src.model.enums import DocumentDomain
from src.model.knowledge_document import KnowledgeDocument
from src.model.session import AsyncSessionLocal


async def _run(verbose: bool) -> int:
    scanned = 0
    dirty_chunks = 0
    by_document: dict[tuple[int, str, DocumentDomain], list[tuple[int, list[str]]]] = defaultdict(list)

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(
                    DocumentChunk.chunk_id,
                    DocumentChunk.content,
                    KnowledgeDocument.document_id,
                    KnowledgeDocument.title,
                    KnowledgeDocument.knowledge_domain,
                )
                .join(DocumentVersion, DocumentVersion.version_id == DocumentChunk.version_id)
                .join(KnowledgeDocument, KnowledgeDocument.document_id == DocumentVersion.document_id)
                .order_by(DocumentChunk.chunk_id)
            )
        ).all()

    for chunk_id, content, document_id, title, domain in rows:
        scanned += 1
        result = scan(content or "")
        if not result.has_findings:
            continue
        dirty_chunks += 1
        rule_ids = sorted({finding.rule_id for finding in result.findings})
        by_document[(document_id, title, domain)].append((chunk_id, rule_ids))

    print(f"chunks scanned: {scanned}")
    print(f"chunks with findings: {dirty_chunks}")
    print(f"documents affected: {len(by_document)}")
    for (document_id, title, domain), items in sorted(by_document.items()):
        rule_ids = sorted({rule for _, rules in items for rule in rules})
        action = (
            "re-run scripts/run_github_sync.py for its project"
            if domain == DocumentDomain.PROJECT
            else "HR must re-upload the policy document"
        )
        print(
            f"- document {document_id} [{domain.value}] {title!r}: "
            f"{len(items)} chunk(s), rules={rule_ids} → {action}"
        )
        if verbose:
            print(f"    chunk_ids: {[chunk_id for chunk_id, _ in items]}")
    if dirty_chunks:
        print(
            "\nDo not UPDATE chunk content directly: the persisted vector was computed from "
            "the current text. Re-ingest so content and embedding stay in sync."
        )
    return 1 if dirty_chunks else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="print affected chunk ids")
    args = parser.parse_args()
    return asyncio.run(_run(args.verbose))


if __name__ == "__main__":
    raise SystemExit(main())
