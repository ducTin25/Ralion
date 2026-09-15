"""F5 audit 2026-08-29 follow-up: regression coverage for the two logging guarantees the audit
found broken -- `chat_observability` events silently failing to reach `docker logs`, and an
unexpected error's stack trace/stage never being captured anywhere. No live app, no DB: these
call `configure_logging`/`attach_trace_id` directly, the same way `test_scope_gate.py` pins a
contract with a fake collaborator instead of a live LLM.
"""

from __future__ import annotations

import json
import logging

import pytest

from src.main import attach_trace_id, configure_logging


@pytest.fixture
def scratch_logger():
    """A logger pytest's own log-capture plugin does not manage, so handler-count assertions
    test only this fix's own logic -- the real call site targets the actual root logger, which
    `configure_logging`'s default argument already covers without a test needing to touch it."""
    logger = logging.getLogger("test_configure_logging_scratch")
    logger.handlers = []
    yield logger
    logger.handlers = []


def test_configure_logging_attaches_one_handler_and_sets_the_level(scratch_logger) -> None:
    configure_logging("DEBUG", logger=scratch_logger)

    assert len(scratch_logger.handlers) == 1
    assert scratch_logger.level == logging.DEBUG


def test_configure_logging_is_idempotent_but_still_reapplies_the_level(scratch_logger) -> None:
    """The bug this fixes: `logging.basicConfig()` is a no-op -- including for the LEVEL -- on
    every call after the first handler exists, so a later, stricter level set by anything else in
    the process silently suppressed `chat_observability`'s INFO events with no error anywhere.
    `configure_logging` must never stack a second handler, but it must always re-apply the level."""
    configure_logging("DEBUG", logger=scratch_logger)
    scratch_logger.setLevel(logging.WARNING)  # simulate something else narrowing the level

    configure_logging("DEBUG", logger=scratch_logger)

    assert len(scratch_logger.handlers) == 1  # still exactly one handler
    assert scratch_logger.level == logging.DEBUG  # level restored, not left at WARNING


@pytest.mark.asyncio
async def test_unexpected_error_is_logged_with_trace_id_type_and_traceback(caplog) -> None:
    """The transport-boundary safety net: an exception no inner handler anticipated must still
    leave a trace_id-correlated, stack-trace-bearing record behind -- the only way to debug it
    once it has degraded to a generic 500 response (F5 audit 2026-08-29, HTTP 500 root cause)."""
    from starlette.requests import Request

    request = Request({"type": "http", "method": "GET", "path": "/api/v1/chat", "headers": []})

    async def call_next(_request):
        raise RuntimeError("a genuinely unexpected bug")

    with caplog.at_level(logging.ERROR, logger="chat_observability"):
        response = await attach_trace_id(request, call_next)

    assert response.status_code == 500
    trace_id = response.headers["X-Trace-Id"]
    records = [r for r in caplog.records if r.name == "chat_observability"]
    assert len(records) == 1
    record = records[0]
    payload = json.loads(record.getMessage())
    assert payload == {
        "event": "request.failed",
        "trace_id": trace_id,
        "path": "/api/v1/chat",
        "error_code": "unexpected_error",
        "error_type": "RuntimeError",
    }
    assert record.exc_info is not None
    assert record.exc_info[1].args == ("a genuinely unexpected bug",)


@pytest.mark.asyncio
async def test_unexpected_error_log_includes_stage_when_the_exception_carries_one(caplog) -> None:
    """`stage` is opportunistic (read from `exc.stage` if present, e.g. `RetrievalUnavailableError`
    -- never a new required contract every exception type must implement)."""
    from starlette.requests import Request

    request = Request({"type": "http", "method": "GET", "path": "/api/v1/chat", "headers": []})

    class _StagedError(RuntimeError):
        stage = "retrieval.datastore"

    async def call_next(_request):
        raise _StagedError("boom")

    with caplog.at_level(logging.ERROR, logger="chat_observability"):
        await attach_trace_id(request, call_next)

    record = next(r for r in caplog.records if r.name == "chat_observability")
    payload = json.loads(record.getMessage())
    assert payload["stage"] == "retrieval.datastore"
