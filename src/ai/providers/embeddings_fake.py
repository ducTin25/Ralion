"""Embedder giả cho dev và test.

BGE-M3 nặng ~2.3GB và cần GPU để chạy nhanh, nên không thể bắt mọi người trong nhóm
tải model chỉ để mở màn hình HR. `FakeEmbedder` sinh vector tất định từ nội dung text
để toàn bộ luồng upload chạy được end-to-end mà không cần model thật.

Vector là tất định (cùng text → cùng vector) nên test so sánh được, và đã chuẩn hoá
L2 đúng như `BgeM3Embedder` — pgvector dùng `vector_cosine_ops` nên chuẩn hoá là bắt buộc.

KHÔNG dùng ở production: vector không mang ngữ nghĩa, retrieval sẽ trả kết quả ngẫu nhiên.
Bật bằng `USE_FAKE_EMBEDDER=true` trong .env cho dev/test.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence

from src.ai.providers.embeddings import EMBEDDING_DIMENSION

FAKE_MODEL_VERSION = "fake-deterministic-v1"


class FakeEmbedder:
    """Sinh vector tất định 1024 chiều, đã chuẩn hoá L2."""

    model_version = FAKE_MODEL_VERSION
    dimension = EMBEDDING_DIMENSION

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector_for(text) for text in texts]

    def _vector_for(self, text: str) -> list[float]:
        # Dùng SHA-256 làm nguồn byte tất định, lặp lại cho đủ số chiều.
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        raw = (digest * (self.dimension // len(digest) + 1))[: self.dimension]
        # Ánh xạ byte 0..255 về khoảng [-1, 1]
        values = [(byte - 127.5) / 127.5 for byte in raw]
        norm = math.sqrt(sum(value * value for value in values))
        if norm == 0:  # chuỗi rỗng cho ra vector 0 — trả về vector đơn vị hợp lệ
            return [1.0] + [0.0] * (self.dimension - 1)
        return [value / norm for value in values]
