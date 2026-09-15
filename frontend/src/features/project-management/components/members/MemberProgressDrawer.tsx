"use client";

import { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { getMemberProgress } from "@/features/project-management/api";
import type { ProjectMembershipDetailResponseDTO } from "@/features/project-management/dto/responseDTO/projectMembership.response";
import type { PmMemberProgressResponseDTO } from "@/features/project-management/dto/responseDTO/pmProgress.response";
import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import { PmKpiRow } from "@/features/project-management/components/ui/PmCard";
import { PmDrawer } from "@/features/project-management/components/ui/PmDrawer";
import { PmPill } from "@/features/project-management/components/ui/PmPill";
import { CATEGORY_OPTIONS } from "@/features/project-management/components/template/TaskFormModal";
import tableStyles from "@/features/project-management/components/ui/PmTable.module.scss";

import styles from "./MemberProgressDrawer.module.scss";

const TASK_STATUS_META: Record<
  PmMemberProgressResponseDTO["tasks"][number]["status"],
  { labelKey: string; variant: "neutral" | "progress" | "success" | "warning" | "critical" }
> = {
  NOT_STARTED: { labelKey: "statusNotStarted", variant: "neutral" },
  IN_PROGRESS: { labelKey: "statusInProgress", variant: "progress" },
  DONE: { labelKey: "statusDone", variant: "success" },
  BLOCKED: { labelKey: "statusBlocked", variant: "critical" },
};

const BLOCKER_STATUS_LABEL_KEYS: Record<string, string> = {
  OPEN: "statusJustReported",
  ROUTED: "statusProcessing",
  RESOLVED: "statusResolved",
};

function formatDateTime(value: string | null, locale: string): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat(locale === "vi" ? "vi-VN" : "en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

type MemberProgressDrawerProps = {
  member: ProjectMembershipDetailResponseDTO;
  projectId: number;
  // Đến từ deep-link chuông thông báo: task nào cần cuộn tới + làm nổi bật khi drawer mở.
  highlightTaskId?: number | null;
  onClose: () => void;
};

/** Drawer "Xem tiến độ" mở từ trang Thành viên — SoT §17.2: PM theo dõi tiến độ, deadline và
 * blocker của TỪNG plan. Chỉ đọc: xử lý blocker vẫn làm ở trang Blocker Engineer (1 chỗ duy nhất
 * thao tác, tránh 2 nơi cùng sửa 1 dữ liệu dễ lệch trạng thái). */
export function MemberProgressDrawer({
  member,
  projectId,
  highlightTaskId = null,
  onClose,
}: MemberProgressDrawerProps) {
  const t = useTranslations("pmUi");
  const locale = useLocale();
  const [progress, setProgress] = useState<PmMemberProgressResponseDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const highlightedRowRef = useRef<HTMLDivElement | null>(null);
  const progressCategories = [
    ...CATEGORY_OPTIONS,
    {
      value: "CONVENTION" as const,
      labelKey: "categoryConventionFuture",
      icon: "book" as const,
      variant: "violet" as const,
    },
    {
      value: "FIRST_TASK" as const,
      labelKey: "categoryFirstTaskFuture",
      icon: "check-circle" as const,
      variant: "success" as const,
    },
    {
      value: "FIRST_PR" as const,
      label: locale.startsWith("vi") ? "Pull request đầu tiên" : "First pull request",
      icon: "arrow" as const,
      variant: "accent" as const,
    },
  ];

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError(null);
      void getMemberProgress(projectId, member.membership_id, controller.signal)
        .then((data) => {
          if (!cancelled) setProgress(data);
        })
        .catch((err) => {
          if (!cancelled) setError(err instanceof Error ? err.message : t("progressLoadError"));
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
  }, [member.membership_id, projectId, t]);

  useEffect(() => {
    if (highlightTaskId === null) return;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    highlightedRowRef.current?.scrollIntoView({
      block: "center",
      behavior: reducedMotion ? "auto" : "smooth",
    });
  }, [highlightTaskId, progress]);

  return (
    <PmDrawer
      variant="workspace"
      title={t("progressFor", { name: member.display_name })}
      eyebrow={<span className={styles.eyebrow}>{member.email}</span>}
      onClose={onClose}
    >
      {loading ? (
        <p className={tableStyles.emptyNote}>{t("loadingProgress")}</p>
      ) : error ? (
        <p className={styles.error}>{error}</p>
      ) : !progress || progress.plan_id === null ? (
        <p className={tableStyles.emptyNote}>{t("noReleasedPlan")}</p>
      ) : (
        <div className={styles.body}>
          <PmKpiRow
            items={[
              {
                label: t("done"),
                value: `${progress.percent}%`,
                icon: "check-circle",
                variant: progress.percent === 100 ? "success" : "accent",
              },
              {
                label: t("requiredTasks"),
                value: `${progress.completed_count}/${progress.total_count}`,
                icon: "check2",
                variant: "accent",
              },
              {
                label: t("overdueTasks"),
                value: progress.overdue_count,
                icon: "alert",
                variant: progress.overdue_count > 0 ? "warning" : "success",
              },
              {
                label: t("openBlockers"),
                value: progress.blockers.filter((b) => b.status !== "RESOLVED").length,
                icon: "flag",
                variant:
                  progress.blockers.filter((b) => b.status !== "RESOLVED").length > 0
                    ? "warning"
                    : "success",
              },
            ]}
          />

          <section className={styles.section}>
            <h4>{t("tasksInPlan", { count: progress.tasks.length })}</h4>
            {progress.tasks.length === 0 ? (
              <p className={tableStyles.emptyNote}>{t("planHasNoTasks")}</p>
            ) : (
              <div className={styles.stageList}>
                {progressCategories.map((category, categoryIndex) => {
                  const categoryTasks = progress.tasks.filter(
                    (task) => task.category === category.value,
                  );
                  if (categoryTasks.length === 0) return null;
                  const categoryDone = categoryTasks.filter(
                    (task) => task.status === "DONE",
                  ).length;
                  return (
                    <section
                      key={category.value}
                      className={styles.stageCard}
                      data-variant={category.variant}
                    >
                      <header className={styles.stageHead}>
                        <span className={styles.stageNumber}>
                          {String(categoryIndex + 1).padStart(2, "0")}
                        </span>
                        <span className={styles.stageIcon}>
                          <PmIcon name={category.icon} size={17} />
                        </span>
                        <span className={styles.stageCopy}>
                          <b>{"label" in category ? category.label : t(category.labelKey)}</b>
                          <small>
                            {categoryDone}/{categoryTasks.length} {t("done").toLowerCase()}
                          </small>
                        </span>
                        <span className={styles.stageBar}>
                          <i
                            style={{
                              width: `${(categoryDone / categoryTasks.length) * 100}%`,
                            }}
                          />
                        </span>
                      </header>
                      <div className={styles.stageTasks}>
                        {categoryTasks.map((task) => {
                          const meta = TASK_STATUS_META[task.status];
                          const highlighted = task.plan_task_id === highlightTaskId;
                          return (
                            <div
                              key={task.plan_task_id}
                              ref={highlighted ? highlightedRowRef : undefined}
                              className={styles.taskRow}
                              data-highlighted={highlighted ? "true" : undefined}
                            >
                              <span className={styles.taskState} data-status={task.status}>
                                <PmIcon
                                  name={task.status === "DONE" ? "check2" : "doc"}
                                  size={14}
                                />
                              </span>
                              <div className={styles.taskMain}>
                                <span className={styles.taskTitle}>{task.title}</span>
                                <span className={styles.taskMeta}>
                                  {task.mandatory && `${t("required")} · `}
                                  {t("dueDate", { date: formatDateTime(task.due_at, locale) })}
                                </span>
                              </div>
                              <div className={styles.taskBadges}>
                                {task.is_overdue && (
                                  <PmPill variant="critical">{t("overdue")}</PmPill>
                                )}
                                <PmPill variant={meta.variant}>{t(meta.labelKey)}</PmPill>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </section>
                  );
                })}
              </div>
            )}
          </section>

          <section className={styles.section}>
            <h4>{t("reportedBlockers", { count: progress.blockers.length })}</h4>
            {progress.blockers.length === 0 ? (
              <p className={tableStyles.emptyNote}>{t("noReportedBlockers")}</p>
            ) : (
              <div className={styles.taskList}>
                {progress.blockers.map((blocker) => (
                  <div key={blocker.blocker_id} className={styles.taskRow}>
                    <div className={styles.taskMain}>
                      <span className={styles.taskTitle}>{blocker.task_title}</span>
                      <span className={styles.taskMeta}>
                        {blocker.reason} · {formatDateTime(blocker.reported_at, locale)}
                      </span>
                      {blocker.attachments.length > 0 && (
                        <span className={styles.taskMeta}>
                          <PmIcon name="doc" size={11} />{" "}
                          {t("attachmentCount", { count: blocker.attachments.length })}
                        </span>
                      )}
                    </div>
                    <PmPill variant={blocker.status === "RESOLVED" ? "success" : "warning"}>
                      {t(BLOCKER_STATUS_LABEL_KEYS[blocker.status])}
                    </PmPill>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </PmDrawer>
  );
}
