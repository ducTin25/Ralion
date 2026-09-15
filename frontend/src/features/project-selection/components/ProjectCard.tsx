import { ChevronRightIcon } from "./icons";
import { ProgressBar } from "./ProgressBar";
import { StatusBadge } from "./StatusBadge";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import { BriefcaseBusiness, Code2, FolderKanban } from "lucide-react";

import type { MembershipCard, SyncStatus } from "@/types/project";

function formatDate(value: string, locale: string) {
  return new Intl.DateTimeFormat(locale === "vi" ? "vi-VN" : "en-US", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}

interface ProjectCardProps {
  membership: MembershipCard;
  openingProjectKey: string | null;
  onContinue: (membership: MembershipCard) => void;
}

export function ProjectCard({ membership, openingProjectKey, onContinue }: ProjectCardProps) {
  const t = useTranslations("projectSelection");
  const locale = useLocale();
  const [renderedAt] = useState(() => Date.now());
  const syncLabels: Record<SyncStatus, { text: string; dot: string }> = {
    SUCCESS: { text: t("syncSuccess"), dot: "bg-success" },
    SYNCING: { text: t("syncing"), dot: "bg-warn" },
    PARTIAL: { text: t("syncPartial"), dot: "bg-warn" },
    FAILED: { text: t("syncFailed"), dot: "bg-danger" },
    NOT_STARTED: { text: t("syncNotStarted"), dot: "bg-text-faint" },
  };
  const relativeDate = (value: string | null) => {
    if (!value) return t("syncNever");
    const difference = renderedAt - new Date(value).getTime();
    const hours = Math.max(0, Math.round(difference / 3_600_000));
    if (hours < 1) return t("justNow");
    if (hours < 24) return t("hoursAgo", { count: hours });
    const days = Math.round(hours / 24);
    if (days === 1) return t("yesterday");
    return t("daysAgo", { count: days });
  };
  const plan = membership.plan;
  const sync = syncLabels[membership.syncStatus];
  const isOpening = openingProjectKey === membership.projectKey;
  const isBusy = openingProjectKey !== null;
  const roleLabel = membership.projectRole === "PM" ? "PM" : t("engineer");

  return (
    <article className="project-card flex h-full flex-col gap-4 rounded-[14px] border border-border bg-surface px-6 pt-6 pb-5 shadow-sm">
      <div className="flex items-start gap-[13px]">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[12px] border border-[var(--ralion-primary-border)] bg-[var(--ralion-primary-subtle)] text-[var(--ralion-primary)]">
          <FolderKanban aria-hidden="true" className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="text-[17px] leading-[1.3] font-semibold tracking-[-0.015em] text-text">
            {membership.projectName}
          </h2>
          <div className="mt-1 flex flex-wrap items-center gap-[9px]">
            <span className="text-[13.5px] text-text-subtle tabular-nums whitespace-nowrap">
              {membership.projectKey}
            </span>
            <span className="h-[11px] w-px bg-border" />
            <span className="inline-flex items-center gap-1.5 text-[13.5px] font-medium text-success-text whitespace-nowrap">
              <span className="h-[7px] w-[7px] rounded-full bg-success" />
              {t("active")}
            </span>
          </div>
        </div>
        <span
          className={`inline-flex h-7 shrink-0 items-center rounded-full border px-2.5 text-xs font-semibold ${
            membership.projectRole === "PM"
              ? "border-tint-navy-border bg-tint-navy text-link"
              : "border-border bg-canvas text-text-muted"
          }`}
        >
          {membership.projectRole === "PM" ? (
            <BriefcaseBusiness aria-hidden="true" className="mr-1 h-3.5 w-3.5" />
          ) : (
            <Code2 aria-hidden="true" className="mr-1 h-3.5 w-3.5" />
          )}
          {roleLabel}
        </span>
      </div>

      <div className="h-px bg-divider" />

      <dl className="grid grid-cols-[124px_1fr] gap-x-3 gap-y-[9px] text-[13.5px] max-[390px]:grid-cols-[120px_1fr]">
        <dt className="text-text-subtle">{t("joined")}</dt>
        <dd className="text-sm text-text tabular-nums">
          {formatDate(membership.joinedAt, locale)}
        </dd>
        <dt className="text-text-subtle">{t("plan")}</dt>
        <dd className="flex flex-wrap items-center gap-2">
          <StatusBadge status={plan?.status ?? null} />
          {plan && (
            <span className="text-[13px] text-text-faint tabular-nums">
              {t("revision", { revision: plan.revision })}
            </span>
          )}
        </dd>
        <dt className="text-text-subtle">{t("blockers")}</dt>
        <dd
          className={`text-sm tabular-nums ${
            (plan?.openBlockers ?? 0) > 0 ? "font-semibold text-danger" : "text-text-muted"
          }`}
        >
          {(plan?.openBlockers ?? 0) > 0 ? plan?.openBlockers : t("none")}
        </dd>
      </dl>

      <ProgressBar
        done={plan?.requiredDone ?? 0}
        total={plan?.requiredTotal ?? 0}
        projectName={membership.projectName}
      />

      {membership.syncStatus === "FAILED" && (
        <div className="flex items-start gap-2 rounded-md border border-warn-border bg-warn-bg px-3 py-2.5 text-[13px] leading-5 text-warn-text">
          <span className="mt-[7px] h-[7px] w-[7px] shrink-0 rounded-full bg-danger" />
          <span>{t("syncWarning", { relative: relativeDate(membership.lastSyncedAt) })}</span>
        </div>
      )}

      <div className="mt-auto flex items-center justify-between gap-3 border-t border-divider-soft pt-3.5 max-md:flex-col max-md:items-stretch">
        <div className="flex min-w-0 items-center gap-2 text-[13px] text-text-subtle">
          <span className={`h-[7px] w-[7px] shrink-0 rounded-full ${sync.dot}`} />
          <span className="truncate">
            {sync.text} · {relativeDate(membership.lastSyncedAt)}
          </span>
        </div>
        <button
          type="button"
          disabled={isBusy}
          aria-label={t("continueLabel", { project: membership.projectName, role: roleLabel })}
          onClick={() => onContinue(membership)}
          className="inline-flex h-11 min-w-[128px] items-center justify-center gap-2 rounded-[10px] border border-navy bg-navy px-4 text-sm font-semibold text-white shadow-sm transition hover:-translate-y-px hover:bg-navy-hover disabled:cursor-not-allowed disabled:border-disabled-border disabled:bg-disabled-bg disabled:text-disabled-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-link max-md:w-full"
        >
          {isOpening ? (
            <>
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/35 border-t-white" />
              {t("opening")}
            </>
          ) : (
            <>
              {t("continue")}
              <ChevronRightIcon className="h-4 w-4" />
            </>
          )}
        </button>
      </div>
    </article>
  );
}
