"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  InfoIcon,
  SearchIcon,
  StarIcon,
  XIcon as CloseIcon,
} from "@primer/octicons-react";

import { ConsoleApiError, consoleApi } from "./api";
import { ConsoleAvatar } from "./ConsoleAvatar";
import { SuspendMembershipDialog } from "./SuspendMembershipDialog";
import type {
  AccessState,
  ConsoleMembership,
  MembershipBulkResult,
  MembershipEligibility,
  MembershipSummary,
  PageMeta,
} from "./types";

const PAGE_SIZE = 8;
const SEARCH_DEBOUNCE_MS = 300;

/* ----------------------------------------------------------------- helpers */

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}

/**
 * Every access state carries its own colour, label and remedy. The remedy matters:
 * a blocked membership is fixed on the user or project screen, not by toggling here.
 */
const ACCESS_META: Record<
  AccessState,
  { label: string; hint: string; chip: string; stripe: string; row: string }
> = {
  ACTIVE: {
    label: "Workspace open",
    hint: "The member can open the project workspace.",
    chip: "border-success-border bg-success-bg text-success-text",
    stripe: "bg-success",
    row: "",
  },
  SUSPENDED: {
    label: "Suspended",
    hint: "The membership is suspended. Reactivate it to restore access.",
    chip: "border-state-suspended-border bg-state-suspended-bg text-state-suspended-text",
    stripe: "bg-warn",
    row: "state-suspended",
  },
  BLOCKED_USER: {
    label: "Account locked",
    hint: "The membership is valid but the account cannot sign in. Unlock it on the Users tab.",
    chip: "border-state-blocked-border bg-state-blocked-bg text-state-blocked-text",
    stripe: "bg-danger",
    row: "state-blocked",
  },
  BLOCKED_PROJECT: {
    label: "Project archived",
    hint: "The project is archived, so its workspace is closed to everyone. Restore it on the Projects tab.",
    chip: "border-state-blocked-border bg-state-blocked-bg text-state-blocked-text",
    stripe: "bg-danger",
    row: "state-blocked",
  },
};

function AccessChip({ state }: { state: AccessState }) {
  const meta = ACCESS_META[state];
  return (
    <span
      title={meta.hint}
      className={`inline-flex items-center rounded border px-2 py-1 text-[11px] font-medium ${meta.chip}`}
    >
      {meta.label}
    </span>
  );
}

function RoleChip({ role, primary }: { role: "PM" | "ENGINEER"; primary?: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-2 py-1 text-[11px] font-medium ${
        role === "PM"
          ? "border-role-pm-border bg-role-pm-bg text-role-pm-text"
          : "border-role-eng-border bg-role-eng-bg text-role-eng-text"
      }`}
    >
      {primary && <StarIcon />}
      {role === "PM" ? (primary ? "Primary PM" : "PM") : "Engineer"}
    </span>
  );
}

function SystemRoleTag({ role }: { role: "ADMIN" | "HR" | null }) {
  if (role === null) {
    return <span className="text-[12px] text-text-subtle">No system role</span>;
  }
  return (
    <span
      className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[11px] font-medium ${
        role === "ADMIN"
          ? "border-role-admin-border bg-role-admin-bg text-role-admin-text"
          : "border-role-hr-border bg-role-hr-bg text-role-hr-text"
      }`}
    >
      {role}
    </span>
  );
}

/** Dùng chung với các tab khác, xem ConsoleAvatar.tsx. */
function Avatar({ name, muted }: { name: string; muted?: boolean }) {
  return <ConsoleAvatar name={name} size={34} muted={muted} />;
}

/* ----------------------------------------------------------- summary strip */

function SummaryStrip({
  summary,
  active,
  onPick,
}: {
  summary: MembershipSummary | null;
  active: string;
  onPick: (value: string) => void;
}) {
  const cards = [
    {
      value: "all",
      label: "All memberships",
      count: summary?.total,
      accent: "text-navy",
      dot: "bg-link",
    },
    {
      value: "ACTIVE",
      label: "Workspace open",
      count: summary?.active,
      accent: "text-success-text",
      dot: "bg-success",
    },
    {
      value: "SUSPENDED",
      label: "Suspended",
      count: summary?.suspended,
      accent: "text-state-suspended-text",
      dot: "bg-warn",
    },
    {
      value: "blocked",
      label: "Blocked",
      count: summary?.blocked,
      accent: "text-state-blocked-text",
      dot: "bg-danger",
    },
  ];
  return (
    <div className="mb-4 flex flex-wrap gap-1" role="group" aria-label="Filter by access state">
      {cards.map((card) => (
        <button
          key={card.value}
          type="button"
          onClick={() => onPick(card.value)}
          aria-pressed={active === card.value}
          className={`inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-[13px] transition ${
            active === card.value
              ? "border-link bg-tint-navy font-semibold text-link"
              : "border-border bg-surface text-text-secondary hover:border-border-hover"
          }`}
        >
          <span className={`h-1.5 w-1.5 rounded-full ${card.dot}`} />
          {card.label}
          <span className="tabular-nums text-text-subtle">{card.count ?? "—"}</span>
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------ assign drawer */

function AssignDrawer({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [eligibility, setEligibility] = useState<MembershipEligibility | null>(null);
  const [projectId, setProjectId] = useState("");
  const [projectRole, setProjectRole] = useState<"PM" | "ENGINEER">("ENGINEER");
  const [search, setSearch] = useState("");
  const [picked, setPicked] = useState<number[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MembershipBulkResult | null>(null);

  // Re-fetched per project so people already on it disappear from the picker.
  useEffect(() => {
    void consoleApi
      .membershipEligibility(projectId ? Number(projectId) : undefined)
      .then(setEligibility)
      .catch(() => setEligibility({ users: [], projects: [] }));
  }, [projectId]);

  const changeProject = (nextProjectId: string) => {
    setProjectId(nextProjectId);
    // Selections belong to the previous project's candidate list.
    setPicked([]);
    setResult(null);
  };

  const candidates = useMemo(() => {
    const needle = search.trim().toLowerCase();
    const users = eligibility?.users ?? [];
    if (!needle) return users;
    return users.filter(
      (user) =>
        user.display_name.toLowerCase().includes(needle) ||
        user.email.toLowerCase().includes(needle),
    );
  }, [eligibility, search]);

  const toggle = (userId: number) =>
    setPicked((current) =>
      current.includes(userId) ? current.filter((id) => id !== userId) : [...current, userId],
    );

  const submit = async () => {
    if (!projectId || picked.length === 0) return;
    setSaving(true);
    setError(null);
    try {
      const response = await consoleApi.createMembershipsBulk({
        project_id: Number(projectId),
        project_role: projectRole,
        user_ids: picked,
      });
      onSaved();
      if (response.skipped.length > 0) {
        // Keep the drawer open so the admin sees exactly who was not assigned and why.
        setResult(response);
        setPicked([]);
      } else {
        onClose();
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The membership could not be created.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-[#0b1c30]/30">
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Assign a member to a project"
        className="flex h-full w-full max-w-[440px] flex-col border-l border-border bg-surface"
      >
        <header className="flex items-center justify-between gap-3 border-b border-divider bg-canvas px-5 py-4">
          <div>
            <p className="text-[11px] font-semibold tracking-[.06em] uppercase text-text-subtle">
              Assign member
            </p>
            <h2 className="mt-1 text-[18px] font-bold text-navy">Project memberships</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-full p-1.5 text-text-subtle transition hover:bg-surface hover:text-navy"
          >
            <CloseIcon />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-5">
          <div className="flex gap-2.5 rounded-md border border-tint-navy-border bg-tint-navy p-3">
            <span className="mt-0.5 shrink-0 text-link">
              <InfoIcon />
            </span>
            <ul className="space-y-1 text-[12px] leading-5 text-link">
              <li>Accounts with an ADMIN/HR role cannot take a project membership.</li>
              <li>Locked accounts and archived projects are not eligible.</li>
              <li>One person holds at most one membership per project.</li>
            </ul>
          </div>

          <label className="mt-5 block text-[13px] font-semibold text-text-secondary">
            Projects
            <select
              value={projectId}
              onChange={(event) => changeProject(event.target.value)}
              className="mt-1.5 h-10 w-full rounded-md border border-border-strong bg-surface px-3 text-[13px] font-normal outline-none focus:border-link"
            >
              <option value="" disabled>
                {eligibility ? "-- Select a project --" : "Loading projects…"}
              </option>
              {eligibility?.projects.map((project) => (
                <option key={project.project_id} value={project.project_id}>
                  {project.name} ({project.key})
                </option>
              ))}
            </select>
          </label>

          <fieldset className="mt-4">
            <legend className="text-[13px] font-semibold text-text-secondary">Project role</legend>
            <div className="mt-1.5 grid grid-cols-2 gap-2">
              {(["PM", "ENGINEER"] as const).map((role) => (
                <label
                  key={role}
                  className={`flex cursor-pointer items-center gap-2 rounded-md border p-2.5 transition ${
                    projectRole === role
                      ? role === "PM"
                        ? "border-role-pm-border bg-role-pm-bg"
                        : "border-role-eng-border bg-role-eng-bg"
                      : "border-border hover:bg-canvas"
                  }`}
                >
                  <input
                    type="radio"
                    name="project_role"
                    checked={projectRole === role}
                    onChange={() => setProjectRole(role)}
                    className="h-4 w-4 accent-[#081534]"
                  />
                  <span className="text-[13px] font-semibold text-navy">
                    {role === "PM" ? "Project Manager" : "Engineer"}
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          <div className="mt-5">
            <div className="flex items-center justify-between gap-2">
              <p className="text-[13px] font-semibold text-text-secondary">
                Eligible people <span className="text-text-subtle">({candidates.length})</span>
              </p>
              {picked.length > 0 && (
                <span className="rounded-full bg-tint-navy px-2 py-0.5 text-[11px] font-bold text-link">
                  {picked.length} selected
                </span>
              )}
            </div>
            <label className="relative mt-2 block">
              <span className="sr-only">Filter people</span>
              <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-text-faint">
                <SearchIcon />
              </span>
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Enter a name or email…"
                className="h-9 w-full rounded-md border border-border-strong bg-surface pr-3 pl-9 text-[13px] outline-none focus:border-link"
              />
            </label>

            <div className="mt-2 max-h-[280px] space-y-1.5 overflow-y-auto">
              {candidates.length === 0 ? (
                <p className="rounded-md border border-dashed border-border-strong p-4 text-center text-[12px] leading-5 text-text-subtle">
                  {projectId
                    ? "No eligible accounts are left for this project."
                    : "Pick a project to see who is eligible."}
                </p>
              ) : (
                candidates.map((user) => {
                  const checked = picked.includes(user.user_id);
                  return (
                    <label
                      key={user.user_id}
                      className={`flex cursor-pointer items-center gap-2.5 rounded-md border p-2.5 transition ${
                        checked ? "border-link bg-tint-navy" : "border-border hover:bg-canvas"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggle(user.user_id)}
                        className="h-4 w-4 shrink-0 accent-[#081534]"
                      />
                      <Avatar name={user.display_name} />
                      <span className="min-w-0">
                        <span className="block truncate text-[13px] font-semibold text-navy">
                          {user.display_name}
                        </span>
                        <span className="block truncate text-[12px] text-text-subtle">
                          {user.email}
                        </span>
                      </span>
                    </label>
                  );
                })
              )}
            </div>
          </div>

          {result && result.skipped.length > 0 && (
            <div className="mt-4 rounded-md border border-state-suspended-border bg-state-suspended-bg p-3">
              <p className="text-[13px] font-bold text-state-suspended-text">
                Created {result.created.length}, skipped {result.skipped.length}
              </p>
              <ul className="mt-2 space-y-1 text-[12px] leading-5 text-state-suspended-text">
                {result.skipped.map((item) => (
                  <li key={item.user_id}>
                    {item.display_name ?? `#${item.user_id}`} — {item.reason}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {error && (
            <p
              role="alert"
              className="mt-4 rounded-md border border-danger-border bg-danger-bg p-3 text-[13px] text-danger"
            >
              {error}
            </p>
          )}
        </div>

        <footer className="flex justify-end gap-2 border-t border-divider bg-canvas p-4">
          <button
            type="button"
            onClick={onClose}
            className="h-9 rounded-md border border-border-strong bg-surface px-4 text-[13px] font-semibold text-navy hover:bg-canvas"
          >
            Close
          </button>
          <button
            type="button"
            disabled={saving || !projectId || picked.length === 0}
            onClick={submit}
            className="h-9 rounded-md bg-navy px-4 text-[13px] font-semibold text-white transition hover:bg-navy-hover disabled:opacity-50"
          >
            {saving
              ? "Creating…"
              : picked.length > 1
                ? `Create ${picked.length} memberships`
                : "Create membership"}
          </button>
        </footer>
      </aside>
    </div>
  );
}

/* -------------------------------------------------------------- main panel */

export function MembershipsPanel({
  reloadToken,
  assignOpen,
  onCloseAssign,
}: {
  reloadToken: number;
  /** The shell header owns the "Gán thành viên" button; this panel just renders the drawer. */
  assignOpen: boolean;
  onCloseAssign: () => void;
}) {
  const [rawQuery, setRawQuery] = useState("");
  const [query, setQuery] = useState("");
  const [stateFilter, setStateFilter] = useState("all");
  const [roleFilter, setRoleFilter] = useState("all");
  const [page, setPage] = useState(1);

  const [rows, setRows] = useState<ConsoleMembership[]>([]);
  const [meta, setMeta] = useState<PageMeta | null>(null);
  const [summary, setSummary] = useState<MembershipSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  // membership_id đang chờ xác nhận tạm ngừng; null = không có hộp thoại nào mở.
  const [suspending, setSuspending] = useState<number | null>(null);
  // Dòng đang đổi vai trò. Giữ nguyên object để hộp thoại biết vai trò hiện tại và có
  // phải PM chính hay không.
  const [changingRole, setChangingRole] = useState<ConsoleMembership | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQuery(rawQuery);
      setPage(1);
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [rawQuery]);

  // Lọc sẵn theo dự án khi được điều hướng tới từ cảnh báo "Dự án chưa có PM" ở trang
  // tổng quan. Đọc một lần lúc mount: sau đó admin đổi bộ lọc thì URL không được kéo
  // ngược lại giá trị cũ.
  //
  // PHẢI có chip hiển thị và nút bỏ lọc (xem phần render): lọc ngầm khiến người dùng
  // thấy một danh sách ngắn bất thường mà không hiểu vì sao, và không có đường thoát
  // ngoài việc tự sửa URL.
  const [projectFilter, setProjectFilter] = useState(() =>
    typeof window === "undefined"
      ? null
      : new URLSearchParams(window.location.search).get("project_id"),
  );

  const params = useMemo(() => {
    const next = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    if (query.trim()) next.set("query", query.trim());
    if (roleFilter !== "all") next.set("project_role", roleFilter);
    if (projectFilter && /^\d+$/.test(projectFilter)) next.set("project_id", projectFilter);
    // "blocked" groups the two blocking causes, which the API exposes separately.
    if (stateFilter === "blocked") next.set("membership_status", "ACTIVE");
    else if (stateFilter !== "all") next.set("state", stateFilter);
    return next;
  }, [page, query, roleFilter, stateFilter, projectFilter]);

  const loadList = useCallback(() => {
    setLoading(true);
    setError(null);
    setErrorStatus(null);
    return consoleApi
      .memberships(params)
      .then((result) => {
        const items =
          stateFilter === "blocked"
            ? result.items.filter((item) => item.access_state.startsWith("BLOCKED"))
            : result.items;
        setRows(items);
        setMeta(result.meta);
      })
      .catch((caught) => {
        setRows([]);
        setMeta(null);
        setErrorStatus(caught instanceof ConsoleApiError ? caught.status : null);
        setError(caught instanceof Error ? caught.message : "Memberships could not be loaded.");
      })
      .finally(() => setLoading(false));
  }, [params, stateFilter]);

  const loadSummary = useCallback(
    () =>
      consoleApi
        .membershipSummary()
        .then(setSummary)
        .catch(() => setSummary(null)),
    [],
  );

  useEffect(() => {
    const timer = window.setTimeout(loadList, 0);
    return () => window.clearTimeout(timer);
  }, [loadList, reloadToken]);

  useEffect(() => {
    const timer = window.setTimeout(loadSummary, 0);
    return () => window.clearTimeout(timer);
  }, [loadSummary, reloadToken]);

  const refresh = useCallback(() => {
    void loadList();
    void loadSummary();
  }, [loadList, loadSummary]);

  const mutate = async (membershipId: number, body: Record<string, string>) => {
    setBusyId(membershipId);
    setActionError(null);
    try {
      await consoleApi.updateMembership(membershipId, body);
      refresh();
    } catch (caught) {
      setActionError(
        caught instanceof Error ? caught.message : "The membership could not be updated.",
      );
    } finally {
      setBusyId(null);
    }
  };

  const totalPages = meta ? Math.max(1, Math.ceil(meta.total / PAGE_SIZE)) : 1;

  return (
    <div className="console-memberships">
      <SummaryStrip
        summary={summary}
        active={stateFilter}
        onPick={(value) => {
          setStateFilter(value);
          setPage(1);
        }}
      />

      {/* Toolbar */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-surface p-2.5">
        <div className="flex flex-1 flex-wrap items-center gap-2">
          <label className="relative min-w-[220px] flex-1 sm:max-w-[300px]">
            <span className="sr-only">Search memberships</span>
            <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-text-faint">
              <SearchIcon />
            </span>
            <input
              value={rawQuery}
              onChange={(event) => setRawQuery(event.target.value)}
              placeholder="Search people or projects…"
              className="h-9 w-full rounded-md border border-border-strong bg-surface pr-3 pl-9 text-[13px] outline-none transition focus:border-link focus:ring-2 focus:ring-tint-navy"
            />
          </label>
          <select
            value={roleFilter}
            onChange={(event) => {
              setRoleFilter(event.target.value);
              setPage(1);
            }}
            className="h-9 cursor-pointer rounded-md border border-border-strong bg-surface px-3 text-[13px] outline-none transition focus:border-link"
          >
            <option value="all">Role: All</option>
            <option value="PM">Project Manager</option>
            <option value="ENGINEER">Engineer</option>
          </select>
        </div>
        <p className="px-2 text-[13px] font-medium text-text-subtle">
          {meta ? `Showing ${meta.total} results` : "…"}
        </p>
      </div>

      {/* Bộ lọc đến từ URL phải hiện ra và bỏ được. Không có chip này thì người bấm
          "Gán PM" từ trang tổng quan chỉ thấy một danh sách ngắn bất thường. */}
      {projectFilter && (
        <div className="mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-tint-navy-border bg-tint-navy px-4 py-2.5">
          <span className="text-[13px] text-link">
            Đang lọc theo dự án{" "}
            <b>{rows[0]?.project_name ?? `#${projectFilter}`}</b>
          </span>
          <button
            type="button"
            onClick={() => {
              setProjectFilter(null);
              setPage(1);
              // Dọn luôn tham số khỏi URL để tải lại trang không lọc lần nữa.
              window.history.replaceState(null, "", window.location.pathname);
            }}
            className="rounded-md border border-border-strong bg-surface px-2.5 py-1 text-[12px] font-semibold text-navy transition hover:bg-canvas"
          >
            Bỏ lọc
          </button>
        </div>
      )}

      {actionError && (
        <p
          role="alert"
          className="mb-4 rounded-md border border-danger-border bg-danger-bg px-4 py-3 text-[13px] text-danger"
        >
          {actionError}
        </p>
      )}

      {/* Table */}
      <div className="flex flex-col overflow-hidden rounded-md border border-border bg-surface">
        {loading && (
          <div className="space-y-2 p-3">
            {Array.from({ length: 6 }, (_, index) => (
              <div
                key={index}
                className="h-14 animate-[project-skeleton_1.5s_ease-in-out_infinite] rounded bg-skeleton-soft"
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
            No memberships match the current filters.
          </p>
        )}

        {!loading && !error && rows.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] border-collapse text-left">
              <thead>
                <tr>
                  {["Nhân sự", "Dự án", "Vai trò dự án", "Quyền hệ thống", "Trạng thái"].map(
                    (header) => (
                      <th
                        key={header}
                        className="text-[11px] font-bold tracking-[.07em] uppercase text-text-subtle"
                      >
                        {header}
                      </th>
                    ),
                  )}
                  <th className="text-right text-[11px] font-bold tracking-[.07em] uppercase text-text-subtle">
                    Thao tác
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-divider">
                {rows.map((row) => {
                  const meta = ACCESS_META[row.access_state];
                  const dimmed = row.access_state !== "ACTIVE";
                  return (
                    <tr key={row.membership_id} className={meta.row}>
                      <td className="relative">
                        <span
                          className={`absolute inset-y-0 left-0 w-[3px] ${meta.stripe}`}
                          aria-hidden="true"
                        />
                        <div className={`flex items-center gap-3 ${dimmed ? "opacity-75" : ""}`}>
                          <Avatar name={row.user_name} muted={dimmed} />
                          <div className="min-w-0">
                            <p className="truncate font-semibold text-navy">{row.user_name}</p>
                            <p className="truncate text-[12px] text-text-subtle">
                              {row.user_email}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className={dimmed ? "opacity-75" : ""}>
                        <p className="font-medium text-navy">{row.project_name}</p>
                        <p className="mt-0.5 font-mono text-[11px] text-text-subtle">
                          {row.project_key}
                          <span className="ml-2 font-sans">Joined {formatDate(row.joined_at)}</span>
                        </p>
                      </td>
                      <td>
                        <div className="flex flex-wrap items-center gap-1.5">
                          <RoleChip role={row.project_role} primary={row.is_primary_pm} />
                          {/* Đổi vai trò ngay tại đây. Trước đây phải sang tab Dự án,
                              tìm đúng dự án rồi mở drawer — vòng vèo không cần thiết ở
                              chính màn hình quản lý membership. */}
                          {row.access_state === "ACTIVE" && (
                            <button
                              type="button"
                              disabled={busyId === row.membership_id}
                              onClick={() => setChangingRole(row)}
                              className="rounded border border-border-strong px-1.5 py-0.5 text-[11px] font-semibold text-link transition hover:bg-tint-navy disabled:opacity-50"
                            >
                              Đổi
                            </button>
                          )}
                        </div>
                      </td>
                      <td>
                        <SystemRoleTag role={row.user_system_role} />
                      </td>
                      <td>
                        <AccessChip state={row.access_state} />
                      </td>
                      <td className="text-right">
                        {row.access_state === "SUSPENDED" ? (
                          <button
                            type="button"
                            disabled={busyId === row.membership_id}
                            onClick={() => mutate(row.membership_id, { status: "ACTIVE" })}
                            className="rounded-md border border-border-strong px-2.5 py-1.5 text-[12px] font-semibold text-link transition hover:bg-tint-navy disabled:opacity-50"
                          >
                            {busyId === row.membership_id ? "Saving…" : "Activate"}
                          </button>
                        ) : row.access_state === "ACTIVE" ? (
                          <button
                            type="button"
                            disabled={busyId === row.membership_id}
                            // Qua hộp thoại chứ không ngừng thẳng: đây là lúc access
                            // creep phát sinh, quyền đã cấp phải được nhắc lại.
                            onClick={() => setSuspending(row.membership_id)}
                            className="rounded-md border border-border-strong px-2.5 py-1.5 text-[12px] font-semibold text-text-muted transition hover:border-danger-border hover:bg-danger-bg hover:text-danger disabled:opacity-50"
                          >
                            {busyId === row.membership_id ? "Saving…" : "Suspend"}
                          </button>
                        ) : (
                          <span
                            title={meta.hint}
                            className="text-[12px] font-medium text-text-subtle"
                          >
                            {row.access_state === "BLOCKED_USER"
                              ? "Edit under Users"
                              : "Edit under Projects"}
                          </span>
                        )}
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
              {rows.length} of {meta.total} memberships
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

      {assignOpen && <AssignDrawer onClose={onCloseAssign} onSaved={refresh} />}

      {suspending !== null && (
        <SuspendMembershipDialog
          membershipId={suspending}
          onClose={() => setSuspending(null)}
          onConfirmed={refresh}
        />
      )}

      {changingRole && (
        <ChangeRoleDialog
          membership={changingRole}
          onClose={() => setChangingRole(null)}
          onConfirmed={refresh}
        />
      )}
    </div>
  );
}

/**
 * Đổi vai trò giữa PM và Kỹ sư.
 *
 * Là hộp thoại chứ không phải nút bấm thẳng vì hạ PM chính xuống Kỹ sư sẽ để trống vị
 * trí phụ trách dự án — hậu quả lan ra ngoài dòng đang thao tác, nên phải nói trước.
 */
function ChangeRoleDialog({
  membership,
  onClose,
  onConfirmed,
}: {
  membership: ConsoleMembership;
  onClose: () => void;
  onConfirmed: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nextRole = membership.project_role === "PM" ? "ENGINEER" : "PM";

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await consoleApi.updateMembership(membership.membership_id, { project_role: nextRole });
      onConfirmed();
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không đổi được vai trò.");
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-6">
      <section
        role="dialog"
        aria-modal="true"
        aria-label="Đổi vai trò dự án"
        className="w-full max-w-[440px] rounded-xl bg-surface p-6 shadow-2xl"
      >
        <h2 className="text-lg font-bold text-navy">
          Đổi thành {nextRole === "PM" ? "PM" : "Kỹ sư"}?
        </h2>
        <p className="mt-1 text-sm text-text-subtle">
          {membership.user_name} · {membership.project_name}
        </p>

        <div className="mt-5 rounded-lg border border-warn-border bg-warn-bg p-4 text-sm leading-6 text-warn-text">
          {nextRole === "PM" ? (
            <>
              Người này sẽ có quyền quản lý lộ trình onboarding của dự án. Nếu dự án chưa có PM
              phụ trách, họ sẽ tự động trở thành PM chính.
            </>
          ) : membership.is_primary_pm ? (
            <b>
              Đây là PM chính của dự án. Hạ xuống Kỹ sư sẽ để trống vị trí phụ trách, và dự án
              xuất hiện ở mục &ldquo;Cần xử lý&rdquo; cho tới khi bạn chỉ định người khác.
            </b>
          ) : (
            <>Người này sẽ mất quyền quản lý lộ trình onboarding của dự án.</>
          )}
        </div>

        {error && (
          <p
            role="alert"
            className="mt-4 rounded-md border border-danger-border bg-danger-bg p-3 text-sm text-danger"
          >
            {error}
          </p>
        )}

        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="h-10 rounded-md border border-border-strong px-4 text-sm font-semibold text-navy"
          >
            Huỷ
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => void confirm()}
            className="h-10 rounded-md bg-navy px-4 text-sm font-semibold text-white disabled:opacity-50"
          >
            {busy ? "Đang lưu…" : "Xác nhận"}
          </button>
        </div>
      </section>
    </div>
  );
}
