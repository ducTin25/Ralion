"use client";

import { useMemo, useState } from "react";
import { FileIcon } from "@primer/octicons-react";
import { useTranslations } from "next-intl";

import { MarkdownView } from "@/components/MarkdownView";

import { consoleApi } from "./api";
import type { PolicyInspectResult } from "./types";

const MAX_FILES = 10;
const INSPECT_CONCURRENCY = 3;
const UPLOAD_CONCURRENCY = 2;

type BatchStatus = "inspecting" | "ready" | "uploading" | "success" | "error";

type BatchItem = {
  id: string;
  file: File;
  status: BatchStatus;
  result: PolicyInspectResult | null;
  documentCode: string;
  title: string;
  category: string;
  version: string;
  effectiveDate: string;
  error: string | null;
};

function itemId(file: File, index: number) {
  return `${file.name}-${file.size}-${file.lastModified}-${Date.now()}-${index}`;
}

function formatSize(size: number) {
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

async function runWithConcurrency<T>(
  values: T[],
  limit: number,
  worker: (value: T) => Promise<void>,
) {
  let cursor = 0;
  const runners = Array.from({ length: Math.min(limit, values.length) }, async () => {
    while (cursor < values.length) {
      const current = values[cursor];
      cursor += 1;
      await worker(current);
    }
  });
  await Promise.all(runners);
}

function isReady(item: BatchItem) {
  if (!item.result || item.status !== "ready") return false;
  const needsManualVersion = !item.result.detected_version;
  return Boolean(
    item.documentCode.trim() &&
    item.title.trim() &&
    item.category &&
    (!needsManualVersion || (item.version.trim() && item.effectiveDate)),
  );
}

export function PolicyBatchUploadDrawer({
  onClose,
  onDone,
}: {
  onClose: () => void;
  onDone: () => void;
}) {
  const t = useTranslations("admin.policyBatch");
  const [items, setItems] = useState<BatchItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [batchError, setBatchError] = useState<string | null>(null);

  const updateItem = (id: string, patch: Partial<BatchItem>) => {
    setItems((current) => current.map((item) => (item.id === id ? { ...item, ...patch } : item)));
  };

  const inspectItem = async (item: BatchItem) => {
    updateItem(item.id, { status: "inspecting", error: null });
    try {
      const result = await consoleApi.inspectPolicyFile(item.file);
      updateItem(item.id, {
        status: "ready",
        result,
        documentCode: result.detected_document_code ?? "",
        title: result.detected_title ?? item.file.name.replace(/\.[^.]+$/, ""),
        version: result.detected_version ?? "",
        effectiveDate: result.detected_effective_date ?? "",
        error: null,
      });
    } catch (caught) {
      updateItem(item.id, {
        status: "error",
        error: caught instanceof Error ? caught.message : t("readError"),
      });
    }
  };

  const addFiles = async (files: File[]) => {
    setBatchError(null);
    const remaining = MAX_FILES - items.length;
    if (remaining <= 0) {
      setBatchError(t("filesPerBatch", { count: MAX_FILES }));
      return;
    }
    const accepted = files.slice(0, remaining);
    if (accepted.length < files.length) {
      setBatchError(t("acceptedFiles", { count: accepted.length, max: MAX_FILES }));
    }
    const next = accepted.map<BatchItem>((file, index) => ({
      id: itemId(file, items.length + index),
      file,
      status: "inspecting",
      result: null,
      documentCode: "",
      title: file.name.replace(/\.[^.]+$/, ""),
      category: "",
      version: "",
      effectiveDate: "",
      error: null,
    }));
    setItems((current) => [...current, ...next]);
    setSelectedId((current) => current ?? next[0]?.id ?? null);
    await runWithConcurrency(next, INSPECT_CONCURRENCY, inspectItem);
  };

  const uploadItem = async (item: BatchItem) => {
    if (!isReady(item)) return;
    updateItem(item.id, { status: "uploading", error: null });
    try {
      await consoleApi.uploadPolicy(item.file, {
        document_code: item.documentCode.trim(),
        title: item.title.trim(),
        policy_category: item.category,
        version: item.version.trim() || undefined,
        effective_date: item.effectiveDate || undefined,
      });
      updateItem(item.id, { status: "success", error: null });
    } catch (caught) {
      updateItem(item.id, {
        status: "error",
        error: caught instanceof Error ? caught.message : t("uploadError"),
      });
    }
  };

  const uploadAll = async () => {
    const ready = items.filter(isReady);
    if (!ready.length) return;
    await runWithConcurrency(ready, UPLOAD_CONCURRENCY, uploadItem);
    onDone();
  };

  const retryItem = async (item: BatchItem) => {
    if (item.result) {
      await uploadItem({ ...item, status: "ready" });
      onDone();
      return;
    }
    await inspectItem(item);
  };

  const selected = items.find((item) => item.id === selectedId) ?? null;
  const counts = useMemo(
    () => ({
      success: items.filter((item) => item.status === "success").length,
      error: items.filter((item) => item.status === "error").length,
      working: items.filter((item) => item.status === "inspecting" || item.status === "uploading")
        .length,
      ready: items.filter(isReady).length,
    }),
    [items],
  );
  const busy = counts.working > 0;
  const completed = counts.success + counts.error;
  const progress = items.length ? Math.round((completed / items.length) * 100) : 0;
  const categories: Record<string, string> = {
    COMPANY_POLICY: t("categoryCompanyPolicy"),
    HR_POLICY: t("categoryHr"),
    SECURITY_POLICY: t("categorySecurity"),
    BENEFIT: t("categoryBenefits"),
    WORKING_RULE: t("categoryWorkingRules"),
    GENERAL: t("categoryGeneral"),
  };
  const statusMeta: Record<BatchStatus, { label: string; className: string; dot: string }> = {
    inspecting: {
      label: t("statusReading"),
      className: "border-tint-navy-border bg-tint-navy text-link",
      dot: "bg-navy animate-pulse",
    },
    ready: {
      label: t("statusReady"),
      className: "border-success-border bg-success-bg text-success-text",
      dot: "bg-success",
    },
    uploading: {
      label: t("statusLoading"),
      className: "border-warn-border bg-warn-bg text-warn-text",
      dot: "bg-warn animate-pulse",
    },
    success: {
      label: t("statusComplete"),
      className: "border-success-border bg-success-bg text-success-text",
      dot: "bg-success",
    },
    error: {
      label: t("statusNeedsAttention"),
      className: "border-danger-border bg-danger-bg text-danger",
      dot: "bg-danger",
    },
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#0b1c30]/40 p-3 md:p-6">
      <section
        role="dialog"
        aria-modal="true"
        aria-label={t("dialogLabel")}
        className="flex h-[min(900px,94vh)] w-full max-w-[1180px] flex-col overflow-hidden rounded-md border border-border bg-canvas"
      >
        <header className="flex items-center justify-between border-b border-divider bg-white px-5 py-4 md:px-7">
          <div>
            <h2 className="text-lg font-semibold text-text">{t("title")}</h2>
            <p className="mt-1 text-xs text-text-subtle">
              {t("filesPerBatch", { count: MAX_FILES })}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="rounded-md border border-border-strong bg-surface px-4 py-2 text-[13px] font-semibold text-navy hover:bg-canvas disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-link"
          >
            {t("close")}
          </button>
        </header>

        <div className="grid min-h-0 flex-1 md:grid-cols-[370px_1fr]">
          <aside className="flex min-h-0 flex-col border-r border-divider bg-white">
            <div className="border-b border-divider p-4">
              <label className="flex cursor-pointer items-center justify-center gap-2 rounded-md border-2 border-dashed border-tint-navy-border bg-tint-navy px-4 py-4 text-sm font-semibold text-link transition hover:border-link focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-link">
                <span className="text-xl leading-none">＋</span>
                {t("chooseDocuments")}
                <input
                  type="file"
                  multiple
                  accept=".md,.markdown,.pdf,.docx"
                  disabled={busy || items.length >= MAX_FILES}
                  onChange={(event) => {
                    const files = Array.from(event.target.files ?? []);
                    event.target.value = "";
                    if (files.length) void addFiles(files);
                  }}
                  className="sr-only"
                />
              </label>
              <p className="mt-2 text-center text-xs leading-5 text-text-subtle">
                .md, .markdown, .pdf, .docx · up to 3 files are read at a time
              </p>
              {items.some((item) => item.result && item.status !== "success") && (
                <label className="mt-3 block text-xs font-bold text-text-secondary">
                  {t("applyCategory")}
                  <select
                    defaultValue=""
                    disabled={busy}
                    onChange={(event) => {
                      const category = event.target.value;
                      if (!category) return;
                      setItems((current) =>
                        current.map((item) =>
                          item.result && item.status !== "success" ? { ...item, category } : item,
                        ),
                      );
                    }}
                    className="mt-1.5 h-10 w-full cursor-pointer rounded-md border border-border-strong bg-white px-2 text-sm font-normal outline-none transition focus:border-link focus:ring-2 focus:ring-tint-navy"
                  >
                    <option value="" disabled>
                      {t("applyToAll")}
                    </option>
                    {Object.entries(categories).map(([key, label]) => (
                      <option key={key} value={key}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {items.length > 0 && (
                <div className="mt-4 rounded-md bg-surface-2 p-3">
                  <div className="flex justify-between text-xs font-bold text-text-secondary">
                    <span>{t("filesQueued", { count: items.length })}</span>
                    <span>{progress}%</span>
                  </div>
                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-3">
                    <div
                      className="h-full rounded-full bg-navy transition-all duration-300"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                  <div className="mt-2 flex gap-3 text-[11px] font-semibold">
                    <span className="text-success-text">✓ {counts.success} xong</span>
                    <span className="text-danger">
                      ! {t("failedCount", { count: counts.error })}
                    </span>
                    <span className="text-link">● {counts.working} processing</span>
                  </div>
                </div>
              )}
            </div>

            <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
              {!items.length && (
                <div className="px-5 py-14 text-center">
                  <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-md border border-border bg-accent-bg text-accent">
                    <FileIcon aria-hidden="true" size={24} />
                  </div>
                  <p className="mt-4 text-sm font-bold text-navy">{t("emptyTitle")}</p>
                  <p className="mt-1 text-xs leading-5 text-text-subtle">{t("emptyBody")}</p>
                </div>
              )}
              {items.map((item) => {
                const needsInfo = item.status === "ready" && !isReady(item);
                const meta = needsInfo
                  ? {
                      label: t("statusMissingInformation"),
                      className: "border-warn-border bg-warn-bg text-warn-text",
                      dot: "bg-warn",
                    }
                  : statusMeta[item.status];
                const active = item.id === selectedId;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setSelectedId(item.id)}
                    className={`w-full rounded-md border p-3 text-left transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-link ${
                      active
                        ? "border-link bg-tint-navy"
                        : "border-border bg-white hover:border-border-strong"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-navy">{item.file.name}</p>
                        <p className="mt-1 text-[11px] text-text-subtle">
                          {formatSize(item.file.size)}
                        </p>
                      </div>
                      <span
                        className={`shrink-0 rounded border px-2 py-1 text-[11px] font-medium ${meta.className}`}
                      >
                        <i className={`mr-1 inline-block h-1.5 w-1.5 rounded-full ${meta.dot}`} />
                        {meta.label}
                      </span>
                    </div>
                    {item.documentCode && (
                      <p className="mt-2 truncate font-mono text-[11px] font-semibold text-text-secondary">
                        {item.documentCode}
                      </p>
                    )}
                    {item.error && (
                      <p className="mt-2 line-clamp-2 text-xs text-danger">{item.error}</p>
                    )}
                  </button>
                );
              })}
            </div>
          </aside>

          <main className="min-h-0 overflow-y-auto p-4 md:p-6 lg:p-7">
            {!selected && (
              <div className="flex h-full min-h-[360px] items-center justify-center">
                <p className="max-w-sm text-center text-sm text-text-subtle">
                  {t("selectDocument")}
                </p>
              </div>
            )}

            {selected && (
              <div className="mx-auto max-w-[720px]">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="break-all text-[15px] font-semibold text-text">
                      {selected.file.name}
                    </h3>
                  </div>
                  {selected.status !== "uploading" && selected.status !== "success" && (
                    <button
                      type="button"
                      onClick={() => {
                        const next = items.filter((item) => item.id !== selected.id);
                        setItems(next);
                        setSelectedId(next[0]?.id ?? null);
                      }}
                      className="rounded-md border border-danger-border bg-white px-3 py-2 text-xs font-bold text-danger"
                    >
                      {t("removeFromBatch")}
                    </button>
                  )}
                </div>

                {selected.status === "inspecting" && (
                  <div className="mt-6 rounded-md border border-tint-navy-border bg-white p-8 text-center">
                    <div className="mx-auto h-9 w-9 animate-spin rounded-full border-4 border-surface-3 border-t-navy" />
                    <p className="mt-4 text-sm font-bold text-navy">
                      Reading and detecting metadata…
                    </p>
                  </div>
                )}

                {selected.error && (
                  <div className="mt-5 flex items-start justify-between gap-4 rounded-md border border-danger-border bg-danger-bg p-4">
                    <div>
                      <p className="text-sm font-semibold text-danger">{t("retryTitle")}</p>
                      <p className="mt-1 text-sm leading-6 text-danger">{selected.error}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => void retryItem(selected)}
                      className="shrink-0 rounded-md bg-white px-3 py-2 text-xs font-semibold text-danger"
                    >
                      {t("retry")}
                    </button>
                  </div>
                )}

                {selected.result && (
                  <div className="mt-5 space-y-5 rounded-md border border-border bg-white p-5 md:p-6">
                    {selected.status === "success" && (
                      <div className="rounded-md border border-success-border bg-success-bg p-4 text-sm font-bold text-success-text">
                        ✓ The document was saved and activated.
                      </div>
                    )}
                    {selected.result.existing_document_id !== null &&
                      selected.documentCode === selected.result.detected_document_code && (
                        <div className="rounded-md border border-tint-navy-border bg-tint-navy p-4 text-sm leading-6 text-link">
                          Code <b>{selected.documentCode}</b> already exists. This becomes a new
                          version of &ldquo;{selected.result.existing_document_title}&rdquo;.
                        </div>
                      )}
                    {selected.result.warnings.map((warning) => (
                      <p
                        key={warning}
                        className="rounded-md border border-warn-border bg-warn-bg p-3 text-sm leading-6 text-warn-text"
                      >
                        {warning}
                      </p>
                    ))}

                    <div className="grid gap-4 md:grid-cols-2">
                      <label className="text-sm font-bold text-text-secondary md:col-span-2">
                        {t("policyName")}
                        <input
                          value={selected.title}
                          disabled={
                            selected.status === "uploading" || selected.status === "success"
                          }
                          onChange={(event) =>
                            updateItem(selected.id, { title: event.target.value })
                          }
                          className="mt-2 h-11 w-full rounded-md border border-border-strong px-3 font-normal disabled:bg-canvas"
                        />
                      </label>
                      <label className="text-sm font-bold text-text-secondary">
                        {t("documentCode")}
                        <input
                          value={selected.documentCode}
                          disabled={
                            selected.status === "uploading" || selected.status === "success"
                          }
                          onChange={(event) =>
                            updateItem(selected.id, { documentCode: event.target.value })
                          }
                          placeholder="HR_LEAVE_POLICY"
                          className="mt-2 h-11 w-full rounded-md border border-border-strong px-3 font-mono text-sm font-normal disabled:bg-canvas"
                        />
                      </label>
                      <label className="text-sm font-bold text-text-secondary">
                        {t("category")}
                        <select
                          value={selected.category}
                          disabled={
                            selected.status === "uploading" || selected.status === "success"
                          }
                          onChange={(event) =>
                            updateItem(selected.id, { category: event.target.value })
                          }
                          className="mt-2 h-11 w-full rounded-md border border-border-strong bg-white px-3 font-normal disabled:bg-canvas"
                        >
                          <option value="" disabled>
                            {t("chooseCategory")}
                          </option>
                          {Object.entries(categories).map(([key, label]) => (
                            <option key={key} value={key}>
                              {label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="text-sm font-bold text-text-secondary">
                        {t("versionNumber")}
                        <input
                          value={selected.version}
                          readOnly={Boolean(selected.result.detected_version)}
                          disabled={
                            selected.status === "uploading" || selected.status === "success"
                          }
                          onChange={(event) =>
                            updateItem(selected.id, { version: event.target.value })
                          }
                          placeholder="3.2"
                          className="mt-2 h-11 w-full rounded-md border border-border-strong px-3 font-normal read-only:bg-canvas read-only:text-text-muted"
                        />
                      </label>
                      <label className="text-sm font-bold text-text-secondary">
                        {t("effectiveDate")}
                        <input
                          type="date"
                          value={selected.effectiveDate}
                          readOnly={Boolean(selected.result.detected_version)}
                          disabled={
                            selected.status === "uploading" || selected.status === "success"
                          }
                          onChange={(event) =>
                            updateItem(selected.id, { effectiveDate: event.target.value })
                          }
                          className="mt-2 h-11 w-full rounded-md border border-border-strong px-3 font-normal read-only:bg-canvas read-only:text-text-muted"
                        />
                      </label>
                    </div>

                    <details className="rounded-md border border-border bg-canvas p-4">
                      <summary className="cursor-pointer text-sm font-semibold text-navy">
                        {t("convertedPreview")}
                      </summary>
                      {/* Render có định dạng thay vì in Markdown thô: HR đang kiểm tra
                          chất lượng chuyển đổi, mà dấu # và ** làm việc đó khó hơn. */}
                      <div className="mt-3 max-h-64 overflow-auto rounded-md bg-white p-4">
                        <MarkdownView
                          source={selected.result.markdown_preview}
                          className="text-[13px] leading-6"
                        />
                      </div>
                    </details>
                  </div>
                )}
              </div>
            )}
          </main>
        </div>

        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-divider bg-white px-5 py-4 md:px-7">
          <div className="text-xs text-text-subtle">
            {counts.success > 0 && (
              <b className="text-success-text">{t("filesDone", { count: counts.success })}</b>
            )}
            {counts.success > 0 && counts.error > 0 && " · "}
            {counts.error > 0 && (
              <b className="text-danger">{t("filesNeedRetry", { count: counts.error })}</b>
            )}
            {!counts.success && !counts.error && t("footerHint")}
          </div>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={busy}
              className="h-11 rounded-md border border-border-strong px-5 text-sm font-semibold text-navy disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-link"
            >
              {counts.success ? t("complete") : t("cancel")}
            </button>
            <button
              type="button"
              onClick={() => void uploadAll()}
              disabled={!counts.ready || busy}
              className="h-11 rounded-md bg-navy px-5 text-sm font-semibold text-white transition hover:bg-navy-hover disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-link"
            >
              {busy ? "Processing…" : `Upload ${counts.ready || ""} files`}
            </button>
          </div>
        </footer>

        {batchError && (
          <div
            role="alert"
            className="absolute top-5 left-1/2 z-10 -translate-x-1/2 rounded-md bg-danger px-4 py-3 text-sm font-bold text-white"
          >
            {batchError}
          </div>
        )}
      </section>
    </div>
  );
}
