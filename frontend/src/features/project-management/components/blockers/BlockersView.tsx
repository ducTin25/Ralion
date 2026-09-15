"use client";

import { useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import type { PmBlockerResponseDTO } from "@/features/project-management/dto/responseDTO/blocker.response";
import type { ProjectResponseDTO } from "@/features/project-management/dto/responseDTO/project.response";
import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import { PmButton } from "@/features/project-management/components/ui/PmButton";
import { PmCard, PmKpiRow, PmPageHead } from "@/features/project-management/components/ui/PmCard";
import { PmPill } from "@/features/project-management/components/ui/PmPill";
import tableStyles from "@/features/project-management/components/ui/PmTable.module.scss";

import styles from "./BlockersView.module.scss";

type BlockerFilter = "ALL" | "OPEN" | "RESOLVED";

const CATEGORY_LABEL_KEYS: Record<PmBlockerResponseDTO["category"], string> = {
  ACCESS: "categoryAccess",
  SETUP: "categorySetup",
  DOCUMENT: "categoryDocuments",
  TECHNICAL: "categoryTechnical",
  OTHER: "categoryOther",
};

const STATUS_META: Record<
  PmBlockerResponseDTO["status"],
  { labelKey: string; variant: "warning" | "progress" | "success" }
> = {
  OPEN: { labelKey: "statusJustReported", variant: "warning" },
  ROUTED: { labelKey: "statusProcessing", variant: "progress" },
  RESOLVED: { labelKey: "statusResolved", variant: "success" },
};

function formatDate(value: string, locale: string) {
  return new Intl.DateTimeFormat(locale === "vi" ? "vi-VN" : "en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

type BlockersViewProps = {
  project: ProjectResponseDTO | null;
  blockers: PmBlockerResponseDTO[];
  loading: boolean;
  onResolve: (blockerId: number) => Promise<void>;
};

export function BlockersView({ project, blockers, loading, onResolve }: BlockersViewProps) {
  const t = useTranslations("pmUi");
  const locale = useLocale();
  const [filter, setFilter] = useState<BlockerFilter>("ALL");
  const [resolvingId, setResolvingId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const openCount = blockers.filter((blocker) => blocker.status !== "RESOLVED").length;
  const resolvedCount = blockers.length - openCount;
  const filtered = useMemo(
    () =>
      blockers.filter((blocker) => {
        if (filter === "OPEN") return blocker.status !== "RESOLVED";
        if (filter === "RESOLVED") return blocker.status === "RESOLVED";
        return true;
      }),
    [blockers, filter],
  );

  const resolve = async (blockerId: number) => {
    setResolvingId(blockerId);
    setActionError(null);
    try {
      await onResolve(blockerId);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : t("blockerUpdateError"));
    } finally {
      setResolvingId(null);
    }
  };

  if (!project) {
    return (
      <section>
        <PmPageHead icon="flag" title={t("blockersTitle")} />
        <PmCard>
          <p className={styles.empty}>
            {t("noManagedProject")}
          </p>
        </PmCard>
      </section>
    );
  }

  return (
    <section>
      <PmPageHead icon="flag" title={t("blockersTitle")} subtitle={t("blockersSubtitle")} />

      <PmKpiRow
        items={[
          { label: t("statusOpen"), value: openCount, icon: "alert", variant: "warning" },
          { label: t("statusResolved"), value: resolvedCount, icon: "check-circle", variant: "success" },
        ]}
      />

      <PmCard>
        <div className={styles.filterRow}>
          <label className={styles.filterLabel}>
            {t("filterByStatus")}
            <select
              className={styles.filterSelect}
              value={filter}
              onChange={(event) => setFilter(event.target.value as BlockerFilter)}
            >
              <option value="ALL">{t("allBlockers")}</option>
              <option value="OPEN">{t("statusOpen")}</option>
              <option value="RESOLVED">{t("statusResolved")}</option>
            </select>
          </label>
          <span className={styles.caption}>{t("blockerCount", { count: filtered.length })}</span>
        </div>

        {actionError && (
          <p className={styles.error} role="alert">
            {actionError}
          </p>
        )}

        {loading ? (
          <p className={styles.empty}>{t("loadingBlockers")}</p>
        ) : filtered.length === 0 ? (
          <p className={styles.empty}>
            {filter === "ALL"
              ? t("noBlockers")
              : t("noBlockersForFilter")}
          </p>
        ) : (
          <div className={tableStyles.tableWrap}>
            <table className={tableStyles.table}>
              <thead>
                <tr>
                  <th>{t("engineer")}</th>
                  <th>{t("task")}</th>
                  <th>{t("blocker")}</th>
                  <th>{t("status")}</th>
                  <th>{t("reported")}</th>
                  <th>{t("actions")}</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((blocker) => {
                  const status = STATUS_META[blocker.status];
                  return (
                    <tr key={blocker.blocker_id}>
                      <td data-label={t("engineer")}>
                        <div className={styles.engineerCell}>
                          <span className={styles.engineerName}>{blocker.engineer_name}</span>
                          <span className={styles.engineerEmail}>{blocker.engineer_email}</span>
                        </div>
                      </td>
                      <td data-label={t("task")}>
                        <span className={styles.taskTitle}>{blocker.task_title}</span>
                      </td>
                      <td data-label={t("blocker")}>
                        <div className={styles.reason}>
                          <strong>{t(CATEGORY_LABEL_KEYS[blocker.category])}</strong>
                          <br />
                          {blocker.reason}
                        </div>
                        {blocker.attachments.length > 0 && (
                          <div className={styles.attachments}>
                            {blocker.attachments.map((attachment) => (
                              <a
                                key={attachment.attachment_id}
                                href={attachment.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className={styles.attachmentChip}
                                title={attachment.file_name}
                              >
                                <PmIcon name="doc" size={12} />
                                {attachment.file_name}
                              </a>
                            ))}
                          </div>
                        )}
                      </td>
                      <td data-label={t("status")}>
                        <PmPill variant={status.variant}>{t(status.labelKey)}</PmPill>
                      </td>
                      <td data-label={t("reported")}>
                        <span className={styles.date}>{formatDate(blocker.reported_at, locale)}</span>
                      </td>
                      <td className={styles.actionCell} data-label={t("actions")}>
                        {blocker.status !== "RESOLVED" ? (
                          <PmButton
                            size="sm"
                            variant="primary"
                            disabled={resolvingId === blocker.blocker_id}
                            onClick={() => void resolve(blocker.blocker_id)}
                          >
                            {resolvingId === blocker.blocker_id ? t("saving") : t("markResolved")}
                          </PmButton>
                        ) : (
                          <span className={styles.date}>
                            {formatDate(blocker.resolved_at ?? blocker.reported_at, locale)}
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
      </PmCard>
    </section>
  );
}
