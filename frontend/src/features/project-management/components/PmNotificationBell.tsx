"use client";

import { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { getProjectNotifications } from "@/features/project-management/api";
import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import type { TaskNotificationResponseDTO } from "@/features/project-management/dto/responseDTO/notification.response";
import { formatDateTime } from "@/features/project-management/lib/formatDateTime";
import {
  dismissNotification,
  isNotificationDismissed,
  loadDismissedNotifications,
  NOTIFICATION_DISMISSAL_CHANGED_EVENT,
} from "@/lib/notificationDismissal";
import {
  PROJECT_OPERATION_COMPLETED_EVENT,
  type ProjectOperationCompletedDetail,
} from "@/lib/projectOperationNotifications";

import styles from "./PmShell.module.scss";

const POLL_INTERVAL_MS = 5 * 60_000;
const DISMISSAL_SCOPE = "pm";

type OperationNotification = ProjectOperationCompletedDetail & { id: string };

type PmNotificationBellProps = {
  projectId: number | null;
  currentUserId?: number;
  onCountChange?: (count: number) => void;
};

export function PmNotificationBell({
  projectId,
  currentUserId = 0,
  onCountChange,
}: PmNotificationBellProps) {
  const t = useTranslations("pmUi");
  const locale = useLocale();
  const [taskItems, setTaskItems] = useState<TaskNotificationResponseDTO[]>([]);
  const [operationItems, setOperationItems] = useState<OperationNotification[]>([]);
  const [dismissed, setDismissed] = useState<Set<string>>(() => new Set());
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTaskItems([]);
    setOperationItems([]);
    setOpen(false);
    if (projectId === null) return;

    setDismissed(loadDismissedNotifications(DISMISSAL_SCOPE, currentUserId, projectId));
    let cancelled = false;
    const controller = new AbortController();
    const load = () =>
      getProjectNotifications(projectId, controller.signal)
        .then((data) => {
          if (!cancelled) setTaskItems(data);
        })
        .catch(() => undefined);
    load();
    const timer = window.setInterval(load, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      controller.abort();
      window.clearInterval(timer);
    };
  }, [currentUserId, projectId]);

  useEffect(() => {
    const onOperationCompleted = (event: Event) => {
      const detail = (event as CustomEvent<ProjectOperationCompletedDetail>).detail;
      if (!detail || detail.projectId !== projectId) return;
      const id = `${detail.projectId}:${detail.operation}:${detail.status}:${detail.completedAt}`;
      setOperationItems((current) =>
        current.some((item) => item.id === id) ? current : [{ ...detail, id }, ...current],
      );
    };
    window.addEventListener(PROJECT_OPERATION_COMPLETED_EVENT, onOperationCompleted);
    return () => window.removeEventListener(PROJECT_OPERATION_COMPLETED_EVENT, onOperationCompleted);
  }, [projectId]);

  useEffect(() => {
    if (projectId === null) return;
    const reload = () =>
      setDismissed(loadDismissedNotifications(DISMISSAL_SCOPE, currentUserId, projectId));
    window.addEventListener(NOTIFICATION_DISMISSAL_CHANGED_EVENT, reload);
    return () => window.removeEventListener(NOTIFICATION_DISMISSAL_CHANGED_EVENT, reload);
  }, [currentUserId, projectId]);

  useEffect(() => {
    if (!open) return;
    const onClickOutside = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    };
    const onEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      triggerRef.current?.focus();
    };
    document.addEventListener("mousedown", onClickOutside);
    document.addEventListener("keydown", onEscape);
    return () => {
      document.removeEventListener("mousedown", onClickOutside);
      document.removeEventListener("keydown", onEscape);
    };
  }, [open]);

  const unreadTasks = taskItems.filter(
    (item) => !isNotificationDismissed(dismissed, item.plan_task_id, item.due_at),
  );
  const orderedTasks = [...taskItems].sort(
    (left, right) =>
      Number(isNotificationDismissed(dismissed, left.plan_task_id, left.due_at)) -
      Number(isNotificationDismissed(dismissed, right.plan_task_id, right.due_at)),
  );
  const notificationCount = unreadTasks.length + operationItems.length;
  const hasCritical =
    unreadTasks.some((item) => item.is_overdue) ||
    operationItems.some((item) => item.status === "FAILED");
  useEffect(() => onCountChange?.(notificationCount), [notificationCount, onCountChange]);

  const notificationTitle = (item: OperationNotification) => {
    const success = item.status === "SUCCEEDED";
    switch (item.operation) {
      case "DOCUMENT_UPLOAD":
        return success
          ? t("operationDocumentUploadSucceeded", { title: item.title || t("document") })
          : t("operationDocumentUploadFailed", { title: item.title || t("document") });
      case "REPOSITORY_IMPORT":
        return success
          ? t("operationRepositoryImportSucceeded", { count: item.documentsImported ?? 0 })
          : t("operationRepositoryImportFailed");
      case "GITHUB_SYNC":
        return success
          ? t("operationGithubSyncSucceeded", {
              repo: item.repo || t("repository"),
              count: item.documentsImported ?? 0,
            })
          : t("operationGithubSyncFailed");
      case "CONVENTION_DISCOVERY":
        return success
          ? t("operationConventionDiscoverySucceeded", {
              created: item.familiesCreated ?? 0,
              updated: item.familiesUpdated ?? 0,
            })
          : t("operationConventionDiscoveryFailed");
    }
  };

  return (
    <div className={styles.bellRoot} ref={rootRef}>
      <button
        ref={triggerRef}
        type="button"
        className={styles.bellBtn}
        disabled={projectId === null}
        aria-label={
          notificationCount > 0
            ? t("notificationCount", { count: notificationCount })
            : t("notifications")
        }
        title={t("notifications")}
        onClick={() => setOpen((value) => !value)}
      >
        <PmIcon name="bell" size={16} />
        {notificationCount > 0 && (
          <span className={styles.bellBadge} data-critical={hasCritical ? "true" : undefined}>
            {notificationCount > 9 ? "9+" : notificationCount}
          </span>
        )}
      </button>
      {open && (
        <div className={styles.bellDropdown} role="menu">
          <header>{t("notifications")}</header>
          {operationItems.length === 0 && orderedTasks.length === 0 ? (
            <p className={styles.bellEmpty}>{t("noNotifications")}</p>
          ) : (
            <ul>
              {operationItems.map((item) => (
                <li key={item.id} data-overdue={item.status === "FAILED" ? "true" : undefined}>
                  <button
                    type="button"
                    className={styles.bellItemLink}
                    onClick={() =>
                      setOperationItems((current) =>
                        current.filter((entry) => entry.id !== item.id),
                      )
                    }
                  >
                    <span className={styles.bellItemTitle}>{notificationTitle(item)}</span>
                    <span className={styles.bellItemMeta}>
                      {item.status === "FAILED"
                        ? item.errorSummary || t("operationRetryHint")
                        : formatDateTime(
                            item.completedAt,
                            undefined,
                            locale === "vi" ? "vi-VN" : "en-US",
                          )}
                    </span>
                  </button>
                </li>
              ))}
              {orderedTasks.map((item) => {
                const isRead = isNotificationDismissed(
                  dismissed,
                  item.plan_task_id,
                  item.due_at,
                );
                return (
                <li
                  key={`${item.plan_task_id}:${item.due_at}`}
                  data-overdue={item.is_overdue || undefined}
                  data-read={isRead || undefined}
                >
                  <button
                    type="button"
                    className={styles.bellItemLink}
                    onClick={() =>
                      setDismissed(
                        dismissNotification(
                          DISMISSAL_SCOPE,
                          currentUserId,
                          projectId!,
                          item.plan_task_id,
                          item.due_at,
                        ),
                      )
                    }
                  >
                    <span className={styles.bellItemTitle}>
                      {!isRead && <i className={styles.bellUnreadDot} aria-hidden="true" />}
                      {item.title}
                    </span>
                    <span className={styles.bellItemMeta}>
                      {formatDateTime(item.due_at, undefined, locale === "vi" ? "vi-VN" : "en-US")}
                      <em>{isRead ? (locale === "vi" ? "Đã xem" : "Read") : (locale === "vi" ? "Chưa xem" : "Unread")}</em>
                    </span>
                  </button>
                </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
