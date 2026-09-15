import { authHeaders } from "@/features/auth/session";
import { EMBEDDING_WARMUP_ENDPOINT, requestJson } from "@/lib/api";

export type EmbeddingWarmupResponse = {
  status: "started" | "in_progress" | "ready" | "unavailable";
};

/**
 * Ask the backend to start its scale-to-zero embedder. Callers intentionally ignore failure:
 * opening Chat or repository scanning must remain usable while Modal is unavailable.
 */
export function requestEmbeddingWarmup(signal?: AbortSignal): Promise<EmbeddingWarmupResponse> {
  return requestJson<EmbeddingWarmupResponse>(
    EMBEDDING_WARMUP_ENDPOINT,
    {
      method: "POST",
      headers: authHeaders(),
      signal,
    },
    { timeoutMs: 5_000 },
  );
}

/** Read readiness without extending Modal's GPU lifetime. */
export function getEmbeddingWarmupStatus(signal?: AbortSignal): Promise<EmbeddingWarmupResponse> {
  return requestJson<EmbeddingWarmupResponse>(
    EMBEDDING_WARMUP_ENDPOINT,
    {
      method: "GET",
      headers: authHeaders(),
      signal,
    },
    { timeoutMs: 5_000 },
  );
}
