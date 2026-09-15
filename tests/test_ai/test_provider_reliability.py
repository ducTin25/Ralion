from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import httpx
import openai
import pytest

from src.ai.providers.embeddings import EMBEDDING_DIMENSION, EMBEDDING_MODEL_VERSION
from src.config import Settings
from src.infrastructure.ai.modal_embedding_adapter import ModalEmbeddingAdapter
from src.infrastructure.ai.openai_completion_adapter import OpenAICompatibleAdapter
from src.infrastructure.ai.resources import create_ai_resources
from src.infrastructure.reliability import RetryExecutor, RetryPolicy
from src.shared.ai.external_failures import ExternalFailureCode, ExternalServiceFailure
from src.shared.ai.request_budget import RequestBudget


def _policy(attempts: int = 2) -> RetryPolicy:
    return RetryPolicy(attempts, 0.1, 0.1, 0.0, 1.0, 0.0)


def _embedding_payload(vectors: list[list[float]]) -> dict[str, object]:
    return {
        "model_version": EMBEDDING_MODEL_VERSION,
        "dimension": EMBEDDING_DIMENSION,
        "vectors": vectors,
    }


# ---------------------------------------------------------------- embed() batching/validation
# F6 Phase 7: Modal's real /embed endpoint caps requests at 32 texts and rejects blank strings
# (measured directly, see CHANGE_LOG.md) — ModalEmbeddingAdapter.embed() must chunk and
# pre-validate so callers never see a cryptic batch-level 400/422 from an oversized/blank input.


@pytest.mark.asyncio
async def test_embed_chunks_batches_over_32_and_preserves_input_order() -> None:
    request_sizes: list[int] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        texts = json.loads(request.content)["texts"]
        request_sizes.append(len(texts))
        # Each vector encodes which input index it came from, so the test can verify the
        # final list is reassembled in the caller's original order.
        vectors = [[float(int(t.split("-")[1]))] * 1024 for t in texts]
        return httpx.Response(200, json=_embedding_payload(vectors), request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = ModalEmbeddingAdapter("https://embed.test", "secret", client, _policy(), RetryExecutor())
        texts = [f"text-{i}" for i in range(70)]
        vectors = await adapter.embed(texts)

    assert request_sizes == [32, 32, 6]  # 70 texts chunked into <=32-item batches
    assert len(vectors) == 70
    assert [v[0] for v in vectors] == [float(i) for i in range(70)]  # order preserved


@pytest.mark.asyncio
async def test_embed_rejects_blank_text_without_any_network_call() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=_embedding_payload([[0.0] * 1024]), request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = ModalEmbeddingAdapter("https://embed.test", "secret", client, _policy(), RetryExecutor())
        with pytest.raises(ValueError, match="blank text at index 1"):
            await adapter.embed(["valid one", "   ", "valid two"])

    assert calls == 0  # fails fast locally, never reaches Modal


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    (("model_version", "BAAI/bge-m3@different"), ("dimension", 384)),
)
async def test_embed_rejects_remote_model_contract_mismatch(field: str, value: object) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = _embedding_payload([[0.0] * EMBEDDING_DIMENSION])
        payload[field] = value
        return httpx.Response(200, json=payload, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = ModalEmbeddingAdapter("https://embed.test", "secret", client, _policy(), RetryExecutor())
        with pytest.raises(ExternalServiceFailure) as captured:
            await adapter.embed_query("query", RequestBudget(5, 5, 0))

    assert captured.value.code is ExternalFailureCode.PROTOCOL


@pytest.mark.asyncio
async def test_embed_batch_failure_raises_instead_of_returning_misaligned_partial_result() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json=_embedding_payload([[0.0] * 1024] * 32), request=request)
        return httpx.Response(400, request=request)  # second chunk fails terminally

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = ModalEmbeddingAdapter("https://embed.test", "secret", client, _policy(), RetryExecutor())
        texts = [f"text-{i}" for i in range(40)]  # 2 chunks: 32 + 8
        with pytest.raises(ExternalServiceFailure) as captured:
            await adapter.embed(texts)

    assert captured.value.code is ExternalFailureCode.BAD_REQUEST
    assert calls == 2  # first chunk succeeded, second failed — no silently-shortened result


@pytest.mark.asyncio
async def test_sequential_embeddings_reuse_the_same_async_client() -> None:
    requests = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, json=_embedding_payload([[0.0] * 1024]), request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = ModalEmbeddingAdapter("https://embed.test", "secret", client, _policy(), RetryExecutor())
    budget = RequestBudget(5, 5, 0)
    await adapter.embed_query("one", budget)
    await adapter.embed_query("two", budget)
    assert requests == 2
    assert adapter._client is client
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 502, 503])
async def test_retryable_embedding_statuses_retry_once(status: int) -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(status, request=request)
        return httpx.Response(200, json=_embedding_payload([[0.0] * 1024]), request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = ModalEmbeddingAdapter("https://embed.test", "secret", client, _policy(), RetryExecutor())
        assert len(await adapter.embed_query("query", RequestBudget(5, 5, 0))) == 1024
    assert calls == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,code", [(400, ExternalFailureCode.BAD_REQUEST), (401, ExternalFailureCode.AUTHENTICATION)]
)
async def test_terminal_embedding_statuses_never_retry(status: int, code: ExternalFailureCode) -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = ModalEmbeddingAdapter("https://embed.test", "secret", client, _policy(), RetryExecutor())
        with pytest.raises(ExternalServiceFailure) as captured:
            await adapter.embed_query("query", RequestBudget(5, 5, 0))
    assert captured.value.code is code
    assert calls == 1


@pytest.mark.asyncio
async def test_cancelled_operation_is_not_wrapped_or_retried() -> None:
    calls = 0

    async def cancelled(_connect: float, _read: float):
        nonlocal calls
        calls += 1
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await RetryExecutor().run(
            cancelled, service="llm", stage="llm", budget=RequestBudget(5, 0, 5), policy=_policy()
        )
    assert calls == 1


@pytest.mark.asyncio
async def test_resources_separate_pools_disable_sdk_retry_and_close_once() -> None:
    settings = Settings(
        _env_file=None,
        openai_api_key="test",
        bge_m3_endpoint="https://embed.test",
        bge_m3_api_key="secret",
        use_fake_embedder=False,
    )
    resources = create_ai_resources(settings)
    assert resources.chat_embedding._client is not resources.ingestion_embedding._client
    assert resources.chat_completion._provider.max_retries == 0
    assert resources.chat_completion._provider.max_tokens == settings.chat_max_output_tokens
    # F5 audit 2026-08-30 (BGK structured-output reliability, Thread C follow-up): AnswerGenerator
    # gets its own provider, same pool/retry/reasoning-effort wiring, higher `max_tokens` only.
    assert resources.answer_generation_completion is not resources.chat_completion
    assert (
        resources.answer_generation_completion._provider.max_tokens
        == settings.answer_generator_max_output_tokens
    )
    assert resources.answer_generation_completion._provider.max_retries == 0
    assert (
        resources.answer_generation_completion._provider.http_async_client
        is resources.chat_completion._provider.http_async_client
    )  # no new connection pool
    assert resources.llm_endpoint is not None
    assert resources.llm_endpoint.client is resources.chat_completion._provider.http_async_client
    clients = resources.clients
    await resources.aclose()
    await resources.aclose()
    assert all(client.is_closed for client in clients)


@pytest.mark.asyncio
async def test_answer_generator_max_output_tokens_falls_back_to_shared_ceiling_when_unset() -> None:
    """F5 audit 2026-08-30: `0` (unset) falls back to `chat_max_output_tokens` -- same idiom as
    `openrouter_model or model_name`."""
    settings = Settings(
        _env_file=None,
        openai_api_key="test",
        bge_m3_endpoint="https://embed.test",
        bge_m3_api_key="secret",
        use_fake_embedder=False,
        answer_generator_max_output_tokens=0,
    )
    resources = create_ai_resources(settings)
    assert resources.answer_generation_completion._provider.max_tokens == settings.chat_max_output_tokens
    await resources.aclose()


@pytest.mark.asyncio
async def test_warmup_uses_patient_policy_and_the_chat_connection_pool() -> None:
    settings = Settings(
        _env_file=None,
        openai_api_key="test",
        bge_m3_endpoint="https://embed.test",
        bge_m3_api_key="secret",
        use_fake_embedder=False,
        chat_embedding_warmup_timeout_seconds=60,
    )
    resources = create_ai_resources(settings)
    try:
        assert resources.warmup_embedding._client is resources.chat_embedding._client
        assert resources.warmup_embedding._policy.max_attempts == 1
        assert resources.warmup_embedding._policy.connect_timeout_seconds == 60
        assert resources.warmup_embedding._policy.read_timeout_seconds == 60
        assert resources.chat_embedding._policy.read_timeout_seconds == 3
    finally:
        await resources.aclose()


@pytest.mark.asyncio
async def test_chat_pools_hold_keepalive_connections_across_turns() -> None:
    """Chat turns are seconds-to-minutes apart; httpx's 5s default keepalive_expiry threw the
    pooled connection away between them, so every question re-paid the TCP+TLS handshake to
    Modal (measured: 562ms median handshake, 1547ms fresh embed vs 688-828ms on a reused
    connection).  That handshake alone consumed most of the old 3s embedding budget and was
    the timeout that produced the embedding_unavailable/system_error fallbacks."""
    settings = Settings(
        _env_file=None,
        openai_api_key="test",
        bge_m3_endpoint="https://embed.test",
        bge_m3_api_key="secret",
        use_fake_embedder=False,
    )
    resources = create_ai_resources(settings)
    try:
        chat_pool = resources.chat_embedding._client
        # Must outlive the gap between two questions, not httpx's 5s default.
        assert chat_pool._transport._pool._keepalive_expiry == settings.chat_http_keepalive_expiry_seconds
        assert settings.chat_http_keepalive_expiry_seconds >= 60.0
    finally:
        await resources.aclose()


def test_chat_embedding_timeouts_cover_measured_modal_latency() -> None:
    """Sized from the deployed endpoint, not guessed: the connect timeout has to clear a
    562ms (609ms max) handshake and the read timeout ~1s of embed compute.  The previous
    0.75s/1.5s pair left ~140ms of margin and fired on ordinary network jitter."""
    settings = Settings(_env_file=None, openai_api_key="test")
    assert settings.chat_embedding_connect_timeout_seconds >= 1.5
    assert settings.chat_embedding_read_timeout_seconds >= 2.5
    # A retry must fit inside the stage budget, otherwise the second attempt is cut off by
    # the budget guard and reported as a timeout it never actually got to run.
    assert (
        settings.chat_embedding_budget_seconds
        >= settings.chat_embedding_max_attempts * settings.chat_embedding_read_timeout_seconds
    )
    # The stage budgets must still fit under the overall deadline safety ceiling.
    assert (
        settings.chat_embedding_budget_seconds + settings.chat_persistence_reserve_seconds
        < settings.chat_overall_deadline_seconds
    )


def test_request_budget_is_cumulative_across_operations() -> None:
    now = [0.0]
    budget = RequestBudget(10, 4, 5, clock=lambda: now[0])
    first = now[0]
    now[0] = 1.5
    budget.charge("embedding", first)
    assert budget.remaining_embedding() == pytest.approx(2.5)
    second = now[0]
    now[0] = 2.5
    budget.charge("embedding", second)
    assert budget.remaining_embedding() == pytest.approx(1.5)


class _LlmProvider:
    def __init__(self, outcomes) -> None:
        self.outcomes = iter(outcomes)
        self.calls = 0

    async def ainvoke(self, _messages):
        self.calls += 1
        outcome = next(self.outcomes)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _response(status: int, **headers: str) -> httpx.Response:
    return httpx.Response(status, headers=headers, request=httpx.Request("POST", "https://llm.test"))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure,code",
    [
        (openai.BadRequestError("bad", response=_response(400), body=None), ExternalFailureCode.BAD_REQUEST),
        (openai.AuthenticationError("auth", response=_response(401), body=None), ExternalFailureCode.AUTHENTICATION),
    ],
)
async def test_terminal_llm_failures_never_retry(failure, code) -> None:
    provider = _LlmProvider([failure])
    adapter = OpenAICompatibleAdapter(provider, _policy(), RetryExecutor())
    with pytest.raises(ExternalServiceFailure) as captured:
        await adapter.complete([], RequestBudget(5, 0, 5), "answer")
    assert captured.value.code is code
    assert provider.calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        openai.APIConnectionError(request=httpx.Request("POST", "https://llm.test")),
        openai.InternalServerError("down", response=_response(503), body=None),
    ],
)
async def test_connect_and_immediate_503_retry_once(failure) -> None:
    provider = _LlmProvider(
        [failure, type("Response", (), {"content": "ok", "response_metadata": {}, "usage_metadata": {}})()]
    )
    adapter = OpenAICompatibleAdapter(provider, _policy(), RetryExecutor())
    result = await adapter.complete([], RequestBudget(5, 0, 5), "answer")
    assert result.content == "ok"
    assert provider.calls == 2


@pytest.mark.asyncio
async def test_llm_read_timeout_after_send_does_not_retry() -> None:
    provider = _LlmProvider([openai.APITimeoutError(request=httpx.Request("POST", "https://llm.test"))])
    adapter = OpenAICompatibleAdapter(provider, _policy(), RetryExecutor())
    with pytest.raises(ExternalServiceFailure) as captured:
        await adapter.complete([], RequestBudget(5, 0, 5), "answer")
    assert captured.value.code is ExternalFailureCode.TIMEOUT
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_llm_429_retries_only_with_retry_after_inside_budget() -> None:
    success = type("Response", (), {"content": "ok", "response_metadata": {}, "usage_metadata": {}})()
    without_hint = _LlmProvider([openai.RateLimitError("rate", response=_response(429), body=None)])
    adapter = OpenAICompatibleAdapter(without_hint, _policy(), RetryExecutor())
    with pytest.raises(ExternalServiceFailure):
        await adapter.complete([], RequestBudget(5, 0, 5), "answer")
    assert without_hint.calls == 1

    with_hint = _LlmProvider(
        [openai.RateLimitError("rate", response=_response(429, **{"Retry-After": "0"}), body=None), success]
    )
    adapter = OpenAICompatibleAdapter(with_hint, _policy(), RetryExecutor())
    assert (await adapter.complete([], RequestBudget(5, 0, 5), "answer")).content == "ok"
    assert with_hint.calls == 2


# ------------------------------------------------------------------ reasoning effort per operation
# 2026-08-26, measured. `Settings.model_name` is `gpt-5-mini`, a REASONING model, and nothing set
# `reasoning_effort` -- so every call ran at the implicit `medium`. One `turn_interpreter` verdict
# measured 12615 ms with 960 reasoning_tokens behind ~68 tokens of visible JSON. Three judges
# share that provider with a ~3s budget each, so the interactive path structurally could not meet
# it, and because `turn_interpreter` fails OPEN the symptom was silent: Phase 2 routing reverting
# to KNOWLEDGE on 16% of real turns.
#
# The effort is NOT one value for all judges, and that distinction is the point of these tests.
# A first pass set everything to `minimal` on the strength of a 6-case check whose cases were all
# STANDALONE utterances -- it never exercised coreference, and `minimal` was then measured to
# mis-route "cái đó áp dụng từ khi nào?" to CONVERSATION 3/3. See
# `_REASONING_EFFORT_BY_OPERATION` for the per-operation measurements.
#
# These tests pin the WIRING. Whether each level preserves verdict quality is live-eval work,
# recorded in CHANGE_LOG.md.


class _KwargRecordingProvider:
    """Records the per-call kwargs the adapter passes to `ainvoke`, which is the whole contract
    under test here. `model_name` is an attribute because the adapter reads it to decide whether
    the configured model understands `reasoning_effort` at all."""

    def __init__(self, model_name: str = "gpt-5-mini") -> None:
        self.model_name = model_name
        self.kwargs: list[dict[str, object]] = []

    async def ainvoke(self, _messages, **kwargs):
        self.kwargs.append(kwargs)
        return SimpleNamespace(content="{}", response_metadata={}, usage_metadata={})


def _enabled_adapter(provider) -> OpenAICompatibleAdapter:
    return OpenAICompatibleAdapter(provider, _policy(), RetryExecutor(), reasoning_effort_enabled=True)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "effort"),
    [
        # One binary verdict about one utterance -- nothing to relate, measured 6/6 at `minimal`.
        ("scope_gate", "minimal"),
        ("query_rewrite", "minimal"),
        ("support_reply", "minimal"),
        # 4/4 correct at minimal across sufficient/insufficient/off-topic/specific-value,
        # including the "bao nhiêu TIỀN" weakening case, and faster than `low` on a realistic
        # 10-candidate prompt -- which matters because this gate fails CLOSED.
        ("evidence_sufficiency_gate", "minimal"),
        # Resolves references ACROSS turns. `minimal` was MEASURED to break this (coreference
        # follow-up -> CONVERSATION 3/3); `low` is the measured-correct floor, not a preference.
        # If this ever gets lowered to "minimal", follow-up questions start mis-routing again.
        ("turn_interpreter", "low"),
    ],
)
async def test_each_operation_gets_the_effort_its_task_needs(operation, effort) -> None:
    provider = _KwargRecordingProvider()

    await _enabled_adapter(provider).complete([], RequestBudget(5, 0, 5), operation)

    assert provider.kwargs == [{"reasoning_effort": effort}]


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["answer", "repair", "conversation_answer"])
async def test_generation_runs_with_reasoning_off_once_it_was_measured(operation) -> None:
    """Generation was deliberately EXCLUDED in the first pass, on the honest grounds that it had
    not been measured. It was measured on 2026-08-26 after a production `system_error`, and the
    result was not the expected "reasoning costs latency but buys quality" trade: at the provider
    default it took 16730ms, and an explicit `medium` run produced NO USABLE CLAIMS at all --
    reasoning tokens share the `chat_max_output_tokens` ceiling with the answer, so deliberation
    truncates the claims JSON it is supposed to improve.

    So this is not "we gave up and made it fast". More reasoning was actively destroying the
    output here. Re-measured across three questions, `minimal` matched or beat `low` on every
    axis available without an eval harness -- 0 retries, every claim citation-validated, claim
    counts 4/2/1 vs 3/2/1 -- while being faster, so generation runs with reasoning OFF
    (`reasoning_tokens: 0`; this model rejects `reasoning_effort="none"` outright).

    The safety floor does not rest on this setting: every claim is citation-validated after
    generation, so a worse answer here can be thinner, never ungrounded."""
    provider = _KwargRecordingProvider()

    await _enabled_adapter(provider).complete([], RequestBudget(5, 0, 5), operation)

    assert provider.kwargs == [{"reasoning_effort": "minimal"}]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "model", ["gpt-4o-mini", "deepseek-chat", "anthropic/claude-sonnet-4", "mistral-large"]
)
async def test_non_reasoning_models_never_receive_the_parameter(model) -> None:
    """`reasoning_effort` sent to a model that does not know it is a 400 -- that would take chat
    down on every turn rather than degrade it. The provider is configurable
    (`openrouter_model or model_name`), so the override is gated on a known family, including the
    OpenRouter "vendor/model" id form."""
    provider = _KwargRecordingProvider(model_name=model)

    await _enabled_adapter(provider).complete([], RequestBudget(5, 0, 5), "scope_gate")

    assert provider.kwargs == [{}]


@pytest.mark.asyncio
async def test_disabled_setting_restores_the_provider_default_everywhere() -> None:
    """`chat_reasoning_effort_enabled=False` is the documented rollback -- config-only, no code
    change, the same shape `knowledge_policy_enabled` uses."""
    provider = _KwargRecordingProvider()
    adapter = OpenAICompatibleAdapter(
        provider, _policy(), RetryExecutor(), reasoning_effort_enabled=False
    )

    await adapter.complete([], RequestBudget(5, 0, 5), "turn_interpreter")

    assert provider.kwargs == [{}]


@pytest.mark.asyncio
async def test_default_construction_passes_no_kwargs() -> None:
    """Every pre-existing call site constructs the adapter without this keyword, so the default
    must be off."""
    provider = _KwargRecordingProvider()
    adapter = OpenAICompatibleAdapter(provider, _policy(), RetryExecutor())

    await adapter.complete([], RequestBudget(5, 0, 5), "turn_interpreter")

    assert provider.kwargs == [{}]


def _settings(**overrides) -> Settings:
    return Settings(
        _env_file=None,
        openai_api_key="test",
        bge_m3_endpoint="https://embed.test",
        bge_m3_api_key="secret",
        use_fake_embedder=False,
        **overrides,
    )


@pytest.mark.asyncio
async def test_resources_wires_the_setting_through_for_a_reasoning_model() -> None:
    """A config key with no reader is a dead key (CLAUDE.md). Pin the one path that reads it.

    The model is passed EXPLICITLY rather than relying on the default: the default moved to
    gpt-4o-mini on 2026-08-26, and a test that silently followed it would stop exercising this
    wiring at all while still passing."""
    settings = _settings(model_name="gpt-5-mini", chat_reasoning_effort_enabled=True)
    resources = create_ai_resources(settings)
    try:
        assert resources.chat_completion._reasoning_effort_enabled is True
    finally:
        await resources.aclose()


@pytest.mark.asyncio
async def test_the_shipped_default_model_uses_luna_with_no_reasoning() -> None:
    settings = _settings(chat_reasoning_effort_enabled=True)
    assert settings.model_name == "gpt-5.6-luna"
    resources = create_ai_resources(settings)
    try:
        assert resources.chat_completion._reasoning_effort_enabled is True
        assert resources.chat_completion._call_kwargs("turn_interpreter") == {"reasoning_effort": "none"}
    finally:
        await resources.aclose()


def test_every_stage_cap_fits_inside_the_request_llm_budget() -> None:
    """The failure that produced trace 72e4e5ed. A KNOWLEDGE turn makes four sequential LLM calls;
    if their timeouts can sum past `chat_llm_budget_seconds`, the budget does not make the turn
    faster, it silently decides which stage gets starved -- and because generation runs LAST, the
    starved one is always the call that writes the answer. Live, generation got 10s of a 20s
    budget, needed 15-17s, and returned `system_error`.

    This guards the arithmetic, not any single number: raise a stage timeout without raising the
    budget and this fails."""
    from src.ai.orchestration.evidence_sufficiency_gate import EvidenceSufficiencyGateConfig
    from src.ai.orchestration.scope_gate import ScopeGateConfig
    from src.ai.orchestration.turn_interpreter import TurnInterpreterConfig

    settings = _settings()
    # `scope_gate` and `turn_interpreter` run CONCURRENTLY (one `asyncio.gather` in
    # `_ask_with_interpreter`), so the pair costs the LONGER of the two, not their sum -- and
    # `RequestBudget.concurrent` is what makes the budget agree with that. ESG stays sequential
    # after them.
    judges = max(
        ScopeGateConfig.from_config().timeout_seconds,
        TurnInterpreterConfig.from_config().timeout_seconds,
    ) + EvidenceSufficiencyGateConfig.from_config().timeout_seconds
    # Generation measured at `low` against a realistic 10-candidate prompt: 5816-6526ms steady
    # state (10821ms on a cold connection). It must still fit after every judge has spent its
    # full cap, which is the worst case that actually bit in production.
    assert settings.chat_llm_budget_seconds - judges >= 6.5
    # And the whole turn has to fit the wall-clock deadline, with embedding and persistence.
    assert (
        settings.chat_llm_budget_seconds
        + settings.chat_embedding_budget_seconds
        + settings.chat_persistence_reserve_seconds
    ) <= settings.chat_overall_deadline_seconds


def test_the_interpreter_timeout_matches_what_the_configured_model_costs() -> None:
    """The interpreter timeout and the model have to agree, and which number is right depends on
    which model is configured -- so this asserts the RELATIONSHIP, not a constant.

    * On a reasoning model the interpreter must run at `low`: gpt-5-mini at `minimal` was measured
      to mis-route coreference follow-ups to CONVERSATION 3/3, and `low` costs p50 4468ms /
      max 8722ms, so the timeout has to be able to pay for it.
    * gpt-4o-mini (today's default) routes the same 8/8 with no reasoning at all, p50 1262ms /
      max 1870ms, so 4.0s is ~2x the measured max.

    Either way the timeout must exceed the measured cost, because this gate fails OPEN: too small
    a value does not slow the turn down, it silently deletes Phase 2 routing.
    """
    from src.ai.orchestration.turn_interpreter import TurnInterpreterConfig
    from src.infrastructure.ai.openai_completion_adapter import (
        _REASONING_EFFORT_BY_OPERATION,
        _supports_reasoning_effort,
    )

    timeout = TurnInterpreterConfig.from_config().timeout_seconds
    settings = _settings()
    if _supports_reasoning_effort(settings.model_name) and settings.chat_reasoning_effort_override is None:
        assert _REASONING_EFFORT_BY_OPERATION["turn_interpreter"] == "low"
        assert timeout >= 8.0
    else:
        # The explicit `none` override is the live latency probe: it must not inherit an old
        # reasoning-model timeout requirement merely because the model family supports reasoning.
        assert timeout >= 3.0
