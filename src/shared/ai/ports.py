from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from src.shared.ai.request_budget import RequestBudget


@dataclass(frozen=True)
class ChatCompletion:
    content: str
    response_metadata: dict[str, Any] = field(default_factory=dict)
    usage_metadata: dict[str, Any] = field(default_factory=dict)


class ChatCompletionPort(Protocol):
    async def complete(
        self,
        messages: Sequence[tuple[str, str]],
        budget: RequestBudget,
        operation: Literal[
            "query_rewrite",
            "answer",
            "repair",
            "scope_gate",
            "evidence_sufficiency_gate",
            "conversation_answer",
            "turn_interpreter",
        ],
    ) -> ChatCompletion: ...


class QueryEmbeddingPort(Protocol):
    model_version: str
    dimension: int

    async def embed_query(self, text: str, budget: RequestBudget) -> list[float]: ...
