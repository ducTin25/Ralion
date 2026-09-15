"use client";

import { Link } from "@/i18n/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArrowRightIcon as ArrowIcon } from "@primer/octicons-react";

import { consoleApi } from "./api";
import type {
  AdminRiskItem,
  AdminUnassignedUser,
  MembershipEligibility,
  PageMeta,
  RiskKind,
} from "./types";

const UNASSIGNED_PAGE_SIZE = 5;

/** Nhãn ngắn cho từng loại cảnh báo, để nhận ra vấn đề mà không phải đọc hết mô tả. */
const RISK_KIND_LABELS: Record<RiskKind, string> = {
  INACTIVE_USER_IN_PROJECT: "Tài khoản đã khoá",
  PROJECT_WITHOUT_PM: "Thiếu PM",
  PENDING_ACCESS_OVERDUE: "Quyền chờ quá hạn",
  ACTIVE_USER_NO_MEMBERSHIP: "Chưa vào dự án",
  STALE_POLICY: "Chính sách quá hạn",
  POLICY_MISSING_EFFECTIVE_DATE: "Thiếu ngày hiệu lực",
};

/* ----------------------------------------------------------------- helpers */

function initials(name: string) {
  return (
    name
      .trim()
      .split(/\s+/)
      .slice(-2)
      .map((part) => part[0] ?? "")
      .join("")
      .toUpperCase() || "?"
  );
}

const ROLE_LABEL: Record<string, string> = {
  ADMIN: "Administrator",
  HR: "HR",
};

function RoleBadge({ role }: { role: "ADMIN" | "HR" | null }) {
  if (role === null) {
    return <span className="text-[12px] text-text-subtle">No system role</span>;
  }
  return (
    <span className="inline-flex items-center rounded border border-tint-navy-border bg-tint-navy px-2 py-1 text-[11px] font-semibold text-link">
      {ROLE_LABEL[role]}
    </span>
  );
}

/* --------------------------------------------------------- assign dialog */

function AssignMembershipDialog({
  user,
  onClose,
  onSaved,
}: {
  user: { user_id: number; display_name: string; email: string };
  onClose: () => void;
  onSaved: () => void;
}) {
  const [eligibility, setEligibility] = useState<MembershipEligibility | null>(null);
  const [projectId, setProjectId] = useState("");
  const [projectRole, setProjectRole] = useState<"PM" | "ENGINEER">("ENGINEER");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void consoleApi
      .membershipEligibility()
      .then(setEligibility)
      .catch(() => setEligibility({ users: [], projects: [] }));
  }, []);

  // Only accounts returned by the eligibility endpoint can actually receive a
  // membership; anything else would be rejected by the API with a 422.
  const eligible = eligibility?.users.some((item) => item.user_id === user.user_id) ?? true;

  const submit = async () => {
    if (!projectId) return;
    setSaving(true);
    setError(null);
    try {
      await consoleApi.createMembership({
        user_id: user.user_id,
        project_id: Number(projectId),
        project_role: projectRole,
        status: "ACTIVE",
      });
      onSaved();
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The membership could not be assigned.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#0b1c30]/30 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Assign a project membership"
        className="w-full max-w-[440px] rounded-md border border-border bg-surface p-6"
      >
        <p className="text-[11px] font-bold uppercase tracking-[.1em] text-link">
          Assign membership
        </p>
        <h2 className="mt-2 text-lg font-bold text-navy">{user.display_name}</h2>
        <p className="mt-1 text-[13px] text-text-subtle">{user.email}</p>

        {eligible ? (
          <div className="mt-5 space-y-4">
            <label className="block text-[13px] font-semibold text-text-secondary">
              Active project
              <select
                value={projectId}
                onChange={(event) => setProjectId(event.target.value)}
                className="mt-1.5 h-10 w-full rounded-md border border-border-strong bg-surface px-3 text-[13px] font-normal outline-none focus:border-link"
              >
                <option value="" disabled>
                  {eligibility ? "Select a project" : "Loading projects…"}
                </option>
                {eligibility?.projects.map((project) => (
                  <option key={project.project_id} value={project.project_id}>
                    {project.name} — {project.key}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-[13px] font-semibold text-text-secondary">
              Project role
              <select
                value={projectRole}
                onChange={(event) => setProjectRole(event.target.value as "PM" | "ENGINEER")}
                className="mt-1.5 h-10 w-full rounded-md border border-border-strong bg-surface px-3 text-[13px] font-normal outline-none focus:border-link"
              >
                <option value="ENGINEER">Engineer</option>
                <option value="PM">PM</option>
              </select>
            </label>
          </div>
        ) : (
          <p className="mt-5 rounded-md border border-warn-border bg-warn-bg p-3 text-[13px] leading-5 text-warn-text">
            This account holds a system role, so it cannot take a project membership. Remove the
            system role first if this person needs to join a project.
          </p>
        )}

        {error && (
          <p
            role="alert"
            className="mt-4 rounded-md border border-danger-border bg-danger-bg p-3 text-[13px] text-danger"
          >
            {error}
          </p>
        )}

        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="h-9 rounded-md border border-border-strong px-4 text-[13px] font-semibold text-navy hover:bg-canvas"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={saving || !projectId || !eligible}
            onClick={submit}
            className="h-9 rounded-md bg-navy px-4 text-[13px] font-semibold text-white transition hover:bg-navy-hover disabled:opacity-50"
          >
            {saving ? "Saving…" : "Assign membership"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------- main panel */

export function OverviewPanel() {
  const [risks, setRisks] = useState<AdminRiskItem[]>([]);
  const [riskTotal, setRiskTotal] = useState(0);
  const [risksLoading, setRisksLoading] = useState(true);
  const [unassigned, setUnassigned] = useState<AdminUnassignedUser[]>([]);
  const [unassignedMeta, setUnassignedMeta] = useState<PageMeta | null>(null);
  const [unassignedPage, setUnassignedPage] = useState(1);
  const [unassignedLoading, setUnassignedLoading] = useState(true);
  const [busyRiskId, setBusyRiskId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [assignTarget, setAssignTarget] = useState<{
    user_id: number;
    display_name: string;
    email: string;
  } | null>(null);

  const loadRisks = useCallback(() => {
    setRisksLoading(true);
    return consoleApi
      .riskItems(8)
      .then((result) => {
        setRisks(result.items);
        setRiskTotal(result.total);
      })
      .catch(() => {
        setRisks([]);
        setRiskTotal(0);
      })
      .finally(() => setRisksLoading(false));
  }, []);

  const loadUnassigned = useCallback(() => {
    setUnassignedLoading(true);
    const params = new URLSearchParams({
      page: String(unassignedPage),
      page_size: String(UNASSIGNED_PAGE_SIZE),
    });
    return consoleApi
      .unassignedUsers(params)
      .then((result) => {
        setUnassigned(result.items);
        setUnassignedMeta(result.meta);
      })
      .catch(() => {
        setUnassigned([]);
        setUnassignedMeta(null);
      })
      .finally(() => setUnassignedLoading(false));
  }, [unassignedPage]);

  // Deferred with a 0ms timer so the loading flags are not set synchronously
  // inside the effect body, matching the pattern used by AdminConsoleScreen.
  useEffect(() => {
    const timer = window.setTimeout(loadRisks, 0);
    return () => window.clearTimeout(timer);
  }, [loadRisks]);
  useEffect(() => {
    const timer = window.setTimeout(loadUnassigned, 0);
    return () => window.clearTimeout(timer);
  }, [loadUnassigned]);

  const refreshAll = useCallback(() => {
    void loadRisks();
    void loadUnassigned();
  }, [loadRisks, loadUnassigned]);

  // Revoking stale access deactivates the membership rather than deleting it so the
  // assignment history stays auditable.
  const revokeMembership = async (risk: AdminRiskItem) => {
    if (risk.membership_id === null) return;
    setBusyRiskId(risk.risk_id);
    setActionError(null);
    try {
      await consoleApi.updateMembership(risk.membership_id, { status: "INACTIVE" });
      refreshAll();
    } catch (caught) {
      setActionError(
        caught instanceof Error ? caught.message : "The membership could not be updated.",
      );
    } finally {
      setBusyRiskId(null);
    }
  };

  return (
    <div className="console-overview">
      {actionError && (
        <p
          role="alert"
          className="mt-4 rounded-md border border-danger-border bg-danger-bg px-4 py-3 text-[13px] text-danger"
        >
          {actionError}
        </p>
      )}

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        {/* Action required */}
        <section className="flex flex-col overflow-hidden rounded-md border border-border bg-surface xl:col-span-1">
          <header className="flex items-center justify-between gap-3 border-b border-divider px-4 py-3">
            <h3 className="text-[14px] font-semibold text-text">Needs attention</h3>
            {riskTotal > 0 && (
              <span className="text-[13px] tabular-nums text-text-subtle">{riskTotal}</span>
            )}
          </header>

          <div className="flex-1">
            {risksLoading && (
              <div className="space-y-2 p-3">
                {Array.from({ length: 3 }, (_, index) => (
                  <div
                    key={index}
                    className="h-[76px] animate-[project-skeleton_1.5s_ease-in-out_infinite] rounded-md bg-skeleton-soft"
                  />
                ))}
              </div>
            )}

            {!risksLoading && risks.length === 0 && (
              <p className="px-2 py-6 text-center text-[13px] text-text-subtle">
                Nothing needs attention.
              </p>
            )}

            {!risksLoading && risks.length > 0 && (
              <ul className="divide-y divide-divider">
                {risks.map((risk, index) => (
                  <li key={risk.risk_id} className="px-4 py-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span
                            className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                              risk.severity === "HIGH" ? "bg-danger" : "bg-warn"
                            }`}
                          />
                          {/* title đầy đủ trong tooltip: tên tài liệu và tên dự án thường
                              dài hơn cột và bị cắt bằng truncate. */}
                          <p
                            title={risk.title}
                            className="truncate text-[13px] font-bold text-navy"
                          >
                            {risk.title}
                          </p>
                          <span className="shrink-0 rounded border border-border bg-surface px-1.5 py-0.5 text-[10px] font-semibold text-text-subtle">
                            {RISK_KIND_LABELS[risk.kind]}
                          </span>
                        </div>
                        {/* Chỉ in mô tả khi nó KHÁC dòng ngay trên. Ba chính sách cùng
                            thiếu ngày hiệu lực sinh ra ba câu chữ y hệt nhau, mắt không
                            quét được. Danh sách đã sắp theo (mức độ, loại, tên) nên các
                            mục trùng luôn nằm liền nhau; nhãn loại ở trên giữ ngữ cảnh
                            cho những dòng bị lược. */}
                        {(index === 0 || risks[index - 1].message !== risk.message) && (
                          <p className="mt-1.5 text-[12px] leading-5 text-text-subtle">
                            {risk.message}
                          </p>
                        )}
                      </div>
                      {risk.kind === "INACTIVE_USER_IN_PROJECT" ? (
                        <button
                          type="button"
                          disabled={busyRiskId === risk.risk_id}
                          onClick={() => revokeMembership(risk)}
                          className="shrink-0 rounded-md border border-danger-border px-3 py-1.5 text-[12px] font-semibold text-danger transition hover:bg-danger-bg disabled:opacity-50"
                        >
                          {busyRiskId === risk.risk_id ? "Removing…" : risk.action_label}
                        </button>
                      ) : risk.kind === "ACTIVE_USER_NO_MEMBERSHIP" && risk.user_id !== null ? (
                        <button
                          type="button"
                          onClick={() =>
                            setAssignTarget({
                              user_id: risk.user_id as number,
                              display_name: risk.title,
                              email: risk.user_email ?? "",
                            })
                          }
                          className="shrink-0 rounded-md border border-border-strong px-3 py-1.5 text-[12px] font-semibold text-link transition hover:bg-canvas"
                        >
                          {risk.action_label}
                        </button>
                      ) : (
                        <Link
                          // Mỗi loại risk phải dẫn tới một màn hình còn tồn tại. Các
                          // cảnh báo quyền quá hạn nay quay về membership vì hàng đợi
                          // cấp quyền riêng đã được gỡ khỏi console.
                          href={
                            risk.kind === "PENDING_ACCESS_OVERDUE"
                              ? risk.project_id !== null
                                ? `/admin/memberships?project_id=${risk.project_id}`
                                : "/admin/memberships"
                              : risk.document_id !== null
                                ? // Kèm document_id để thư viện tự mở đúng tài liệu.
                                  // Thiếu tham số này thì người dùng rơi vào danh sách
                                  // 13 chính sách mà không biết phải sửa cái nào.
                                  `/hr?document_id=${risk.document_id}`
                                : risk.project_id !== null
                                  ? // Cùng lý do: "Gán PM" mà đổ về danh sách membership
                                    // chung thì admin phải tự nhớ dự án nào đang thiếu.
                                    `/admin/memberships?project_id=${risk.project_id}`
                                  : "/admin/memberships"
                          }
                          className="shrink-0 rounded-md border border-border-strong px-3 py-1.5 text-[12px] font-semibold text-link transition hover:bg-canvas"
                        >
                          {risk.action_label}
                        </Link>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {riskTotal > risks.length && (
            <footer className="border-t border-divider px-4 py-2.5 text-[12px] text-text-subtle">
              Showing {risks.length} of {riskTotal} items.
            </footer>
          )}
        </section>

        {/* Unassigned users */}
        <section className="flex flex-col overflow-hidden rounded-md border border-border bg-surface xl:col-span-2">
          <header className="flex items-center justify-between gap-3 border-b border-divider px-4 py-3">
            <h3 className="text-[14px] font-semibold text-text">Not in any project</h3>
            <Link
              href="/admin/memberships"
              className="flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[12px] font-semibold text-link transition hover:bg-tint-navy"
            >
              View all
              <ArrowIcon />
            </Link>
          </header>

          <div className="flex-1 overflow-x-auto">
            {unassignedLoading && (
              <div className="space-y-2 p-3">
                {Array.from({ length: 4 }, (_, index) => (
                  <div
                    key={index}
                    className="h-11 animate-[project-skeleton_1.5s_ease-in-out_infinite] rounded bg-skeleton-soft"
                  />
                ))}
              </div>
            )}

            {!unassignedLoading && unassigned.length === 0 && (
              <p className="px-6 py-12 text-center text-[13px] text-text-subtle">
                Every active account already has a membership.
              </p>
            )}

            {!unassignedLoading && unassigned.length > 0 && (
              <table className="w-full min-w-[600px] border-collapse text-left">
                <thead>
                  <tr>
                    <th className="px-4 py-3 text-[11px] font-bold uppercase tracking-[.07em] text-text-subtle">
                      People
                    </th>
                    <th className="px-4 py-3 text-[11px] font-bold uppercase tracking-[.07em] text-text-subtle">
                      System role
                    </th>
                    <th className="px-4 py-3 text-right text-[11px] font-bold uppercase tracking-[.07em] text-text-subtle">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {unassigned.map((user) => (
                    <tr key={user.user_id} className="border-b border-divider last:border-0">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-tint-navy text-[11px] font-bold text-link">
                            {initials(user.display_name)}
                          </span>
                          <div className="min-w-0">
                            <p className="truncate text-[13px] font-semibold text-navy">
                              {user.display_name}
                            </p>
                            <p className="truncate text-[12px] text-text-subtle">{user.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <RoleBadge role={user.system_role} />
                        {user.inactive_membership_count > 0 && (
                          <p className="mt-1 text-[11px] text-warn-text">
                            {user.inactive_membership_count} inactive memberships
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          type="button"
                          onClick={() =>
                            setAssignTarget({
                              user_id: user.user_id,
                              display_name: user.display_name,
                              email: user.email,
                            })
                          }
                          className="rounded-md border border-link px-3 py-1.5 text-[12px] font-semibold text-link transition hover:bg-link hover:text-white"
                        >
                          Assign membership
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-divider px-4 py-2.5">
            <p className="text-[12px] text-text-subtle">
              {unassignedMeta
                ? `Showing ${unassigned.length} of ${unassignedMeta.total} accounts`
                : "—"}
            </p>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={unassignedPage === 1}
                onClick={() => setUnassignedPage((page) => page - 1)}
                className="pager-console h-8 text-[12px]"
              >
                Previous
              </button>
              <span className="text-[12px] text-text-subtle">Page {unassignedPage}</span>
              <button
                type="button"
                disabled={
                  !unassignedMeta || unassignedPage * UNASSIGNED_PAGE_SIZE >= unassignedMeta.total
                }
                onClick={() => setUnassignedPage((page) => page + 1)}
                className="pager-console h-8 text-[12px]"
              >
                Next
              </button>
            </div>
          </footer>
        </section>
      </div>

      {assignTarget && (
        <AssignMembershipDialog
          user={assignTarget}
          onClose={() => setAssignTarget(null)}
          onSaved={refreshAll}
        />
      )}
    </div>
  );
}
