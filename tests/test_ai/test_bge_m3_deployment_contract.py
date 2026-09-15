from modal_bge_m3.app import (
    GPU_CONFIG,
    MAX_CONTAINERS,
    MIN_CONTAINERS,
    MODEL_NAME,
    MODEL_REVISION,
    MODEL_VERSION,
    SCALEDOWN_WINDOW_SECONDS,
)
from src.ai.providers.embeddings import (
    EMBEDDING_MODEL,
    EMBEDDING_MODEL_REVISION,
    EMBEDDING_MODEL_VERSION,
    BgeM3Embedder,
)
from src.config import Settings
from src.infrastructure.ai.modal_embedding_adapter import ModalEmbeddingAdapter


def test_modal_and_backend_share_pinned_gpu_embedding_contract() -> None:
    assert GPU_CONFIG == "L4"
    assert MIN_CONTAINERS == 0
    assert MAX_CONTAINERS == 1
    assert SCALEDOWN_WINDOW_SECONDS == 120
    assert MODEL_NAME == EMBEDDING_MODEL
    assert MODEL_REVISION == EMBEDDING_MODEL_REVISION
    assert MODEL_VERSION == EMBEDDING_MODEL_VERSION
    assert ModalEmbeddingAdapter.model_version == EMBEDDING_MODEL_VERSION
    assert BgeM3Embedder().model_version == EMBEDDING_MODEL_VERSION


def test_backend_warmup_is_enabled_so_every_embedding_use_case_stays_warm() -> None:
    settings = Settings(_env_file=None)

    assert settings.chat_embedding_warmup_enabled is True
