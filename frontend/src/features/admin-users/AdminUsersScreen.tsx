"use client";

import { Link } from "@/i18n/navigation";
import { useEffect, useMemo, useState } from "react";

import { MOCK_ADMIN_USERS } from "./mockUsers";
import type { AdminUser, SystemRole, UserStatus } from "./types";

const PAGE_SIZE = 6;

type LoadState = "loading" | "ready" | "error";
type SortKey = "displayName" | "createdAt";
type SortDirection = "asc" | "desc";

function Icon({ name, className = "h-[17px] w-[17px]" }: { name: string; className?: string }) {
  const common = {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.9,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
  const paths: Record<string, React.ReactNode> = {
    chart: (
      <>
        <path d="M5 18v-4" />
        <path d="M12 18V9" />
        <path d="M19 18V5" />
      </>
    ),
    grid: (
      <>
        <rect x="4" y="4" width="6" height="6" rx="1" />
        <rect x="14" y="4" width="6" height="6" rx="1" />
        <rect x="4" y="14" width="6" height="6" rx="1" />
        <rect x="14" y="14" width="6" height="6" rx="1" />
      </>
    ),
    users: (
      <>
        <circle cx="9" cy="8" r="3.2" />
        <path d="M3 20a6 6 0 0 1 12 0" />
        <path d="M16 5.5a3 3 0 0 1 0 5.6" />
        <path d="M18 20a5.6 5.6 0 0 0-2-4" />
      </>
    ),
    folder: (
      <>
        <path d="M3.5 7.5h6l1.7 2H20a1 1 0 0 1 1 1v7.8a1.7 1.7 0 0 1-1.7 1.7H4.7A1.7 1.7 0 0 1 3 18.3V9.2a1.7 1.7 0 0 1 .5-1.2Z" />
      </>
    ),
    layers: (
      <>
        <path d="m12 3 8 4.5-8 4.5-8-4.5L12 3Z" />
        <path d="m4 12 8 4.5 8-4.5" />
        <path d="m4 16.5 8 4.5 8-4.5" />
      </>
    ),
    search: (
      <>
        <circle cx="11" cy="11" r="6.5" />
        <path d="m20 20-3.7-3.7" />
      </>
    ),
    plus: (
      <>
        <path d="M12 5v14" />
        <path d="M5 12h14" />
      </>
    ),
    chevron: <path d="m9 18 6-6-6-6" />,
    more: (
      <>
        <circle cx="5" cy="12" r=".8" fill="currentColor" />
        <circle cx="12" cy="12" r=".8" fill="currentColor" />
        <circle cx="19" cy="12" r=".8" fill="currentColor" />
      </>
    ),
  };

  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true" {...common}>
      {paths[name]}
    </svg>
  );
}

function initials(name: string) {
  const names = name.trim().split(/\s+/);
  return `${names.at(-2)?.[0] ?? names[0][0]}${names.at(-1)?.[0] ?? ""}`.toUpperCase();
}

function systemRoleLabel(role: SystemRole) {
  if (role === "ADMIN") return "Quản trị viên";
  if (role === "HR") return "Nhân sự";
  return "Không có quyền hệ thống";
}

function statusLabel(status: UserStatus) {
  return status === "ACTIVE" ? "Đang hoạt động" : "Đã khóa";
}

function UserRow({ user }: { user: AdminUser }) {
  return (
    <tr className="border-b border-divider last:border-b-0 hover:bg-[#f7f8fa]">
      <td className="min-w-[250px] px-4 py-3.5">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[#d5d9e2] bg-[#e4e7ee] text-xs font-semibold text-[#3d4759]">
            {initials(user.displayName)}
          </span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium text-text">{user.displayName}</span>
            <span className="block truncate text-[13px] text-text-subtle">{user.email}</span>
          </span>
        </div>
      </td>
      <td className="min-w-[160px] px-4 py-3.5 text-sm text-text-secondary">
        {systemRoleLabel(user.systemRole)}
      </td>
      <td className="min-w-[135px] px-4 py-3.5">
        <span
          className={`inline-flex items-center gap-1.5 rounded border px-2 py-1 text-[13px] ${user.status === "ACTIVE" ? "border-success-border bg-success-bg text-success-text" : "border-border bg-canvas text-text-muted"}`}
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${user.status === "ACTIVE" ? "bg-success" : "bg-text-faint"}`}
          />
          {statusLabel(user.status)}
        </span>
      </td>
      <td className="min-w-[90px] px-4 py-3.5">
        <button
          type="button"
          className="text-sm font-medium text-link hover:underline"
          aria-label={`Xem ${user.projectCount} dự án của ${user.displayName}`}
        >
          {user.projectCount} dự án
        </button>
      </td>
      <td className="min-w-[135px] px-4 py-3.5 text-sm text-text-secondary">
        {user.createdAtLabel}
      </td>
      <td className="min-w-[140px] px-4 py-3.5 text-sm text-text-secondary">{user.createdBy}</td>
      <td className="px-4 py-3.5 text-right">
        <button
          type="button"
          aria-label={`Mở chi tiết ${user.displayName}`}
          className="inline-flex h-8 w-8 items-center justify-center rounded text-text-muted hover:bg-canvas hover:text-text focus-visible:outline-2 focus-visible:outline-link"
        >
          <Icon name="more" />
        </button>
      </td>
    </tr>
  );
}

function TableSkeleton() {
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      <div className="h-12 border-b border-divider bg-[#fafbfc]" />
      {Array.from({ length: 6 }, (_, index) => (
        <div
          key={index}
          className="flex items-center gap-4 border-b border-divider px-4 py-3.5 last:border-b-0"
        >
          <span className="h-8 w-8 animate-[project-skeleton_1.5s_ease-in-out_infinite] rounded-full bg-skeleton" />
          <span className="h-8 flex-1 animate-[project-skeleton_1.5s_ease-in-out_infinite] rounded bg-skeleton-soft" />
          <span className="h-6 w-32 animate-[project-skeleton_1.5s_ease-in-out_infinite] rounded bg-skeleton-soft" />
          <span className="h-6 w-24 animate-[project-skeleton_1.5s_ease-in-out_infinite] rounded bg-skeleton-soft" />
        </div>
      ))}
    </div>
  );
}

export function AdminUsersScreen() {
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [query, setQuery] = useState("");
  const [role, setRole] = useState<"all" | Exclude<SystemRole, null> | "none">("all");
  const [status, setStatus] = useState<"all" | UserStatus>("all");
  const [sortKey, setSortKey] = useState<SortKey>("createdAt");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [page, setPage] = useState(1);

  const loadMockData = () => {
    setLoadState("loading");
    window.setTimeout(() => setLoadState("ready"), 350);
  };

  useEffect(() => {
    const timer = window.setTimeout(() => setLoadState("ready"), 350);
    return () => window.clearTimeout(timer);
  }, []);

  const filteredUsers = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return MOCK_ADMIN_USERS.filter((user) => {
      const matchesQuery =
        !normalized ||
        user.displayName.toLowerCase().includes(normalized) ||
        user.email.toLowerCase().includes(normalized);
      const matchesRole =
        role === "all" || (role === "none" ? user.systemRole === null : user.systemRole === role);
      const matchesStatus = status === "all" || user.status === status;
      return matchesQuery && matchesRole && matchesStatus;
    }).toSorted((first, second) => {
      const value =
        sortKey === "createdAt"
          ? first.createdAt.localeCompare(second.createdAt)
          : first.displayName.localeCompare(second.displayName, "vi");
      return sortDirection === "asc" ? value : -value;
    });
  }, [query, role, status, sortKey, sortDirection]);

  const totalPages = Math.max(1, Math.ceil(filteredUsers.length / PAGE_SIZE));
  const activePage = Math.min(page, totalPages);
  const currentUsers = filteredUsers.slice((activePage - 1) * PAGE_SIZE, activePage * PAGE_SIZE);
  const showingStart = filteredUsers.length ? (activePage - 1) * PAGE_SIZE + 1 : 0;
  const showingEnd = Math.min(activePage * PAGE_SIZE, filteredUsers.length);
  const hasFilters = query.length > 0 || role !== "all" || status !== "all";

  const updateSort = (nextKey: SortKey) => {
    if (sortKey === nextKey) setSortDirection((value) => (value === "asc" ? "desc" : "asc"));
    else {
      setSortKey(nextKey);
      setSortDirection("asc");
    }
    setPage(1);
  };

  const clearFilters = () => {
    setQuery("");
    setRole("all");
    setStatus("all");
    setPage(1);
  };

  return (
    <main className="min-h-screen bg-canvas text-text">
      <div className="flex min-h-screen">
        <aside className="hidden w-[232px] shrink-0 flex-col border-r border-header-border bg-surface py-4 md:flex">
          <div className="mb-2 flex items-center gap-2.5 border-b border-divider px-4 pb-4">
            <span className="flex h-[26px] w-[26px] items-center justify-center rounded-md bg-navy text-white">
              <Icon name="chart" className="h-[15px] w-[15px]" />
            </span>
            <span className="text-[15px] font-semibold">Ralion</span>
          </div>
          <nav aria-label="Điều hướng quản trị" className="flex flex-col gap-1 px-2">
            <Link
              href="/admin"
              className="flex h-[38px] items-center gap-3 rounded-md px-2.5 text-sm text-text-muted hover:bg-canvas"
            >
              <Icon name="grid" />
              Tổng quan
            </Link>
            <Link
              href="/admin/users"
              aria-current="page"
              className="flex h-[38px] items-center gap-3 rounded-md bg-tint-navy px-2.5 text-sm font-semibold text-navy"
            >
              <Icon name="users" />
              Người dùng
            </Link>
            <span className="flex h-[38px] items-center gap-3 rounded-md px-2.5 text-sm text-text-muted">
              <Icon name="folder" />
              Dự án
            </span>
            <span className="flex h-[38px] items-center gap-3 rounded-md px-2.5 text-sm text-text-muted">
              <Icon name="layers" />
              Membership dự án
            </span>
          </nav>
        </aside>
        <section className="min-w-0 flex-1">
          <header className="flex h-14 items-center justify-between border-b border-header-border bg-surface px-5 md:px-6">
            <span className="text-sm font-semibold">Admin Portal</span>
            <div className="flex items-center gap-3">
              <button
                type="button"
                aria-label="Tìm kiếm"
                className="inline-flex h-9 w-9 items-center justify-center rounded-md text-text-muted hover:bg-canvas"
              >
                <Icon name="search" />
              </button>
              <span className="h-5 w-px bg-header-border" />
              <div className="flex items-center gap-2">
                <span className="flex h-[30px] w-[30px] items-center justify-center rounded-full border border-[#d5d9e2] bg-[#e4e7ee] text-xs font-semibold text-[#3d4759]">
                  BN
                </span>
                <span className="hidden leading-tight sm:block">
                  <span className="block text-sm font-medium">Bao Nguyen</span>
                  <span className="block text-[13px] text-text-subtle">Administrator</span>
                </span>
              </div>
            </div>
          </header>
          <div className="mx-auto max-w-[1280px] px-5 pt-5 pb-8 md:px-6">
            <nav aria-label="Breadcrumb" className="mb-2 text-[13.5px] text-text-subtle">
              Admin Portal <span className="px-1.5 text-[#b6bcc7]">/</span>
              <span className="text-text">Người dùng</span>
            </nav>
            <div className="mb-[18px] flex flex-wrap items-end justify-between gap-4">
              <div>
                <h1 className="text-[22px] font-semibold tracking-[-0.01em]">Người dùng</h1>
                <p className="mt-1 text-sm text-text-subtle">
                  Tài khoản do quản trị viên tạo. Vai trò PM/Kỹ sư thuộc về từng dự án, không đặt ở
                  đây.
                </p>
              </div>
              <button
                type="button"
                className="inline-flex h-10 items-center gap-2 rounded-md border border-navy bg-navy px-3.5 text-sm font-semibold text-white hover:bg-navy-hover"
              >
                <Icon name="plus" className="h-4 w-4" />
                Tạo người dùng
              </button>
            </div>
            <div className="mb-4 flex flex-wrap items-center gap-3">
              <label className="relative min-w-[240px] flex-1">
                <span className="sr-only">Tìm theo tên hoặc email</span>
                <Icon
                  name="search"
                  className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-text-faint"
                />
                <input
                  value={query}
                  onChange={(event) => {
                    setQuery(event.target.value);
                    setPage(1);
                  }}
                  type="search"
                  placeholder="Tìm theo tên hoặc email"
                  className="h-10 w-full rounded-md border border-border-strong bg-surface pr-3 pl-9 text-sm placeholder:text-text-faint focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-link"
                />
              </label>
              <select
                value={role}
                onChange={(event) => {
                  setRole(event.target.value as typeof role);
                  setPage(1);
                }}
                aria-label="Lọc quyền hệ thống"
                className="h-10 rounded-md border border-border-strong bg-surface px-3 text-sm text-text-secondary focus-visible:outline-2 focus-visible:outline-link"
              >
                <option value="all">Tất cả quyền hệ thống</option>
                <option value="ADMIN">Quản trị viên</option>
                <option value="HR">Nhân sự</option>
                <option value="none">Không có quyền hệ thống</option>
              </select>
              <select
                value={status}
                onChange={(event) => {
                  setStatus(event.target.value as typeof status);
                  setPage(1);
                }}
                aria-label="Lọc trạng thái tài khoản"
                className="h-10 rounded-md border border-border-strong bg-surface px-3 text-sm text-text-secondary focus-visible:outline-2 focus-visible:outline-link"
              >
                <option value="all">Tất cả trạng thái</option>
                <option value="ACTIVE">Đang hoạt động</option>
                <option value="INACTIVE">Đã khóa</option>
              </select>
              {hasFilters && (
                <button
                  type="button"
                  onClick={clearFilters}
                  className="h-10 rounded-md border border-border-strong bg-surface px-3.5 text-sm font-semibold text-navy hover:bg-canvas"
                >
                  Xóa bộ lọc
                </button>
              )}
            </div>
            {loadState === "loading" && <TableSkeleton />}
            {loadState === "error" && (
              <div role="alert" className="rounded-lg border border-danger-border bg-surface p-5">
                <p className="font-semibold text-danger">Không thể tải danh sách người dùng</p>
                <p className="mt-1 text-sm text-text-subtle">
                  Dữ liệu mock hiện không khả dụng. Vui lòng thử lại.
                </p>
                <button
                  type="button"
                  onClick={loadMockData}
                  className="mt-4 h-10 rounded-md border border-navy bg-navy px-4 text-sm font-semibold text-white"
                >
                  Thử lại
                </button>
              </div>
            )}
            {loadState === "ready" && currentUsers.length === 0 && (
              <div className="rounded-lg border border-border bg-surface px-6 py-12 text-center">
                <h2 className="text-base font-semibold">Không tìm thấy người dùng phù hợp</h2>
                <p className="mt-1 text-sm text-text-subtle">
                  Thử thay đổi từ khóa tìm kiếm hoặc bộ lọc.
                </p>
                <button
                  type="button"
                  onClick={clearFilters}
                  className="mt-4 h-10 rounded-md border border-border-strong bg-surface px-4 text-sm font-semibold text-navy hover:bg-canvas"
                >
                  Xóa bộ lọc
                </button>
              </div>
            )}
            {loadState === "ready" && currentUsers.length > 0 && (
              <>
                <div className="overflow-x-auto rounded-lg border border-border bg-surface">
                  <table className="w-full min-w-[1100px] border-collapse">
                    <thead className="bg-[#fafbfc] text-left">
                      <tr className="border-b border-divider">
                        {(
                          [
                            ["Người dùng", "displayName"],
                            ["Quyền hệ thống", null],
                            ["Trạng thái", null],
                            ["Dự án", null],
                            ["Ngày tạo", "createdAt"],
                            ["Tạo bởi", null],
                          ] as const
                        ).map(([label, key]) => (
                          <th
                            key={label}
                            aria-sort={
                              key
                                ? sortKey === key
                                  ? sortDirection === "asc"
                                    ? "ascending"
                                    : "descending"
                                  : "none"
                                : undefined
                            }
                            className="px-4 py-3 text-[12px] font-semibold uppercase tracking-[0.05em] text-text-subtle"
                          >
                            {key ? (
                              <button
                                type="button"
                                onClick={() => updateSort(key)}
                                className="inline-flex items-center gap-1 hover:text-text"
                              >
                                {label}
                                <span aria-hidden="true">
                                  {sortKey === key && sortDirection === "asc" ? "↑" : "↓"}
                                </span>
                              </button>
                            ) : (
                              label
                            )}
                          </th>
                        ))}
                        <th className="w-14 px-4 py-3">
                          <span className="sr-only">Chi tiết</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {currentUsers.map((user) => (
                        <UserRow key={user.id} user={user} />
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                  <span role="status" aria-live="polite" className="text-[13.5px] text-text-subtle">
                    Hiển thị {showingStart}–{showingEnd} trong tổng số {filteredUsers.length} người
                    dùng
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      disabled={activePage === 1}
                      onClick={() => setPage((value) => value - 1)}
                      className="h-9 rounded-md border border-border-strong bg-surface px-3 text-sm font-medium text-navy disabled:cursor-not-allowed disabled:border-disabled-border disabled:bg-disabled-bg disabled:text-disabled-text"
                    >
                      Trước
                    </button>
                    <span className="text-sm text-text-muted">
                      Trang {activePage} / {totalPages}
                    </span>
                    <button
                      type="button"
                      disabled={activePage === totalPages}
                      onClick={() => setPage((value) => value + 1)}
                      className="h-9 rounded-md border border-border-strong bg-surface px-3 text-sm font-medium text-navy disabled:cursor-not-allowed disabled:border-disabled-border disabled:bg-disabled-bg disabled:text-disabled-text"
                    >
                      Sau
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
