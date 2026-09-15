"use client";

import { useCallback, useEffect, useState } from "react";

import { listApprovedConventions } from "@/features/conventions/api";
import type {
  PageMetaDTO,
  RuleFamilyItemDTO,
} from "@/features/conventions/dto/ruleFamily.response";

export const CONVENTIONS_PAGE_SIZE = 20;

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}

/**
 * Danh sách convention đã được PM duyệt, dành cho Member.
 *
 * Read-only theo thiết kế: Member không có hành động nào trên rule, và không nhận provenance
 * metadata nội bộ (reviewer count / match confidence) — xem UI_SPEC B.3.
 */
export function useConventions(enabled: boolean, fallbackError = "Could not load conventions.") {
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<RuleFamilyItemDTO[]>([]);
  const [meta, setMeta] = useState<PageMetaDTO>({
    page: 1,
    page_size: CONVENTIONS_PAGE_SIZE,
    total: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true);
      setError(null);
      try {
        const data = await listApprovedConventions(page, CONVENTIONS_PAGE_SIZE, signal);
        if (signal?.aborted) return;
        setItems(data.items);
        setMeta(data.meta);
      } catch (caught) {
        if (signal?.aborted || isAbortError(caught)) return;
        setError(caught instanceof Error ? caught.message : fallbackError);
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [fallbackError, page],
  );

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    // Fetch dữ liệu khi mount/đổi filter — đồng bộ với external system (API), đúng pattern
    // react.dev/learn/you-might-not-need-an-effect. Rule chỉ nhận diện được setState gọi trực
    // tiếp trong effect, không theo dõi được qua useCallback tách riêng (giống
    // useProjectManagement).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load(controller.signal);
    return () => controller.abort();
  }, [enabled, load]);

  return { items, meta, page, setPage, loading, error, reload: load };
}
