import { useLocale, useTranslations } from "next-intl";

import { ShallowSearchLink } from "@/components/navigation/ShallowSearchLink";
import { MemberIcon } from "@/features/member-onboarding/components/MemberIcon";
import type {
  MemberChecklist,
  MemberProfile,
  TaskNotification,
} from "@/features/member-onboarding/types";

import styles from "./MemberPortal.module.scss";

type EngineerOverviewProps = {
  member: MemberProfile;
  checklist: MemberChecklist;
  notifications: TaskNotification[];
  tasksHref: string;
  notificationsHref: string;
  hrefForTask: (taskId: number) => string;
};

export function EngineerOverview({
  member,
  checklist,
  notifications,
  tasksHref,
  notificationsHref,
  hrefForTask,
}: EngineerOverviewProps) {
  const t = useTranslations("member.overviewView");
  const locale = useLocale();
  const tasks = checklist.groups.flatMap((group) => group.tasks);
  const inProgress = tasks.filter((task) => task.status === "IN_PROGRESS");
  const overdue = tasks.filter((task) => task.is_overdue && task.status !== "DONE");
  const blocked = tasks.filter((task) => task.open_blocker_count > 0 || task.status === "BLOCKED");
  const nextTask =
    inProgress[0] ?? tasks.find((task) => task.status === "NOT_STARTED" && !task.is_locked);
  const remainingTasks = Math.max(checklist.progress.total - checklist.progress.completed, 0);
  const categoryLabels = locale.startsWith("vi")
    ? {
        COMPANY: "Tìm hiểu công ty",
        ORIENTATION: "Tổng quan dự án",
        ACCESS: "Quyền truy cập và bảo mật",
        SETUP: "Thiết lập môi trường",
        CODEBASE: "Tìm hiểu codebase",
        CONVENTION: "Quy ước dự án",
      }
    : {
        COMPANY: "Company introduction",
        ORIENTATION: "Project overview",
        ACCESS: "Access and security",
        SETUP: "Environment setup",
        CODEBASE: "Codebase introduction",
        CONVENTION: "Project conventions",
      };

  const metrics = [
    { icon: "check" as const, value: checklist.progress.completed, label: t("completed") },
    { icon: "clock" as const, value: inProgress.length, label: t("inProgress") },
    { icon: "bell" as const, value: overdue.length, label: t("overdue") },
    { icon: "flag" as const, value: blocked.length, label: t("blocked") },
  ];

  return (
    <div className={styles.engineerOverview}>
      <header className={styles.overviewHeader}>
        <div>
          <h1 className={styles.pageTitleWithIcon}>
            <span>
              <MemberIcon name="dashboard" size={20} />
            </span>
            {t("hello", { name: member.display_name })}
          </h1>
          <p>{t("summary", { project: checklist.project.name })}</p>
        </div>
        <div
          className={styles.overviewProgress}
          aria-label={t("progress", { percent: checklist.progress.percent })}
        >
          <b>{checklist.progress.percent}%</b>
          <span>{t("progressLabel")}</span>
        </div>
      </header>

      <section className={styles.overviewMetrics} aria-label={t("metrics")}>
        {metrics.map((metric) => (
          <article key={metric.label}>
            <span>
              <MemberIcon name={metric.icon} size={17} />
            </span>
            <b>{metric.value}</b>
            <small>{metric.label}</small>
          </article>
        ))}
      </section>

      <div className={styles.overviewGrid}>
        <section className={styles.overviewMainCard}>
          <header>
            <div>
              <h2>{t("continueTitle")}</h2>
            </div>
            <ShallowSearchLink href={tasksHref}>{t("viewAll")}</ShallowSearchLink>
          </header>
          {nextTask ? (
            <ShallowSearchLink
              href={hrefForTask(nextTask.plan_task_id)}
              className={styles.overviewNextTask}
            >
              <span className={styles.overviewTaskState}>
                <MemberIcon name="arrow" size={17} />
              </span>
              <span>
                <b>{nextTask.title}</b>
                <small>{t("taskMeta", { minutes: nextTask.estimated_minutes })}</small>
              </span>
              <MemberIcon name="chevron" size={17} />
            </ShallowSearchLink>
          ) : (
            <p className={styles.overviewEmpty}>{t("allDone")}</p>
          )}
          <div className={styles.overviewJourneySummary}>
            <div className={styles.overviewJourneyHeading}>
              <span>{locale.startsWith("vi") ? "Tiến độ lộ trình" : "Journey progress"}</span>
              <b>
                {checklist.progress.completed}/{checklist.progress.total}
              </b>
            </div>
            <div
              className={styles.overviewJourneyTrack}
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={checklist.progress.percent}
            >
              <i style={{ width: `${checklist.progress.percent}%` }} />
            </div>
            <div className={styles.overviewJourneyMeta}>
              <span>
                <MemberIcon name="folder" size={15} />
                <small>{locale.startsWith("vi") ? "Giai đoạn hiện tại" : "Current stage"}</small>
                <b>{nextTask ? categoryLabels[nextTask.category] : t("allDone")}</b>
              </span>
              <span>
                <MemberIcon name="check" size={15} />
                <small>{locale.startsWith("vi") ? "Còn lại" : "Remaining"}</small>
                <b>
                  {locale.startsWith("vi")
                    ? `${remainingTasks} nhiệm vụ`
                    : `${remainingTasks} tasks`}
                </b>
              </span>
            </div>
          </div>
        </section>

        <section className={styles.overviewSideCard}>
          <header>
            <h2>{t("notifications")}</h2>
            <ShallowSearchLink href={notificationsHref}>{t("viewAll")}</ShallowSearchLink>
          </header>
          <div className={styles.overviewNoticeList}>
            {notifications.slice(0, 3).map((item) => (
              <ShallowSearchLink key={item.plan_task_id} href={hrefForTask(item.plan_task_id)}>
                <MemberIcon name={item.is_overdue ? "bell" : "clock"} size={15} />
                <span>
                  <b>{item.title}</b>
                  <small>{item.is_overdue ? t("overdue") : t("dueSoon")}</small>
                </span>
              </ShallowSearchLink>
            ))}
            {notifications.length === 0 && (
              <p className={styles.overviewEmpty}>{t("noNotifications")}</p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
