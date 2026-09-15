import asyncio
import contextlib
import json
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.api.routers import api_router
from src.config import get_settings
from src.infrastructure.ai.resources import create_ai_resources
from src.infrastructure.observability import shutdown_chat_telemetry
from src.infrastructure.scheduling.convention_discovery_scheduler import (
    convention_discovery_scheduler_loop,
)
from src.infrastructure.scheduling.embedding_warmup import embedding_warmup_loop
from src.infrastructure.scheduling.llm_warmup import llm_warmup_loop
from src.model.session import engine


def configure_logging(level: str, *, logger: logging.Logger | None = None) -> None:
    """Attach the process's one stdlib logging handler and set the effective level.
    `logger` defaults to the root logger (every app logger propagates to it); overridable only so
    a test can target a scratch logger instead of the real, pytest-managed root.
    """
    target = logger if logger is not None else logging.getLogger()
    target.setLevel(getattr(logging, level))
    if not target.handlers:
        target.addHandler(logging.StreamHandler())


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    logging.getLogger(__name__).info(
        json.dumps({"event": "application.started", "environment": settings.app_env})
    )
    app.state.ai_resources = create_ai_resources(settings)
    app.state.ai_resources.validate_embedding_contract()
    app.state.on_demand_embedding_warmup_task = None
    app.state.on_demand_embedding_warmup_ready_until = 0.0
    app.state.convention_discovery_task = asyncio.create_task(
        convention_discovery_scheduler_loop(settings)
    )
    # Item 1: a fake embedder has no cold-start concept, and other modules must not depend on
    # this task existing -- both create_ai_resources() and the rest of startup succeed either way.
    app.state.embedding_warmup_task = (
        asyncio.create_task(
            embedding_warmup_loop(settings, app.state.ai_resources.warmup_embedding)
        )
        if settings.chat_embedding_warmup_enabled and not settings.use_fake_embedder
        else None
    )
    # RC-1: keeps a pooled connection to the LLM provider open so the first interpreted turn does
    # not spend its stage timeout on a TCP+TLS handshake. Optional in exactly the same way as the
    # embedding warm-up -- nothing else depends on the task existing.
    app.state.llm_warmup_task = (
        asyncio.create_task(llm_warmup_loop(settings, app.state.ai_resources.llm_endpoint))
        if settings.chat_llm_warmup_enabled and app.state.ai_resources.llm_endpoint is not None
        else None
    )
    yield
    app.state.convention_discovery_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await app.state.convention_discovery_task
    if app.state.embedding_warmup_task is not None:
        app.state.embedding_warmup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await app.state.embedding_warmup_task
    if app.state.on_demand_embedding_warmup_task is not None:
        app.state.on_demand_embedding_warmup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await app.state.on_demand_embedding_warmup_task
    await app.state.ai_resources.aclose()
    await shutdown_chat_telemetry()
    logging.getLogger(__name__).info('{"event":"application.stopped"}')


app = FastAPI(
    title="AI20K Agent",
    description="AI Agent built with LangGraph",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()


@app.middleware("http")
async def attach_trace_id(request: Request, call_next):
    """Server-owned correlation ID for every HTTP outcome, including unexpected errors."""
    trace_id = uuid.uuid4().hex
    request.state.trace_id = trace_id
    try:
        response = await call_next(request)
    except Exception as exc:  # noqa: BLE001 - transport boundary returns a safe generic error
        # Last-resort diagnostic for a failure NO inner handler anticipated (an anticipated one
        # -- embedding/LLM/retrieval-datastore outage -- is already caught deeper and degrades to
        # a normal fallback response, logged with its own error_stage/error_code by
        # `chat_telemetry.py`'s `chat.failed`, never reaching here at all). `stage` is
        # opportunistic, not a new contract: a handful of typed failures (e.g.
        # `RetrievalUnavailableError`) already carry a `.stage` attribute; a bare bug does not,
        # and `exc_info` -- never logged elsewhere -- is what actually locates it. Metadata only,
        # same as every other line this logger emits: no prompt, retrieved context, conversation
        # history, or model output ever reaches app logs -- that stays Langfuse's job.
        payload = {
            "event": "request.failed",
            "trace_id": trace_id,
            "path": request.url.path,
            "error_code": "unexpected_error",
            "error_type": type(exc).__name__,
            "stage": getattr(exc, "stage", None),
        }
        logging.getLogger("chat_observability").error(
            json.dumps({k: v for k, v in payload.items() if v is not None}, sort_keys=True),
            exc_info=exc,
        )
        response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "trace_id": trace_id},
        )
    response.headers["X-Trace-Id"] = trace_id
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}


async def check_database() -> None:
    """Fail when PostgreSQL cannot accept a trivial query."""
    async with asyncio.timeout(5):
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))


async def check_rag() -> int:
    """Validate production RAG configuration and return active embedded chunk count.

    This intentionally does not call the remote embedder: readiness checks run
    frequently and must not wake a scaled-to-zero inference worker. A separate
    post-deploy smoke probe exercises a real embedding request.
    """
    if not settings.bge_m3_endpoint or not settings.bge_m3_api_key:
        raise RuntimeError("remote embedding service is not configured")
    async with asyncio.timeout(5):
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    """
                    SELECT count(*)
                    FROM document_chunks AS chunk
                    JOIN document_versions AS version
                      ON version.version_id = chunk.version_id
                    JOIN knowledge_documents AS document
                      ON document.document_id = version.document_id
                    WHERE chunk.embedding IS NOT NULL
                      AND version.status::text = 'ACTIVE'
                      AND document.status::text = 'ACTIVE'
                    """
                )
            )
            active_chunks = int(result.scalar_one())
    if active_chunks < 1:
        raise RuntimeError("RAG corpus has no active embedded chunks")
    return active_chunks


@app.get("/ready")
async def readiness():
    """Deployment readiness probe, including the required database dependency."""
    try:
        await check_database()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ready", "dependencies": {"database": "ok"}}


@app.get("/ready/rag")
async def rag_readiness():
    """RAG-specific readiness without making the core API depend on inference warmup."""
    try:
        active_chunks = await check_rag()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="rag unavailable") from exc
    return {
        "status": "ready",
        "dependencies": {
            "database": "ok",
            "embedding": "configured",
            "active_chunks": active_chunks,
        },
    }
