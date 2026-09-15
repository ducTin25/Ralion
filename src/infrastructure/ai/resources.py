from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx
from langchain_openai import ChatOpenAI

from src.ai.providers.embeddings_fake import FakeEmbedder
from src.config import Settings
from src.infrastructure.ai.modal_embedding_adapter import ModalEmbeddingAdapter
from src.infrastructure.ai.openai_completion_adapter import OpenAICompatibleAdapter
from src.infrastructure.reliability import RetryExecutor, RetryPolicy
from src.infrastructure.scheduling.llm_warmup import LlmEndpoint
from src.shared.ai.request_budget import RequestBudget


class AsyncLocalEmbeddingAdapter:
    def __init__(self, embedder) -> None:
        self._embedder = embedder
        self.model_version = embedder.model_version
        self.dimension = embedder.dimension

    async def embed(self, texts):
        if isinstance(self._embedder, FakeEmbedder):
            return await self._embedder.embed(texts)
        return await asyncio.to_thread(self._embedder.embed, texts)

    async def embed_query(self, text: str, _budget: RequestBudget) -> list[float]:
        return (await self.embed([text]))[0]


@dataclass
class AiResources:
    chat_embedding: object
    ingestion_embedding: object
    warmup_embedding: object
    chat_completion: OpenAICompatibleAdapter
    # F5 audit 2026-08-30 (BGK structured-output reliability, Thread C follow-up): a SEPARATE
    # adapter, isolated to AnswerGenerator only -- same provider settings (model, api_key,
    # temperature, timeout, retry policy, connection pool) as `chat_completion`, differing only in
    # `max_tokens` (`Settings.answer_generator_max_output_tokens`). ScopeGate/TurnInterpreter/
    # EvidenceSufficiencyGate keep using `chat_completion` unchanged -- their short single-verdict
    # calls never needed more room, so this does not re-provision them.
    answer_generation_completion: OpenAICompatibleAdapter
    clients: tuple[httpx.AsyncClient, ...]
    # RC-1: the pooled client + base URL the chat completions actually go through, so the
    # warm-up loop fills the same pool generation reads from (see scheduling/llm_warmup.py).
    llm_endpoint: LlmEndpoint | None = None
    _closed: bool = False

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        for client in self.clients:
            await client.aclose()

    def validate_embedding_contract(self) -> None:
        """Guarantee ingestion and retrieval address the same vector space."""
        if (
            self.chat_embedding.model_version != self.ingestion_embedding.model_version
            or self.chat_embedding.dimension != self.ingestion_embedding.dimension
        ):
            raise ValueError("Ingestion and retrieval embedders must use the same model and dimension")


# ChatOpenAI's own default when no base_url is passed; kept here only so the warm-up knows
# which host the pooled connection should be opened against.
_DEFAULT_OPENAI_BASE = "https://api.openai.com/v1"


def create_ai_resources(settings: Settings) -> AiResources:
    executor = RetryExecutor()
    clients: list[httpx.AsyncClient] = []
    if settings.use_fake_embedder:
        embedding = AsyncLocalEmbeddingAdapter(FakeEmbedder())
        chat_embedding = embedding
        ingestion_embedding = embedding
        warmup_embedding = embedding
    else:
        # keepalive_expiry is the difference between a ~700ms embed and a ~1550ms one: without
        # it httpx drops the pooled connection after 5s idle, so every chat turn re-ran the
        # TCP+TLS handshake to Modal and spent most of its embedding budget on it.
        chat_http = httpx.AsyncClient(
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=settings.chat_http_keepalive_expiry_seconds,
            )
        )
        ingestion_http = httpx.AsyncClient(limits=httpx.Limits(max_connections=8, max_keepalive_connections=4))
        clients.extend((chat_http, ingestion_http))
        chat_embedding = ModalEmbeddingAdapter(
            settings.bge_m3_endpoint,
            settings.bge_m3_api_key,
            chat_http,
            RetryPolicy(
                settings.chat_embedding_max_attempts,
                settings.chat_embedding_connect_timeout_seconds,
                settings.chat_embedding_read_timeout_seconds,
                settings.chat_embedding_backoff_initial_seconds,
                settings.chat_embedding_backoff_multiplier,
                settings.chat_embedding_backoff_max_seconds,
            ),
            executor,
        )
        ingestion_embedding = ModalEmbeddingAdapter(
            settings.bge_m3_endpoint,
            settings.bge_m3_api_key,
            ingestion_http,
            RetryPolicy(
                settings.ingestion_embedding_max_attempts,
                settings.ingestion_embedding_connect_timeout_seconds,
                settings.ingestion_embedding_read_timeout_seconds,
                settings.ingestion_embedding_backoff_initial_seconds,
                settings.ingestion_embedding_backoff_multiplier,
                settings.ingestion_embedding_backoff_max_seconds,
            ),
            executor,
            operation_budget_seconds=settings.ingestion_overall_deadline_seconds,
        )
        # The Starter-budget Modal deployment scales the L4 to zero when idle, so this ping
        # (enabled by default, see chat_embedding_warmup_enabled) keeps a container warm for
        # every embedding-dependent use case -- chat, PM/HR upload, GitHub sync -- not just
        # chat's own retry budget. Shares the chat connection pool.
        warmup_embedding = ModalEmbeddingAdapter(
            settings.bge_m3_endpoint,
            settings.bge_m3_api_key,
            chat_http,
            RetryPolicy(
                1,
                # A scaled-to-zero Modal deployment may not accept the initial TCP/TLS
                # connection until its GPU container has started.  The interactive chat
                # policy rightly fails fast, but this background warm-up is specifically
                # allowed to wait for that cold start.
                settings.chat_embedding_warmup_timeout_seconds,
                settings.chat_embedding_warmup_timeout_seconds,
                0.0,
                1.0,
                0.0,
            ),
            executor,
            operation_budget_seconds=settings.chat_embedding_warmup_timeout_seconds,
        )

    llm_http = httpx.AsyncClient(
        limits=httpx.Limits(
            max_connections=20,
            max_keepalive_connections=10,
            keepalive_expiry=settings.chat_http_keepalive_expiry_seconds,
        )
    )
    clients.append(llm_http)
    # Unit/API tests use fake collaborators and must not require a real provider
    # credential merely to construct the application dependency graph. The
    # placeholder is confined to APP_ENV=test; no request is sent by it.
    llm_api_key = settings.openrouter_api_key or settings.openai_api_key
    if settings.app_env == "test" and not llm_api_key:
        llm_api_key = "test-only-placeholder"
    kwargs = {
        "model": settings.openrouter_model or settings.model_name,
        "api_key": llm_api_key,
        "temperature": 0,
        "max_tokens": settings.chat_max_output_tokens,
        "max_retries": 0,
        "timeout": httpx.Timeout(
            settings.chat_llm_read_timeout_seconds, connect=settings.chat_llm_connect_timeout_seconds
        ),
        "http_async_client": llm_http,
    }
    if settings.openrouter_api_key:
        kwargs["base_url"] = settings.openrouter_api_base
    provider = ChatOpenAI(**kwargs)
    retry_policy = RetryPolicy(
        settings.chat_llm_max_attempts,
        settings.chat_llm_connect_timeout_seconds,
        settings.chat_llm_read_timeout_seconds,
        settings.chat_llm_backoff_initial_seconds,
        settings.chat_llm_backoff_multiplier,
        settings.chat_llm_backoff_max_seconds,
    )
    completion = OpenAICompatibleAdapter(
        provider,
        retry_policy,
        executor,
        reasoning_effort_enabled=settings.chat_reasoning_effort_enabled,
        reasoning_effort_override=settings.chat_reasoning_effort_override,
    )
    # F5 audit 2026-08-30 (BGK structured-output reliability, Thread C follow-up): AnswerGenerator
    # gets its own provider instance, identical to `provider` above (same model/api_key/
    # temperature/timeout/retry policy, same pooled `llm_http` client -- no new connection pool)
    # except for `max_tokens`. `0` (falsy) means unconfigured -- same fallback idiom as
    # `openrouter_model or model_name` above -- and falls back to the shared ceiling.
    answer_generator_kwargs = {
        **kwargs,
        "max_tokens": settings.answer_generator_max_output_tokens or settings.chat_max_output_tokens,
    }
    answer_generation_completion = OpenAICompatibleAdapter(
        ChatOpenAI(**answer_generator_kwargs),
        retry_policy,
        executor,
        reasoning_effort_enabled=settings.chat_reasoning_effort_enabled,
        reasoning_effort_override=settings.chat_reasoning_effort_override,
    )
    resources = AiResources(
        chat_embedding,
        ingestion_embedding,
        warmup_embedding,
        completion,
        answer_generation_completion,
        tuple(clients),
        LlmEndpoint(llm_http, kwargs.get("base_url", _DEFAULT_OPENAI_BASE)),
    )
    resources.validate_embedding_contract()
    return resources
