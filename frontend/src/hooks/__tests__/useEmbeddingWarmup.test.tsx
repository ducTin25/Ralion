import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  EMBEDDING_KEEPALIVE_INTERVAL_MS,
  EMBEDDING_PREPARATION_TIMEOUT_MS,
  EMBEDDING_STATUS_POLL_INTERVAL_MS,
  useEmbeddingWarmup,
} from "@/hooks/useEmbeddingWarmup";

const requestEmbeddingWarmupMock = vi.hoisted(() => vi.fn());
const getEmbeddingWarmupStatusMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/embeddingWarmup", () => ({
  requestEmbeddingWarmup: requestEmbeddingWarmupMock,
  getEmbeddingWarmupStatus: getEmbeddingWarmupStatusMock,
}));

function Harness({ enabled = true }: { enabled?: boolean }) {
  const state = useEmbeddingWarmup(enabled);
  return <span data-testid="state">{state}</span>;
}

describe("useEmbeddingWarmup", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-24T00:00:00Z"));
    requestEmbeddingWarmupMock.mockReset().mockResolvedValue({ status: "ready" });
    getEmbeddingWarmupStatusMock.mockReset().mockResolvedValue({ status: "ready" });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("warms immediately, keeps an active page warm, then stops after inactivity", async () => {
    render(<Harness />);
    expect(requestEmbeddingWarmupMock).toHaveBeenCalledTimes(1);
    await act(async () => Promise.resolve());
    expect(screen.getByTestId("state")).toHaveTextContent("ready");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(EMBEDDING_KEEPALIVE_INTERVAL_MS);
    });
    expect(requestEmbeddingWarmupMock).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(EMBEDDING_KEEPALIVE_INTERVAL_MS);
    });
    expect(requestEmbeddingWarmupMock).toHaveBeenCalledTimes(2);
  });

  it("warms immediately when activity resumes after idle", async () => {
    render(<Harness />);
    await act(async () => Promise.resolve());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(EMBEDDING_KEEPALIVE_INTERVAL_MS * 2);
      window.dispatchEvent(new Event("pointerdown"));
    });

    expect(requestEmbeddingWarmupMock).toHaveBeenCalledTimes(3);
  });

  it("does nothing while disabled and fails open when the warm-up request fails", async () => {
    const { rerender } = render(<Harness enabled={false} />);
    expect(requestEmbeddingWarmupMock).not.toHaveBeenCalled();

    requestEmbeddingWarmupMock.mockRejectedValueOnce(new Error("offline"));
    rerender(<Harness enabled />);
    await act(async () => Promise.resolve());

    expect(requestEmbeddingWarmupMock).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("state")).toHaveTextContent("ready");
  });

  it("reports preparing until the backend confirms BGE-M3 readiness", async () => {
    requestEmbeddingWarmupMock.mockResolvedValueOnce({ status: "started" });
    getEmbeddingWarmupStatusMock
      .mockResolvedValueOnce({ status: "in_progress" })
      .mockResolvedValueOnce({ status: "ready" });

    render(<Harness />);
    await act(async () => Promise.resolve());
    expect(screen.getByTestId("state")).toHaveTextContent("preparing");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(EMBEDDING_STATUS_POLL_INTERVAL_MS);
    });
    expect(screen.getByTestId("state")).toHaveTextContent("preparing");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(EMBEDDING_STATUS_POLL_INTERVAL_MS);
    });
    expect(screen.getByTestId("state")).toHaveTextContent("ready");
  });

  it("fails open after the bounded preparation window", async () => {
    requestEmbeddingWarmupMock.mockResolvedValueOnce({ status: "started" });
    getEmbeddingWarmupStatusMock.mockResolvedValue({ status: "in_progress" });

    render(<Harness />);
    await act(async () => Promise.resolve());
    expect(screen.getByTestId("state")).toHaveTextContent("preparing");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(EMBEDDING_PREPARATION_TIMEOUT_MS);
    });
    expect(screen.getByTestId("state")).toHaveTextContent("ready");
  });
});
