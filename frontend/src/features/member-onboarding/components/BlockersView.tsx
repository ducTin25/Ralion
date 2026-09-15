import { ShallowSearchLink } from "@/components/navigation/ShallowSearchLink";
import { useLocale, useTranslations } from "next-intl";

import {
  BLOCKER_CATEGORY_LABEL_KEYS,
  BLOCKER_STATUS_LABEL_KEYS,
  formatDate,
} from "@/features/member-onboarding/components/memberPortalUi";
import {
  ContentLoading,
  PortalError,
} from "@/features/member-onboarding/components/PortalFeedback";
import type { MemberBlocker } from "@/features/member-onboarding/types";
import { MemberIcon } from "@/features/member-onboarding/components/MemberIcon";

import styles from "./MemberPortal.module.scss";

type BlockersViewProps = {
  blockers: MemberBlocker[];
  loading: boolean;
  error: string | null;
  checklistHref: string;
  hrefForTask: (taskId: number) => string;
  onRetry: () => void;
};

export function BlockersView({
  blockers,
  loading,
  error,
  checklistHref,
  hrefForTask,
  onRetry,
}: BlockersViewProps) {
  const t = useTranslations("member.blockerList");
  const locale = useLocale();

  if (loading) return <ContentLoading label={t("loading")} />;
  if (error) return <PortalError message={error} onRetry={onRetry} />;

  return (
    <div className={styles.contentInner}>
      <section className={styles.pageHeading}>
        <div>
          <h1 className={styles.pageTitleWithIcon}>
            <span>
              <MemberIcon name="flag" size={20} />
            </span>
            {t("title")}
          </h1>
        </div>
      </section>
      {blockers.length === 0 ? (
        <div className={styles.blockerEmpty}>
          <p>{t("empty")}</p>
          <ShallowSearchLink className={styles.secondaryButton} href={checklistHref}>
            {t("backToChecklist")}
          </ShallowSearchLink>
        </div>
      ) : (
        <div className={styles.blockerTableWrap}>
          <table className={styles.blockerTable}>
            <thead>
              <tr>
                <th>{t("relatedTask")}</th>
                <th>{t("reason")}</th>
                <th>{t("type")}</th>
                <th>{t("reported")}</th>
                <th>{t("status")}</th>
              </tr>
            </thead>
            <tbody>
              {blockers.map((blocker) => (
                <tr key={blocker.blocker_id}>
                  <td data-label={t("relatedTask")}>
                    <ShallowSearchLink href={hrefForTask(blocker.plan_task_id)}>
                      {blocker.task_title}
                    </ShallowSearchLink>
                  </td>
                  <td data-label={t("reason")}>{blocker.reason}</td>
                  <td data-label={t("type")}>
                    <span className={styles.neutralTag}>
                      {t(BLOCKER_CATEGORY_LABEL_KEYS[blocker.category])}
                    </span>
                  </td>
                  <td data-label={t("reported")}>{formatDate(blocker.reported_at, locale)}</td>
                  <td data-label={t("status")}>
                    <span
                      className={`${styles.blockerStatus} ${styles[`blocker${blocker.status}`]}`}
                    >
                      {t(BLOCKER_STATUS_LABEL_KEYS[blocker.status])}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
