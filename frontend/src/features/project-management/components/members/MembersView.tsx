"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import type { ProjectResponseDTO } from "@/features/project-management/dto/responseDTO/project.response";
import type { ProjectMembershipDetailResponseDTO } from "@/features/project-management/dto/responseDTO/projectMembership.response";
import type { OnboardingPlanResponseDTO } from "@/features/project-management/dto/responseDTO/onboardingPlan.response";
import { listOnboardingPlansByProject } from "@/features/project-management/api";
import { PmAvatar } from "@/features/project-management/components/ui/PmAvatar";
import { PmButton } from "@/features/project-management/components/ui/PmButton";
import { PmCard, PmKpiRow, PmPageHead } from "@/features/project-management/components/ui/PmCard";
import { PmField, PmSelect } from "@/features/project-management/components/ui/PmField";
import { PmPill, PmTag } from "@/features/project-management/components/ui/PmPill";
import { PmSearchInput } from "@/features/project-management/components/ui/PmSearchInput";
import { PmTableFooter } from "@/features/project-management/components/ui/PmTableFooter";
import tableStyles from "@/features/project-management/components/ui/PmTable.module.scss";

import { MemberProgressDrawer } from "./MemberProgressDrawer";
import styles from "./MembersView.module.scss";

const PAGE_SIZE = 10;

type PlanFilter = "ALL" | "NONE" | OnboardingPlanResponseDTO["status"];

const PLAN_FILTER_OPTIONS: { value: PlanFilter; labelKey: string }[] = [
  { value: "ALL", labelKey: "allPlanStates" },
  { value: "NONE", labelKey: "noPlan" },
  { value: "DRAFT", labelKey: "statusDraft" },
  { value: "APPROVED", labelKey: "statusApproved" },
  { value: "ACTIVE", labelKey: "statusInProgress" },
  { value: "PROJECT_READY", labelKey: "statusReadyHandover" },
  { value: "ONBOARDING_CLOSED", labelKey: "statusComplete" },
];

const PLAN_STATUS_META: Record<
  OnboardingPlanResponseDTO["status"],
  { labelKey: string; variant: "neutral" | "progress" | "success" }
> = {
  DRAFT: { labelKey: "statusDraft", variant: "neutral" },
  APPROVED: { labelKey: "statusApproved", variant: "progress" },
  ACTIVE: { labelKey: "statusInProgress", variant: "progress" },
  PROJECT_READY: { labelKey: "statusReadyHandover", variant: "success" },
  ONBOARDING_CLOSED: { labelKey: "statusComplete", variant: "success" },
};

type MembersViewProps = {
  project: ProjectResponseDTO | null;
  members: ProjectMembershipDetailResponseDTO[];
  loading: boolean;
  /** Bấm "Tạo Onboarding Plan" — page.tsx chuyển sang màn PlanGeneratingView (Phase 4). */
  onGeneratePlan: (member: ProjectMembershipDetailResponseDTO) => void;
  /** Bấm "Xem plan" khi thành viên đã có plan — mở thẳng màn duyệt/xem lộ trình. */
  onOpenPlan: (member: ProjectMembershipDetailResponseDTO, planId: number) => void;
  /** Deep-link từ chuông thông báo (`?membershipId=..&taskId=..`) — tự mở đúng drawer "Xem tiến
   * độ" của Engineer đó và cuộn tới đúng task. `null` = mở trang bình thường, không có gì để focus. */
  focusMembershipId?: number | null;
  focusTaskId?: number | null;
};

/**
 * View "Thành viên" — theo dõi trạng thái Onboarding Plan của từng Engineer đã có sẵn trong
 * project (do Admin thêm vào). PM KHÔNG thêm/xoá/khoá thành viên ở đây — chỉ Admin làm việc đó.
 * Đây cũng là điểm vào của Phase 4: chưa có plan thì "Tạo Onboarding Plan", có rồi thì "Xem plan".
 */
export function MembersView({
  project,
  members,
  loading,
  onGeneratePlan,
  onOpenPlan,
  focusMembershipId = null,
  focusTaskId = null,
}: MembersViewProps) {
  const t = useTranslations("pmUi");
  const [plans, setPlans] = useState<OnboardingPlanResponseDTO[]>([]);
  const [loadingPlans, setLoadingPlans] = useState(false);
  const [search, setSearch] = useState("");
  const [planFilter, setPlanFilter] = useState<PlanFilter>("ALL");
  const [page, setPage] = useState(1);
  const [progressMember, setProgressMember] = useState<ProjectMembershipDetailResponseDTO | null>(
    null,
  );
  // Deep-link 1 lần cho mỗi membershipId trên URL — không tự bật lại nếu PM đã tự tay đóng drawer.
  const [appliedFocusMembershipId, setAppliedFocusMembershipId] = useState<number | null>(null);

  // Reset danh sách Plan khi đổi project — điều chỉnh state ngay trong render thay vì effect
  // (theo react.dev/learn/you-might-not-need-an-effect#adjusting-some-state-when-a-prop-changes).
  const [loadedProjectId, setLoadedProjectId] = useState<number | null>(null);
  if ((project?.project_id ?? null) !== loadedProjectId) {
    setLoadedProjectId(project?.project_id ?? null);
    setPlans([]);
  }

  useEffect(() => {
    if (project === null) return;
    let cancelled = false;
    // Fetch dữ liệu khi project đổi — đồng bộ với external API, pattern hợp lệ theo
    // react.dev/learn/you-might-not-need-an-effect (rule không theo dõi được set trực tiếp ở đây).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoadingPlans(true);
    listOnboardingPlansByProject(project.project_id)
      .then((data) => {
        if (!cancelled) setPlans(data);
      })
      .catch(() => {
        if (!cancelled) setPlans([]);
      })
      .finally(() => {
        if (!cancelled) setLoadingPlans(false);
      });
    return () => {
      cancelled = true;
    };
  }, [project]);

  const [pageResetKey, setPageResetKey] = useState(
    `${search}|${planFilter}|${project?.project_id}`,
  );
  const nextPageResetKey = `${search}|${planFilter}|${project?.project_id}`;
  if (pageResetKey !== nextPageResetKey) {
    setPageResetKey(nextPageResetKey);
    setPage(1);
  }

  if (!project) {
    return (
      <section>
        <PmPageHead icon="users" title={t("membersTitle")} />
        <PmCard>
          <p className={tableStyles.emptyNote}>{t("noManagedProject")}</p>
        </PmCard>
      </section>
    );
  }

  const planByMembership = new Map(plans.map((p) => [p.membership_id, p]));
  const engineers = members.filter((m) => m.project_role === "ENGINEER");

  // Deep-link từ chuông thông báo: mở đúng drawer khi thấy membershipId khớp — điều chỉnh state
  // ngay trong render (react.dev/learn/you-might-not-need-an-effect#adjusting-some-state-when-a-prop-changes),
  // không cần effect. Chưa khớp được (danh sách Engineer chưa tải xong) thì tự thử lại render sau.
  if (focusMembershipId !== null && focusMembershipId !== appliedFocusMembershipId) {
    const match = engineers.find((m) => m.membership_id === focusMembershipId);
    if (match) {
      setAppliedFocusMembershipId(focusMembershipId);
      setProgressMember(match);
    }
  }

  const query = search.trim().toLowerCase();
  const filtered = engineers.filter((m) => {
    if (
      query &&
      !m.display_name.toLowerCase().includes(query) &&
      !m.email.toLowerCase().includes(query)
    ) {
      return false;
    }
    const plan = planByMembership.get(m.membership_id);
    if (planFilter === "ALL") return true;
    if (planFilter === "NONE") return !plan;
    return plan?.status === planFilter;
  });

  const isLoading = loading || loadingPlans;
  const withPlanCount = engineers.filter((m) => planByMembership.has(m.membership_id)).length;
  const doneCount = engineers.filter(
    (m) => planByMembership.get(m.membership_id)?.status === "ONBOARDING_CLOSED",
  ).length;

  const pageItems = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <section>
      <PmPageHead icon="users" title={t("membersTitle")} subtitle={t("membersSubtitle")} />

      {!isLoading && engineers.length > 0 && (
        <PmKpiRow
          items={[
            {
              label: t("engineers"),
              value: engineers.length,
              icon: "users",
              variant: "accent",
            },
            {
              label: t("noPlan"),
              value: engineers.length - withPlanCount,
              icon: "doc",
              variant: "warning",
            },
            { label: t("completed"), value: doneCount, icon: "check-circle", variant: "violet" },
          ]}
        />
      )}

      <PmCard>
        <div className={styles.filterRow}>
          <PmField label={t("search")}>
            <PmSearchInput value={search} onChange={setSearch} placeholder={t("searchMembers")} />
          </PmField>
          <PmField label={t("filterByPlanStatus")}>
            <PmSelect
              value={planFilter}
              onChange={(e) => setPlanFilter(e.target.value as PlanFilter)}
            >
              {PLAN_FILTER_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {t(opt.labelKey)}
                </option>
              ))}
            </PmSelect>
          </PmField>
        </div>

        {isLoading ? (
          <p className={tableStyles.emptyNote}>{t("loadingMembers")}</p>
        ) : engineers.length === 0 ? (
          <p className={tableStyles.emptyNote}>{t("noEngineers")}</p>
        ) : filtered.length === 0 ? (
          <p className={tableStyles.emptyNote}>{t("noMembersMatch")}</p>
        ) : (
          <>
            <div className={`${tableStyles.tableWrap} ${styles.memberTableWrap}`}>
              <table className={tableStyles.table}>
                <thead>
                  <tr>
                    <th>{t("membersTitle")}</th>
                    <th>{t("onboardingPlan")}</th>
                    <th>{t("actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {pageItems.map((m) => {
                    const plan = planByMembership.get(m.membership_id);
                    const meta = plan ? PLAN_STATUS_META[plan.status] : null;
                    return (
                      <tr key={m.membership_id}>
                        <td data-label={t("membersTitle")}>
                          <div className={styles.memberCell}>
                            <PmAvatar seed={m.email} label={m.display_name} />
                            <div>
                              <div className={styles.memberMain}>
                                {m.display_name}
                                {m.status !== "ACTIVE" && <PmTag>{t("locked")}</PmTag>}
                              </div>
                              <div className={styles.memberSub}>{m.email}</div>
                            </div>
                          </div>
                        </td>
                        <td data-label={t("onboardingPlan")}>
                          <PmPill variant={meta?.variant ?? "neutral"}>
                            {meta ? t(meta.labelKey) : t("noPlan")}
                          </PmPill>
                        </td>
                        <td data-label={t("actions")}>
                          <div className={styles.actionCell}>
                            {plan ? (
                              <PmButton size="sm" onClick={() => onOpenPlan(m, plan.plan_id)}>
                                {t("viewPlan")}
                              </PmButton>
                            ) : (
                              <PmButton
                                size="sm"
                                variant="primary"
                                onClick={() => onGeneratePlan(m)}
                                disabled={m.status !== "ACTIVE"}
                                title={m.status !== "ACTIVE" ? t("lockedPlanHelp") : undefined}
                              >
                                {t("createOnboardingPlan")}
                              </PmButton>
                            )}
                            {/* Xem task/quá hạn/blocker của thành viên — SoT §17.2. Vẫn hiện dù
                                chưa có plan, nút bên trong drawer tự báo "chưa có gì để theo dõi". */}
                            <PmButton size="sm" onClick={() => setProgressMember(m)}>
                              {t("viewProgress")}
                            </PmButton>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <p className={styles.caption}>{t("planStatusHelp")}</p>

            <PmTableFooter
              total={filtered.length}
              page={page}
              pageSize={PAGE_SIZE}
              onPageChange={setPage}
            />
          </>
        )}
      </PmCard>

      {progressMember && (
        <MemberProgressDrawer
          member={progressMember}
          projectId={project.project_id}
          highlightTaskId={progressMember.membership_id === focusMembershipId ? focusTaskId : null}
          onClose={() => setProgressMember(null)}
        />
      )}
    </section>
  );
}
