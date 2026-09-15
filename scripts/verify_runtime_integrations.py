"""Safe post-deploy provider smoke test.

The script deliberately uses synthetic text and prints booleans only. It must never print
credentials, prompts from users, document chunks, or provider response bodies.
"""

from __future__ import annotations

import asyncio
import json

from src.config import get_settings
from src.infrastructure.ai.langchain_llm import get_classifier_llm
from src.infrastructure.ai.resources import create_ai_resources
from src.infrastructure.observability.langfuse import get_langfuse_client
from src.shared.ai.request_budget import RequestBudget


async def _verify() -> dict[str, bool]:
    settings = get_settings()
    required = {
        "openai_configured": bool(settings.openai_api_key or settings.openrouter_api_key),
        "deepseek_configured": bool(settings.deepseek_api_key),
        "bge_configured": bool(settings.bge_m3_endpoint and settings.bge_m3_api_key),
        "langfuse_configured": bool(
            settings.langfuse_public_key and settings.langfuse_secret_key
        ),
    }
    if not all(required.values()):
        missing = sorted(key for key, configured in required.items() if not configured)
        raise RuntimeError(f"Missing runtime integrations: {', '.join(missing)}")

    resources = create_ai_resources(settings)
    try:
        vector = await resources.warmup_embedding.embed_query(
            "release integration probe",
            RequestBudget(
                settings.chat_embedding_warmup_timeout_seconds,
                settings.chat_embedding_warmup_timeout_seconds,
                0.0,
            ),
        )
        if len(vector) != 1024:
            raise RuntimeError("BGE-M3 returned an unexpected vector dimension")

        response = await get_classifier_llm().ainvoke(
            "Return exactly OVERVIEW|0.9 and nothing else. This is a synthetic health probe."
        )
        if not str(response.content).strip().upper().startswith("OVERVIEW|"):
            raise RuntimeError("DeepSeek classifier returned an unexpected response shape")

        client = get_langfuse_client()
        if client is None:
            raise RuntimeError("Langfuse client could not be initialized")
        auth_check = getattr(client, "auth_check", None)
        if callable(auth_check) and not auth_check():
            raise RuntimeError("Langfuse authentication failed")
        observation = client.start_observation(
            name="release.integration",
            as_type="span",
            metadata={"synthetic": True, "content_exported": False},
        )
        if hasattr(observation, "end"):
            observation.end()
        client.flush()
    finally:
        await resources.aclose()

    return {**required, "bge_ok": True, "deepseek_ok": True, "langfuse_ok": True}


if __name__ == "__main__":
    print(json.dumps(asyncio.run(_verify()), sort_keys=True))
