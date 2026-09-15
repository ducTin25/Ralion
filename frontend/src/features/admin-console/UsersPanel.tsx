"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertIcon as PrimerAlertIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  LockIcon,
  SearchIcon,
  UnlockIcon,
  XIcon as CloseIcon,
} from "@primer/octicons-react";

import { ConsoleApiError, consoleApi } from "./api";
import { ConsoleAvatar } from "./ConsoleAvatar";
import { DeactivateUserDialog } from "./DeactivateUserDialog";
import { ResetPasswordDialog } from "./ResetPasswordDialog";
import type { ConsoleUser, ConsoleUserDetail, PageMeta } from "./types";

const PAGE_SIZE = 8;
const SEARCH_DEBOUNCE_MS = 300;

const AlertIcon = () => <PrimerAlertIcon aria-hidden="true" size={24} />;

/* ----------------------------------------------------------------- helpers */

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}

function RoleChip({ role }: { role: ConsoleUser["system_role"] }) {
  if (role === "ADMIN") {
    return (
      <span className="inline-flex items-center rounded border border-role-admin-border bg-role-admin-bg px-2 py-0.5 text-[11px] font-bold text-role-admin-text">
        ADMIN
      </span>
    );
  }
  if (role === "HR") {
    return (
      <span className="inline-flex items-center rounded border border-role-hr-border bg-role-hr-bg px-2 py-0.5 text-[11px] font-bold text-role-hr-text">
        HR
      </span>
    );
  }
  return <span className="text-[12px] text-text-subtle">No system role</span>;
}

function StatusDot({ active }: { active: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-[12px] ${active ? "text-text" : "text-text-subtle"}`}
    >
      <span className={`h-2 w-2 rounded-full ${active ? "bg-success" : "bg-text-faint"}`} />
      {active ? "Active" : "Locked"}
    </span>
  );
}

/** Dùng chung với các tab khác, xem ConsoleAvatar.tsx. */
const Avatar = ConsoleAvatar;

/* ------------------------------------------------------------ detail drawer */

function UserDetailDrawer({
  detail,
  loading,
  onClose,
  onRetry,
  onToggleStatus,
  toggling,
  onChangeStartDate,
  savingStartDate,
  error,
  onSaveProfile,
  savingProfile,
  onResetPassword,
}: {
  detail: ConsoleUserDetail | null;
  loading: boolean;
  onClose: () => void;
  onRetry: () => void;
  onToggleStatus: () => void;
  toggling: boolean;
  onChangeStartDate: (value: string) => Promise<void>;
  savingStartDate: boolean;
  error: string | null;
  /** Trả về true khi lưu thành công, để form tự đóng chế độ sửa. */
  onSaveProfile: (patch: Record<string, unknown>) => Promise<boolean>;
  savingProfile: boolean;
  onResetPassword: () => void;
}) {
  const active = detail?.status === "ACTIVE";
  // Lưu user_id đang sửa thay vì một cờ boolean: đổi sang tài khoản khác thì form tự
  // đóng, không cần effect đồng bộ. Giữ cờ boolean sẽ để lại defaultValue của người cũ
  // trên màn hình của người mới.
  const [editingFor, setEditingFor] = useState<number | null>(null);
  const editing = detail !== null && editingFor === detail.user_id;
  const setEditing = (value: boolean | ((current: boolean) => boolean)) => {
    const next = typeof value === "function" ? value(editing) : value;
    setEditingFor(next && detail ? detail.user_id : null);
  };
  return (
    <aside
      aria-label="Account details"
      className="flex h-full w-full flex-col overflow-hidden border-l border-border bg-surface"
    >
      {loading && !detail ? (
        <div className="space-y-3 p-6">
          <div className="mx-auto h-20 w-20 animate-[project-skeleton_1.5s_ease-in-out_infinite] rounded-full bg-skeleton-soft" />
          <div className="mx-auto h-5 w-40 animate-[project-skeleton_1.5s_ease-in-out_infinite] rounded bg-skeleton-soft" />
          <div className="mx-auto h-4 w-52 animate-[project-skeleton_1.5s_ease-in-out_infinite] rounded bg-skeleton-soft" />
          <div className="h-32 animate-[project-skeleton_1.5s_ease-in-out_infinite] rounded-md bg-skeleton-soft" />
        </div>
      ) : !detail ? (
        /* Without this branch a failed detail request left the drawer completely blank. */
        <div className="relative flex h-full flex-col items-center justify-center px-6 text-center">
          <button
            type="button"
            onClick={onClose}
            aria-label="Close details"
            className="absolute top-4 right-4 rounded-full p-1.5 text-text-subtle transition hover:bg-canvas hover:text-navy"
          >
            <CloseIcon />
          </button>
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-danger-bg text-danger">
            <AlertIcon />
          </span>
          <p className="mt-3 text-[14px] font-bold text-navy">Details could not be loaded</p>
          <p className="mt-1 text-[12px] leading-5 text-text-subtle">
            {error ?? "The server returned no data for this account."}
          </p>
          <button
            type="button"
            onClick={onRetry}
            className="mt-4 h-9 rounded-md bg-navy px-4 text-[13px] font-semibold text-white transition hover:bg-navy-hover"
          >
            Try again
          </button>
        </div>
      ) : (
        <>
          {/* Identity header */}
          <header className="relative flex flex-col items-center border-b border-divider px-6 py-6 text-center">
            <button
              type="button"
              onClick={onClose}
              aria-label="Close details"
              className="absolute top-4 right-4 rounded-full p-1.5 text-text-subtle transition hover:bg-canvas hover:text-navy"
            >
              <CloseIcon />
            </button>
            <Avatar name={detail.display_name} size={80} />
            <h2 className="mt-4 text-[19px] font-bold text-navy">{detail.display_name}</h2>
            <p className="mt-1 text-[13px] break-all text-text-subtle">{detail.email}</p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              <a
                href={`mailto:${detail.email}`}
                className="rounded-md border border-border-strong px-3 py-1.5 text-[13px] font-medium text-navy transition hover:bg-canvas"
              >
                Send email
              </a>
              <button
                type="button"
                onClick={() => setEditing((value) => !value)}
                className="rounded-md border border-border-strong px-3 py-1.5 text-[13px] font-medium text-navy transition hover:bg-canvas"
              >
                {editing ? "Huỷ sửa" : "Sửa hồ sơ"}
              </button>
              {/* Hệ thống chưa có luồng "quên mật khẩu" tự phục vụ, nên đây là đường duy
                  nhất để một nhân viên quên mật khẩu quay lại làm việc. */}
              <button
                type="button"
                onClick={onResetPassword}
                className="rounded-md border border-border-strong px-3 py-1.5 text-[13px] font-medium text-navy transition hover:bg-canvas"
              >
                Đặt lại mật khẩu
              </button>
            </div>
          </header>

          <div className="flex-1 overflow-y-auto px-6 py-6">
            {editing && (
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  const form = new FormData(event.currentTarget);
                  const role = String(form.get("system_role") ?? "");
                  void onSaveProfile({
                    display_name: String(form.get("display_name") ?? "").trim(),
                    email: String(form.get("email") ?? "").trim(),
                    // Backend phân biệt "không đổi" (bỏ trường) với "gỡ quyền" (cờ riêng),
                    // vì `null` không diễn đạt được cả hai.
                    ...(role ? { system_role: role } : { clear_system_role: true }),
                  }).then((ok: boolean) => ok && setEditing(false));
                }}
                className="mb-7 rounded-lg border border-border bg-canvas p-4"
              >
                <h3 className="text-[11px] font-bold tracking-[.08em] uppercase text-text-subtle">
                  Sửa hồ sơ
                </h3>
                <label className="mt-3 block text-[13px] font-semibold text-text-secondary">
                  Họ và tên
                  <input
                    name="display_name"
                    defaultValue={detail.display_name}
                    required
                    className="mt-1.5 h-9 w-full rounded-md border border-border-strong bg-surface px-2.5 text-[13px] font-normal"
                  />
                </label>
                <label className="mt-3 block text-[13px] font-semibold text-text-secondary">
                  Email
                  <input
                    name="email"
                    type="email"
                    defaultValue={detail.email}
                    required
                    className="mt-1.5 h-9 w-full rounded-md border border-border-strong bg-surface px-2.5 text-[13px] font-normal"
                  />
                </label>
                <label className="mt-3 block text-[13px] font-semibold text-text-secondary">
                  Quyền hệ thống
                  <select
                    name="system_role"
                    defaultValue={detail.system_role ?? ""}
                    className="mt-1.5 h-9 w-full rounded-md border border-border-strong bg-surface px-2.5 text-[13px] font-normal"
                  >
                    <option value="">Không có quyền hệ thống</option>
                    <option value="ADMIN">Quản trị viên</option>
                    <option value="HR">Nhân sự</option>
                  </select>
                </label>
                {/* Cấp quyền hệ thống cho người đang ở trong dự án là mâu thuẫn: ADMIN/HR
                    không được phép có membership. Nói trước để admin không bấm rồi mới
                    nhận lỗi từ server. */}
                {detail.system_role === null && detail.active_project_count > 0 && (
                  <p className="mt-2 text-xs leading-5 text-warn-text">
                    Tài khoản đang có {detail.active_project_count} membership hoạt động. Cấp quyền
                    hệ thống có thể bị từ chối.
                  </p>
                )}
                <button
                  type="submit"
                  disabled={savingProfile}
                  className="mt-4 h-9 w-full rounded-md bg-navy text-[13px] font-bold text-white disabled:opacity-50"
                >
                  {savingProfile ? "Đang lưu…" : "Lưu thay đổi"}
                </button>
              </form>
            )}

            {/* System info */}
            <section>
              <h3 className="text-[11px] font-semibold tracking-[.06em] uppercase text-text-subtle">
                System information
              </h3>
              <dl className="mt-4 space-y-3.5">
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-[13px] text-text-subtle">System role</dt>
                  <dd>
                    <RoleChip role={detail.system_role} />
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-[13px] text-text-subtle">Account status</dt>
                  <dd className="flex items-center gap-2.5">
                    <span className="text-[13px] font-semibold text-navy">
                      {active ? "Active" : "Locked"}
                    </span>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={active}
                      aria-label="Toggle account status"
                      disabled={toggling}
                      onClick={onToggleStatus}
                      className={`relative h-5 w-9 shrink-0 rounded-full transition disabled:opacity-50 ${
                        active ? "bg-navy" : "bg-disabled-bg ring-1 ring-border-strong"
                      }`}
                    >
                      <span
                        className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all ${
                          active ? "left-[18px]" : "left-0.5"
                        }`}
                      />
                    </button>
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-[13px] text-text-subtle">Start date</dt>
                  <dd>
                    {/* Sửa được ngay tại đây: tài khoản tạo trước khi có cột này đều
                        trống, và trước đó không có màn hình nào sửa hồ sơ. */}
                    <input
                      type="date"
                      value={detail.start_date ?? ""}
                      disabled={savingStartDate}
                      onChange={(event) => void onChangeStartDate(event.target.value)}
                      className="h-8 rounded-md border border-border-strong px-2 text-[13px] text-navy disabled:opacity-50"
                    />
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-[13px] text-text-subtle">Mật khẩu</dt>
                  <dd>
                    {/* Tài khoản còn dùng mật khẩu do admin đặt là nhóm rủi ro nhất —
                        admin biết mật khẩu của họ. Trước đây dữ liệu này có trong API
                        nhưng không màn hình nào hiển thị. */}
                    {detail.must_change_password ? (
                      <span className="inline-flex items-center rounded border border-warn-border bg-warn-bg px-2 py-0.5 text-[12px] font-semibold text-warn-text">
                        Chưa tự đổi
                      </span>
                    ) : (
                      <span className="text-[13px] font-medium text-navy">Đã tự đặt</span>
                    )}
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-[13px] text-text-subtle">Quyền truy cập chờ cấp</dt>
                  <dd>
                    {detail.pending_access_count > 0 ? (
                      <span className="inline-flex items-center rounded border border-warn-border bg-warn-bg px-2 py-0.5 text-[12px] font-semibold text-warn-text">
                        {detail.pending_access_count} quyền →
                      </span>
                    ) : (
                      <span className="text-[13px] font-medium text-navy">Không có</span>
                    )}
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-[13px] text-text-subtle">Ngày tạo</dt>
                  <dd className="text-[13px] font-medium text-navy">
                    {formatDate(detail.created_at)}
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-[13px] text-text-subtle">Created by</dt>
                  <dd className="text-[13px] font-medium text-navy">
                    {detail.created_by_name ?? "System"}
                  </dd>
                </div>
              </dl>
            </section>

            {error && (
              <p
                role="alert"
                className="mt-4 rounded-md border border-danger-border bg-danger-bg p-3 text-[13px] text-danger"
              >
                {error}
              </p>
            )}

            {/* Memberships */}
            <section className="mt-8">
              <h3 className="text-[11px] font-semibold tracking-[.06em] uppercase text-text-subtle">
                Project memberships ({detail.memberships.length})
              </h3>
              {detail.memberships.length === 0 ? (
                <p className="mt-4 text-[13px] leading-5 text-text-subtle">
                  {detail.system_role
                    ? "This account holds a system role, so it cannot take a project membership."
                    : "No membership yet — this account cannot open any project workspace."}
                </p>
              ) : (
                <ul className="mt-4 space-y-3">
                  {detail.memberships.map((membership) => (
                    <li
                      key={membership.membership_id}
                      className={`rounded-md border border-border p-3 transition hover:border-border-hover ${
                        membership.status === "ACTIVE" ? "bg-surface" : "bg-canvas opacity-75"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-[14px] font-semibold text-navy">
                          {membership.project_name}
                        </p>
                        <span className="shrink-0 font-mono text-[11px] text-text-faint">
                          {membership.project_key}
                        </span>
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <span className="inline-flex items-center rounded border border-border bg-canvas px-2 py-0.5 text-[11px] font-bold text-text-muted">
                          {membership.project_role === "PM" ? "PM" : "Engineer"}
                        </span>
                        {membership.status !== "ACTIVE" && (
                          <span className="inline-flex items-center rounded border border-warn-border bg-warn-bg px-2 py-0.5 text-[11px] font-semibold text-warn-text">
                            Inactive
                          </span>
                        )}
                        {membership.project_status === "ARCHIVED" && (
                          <span className="inline-flex items-center rounded border border-border bg-canvas px-2 py-0.5 text-[11px] font-medium text-text-subtle">
                            Project archived
                          </span>
                        )}
                        <span className="text-[12px] text-text-subtle">
                          Joined {formatDate(membership.joined_at)}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>

          {/* Footer action */}
          <footer className="border-t border-divider p-4">
            <button
              type="button"
              disabled={toggling}
              onClick={onToggleStatus}
              className={`flex w-full items-center justify-center gap-2 rounded-md px-4 py-2.5 text-[13px] font-semibold transition disabled:opacity-50 ${
                active
                  ? "border border-danger-border bg-danger-bg text-danger hover:bg-surface"
                  : "bg-navy text-white hover:bg-navy-hover"
              }`}
            >
              {active ? <LockIcon /> : <UnlockIcon />}
              {toggling ? "Updating…" : active ? "Lock account" : "Unlock account"}
            </button>
            {active && (
              <p className="mt-2 text-center text-[11px] leading-4 text-text-subtle">
                Khoá tài khoản sẽ huỷ ngay phiên đăng nhập hiện tại. Bước xác nhận liệt kê đầy đủ
                membership và quyền cần thu hồi.
              </p>
            )}
          </footer>
        </>
      )}
    </aside>
  );
}

/* -------------------------------------------------------------- main panel */

export function UsersPanel({ reloadToken }: { reloadToken: number }) {
  const [rawQuery, setRawQuery] = useState("");
  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [startFilter, setStartFilter] = useState("all");
  const [passwordFilter, setPasswordFilter] = useState("all");
  const [page, setPage] = useState(1);

  const [rows, setRows] = useState<ConsoleUser[]>([]);
  const [meta, setMeta] = useState<PageMeta | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ConsoleUserDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [toggling, setToggling] = useState(false);
  // user_id đang chờ xác nhận khoá; null = không có hộp thoại nào mở.
  const [deactivating, setDeactivating] = useState<number | null>(null);
  const [savingStartDate, setSavingStartDate] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  // user_id đang mở hộp thoại đặt lại mật khẩu; null = không mở.
  const [resetting, setResetting] = useState<number | null>(null);

  // Debounce typing so a search does not fire a request per keystroke.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQuery(rawQuery);
      setPage(1);
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [rawQuery]);

  const params = useMemo(() => {
    const next = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    if (query.trim()) next.set("query", query.trim());
    // Role and status are independent server-side filters, so both can apply at once.
    if (roleFilter !== "all") next.set("system_role", roleFilter);
    if (statusFilter !== "all") next.set("account_status", statusFilter);
    if (startFilter !== "all") next.set("start_status", startFilter);
    if (passwordFilter !== "all") next.set("password_state", passwordFilter);
    return next;
  }, [page, query, roleFilter, statusFilter, startFilter, passwordFilter]);

  const loadList = useCallback(() => {
    setLoading(true);
    setError(null);
    setErrorStatus(null);
    return consoleApi
      .users(params)
      .then((result) => {
        setRows(result.items);
        setMeta(result.meta);
      })
      .catch((caught) => {
        setRows([]);
        setMeta(null);
        setErrorStatus(caught instanceof ConsoleApiError ? caught.status : null);
        setError(caught instanceof Error ? caught.message : "Users could not be loaded.");
      })
      .finally(() => setLoading(false));
  }, [params]);

  useEffect(() => {
    const timer = window.setTimeout(loadList, 0);
    return () => window.clearTimeout(timer);
  }, [loadList, reloadToken]);

  const loadDetail = useCallback((userId: number) => {
    setDetailLoading(true);
    setDetailError(null);
    return consoleApi
      .userDetail(userId)
      .then(setDetail)
      .catch((caught) => {
        setDetail(null);
        setDetailError(caught instanceof Error ? caught.message : "Details could not be loaded.");
      })
      .finally(() => setDetailLoading(false));
  }, []);

  useEffect(() => {
    if (selectedId === null) return;
    const timer = window.setTimeout(() => loadDetail(selectedId), 0);
    return () => window.clearTimeout(timer);
  }, [selectedId, loadDetail]);

  // Clearing the detail lives with the selection change, not in an effect, so the
  // drawer never briefly shows the previous user's profile.
  const selectUser = (userId: number | null) => {
    setSelectedId(userId);
    setDetail(null);
    setDetailError(null);
  };

  /** Sửa ngày vào làm. Chuỗi rỗng nghĩa là xoá — dùng cờ riêng để phân biệt với
      "không đổi", giống cách xử lý quyền hệ thống. */
  const changeStartDate = async (value: string) => {
    if (!detail) return;
    setSavingStartDate(true);
    setDetailError(null);
    try {
      const updated = await consoleApi.updateUser(
        detail.user_id,
        value ? { start_date: value } : { clear_start_date: true },
      );
      setDetail(updated);
      loadList();
    } catch (caught) {
      setDetailError(caught instanceof Error ? caught.message : "Không lưu được ngày vào làm.");
    } finally {
      setSavingStartDate(false);
    }
  };

  /** Lưu tên, email và quyền hệ thống. Trả về true khi thành công để form tự đóng. */
  const saveProfile = async (patch: Record<string, unknown>) => {
    if (!detail) return false;
    setSavingProfile(true);
    setDetailError(null);
    try {
      setDetail(await consoleApi.updateUser(detail.user_id, patch));
      loadList();
      return true;
    } catch (caught) {
      setDetailError(caught instanceof Error ? caught.message : "Không lưu được hồ sơ.");
      return false;
    } finally {
      setSavingProfile(false);
    }
  };

  const toggleStatus = async () => {
    if (!detail) return;
    // Khoá là thao tác có hậu quả lan rộng (ngừng membership, huỷ phiên, để lại quyền
    // cần thu hồi tay) nên phải qua bước xác nhận nêu rõ từng thứ. MỞ khoá thì không —
    // nó chỉ trả lại quyền truy cập, không phá hỏng gì.
    if (detail.status === "ACTIVE") {
      setDeactivating(detail.user_id);
      return;
    }
    setToggling(true);
    setDetailError(null);
    try {
      await consoleApi.changeUserStatus(detail.user_id, "ACTIVE");
      await Promise.all([loadDetail(detail.user_id), loadList()]);
    } catch (caught) {
      setDetailError(
        caught instanceof Error ? caught.message : "The account status could not be changed.",
      );
    } finally {
      setToggling(false);
    }
  };

  const totalPages = meta ? Math.max(1, Math.ceil(meta.total / PAGE_SIZE)) : 1;
  const drawerOpen = selectedId !== null;

  return (
    <div className="console-users">
      {/* Toolbar */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-surface p-2.5">
        <div className="flex flex-1 flex-wrap items-center gap-2">
          <label className="relative min-w-[220px] flex-1 sm:max-w-[280px]">
            <span className="sr-only">Search users</span>
            <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-text-faint">
              <SearchIcon />
            </span>
            <input
              value={rawQuery}
              onChange={(event) => setRawQuery(event.target.value)}
              placeholder="Search by name or email…"
              className="h-9 w-full rounded-md border border-border-strong bg-surface pr-3 pl-9 text-[13px] outline-none transition focus:border-link focus:ring-2 focus:ring-tint-navy"
            />
          </label>
          <span className="hidden h-6 w-px bg-border sm:block" />
          <select
            value={roleFilter}
            onChange={(event) => {
              setRoleFilter(event.target.value);
              setPage(1);
            }}
            className="h-9 cursor-pointer rounded-md border border-border-strong bg-surface px-3 text-[13px] outline-none transition focus:border-link focus:ring-2 focus:ring-tint-navy"
          >
            <option value="all">System role: All</option>
            <option value="ADMIN">Administrator</option>
            <option value="HR">People</option>
            <option value="NONE">No access</option>
          </select>
          <select
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value);
              setPage(1);
            }}
            className="h-9 cursor-pointer rounded-md border border-border-strong bg-surface px-3 text-[13px] outline-none transition focus:border-link focus:ring-2 focus:ring-tint-navy"
          >
            <option value="all">Status: All</option>
            <option value="ACTIVE">Active</option>
            <option value="INACTIVE">Locked</option>
          </select>
          <select
            value={startFilter}
            onChange={(event) => {
              setStartFilter(event.target.value);
              setPage(1);
            }}
            className="h-9 cursor-pointer rounded-md border border-border-strong bg-surface px-3 text-[13px] outline-none transition focus:border-link focus:ring-2 focus:ring-tint-navy"
          >
            <option value="all">Start date: All</option>
            <option value="UPCOMING">Upcoming</option>
            <option value="STARTED">Started</option>
          </select>
          <select
            value={passwordFilter}
            onChange={(event) => {
              setPasswordFilter(event.target.value);
              setPage(1);
            }}
            className="h-9 cursor-pointer rounded-md border border-border-strong bg-surface px-3 text-[13px] outline-none transition focus:border-link focus:ring-2 focus:ring-tint-navy"
          >
            <option value="all">Mật khẩu: Tất cả</option>
            <option value="PENDING">Chưa tự đổi</option>
            <option value="SET">Đã tự đặt</option>
          </select>
        </div>
        <p className="px-2 text-[13px] font-medium text-text-subtle">
          {meta ? `Showing ${meta.total} results` : "…"}
        </p>
      </div>

      {/* Master + detail */}
      <div
        className={`grid gap-4 ${drawerOpen ? "xl:grid-cols-[minmax(0,1fr)_340px]" : "grid-cols-1"}`}
      >
        {/* Table */}
        <div className="flex min-w-0 flex-col overflow-hidden rounded-md border border-border bg-surface">
          {loading && (
            <div className="space-y-2 p-3">
              {Array.from({ length: 6 }, (_, index) => (
                <div
                  key={index}
                  className="h-12 animate-[project-skeleton_1.5s_ease-in-out_infinite] rounded bg-skeleton-soft"
                />
              ))}
            </div>
          )}

          {!loading && error && (
            <div role="alert" className="p-8 text-center">
              <p className="text-[15px] font-bold text-danger">
                {errorStatus === 401 || errorStatus === 403
                  ? "This session does not have Admin rights"
                  : "Data could not be loaded"}
              </p>
              <p className="mt-1 text-[13px] text-text-subtle">{error}</p>
              <button
                type="button"
                onClick={loadList}
                className="mt-4 h-9 rounded-md bg-navy px-4 text-[13px] font-semibold text-white"
              >
                Try again
              </button>
            </div>
          )}

          {!loading && !error && rows.length === 0 && (
            <p className="px-6 py-16 text-center text-[13px] text-text-subtle">
              No users match the current filters.
            </p>
          )}

          {!loading && !error && rows.length > 0 && (
            <div className="min-w-0 flex-1 overflow-x-auto">
              <table className="w-full min-w-[680px] border-collapse text-left">
                <thead>
                  <tr>
                    {[
                      "Người dùng",
                      "Quyền hệ thống",
                      "Trạng thái",
                      "Số dự án",
                      "Ngày vào làm",
                      "Ngày tạo",
                      "Tạo bởi",
                    ].map((header) => (
                      <th
                        key={header}
                        className="text-[11px] font-semibold tracking-[.06em] uppercase text-text-subtle"
                      >
                        {header}
                      </th>
                    ))}
                    <th className="w-10" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-divider">
                  {rows.map((user) => {
                    const selected = user.user_id === selectedId;
                    return (
                      <tr
                        key={user.user_id}
                        tabIndex={0}
                        aria-label={`View details for ${user.display_name}`}
                        onClick={() => selectUser(selected ? null : user.user_id)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            selectUser(selected ? null : user.user_id);
                          }
                        }}
                        aria-selected={selected}
                        className={`group cursor-pointer transition-colors ${
                          selected ? "row-selected" : ""
                        }`}
                      >
                        <td
                          className={`border-l-2 ${selected ? "border-l-link" : "border-l-transparent"}`}
                        >
                          <div className="flex items-center gap-3">
                            <Avatar name={user.display_name} />
                            <div className="min-w-0">
                              <p className="truncate font-semibold text-navy">
                                {user.display_name}
                              </p>
                              <p className="truncate text-[12px] text-text-subtle">{user.email}</p>
                            </div>
                          </div>
                        </td>
                        <td>
                          <RoleChip role={user.system_role} />
                        </td>
                        <td>
                          <div className="flex flex-wrap items-center gap-1.5">
                            <StatusDot active={user.status === "ACTIVE"} />
                            {/* Tài khoản còn dùng mật khẩu do admin đặt: admin biết mật
                                khẩu của họ, nên đây là nhóm cần theo dõi. */}
                            {user.must_change_password && (
                              <span
                                title="Mật khẩu hiện tại do quản trị viên đặt, người dùng chưa tự đổi"
                                className="rounded-full bg-warn-bg px-2 py-0.5 text-[11px] font-bold text-warn-text"
                              >
                                Chưa đổi MK
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="font-semibold text-navy tabular-nums">
                          {user.project_count}
                        </td>
                        <td className="text-text-subtle">
                          {user.start_date ? (
                            <span className="inline-flex items-center gap-2">
                              {formatDate(user.start_date)}
                              {/* Chip chỉ hiện với ngày tương lai: đó là thông tin admin
                                  cần hành động (chuẩn bị quyền, gán dự án trước ngày đầu). */}
                              {user.start_date > new Date().toISOString().slice(0, 10) && (
                                <span className="rounded-full bg-[#fdf3e6] px-2 py-0.5 text-[11px] font-bold text-[#b3721b]">
                                  Upcoming
                                </span>
                              )}
                            </span>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className="text-text-subtle">{formatDate(user.created_at)}</td>
                        <td className="text-text-subtle">{user.created_by_name ?? "System"}</td>
                        <td className="text-right">
                          <span
                            className={`inline-flex text-text-faint transition-opacity ${
                              selected
                                ? "text-link opacity-100"
                                : "opacity-0 group-hover:opacity-100"
                            }`}
                          >
                            <ChevronRightIcon />
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {!loading && !error && meta && meta.total > 0 && (
            <footer className="console-table-footer flex items-center justify-between gap-3 px-4 py-3">
              <p className="text-[12px] text-text-subtle">
                Page {page} of {totalPages}
                <span className="mx-2 text-border-strong">·</span>
                {rows.length} of {meta.total} accounts
              </p>
              <div className="flex gap-1">
                <button
                  type="button"
                  aria-label="Previous page"
                  disabled={page === 1}
                  onClick={() => setPage((current) => current - 1)}
                  className="pager-console flex h-8 w-8 items-center justify-center px-0"
                >
                  <ChevronLeftIcon />
                </button>
                <button
                  type="button"
                  aria-label="Next page"
                  disabled={page >= totalPages}
                  onClick={() => setPage((current) => current + 1)}
                  className="pager-console flex h-8 w-8 items-center justify-center px-0"
                >
                  <ChevronRightIcon />
                </button>
              </div>
            </footer>
          )}
        </div>

        {/* Detail drawer: docked beside the table on wide screens, overlay below xl. */}
        {drawerOpen && (
          <>
            <div
              role="presentation"
              onClick={() => selectUser(null)}
              className="fixed inset-0 z-40 bg-[#0b1c30]/25 xl:hidden"
            />
            <div className="fixed inset-y-0 right-0 z-40 w-full max-w-[360px] xl:static xl:z-auto xl:max-w-none">
              <div className="h-full xl:sticky xl:top-4 xl:h-[calc(100vh-9rem)] xl:overflow-hidden xl:rounded-md xl:border xl:border-border">
                <UserDetailDrawer
                  detail={detail}
                  loading={detailLoading}
                  onClose={() => selectUser(null)}
                  onRetry={() => selectedId !== null && loadDetail(selectedId)}
                  onToggleStatus={toggleStatus}
                  toggling={toggling}
                  onChangeStartDate={changeStartDate}
                  savingStartDate={savingStartDate}
                  error={detailError}
                  onSaveProfile={saveProfile}
                  savingProfile={savingProfile}
                  onResetPassword={() => setResetting(detail?.user_id ?? null)}
                />
              </div>
            </div>
          </>
        )}
      </div>
      {resetting !== null && detail && (
        <ResetPasswordDialog
          userId={resetting}
          displayName={detail.display_name}
          onClose={() => setResetting(null)}
          onDone={() => {
            void Promise.all([loadDetail(resetting), loadList()]);
          }}
        />
      )}
      {deactivating !== null && (
        <DeactivateUserDialog
          userId={deactivating}
          onClose={() => setDeactivating(null)}
          onConfirmed={() => {
            void Promise.all([loadDetail(deactivating), loadList()]);
          }}
        />
      )}
    </div>
  );
}
