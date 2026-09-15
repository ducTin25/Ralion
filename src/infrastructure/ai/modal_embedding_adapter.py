from __future__ import annotations

import httpx

from src.ai.providers.embeddings import EMBEDDING_DIMENSION, EMBEDDING_MODEL_VERSION
from src.infrastructure.reliability import RetryExecutor, RetryPolicy
from src.shared.ai.external_failures import ExternalFailureCode, ExternalServiceFailure
from src.shared.ai.request_budget import RequestBudget

# Hard limit of the Modal /embed endpoint itself (measured: 422 "List should have at most 32
# items"), not a tunable — every batch sent to Modal must be chunked to this size or smaller.
MAX_EMBED_BATCH_SIZE = 32


class ModalEmbeddingAdapter:
    model_version = EMBEDDING_MODEL_VERSION
    dimension = EMBEDDING_DIMENSION

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        client: httpx.AsyncClient,
        policy: RetryPolicy,
        executor: RetryExecutor,
        *,
        operation_budget_seconds: float = 600.0,
    ) -> None:
        if not endpoint or not api_key:
            raise ValueError("Remote BGE-M3 endpoint and API key are required")
        self._url = f"{endpoint.rstrip('/')}/embed"
        self._api_key = api_key
        self._client = client
        self._policy = policy
        self._executor = executor
        self._operation_budget_seconds = operation_budget_seconds

    async def embed_query(self, text: str, budget: RequestBudget) -> list[float]:
        vectors = await self._embed([text], budget)
        return vectors[0]

    async def embed(self, texts) -> list[list[float]]:
        texts = list(texts)
        for index, text in enumerate(texts):
            if not text.strip():
                raise ValueError(f"ModalEmbeddingAdapter.embed: blank text at index {index}")

        # Ingestion owns a separate adapter/policy; this budget is cumulative for the whole
        # logical embed() call even though it may now take several physical HTTP requests
        # (Modal's /embed endpoint rejects more than MAX_EMBED_BATCH_SIZE texts per call) —
        # RequestBudget is designed to be shared/charged across multiple _embed() calls.
        budget = RequestBudget(self._operation_budget_seconds, self._operation_budget_seconds, 0.0)
        vectors: list[list[float]] = []
        for start in range(0, len(texts), MAX_EMBED_BATCH_SIZE):
            chunk = texts[start : start + MAX_EMBED_BATCH_SIZE]
            # No partial-result recovery on failure by design: if a chunk fails terminally,
            # this raises and the caller gets nothing rather than a shorter, silently
            # misaligned vector list (the "batch failure must not corrupt the evidence-unit
            # <-> embedding mapping" requirement).
            vectors.extend(await self._embed(chunk, budget))
        return vectors

    async def _embed(self, texts: list[str], budget: RequestBudget) -> list[list[float]]:
        async def attempt(connect_timeout: float, read_timeout: float) -> list[list[float]]:
            try:
                response = await self._client.post(
                    self._url,
                    json={"texts": texts},
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    timeout=httpx.Timeout(read_timeout, connect=connect_timeout),
                )
            except httpx.TimeoutException as exc:
                raise ExternalServiceFailure(
                    "embedding", ExternalFailureCode.TIMEOUT, True, timeout_scope="attempt"
                ) from exc
            except (httpx.ConnectError, httpx.NetworkError) as exc:
                raise ExternalServiceFailure("embedding", ExternalFailureCode.CONNECTION, True) from exc
            if response.status_code in (401, 403):
                raise ExternalServiceFailure("embedding", ExternalFailureCode.AUTHENTICATION, False)
            if response.status_code == 429:
                retry_after = _retry_after(response)
                raise ExternalServiceFailure(
                    "embedding", ExternalFailureCode.RATE_LIMITED, True, retry_after_seconds=retry_after
                )
            if response.status_code in (408, 500, 502, 503, 504):
                code = ExternalFailureCode.TIMEOUT if response.status_code == 408 else ExternalFailureCode.UNAVAILABLE
                raise ExternalServiceFailure(
                    "embedding", code, True, timeout_scope="attempt" if response.status_code == 408 else None
                )
            if 400 <= response.status_code < 500:
                raise ExternalServiceFailure("embedding", ExternalFailureCode.BAD_REQUEST, False)
            if response.status_code >= 500:
                raise ExternalServiceFailure("embedding", ExternalFailureCode.UNAVAILABLE, True)
            try:
                data = response.json()
            except ValueError as exc:
                raise ExternalServiceFailure("embedding", ExternalFailureCode.PROTOCOL, False) from exc
            if data.get("model_version") != self.model_version or data.get("dimension") != self.dimension:
                raise ExternalServiceFailure("embedding", ExternalFailureCode.PROTOCOL, False)
            vectors = data.get("vectors")
            if (
                not isinstance(vectors, list)
                or len(vectors) != len(texts)
                or any(not isinstance(v, list) or len(v) != self.dimension for v in vectors)
            ):
                raise ExternalServiceFailure("embedding", ExternalFailureCode.PROTOCOL, False)
            return vectors

        return await self._executor.run(
            attempt, service="embedding", stage="embedding", budget=budget, policy=self._policy
        )


def _retry_after(response: httpx.Response) -> float | None:
    try:
        return max(0.0, float(response.headers["Retry-After"]))
    except (KeyError, ValueError):
        return None
