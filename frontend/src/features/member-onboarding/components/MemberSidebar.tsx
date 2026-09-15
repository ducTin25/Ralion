import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { LogoutButton } from "@/components/auth/LogoutButton";
import { BrandHomeLink } from "@/components/brand/BrandHomeLink";
import { RalionBrand } from "@/components/brand/RalionBrand";
import { MemberIcon } from "@/features/member-onboarding/components/MemberIcon";
import { initials } from "@/features/member-onboarding/components/memberPortalUi";
import type { MemberProfile } from "@/features/member-onboarding/types";
import type { MemberChecklist } from "@/features/member-onboarding/types";
import type { MemberPortalView } from "@/features/member-onboarding/hooks/useMemberPortalUrl";
import { OnboardingJourney } from "./OnboardingJourney";
import { policyApi } from "@/features/policy-acknowledgement/api";
import { ShallowSearchLink } from "@/components/navigation/ShallowSearchLink";

import styles from "./MemberPortal.module.scss";

type MemberSidebarProps = {
  member: MemberProfile;
  activeView: MemberPortalView;
  overviewHref?: string;
  tasksHref?: string;
  notificationsHref?: string;
  checklistHref: string;
  blockersHref: string;
  conventionsHref?: string;
  chatHref?: string;
  policyHref?: string;
  blockerCount: number;
  notificationCount?: number;
  roleLabel?: string;
  showMemberNavigation?: boolean;
  switchProjectHref?: string;
  onSignOut?: () => void;
  checklist?: MemberChecklist | null;
  activeTaskId?: number | null;
  activeCategory?: import("@/features/member-onboarding/types").TaskCategory | null;
  hrefForTask?: (taskId: number) => string;
};

export function MemberSidebar({
  member,
  activeView,
  overviewHref = "/user",
  tasksHref,
  checklistHref,
  blockersHref,
  conventionsHref,
  chatHref = "/chat",
  policyHref,
  blockerCount,
  showMemberNavigation = true,
  switchProjectHref,
  onSignOut,
  checklist,
  activeTaskId = null,
  activeCategory = null,
  hrefForTask,
}: MemberSidebarProps) {
  const t = useTranslations("member");
  const common = useTranslations("common");

  const [pendingPolicyCount, setPendingPolicyCount] = useState(0);
  useEffect(() => {
    if (!policyHref) return;
    let alive = true;
    policyApi
      .pending()
      .then((response) => {
        if (alive) setPendingPolicyCount(response.items.length);
      })
      .catch(() => {
        // Badge phụ trên sidebar: lỗi thì im lặng ẩn đi, không phá nav chính.
        if (alive) setPendingPolicyCount(0);
      });
    return () => {
      alive = false;
    };
  }, [policyHref]);

  return (
    <aside className={styles.sidebar}>
      <BrandHomeLink className={styles.sidebarBrand}>
        <RalionBrand size={28} />
      </BrandHomeLink>

      {activeView === "tasks" && checklist && hrefForTask ? (
        <div className={styles.taskSidebarIntro}>
          <ShallowSearchLink href={overviewHref}>
            <MemberIcon name="back" size={16} />
            <span>{t("overview")}</span>
          </ShallowSearchLink>
          <div>
            <b>{checklist.project.name}</b>
            <span>
              {checklist.progress.completed}/{checklist.progress.total} ·{" "}
              {checklist.progress.percent}%
            </span>
          </div>
        </div>
      ) : null}

      {activeView === "tasks" && (
        <ShallowSearchLink
          aria-label={t("chat")}
          href={chatHref}
          className={styles.taskChatShortcut}
        >
          <MemberIcon name="chat" />
          <span>{t("chat")}</span>
        </ShallowSearchLink>
      )}

      {activeView !== "tasks" && (
        <nav className={styles.nav} aria-label={t("navigation")}>
          {showMemberNavigation && (
            <ShallowSearchLink
              aria-label={t("overview")}
              href={overviewHref}
              className={activeView === "overview" ? styles.navActive : ""}
              aria-current={activeView === "overview" ? "page" : undefined}
            >
              <MemberIcon name="dashboard" />
              <span>{t("overview")}</span>
            </ShallowSearchLink>
          )}
          {showMemberNavigation && (
            <ShallowSearchLink aria-label={t("tasks")} href={tasksHref ?? checklistHref}>
              <MemberIcon name="check" />
              <span>{t("tasks")}</span>
            </ShallowSearchLink>
          )}

          <ShallowSearchLink
            aria-label={t("chat")}
            href={chatHref}
            className={activeView === "chat" ? styles.navActive : ""}
            aria-current={activeView === "chat" ? "page" : undefined}
          >
            <MemberIcon name="chat" />
            <span>{t("chat")}</span>
          </ShallowSearchLink>
          {policyHref && (
            <ShallowSearchLink
              aria-label={t("policy.title")}
              href={policyHref}
              className={activeView === "policy" ? styles.navActive : ""}
              aria-current={activeView === "policy" ? "page" : undefined}
            >
              <MemberIcon name="shield" />
              <span>{t("policy.title")}</span>
              {pendingPolicyCount > 0 && <small>{pendingPolicyCount}</small>}
            </ShallowSearchLink>
          )}
          {showMemberNavigation && conventionsHref && (
            <ShallowSearchLink
              aria-label={t("conventions")}
              href={conventionsHref}
              className={activeView === "conventions" ? styles.navActive : ""}
              aria-current={activeView === "conventions" ? "page" : undefined}
            >
              <MemberIcon name="book" />
              <span>{t("conventions")}</span>
            </ShallowSearchLink>
          )}
          {showMemberNavigation && (
            <ShallowSearchLink
              aria-label={t("blockers")}
              href={blockersHref}
              className={activeView === "blockers" ? styles.navActive : ""}
              aria-current={activeView === "blockers" ? "page" : undefined}
            >
              <MemberIcon name="flag" />
              <span>{t("blockers")}</span>

              {blockerCount > 0 && <small>{blockerCount}</small>}
            </ShallowSearchLink>
          )}
        </nav>
      )}

      {activeView === "tasks" && checklist && hrefForTask && (
        <div className={styles.sidebarJourney}>
          <OnboardingJourney
            checklist={checklist}
            activeTaskId={activeTaskId}
            activeCategory={activeCategory}
            hrefForTask={hrefForTask}
          />
        </div>
      )}

      {activeView !== "tasks" && (
        <div className={styles.sidebarAccount}>
          <div className={styles.sidebarUser}>
            <span className={styles.avatar}>{initials(member.display_name)}</span>

            <div>
              <b>{member.display_name}</b>
              <small>{member.email}</small>
            </div>
          </div>

          {switchProjectHref && (
            <div className={styles.accountActions}>
              <ShallowSearchLink
                aria-label={t("switchProject")}
                href={switchProjectHref}
                className={styles.accountAction}
              >
                <MemberIcon name="chevron" size={15} />
                <span>{t("switchProject")}</span>
              </ShallowSearchLink>
            </div>
          )}

          <div className={styles.sidebarAccountControls}>
            {onSignOut ? (
              <button
                aria-label={common("logout")}
                type="button"
                className={styles.logoutButton}
                onClick={onSignOut}
              >
                <MemberIcon name="logout" size={15} />
                <span>{common("logout")}</span>
              </button>
            ) : (
              <LogoutButton className={styles.logoutButton}>
                <MemberIcon name="logout" size={15} />
                <span>{common("logout")}</span>
              </LogoutButton>
            )}
          </div>
        </div>
      )}
    </aside>
  );
}
