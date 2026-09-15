"use client";

import { useCallback, useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { consoleApi } from "./api";
import type { PolicyCoverage, PolicyCoverageDetail } from "./types";

const formatDate = (value: string | null, locale: string) =>
  value
    ? new Intl.DateTimeFormat(locale, {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      }).format(new Date(value))
    : "—";

const formatDateTime = (value: string | null, locale: string) =>
  value
    ? new Intl.DateTimeFormat(locale, {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      }).format(new Date(value))
    : "—";

/**
 * Ngưỡng màu cho tỷ lệ xác nhận.
 *
 * Ba mức chứ không phải hai: nếu chỉ có "đạt/không đạt" thì mọi chính sách vừa ban hành
 * đều đỏ, và HR sẽ học cách bỏ qua màu đỏ.
 */
const categoryKeys: Record<
  string,
  | "categoryCompanyPolicy"
  | "categoryHr"
  | "categorySecurity"
  | "categoryBenefits"
  | "categoryWorkingRules"
  | "categoryGeneral"
> = {
  COMPANY_POLICY: "categoryCompanyPolicy",
  HR_POLICY: "categoryHr",
  SECURITY_POLICY: "categorySecurity",
  BENEFIT: "categoryBenefits",
  WORKING_RULE: "categoryWorkingRules",
  GENERAL: "categoryGeneral",
};

function coverageTone(percent: number) {
  if (percent >= 90) return { bar: "bg-success", text: "text-success-text" };
  if (percent >= 50) return { bar: "bg-warn", text: "text-warn-text" };
  return { bar: "bg-danger", text: "text-danger" };
}

function CoverageBar({ percent, label }: { percent: number; label: string }) {
  const tone = coverageTone(percent);
  return (
    <div className="flex items-center gap-3">
      <div
        className="h-2 w-28 overflow-hidden rounded-full bg-surface-2"
        role="img"
        aria-label={label}
      >
        <div className={`h-full rounded-full ${tone.bar}`} style={{ width: `${percent}%` }} />
      </div>
      <b className={`text-sm tabular-nums ${tone.text}`}>{percent}%</b>
    </div>
  );
}

function CoverageDrawer({
  documentId,
  onClose,
  onChanged,
}: {
  documentId: number;
  onClose: () => void;
  onChanged: () => void;
}) {
  const t = useTranslations("admin.policyCoverage");
  const locale = useLocale();
  const [detail, setDetail] = useState<PolicyCoverageDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setDetail(await consoleApi.policyCoverageDetail(documentId));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("detailsLoadError"));
    }
  }, [documentId, t]);

  useEffect(() => {
    // Hoãn sang macrotask: gọi thẳng thì setState chạy đồng bộ trong effect và React
    // cảnh báo cascading render.
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const toggleRequired = async () => {
    if (!detail) return;
    setBusy(true);
    setError(null);
    try {
      setDetail(
        await consoleApi.setPolicyAckRequired(documentId, !detail.requires_acknowledgement),
      );
      onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("settingUpdateError"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-[#0b1c30]/30">
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={t("dialogLabel")}
        className="flex h-full w-full max-w-[560px] flex-col border-l border-border bg-surface"
      >
        <header className="flex items-start justify-between border-b border-divider px-7 py-5">
          <div>
            <p className="text-xs font-semibold text-text-subtle">{t("eyebrow")}</p>
            <h2 className="mt-2 text-xl font-bold text-navy">{detail?.title ?? t("loading")}</h2>
            {detail?.version_no && (
              <p className="mt-1 text-sm text-text-subtle">
                {t("version", { version: detail.version_no })}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-3 py-2 text-sm font-semibold hover:bg-canvas"
          >
            {t("close")}
          </button>
        </header>

        <div className="flex-1 overflow-auto px-7 py-6">
          {error && (
            <p
              role="alert"
              className="mb-5 rounded-md border border-danger-border bg-danger-bg p-3 text-sm leading-6 text-danger"
            >
              {error}
            </p>
          )}

          {detail && (
            <>
              <div className="mb-6 flex items-center justify-between rounded-md border border-border bg-canvas p-4">
                <div>
                  <p className="text-sm font-bold text-navy">{t("requireAcknowledgement")}</p>
                  <p className="mt-1 text-xs text-text-subtle">{t("requireAcknowledgementHint")}</p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={detail.requires_acknowledgement}
                  disabled={busy}
                  onClick={toggleRequired}
                  className={`h-7 w-12 shrink-0 rounded-full transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-link ${
                    detail.requires_acknowledgement ? "bg-navy" : "bg-border-strong"
                  } disabled:opacity-50`}
                >
                  <span
                    className={`block h-5 w-5 rounded-full bg-white transition ${
                      detail.requires_acknowledgement ? "translate-x-6" : "translate-x-1"
                    }`}
                  />
                </button>
              </div>

              {/* Danh sách CHƯA xác nhận đứng trước — đó mới là thứ HR cần để đi nhắc.
                  Danh sách đã xác nhận chỉ dùng khi cần đối chiếu. */}
              <section>
                <h3 className="text-sm font-bold text-navy">
                  {t("notAcknowledged", { count: detail.pending.length })}
                </h3>
                {detail.pending.length === 0 ? (
                  <p className="mt-3 rounded-md border border-success-border bg-success-bg p-3 text-sm text-success-text">
                    {t("everyoneAcknowledged")}
                  </p>
                ) : (
                  <ul className="mt-3 divide-y divide-divider rounded-md border border-border">
                    {detail.pending.map((user) => (
                      <li key={user.user_id} className="px-4 py-3">
                        <b className="text-sm text-navy">{user.display_name}</b>
                        <p className="text-xs text-text-subtle">{user.email}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section className="mt-7">
                <h3 className="text-sm font-bold text-navy">
                  {t("acknowledged", { count: detail.acknowledged.length })}
                </h3>
                {detail.acknowledged.length === 0 ? (
                  <p className="mt-3 text-sm text-text-subtle">{t("nobodyAcknowledged")}</p>
                ) : (
                  <ul className="mt-3 divide-y divide-divider rounded-md border border-border">
                    {detail.acknowledged.map((user) => (
                      <li
                        key={user.user_id}
                        className="flex items-center justify-between px-4 py-3"
                      >
                        <div>
                          <b className="text-sm text-navy">{user.display_name}</b>
                          <p className="text-xs text-text-subtle">{user.email}</p>
                        </div>
                        <span className="text-xs text-text-subtle">
                          {formatDateTime(user.acknowledged_at, locale)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}

export function PolicyCoveragePanel() {
  const t = useTranslations("admin.policyCoverage");
  const locale = useLocale();
  const [items, setItems] = useState<PolicyCoverage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await consoleApi.policyCoverage();
      setItems(response.items);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("coverageLoadError"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    // Hoãn sang macrotask: gọi thẳng thì setState chạy đồng bộ trong effect và React
    // cảnh báo cascading render.
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  return (
    <section className="rounded-md border border-border bg-surface">
      <header className="flex items-center justify-between gap-4 border-b border-border px-5 py-4">
        <div className="min-w-0">
          <h2 className="text-[14px] font-semibold text-text">{t("title")}</h2>
          <p className="mt-0.5 text-[13px] text-text-subtle">{t("description")}</p>
        </div>
        <button
          type="button"
          onClick={load}
          className="h-[34px] flex-shrink-0 rounded-md border border-border px-3 text-[12.5px] font-semibold text-text-secondary transition hover:bg-surface-2"
        >
          {t("reload")}
        </button>
      </header>

      {loading ? (
        <div className="space-y-3 p-6">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="h-12 animate-pulse rounded-md bg-skeleton-faint" />
          ))}
        </div>
      ) : error ? (
        <div className="p-8 text-center">
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
      ) : items.length === 0 ? (
        <p className="p-12 text-center text-sm text-text-subtle">{t("empty")}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[880px] text-left">
            {/* Bỏ nền hardcode #fafbfe và chữ hoa: `.ralion-console table th` ở
                globals.css đã lo nền chìm, chiều cao và cỡ chữ cho mọi bảng trong
                console. Giữ màu cứng ở đây là cách bảng này lệch khỏi các bảng khác. */}
            <thead>
              <tr>
                {[
                  "policy",
                  "category",
                  "versionHeader",
                  "effectiveDate",
                  "acknowledgedHeader",
                  "rate",
                ].map((heading) => (
                  <th key={heading}>
                    {t(heading)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.document_id}>
                  <td>
                    {/* Nút thật thay vì onClick trên <tr>: bàn phím và trình đọc màn hình
                        phải mở được chi tiết. */}
                    <button
                      type="button"
                      onClick={() => setSelected(item.document_id)}
                      className="rounded text-left text-sm font-bold text-navy underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-link"
                    >
                      {item.title}
                    </button>
                  </td>
                  <td className="text-[13.5px]">
                    {t(categoryKeys[item.policy_category] ?? "categoryGeneral")}
                  </td>
                  <td className="text-[13.5px]">
                    {item.version_no ? `v${item.version_no}` : "—"}
                  </td>
                  <td className="text-[13.5px]">{formatDate(item.effective_date, locale)}</td>
                  <td className="text-[13.5px] tabular-nums">
                    {item.acknowledged_count}/{item.required_count}
                  </td>
                  <td>
                    <CoverageBar
                      percent={item.coverage_percent}
                      label={t("acknowledgedPercent", { percent: item.coverage_percent })}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected !== null && (
        <CoverageDrawer documentId={selected} onClose={() => setSelected(null)} onChanged={load} />
      )}
    </section>
  );
}
