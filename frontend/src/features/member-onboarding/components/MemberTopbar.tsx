import { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { LanguageSwitcher } from "@/components/i18n/LanguageSwitcher";
import { MobileNavDrawer } from "@/components/navigation/MobileNavDrawer";
import { MemberIcon } from "@/features/member-onboarding/components/MemberIcon";
import type { MemberProject, TaskNotification } from "@/features/member-onboarding/types";
import type { MemberPortalView } from "@/features/member-onboarding/hooks/useMemberPortalUrl";
import type { MemberTheme } from "@/features/member-onboarding/hooks/usePersistentTheme";
import { ShallowSearchLink } from "@/components/navigation/ShallowSearchLink";

import styles from "./MemberPortal.module.scss";

type MemberTopbarProps = {
  activeView: MemberPortalView;
  projectName: string;
  projects: MemberProject[];
  selectedProjectId: number;
  search: string;
  theme: MemberTheme;
  notifications: TaskNotification[];
  readNotificationIds: number[];
  onMarkNotificationRead: (taskId: number) => void;
  onMarkAllNotificationsRead: () => void;
  onSearch: (value: string) => void;
  onSelectProject: (projectId: number) => void;
  onToggleTheme: () => void;
  onNewConversation: () => void;
  switchProjectHref: string;
  checklistHref: string;
  overviewHref?: string;
  hrefForTask: (taskId: number) => string;
  blockersHref: string;
  conventionsHref: string;
  chatHref: string;
  policyHref: string;
  onSignOut: () => void;
};

function NotificationBell({
  notifications,
  hrefForTask,
  readIds,
  onMarkRead,
  onMarkAllRead,
}: {
  notifications: TaskNotification[];
  hrefForTask: (taskId: number) => string;
  readIds: number[];
  onMarkRead: (taskId: number) => void;
  onMarkAllRead: () => void;
}) {
  const t = useTranslations("member");
  const locale = useLocale();
  const unreadCount = notifications.filter(
    (item) => !readIds.includes(item.plan_task_id),
  ).length;
  const overdueCount = notifications.filter(
    (item) => item.is_overdue && !readIds.includes(item.plan_task_id),
  ).length;
  const sortedNotifications = [...notifications].sort(
    (left, right) =>
      Number(readIds.includes(left.plan_task_id)) - Number(readIds.includes(right.plan_task_id)),
  );
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

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

  return (
    <div className={styles.bellRoot} ref={rootRef}>
      <button
        ref={triggerRef}
        type="button"
        className={styles.topbarIconButton}
        aria-label={
          unreadCount > 0
            ? t("notificationCount", { count: unreadCount })
            : t("notifications")
        }
        title={t("notifications")}
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => setOpen((value) => !value)}
      >
        <MemberIcon name="bell" size={16} />
        {unreadCount > 0 && (
          <span className={styles.bellBadge} data-critical={overdueCount > 0 ? "true" : undefined}>
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>
      {open && (
        <div className={styles.bellDropdown} role="menu">
          <header className={styles.bellDropdownHeader}>
            <span>{t("notifications")}</span>
            {unreadCount > 0 && (
              <button type="button" onClick={onMarkAllRead}>
                {locale === "vi" ? "Đánh dấu tất cả đã xem" : "Mark all as read"}
              </button>
            )}
          </header>
          {notifications.length === 0 ? (
            <p className={styles.bellEmpty}>—</p>
          ) : (
            <ul>
              {sortedNotifications.map((item) => {
                const isRead = readIds.includes(item.plan_task_id);
                return (
                <li
                  key={`${item.plan_task_id}:${item.due_at}`}
                  data-overdue={item.is_overdue || undefined}
                  data-read={isRead || undefined}
                >
                  <ShallowSearchLink
                    href={hrefForTask(item.plan_task_id)}
                    className={styles.bellItemLink}
                    onClick={() => {
                      onMarkRead(item.plan_task_id);
                      setOpen(false);
                    }}
                  >
                    <span className={styles.bellItemTitle}>
                      {!isRead && <i className={styles.unreadDot} aria-hidden="true" />}
                      {item.title}
                    </span>
                    <span className={styles.bellItemMeta}>
                      {new Date(item.due_at).toLocaleString(locale === "vi" ? "vi-VN" : "en-US")}
                      <em>
                        {isRead
                          ? locale === "vi" ? "Đã xem" : "Read"
                          : locale === "vi" ? "Chưa xem" : "Unread"}
                      </em>
                    </span>
                  </ShallowSearchLink>
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

export function MemberTopbar({
  activeView,
  projectName,
  projects,
  selectedProjectId,
  search,
  theme,
  notifications,
  readNotificationIds,
  onMarkNotificationRead,
  onMarkAllNotificationsRead,
  onSearch,
  onSelectProject,
  onToggleTheme,
  onNewConversation,
  switchProjectHref,
  checklistHref,
  overviewHref = checklistHref,
  hrefForTask,
  blockersHref,
  conventionsHref,
  chatHref,
  policyHref,
  onSignOut,
}: MemberTopbarProps) {
  const t = useTranslations("member");
  const chatT = useTranslations("chat");
  const common = useTranslations("common");
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  return (
    <>
      <header className={styles.topbar}>
        <button
          aria-label={common("openMenu")}
          className={styles.mobileMenuButton}
          onClick={() => setMobileNavOpen(true)}
          type="button"
        >
          <span aria-hidden="true">☰</span>
        </button>
        <div className={styles.crumb}>
          <b>
            {activeView === "overview"
              ? t("overview")
              : activeView === "tasks"
                ? t("tasks")
                : activeView === "notifications"
                  ? t("notifications")
                  : activeView === "chat"
                    ? t("chat")
                    : activeView === "policy"
                      ? t("policy.title")
                      : activeView === "conventions"
                        ? t("conventions")
                        : t("blockers")}
          </b>
          <span>·</span>
          <span>{projectName}</span>
        </div>
        {activeView === "tasks" ? (
          <label className={styles.searchBox}>
            <MemberIcon name="search" size={15} />
            <span className={styles.srOnly}>{t("searchTask")}</span>
            <input
              value={search}
              onChange={(event) => onSearch(event.target.value)}
              placeholder={t("searchPlaceholder")}
            />
          </label>
        ) : (
          <div className={styles.topbarSpacer} />
        )}
        <div className={styles.topbarActions}>
          {activeView === "chat" && (
            <button
              type="button"
              className={styles.newConversationAction}
              onClick={onNewConversation}
            >
              <MemberIcon name="refresh" size={15} />
              <span>{chatT("newConversation")}</span>
            </button>
          )}
          {projects.length > 1 ? (
            <label className={styles.projectSelect}>
              <MemberIcon name="folder" size={16} />
              <span className={styles.srOnly}>{t("switchProject")}</span>
              <select
                aria-label={t("switchProject")}
                value={selectedProjectId}
                onChange={(event) => onSelectProject(Number(event.target.value))}
              >
                {projects.map((project) => (
                  <option key={project.project_id} value={project.project_id}>
                    {project.name}
                  </option>
                ))}
              </select>
              <MemberIcon name="chevronDown" size={14} />
            </label>
          ) : projects.length === 1 ? (
            <ShallowSearchLink
              href={switchProjectHref}
              className={styles.projectSelect}
              aria-label={t("switchProject")}
            >
              <MemberIcon name="folder" size={16} />
              <b>{projects[0].name}</b>
              <MemberIcon name="chevron" size={14} />
            </ShallowSearchLink>
          ) : null}
          <LanguageSwitcher className={styles.topbarLanguage} compact />
          <span aria-hidden="true" className={styles.topbarDivider} />
          <button
            type="button"
            className={styles.topbarIconButton}
            aria-label={t("theme")}
            title={t("theme")}
            onClick={onToggleTheme}
          >
            <MemberIcon name={theme === "dark" ? "sun" : "moon"} size={16} />
          </button>
          <NotificationBell
            notifications={notifications}
            hrefForTask={hrefForTask}
            readIds={readNotificationIds}
            onMarkRead={onMarkNotificationRead}
            onMarkAllRead={onMarkAllNotificationsRead}
          />
          <div className={styles.mobileAccountActions}>
            <ShallowSearchLink href={switchProjectHref}>{t("projects")}</ShallowSearchLink>
            <button type="button" onClick={onSignOut}>
              {common("logout")}
            </button>
          </div>
        </div>
      </header>
      <MobileNavDrawer
        label={t("navigation")}
        onClose={() => setMobileNavOpen(false)}
        open={mobileNavOpen}
      >
        <nav className={styles.mobileDrawerNav}>
          <ShallowSearchLink href={overviewHref} onClick={() => setMobileNavOpen(false)}>
            {t("overview")}
          </ShallowSearchLink>
          <ShallowSearchLink href={checklistHref} onClick={() => setMobileNavOpen(false)}>
            {t("tasks")}
          </ShallowSearchLink>
          <ShallowSearchLink href={chatHref} onClick={() => setMobileNavOpen(false)}>
            {t("chat")}
          </ShallowSearchLink>
          <ShallowSearchLink href={policyHref} onClick={() => setMobileNavOpen(false)}>
            {t("policy.title")}
          </ShallowSearchLink>
          <ShallowSearchLink href={conventionsHref} onClick={() => setMobileNavOpen(false)}>
            {t("conventions")}
          </ShallowSearchLink>
          <ShallowSearchLink href={blockersHref} onClick={() => setMobileNavOpen(false)}>
            {t("blockers")}
          </ShallowSearchLink>
          <ShallowSearchLink href={switchProjectHref} onClick={() => setMobileNavOpen(false)}>
            {t("switchProject")}
          </ShallowSearchLink>
        </nav>
        <div className={styles.mobileDrawerFoot}>
          <LanguageSwitcher />
          <button type="button" onClick={onToggleTheme}>
            {t("theme")}
          </button>
          <button type="button" onClick={onSignOut}>
            {common("logout")}
          </button>
        </div>
      </MobileNavDrawer>
    </>
  );
}
