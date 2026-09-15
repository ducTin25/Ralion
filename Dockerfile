# ---- Stage 1: Build dependencies ----
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

ARG TORCH_VERSION=2.6.0
ARG PIP_TIMEOUT_SECONDS=120

COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --retries 10 --timeout "${PIP_TIMEOUT_SECONDS}" \
        --index-url https://download.pytorch.org/whl/cpu \
        "torch==${TORCH_VERSION}+cpu" \
    && /opt/venv/bin/pip install --no-cache-dir --retries 10 --timeout "${PIP_TIMEOUT_SECONDS}" \
        -r requirements.txt

# ---- Stage 2: Production ----
FROM python:3.11-slim-bookworm AS runtime

WORKDIR /app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=builder /opt/venv /opt/venv

# Use a stable uid so mounted volumes can grant access explicitly.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app

COPY --chown=appuser:appuser src ./src
COPY --chown=appuser:appuser config ./config
COPY --chown=appuser:appuser alembic.ini ./
COPY --chown=appuser:appuser alembic ./alembic
COPY --chown=appuser:appuser scripts/verify_runtime_integrations.py ./scripts/verify_runtime_integrations.py

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
