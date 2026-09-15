"use client";

import { useCallback, useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { MarkdownView } from "@/components/MarkdownView";

import { consoleApi } from "./api";
import type { PolicyContent } from "./types";

const formatDate = (value: string | null, locale: string) =>
  value
    ? new Intl.DateTimeFormat(locale, {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      }).format(new Date(value))
    : null;

/**
 * Xem nội dung chính sách ngay trong ứng dụng.
 *
 * Trước đây chỗ này là một link tới Cloudinary: bấm vào là mở tab mới rồi tải file về.
 * HR muốn đọc lướt một điều khoản thì phải tải file, mở bằng ứng dụng ngoài, rồi quay
 * lại — ba bước cho một việc đáng lẽ không rời trang.
 *
 * Nội dung hiển thị là bản đã chuyển đổi (cùng nguồn với thứ nhân viên đọc khi xác
 * nhận), nên HR nhìn thấy đúng cái nhân viên nhìn thấy. Nút tải file gốc vẫn còn cho
 * ai cần bản PDF/DOCX nguyên vẹn.
 */
export function PolicyDocumentModal({
  documentId,
  sourceUrl,
  archived = false,
  onClose,
}: {
  documentId: number;
  sourceUrl: string | null;
  archived?: boolean;
  onClose: () => void;
}) {
  const t = useTranslations("admin.policyDocument");
  const locale = useLocale();
  const [policy, setPolicy] = useState<PolicyContent | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setPolicy(await consoleApi.policyContent(documentId));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("contentLoadError"));
    }
  }, [documentId, t]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  // Đóng bằng Esc: modal chiếm gần hết màn hình, không có phím thoát thì phải rê chuột
  // lên góc mới đóng được.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-[#0b1c30]/50 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={t("dialogLabel")}
        onClick={(event) => event.stopPropagation()}
        className="flex h-full max-h-[92vh] w-full max-w-[900px] flex-col overflow-hidden rounded-md bg-white"
      >
        <header className="flex items-start justify-between gap-4 border-b border-divider px-7 py-5">
          <div className="min-w-0">
            <p className="text-xs font-bold tracking-[.1em] text-accent">{t("eyebrow")}</p>
            <h2 className="mt-2 truncate text-xl font-bold text-navy">
              {policy?.title ?? t("loading")}
            </h2>
            {policy && (
              <p className="mt-1 text-sm text-text-subtle">
                {t("version", { version: policy.version_no })}
                {(() => {
                  const effectiveDate = formatDate(policy.effective_date, locale);
                  return effectiveDate ? ` · ${t("effectiveDate", { date: effectiveDate })}` : "";
                })()}
              </p>
            )}
            {archived && (
              <span className="mt-2 inline-flex rounded-full border border-border bg-canvas px-2.5 py-1 text-xs font-semibold text-text-muted">
                {t("archived")}
              </span>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {sourceUrl?.startsWith("http") && (
              <a
                href={sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="h-9 rounded-md border border-border-strong px-3 text-sm font-bold leading-9 text-navy focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-link"
              >
                {t("downloadOriginal")}
              </a>
            )}
            <button
              type="button"
              onClick={onClose}
              className="h-9 rounded-md px-3 text-sm font-semibold hover:bg-canvas focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-link"
            >
              {t("close")}
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-auto px-8 py-7">
          {error ? (
            <div className="py-12 text-center">
              <p role="alert" className="text-sm text-danger">
                {error}
              </p>
              <button
                type="button"
                onClick={load}
                className="mt-4 h-10 rounded-md bg-navy px-4 text-sm font-bold text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-link"
              >
                {t("retry")}
              </button>
            </div>
          ) : policy ? (
            <MarkdownView source={policy.content} className="mx-auto max-w-[760px]" />
          ) : (
            <div className="mx-auto max-w-[760px] space-y-3">
              {Array.from({ length: 10 }).map((_, index) => (
                <div key={index} className="h-4 animate-pulse rounded bg-skeleton-faint" />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
