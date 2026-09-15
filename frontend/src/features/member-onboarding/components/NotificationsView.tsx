import { useLocale, useTranslations } from "next-intl";

import { ShallowSearchLink } from "@/components/navigation/ShallowSearchLink";
import type { TaskNotification } from "@/features/member-onboarding/types";

import { MemberIcon } from "./MemberIcon";
import styles from "./MemberPortal.module.scss";

type NotificationsViewProps = {
  notifications: TaskNotification[];
  readIds: number[];
  hrefForTask: (id: number) => string;
  onMarkRead: (id: number) => void;
  onMarkAllRead: () => void;
};

export function NotificationsView({
  notifications,
  readIds,
  hrefForTask,
  onMarkRead,
  onMarkAllRead,
}: NotificationsViewProps) {
  const t = useTranslations("member.notificationsView");
  const locale = useLocale();
  const unreadCount = notifications.filter((item) => !readIds.includes(item.plan_task_id)).length;
  const sortedNotifications = [...notifications].sort(
    (left, right) =>
      Number(readIds.includes(left.plan_task_id)) - Number(readIds.includes(right.plan_task_id)),
  );
  const dueLabel = (value: string) =>
    new Intl.DateTimeFormat(locale === "vi" ? "vi-VN" : "en-US", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));

  return (
    <div className={styles.notificationsPage}>
      <header className={styles.plainPageHeader}>
        <div>
          <h1 className={styles.pageTitleWithIcon}>
            <span>
              <MemberIcon name="bell" size={20} />
            </span>
            {t("title")}
          </h1>
          <p>{t("summary")}</p>
        </div>
        <div className={styles.notificationHeaderActions}>
          <span>
            {locale.startsWith("vi") ? `${unreadCount} chưa xem` : `${unreadCount} unread`}
          </span>
          {unreadCount > 0 && (
            <button type="button" onClick={onMarkAllRead}>
              <MemberIcon name="check" size={14} />
              {locale.startsWith("vi") ? "Đánh dấu tất cả đã xem" : "Mark all as read"}
            </button>
          )}
        </div>
      </header>

      <section className={styles.notificationList}>
        {sortedNotifications.map((item) => {
          const isRead = readIds.includes(item.plan_task_id);
          return (
            <ShallowSearchLink
              key={item.plan_task_id}
              href={hrefForTask(item.plan_task_id)}
              data-overdue={item.is_overdue || undefined}
              data-read={isRead || undefined}
              onClick={() => onMarkRead(item.plan_task_id)}
            >
              <span>
                <MemberIcon name={item.is_overdue ? "bell" : "clock"} size={17} />
              </span>
              <span>
                <b>
                  {!isRead && <i aria-hidden="true" />}
                  {item.title}
                </b>
                <small>
                  {item.is_overdue ? t("overdue") : t("dueSoon")} · {dueLabel(item.due_at)}
                </small>
              </span>
              <em>
                {isRead
                  ? locale.startsWith("vi")
                    ? "Đã xem"
                    : "Read"
                  : locale.startsWith("vi")
                    ? "Chưa xem"
                    : "Unread"}
              </em>
              <MemberIcon name="chevron" size={17} />
            </ShallowSearchLink>
          );
        })}
        {!notifications.length && <p className={styles.overviewEmpty}>{t("empty")}</p>}
      </section>
    </div>
  );
}
