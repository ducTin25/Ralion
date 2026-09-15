"""Load chunking and embedding parameters from the repository config."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


@lru_cache(maxsize=1)
def load_chunking_config(path: str | Path = "config/chunking_params.yaml") -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open(encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    if not isinstance(config, dict) or "policy" not in config or "embedding" not in config:
        raise ValueError("Chunking config must define policy and embedding sections")
    return config


def policy_params(config: dict[str, Any] | None = None) -> dict[str, Any]:
    return (config or load_chunking_config())["policy"]


def embedding_params(config: dict[str, Any] | None = None) -> dict[str, Any]:
    return (config or load_chunking_config())["embedding"]


def retrieval_params(config: dict[str, Any] | None = None) -> dict[str, Any]:
    retrieval = (config or load_chunking_config()).get("retrieval")
    if not isinstance(retrieval, dict):
        raise ValueError("Chunking config must define a retrieval section")
    return retrieval


def rule_mining_params(config: dict[str, Any] | None = None) -> dict[str, Any]:
    rule_mining = (config or load_chunking_config()).get("rule_mining")
    if not isinstance(rule_mining, dict):
        raise ValueError("Chunking config must define a rule_mining section")
    return rule_mining
