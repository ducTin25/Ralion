"""F6_RULE_MINING_SPEC.md §4.1/§4.4 — connected-components clustering on rule_text_draft
embedding cosine similarity. Pure, DB-free: takes node ids + vectors, returns components.
Deliberately not HDBSCAN/agglomerative — see SPEC §4.1 for why (union-find is simplest-code-
is-correct-code at the expected family size of 2, and every edge is a literal cosine number
that can be shown in the Review Queue, not a reconstructed dendrogram distance).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def confidence_from_cosine(cosine: float, *, merge_threshold: float, high_threshold: float) -> Literal["HIGH", "MEDIUM"] | None:
    """Derived, display-only mapping (SPEC §4.4) — never persisted as its own column, always
    computed from `RuleEvidence.cluster_edge_cosine_similarity` at read time so there is exactly
    one source of truth for the cosine number."""
    if cosine >= high_threshold:
        return "HIGH"
    if cosine >= merge_threshold:
        return "MEDIUM"
    return None


@dataclass
class _UnionFind:
    parent: dict[str, str] = field(default_factory=dict)

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> bool:
        """Returns True if this call actually merged two different components."""
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        self.parent[ra] = rb
        return True


@dataclass(frozen=True)
class Component:
    node_ids: tuple[str, ...]
    # cosine of the edge that first merged each node into the component; None for the node
    # that never had an incoming edge (RuleEvidence.cluster_edge_cosine_similarity's NULL case,
    # SPEC §5.2). Populated for every node in node_ids.
    edge_cosine: dict[str, float | None]


def cluster_by_cosine(vectors: dict[str, list[float]], *, merge_threshold: float) -> list[Component]:
    """vectors: {node_id: embedding}. Edges considered strongest-first (descending cosine) so
    that when a node has multiple candidate partners above threshold, the displayed "matched at
    cosine=X" edge is its best match, not an arbitrary one. Singleton components (no edge >=
    threshold) are still returned — callers filter to size>=2 for family creation (SPEC §4.1:
    "family = 1 connected component có ≥2 node")."""
    node_ids = list(vectors.keys())
    edges: list[tuple[float, str, str]] = []
    for i in range(len(node_ids)):
        for j in range(i + 1, len(node_ids)):
            a, b = node_ids[i], node_ids[j]
            cosine = cosine_similarity(vectors[a], vectors[b])
            if cosine >= merge_threshold:
                edges.append((cosine, a, b))
    edges.sort(key=lambda e: e[0], reverse=True)

    uf = _UnionFind()
    for node_id in node_ids:
        uf.find(node_id)
    edge_cosine: dict[str, float | None] = dict.fromkeys(node_ids)
    for cosine, a, b in edges:
        if uf.union(a, b):
            # Attribute the merge to whichever side has no incoming edge yet, so exactly one
            # node in a fresh 2-node pair keeps None (the family's "first" node, SPEC §5.2). If
            # both sides already have an incoming edge (only possible when >2 members merge —
            # not observed in SPEC's fixture data, where every family is size 2), fall back to
            # attributing it to b; which side is arbitrary in that case, but still deterministic.
            if edge_cosine[b] is None:
                edge_cosine[b] = cosine
            elif edge_cosine[a] is None:
                edge_cosine[a] = cosine
            else:
                edge_cosine[b] = cosine

    groups: dict[str, list[str]] = {}
    for node_id in node_ids:
        groups.setdefault(uf.find(node_id), []).append(node_id)

    return [
        Component(node_ids=tuple(members), edge_cosine={m: edge_cosine[m] for m in members})
        for members in groups.values()
    ]
