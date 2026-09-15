"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { BriefcaseBusiness, Code2, FolderKanban, Sparkles } from "lucide-react";

import { LanguageSwitcher } from "@/components/i18n/LanguageSwitcher";
import { useRouter } from "@/i18n/navigation";
import { EmptySearchState } from "./EmptySearchState";
import { AlertIcon, CheckIcon, SearchIcon, XIcon } from "./icons";
import { ProjectCard } from "./ProjectCard";
import { SelectionSkeleton } from "./SelectionSkeleton";

import {
  MembershipApiError,
  useProjectMemberships,
} from "@/features/project-selection/hooks/useProjectMemberships";
import { RalionBrand } from "@/components/brand/RalionBrand";
import { defaultLandingPath, projectPortalPath } from "@/features/auth/routing";
import { useSession } from "@/features/auth/session";
import type { MembershipCard } from "@/types/project";

type SortValue = "joined" | "name" | "progress";

function progress(membership: MembershipCard) {
  const plan = membership.plan;
  return plan && plan.requiredTotal > 0 ? plan.requiredDone / plan.requiredTotal : 0;
}

function initials(displayName: string) {
  return displayName
    .trim()
    .split(/\s+/)
    .slice(-2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

function ErrorPanel({
  message,
  primaryLabel,
  onPrimary,
  showContact = false,
}: {
  message: string;
  primaryLabel: string;
  onPrimary: () => void;
  showContact?: boolean;
}) {
  const t = useTranslations("projectSelection");
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div
        role="alert"
        className="flex items-start gap-2.5 rounded-md border border-danger-border bg-danger-bg px-3 py-2.5 text-sm leading-[1.45] text-danger"
      >
        <AlertIcon className="mt-0.5 h-4 w-4 shrink-0" />
        <span>{message}</span>
      </div>
      <div className="mt-3.5 flex flex-wrap gap-2.5">
        <button
          type="button"
          onClick={onPrimary}
          className="h-10 rounded-md border border-navy bg-navy px-4 text-sm font-semibold text-white hover:bg-navy-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-link"
        >
          {primaryLabel}
        </button>
        {showContact && (
          <a
            href="mailto:admin@ralion.local"
            className="inline-flex h-10 items-center rounded-md border border-border-strong bg-surface px-4 text-sm font-semibold text-navy hover:bg-canvas hover:no-underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-link"
          >
            {t("contactAdmin")}
          </a>
        )}
      </div>
    </div>
  );
}

export function ProjectSelectionScreen() {
  const t = useTranslations("projectSelection");
  const locale = useLocale();
  const router = useRouter();
  const { user, loading: sessionLoading, error: sessionError, signOut } = useSession();
  const canSelectProject = user !== null && user.system_role === null;
  const { data, isLoading, error, refetch, establishMembership } =
    useProjectMemberships(canSelectProject);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortValue>("joined");
  const [opening, setOpening] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [actionError, setActionError] = useState<MembershipApiError | null>(null);

  useEffect(() => {
    if (sessionLoading) return;
    if (!user) {
      if (sessionError?.status === 401) router.replace("/login?next=/select-project");
      return;
    }
    if (user.system_role !== null) router.replace(defaultLandingPath(user));
  }, [router, sessionError, sessionLoading, user]);

  const filtered = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return data
      .filter(
        (membership) =>
          !normalizedQuery ||
          membership.projectName.toLowerCase().includes(normalizedQuery) ||
          membership.projectKey.toLowerCase().includes(normalizedQuery),
      )
      .toSorted((first, second) => {
        if (sort === "name") return first.projectName.localeCompare(second.projectName);
        if (sort === "progress") return progress(second) - progress(first);
        return new Date(second.joinedAt).getTime() - new Date(first.joinedAt).getTime();
      });
  }, [data, query, sort]);
  const pmCount = data.filter((membership) => membership.projectRole === "PM").length;
  const engineerCount = data.filter((membership) => membership.projectRole === "ENGINEER").length;

  const clearSearch = () => {
    setQuery("");
  };

  const continueToProject = useCallback(
    async (membership: MembershipCard) => {
      if (opening) return;
      setOpening(membership.projectKey);
      setActionError(null);
      setToast(null);
      try {
        const context = await establishMembership(membership.membershipId);
        setToast(t("selected", { name: context.projectName, key: context.projectKey }));
        // Dựng URL từ structured context đã được backend xác minh, để project
        // context luôn là một phần bắt buộc của URL portal.
        router.replace(projectPortalPath(context.projectRole, context.projectId));
      } catch (caught) {
        setActionError(
          caught instanceof MembershipApiError
            ? caught
            : new MembershipApiError("SYSTEM_ERROR", t("openError"), 503),
        );
      } finally {
        setOpening(null);
      }
    },
    [establishMembership, opening, router, t],
  );

  if (sessionLoading || (user && user.system_role !== null)) return null;

  if (!user) {
    if (sessionError?.status === 401) return null;
    return (
      <main className="ralion-workspace flex min-h-screen items-center justify-center bg-canvas px-5 text-text">
        <ErrorPanel
          message={t("verifyError")}
          primaryLabel={t("retry")}
          onPrimary={() => window.location.reload()}
        />
      </main>
    );
  }

  return (
    <main className="ralion-workspace min-h-screen bg-[radial-gradient(circle_at_82%_0%,rgba(16,144,203,.12),transparent_30%),linear-gradient(180deg,#f8fbfd_0%,#f3f7fa_100%)] text-text">
      <header className="sticky top-0 z-10 flex h-[68px] items-center justify-between border-b border-header-border/80 bg-surface/90 px-7 backdrop-blur-xl max-md:px-[18px]">
        <RalionBrand size={26} />
        <div className="flex items-center gap-4">
          <LanguageSwitcher compact />
          <div className="flex items-center gap-[9px]">
            <span className="flex h-7 w-7 items-center justify-center rounded-md border border-border-strong bg-surface-3 text-xs font-semibold text-text-secondary">
              {initials(user.display_name)}
            </span>
            <span className="text-sm max-sm:hidden">{user.display_name}</span>
          </div>
          <span className="h-5 w-px bg-header-border" />
          <button
            type="button"
            onClick={() => void signOut()}
            className="h-10 px-1 text-sm text-link hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-link"
          >
            {t("logout")}
          </button>
        </div>
      </header>

      {toast && (
        <div
          role="status"
          className="fixed top-[70px] right-7 z-20 flex max-w-[430px] items-start gap-2.5 rounded-md border border-success-border bg-success-bg px-3.5 py-3 text-sm leading-5 text-success-text shadow-[0_2px_10px_rgba(31,36,48,.1)] max-md:right-[18px] max-md:left-[18px]"
        >
          <CheckIcon className="mt-0.5 h-4 w-4 shrink-0" />
          <span className="flex-1">{toast}</span>
          <button
            type="button"
            aria-label={t("closeNotice")}
            onClick={() => setToast(null)}
            className="rounded p-0.5 hover:bg-success-border/40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-link"
          >
            <XIcon className="h-4 w-4" />
          </button>
        </div>
      )}

      <div className="mx-auto max-w-[1760px] px-6 pt-7 pb-10 max-md:px-[18px] max-md:pt-5 max-md:pb-6">
        <section className="relative overflow-hidden rounded-[22px] border border-[#d5e8f1] bg-white px-8 py-7 shadow-[0_14px_40px_rgba(23,59,96,.07)] max-md:px-5 max-md:py-5">
          <div className="pointer-events-none absolute -top-24 -right-16 h-64 w-64 rounded-full bg-[#dff3fb] blur-2xl" />
          <div className="relative grid grid-cols-[1fr_300px] items-center gap-8 max-md:grid-cols-1 max-md:gap-5">
            <div>
              <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-[var(--ralion-primary-subtle)] px-3 py-1.5 text-xs font-semibold text-[var(--ralion-primary-ink)]">
                <Sparkles aria-hidden="true" className="h-3.5 w-3.5" />
                Ralion workspace
              </div>
              <h1 className="max-w-2xl text-[clamp(1.8rem,3vw,2.55rem)] leading-[1.1] font-bold tracking-[-0.04em] text-[#0b1f3a]">
                {t("title")}
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-text-subtle">{t("lead")}</p>
              {!isLoading && !error && data.length > 0 && (
                <span className="mt-4 inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1.5 text-xs text-text-subtle tabular-nums">
                  <FolderKanban aria-hidden="true" className="h-3.5 w-3.5 text-[var(--ralion-primary)]" />
                  {t("activeAccess", { count: data.length })}
                </span>
              )}
            </div>
            <div className="rounded-[20px] border border-[#d6e6f2] bg-[linear-gradient(145deg,#eef8fc,#f4f8fd)] p-4">
              <div className="flex items-center gap-3 border-b border-[#cfe5ec] pb-3">
                <span className="flex h-11 w-11 items-center justify-center rounded-[13px] bg-white text-[var(--ralion-primary)] shadow-sm">
                  <FolderKanban aria-hidden="true" className="h-5 w-5" />
                </span>
                <div>
                  <b className="block text-sm text-[#0b1f3a]">
                    {locale.startsWith("vi") ? "Workspace của bạn" : "Your workspace"}
                  </b>
                  <small className="text-xs text-text-subtle">
                    {locale.startsWith("vi")
                      ? "Chọn đúng vai trò để tiếp tục"
                      : "Continue with the right role"}
                  </small>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {pmCount > 0 && (
                  <span className="inline-flex items-center gap-2 rounded-full border border-[#cfdef7] bg-white px-3 py-2 text-xs font-semibold text-[#2463d4]">
                    <BriefcaseBusiness aria-hidden="true" className="h-4 w-4" /> PM · {pmCount}
                  </span>
                )}
                {engineerCount > 0 && (
                  <span className="inline-flex items-center gap-2 rounded-full border border-[var(--ralion-primary-border)] bg-white px-3 py-2 text-xs font-semibold text-[var(--ralion-primary-ink)]">
                    <Code2 aria-hidden="true" className="h-4 w-4" /> {t("engineer")} ·{" "}
                    {engineerCount}
                  </span>
                )}
              </div>
            </div>
          </div>
        </section>

        {!isLoading && !error && data.length > 0 && (
          <div className="mt-7 flex flex-wrap items-center gap-3 rounded-xl border border-border bg-surface p-3 shadow-sm">
            <label className="relative min-w-[260px] flex-1 max-md:w-full max-md:flex-auto">
              <span className="sr-only">{t("searchLabel")}</span>
              <SearchIcon className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-text-faint" />
              <input
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  setToast(null);
                }}
                aria-label={t("searchLabel")}
                placeholder={t("searchPlaceholder")}
                className="h-11 w-full rounded-[10px] border border-border-strong bg-surface pr-3 pl-9 text-sm text-text placeholder:text-text-faint focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-link max-md:text-[15px]"
              />
            </label>
            <label className="max-md:flex-1">
              <span className="sr-only">{t("sortLabel")}</span>
              <select
                value={sort}
                onChange={(event) => setSort(event.target.value as SortValue)}
                aria-label={t("sortLabel")}
                className="h-11 rounded-[10px] border border-border-strong bg-surface px-3 text-sm text-text-muted focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-link max-md:w-full max-md:text-[15px]"
              >
                <option value="joined">{t("sortRecent")}</option>
                <option value="name">{t("sortName")}</option>
                <option value="progress">{t("sortProgress")}</option>
              </select>
            </label>
            <span
              role="status"
              aria-live="polite"
              className="ml-auto text-[13px] text-text-subtle tabular-nums max-md:w-full"
            >
              {filtered.length === data.length
                ? t("resultAll", { count: data.length })
                : t("resultFiltered", { filtered: filtered.length, total: data.length })}
            </span>
          </div>
        )}

        <div className="mt-6">
          {isLoading && <SelectionSkeleton />}
          {!isLoading && error && (
            <ErrorPanel message={t("loadError")} primaryLabel={t("retry")} onPrimary={refetch} />
          )}
          {!isLoading && !error && data.length === 0 && (
            <div className="rounded-lg border border-border bg-surface px-6 py-8 text-center">
              <h2 className="text-base font-semibold">{t("emptyTitle")}</h2>
              <p className="mx-auto mt-1.5 max-w-xl text-sm leading-6 text-text-subtle">
                {t("emptyBody")}
              </p>
              <div className="mt-5 flex flex-wrap justify-center gap-2.5">
                <a
                  href="mailto:admin@ralion.local"
                  className="inline-flex h-11 items-center rounded-md border border-navy bg-navy px-[18px] text-sm font-semibold text-white hover:bg-navy-hover hover:no-underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-link"
                >
                  {t("contactAdmin")}
                </a>
                <button
                  type="button"
                  onClick={() => void signOut()}
                  className="h-11 rounded-md border border-border-strong bg-surface px-[18px] text-sm font-semibold text-navy hover:bg-canvas focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-link"
                >
                  {t("logout")}
                </button>
              </div>
            </div>
          )}
          {!isLoading && !error && data.length > 0 && actionError && (
            <ErrorPanel
              message={actionError.message}
              primaryLabel={
                actionError.code === "PROJECT_ARCHIVED" ? t("reload") : t("chooseAnother")
              }
              onPrimary={() => {
                setActionError(null);
                refetch();
              }}
              showContact={actionError.code !== "PROJECT_ARCHIVED"}
            />
          )}
          {!isLoading && !error && data.length > 0 && !actionError && filtered.length === 0 && (
            <EmptySearchState onClear={clearSearch} />
          )}
          {!isLoading && !error && data.length > 0 && !actionError && filtered.length > 0 && (
            <div className="project-grid">
              {filtered.map((membership) => (
                <ProjectCard
                  key={membership.membershipId}
                  membership={membership}
                  openingProjectKey={opening}
                  onContinue={continueToProject}
                />
              ))}
            </div>
          )}
        </div>

        {!isLoading && !error && data.length > 0 && (
          <p className="mt-5 text-[13px] leading-5 text-text-faint">{t("footnote")}</p>
        )}
      </div>
    </main>
  );
}
