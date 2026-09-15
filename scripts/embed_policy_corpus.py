"""Kaggle-friendly batch embedding for the checked-in policy seed corpus.

Usage:
    python scripts/embed_policy_corpus.py --input demo-data/company-policy --output policy_embeddings.jsonl

The output is a portable manifest for loading through the policy ingestion workflow.
It deliberately contains both display content and derived embedding text so citations
never need to reconstruct source content from vectors.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.ai.providers.embeddings import BgeM3Embedder
from src.ai.retrieval_engine.policy_chunker import chunk_policy_markdown, embedding_text_for_policy_chunk
from src.core.security.secret_scan import record_secret_findings, scan
from src.modules.knowledge.policy_ingestion import parse_policy_header


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("demo-data/company-policy"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default=None, help="Optional torch device, e.g. cuda or cpu")
    args = parser.parse_args()

    files = sorted(args.input.glob("*.md"))
    if not files:
        raise SystemExit(f"No Markdown policy files found under {args.input}")
    embedder = BgeM3Embedder(device=args.device)
    records: list[dict] = []
    for path in files:
        # Redact before chunking and embedding, mirroring the ingest core. The
        # importer rejects any artifact row that still carries a secret, so this is
        # where the offline path has to satisfy the scan-before-embed invariant.
        redaction = scan(path.read_text(encoding="utf-8"))
        record_secret_findings(
            redaction, boundary="ingest.policy_artifact", document_reference=str(path)
        )
        content = redaction.redacted_content
        metadata = parse_policy_header(content)
        document_code = metadata.get("mã tài liệu", path.stem)
        chunks = chunk_policy_markdown(content, document_code=document_code)
        texts = [embedding_text_for_policy_chunk(chunk, document_code=document_code) for chunk in chunks]
        vectors = embedder.embed(texts)
        records.append(
            {
                "source_file": str(path),
                "document_code": document_code,
                "title": path.stem,
                "chunks": [
                    {
                        "chunk_index": index,
                        "heading": chunk.heading_path,
                        "content": chunk.content,
                        "embedding_text": text,
                        "token_count": chunk.token_count,
                        "embedding": vector,
                    }
                    for index, (chunk, text, vector) in enumerate(zip(chunks, texts, vectors, strict=True))
                ],
            }
        )
    args.output.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records), encoding="utf-8")


if __name__ == "__main__":
    main()
