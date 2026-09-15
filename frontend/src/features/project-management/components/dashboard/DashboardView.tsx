"use client";

import { useEffect, useState, type CSSProperties } from "react";
import { useLocale, useTranslations } from "next-intl";

import { getProjectDashboard } from "@/features/project-management/api";
import type { ProjectResponseDTO } from "@/features/project-management/dto/responseDTO/project.response";
import type { PmDashboardResponseDTO } from "@/features/project-management/dto/responseDTO/pmDashboard.response";
import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import { PmButton } from "@/features/project-management/components/ui/PmButton";
import { PmCard, PmKpiRow, PmPageHead } from "@/features/project-management/components/ui/PmCard";
import { PmPill } from "@/features/project-management/components/ui/PmPill";
import tableStyles from "@/features/project-management/components/ui/PmTable.module.scss";

import styles from "./DashboardView.module.scss";

const CATEGORY_LABEL_KEYS: Record<string, string> = {
  ACCESS: "categoryAccess",
  SETUP: "categorySetup",
  DOCUMENT: "categoryDocument",
  TECHNICAL: "categoryTechnical",
  OTHER: "categoryOther",
};

function formatDate(value: string, locale: string) {
  return new Intl.DateTimeFormat(locale === "vi" ? "vi-VN" : "en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}

type DashboardViewProps = {
  project: ProjectResponseDTO | null;
  onGoToMembers: () => void;
  onGoToBlockers: () => void;
  onGoToDocs: () => void;
  onGoToTemplate: () => void;
};

/** Trang "Tổng quan" — SoT §21 (TV1): "Progress dashboard và close onboarding". Tổng hợp số liệu
 * đã có sẵn ở các trang khác vào 1 màn hình, mỗi khối có nút mở đúng trang chi tiết tương ứng. */
export function DashboardView({
  project,
  onGoToMembers,
  onGoToBlockers,
  onGoToDocs,
  onGoToTemplate,
}: DashboardViewProps) {
  const t = useTranslations("pm.dashboard");
  const locale = useLocale();
  const [data, setData] = useState<PmDashboardResponseDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!project) return;
    let cancelled = false;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError(null);
      void getProjectDashboard(project.project_id, controller.signal)
        .then((result) => {
          if (!cancelled) setData(result);
        })
        .catch((err) => {
          if (!cancelled) setError(err instanceof Error ? err.message : t("loadError"));
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 0);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [project, t]);

  if (!project) {
    return (
      <section>
        <PmPageHead icon="grid" title={t("title")} />
        <PmCard>
          <p className={tableStyles.emptyNote}>{t("noProject")}</p>
        </PmCard>
      </section>
    );
  }

  return (
    <section>
      <PmPageHead icon="grid" title={t("title")} subtitle={t("subtitle", { project: project.name })} />

      {loading ? (
        <PmCard>
          <p className={tableStyles.emptyNote}>{t("loading")}</p>
        </PmCard>
      ) : error || !data ? (
        <PmCard>
          <p className={styles.error}>{error ?? t("dataUnavailable")}</p>
        </PmCard>
      ) : (
        <>
          <PmCard className={styles.priorityCard}>
            <div className={styles.priorityIcon}>
              <PmIcon name={data.overdue_task_count > 0 ? "alert" : "check-circle"} size={24} />
            </div>
            <div className={styles.priorityCopy}>
              {!data.template_approved ? (
                <>
                  <h2>{t("priorityTemplateTitle")}</h2>
                  <p>{t("priorityTemplateBody")}</p>
                </>
              ) : data.document_group_count < data.document_group_total ? (
                <>
                  <h2>{t("priorityDocumentsTitle")}</h2>
                  <p>
                    {t("priorityDocumentsBody", {
                      current: data.document_group_count,
                      total: data.document_group_total,
                    })}
                  </p>
                </>
              ) : data.open_blocker_count > 0 ? (
                <>
                  <h2>{t("priorityBlockersTitle")}</h2>
                  <p>{t("priorityBlockersBody", { count: data.open_blocker_count })}</p>
                </>
              ) : data.overdue_task_count > 0 ? (
                <>
                  <h2>{t("priorityOverdueTitle")}</h2>
                  <p>{t("priorityOverdueBody", { count: data.overdue_task_count })}</p>
                </>
              ) : (
                <>
                  <h2>{t("priorityClearTitle")}</h2>
                  <p>{t("priorityClearBody")}</p>
                </>
              )}
            </div>
            <div className={styles.priorityAction}>
              <PmButton
                variant="primary"
                onClick={
                  !data.template_approved
                    ? onGoToTemplate
                    : data.document_group_count < data.document_group_total
                      ? onGoToDocs
                      : data.open_blocker_count > 0
                        ? onGoToBlockers
                        : onGoToMembers
                }
              >
                {t("reviewAction")}
              </PmButton>
              <div className={styles.aiCost}>
                <PmIcon name="coin" size={16} />
                {t("aiCost")}:{" "}
                {data.total_ai_cost_usd === null ? "—" : `$${data.total_ai_cost_usd.toFixed(2)}`}
              </div>
            </div>
          </PmCard>

          <PmKpiRow
            items={[
              {
                label: t("engineers"),
                value: data.engineer_count,
                icon: "users",
                variant: "accent",
              },
              {
                label: t("hasPlan"),
                value: data.with_plan_count,
                icon: "check2",
                variant: "violet",
              },
              {
                label: t("completed"),
                value: data.done_count,
                icon: "check-circle",
                variant: "success",
              },
              {
                label: t("openBlockers"),
                value: data.open_blocker_count,
                icon: "flag",
                variant: data.open_blocker_count > 0 ? "warning" : "success",
              },
              {
                label: t("overdueTasks"),
                value: data.overdue_task_count,
                icon: "alert",
                variant: data.overdue_task_count > 0 ? "warning" : "success",
              },
            ]}
          />

          <div className={styles.chartGrid}>
            <PmCard className={styles.chartCard}>
              <div className={styles.chartHead}>
                <div><span>{t("engineers")}</span><h3>{t("hasPlan")}</h3></div>
                <strong>{data.engineer_count === 0 ? 0 : Math.round((data.with_plan_count / data.engineer_count) * 100)}%</strong>
              </div>
              <div className={styles.donutLayout}>
                <div
                  className={styles.donut}
                  style={{ "--chart-value": data.engineer_count === 0 ? 0 : (data.with_plan_count / data.engineer_count) * 100 } as CSSProperties}
                  role="img"
                  aria-label={`${t("hasPlan")}: ${data.with_plan_count}/${data.engineer_count}`}
                >
                  <span><b>{data.with_plan_count}</b><small>/{data.engineer_count}</small></span>
                </div>
                <div className={styles.legend}>
                  <span><i data-tone="accent" />{t("hasPlan")}<b>{data.with_plan_count}</b></span>
                  <span><i data-tone="muted" />{t("engineers")}<b>{Math.max(data.engineer_count - data.with_plan_count, 0)}</b></span>
                  <span><i data-tone="success" />{t("completed")}<b>{data.done_count}</b></span>
                </div>
              </div>
            </PmCard>

            <PmCard className={styles.chartCard}>
              <div className={styles.chartHead}>
                <div><span>{t("projectDocuments")}</span><h3>{t("categoriesCovered")}</h3></div>
                <strong>{data.document_group_count}/{data.document_group_total}</strong>
              </div>
              <div className={styles.barChart}>
                {[
                  { label: t("documentsPresent"), value: data.document_group_count, total: data.document_group_total, tone: "accent" },
                  { label: t("hasPlan"), value: data.with_plan_count, total: data.engineer_count, tone: "violet" },
                  { label: t("completed"), value: data.done_count, total: data.engineer_count, tone: "success" },
                ].map((item) => {
                  const percentage = item.total === 0 ? 0 : Math.min((item.value / item.total) * 100, 100);
                  return (
                    <div key={item.label} className={styles.barRow}>
                      <span>{item.label}<b>{item.value}/{item.total}</b></span>
                      <div><i data-tone={item.tone} style={{ width: `${percentage}%` }} /></div>
                    </div>
                  );
                })}
              </div>
            </PmCard>
          </div>

          <div className={styles.stack}>
            <div className={styles.grid}>
              <PmCard>
                <div className={styles.cardHead}>
                  <h4>{t("projectDocuments")}</h4>
                  <PmButton size="sm" onClick={onGoToDocs}>
                    {t("openDocuments")}
                  </PmButton>
                </div>
                <p className={styles.cardBody}>
                  {t("documentsPresent")}{" "}
                  <strong>
                    {data.document_group_count}/{data.document_group_total}
                  </strong>{" "}
                  required categories.
                </p>
                <PmPill
                  variant={
                    data.document_group_count === data.document_group_total ? "success" : "warning"
                  }
                >
                  {data.document_group_count === data.document_group_total
                    ? t("categoriesCovered")
                    : t("categoriesMissing")}
                </PmPill>
              </PmCard>

              <PmCard>
                <div className={styles.cardHead}>
                  <h4>{t("masterTemplate")}</h4>
                  <PmButton size="sm" onClick={onGoToTemplate}>
                    {t("openTemplate")}
                  </PmButton>
                </div>
                <p className={styles.cardBody}>
                  {data.template_approved
                    ? t("templateApproved", { count: data.template_task_count })
                    : t("templateNotApproved")}
                </p>
                <PmPill variant={data.template_approved ? "success" : "warning"}>
                  {data.template_approved ? t("ready") : t("needsApproval")}
                </PmPill>
              </PmCard>
            </div>

            <PmCard>
              <div className={styles.cardHead}>
                <h4>{t("oldestBlockers", { count: data.oldest_open_blockers.length })}</h4>
                <PmButton size="sm" onClick={onGoToBlockers}>
                  {t("openBlockersAction")}
                </PmButton>
              </div>
              {data.oldest_open_blockers.length === 0 ? (
                <p className={tableStyles.emptyNote}>{t("noOpenBlockers")}</p>
              ) : (
                <div className={styles.rowList}>
                  {data.oldest_open_blockers.map((blocker) => (
                    <div key={blocker.blocker_id} className={styles.row}>
                      <div className={styles.rowMain}>
                        <span className={styles.rowTitle}>{blocker.engineer_name}</span>
                        <span className={styles.rowMeta}>
                          {CATEGORY_LABEL_KEYS[blocker.category]
                            ? t(CATEGORY_LABEL_KEYS[blocker.category])
                            : blocker.category}{" "}
                          · {blocker.task_title}
                        </span>
                      </div>
                      <span className={styles.rowMeta}>
                        {t("reported", { date: formatDate(blocker.reported_at, locale) })}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </PmCard>

            <PmCard>
              <div className={styles.cardHead}>
                <h4>{t("mostOverdue", { count: data.engineers_with_most_overdue.length })}</h4>
                <PmButton size="sm" onClick={onGoToMembers}>
                  {t("openMembers")}
                </PmButton>
              </div>
              {data.engineers_with_most_overdue.length === 0 ? (
                <p className={tableStyles.emptyNote}>{t("noOverdue")}</p>
              ) : (
                <div className={styles.rowList}>
                  {data.engineers_with_most_overdue.map((item) => (
                    <div key={item.membership_id} className={styles.row}>
                      <span className={styles.rowTitle}>{item.engineer_name}</span>
                      <PmPill variant="warning">
                        {t("overdueCount", { count: item.overdue_count })}
                      </PmPill>
                    </div>
                  ))}
                </div>
              )}
            </PmCard>
          </div>
        </>
      )}
    </section>
  );
}
