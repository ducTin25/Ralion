"""GPU Modal deployment for the Ralion BGE-M3 embedding service.

Deploy with: python -m modal deploy modal_bge_m3/app.py
The deployment requires the Modal secret `ralion-bge-m3-api` containing
`EMBEDDING_API_KEY`. Requests use the Authorization: Bearer header.

The exact Hugging Face revision is downloaded while the image is built. Runtime
containers therefore never fetch mutable model weights during a cold start.
"""

import hmac
import os
from contextlib import asynccontextmanager

import modal

APP_NAME = "ralion-bge-m3-embedder"
MODEL_NAME = "BAAI/bge-m3"
MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"  # pragma: allowlist secret
MODEL_VERSION = f"{MODEL_NAME}@{MODEL_REVISION}"
MODEL_DIR = "/models/bge-m3"
MODEL_DIMENSION = 1024
API_SECRET_NAME = "ralion-bge-m3-api"  # pragma: allowlist secret
GPU_CONFIG = "L4"
# Staging and low-traffic production must stay within the Modal Starter credit.
# Keep the L4 GPU on demand, cap scale-out to one container, and retain it briefly
# after a request so related calls can reuse the loaded model.
MIN_CONTAINERS = 0
MAX_CONTAINERS = 1
SCALEDOWN_WINDOW_SECONDS = 120


def download_model() -> None:
    """Bake the pinned dense model into the immutable Modal image."""

    from huggingface_hub import snapshot_download

    snapshot_download(
        repo_id=MODEL_NAME,
        revision=MODEL_REVISION,
        local_dir=MODEL_DIR,
        ignore_patterns=(
            "onnx/**",
            "imgs/**",
            "bge-m3-with-deocder/**",
            "*.md",
            "*.jpg",
        ),
    )


app = modal.App(APP_NAME)
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "fastapi==0.115.12",
        "huggingface-hub==0.28.1",
        "pydantic==2.10.6",
        "sentence-transformers==3.4.1",
        "torch==2.6.0",
        "transformers==4.48.3",
    )
    .run_function(download_model)
    .env(
        {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "TOKENIZERS_PARALLELISM": "false",
        }
    )
)


@app.function(
    image=image,
    gpu=GPU_CONFIG,
    cpu=2.0,
    memory=8192,
    timeout=300,
    scaledown_window=SCALEDOWN_WINDOW_SECONDS,
    min_containers=MIN_CONTAINERS,
    max_containers=MAX_CONTAINERS,
    secrets=[modal.Secret.from_name(API_SECRET_NAME)],
)
@modal.concurrent(max_inputs=1)
@modal.asgi_app()
def api():
    """Create one FastAPI process and load pinned BGE-M3 once on NVIDIA L4."""
    import torch
    from fastapi import Body, Depends, FastAPI, Header, HTTPException, status
    from pydantic import BaseModel, Field
    from sentence_transformers import SentenceTransformer

    expected_api_key = os.environ["EMBEDDING_API_KEY"]
    model: SentenceTransformer | None = None

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        nonlocal model
        if not torch.cuda.is_available():
            raise RuntimeError("BGE-M3 Modal deployment requires a CUDA GPU")
        model = SentenceTransformer(MODEL_DIR, device="cuda")
        yield
        model = None

    web = FastAPI(title="Ralion BGE-M3 Embedder", lifespan=lifespan)

    class EmbedRequest(BaseModel):
        texts: list[str] = Field(min_length=1, max_length=32)

    class EmbedResponse(BaseModel):
        model: str
        revision: str
        model_version: str
        dimension: int
        vectors: list[list[float]]

    def authorize(authorization: str | None = Header(default=None)) -> None:
        expected = f"Bearer {expected_api_key}"
        if authorization is None or not hmac.compare_digest(authorization, expected):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    @web.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "model": MODEL_NAME,
            "revision": MODEL_REVISION,
            "model_version": MODEL_VERSION,
            "dimension": MODEL_DIMENSION,
            "device": "cuda",
            "gpu": torch.cuda.get_device_name(0),
        }

    @web.post("/embed", response_model=EmbedResponse)
    def embed(payload: EmbedRequest = Body(...), _: None = Depends(authorize)) -> EmbedResponse:
        if model is None:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Model is warming up")
        if any(not text.strip() for text in payload.texts):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="texts must not be blank")
        vectors = model.encode(
            payload.texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).tolist()
        if any(len(vector) != MODEL_DIMENSION for vector in vectors):
            raise HTTPException(status_code=500, detail="Unexpected embedding dimension")
        return EmbedResponse(
            model=MODEL_NAME,
            revision=MODEL_REVISION,
            model_version=MODEL_VERSION,
            dimension=MODEL_DIMENSION,
            vectors=vectors,
        )

    return web
