"use client";

import { Link } from "@/i18n/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocale } from "next-intl";
import { FileIcon, SearchIcon } from "@primer/octicons-react";

import { LogoutButton } from "@/components/auth/LogoutButton";
import { BrandHomeLink } from "@/components/brand/BrandHomeLink";
import { RalionBrand } from "@/components/brand/RalionBrand";
import { useSession } from "@/features/auth/session";

import { consoleApi } from "./api";
import type { ConsolePolicy, PolicyDetail } from "./types";
import { PolicyBatchUploadDrawer } from "./PolicyBatchUploadDrawer";
import { PolicyCoveragePanel } from "./PolicyCoveragePanel";
import { PolicyDocumentModal } from "./PolicyDocumentModal";

const categories: Record<string, string> = {
  COMPANY_POLICY: "Company policy",
  HR_POLICY: "HR",
  SECURITY_POLICY: "Security",
  BENEFIT: "Benefits",
  WORKING_RULE: "Working rules",
  GENERAL: "Chung",
};
const statusLabel: Record<string, string> = {
  ACTIVE: "Active",
  PROCESSING: "Processing",
  FAILED: "Processing failed",
  ARCHIVED: "Archived",
};
const statusClass: Record<string, string> = {
  ACTIVE: "border-success-border bg-success-bg text-success-text",
  PROCESSING: "border-warn-border bg-warn-bg text-warn-text",
  FAILED: "border-danger-border bg-danger-bg text-danger",
  ARCHIVED: "border-border bg-canvas text-text-muted",
};
// effective_date có thể null (tài liệu cũ chưa có), nên nhận cả null thay vì để
// nơi gọi tự kiểm tra — quên một chỗ là hiện "Invalid Date" trên bảng.
/** Chữ cái đầu của tên, dùng cho avatar tròn. */
const initials = (name?: string | null) =>
  (name ?? "")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(-2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("") || "?";

const formatDate = (value: string | null, locale: string) =>
  value
    ? new Intl.DateTimeFormat(locale === "vi" ? "vi-VN" : "en-GB", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      }).format(new Date(value))
    : "—";

function Status({ value }: { value: string | null }) {
  const key = value ?? "ARCHIVED";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border px-2 py-1 text-xs font-medium ${statusClass[key]}`}
    >
      <i className="h-1.5 w-1.5 rounded-full bg-current" />
      {statusLabel[key] ?? "No version yet"}
    </span>
  );
}

export function HRPolicyLibrary() {
  const locale = useLocale();
  const [items, setItems] = useState<ConsolePolicy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [status, setStatus] = useState("all");
  const [selected, setSelected] = useState<PolicyDetail | null>(null);
  // Tạo mới và tải phiên bản mới dùng chung một drawer — backend tự phân biệt
  // qua document_code, nên UI không cần hai luồng riêng.
  const [form, setForm] = useState(false);
  // Hai góc nhìn trên cùng dữ liệu: "thư viện" là tài liệu có gì,
  // "xác nhận" là ai đã đọc. HR cần cả hai nhưng không cùng lúc.
  const [view, setView] = useState<"library" | "coverage">("library");
  const [ackBusy, setAckBusy] = useState(false);
  const [viewerOpen, setViewerOpen] = useState(false);
  const { user: sessionUser } = useSession();
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [restoreOpen, setRestoreOpen] = useState(false);
  const [statusBusy, setStatusBusy] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [detailWarning, setDetailWarning] = useState<string | null>(null);
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: "1", page_size: "100" });
      if (query) params.set("query", query);
      const result = await consoleApi.policies(params);
      setItems(result.items);
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Policies could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [query]);
  useEffect(() => {
    const id = window.setTimeout(load, 150);
    return () => window.clearTimeout(id);
  }, [load]);

  const openedFromUrl = useRef(false);
  const filtered = useMemo(
    () =>
      items.filter(
        (item) =>
          (category === "all" || item.policy_category === category) &&
          (status === "all" || item.version_status === status),
      ),
    [items, category, status],
  );
  // useCallback vì effect mở tài liệu theo ?document_id= phụ thuộc vào hàm này; không
  // bọc thì mỗi lần render lại tạo hàm mới và effect chạy vô hạn.
  const select = useCallback(async (item: ConsolePolicy) => {
    setSelected({ ...item, source_url: "Chưa có thông tin nguồn trong dữ liệu danh sách." });
    setDetailWarning(null);
    try {
      setSelected(await consoleApi.policy(item.document_id));
    } catch {
      setDetailWarning(
        "Full metadata could not be loaded. Basic policy information is still available.",
      );
    }
  }, []);

  // Mở sẵn tài liệu được chỉ đích danh qua ?document_id=... — dùng cho nút cảnh báo ở
  // trang tổng quan Admin. Thiếu bước này thì người dùng rơi vào danh sách hàng chục
  // chính sách mà không biết phải sửa cái nào.
  //
  // Ref chứ không so với `selected`: đóng drawer xong thì nó không được tự mở lại.
  useEffect(() => {
    if (openedFromUrl.current || items.length === 0) return;
    const raw = new URLSearchParams(window.location.search).get("document_id");
    const target = items.find((item) => item.document_id === Number(raw));
    if (!target) return;
    openedFromUrl.current = true;
    // Hoãn sang macrotask: gọi thẳng thì setState chạy đồng bộ trong effect và React
    // cảnh báo cascading render.
    const timer = window.setTimeout(() => void select(target), 0);
    return () => window.clearTimeout(timer);
  }, [items, select]);

  const archive = async () => {
    if (!selected) return;
    setStatusBusy(true);
    setStatusError(null);
    try {
      await consoleApi.archivePolicy(selected.document_id);
      setArchiveOpen(false);
      closeDetail();
      await load();
    } catch (caught) {
      setStatusError(caught instanceof Error ? caught.message : "Could not archive policy.");
    } finally {
      setStatusBusy(false);
    }
  };
  const restore = async () => {
    if (!selected) return;
    setStatusBusy(true);
    setStatusError(null);
    try {
      const restored = await consoleApi.restorePolicy(selected.document_id);
      setSelected(restored);
      setRestoreOpen(false);
      await load();
    } catch (caught) {
      setStatusError(caught instanceof Error ? caught.message : "Could not restore policy.");
    } finally {
      setStatusBusy(false);
    }
  };
  const reset = () => {
    setQuery("");
    setCategory("all");
    setStatus("all");
  };
  /** Đóng drawer chi tiết, đồng thời đóng modal xem tài liệu nếu đang mở. */
  const closeDetail = () => {
    setViewerOpen(false);
    setSelected(null);
  };

  /** Bật/tắt yêu cầu xác nhận đã đọc cho chính sách đang mở. */
  const toggleAckRequired = async () => {
    if (!selected) return;
    setAckBusy(true);
    try {
      await consoleApi.setPolicyAckRequired(
        selected.document_id,
        !selected.requires_acknowledgement,
      );
      setSelected({
        ...selected,
        requires_acknowledgement: !selected.requires_acknowledgement,
      });
      await load();
    } catch {
      // Giữ nguyên trạng thái cũ trên UI; người dùng bấm lại được.
    } finally {
      setAckBusy(false);
    }
  };

  return (
    <main className="ralion-console h-screen overflow-hidden bg-canvas text-text">
      <div className="flex h-full">
        {/* Cùng lớp `console-sidebar` với Admin: nền navy và bộ biến chữ đảo ngược
            đến từ globals.css, nên hai không gian làm việc không trôi ra hai kiểu. */}
        <aside className="console-sidebar hidden shrink-0 flex-col py-0 md:flex">
          <BrandHomeLink className="mb-1 inline-flex px-4 pt-4 pb-3.5">
            <RalionBrand size={26} />
          </BrandHomeLink>
          <p className="px-[18px] pt-2.5 pb-1.5 text-[10.5px] font-semibold uppercase tracking-[.06em] text-text-faint">
            HR workspace
          </p>
          <nav className="flex flex-col px-2.5">
            <span className="nav-console nav-console-active">
              <FileIcon aria-hidden="true" size={16} />
              Thư viện chính sách
            </span>
            {/* Admin vào đây qua nút "Bổ sung ngày" ở trang tổng quan. Không có link này
                thì họ mắc kẹt: sidebar HR chỉ có đúng một mục, và không ai nghĩ tới việc
                gõ tay /admin lên thanh địa chỉ. */}
            {sessionUser?.system_role === "ADMIN" && (
              <Link href="/admin" className="nav-console">
                <span aria-hidden="true">←</span>
                Về Admin Workspace
              </Link>
            )}
          </nav>
          <div className="console-account mx-2.5 mt-auto border-t border-border pt-2.5">
            <div className="flex items-center gap-2.5 rounded-md px-2 py-1.5">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-border-strong bg-surface-3 text-[11px] font-semibold text-text">
                {initials(sessionUser?.display_name)}
              </span>
              <div className="min-w-0">
                <p className="truncate text-[12.5px] font-semibold text-text">
                  {sessionUser?.display_name ?? "…"}
                </p>
                <p className="truncate text-[11px] text-text-faint">{sessionUser?.email ?? ""}</p>
              </div>
            </div>
            <LogoutButton className="mt-1 flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-[12px] font-medium text-text-faint transition hover:bg-surface-2 hover:text-text" />
          </div>
        </aside>
        <section className="flex min-w-0 flex-1 flex-col">
          <header className="console-topbar flex flex-none items-center justify-between border-b border-border bg-surface px-5 md:px-7">
            <div className="leading-[1.25]">
              <p className="text-[12.5px] font-semibold text-text">HR Workspace</p>
              <p className="hidden text-[11px] text-text-faint sm:block">Ralion · Nội bộ</p>
            </div>
          </header>
          <div className="flex-1 overflow-y-auto">
            <div className="mx-auto max-w-[1520px] px-5 pt-7 pb-10 md:px-8">
              <nav className="mb-3.5 flex items-center gap-1.5 text-[12.5px] text-text-faint">
                <span className="font-medium text-text-subtle">HR Workspace</span>
                <span>/</span>
                <span className="font-semibold text-text">Policy library</span>
              </nav>
              <div className="mb-[22px] flex items-start justify-between gap-6">
                <div className="min-w-0">
                  <h1 className="text-[24px] font-semibold tracking-[-0.015em] text-text">
                    Policy library
                  </h1>
                  <p className="mt-1 text-[13.5px] text-text-subtle">
                    Tài liệu phạm vi tổ chức dùng chung cho onboarding.
                  </p>
                </div>
                <button
                  onClick={() => setForm(true)}
                  className="mt-px flex h-9 flex-shrink-0 items-center gap-1.5 rounded-md border border-navy bg-navy px-[15px] text-[13px] font-semibold text-white transition hover:bg-navy-hover"
                >
                  <span aria-hidden="true" className="text-[15px] leading-none">
                    +
                  </span>
                  Upload document
                </button>
              </div>
              <div className="mb-1 flex gap-1 border-b border-border" role="tablist">
                {(
                  [
                    ["library", "Document library"],
                    ["coverage", "Acknowledgement"],
                  ] as const
                ).map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    role="tab"
                    aria-selected={view === key}
                    onClick={() => setView(key)}
                    className={`-mb-px border-b-2 px-4 py-2.5 text-[13px] font-semibold transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-link ${
                      view === key
                        ? "border-navy text-navy"
                        : "border-transparent text-text-subtle hover:text-navy"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {view === "coverage" ? (
                <div className="mt-7">
                  <PolicyCoveragePanel />
                </div>
              ) : (
                <>
                  {/* Toolbar nằm NGOÀI thẻ bảng, giống tab Admin và bản mẫu. Nhét bộ
                      lọc vào trong khung bảng khiến thẻ trông như hai bảng chồng nhau. */}
                  <div className="console-toolbar mt-5 mb-2.5 flex flex-wrap items-center gap-2">
                    <label className="flex h-[34px] min-w-[200px] flex-1 items-center gap-2 rounded-md border border-border bg-surface px-2.5 focus-within:border-navy sm:max-w-[340px]">
                      <span className="sr-only">Search</span>
                      <SearchIcon aria-hidden="true" className="shrink-0 text-text-faint" size={14} />
                      <input
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="Search by policy name"
                        className="h-full flex-1 border-none bg-transparent text-[13px] text-text outline-none"
                      />
                    </label>
                    <select
                      value={category}
                      onChange={(e) => setCategory(e.target.value)}
                      className="h-[34px] cursor-pointer rounded-md border border-border bg-surface px-2.5 text-[12.5px] font-medium text-text-subtle"
                    >
                      <option value="all">Category: All</option>
                      {Object.entries(categories).map(([key, label]) => (
                        <option key={key} value={key}>
                          {label}
                        </option>
                      ))}
                    </select>
                    <select
                      value={status}
                      onChange={(e) => setStatus(e.target.value)}
                      className="h-[34px] cursor-pointer rounded-md border border-border bg-surface px-2.5 text-[12.5px] font-medium text-text-subtle"
                    >
                      <option value="all">Status: All</option>
                      {Object.entries(statusLabel).map(([key, label]) => (
                        <option key={key} value={key}>
                          {label}
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={reset}
                      className="h-[34px] px-2 text-[12.5px] font-semibold text-link transition hover:text-navy-hover"
                    >
                      Clear filters
                    </button>
                  </div>
                  <p
                    aria-live="polite"
                    className="mb-2 text-right text-[12px] text-text-faint"
                  >
                    {filtered.length} matching policies
                  </p>
                  <section className="overflow-hidden rounded-md border border-border bg-surface">
                    {loading ? (
                      <div className="p-8 text-sm text-text-subtle">Loading the library…</div>
                    ) : error ? (
                      <div className="m-5 rounded-md border border-danger-border bg-danger-bg p-4 text-sm text-danger">
                        {error}
                      </div>
                    ) : filtered.length === 0 ? (
                      <p className="p-12 text-center text-sm text-text-subtle">
                        No matching policies.
                      </p>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full min-w-[1080px] text-left">
                          <thead>
                            <tr>
                              {[
                                "Policy",
                                // "Miền kiến thức" bị bỏ: mọi dòng đều là "Chính sách" nên cột
                                // đó không phân biệt được gì. Mã tài liệu mới là thứ HR tra cứu.
                                "Document code",
                                "Category",
                                "Version",
                                "Effective date",
                                "Updated",
                                "Status",
                                "",
                              ].map((h) => (
                                <th key={h}>{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {filtered.map((item) => (
                              <tr
                                key={item.document_id}
                                tabIndex={0}
                                role="button"
                                aria-label={`View details for ${item.title}`}
                                onClick={() => select(item)}
                                onKeyDown={(event) => {
                                  if (event.key === "Enter" || event.key === " ") {
                                    event.preventDefault();
                                    select(item);
                                  }
                                }}
                                className="cursor-pointer border-b border-divider last:border-0 outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-link"
                              >
                                <td>
                                  <b className="text-[13px] font-semibold text-text">
                                    {item.title}
                                  </b>
                                  <p className="mt-0.5 text-xs text-text-subtle">
                                    Updated by {item.created_by_name ?? "—"}
                                  </p>
                                </td>
                                <td className="font-mono text-xs text-text-secondary">
                                  {item.source_key ?? "—"}
                                </td>
                                <td>{categories[item.policy_category]}</td>
                                <td>{item.version_no ? `v${item.version_no}` : "—"}</td>
                                <td>
                                  {item.effective_date ? (
                                    formatDate(item.effective_date, locale)
                                  ) : (
                                    <span className="inline-flex items-center rounded border border-warn-border bg-warn-bg px-2 py-0.5 text-[11px] font-semibold text-warn-text">
                                      Missing date
                                    </span>
                                  )}
                                </td>
                                <td>{formatDate(item.created_at, locale)}</td>
                                <td>
                                  <Status value={item.version_status} />
                                </td>
                                <td className="text-link">›</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </section>
                </>
              )}
            </div>
          </div>
        </section>
      </div>
      {viewerOpen && selected && (
        <PolicyDocumentModal
          documentId={selected.document_id}
          sourceUrl={selected.source_url}
          archived={selected.status === "ARCHIVED"}
          onClose={() => setViewerOpen(false)}
        />
      )}
      {form && <PolicyBatchUploadDrawer onClose={() => setForm(false)} onDone={load} />}
      {selected && (
        <div className="fixed inset-0 z-40 flex justify-end bg-[#0b1c30]/30">
          <aside
            role="dialog"
            aria-modal="true"
            className="h-full w-full max-w-[500px] overflow-auto border-l border-border bg-surface p-6"
          >
            <div className="flex justify-between">
              <div>
                <p className="text-xs font-bold tracking-[.1em] text-accent">POLICY DETAILS</p>
                <h2 className="mt-2 text-xl font-bold text-navy">{selected.title}</h2>
                <p className="mt-2 text-[13px] text-text-subtle">
                  {categories[selected.policy_category]}
                </p>
              </div>
              <button
                onClick={() => closeDetail()}
                className="h-9 rounded-md px-3 text-[13px] font-semibold hover:bg-canvas focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-link"
              >
                Close
              </button>
            </div>
            <div className="mt-7 space-y-4">
              {detailWarning && (
                <p className="rounded-md border border-warn-border bg-warn-bg p-3 text-sm text-warn-text">
                  {detailWarning}
                </p>
              )}
              {statusError && (
                <p role="alert" className="rounded-md border border-danger-border bg-danger-bg p-3 text-sm text-danger">
                  {statusError}
                </p>
              )}
              <div className="border-t border-divider pt-4">
                <div className="flex items-center gap-3">
                  <Status value={selected.version_status} />
                  <span className="text-[13px] text-text-subtle">
                    {selected.version_no ? `v${selected.version_no}` : "No version yet"}
                  </span>
                </div>
              </div>
              <div className="border-t border-divider pt-4">
                {/* Mở modal đọc ngay trong ứng dụng thay vì link thẳng tới Cloudinary —
                    link đó mở tab mới rồi tải file về, HR phải mở bằng ứng dụng ngoài
                    chỉ để xem lướt một điều khoản. Nút tải file gốc nằm trong modal. */}
                <button
                  type="button"
                  onClick={() => setViewerOpen(true)}
                  className="h-9 rounded-md border border-navy px-3 text-[13px] font-semibold text-navy"
                >
                  View document
                </button>
                <p className="mt-3 text-[13px] text-text-subtle">
                  Created by {selected.created_by_name ?? "—"} · {formatDate(selected.created_at, locale)}
                </p>
              </div>
            </div>
            {/* Công tắc phải nằm ở ĐÂY chứ không chỉ ở tab Tỷ lệ xác nhận: tab đó chỉ
                liệt kê chính sách đã bật cờ, nên nếu để riêng bên đó thì không có
                đường bật lần đầu. */}
            <div className="mt-6 flex items-center justify-between border-t border-divider pt-4">
              <div className="pr-4">
                <p className="text-[13px] font-semibold text-text">Require read acknowledgement</p>
                <p className="mt-1 text-xs leading-5 text-text-subtle">
                  Employees must read and acknowledge this policy.
                </p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={selected.requires_acknowledgement}
                aria-label="Require read acknowledgement"
                disabled={ackBusy || selected.status !== "ACTIVE"}
                onClick={toggleAckRequired}
                className={`h-7 w-12 shrink-0 rounded-full transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-link ${
                  selected.requires_acknowledgement ? "bg-navy" : "bg-border-strong"
                } disabled:opacity-50`}
              >
                <span
                  className={`block h-5 w-5 rounded-full bg-white transition ${
                    selected.requires_acknowledgement ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
            </div>
            {selected.status === "ACTIVE" && (
              <div className="mt-7 flex flex-wrap gap-3">
                <button
                  onClick={() => setForm(true)}
                  className="h-9 rounded-md border border-navy px-4 text-[13px] font-semibold text-navy"
                >
                  Upload a new version
                </button>
                <button
                  onClick={() => setArchiveOpen(true)}
                  className="h-9 rounded-md border border-danger-border bg-danger-bg px-4 text-[13px] font-semibold text-danger"
                >
                  Archive policy
                </button>
              </div>
            )}
            {selected.status === "ARCHIVED" && (
              <div className="mt-7">
                <button
                  onClick={() => {
                    setStatusError(null);
                    setRestoreOpen(true);
                  }}
                  className="h-9 rounded-md bg-navy px-4 text-[13px] font-semibold text-white transition hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-link"
                >
                  Restore policy
                </button>
              </div>
            )}
          </aside>
        </div>
      )}
      {archiveOpen && selected && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-[#0b1c30]/40 p-4">
          <div
            role="dialog"
            aria-modal="true"
            className="w-full max-w-md rounded-md border border-border bg-surface p-6"
          >
            <h2 className="text-lg font-bold text-navy">Archive this policy?</h2>
            <p className="mt-3 text-sm leading-6 text-text-subtle">
              The policy stops being active, but its version history is kept.
            </p>
            <div className="mt-4 rounded-md bg-canvas p-3 text-sm">
              <b>{selected.title}</b>
              <p className="mt-1 text-text-subtle">
                Version {selected.version_no ? `v${selected.version_no}` : "—"}
              </p>
            </div>
            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => setArchiveOpen(false)}
                disabled={statusBusy}
                className="h-10 rounded-md border border-border-strong px-4 text-sm font-bold"
              >
                Cancel
              </button>
              <button
                onClick={archive}
                disabled={statusBusy}
                className="h-10 rounded-md bg-danger px-4 text-sm font-bold text-white transition hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-link"
              >
                {statusBusy ? "Archiving…" : "Archive policy"}
              </button>
            </div>
          </div>
        </div>
      )}
      {restoreOpen && selected && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-[#0b1c30]/40 p-4">
          <div
            role="dialog"
            aria-modal="true"
            className="w-full max-w-md rounded-md border border-border bg-surface p-6"
          >
            <h2 className="text-lg font-bold text-navy">Restore this policy?</h2>
            <p className="mt-3 text-sm leading-6 text-text-subtle">
              Its latest revision will become active again for PMs, engineers, chat, and newly generated onboarding plans.
            </p>
            <div className="mt-4 rounded-md bg-canvas p-3 text-sm">
              <b>{selected.title}</b>
              <p className="mt-1 text-text-subtle">
                Version {selected.version_no ? `v${selected.version_no}` : "—"}
              </p>
            </div>
            {statusError && <p role="alert" className="mt-4 text-sm text-danger">{statusError}</p>}
            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => setRestoreOpen(false)}
                disabled={statusBusy}
                className="h-10 rounded-md border border-border-strong px-4 text-sm font-bold disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={restore}
                disabled={statusBusy}
                className="h-10 rounded-md bg-navy px-4 text-sm font-bold text-white transition hover:opacity-90 disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-link"
              >
                {statusBusy ? "Restoring…" : "Restore policy"}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
