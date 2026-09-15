"use client";

import { useEffect, useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { getProjectNotifications } from "@/features/project-management/api";
import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import type { TaskNotificationResponseDTO } from "@/features/project-management/dto/responseDTO/notification.response";
import { formatDateTime } from "@/features/project-management/lib/formatDateTime";
import {
  dismissNotification,
  isNotificationDismissed,
  loadDismissedNotifications,
} from "@/lib/notificationDismissal";

import styles from "./PmNotificationsView.module.scss";

const SCOPE = "pm";

export function PmNotificationsView({
  projectId,
  currentUserId,
}: {
  projectId: number;
  currentUserId: number;
}) {
  const t = useTranslations("pmUi");
  const locale = useLocale();
  const isVi = locale === "vi";
  const [items, setItems] = useState<TaskNotificationResponseDTO[]>([]);
  const [dismissed, setDismissed] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    const hydrate = window.setTimeout(
      () => setDismissed(loadDismissedNotifications(SCOPE, currentUserId, projectId)),
      0,
    );
    const controller = new AbortController();
    getProjectNotifications(projectId, controller.signal).then(setItems).catch(() => setItems([]));
    return () => {
      window.clearTimeout(hydrate);
      controller.abort();
    };
  }, [currentUserId, projectId]);

  const ordered = useMemo(
    () =>
      [...items].sort((a, b) => {
        const aRead = isNotificationDismissed(dismissed, a.plan_task_id, a.due_at);
        const bRead = isNotificationDismissed(dismissed, b.plan_task_id, b.due_at);
        return Number(aRead) - Number(bRead);
      }),
    [dismissed, items],
  );
  const unread = ordered.filter(
    (item) => !isNotificationDismissed(dismissed, item.plan_task_id, item.due_at),
  );

  const markRead = (item: TaskNotificationResponseDTO) =>
    setDismissed(
      dismissNotification(SCOPE, currentUserId, projectId, item.plan_task_id, item.due_at),
    );
  const markAllRead = () => {
    let next = dismissed;
    unread.forEach((item) => {
      next = dismissNotification(SCOPE, currentUserId, projectId, item.plan_task_id, item.due_at);
    });
    setDismissed(new Set(next));
  };

  return (
    <section className={styles.page}>
      <header className={styles.pageHeader}>
        <div className={styles.heading}>
          <span className={styles.headingIcon}><PmIcon name="bell" size={23} /></span>
          <div>
            <h1>{t("notifications")}</h1>
            <p>{isVi ? "Các nhiệm vụ sắp đến hạn hoặc cần bạn xử lý." : "Tasks that are due soon or need your attention."}</p>
          </div>
        </div>
        <div className={styles.headerActions}>
          <span className={styles.unreadCount}>{unread.length} {isVi ? "chưa xem" : "unread"}</span>
          <button type="button" onClick={markAllRead} disabled={unread.length === 0}>
            <PmIcon name="check2" size={16} />
            {isVi ? "Đánh dấu tất cả đã xem" : "Mark all as read"}
          </button>
        </div>
      </header>

      <div className={styles.list}>
        {ordered.length === 0 ? (
          <div className={styles.empty}><PmIcon name="check-circle" size={25} />{isVi ? "Không có thông báo cần xử lý." : "No notifications need your attention."}</div>
        ) : ordered.map((item) => {
          const read = isNotificationDismissed(dismissed, item.plan_task_id, item.due_at);
          const href = item.membership_id === null
            ? null
            : `/product-manager?project=${projectId}&view=members&membershipId=${item.membership_id}&taskId=${item.plan_task_id}`;
          const content = (
            <>
              <span className={styles.rowIcon}><PmIcon name="bell" size={19} /></span>
              <span className={styles.rowBody}>
                <strong>{!read && <i aria-hidden="true" />}{item.title}</strong>
                <small>{item.engineer_name ? `${item.engineer_name} · ` : ""}{item.is_overdue ? t("overdue") : t("dueSoon")} · {formatDateTime(item.due_at, undefined, isVi ? "vi-VN" : "en-US")}</small>
              </span>
              <span className={styles.status}>{read ? (isVi ? "Đã xem" : "Read") : (isVi ? "Chưa xem" : "Unread")}</span>
              <PmIcon name="arrow" size={17} />
            </>
          );
          return href ? (
            <Link key={item.plan_task_id} href={href} className={styles.row} data-read={read} onClick={() => markRead(item)}>{content}</Link>
          ) : (
            <button key={item.plan_task_id} type="button" className={styles.row} data-read={read} onClick={() => markRead(item)}>{content}</button>
          );
        })}
      </div>
    </section>
  );
}
