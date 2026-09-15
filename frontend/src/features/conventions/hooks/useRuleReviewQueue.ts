"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import {
  approveRuleCandidate,
  listPendingRuleCandidates,
  listProjectApprovedConventions,
  reindexRuleCandidate,
  rejectRuleCandidate,
} from "@/features/conventions/api";
import type {
  RuleFamilyItemDTO,
  PageMetaDTO,
} from "@/features/conventions/dto/ruleFamily.response";
import { ApiError } from "@/lib/api";

/** Backend chỉ expose 2 danh sách: PENDING (`/rule-candidates/pending`) và APPROVED
 * (`/conventions`). Không có endpoint liệt kê REJECTED nên UI cũng không có tab đó — không
 * tự dựng filter phía client trên dữ liệu không được trả về. */
export type RuleReviewFilter = "PENDING" | "APPROVED";

export const RULE_REVIEW_PAGE_SIZE = 20;

export type RuleRowNotice = {
  kind: "conflict" | "not-indexed" | "error";
  message: string;
};

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}

/**
 * Trạng thái của PM Rule Review Queue: danh sách theo filter + 3 hành động HITL.
 *
 * Không có logic mining/clustering/eligibility ở đây. Guardrail ">=2 evidence, >=2 PR" đã chạy
 * ở tầng backend lúc mining; hook này chỉ đọc kết quả và gửi quyết định của PM đi.
 *
 * `projectId`: mọi list/decision đều scope theo repo GitHub của project này (server-side, xem
 * rule_review_router._project_repo_or_404) — `null` chỉ khi PM chưa có project nào active.
 */
export function useRuleReviewQueue(enabled: boolean, projectId: number | null) {
  const t = useTranslations("pmUi");
  const [filter, setFilter] = useState<RuleReviewFilter>("PENDING");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<RuleFamilyItemDTO[]>([]);
  const [meta, setMeta] = useState<PageMetaDTO>({
    page: 1,
    page_size: RULE_REVIEW_PAGE_SIZE,
    total: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [notices, setNotices] = useState<Record<number, RuleRowNotice>>({});

  const load = useCallback(
    async (signal?: AbortSignal) => {
      if (projectId === null) return;
      setLoading(true);
      setError(null);
      try {
        const fetchPage =
          filter === "PENDING" ? listPendingRuleCandidates : listProjectApprovedConventions;
        const data = await fetchPage(projectId, page, RULE_REVIEW_PAGE_SIZE, signal);
        if (signal?.aborted) return;
        setItems(data.items);
        setMeta(data.meta);
      } catch (caught) {
        if (signal?.aborted || isAbortError(caught)) return;
        setError(caught instanceof Error ? caught.message : t("ruleCandidatesLoadError"));
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [filter, page, projectId, t],
  );

  useEffect(() => {
    if (!enabled || projectId === null) return;
    const controller = new AbortController();
    // Fetch dữ liệu khi mount/đổi filter — đồng bộ với external system (API), đúng pattern
    // react.dev/learn/you-might-not-need-an-effect. Rule chỉ nhận diện được setState gọi trực
    // tiếp trong effect, không theo dõi được qua useCallback tách riêng (giống
    // useProjectManagement).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load(controller.signal);
    return () => controller.abort();
  }, [enabled, load, projectId]);

  const clearNotice = useCallback((ruleFamilyId: number) => {
    setNotices((current) => {
      if (!(ruleFamilyId in current)) return current;
      const next = { ...current };
      delete next[ruleFamilyId];
      return next;
    });
  }, []);

  const setNotice = useCallback((ruleFamilyId: number, notice: RuleRowNotice) => {
    setNotices((current) => ({ ...current, [ruleFamilyId]: notice }));
  }, []);

  /**
   * Approve/Reject một candidate.
   *
   * 409 = một reviewer khác đã quyết định trước (optimistic lock ở backend thua cuộc). Khi đó
   * hàng đó được đánh dấu rõ ràng và danh sách tự tải lại — không im lặng nuốt lỗi, cũng không
   * để UI hiển thị trạng thái khác backend.
   */
  const decide = useCallback(
    async (ruleFamilyId: number, action: "approve" | "reject") => {
      if (projectId === null) return null;
      setBusyId(ruleFamilyId);
      clearNotice(ruleFamilyId);
      try {
        const result =
          action === "approve"
            ? await approveRuleCandidate(projectId, ruleFamilyId)
            : await rejectRuleCandidate(projectId, ruleFamilyId);
        // Optimistic: hàng chuyển sang trạng thái đã quyết định ngay, không chờ backend index
        // xong vào retrieval engine (việc đó chạy event-driven và có thể retry riêng).
        setItems((current) =>
          current.map((item) =>
            item.rule_family_id === ruleFamilyId ? { ...item, status: result.status } : item,
          ),
        );
        if (result.retrieval_indexed === false) {
          setNotice(ruleFamilyId, {
            kind: "not-indexed",
            message: t("ruleApprovedNotIndexed"),
          });
        }
        return result;
      } catch (caught) {
        if (caught instanceof ApiError && caught.status === 409) {
          setNotice(ruleFamilyId, {
            kind: "conflict",
            message: t("ruleReviewConflict"),
          });
          await load();
          return null;
        }
        setNotice(ruleFamilyId, {
          kind: "error",
          message: caught instanceof Error ? caught.message : t("ruleDecisionError"),
        });
        return null;
      } finally {
        setBusyId(null);
      }
    },
    [clearNotice, load, setNotice, projectId, t],
  );

  const reindex = useCallback(
    async (ruleFamilyId: number) => {
      if (projectId === null) return null;
      setBusyId(ruleFamilyId);
      try {
        const result = await reindexRuleCandidate(projectId, ruleFamilyId);
        if (result.retrieval_indexed === false) {
          setNotice(ruleFamilyId, {
            kind: "not-indexed",
            message: t("ruleReindexStillFailed"),
          });
        } else {
          clearNotice(ruleFamilyId);
        }
        return result;
      } catch (caught) {
        setNotice(ruleFamilyId, {
          kind: "error",
          message: caught instanceof Error ? caught.message : t("ruleReindexError"),
        });
        return null;
      } finally {
        setBusyId(null);
      }
    },
    [clearNotice, setNotice, projectId, t],
  );

  const changeFilter = useCallback((next: RuleReviewFilter) => {
    setFilter(next);
    setPage(1);
    setNotices({});
  }, []);

  return {
    filter,
    changeFilter,
    page,
    setPage,
    items,
    meta,
    loading,
    error,
    busyId,
    notices,
    decide,
    reindex,
    refresh: load,
  };
}
