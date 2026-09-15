import { useTranslations } from "next-intl";

import { ShallowSearchLink } from "@/components/navigation/ShallowSearchLink";
import {
  MemberIcon,
  type MemberIconName,
} from "@/features/member-onboarding/components/MemberIcon";
import { CATEGORY_LABEL_KEYS } from "@/features/member-onboarding/components/memberPortalUi";
import type { MemberChecklist, TaskCategory } from "@/features/member-onboarding/types";

import styles from "./MemberPortal.module.scss";

const ICONS: Record<TaskCategory, MemberIconName> = {
  COMPANY: "building",
  ORIENTATION: "folder",
  ACCESS: "shield",
  SETUP: "settings",
  CODEBASE: "code",
  CONVENTION: "book",
};

export function TaskStagesView({
  checklist,
  hrefForCategory,
}: {
  checklist: MemberChecklist;
  hrefForCategory: (category: TaskCategory) => string;
}) {
  const t = useTranslations("member.tasksView");
  const memberT = useTranslations("member");
  return (
    <div className={styles.taskStagesPage}>
      <header className={styles.plainPageHeader}>
        <h1 className={styles.pageTitleWithIcon}>
          <span>
            <MemberIcon name="check" size={20} />
          </span>
          {t("title")}
        </h1>
        <p>{t("summary")}</p>
      </header>
      <div className={styles.stageList}>
        {checklist.groups.map((group, index) => {
          const done = group.tasks.filter((task) => task.status === "DONE").length;
          return (
            <ShallowSearchLink
              key={group.category}
              href={hrefForCategory(group.category)}
              className={styles.stageRow}
              data-category={group.category.toLowerCase()}
            >
              <span className={styles.stageNumber}>{String(index + 1).padStart(2, "0")}</span>
              <span className={styles.stageIcon}>
                <MemberIcon name={ICONS[group.category]} size={18} />
              </span>
              <span className={styles.stageCopy}>
                <b>{memberT(CATEGORY_LABEL_KEYS[group.category])}</b>
                <small>{t("progress", { done, total: group.tasks.length })}</small>
              </span>
              <span className={styles.stageBar}>
                <i
                  style={{
                    width: `${group.tasks.length ? (done / group.tasks.length) * 100 : 0}%`,
                  }}
                />
              </span>
              <MemberIcon name="chevron" size={17} />
            </ShallowSearchLink>
          );
        })}
      </div>
    </div>
  );
}
