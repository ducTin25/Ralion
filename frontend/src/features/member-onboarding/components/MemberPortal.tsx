"use client";

import {
  HydrationBoundary,
  QueryClientProvider,
  type DehydratedState,
} from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";

import { BlockerModal } from "@/features/member-onboarding/components/BlockerModal";
import { BlockersView } from "@/features/member-onboarding/components/BlockersView";
import { ChecklistView } from "@/features/member-onboarding/components/ChecklistView";
import { MemberIcon } from "@/features/member-onboarding/components/MemberIcon";
import { EngineerOverview } from "@/features/member-onboarding/components/EngineerOverview";
import { TaskStagesView } from "@/features/member-onboarding/components/TaskStagesView";
import { NotificationsView } from "@/features/member-onboarding/components/NotificationsView";
import { MemberSidebar } from "@/features/member-onboarding/components/MemberSidebar";
import { MemberTopbar } from "@/features/member-onboarding/components/MemberTopbar";
import {
  ContentLoading,
  LoadingScreen,
  PortalError,
} from "@/features/member-onboarding/components/PortalFeedback";
import { TaskDetailPage } from "@/features/member-onboarding/components/TaskDetailPage";
import { MemberPolicyScreen } from "@/features/member-onboarding/components/MemberPolicyScreen";
import { ChatScreen } from "@/features/chat/ChatScreen";
import {
  memberErrorMessage,
  useMemberOnboarding,
} from "@/features/member-onboarding/hooks/useMemberOnboarding";
import { useMemberPortalUrl } from "@/features/member-onboarding/hooks/useMemberPortalUrl";
import { usePersistentTheme } from "@/features/member-onboarding/hooks/usePersistentTheme";
import { createMemberQueryClient } from "@/features/member-onboarding/queryClient";
import { useSession } from "@/features/auth/session";
import type { CurrentUser } from "@/features/auth/session";
import { usePathname, useRouter } from "@/i18n/navigation";
import { MemberConventionsView } from "@/features/conventions/components/MemberConventionsView";
import { ShallowSearchLink } from "@/components/navigation/ShallowSearchLink";

import styles from "./MemberPortal.module.scss";

type OnboardingState = ReturnType<typeof useMemberOnboarding>;

function PortalUnavailable({
  title,
  message,
  retry,
}: {
  title: string;
  message: string;
  retry?: () => void;
}) {
  const t = useTranslations("member.portal");
  return (
    <main className={styles.errorPage}>
      <div className={styles.errorIcon}>!</div>
      <h1>{title}</h1>
      <p>{message}</p>
      {retry && (
        <button type="button" className={styles.primaryButton} onClick={retry}>
          <MemberIcon name="refresh" size={16} /> {t("retry")}
        </button>
      )}
    </main>
  );
}

function MemberPortalWorkspace({
  onboarding,
  currentUser,
  onSignOut,
}: {
  onboarding: OnboardingState;
  currentUser: CurrentUser;
  onSignOut: () => void;
}) {
  const t = useTranslations("member.portal");
  const tasksT = useTranslations("member.tasksView");
  const locale = useLocale();
  const portalUrl = useMemberPortalUrl();
  const { theme, toggleTheme } = usePersistentTheme();
  const [search, setSearch] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [showBlockerModal, setShowBlockerModal] = useState(false);
  const [newConversationRequest, setNewConversationRequest] = useState(0);
  const [readNotifications, setReadNotifications] = useState<Record<string, number[]>>({});
  const localizedError = (error: unknown, fallback: string) =>
    memberErrorMessage(error, fallback, {
      401: t("sessionExpired"),
      403: t("accessDenied"),
      404: t("dataNotFound"),
    });

  useEffect(() => {
    if (!notice) return;
    const timeout = window.setTimeout(() => setNotice(null), 3000);
    return () => window.clearTimeout(timeout);
  }, [notice]);

  useEffect(() => {
    const hydrateReadState = window.setTimeout(() => {
      try {
        setReadNotifications(
          JSON.parse(window.localStorage.getItem("member-read-notifications") ?? "{}") as Record<
            string,
            number[]
          >,
        );
      } catch {
        window.localStorage.removeItem("member-read-notifications");
      }
    }, 0);
    return () => window.clearTimeout(hydrateReadState);
  }, []);

  const projectData = onboarding.projectData as NonNullable<OnboardingState["projectData"]>;
  const selectedProject = projectData.projects.find(
    (project) => project.project_id === portalUrl.projectId,
  );
  const member = projectData.member;
  const notificationReadKey = `${member.user_id}:${portalUrl.projectId ?? 0}`;
  const readNotificationIds = readNotifications[notificationReadKey] ?? [];
  const unreadNotifications = onboarding.notifications.filter(
    (notification) => !readNotificationIds.includes(notification.plan_task_id),
  );
  const markNotificationsRead = (taskIds: number[]) => {
    setReadNotifications((current) => {
      const next = {
        ...current,
        [notificationReadKey]: Array.from(
          new Set([...(current[notificationReadKey] ?? []), ...taskIds]),
        ),
      };
      window.localStorage.setItem("member-read-notifications", JSON.stringify(next));
      return next;
    });
  };
  const filteredGroups = useMemo(() => {
    if (!onboarding.checklist) return [];
    const term = search.trim().toLocaleLowerCase(locale);
    const groups = portalUrl.category
      ? onboarding.checklist.groups.filter((group) => group.category === portalUrl.category)
      : onboarding.checklist.groups;
    if (!term) return groups;
    return groups
      .map((group) => ({
        ...group,
        tasks: group.tasks.filter((task) => task.title.toLocaleLowerCase(locale).includes(term)),
      }))
      .filter((group) => group.tasks.length > 0);
  }, [locale, onboarding.checklist, portalUrl.category, search]);
  if (!selectedProject || portalUrl.projectId === null) return null;

  const overviewHref = portalUrl.href({ view: "overview", taskId: null, category: null });
  const checklistHref = portalUrl.href({ view: "tasks", taskId: null, category: null });
  const notificationsHref = portalUrl.href({ view: "notifications", taskId: null, category: null });
  const blockersHref = portalUrl.href({ view: "blockers", taskId: null });
  const conventionsHref = portalUrl.href({ view: "conventions", taskId: null });
  const chatHref = portalUrl.href({ view: "chat", taskId: null });
  const policyHref = portalUrl.href({ view: "policy", taskId: null });
  const hrefForCategory = (category: import("@/features/member-onboarding/types").TaskCategory) =>
    portalUrl.href({ view: "tasks", taskId: null, category });
  const hrefForTask = (taskId: number) => {
    const category = onboarding.checklist?.groups
      .flatMap((group) => group.tasks.map((task) => ({ task, category: group.category })))
      .find((item) => item.task.plan_task_id === taskId)?.category;
    return portalUrl.href({ view: "tasks", taskId, category: category ?? null });
  };
  const taskBelongsToProject =
    onboarding.taskDetail !== null &&
    onboarding.checklist !== null &&
    onboarding.taskDetail.plan_id === onboarding.checklist.plan_id;
  const taskMismatch =
    onboarding.taskDetail !== null &&
    onboarding.checklist !== null &&
    onboarding.taskDetail.plan_id !== onboarding.checklist.plan_id;
  const taskDetail = taskBelongsToProject ? onboarding.taskDetail : null;

  const closeTask = () => {
    setShowBlockerModal(false);
    portalUrl.navigate({ taskId: null }, true);
  };
  const handleTransition = async (status: "IN_PROGRESS" | "DONE") => {
    if (!taskDetail) return;
    const updated = await onboarding.transitionTask(taskDetail.plan_task_id, status);
    if (updated) {
      setNotice(status === "DONE" ? t("taskDone") : t("taskStarted"));
    }
  };
  const handleReportBlocker = async (payload: Parameters<typeof onboarding.reportBlocker>[1]) => {
    if (!taskDetail) return false;
    const created = await onboarding.reportBlocker(taskDetail.plan_task_id, payload);
    if (created) setNotice(t("blockerRecorded"));
    return created !== null;
  };

  return (
    <div className={`${styles.portal} ralion-workspace`} data-theme={theme}>
      <MemberSidebar
        member={member}
        activeView={portalUrl.view}
        overviewHref={overviewHref}
        tasksHref={checklistHref}
        notificationsHref={notificationsHref}
        checklistHref={checklistHref}
        blockersHref={blockersHref}
        conventionsHref={conventionsHref}
        blockerCount={onboarding.blockers.length}
        notificationCount={unreadNotifications.length}
        chatHref={chatHref}
        policyHref={policyHref}
        switchProjectHref="/select-project"
        onSignOut={onSignOut}
        checklist={onboarding.checklist}
        activeTaskId={portalUrl.taskId}
        activeCategory={portalUrl.category}
        hrefForTask={hrefForTask}
      />

      <div className={styles.main}>
        <MemberTopbar
          activeView={portalUrl.view}
          projectName={selectedProject.name}
          projects={projectData.projects}
          selectedProjectId={selectedProject.project_id}
          search={search}
          theme={theme}
          notifications={onboarding.notifications}
          readNotificationIds={readNotificationIds}
          onMarkNotificationRead={(taskId) => markNotificationsRead([taskId])}
          onMarkAllNotificationsRead={() =>
            markNotificationsRead(
              onboarding.notifications.map((notification) => notification.plan_task_id),
            )
          }
          onSearch={setSearch}
          onSelectProject={(projectId) =>
            portalUrl.navigate({ projectId, view: "overview", taskId: null, category: null })
          }
          onToggleTheme={toggleTheme}
          onNewConversation={() => setNewConversationRequest((request) => request + 1)}
          switchProjectHref="/select-project"
          checklistHref={checklistHref}
          overviewHref={overviewHref}
          hrefForTask={hrefForTask}
          blockersHref={blockersHref}
          conventionsHref={conventionsHref}
          chatHref={chatHref}
          policyHref={policyHref}
          onSignOut={onSignOut}
        />

        <main
          className={`${styles.content} ${portalUrl.view === "chat" ? styles.contentChat : ""}`}
        >
          {portalUrl.view === "chat" ? (
            <ChatScreen
              embeddedUser={currentUser}
              newConversationRequest={newConversationRequest}
            />
          ) : portalUrl.view === "overview" ? (
            onboarding.checklist ? (
              <EngineerOverview
                member={member}
                checklist={onboarding.checklist}
                notifications={onboarding.notifications}
                tasksHref={checklistHref}
                notificationsHref={notificationsHref}
                hrefForTask={hrefForTask}
              />
            ) : (
              <ContentLoading label={t("loadingChecklist")} />
            )
          ) : portalUrl.view === "notifications" ? (
            <NotificationsView
              notifications={onboarding.notifications}
              readIds={readNotificationIds}
              hrefForTask={hrefForTask}
              onMarkRead={(taskId) => markNotificationsRead([taskId])}
              onMarkAllRead={() =>
                markNotificationsRead(
                  onboarding.notifications.map((notification) => notification.plan_task_id),
                )
              }
            />
          ) : portalUrl.view === "policy" ? (
            <MemberPolicyScreen
              embedded
              embeddedUser={currentUser}
              projectId={selectedProject.project_id}
            />
          ) : portalUrl.view === "blockers" ? (
            <BlockersView
              blockers={onboarding.blockers}
              loading={onboarding.loadingBlockers}
              error={
                onboarding.blockersLoadError
                  ? localizedError(onboarding.blockersLoadError, t("blockersLoadError"))
                  : null
              }
              checklistHref={checklistHref}
              hrefForTask={hrefForTask}
              onRetry={() => void onboarding.refreshBlockers()}
            />
          ) : portalUrl.view === "conventions" ? (
            <MemberConventionsView projectId={selectedProject.project_id} />
          ) : portalUrl.taskId !== null ? (
            onboarding.loadingTask || onboarding.loadingChecklist ? (
              <ContentLoading label={t("loadingTask")} />
            ) : onboarding.taskLoadError ? (
              <PortalError message={localizedError(onboarding.taskLoadError, t("taskLoadError"))} />
            ) : taskMismatch ? (
              <PortalError message={t("taskProjectMismatch")} />
            ) : taskDetail && onboarding.checklist ? (
              <TaskDetailPage
                key={taskDetail.plan_task_id}
                task={taskDetail}
                onBack={closeTask}
                onTransition={handleTransition}
                onReportBlocker={() => setShowBlockerModal(true)}
                updating={onboarding.updatingTask}
                actionError={
                  onboarding.taskActionError
                    ? localizedError(onboarding.taskActionError, t("taskUpdateError"))
                    : null
                }
              />
            ) : null
          ) : onboarding.checklist && !onboarding.loadingChecklist && !onboarding.checklistError ? (
            portalUrl.category ? (
              <div className={styles.categoryPage}>
                <ShallowSearchLink className={styles.categoryBack} href={checklistHref}>
                  <MemberIcon name="back" size={16} />
                  {tasksT("backToStages")}
                </ShallowSearchLink>
                <ChecklistView
                  member={member}
                  checklist={onboarding.checklist}
                  filteredGroups={filteredGroups}
                  search={search}
                  loading={false}
                  error={null}
                  hrefForTask={hrefForTask}
                  onRetry={() => void onboarding.refreshChecklist()}
                />
              </div>
            ) : (
              <TaskStagesView checklist={onboarding.checklist} hrefForCategory={hrefForCategory} />
            )
          ) : (
            <ChecklistView
              member={member}
              checklist={onboarding.checklist}
              filteredGroups={filteredGroups}
              search={search}
              loading={onboarding.loadingChecklist}
              error={
                onboarding.checklistError
                  ? localizedError(onboarding.checklistError, t("checklistLoadError"))
                  : null
              }
              hrefForTask={hrefForTask}
              onRetry={() => void onboarding.refreshChecklist()}
            />
          )}
        </main>
      </div>

      {notice && (
        <div className={styles.toast} role="status">
          <MemberIcon name="check" size={16} /> {notice}
        </div>
      )}
      {showBlockerModal && taskDetail && (
        <BlockerModal
          taskTitle={taskDetail.title}
          submitting={onboarding.creatingBlocker}
          requestError={
            onboarding.blockerActionError
              ? localizedError(onboarding.blockerActionError, t("blockerReportError"))
              : null
          }
          onClose={() => setShowBlockerModal(false)}
          onSubmit={handleReportBlocker}
        />
      )}
    </div>
  );
}

// chore/ui-polish tách đôi: MemberPortalData giữ phần dữ liệu, MemberPortalContent (bên dưới) lo
// auth + truyền onSignOut xuống. Giữ `router` vì thân hàm này vẫn dùng để redirect khi thiếu project.
function MemberPortalData({
  currentUser,
  onSignOut,
}: {
  currentUser: CurrentUser;
  onSignOut: () => void;
}) {
  const t = useTranslations("member.portal");
  const router = useRouter();
  const portalUrl = useMemberPortalUrl();
  const { projectId } = portalUrl;
  const onboarding = useMemberOnboarding({
    projectId,
    taskId: portalUrl.taskId,
  });
  const localizedError = (error: unknown, fallback: string) =>
    memberErrorMessage(error, fallback, {
      401: t("sessionExpired"),
      403: t("accessDenied"),
      404: t("dataNotFound"),
    });

  useEffect(() => {
    if (projectId === null) router.replace("/select-project");
  }, [projectId, router]);

  // `app/user/page.tsx` redirect ở server; nhánh này là fallback nếu component
  // được mount độc lập hoặc trong lúc client navigation đang chuyển route.
  if (projectId === null) return <LoadingScreen />;

  if (onboarding.loadingProjects) return <LoadingScreen />;
  if (!onboarding.projectData) {
    return (
      <PortalUnavailable
        title={t("unavailableTitle")}
        message={localizedError(onboarding.projectsError, t("memberLoadError"))}
        retry={() => void onboarding.refreshProjects()}
      />
    );
  }
  if (onboarding.projectData.projects.length === 0) {
    return <PortalUnavailable title={t("noProjectsTitle")} message={t("noProjectsBody")} />;
  }
  if (!onboarding.projectData.projects.some((project) => project.project_id === projectId)) {
    return (
      <PortalUnavailable
        title={t("projectUnavailableTitle")}
        message={t("projectUnavailableBody")}
      />
    );
  }

  return (
    <MemberPortalWorkspace
      key={portalUrl.projectId}
      onboarding={onboarding}
      currentUser={currentUser}
      onSignOut={onSignOut}
    />
  );
}

function MemberPortalContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { user, loading, error, signOut } = useSession();
  const hasEngineerMembership =
    user?.memberships.some(
      (membership) =>
        membership.project_role === "ENGINEER" &&
        membership.status === "ACTIVE" &&
        membership.project_status === "ACTIVE",
    ) ?? false;

  useEffect(() => {
    if (loading) return;
    if (!user) {
      if (error?.status === 401) {
        const query = searchParams.toString();
        router.replace(
          `/login?next=${encodeURIComponent(`${pathname}${query ? `?${query}` : ""}`)}`,
        );
      }
      return;
    }
    if (user.system_role !== null) router.replace("/access-denied");
    else if (!hasEngineerMembership) router.replace("/select-project");
  }, [error, hasEngineerMembership, loading, pathname, router, searchParams, user]);

  if (loading || !user || user.system_role !== null || !hasEngineerMembership) return null;
  return <MemberPortalData currentUser={user} onSignOut={() => void signOut()} />;
}

export function MemberPortal({ dehydratedState }: { dehydratedState?: DehydratedState }) {
  const [queryClient] = useState(createMemberQueryClient);
  return (
    <QueryClientProvider client={queryClient}>
      <HydrationBoundary state={dehydratedState}>
        <MemberPortalContent />
      </HydrationBoundary>
    </QueryClientProvider>
  );
}
