import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { parseJsonOrThrow, requestJson } from "@/lib/api";

/**
 * Cookie phiên chỉ được trình duyệt lưu khi API cùng site với trang. Base URL sai là lỗi
 * "đăng nhập trả 200 nhưng không có phiên", nên khoá hành vi này bằng test.
 */
describe("API base URL", () => {
  const original = process.env.NEXT_PUBLIC_API_URL;

  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    if (original === undefined) delete process.env.NEXT_PUBLIC_API_URL;
    else process.env.NEXT_PUBLIC_API_URL = original;
  });

  it("gọi API cùng origin khi không cấu hình gì", async () => {
    delete process.env.NEXT_PUBLIC_API_URL;

    const { API_BASE_URL, AUTH_ENDPOINT } = await import("@/lib/api");

    expect(API_BASE_URL).toBe("");
    expect(AUTH_ENDPOINT).toBe("/api/v1/auth");
  });

  it("coi biến rỗng như không cấu hình", async () => {
    process.env.NEXT_PUBLIC_API_URL = "   ";

    const { API_BASE_URL } = await import("@/lib/api");

    expect(API_BASE_URL).toBe("");
  });

  it("đồng bộ hostname loopback với trang đang mở khi trỏ backend trực tiếp", async () => {
    process.env.NEXT_PUBLIC_API_URL = "http://127.0.0.1:8001";

    const { API_BASE_URL } = await import("@/lib/api");

    expect(API_BASE_URL).toBe(`http://${window.location.hostname}:8001`);
  });
});

describe("API error contract", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("preserves HTTP status and backend detail", async () => {
    const response = new Response(JSON.stringify({ detail: "Sign-in required" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });

    await expect(parseJsonOrThrow(response)).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
      message: "Sign-in required",
    });
  });

  it("turns a request timeout into a typed 408 error", async () => {
    vi.useFakeTimers();
    vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
      return new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () =>
          reject(new DOMException("Aborted", "AbortError")),
        );
      });
    });

    const request = requestJson("https://example.test/slow", {}, { timeoutMs: 25 });
    const assertion = expect(request).rejects.toEqual(expect.objectContaining({ status: 408 }));
    await vi.advanceTimersByTimeAsync(25);
    await assertion;
  });

  it("propagates caller cancellation to fetch", async () => {
    const controller = new AbortController();
    let fetchSignal: AbortSignal | null = null;
    vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
      fetchSignal = init?.signal ?? null;
      return new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () =>
          reject(new DOMException("Aborted", "AbortError")),
        );
      });
    });

    const request = requestJson("https://example.test/cancel", { signal: controller.signal });
    const assertion = expect(request).rejects.toMatchObject({ name: "AbortError" });
    controller.abort();
    await assertion;
    expect(fetchSignal).not.toBeNull();
    expect((fetchSignal as unknown as AbortSignal).aborted).toBe(true);
  });

  it("sends the signed-in cookie with API requests by default", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));

    await requestJson("https://example.test/session");

    expect(fetchMock).toHaveBeenCalledWith(
      "https://example.test/session",
      expect.objectContaining({ credentials: "include" }),
    );
  });
});
