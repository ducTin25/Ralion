from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any, Literal

import openai
from langchain_openai import ChatOpenAI

from src.infrastructure.reliability import RetryExecutor, RetryPolicy
from src.shared.ai.external_failures import ExternalFailureCode, ExternalServiceFailure
from src.shared.ai.ports import ChatCompletion
from src.shared.ai.request_budget import RequestBudget

_MAX_PROVIDER_ERROR_MESSAGE_CHARS = 512

# Reasoning effort per operation. NOT one value for "judges": the right effort is a property of
# the TASK, and these tasks differ more than their shared "one short call" shape suggests.
#
# Measured 2026-08-26 on the live provider (`gpt-5-mini`). The first pass here set every judge to
# `minimal` on the strength of a 6-case check -- but every one of those cases was a STANDALONE
# utterance, so it never exercised coreference resolution, which is the one thing the interpreter
# does that genuinely needs deliberation. Re-measured with conversation history:
#
#   "cái đó áp dụng từ khi nào?" (follow-up to a leave-policy answer)
#     minimal -> CONVERSATION  3/3   WRONG: it asks a new fact about the policy, not about the chat
#     low     -> KNOWLEDGE     3/3   correct
#     medium  -> KNOWLEDGE     3/3   correct
#
# So `minimal` is correct only where a call judges ONE utterance in isolation. Anything that must
# relate the current turn to a previous one, or weigh evidence, gets `low`.
#
# Full re-measurement at `low` across all six route kinds (standalone, coreference follow-up,
# re-presentation, history question, and both mixed-affect shapes): 8/8 correct, p50 4468ms,
# max 8722ms (first call, cold).
_REASONING_EFFORT_BY_OPERATION = {
    "scope_gate": "minimal",
    "query_rewrite": "minimal",
    "support_reply": "minimal",
    "evidence_sufficiency_gate": "minimal",
    "answer": "minimal",
    "repair": "minimal",
    "conversation_answer": "minimal",
    "turn_interpreter": "low",
}

# Model families that accept `reasoning_effort`. Sending it to a model that does not know the
# parameter is a 400 that would take chat down, and this provider is configurable
# (`openrouter_model or model_name`), so the override is applied only to a family known to
# support it -- anything else keeps today's behaviour exactly.
_REASONING_MODEL_PREFIXES = ("gpt-5", "o1", "o3", "o4")


def _supports_reasoning_effort(model: object) -> bool:
    if not isinstance(model, str):
        return False
    name = model.rsplit("/", 1)[-1].casefold()  # tolerate an OpenRouter "vendor/model" id
    return name.startswith(_REASONING_MODEL_PREFIXES)


class OpenAICompatibleAdapter:
    def __init__(
        self,
        provider: ChatOpenAI,
        policy: RetryPolicy,
        executor: RetryExecutor,
        *,
        reasoning_effort_enabled: bool = False,
        reasoning_effort_override: str | None = None,
    ) -> None:
        self._provider = provider
        self._policy = policy
        self._executor = executor
        # Resolved once at construction, not per call: whether the configured model supports the
        # parameter cannot change between turns, and a per-call check would be dead work on the
        # hot path. `False` (the default) disables the override entirely, so every call site that
        # does not pass it is byte-identical to before this parameter existed.
        self._reasoning_effort_enabled = reasoning_effort_enabled and _supports_reasoning_effort(
            getattr(provider, "model_name", None)
        )
        self._reasoning_effort_override = (
            reasoning_effort_override if self._reasoning_effort_enabled else None
        )

    def _call_kwargs(self, operation: str) -> dict[str, str]:
        if not self._reasoning_effort_enabled:
            return {}
        if self._reasoning_effort_override is not None:
            return {"reasoning_effort": self._reasoning_effort_override}
        effort = _REASONING_EFFORT_BY_OPERATION.get(operation)
        return {"reasoning_effort": effort} if effort else {}

    @staticmethod
    def _failure_metadata(exc: BaseException) -> dict[str, object]:
        """Return a small, secret-safe subset of a provider failure.

        The OpenAI SDK's exception body may be a dict or a string.  It is useful for diagnosis
        (for example, a transient upstream 404 versus an invalid request), but must never become
        a prompt dump or credential leak, so only its bounded message is retained.
        """
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", None)
        request = getattr(exc, "request", None)
        body: Any = getattr(exc, "body", None)
        if isinstance(body, dict):
            error = body.get("error", body)
            message = error.get("message") if isinstance(error, dict) else str(error)
        elif body is None:
            message = str(exc)
        else:
            message = str(body)
        # Error messages are provider-controlled metadata, but may still echo a malformed input.
        # Keep a bounded, one-line diagnostic rather than an arbitrary response body.
        message = " ".join(message.split())[:_MAX_PROVIDER_ERROR_MESSAGE_CHARS]
        return {
            "provider_exception_type": type(exc).__name__,
            "provider_status_code": getattr(exc, "status_code", None)
            or getattr(response, "status_code", None),
            "provider_error_message": message or None,
            "provider_request_id": headers.get("x-request-id") if headers is not None else None,
            "provider_endpoint": str(getattr(request, "url", "")) or None,
        }

    async def complete(self, messages: Sequence[tuple[str, str]], budget: RequestBudget, operation: Literal["query_rewrite", "answer", "repair", "scope_gate", "evidence_sufficiency_gate", "conversation_answer", "turn_interpreter", "support_reply"]) -> ChatCompletion:
        # "turn_interpreter" was missing from this Literal even though `TurnInterpreter` has always
        # passed it -- annotation-only drift (no runtime effect), fixed here because the value is
        # now load-bearing: it selects the reasoning-effort override below.
        call_kwargs = self._call_kwargs(operation)

        async def attempt(_connect_timeout: float, read_timeout: float) -> ChatCompletion:
            try:
                async with asyncio.timeout(read_timeout):
                    response = await self._provider.ainvoke(list(messages), **call_kwargs)
            except asyncio.CancelledError:
                raise
            except (TimeoutError, openai.APITimeoutError) as exc:
                # A request may already have reached the provider: no duplicate interactive generation.
                raise ExternalServiceFailure(
                    "llm", ExternalFailureCode.TIMEOUT, False, timeout_scope="attempt",
                    **self._failure_metadata(exc),
                ) from exc
            except openai.AuthenticationError as exc:
                raise ExternalServiceFailure(
                    "llm", ExternalFailureCode.AUTHENTICATION, False, **self._failure_metadata(exc)
                ) from exc
            except openai.BadRequestError as exc:
                raise ExternalServiceFailure(
                    "llm", ExternalFailureCode.BAD_REQUEST, False, **self._failure_metadata(exc)
                ) from exc
            except openai.RateLimitError as exc:
                retry_after = _header_seconds(exc, "retry-after")
                raise ExternalServiceFailure(
                    "llm", ExternalFailureCode.RATE_LIMITED, retry_after is not None,
                    retry_after_seconds=retry_after, **self._failure_metadata(exc),
                ) from exc
            except openai.APIConnectionError as exc:
                raise ExternalServiceFailure(
                    "llm", ExternalFailureCode.CONNECTION, True, **self._failure_metadata(exc)
                ) from exc
            except openai.APIStatusError as exc:
                retryable = exc.status_code in (502, 503)
                code = ExternalFailureCode.UNAVAILABLE if exc.status_code >= 500 else ExternalFailureCode.BAD_REQUEST
                raise ExternalServiceFailure(
                    "llm", code, retryable, **self._failure_metadata(exc)
                ) from exc
            content = getattr(response, "content", None)
            if not isinstance(content, str):
                raise ExternalServiceFailure("llm", ExternalFailureCode.PROTOCOL, False)
            return ChatCompletion(content, getattr(response, "response_metadata", {}) or {}, getattr(response, "usage_metadata", {}) or {})

        return await self._executor.run(attempt, service="llm", stage="llm", budget=budget, policy=self._policy)


def _header_seconds(exc: openai.APIStatusError, name: str) -> float | None:
    try:
        value = exc.response.headers.get(name)
        return max(0.0, float(value)) if value is not None else None
    except (TypeError, ValueError):
        return None
