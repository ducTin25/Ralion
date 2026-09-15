"""Read-only offline audit for Cargo discovery job 17.

Exports persisted candidate data, all pairwise cosine scores, nearest neighbors, and
threshold-sweep connected components.  It never writes to the application database.
"""

import asyncio
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import text

from src.model.session import AsyncSessionLocal


PROJECT_REPO = "rust-lang/cargo"
RUN_STARTED_AT = "2026-08-28 15:10:49"
RUN_FINISHED_AT = "2026-08-28 15:14:20"
THRESHOLDS = tuple(round(value / 100, 2) for value in range(55, 76, 1))
OUTPUT_PATH = REPO_ROOT / "output/cargo-rule-mining-audit.json"


def cosine(left: list[float], right: list[float]) -> float:
    # BGE-M3 vectors are normalized in production; retain the explicit norm calculation so
    # the audit remains correct if a stored vector is not normalized.
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    return dot / (left_norm * right_norm)


def components(candidates: list[dict], pairs: list[dict], threshold: float) -> list[list[int]]:
    parent = {candidate["rule_candidate_id"]: candidate["rule_candidate_id"] for candidate in candidates}

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for pair in pairs:
        if pair["cosine"] >= threshold:
            union(pair["left_id"], pair["right_id"])

    grouped: dict[int, list[int]] = defaultdict(list)
    for candidate_id in parent:
        grouped[find(candidate_id)].append(candidate_id)
    return sorted((sorted(group) for group in grouped.values() if len(group) > 1), key=lambda group: group)


async def main() -> None:
    query = text(
        """
        SELECT
          rc.rule_candidate_id,
          rc.evidence_unit_id,
          rc.pr_number,
          rc.evidence_type::text AS evidence_type,
          rc.reuse_scope,
          rc.rule_text_draft,
          rc.rationale,
          rc.embedding::text AS embedding,
          rc.embedding_model_version,
          rpc.url,
          rpc.body AS source_comment
        FROM rule_candidates rc
        JOIN raw_pr_comments rpc
          ON CONCAT(rpc.type, ':', rpc.raw_pr_comment_id) = rc.evidence_unit_id
        WHERE rpc.repo = :repo
          AND rpc.mining_processed_at BETWEEN CAST(:started_at AS timestamp) AND CAST(:finished_at AS timestamp)
          AND rc.embedding IS NOT NULL
        ORDER BY rc.rule_candidate_id
        """
    )
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(query, {
            "repo": PROJECT_REPO,
            "started_at": datetime.fromisoformat(RUN_STARTED_AT),
            "finished_at": datetime.fromisoformat(RUN_FINISHED_AT),
        })).mappings().all()

    candidates = []
    for row in rows:
        candidate = dict(row)
        candidate["embedding"] = json.loads(candidate["embedding"])
        candidates.append(candidate)

    pairs = []
    for left_index, left in enumerate(candidates):
        for right in candidates[left_index + 1 :]:
            pairs.append({
                "left_id": left["rule_candidate_id"],
                "left_pr": left["pr_number"],
                "right_id": right["rule_candidate_id"],
                "right_pr": right["pr_number"],
                "cosine": round(cosine(left["embedding"], right["embedding"]), 8),
            })
    pairs.sort(key=lambda pair: (-pair["cosine"], pair["left_id"], pair["right_id"]))

    nearest_neighbors = []
    for candidate in candidates:
        neighbors = [
            pair for pair in pairs
            if candidate["rule_candidate_id"] in (pair["left_id"], pair["right_id"])
        ]
        best = neighbors[0]
        neighbor_id = best["right_id"] if best["left_id"] == candidate["rule_candidate_id"] else best["left_id"]
        neighbor_pr = best["right_pr"] if best["left_id"] == candidate["rule_candidate_id"] else best["left_pr"]
        nearest_neighbors.append({
            "rule_candidate_id": candidate["rule_candidate_id"],
            "pr_number": candidate["pr_number"],
            "nearest_candidate_id": neighbor_id,
            "nearest_pr": neighbor_pr,
            "cosine": best["cosine"],
        })

    sweeps = []
    for threshold in THRESHOLDS:
        clusters = components(candidates, pairs, threshold)
        eligible_clusters = [
            cluster
            for cluster in clusters
            if len({candidate["pr_number"] for candidate in candidates if candidate["rule_candidate_id"] in cluster}) >= 2
        ]
        sweeps.append({
            "threshold": threshold,
            "clusters": clusters,
            "families_after_distinct_pr_gate": eligible_clusters,
        })

    output = {
        "repo": PROJECT_REPO,
        "run_window": {"started_at": RUN_STARTED_AT, "finished_at": RUN_FINISHED_AT},
        "candidate_count": len(candidates),
        "candidates": candidates,
        "pairwise_cosines": pairs,
        "nearest_neighbors": nearest_neighbors,
        "threshold_sweep": sweeps,
    }
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(OUTPUT_PATH)


if __name__ == "__main__":
    asyncio.run(main())
