"use client";

import { Link, useRouter } from "@/i18n/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { useTranslations } from "next-intl";
import {
  BookIcon,
  FileDirectoryIcon as FolderIcon,
  PeopleIcon as UsersIcon,
  ProjectIcon as GridIcon,
  SearchIcon,
  SignOutIcon as LogoutIcon,
  StackIcon as LayersIcon,
} from "@primer/octicons-react";

import { AccountMenu } from "@/components/auth/AccountMenu";
import { BrandHomeLink } from "@/components/brand/BrandHomeLink";
import { RalionBrand } from "@/components/brand/RalionBrand";
import { LanguageSwitcher } from "@/components/i18n/LanguageSwitcher";
import { MobileNavDrawer } from "@/components/navigation/MobileNavDrawer";
import { useSession } from "@/features/auth/session";

import { ConsoleApiError, consoleApi, fetchSection } from "./api";
import { MasterTemplatePanel } from "./MasterTemplatePanel";
import { MembershipsPanel } from "./MembershipsPanel";
import { OverviewPanel } from "./OverviewPanel";
import { ProjectsPanel } from "./ProjectsPanel";
import { UsersPanel } from "./UsersPanel";
import type { ConsolePolicy, ConsoleSection, Overview, PageMeta } from "./types";

const PAGE_SIZE = 6;
const subscribeToHydration = () => () => undefined;
const getClientHydrationSnapshot = () => true;
const getServerHydrationSnapshot = () => false;

const SECTION_META: Record<ConsoleSection, { title: string; lead: string; action?: string }> = {
  overview: {
    title: "Tổng quan",
    lead: "Theo dõi nhanh tài khoản, dự án và membership trong hệ thống.",
  },
  users: {
    title: "Người dùng",
    lead: "Tài khoản do quản trị viên tạo. Vai trò PM/Kỹ sư thuộc về từng dự án, không đặt ở đây.",
    action: "Tạo người dùng",
  },
  projects: {
    title: "Dự án",
    lead: "Quản trị viên tạo dự án và chỉ định PM chính qua membership.",
    action: "Tạo dự án",
  },
  "master-template": {
    title: "Master Template",
    lead: "Checklist onboarding chuẩn áp dụng cho MỌI dự án — mỗi dự án mới tự có bản sao từ đây.",
  },
  memberships: {
    title: "Membership dự án",
    lead: "Mỗi người chỉ có một membership cho một dự án.",
    action: "Gán thành viên",
  },
  policies: {
    title: "Thư viện chính sách",
    lead: "Tài liệu phạm vi tổ chức dùng chung cho onboarding.",
  },
};

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

function Badge({ active, children }: { active: boolean; children: React.ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border px-2 py-1 text-[13px] ${active ? "border-success-border bg-success-bg text-success-text" : "border-border bg-canvas text-text-muted"}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${active ? "bg-success" : "bg-text-faint"}`} />
      {children}
    </span>
  );
}

function TableSkeleton() {
  return (
    <div className="overflow-hidden rounded-md border border-border bg-surface">
      {Array.from({ length: 7 }, (_, index) => (
        <div key={index} className="flex gap-4 border-b border-divider p-4">
          <span className="h-7 flex-1 animate-[project-skeleton_1.5s_ease-in-out_infinite] rounded bg-skeleton-soft" />
          <span className="h-7 w-32 animate-[project-skeleton_1.5s_ease-in-out_infinite] rounded bg-skeleton-soft" />
          <span className="h-7 w-24 animate-[project-skeleton_1.5s_ease-in-out_infinite] rounded bg-skeleton-soft" />
        </div>
      ))}
    </div>
  );
}

function Modal({
  section,
  onClose,
  onCreated,
}: {
  section: ConsoleSection;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [eligibility, setEligibility] = useState<Awaited<
    ReturnType<typeof consoleApi.membershipEligibility>
  > | null>(null);
  useEffect(() => {
    if (section === "memberships")
      void consoleApi
        .membershipEligibility()
        .then(setEligibility)
        .catch(() => setEligibility(null));
  }, [section]);
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    const form = new FormData(event.currentTarget);
    try {
      if (section === "users")
        await consoleApi.createUser({
          display_name: form.get("name"),
          email: form.get("email"),
          temporary_password: form.get("password"),
          system_role: form.get("role") || null,
          status: form.get("status"),
        });
      if (section === "projects")
        await consoleApi.createProject({ name: form.get("name"), key: form.get("key") });
      if (section === "memberships")
        await consoleApi.createMembership({
          user_id: Number(form.get("user_id")),
          project_id: Number(form.get("project_id")),
          project_role: form.get("project_role"),
          status: form.get("status"),
        });
      onCreated();
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Changes could not be saved.");
    } finally {
      setSaving(false);
    }
  };
  const fields =
    section === "users" ? (
      <>
        <label>
          Full name
          <input name="name" required />
        </label>
        <label>
          Company email
          <input name="email" type="email" required />
        </label>
        <label>
          Temporary password
          <input name="password" type="password" minLength={8} required />
        </label>
        <label>
          System role
          <select name="role" defaultValue="">
            <option value="">No system role</option>
            <option value="ADMIN">Administrator</option>
            <option value="HR">People</option>
          </select>
        </label>
        <label>
          Status
          <select name="status" defaultValue="ACTIVE">
            <option value="ACTIVE">Active</option>
            <option value="INACTIVE">Locked</option>
          </select>
        </label>
      </>
    ) : section === "projects" ? (
      <>
        <label>
          Project name
          <input name="name" required />
        </label>
        <label>
          Project key
          <input name="key" required pattern="[A-Za-z0-9_-]+" />
        </label>
      </>
    ) : (
      <>
        <label>
          Eligible members
          <select name="user_id" required defaultValue="">
            <option value="" disabled>
              {eligibility ? "Select a member" : "Loading members…"}
            </option>
            {eligibility?.users.map((user) => (
              <option key={user.user_id} value={user.user_id}>
                {user.display_name} — {user.email}
              </option>
            ))}
          </select>
        </label>
        <label>
          Active projects
          <select name="project_id" required defaultValue="">
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
        <label>
          Project role
          <select name="project_role" defaultValue="ENGINEER">
            <option value="ENGINEER">Engineer</option>
            <option value="PM">PM</option>
          </select>
        </label>
        <label>
          Status
          <select name="status" defaultValue="ACTIVE">
            <option value="ACTIVE">Active</option>
            <option value="INACTIVE">Inactive</option>
          </select>
        </label>
      </>
    );
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/25" role="presentation">
      <form
        onSubmit={submit}
        role="dialog"
        aria-modal="true"
        aria-label={SECTION_META[section].action}
        className="h-full w-full max-w-[440px] overflow-auto border-l border-border bg-surface p-6"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">{SECTION_META[section].action}</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded px-2 py-1 text-text-muted hover:bg-canvas"
          >
            Close
          </button>
        </div>
        <div className="mt-6 flex flex-col gap-4 [&_input]:mt-1 [&_input]:h-10 [&_input]:w-full [&_input]:rounded-md [&_input]:border [&_input]:border-border-strong [&_input]:px-3 [&_label]:text-sm [&_label]:font-medium [&_select]:mt-1 [&_select]:h-10 [&_select]:w-full [&_select]:rounded-md [&_select]:border [&_select]:border-border-strong [&_select]:px-3">
          {fields}
        </div>
        {section === "memberships" && (
          <p className="mt-4 rounded-md border border-warn-border bg-warn-bg p-3 text-xs leading-5 text-warn-text">
            Only ACTIVE accounts without a system role and ACTIVE projects are eligible. An inactive
            membership cannot open the project workspace.
          </p>
        )}
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
            Cancel
          </button>
          <button
            disabled={saving}
            className="h-10 rounded-md bg-navy px-4 text-sm font-semibold text-white disabled:opacity-60"
          >
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </form>
    </div>
  );
}

export function AdminConsoleScreen({ section }: { section: ConsoleSection }) {
  const t = useTranslations("admin");
  const common = useTranslations("common");
  const hydrated = useSyncExternalStore(
    subscribeToHydration,
    getClientHydrationSnapshot,
    getServerHydrationSnapshot,
  );
  const router = useRouter();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const closeMobileNav = useCallback(() => setMobileNavOpen(false), []);
  const { user: sessionUser, loading: sessionLoading, error: sessionError, signOut } = useSession();

  // Kiểm tra quyền ngay khi biết danh tính, thay vì để từng request API trả 403 lẻ tẻ.
  // Middleware chỉ chặn được người chưa có cookie; đây mới là chỗ chặn sai vai trò.
  const needsHrOrAdmin = section === "policies";
  useEffect(() => {
    if (sessionLoading) return;
    if (!sessionUser) {
      if (sessionError?.status === 401) router.replace("/login");
      return;
    }
    const allowed = needsHrOrAdmin
      ? sessionUser.system_role === "ADMIN" || sessionUser.system_role === "HR"
      : sessionUser.system_role === "ADMIN";
    if (!allowed) router.replace("/access-denied");
  }, [needsHrOrAdmin, router, sessionError, sessionLoading, sessionUser]);
  const [data, setData] = useState<Overview | { items: unknown[]; meta: PageMeta } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [filter] = useState("all");
  const [page, setPage] = useState(1);
  const [modal, setModal] = useState(false);
  // Bumped after a create so the self-managed Users/Projects/Memberships panels refetch.
  const [panelReloadToken, setPanelReloadToken] = useState(0);
  const params = useMemo(() => {
    const next = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    if (query) next.set("query", query);
    // The users tab has its own richer filter set inside UsersPanel.
    if (section === "projects" && filter !== "all")
      next.set("project_status", filter.toUpperCase());
    if (section === "memberships" && filter !== "all")
      next.set("membership_status", filter.toUpperCase());
    return next;
  }, [filter, page, query, section]);
  const load = useCallback(() => {
    // The users and projects tabs are self-managed: their panels own filters,
    // pagination and the detail drawer, so the shared shell must not fetch for them.
    if (
      section === "users" ||
      section === "projects" ||
      section === "memberships" ||
      section === "master-template"
    ) {
      setData(null);
      setLoading(false);
      setError(null);
      setErrorStatus(null);
      return;
    }
    setLoading(true);
    setError(null);
    setErrorStatus(null);
    fetchSection(section, params)
      .then(setData)
      .catch((caught) => {
        setErrorStatus(caught instanceof ConsoleApiError ? caught.status : null);
        setError(caught instanceof Error ? caught.message : "The console could not be loaded.");
      })
      .finally(() => setLoading(false));
  }, [params, section]);
  useEffect(() => {
    const timer = window.setTimeout(load, 0);
    return () => window.clearTimeout(timer);
  }, [load]);
  if (!hydrated) {
    return (
      <main className="ralion-console h-screen overflow-hidden bg-canvas text-text">
        <div className="flex h-full">
          <aside className="console-sidebar hidden w-[240px] border-r border-header-border bg-surface md:block" />
          <section className="flex-1 overflow-y-auto p-6">
            <TableSkeleton />
          </section>
        </div>
      </main>
    );
  }
  const paged = data && "items" in data ? data : null;
  const overview = data && "active_users" in data ? data : null;
  const rows = paged?.items ?? [];
  const meta = paged?.meta;
  const isHrPortal = section === "policies";
  const navigation = isHrPortal
    ? [{ href: "/hr", label: t("hrWorkspace"), icon: <FolderIcon />, active: true }]
    : [
        {
          href: "/admin",
          label: t("overview"),
          icon: <GridIcon />,
          active: section === "overview",
        },
        {
          href: "/admin/users",
          label: t("users"),
          icon: <UsersIcon />,
          active: section === "users",
        },
        {
          href: "/admin/projects",
          label: t("projects"),
          icon: <FolderIcon />,
          active: section === "projects",
        },
        {
          href: "/admin/master-template",
          label: t("masterTemplate"),
          icon: <BookIcon />,
          active: section === "master-template",
        },
        {
          href: "/admin/memberships",
          label: t("memberships"),
          icon: <LayersIcon />,
          active: section === "memberships",
        },
      ];
  return (
    <main className="ralion-console h-screen overflow-hidden bg-canvas text-text">
      <div className="flex h-full">
        <aside className="console-sidebar hidden shrink-0 flex-col py-0 md:flex">
          <BrandHomeLink className="mb-1 inline-flex px-4 pt-4 pb-3.5">
            <RalionBrand size={26} />
          </BrandHomeLink>
          <div className="px-[18px] pt-2.5 pb-1.5 text-[10.5px] font-semibold uppercase tracking-[.06em] text-text-faint">
            {isHrPortal ? "HR workspace" : "Admin workspace"}
          </div>
          <nav className="flex flex-col px-2.5">
            {navigation.map((item) => (
              <Link
                key={item.href}
                className={`nav-console ${item.active ? "nav-console-active" : ""}`}
                href={item.href}
              >
                {item.icon}
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="console-account mx-2.5 mt-auto border-t border-border pt-2.5">
            <div className="flex items-center gap-2.5 rounded-md px-2 py-1.5">
              {/* Avatar tròn viền sáng để nổi trên nền navy — hình vuông nền tint
                  như trước gần như biến mất trên nền tối. */}
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-border-strong bg-surface-3 text-[11px] font-semibold text-text">
                {sessionUser ? initials(sessionUser.display_name) : "…"}
              </span>
              <div className="console-account-id min-w-0">
                <p className="truncate text-[12.5px] font-semibold text-text">
                  {sessionUser?.display_name ?? "Loading…"}
                </p>
                <p className="truncate text-[11px] text-text-faint">{sessionUser?.email ?? ""}</p>
              </div>
            </div>
            <button
              type="button"
              onClick={signOut}
              className="mt-1 flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-[12px] font-medium text-text-faint transition hover:bg-surface-2 hover:text-text"
            >
              <LogoutIcon />
              <span className="console-account-label">Sign out</span>
            </button>
          </div>
        </aside>
        <MobileNavDrawer
          label={isHrPortal ? t("hrWorkspace") : t("navigation")}
          onClose={closeMobileNav}
          open={mobileNavOpen}
        >
          <BrandHomeLink className="mb-5 inline-flex" onClick={closeMobileNav}>
            <RalionBrand size={28} />
          </BrandHomeLink>
          <nav className="flex flex-col gap-1">
            {navigation.map((item) => (
              <Link
                key={item.href}
                className={`nav-console ${item.active ? "nav-console-active" : ""}`}
                href={item.href}
                onClick={closeMobileNav}
              >
                {item.icon}
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="mt-auto grid gap-3 border-t border-divider pt-4">
            <LanguageSwitcher />
            <button
              className="min-h-11 rounded-md border border-border-strong px-3 text-sm font-semibold"
              onClick={signOut}
              type="button"
            >
              {common("logout")}
            </button>
          </div>
        </MobileNavDrawer>
        <section className="flex min-w-0 flex-1 flex-col">
          <header className="console-topbar flex flex-none items-center justify-between border-b border-border bg-surface px-5 md:px-7">
            <div className="flex min-w-0 items-center gap-3">
              <button
                aria-label={common("openMenu")}
                className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-md border border-border-strong text-xl md:hidden"
                onClick={() => setMobileNavOpen(true)}
                type="button"
              >
                <span aria-hidden="true">☰</span>
              </button>
              <div className="min-w-0 leading-[1.25]">
                <p className="text-[12.5px] font-semibold text-text">
                  {isHrPortal ? "HR Workspace" : "Operations Workspace"}
                </p>
                <p className="hidden text-[11px] text-text-faint sm:block">Ralion · Nội bộ</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <LanguageSwitcher className="hidden md:inline-flex" compact />
              <AccountMenu
                displayName={sessionUser?.display_name}
                roleLabel={sessionUser?.system_role ?? undefined}
              />
            </div>
          </header>
          <div className="flex-1 overflow-y-auto">
            <div className="mx-auto max-w-[1520px] px-5 pt-7 pb-10 md:px-8">
              <nav className="mb-3.5 flex items-center gap-1.5 text-[12.5px] text-text-faint">
                <span className="font-medium text-text-subtle">
                  {isHrPortal ? "HR Workspace" : "Admin Workspace"}
                </span>
                <span>/</span>
                <span className="font-semibold text-text">{SECTION_META[section].title}</span>
              </nav>
              {/* Tiêu đề và mô tả nằm cùng cụm bên trái, nút chính neo phải và
                  không co lại — đúng bố cục page-head của mẫu. */}
              <div className="mb-[22px] flex items-start justify-between gap-6">
                <div className="min-w-0">
                  <h1 className="text-[24px] font-semibold tracking-[-0.015em] text-text">
                    {SECTION_META[section].title}
                  </h1>
                  <p className="mt-1 text-[13.5px] text-text-subtle">
                    {SECTION_META[section].lead}
                  </p>
                </div>
                {SECTION_META[section].action && (
                  <button
                    type="button"
                    onClick={() => setModal(true)}
                    className="mt-px flex h-9 flex-shrink-0 items-center gap-1.5 rounded-md border border-navy bg-navy px-[15px] text-[13px] font-semibold text-white transition hover:bg-navy-hover"
                  >
                    <span aria-hidden="true" className="text-[15px] leading-none">
                      +
                    </span>
                    {SECTION_META[section].action}
                  </button>
                )}
              </div>
              {section === "policies" && (
                <div className="console-toolbar mb-4 flex flex-wrap gap-2 rounded-md border border-border bg-surface p-2.5">
                  <label className="relative min-w-[240px] flex-1">
                    <span className="sr-only">Search</span>
                    <span className="pointer-events-none absolute top-3 left-3 text-text-faint">
                      <SearchIcon />
                    </span>
                    <input
                      value={query}
                      onChange={(event) => {
                        setQuery(event.target.value);
                        setPage(1);
                      }}
                      placeholder="Search by title"
                      className="h-9 w-full rounded-md border border-border-strong bg-surface pr-3 pl-9 text-[13px] outline-none transition focus:border-link focus:ring-2 focus:ring-tint-navy"
                    />
                  </label>
                </div>
              )}
              {loading && <TableSkeleton />}
              {error && (
                <div role="alert" className="rounded-md border border-danger-border bg-surface p-5">
                  <p className="font-semibold text-danger">
                    {errorStatus === 401 || errorStatus === 403
                      ? "This session does not have Admin rights"
                      : "Data could not be loaded"}
                  </p>
                  <p className="mt-1 text-sm text-text-subtle">{error}</p>
                  {errorStatus === 401 || errorStatus === 403 ? (
                    <button
                      type="button"
                      onClick={signOut}
                      className="mt-4 inline-flex h-10 items-center rounded-md bg-navy px-4 text-sm font-semibold text-white"
                    >
                      Sign in as an administrator
                    </button>
                  ) : (
                    <button
                      onClick={load}
                      className="mt-4 h-10 rounded-md bg-navy px-4 text-sm font-semibold text-white"
                    >
                      Try again
                    </button>
                  )}
                </div>
              )}
              {!loading && !error && overview && <OverviewPanel />}
              {section === "users" && <UsersPanel reloadToken={panelReloadToken} />}
              {section === "projects" && <ProjectsPanel reloadToken={panelReloadToken} />}
              {section === "master-template" && <MasterTemplatePanel />}
              {section === "memberships" && (
                <MembershipsPanel
                  reloadToken={panelReloadToken}
                  assignOpen={modal}
                  onCloseAssign={() => setModal(false)}
                />
              )}
              {!loading && !error && paged && rows.length === 0 && (
                <div className="rounded-md border border-border bg-surface p-10 text-center text-sm text-text-subtle">
                  No matching records.
                </div>
              )}
              {!loading && !error && paged && rows.length > 0 && (
                <ConsoleTable section={section} rows={rows} />
              )}
              {!loading && !error && meta && (
                <div className="mt-4 flex items-center justify-between gap-3 rounded-md border border-border bg-surface px-4 py-3 text-[13px] text-text-subtle">
                  <span>
                    Showing {rows.length} of {meta.total} records
                  </span>
                  <div className="flex gap-2">
                    <button
                      disabled={page === 1}
                      onClick={() => setPage(page - 1)}
                      className="pager-console"
                    >
                      Previous
                    </button>
                    <span className="self-center">Page {page}</span>
                    <button
                      disabled={page * PAGE_SIZE >= meta.total}
                      onClick={() => setPage(page + 1)}
                      className="pager-console"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
              {modal && section !== "memberships" && (
                <Modal
                  section={section}
                  onClose={() => setModal(false)}
                  onCreated={() => {
                    setPanelReloadToken((token) => token + 1);
                    load();
                  }}
                />
              )}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

// Rendered only for section "policies": users/projects/memberships are self-managed
// panels (see `load` above, which never populates `data` for them).
function ConsoleTable({ section, rows }: { section: ConsoleSection; rows: unknown[] }) {
  const headers = [
    "Policy document",
    "Policy category",
    "Version",
    "Version status",
    "Created by",
    "Document status",
  ];
  return (
    <div className="overflow-hidden rounded-md border border-border bg-surface">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[820px] border-collapse text-left">
          {/* Nền, chiều cao và cỡ chữ của th do `.ralion-console table th` lo. Đặt
              màu cứng #fafbfe ở đây khiến bảng này không đổi theo bảng màu console. */}
          <thead>
            <tr>
              {headers.map((header) => (
                <th key={header}>{header}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {section === "policies" &&
              (rows as ConsolePolicy[]).map((policy) => (
                <tr key={policy.document_id} className="border-b border-divider last:border-0">
                  <td className="px-5 py-4 text-sm font-semibold text-navy">{policy.title}</td>
                  <td className="px-5 py-4 text-sm">{policy.policy_category}</td>
                  <td className="px-5 py-4 text-sm">
                    {policy.version_no ? `Version ${policy.version_no}` : "—"}
                  </td>
                  <td className="px-5 py-4 text-sm">{policy.version_status ?? "None"}</td>
                  <td className="px-5 py-4 text-sm">{policy.created_by_name ?? "—"}</td>
                  <td className="px-5 py-4">
                    <Badge active={policy.status === "ACTIVE"}>
                      {policy.status === "ACTIVE" ? "Active" : "Archived"}
                    </Badge>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
