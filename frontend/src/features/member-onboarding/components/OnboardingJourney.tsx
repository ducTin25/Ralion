"use client";

import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";

import { ShallowSearchLink } from "@/components/navigation/ShallowSearchLink";
import {
  MemberIcon,
  type MemberIconName,
} from "@/features/member-onboarding/components/MemberIcon";
import {
  CATEGORY_LABEL_KEYS,
  STATUS_LABEL_KEYS,
} from "@/features/member-onboarding/components/memberPortalUi";
import type { MemberChecklist, TaskCategory } from "@/features/member-onboarding/types";

import styles from "./MemberPortal.module.scss";

const CATEGORY_ICONS: Record<TaskCategory, MemberIconName> = {
  COMPANY: "building",
  ORIENTATION: "folder",
  ACCESS: "shield",
  SETUP: "settings",
  CODEBASE: "code",
  CONVENTION: "book",
};

type OnboardingJourneyProps = {
  checklist: MemberChecklist;
  activeTaskId: number | null;
  activeCategory?: TaskCategory | null;
  hrefForTask: (taskId: number) => string;
};

export function OnboardingJourney({
  checklist,
  activeTaskId,
  activeCategory = null,
  hrefForTask,
}: OnboardingJourneyProps) {
  const t = useTranslations("member.journey");
  const memberT = useTranslations("member");

  const content = (
    <>
      <div className={styles.journeyProgress}>
        <div
          className={styles.journeyRing}
          style={
            { "--journey-progress": `${checklist.progress.percent * 3.6}deg` } as CSSProperties
          }
          aria-hidden="true"
        >
          <span>{checklist.progress.percent}%</span>
        </div>
        <div>
          <b>{t("progressTitle")}</b>
          <span>
            {t("progressSummary", {
              completed: checklist.progress.completed,
              total: checklist.progress.total,
            })}
          </span>
        </div>
      </div>

      <div className={styles.journeyGroups}>
        {checklist.groups.map((group, groupIndex) => {
          const completed = group.tasks.filter((task) => task.status === "DONE").length;
          const containsActive = group.tasks.some((task) => task.plan_task_id === activeTaskId);
          const isActiveGroup = group.category === activeCategory || containsActive;
          return (
            <details
              key={group.category}
              className={styles.journeyGroup}
              data-active={isActiveGroup || undefined}
              data-category={group.category.toLowerCase()}
              open={
                isActiveGroup ||
                (activeTaskId === null && activeCategory === null && groupIndex === 0)
              }
            >
              <summary>
                <span className={styles.journeyCategoryIcon}>
                  <MemberIcon name={CATEGORY_ICONS[group.category]} size={16} />
                </span>
                <span className={styles.journeyCategoryCopy}>
                  <b>{memberT(CATEGORY_LABEL_KEYS[group.category])}</b>
                  <small>{t("groupProgress", { completed, total: group.tasks.length })}</small>
                </span>
                <MemberIcon name="chevron" size={15} />
              </summary>
              <div className={styles.journeyTasks}>
                {group.tasks.map((task) => (
                  <ShallowSearchLink
                    key={task.plan_task_id}
                    href={hrefForTask(task.plan_task_id)}
                    className={task.plan_task_id === activeTaskId ? styles.journeyTaskActive : ""}
                    aria-current={task.plan_task_id === activeTaskId ? "page" : undefined}
                    aria-label={t("openTask", { order: task.display_order })}
                    title={task.title}
                    data-status={task.status.toLowerCase()}
                    data-overdue={task.is_overdue && task.status !== "DONE" ? "true" : undefined}
                    data-due-soon={task.is_due_soon && task.status !== "DONE" ? "true" : undefined}
                  >
                    <span
                      className={`${styles.journeyTaskState} ${styles[`task${task.status}`]}`}
                      aria-hidden="true"
                    >
                      {task.status === "DONE" ? (
                        <MemberIcon name="check" size={12} />
                      ) : task.is_locked ? (
                        <MemberIcon name="lock" size={11} />
                      ) : (
                        task.display_order
                      )}
                    </span>
                    <span>
                      <b>{task.title}</b>
                      <small>
                        {task.is_overdue && task.status !== "DONE"
                          ? memberT("overdue")
                          : task.is_due_soon && task.status !== "DONE"
                            ? memberT("dueSoon")
                            : memberT(STATUS_LABEL_KEYS[task.status])}{" "}
                        · {task.estimated_minutes} phút
                      </small>
                    </span>
                  </ShallowSearchLink>
                ))}
              </div>
            </details>
          );
        })}
      </div>
    </>
  );

  return (
    <aside className={styles.journeyPanel} aria-label={t("title")}>
      <div className={styles.journeyDesktopHeader}>
        <h2>{t("title")}</h2>
        <p>{checklist.project.name}</p>
      </div>
      <details className={styles.journeyDisclosure} open>
        <summary>
          <span>
            <MemberIcon name="check" size={17} />
            <b>{t("title")}</b>
          </span>
          <small>{checklist.progress.percent}%</small>
          <MemberIcon name="chevron" size={15} />
        </summary>
        <div className={styles.journeyBody}>{content}</div>
      </details>
    </aside>
  );
}
