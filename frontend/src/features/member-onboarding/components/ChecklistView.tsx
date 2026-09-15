import { ShallowSearchLink } from "@/components/navigation/ShallowSearchLink";
import { useLocale, useTranslations } from "next-intl";

import {
  MemberIcon,
  type MemberIconName,
} from "@/features/member-onboarding/components/MemberIcon";
import {
  CATEGORY_LABEL_KEYS,
  formatDate,
  STATUS_LABEL_KEYS,
} from "@/features/member-onboarding/components/memberPortalUi";
import {
  ContentLoading,
  PortalError,
} from "@/features/member-onboarding/components/PortalFeedback";
import type {
  MemberChecklist,
  MemberProfile,
  MemberTaskGroup,
  TaskCategory,
} from "@/features/member-onboarding/types";

import styles from "./MemberPortal.module.scss";

const CATEGORY_ICONS: Record<TaskCategory, MemberIconName> = {
  COMPANY: "building",
  ORIENTATION: "folder",
  ACCESS: "shield",
  SETUP: "settings",
  CODEBASE: "code",
  CONVENTION: "book",
};

type ChecklistViewProps = {
  member: MemberProfile;
  checklist: MemberChecklist | null;
  filteredGroups: MemberTaskGroup[];
  search: string;
  loading: boolean;
  error: string | null;
  hrefForTask: (taskId: number) => string;
  onRetry: () => void;
};

export function ChecklistView({
  member,
  checklist,
  filteredGroups,
  search,
  loading,
  error,
  hrefForTask,
  onRetry,
}: ChecklistViewProps) {
  const t = useTranslations("member.checklistView");
  const memberT = useTranslations("member");
  const locale = useLocale();

  if (loading) return <ContentLoading label={t("loading")} />;
  if (error) return <PortalError message={error} onRetry={onRetry} />;
  if (!checklist) return <PortalError message={t("noData")} />;

  const planStatusLabel =
    checklist.plan_status === "ONBOARDING_CLOSED" ? t("planClosed") : t("planInProgress");
  const allTasks = checklist.groups.flatMap((group) => group.tasks);
  const nextTask =
    allTasks.find((task) => task.status === "IN_PROGRESS" && !task.is_locked) ??
    allTasks.find((task) => task.status === "NOT_STARTED" && !task.is_locked);

  return (
    <div className={styles.contentInner}>
      <section className={styles.pageHeading}>
        <div>
          <h1>{t("hello", { name: member.display_name })}</h1>
          <p>
            {t("summary", { status: planStatusLabel, project: checklist.project.name })}
            {checklist.approved_at && (
              <> · {t("released", { date: formatDate(checklist.approved_at, locale) ?? "—" })}</>
            )}
          </p>
        </div>
      </section>

      <section
        className={styles.memberKpis}
        aria-label={t("progressAria", { percent: checklist.progress.percent })}
      >
        <span className={styles.srOnly}>
          {t("progressText", {
            completed: checklist.progress.completed,
            total: checklist.progress.total,
            percent: checklist.progress.percent,
          })}
        </span>
        <article className={styles.progressCard}>
          <div>
            <h2>{t("requiredProgress")}</h2>
            <b>{checklist.progress.percent}%</b>
          </div>
          <div className={styles.progressTrack}>
            <span style={{ transform: `scaleX(${checklist.progress.percent / 100})` }} />
          </div>
          <small>
            {t("requiredDone", {
              completed: checklist.progress.completed,
              total: checklist.progress.total,
            })}
          </small>
        </article>
      </section>

      {nextTask && (
        <ShallowSearchLink
          href={hrefForTask(nextTask.plan_task_id)}
          className={styles.nextTaskCard}
          aria-label={nextTask.status === "IN_PROGRESS" ? t("continueTask") : t("openTask")}
        >
          <span className={styles.nextTaskIcon}>
            <MemberIcon name={nextTask.status === "IN_PROGRESS" ? "arrow" : "check"} size={18} />
          </span>
          <span className={styles.nextTaskCopy}>
            <b>{nextTask.title}</b>
            <span>
              <MemberIcon name="clock" size={14} />
              {t("minutes", { count: nextTask.estimated_minutes })}
            </span>
          </span>
          <span className={styles.nextTaskButton}>
            {nextTask.status === "IN_PROGRESS" ? t("continueTask") : t("openTask")}
            <MemberIcon name="chevron" size={16} />
          </span>
        </ShallowSearchLink>
      )}

      <div className={styles.groups}>
        {filteredGroups.map((group) => (
          <section key={group.category} className={styles.taskGroup}>
            <header>
              <span>
                <MemberIcon name={CATEGORY_ICONS[group.category]} size={17} />
              </span>
              <h2>{memberT(CATEGORY_LABEL_KEYS[group.category])}</h2>
              <small>
                {t("taskCount", {
                  count:
                    checklist.groups.find((item) => item.category === group.category)?.tasks
                      .length ?? group.tasks.length,
                })}
              </small>
            </header>
            <div className={styles.taskList}>
              {group.tasks.map((task) => (
                <ShallowSearchLink
                  key={task.plan_task_id}
                  href={hrefForTask(task.plan_task_id)}
                  className={styles.taskRow}
                >
                  <span className={`${styles.taskStatusIcon} ${styles[`task${task.status}`]}`}>
                    {task.status === "DONE" ? (
                      <MemberIcon name="check" size={15} />
                    ) : task.is_locked ? (
                      <MemberIcon name="lock" size={14} />
                    ) : (
                      <span />
                    )}
                  </span>
                  <span className={styles.taskText}>
                    <b>{task.title}</b>
                    <small>
                      {memberT(STATUS_LABEL_KEYS[task.status])}
                      {!task.mandatory && <i>{t("optional")}</i>}
                      {task.open_blocker_count > 0 && (
                        <i className={styles.blockerTag}>
                          {t("blockerCount", { count: task.open_blocker_count })}
                        </i>
                      )}
                      {task.is_locked && task.lock_reason && (
                        <i className={styles.lockText}>{task.lock_reason}</i>
                      )}
                    </small>
                  </span>
                  <span className={styles.taskMeta}>
                    {task.mandatory && <i>{t("required")}</i>}
                    {task.source_count > 0 && (
                      <span>{t("sourceCount", { count: task.source_count })}</span>
                    )}
                    <MemberIcon name="clock" size={14} />
                    {t("minutes", { count: task.estimated_minutes })}
                    {task.due_at && (
                      <span>{t("due", { date: formatDate(task.due_at, locale) ?? "—" })}</span>
                    )}
                  </span>
                  <MemberIcon name="chevron" size={16} />
                </ShallowSearchLink>
              ))}
            </div>
          </section>
        ))}
        {filteredGroups.length === 0 && (
          <div className={styles.noResults}>{t("noResults", { search })}</div>
        )}
      </div>
    </div>
  );
}
