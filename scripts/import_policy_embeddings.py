"""Persist policy_embeddings.jsonl without recomputing embeddings.

Usage:
    python scripts/import_policy_embeddings.py
    python scripts/import_policy_embeddings.py --no-upload  # local/dev fallback
"""

from __future__ import annotations

# The root-path bootstrap below must run before importing the local ``src`` package.
# ruff: noqa: E402, I001

import argparse
import re
import sys
from pathlib import Path

import cloudinary
import cloudinary.uploader

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import get_settings  # noqa: E402
from src.infrastructure.persistence.policy_embedding_import import import_policy_embeddings  # noqa: E402
from src.model.session import AsyncSessionLocal  # noqa: E402

def build_uploader(*, upload: bool):
    settings = get_settings()
    if upload:
        missing = [
            name
            for name, value in (
                ("CLOUDINARY_CLOUD_NAME", settings.cloudinary_cloud_name),
                ("CLOUDINARY_API_KEY", settings.cloudinary_api_key),
                ("CLOUDINARY_API_SECRET", settings.cloudinary_api_secret),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(f"Cloudinary upload requires: {', '.join(missing)}")
        cloudinary.config(
            cloud_name=settings.cloudinary_cloud_name,
            api_key=settings.cloudinary_api_key,
            api_secret=settings.cloudinary_api_secret,
        )

    def source_uri_for(path: Path, source_key: str, checksum: str) -> str:
        if not upload:
            return path.resolve().as_uri()
        safe_source_key = re.sub(r"[^A-Za-z0-9._-]+", "-", source_key).strip(".-")
        result = cloudinary.uploader.upload(
            str(path),
            resource_type="raw",
            folder="knowledge-documents/policy",
            public_id=f"{safe_source_key}/{checksum}",
            overwrite=True,
            unique_filename=False,
        )
        return result["secure_url"]

    return source_uri_for


async def run(args: argparse.Namespace) -> None:
    source_uri_for = build_uploader(upload=not args.no_upload)
    async with AsyncSessionLocal() as db:
        documents, chunks = await import_policy_embeddings(
            db,
            embedding_path=args.embedding,
            labels_path=args.labels,
            source_root=args.source_root,
            source_uri_for=source_uri_for,
        )
    print(f"Imported {documents} document(s), {chunks} chunk(s)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    policy_data = ROOT / "demo-data" / "company-policy"
    parser.add_argument("--embedding", type=Path, default=ROOT / "policy_embeddings.jsonl")
    parser.add_argument("--labels", type=Path, default=ROOT / "policy_category_labels.json")
    parser.add_argument("--source-root", type=Path, default=policy_data)
    parser.add_argument("--no-upload", action="store_true", help="Use local file:// URI instead of Cloudinary")
    args = parser.parse_args()
    import asyncio

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
