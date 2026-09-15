from __future__ import annotations

from src.modules.knowledge.mining.clustering import (
    cluster_by_cosine,
    confidence_from_cosine,
    cosine_similarity,
)


def test_cosine_similarity_identical_vectors_is_one() -> None:
    v = [1.0, 2.0, 3.0]
    assert cosine_similarity(v, v) == 1.0


def test_cosine_similarity_orthogonal_vectors_is_zero() -> None:
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_two_similar_nodes_merge_into_one_component() -> None:
    vectors = {"a": [1.0, 0.0], "b": [0.99, 0.01]}
    components = cluster_by_cosine(vectors, merge_threshold=0.70)
    assert len(components) == 1
    assert set(components[0].node_ids) == {"a", "b"}


def test_dissimilar_nodes_stay_in_separate_singleton_components() -> None:
    vectors = {"a": [1.0, 0.0], "b": [0.0, 1.0]}
    components = cluster_by_cosine(vectors, merge_threshold=0.70)
    assert len(components) == 2
    assert all(len(c.node_ids) == 1 for c in components)


def test_edge_cosine_has_exactly_one_null_per_two_node_component() -> None:
    vectors = {"a": [1.0, 0.0], "b": [0.99, 0.01]}
    components = cluster_by_cosine(vectors, merge_threshold=0.70)
    component = components[0]
    none_count = sum(1 for v in component.edge_cosine.values() if v is None)
    assigned_count = sum(1 for v in component.edge_cosine.values() if v is not None)
    assert none_count == 1
    assert assigned_count == 1


def test_singleton_component_edge_cosine_is_null() -> None:
    vectors = {"a": [1.0, 0.0]}
    components = cluster_by_cosine(vectors, merge_threshold=0.70)
    assert components[0].edge_cosine == {"a": None}


def test_confidence_from_cosine_mapping() -> None:
    assert confidence_from_cosine(0.90, merge_threshold=0.70, high_threshold=0.85) == "HIGH"
    assert confidence_from_cosine(0.85, merge_threshold=0.70, high_threshold=0.85) == "HIGH"
    assert confidence_from_cosine(0.75, merge_threshold=0.70, high_threshold=0.85) == "MEDIUM"
    assert confidence_from_cosine(0.70, merge_threshold=0.70, high_threshold=0.85) == "MEDIUM"
    assert confidence_from_cosine(0.69, merge_threshold=0.70, high_threshold=0.85) is None
