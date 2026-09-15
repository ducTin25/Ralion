"use client";

import { useEffect, useState } from "react";

import { getEmbeddingWarmupStatus, requestEmbeddingWarmup } from "@/lib/embeddingWarmup";

export const EMBEDDING_KEEPALIVE_INTERVAL_MS = 60_000;
export const EMBEDDING_ACTIVE_WINDOW_MS = 75_000;
export const EMBEDDING_STATUS_POLL_INTERVAL_MS = 1_000;
export const EMBEDDING_PREPARATION_TIMEOUT_MS = 30_000;

export type EmbeddingWarmupUiState = "idle" | "preparing" | "ready";

/**
 * Warm BGE-M3 when an authenticated AI workflow opens, then retain it only while the user is
 * active. Combined with Modal's 120-second scaledown window, an idle GPU stops after roughly
 * two to three minutes instead of being held open by a permanent backend scheduler.
 */
export function useEmbeddingWarmup(enabled: boolean): EmbeddingWarmupUiState {
  const [warmupState, setWarmupState] = useState<EmbeddingWarmupUiState>(
    enabled ? "preparing" : "idle",
  );

  useEffect(() => {
    if (!enabled) return;

    const controller = new AbortController();
    let disposed = false;
    let requestInFlight = false;
    let statusInFlight = false;
    let waitingForReady = false;
    let lastActivityAt = Date.now();
    let lastWarmupAt = 0;
    let statusPoll: number | undefined;
    let preparationTimeout: number | undefined;

    const finishPreparation = () => {
      if (disposed) return;
      waitingForReady = false;
      if (statusPoll !== undefined) window.clearTimeout(statusPoll);
      if (preparationTimeout !== undefined) window.clearTimeout(preparationTimeout);
      setWarmupState("ready");
    };

    const scheduleStatusPoll = () => {
      if (disposed || !waitingForReady || statusPoll !== undefined) return;
      statusPoll = window.setTimeout(() => {
        statusPoll = undefined;
        if (disposed || !waitingForReady || statusInFlight) return;
        statusInFlight = true;
        void getEmbeddingWarmupStatus(controller.signal)
          .then((response) => {
            if (response.status === "ready") {
              finishPreparation();
              return;
            }
            scheduleStatusPoll();
          })
          .catch(finishPreparation)
          .finally(() => {
            statusInFlight = false;
          });
      }, EMBEDDING_STATUS_POLL_INTERVAL_MS);
    };

    const warm = (waitForReady = false) => {
      if (disposed) return;
      if (requestInFlight) {
        if (waitForReady) scheduleStatusPoll();
        return;
      }
      requestInFlight = true;
      lastWarmupAt = Date.now();
      void requestEmbeddingWarmup(controller.signal)
        .then((response) => {
          if (!waitForReady) return;
          if (response.status === "ready") finishPreparation();
          else scheduleStatusPoll();
        })
        .catch(() => {
          if (waitForReady) finishPreparation();
        })
        .finally(() => {
          requestInFlight = false;
        });
    };

    const beginPreparation = () => {
      waitingForReady = true;
      if (statusPoll !== undefined) window.clearTimeout(statusPoll);
      if (preparationTimeout !== undefined) window.clearTimeout(preparationTimeout);
      statusPoll = undefined;
      setWarmupState("preparing");
      preparationTimeout = window.setTimeout(finishPreparation, EMBEDDING_PREPARATION_TIMEOUT_MS);
      warm(true);
    };

    const recordActivity = () => {
      const now = Date.now();
      const resumedAfterIdle = now - lastActivityAt > EMBEDDING_ACTIVE_WINDOW_MS;
      lastActivityAt = now;
      if (document.visibilityState !== "visible") return;
      if (resumedAfterIdle) {
        beginPreparation();
      } else if (now - lastWarmupAt >= EMBEDDING_KEEPALIVE_INTERVAL_MS) {
        warm();
      }
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        const now = Date.now();
        const resumedAfterIdle = now - lastActivityAt > EMBEDDING_ACTIVE_WINDOW_MS;
        lastActivityAt = now;
        if (resumedAfterIdle) beginPreparation();
        else warm();
      }
    };

    beginPreparation();
    const interval = window.setInterval(() => {
      const now = Date.now();
      if (
        document.visibilityState === "visible" &&
        now - lastActivityAt <= EMBEDDING_ACTIVE_WINDOW_MS &&
        now - lastWarmupAt >= EMBEDDING_KEEPALIVE_INTERVAL_MS
      ) {
        warm();
      }
    }, EMBEDDING_KEEPALIVE_INTERVAL_MS);

    window.addEventListener("pointerdown", recordActivity, { passive: true });
    window.addEventListener("touchstart", recordActivity, { passive: true });
    window.addEventListener("keydown", recordActivity);
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      disposed = true;
      controller.abort();
      window.clearInterval(interval);
      if (statusPoll !== undefined) window.clearTimeout(statusPoll);
      if (preparationTimeout !== undefined) window.clearTimeout(preparationTimeout);
      window.removeEventListener("pointerdown", recordActivity);
      window.removeEventListener("touchstart", recordActivity);
      window.removeEventListener("keydown", recordActivity);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [enabled]);

  return enabled ? warmupState : "idle";
}
