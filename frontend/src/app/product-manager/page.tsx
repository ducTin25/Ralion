"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { useRouter } from "@/i18n/navigation";
import { shallowNavigate } from "@/lib/shallowNavigation";

import { useSession } from "@/features/auth/session";
import { startPlanGeneration } from "@/features/project-management/api";
import { BlockersView } from "@/features/project-management/components/blockers/BlockersView";
import { DashboardView } from "@/features/project-management/components/dashboard/DashboardView";
import { DocumentsView } from "@/features/project-management/components/documents/DocumentsView";
import { MembersView } from "@/features/project-management/components/members/MembersView";
import { PmNotificationsView } from "@/features/project-management/components/notifications/PmNotificationsView";
import { ProjectSwitcher } from "@/features/project-management/components/members/ProjectSwitcher";
import { GenerateStartTimeModal } from "@/features/project-management/components/plan/GenerateStartTimeModal";
import { PlanGeneratingView } from "@/features/project-management/components/plan/PlanGeneratingView";
import { PlanReviewView } from "@/features/project-management/components/plan/PlanReviewView";
import { ReferencePlanView } from "@/features/project-management/components/plan/ReferencePlanView";
import { ProjectListView } from "@/features/project-management/components/projects/ProjectListView";
import { RuleReviewView } from "@/features/project-management/components/rules/RuleReviewView";
import { TemplateView } from "@/features/project-management/components/template/TemplateView";
import { PmButton } from "@/features/project-management/components/ui/PmButton";
import { PmShell, type PmNavKey } from "@/features/project-management/components/PmShell";
import type { PlanGenerationJobResponseDTO } from "@/features/project-management/dto/responseDTO/planGenerationJob.response";
import type { ProjectMembershipDetailResponseDTO } from "@/features/project-management/dto/responseDTO/projectMembership.response";
import { useProjectManagement } from "@/features/project-management/hooks/useProjectManagement";

const CRUMB_BY_NAV: Record<PmNavKey, string> = {
  overview: "Overview",
  projects: "Projects",
  template: "Master Template",
  plan: "Onboarding Plan",
  docs: "Project documents",
  members: "Members",
  notifications: "Notifications",
  blockers: "Blocker Engineer",
  rules: "Rule Review",
};

/** Các view mở được bằng URL `?view=`. Suy thẳng từ CRUMB_BY_NAV nên thêm mục nav mới là tự có. */
const NAVIGABLE_VIEWS = new Set<PmNavKey>(Object.keys(CRUMB_BY_NAV) as PmNavKey[]);

/** Luồng Phase 4 là 1 "màn hình con" nằm trong mục Thành viên, không phải mục nav riêng:
 * danh sách thành viên → đang sinh plan (6 bước) → duyệt plan. Giữ nguyên breadcrumb "Thành viên"
 * để PM không bị lạc, và quay lại là về đúng danh sách cũ. */
type PlanFlow =
  | { stage: "none" }
  // Mở trước bước "generating" — PM chọn/xác nhận giờ bắt đầu ở modal, chưa gọi API sinh plan.
  | { stage: "choosing-start"; member: ProjectMembershipDetailResponseDTO }
  | {
      stage: "generating";
      member: ProjectMembershipDetailResponseDTO;
      job: PlanGenerationJobResponseDTO;
    }
  | { stage: "review"; member: ProjectMembershipDetailResponseDTO; planId: number };

function ProductManagerContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, loading: sessionLoading, error: sessionError, signOut } = useSession();
  // `activeNav` KHÔNG còn là useState: lấy theo query `?view=` (cách của chore/ui-polish) để
  // refresh/bookmark không mất trang đang xem. Riêng planFlow/planError vẫn là state cục bộ vì
  // chúng là trạng thái tạm của luồng sinh plan, không cần nằm trên URL.
  const [planFlow, setPlanFlow] = useState<PlanFlow>({ stage: "none" });
  const [planError, setPlanError] = useState<string | null>(null);
  const requestedProjectValue = searchParams.get("project");
  const requestedProjectId =
    requestedProjectValue && /^\d+$/.test(requestedProjectValue)
      ? Number(requestedProjectValue)
      : null;
  const requestedView = searchParams.get("view");
  // Deep-link từ chuông thông báo PM: `?view=members&membershipId=..&taskId=..` phải tự mở đúng
  // drawer "Xem tiến độ" của đúng Engineer, cuộn tới đúng task — xem MembersView/MemberProgressDrawer.
  const requestedMembershipValue = searchParams.get("membershipId");
  const focusMembershipId =
    requestedMembershipValue && /^\d+$/.test(requestedMembershipValue)
      ? Number(requestedMembershipValue)
      : null;
  const requestedTaskValue = searchParams.get("taskId");
  const focusTaskId =
    requestedTaskValue && /^\d+$/.test(requestedTaskValue) ? Number(requestedTaskValue) : null;
  // Bản chore/ui-polish whitelist cứng 3 giá trị (template|docs|members). Nhánh PM có thêm
  // overview/plan/blockers -> giữ nguyên whitelist đó là 3 trang này rơi hết về "projects".
  // Validate theo NAVIGABLE_VIEWS (suy ra từ CRUMB_BY_NAV) để thêm mục nav mới về sau không phải
  // nhớ sửa thêm chỗ này nữa.
  const activeNav: PmNavKey =
    requestedView && NAVIGABLE_VIEWS.has(requestedView as PmNavKey)
      ? (requestedView as PmNavKey)
      : "overview";
  const hasPmMembership =
    user?.memberships.some(
      (membership) =>
        membership.project_role === "PM" &&
        membership.status === "ACTIVE" &&
        membership.project_status === "ACTIVE",
    ) ?? false;
  const canAccessPm = user?.system_role === null && hasPmMembership;

  useEffect(() => {
    if (sessionLoading) return;
    if (!user) {
      if (sessionError?.status === 401) router.replace("/login");
      return;
    }
    if (user.system_role !== null || !hasPmMembership) router.replace("/access-denied");
  }, [hasPmMembership, router, sessionError, sessionLoading, user]);

  const {
    projects,
    selectedProjectId,
    members,
    blockers,
    loadingProjects,
    loadingMembers,
    loadingBlockers,
    error,
    resolveBlocker,
  } = useProjectManagement(requestedProjectId, canAccessPm);

  useEffect(() => {
    if (
      !canAccessPm ||
      loadingProjects ||
      selectedProjectId === null ||
      requestedProjectId === selectedProjectId
    ) {
      return;
    }
    const next = `/product-manager?project=${selectedProjectId}${activeNav === "overview" ? "" : `&view=${activeNav}`}`;
    if (!shallowNavigate(next, true)) router.replace(next, { scroll: false });
  }, [activeNav, canAccessPm, loadingProjects, requestedProjectId, router, selectedProjectId]);

  if (sessionLoading) return null;
  if (!user) {
    if (sessionError?.status === 401) return null;
    return (
      <main className="flex min-h-screen items-center justify-center p-6" role="alert">
        Your session could not be verified. Please reload the page.
      </main>
    );
  }
  if (!canAccessPm) return null;

  const selectedProject = projects.find((p) => p.project_id === selectedProjectId) ?? null;

  // Chỉ mở modal chọn giờ — chưa gọi API. Xem `handleConfirmStartTime` cho bước gọi thật.
  function handleGeneratePlan(member: ProjectMembershipDetailResponseDTO) {
    setPlanError(null);
    setPlanFlow({ stage: "choosing-start", member });
  }

  async function handleConfirmStartTime(
    member: ProjectMembershipDetailResponseDTO,
    startAt: string | undefined,
  ) {
    try {
      const job = await startPlanGeneration(member.membership_id, startAt);
      setPlanFlow({ stage: "generating", member, job });
    } catch (err) {
      setPlanFlow({ stage: "none" });
      setPlanError(err instanceof Error ? err.message : "The plan could not be started");
    }
  }

  // Quay lại danh sách = MembersView được mount lại, effect trong đó tự gọi lại
  // listOnboardingPlansByProject nên trạng thái Plan luôn mới, không cần refresh thủ công.
  function backToMembers() {
    setPlanFlow({ stage: "none" });
  }

  /** Đổi trang bằng URL (thay cho setActiveNav trước đây) — giữ nguyên project đang chọn. */
  function goToView(next: PmNavKey) {
    const params = new URLSearchParams();
    if (selectedProjectId !== null) params.set("project", String(selectedProjectId));
    if (next !== "overview") params.set("view", next);
    const nextHref = `/product-manager?${params}`;
    if (!shallowNavigate(nextHref)) router.push(nextHref, { scroll: false });
  }

  const showProjectSwitcher =
    planFlow.stage === "none" &&
    (activeNav === "overview" ||
      activeNav === "members" ||
      activeNav === "notifications" ||
      activeNav === "blockers" ||
      activeNav === "template" ||
      activeNav === "plan" ||
      activeNav === "docs");

  return (
    <PmShell
      active={activeNav}
      onNavigate={(key) => {
        // Điều hướng bằng URL theo chore/ui-polish, NHƯNG bỏ nhánh `return` chặn "overview":
        // nhánh PM có trang Tổng quan thật, chặn ở đây là bấm vào nav không có phản ứng gì.
        // Vẫn reset planFlow như bản PM để rời luồng sinh plan khi đổi trang.
        setPlanFlow({ stage: "none" });
        goToView(key);
      }}
      crumb={CRUMB_BY_NAV[activeNav]}
      currentUser={user}
      switchProjectHref="/select-project"
      projectId={selectedProjectId}
      onSignOut={() => void signOut()}
      projectSwitcher={
        showProjectSwitcher ? (
          <ProjectSwitcher
            projects={projects}
            selectedProjectId={selectedProjectId}
            onSelect={(projectId) => {
              const nextHref = `/product-manager?project=${projectId}&view=${activeNav}`;
              if (!shallowNavigate(nextHref)) router.push(nextHref, { scroll: false });
            }}
          />
        ) : undefined
      }
    >
      {error && <p style={{ color: "var(--pm-critical)", marginBottom: "16px" }}>{error}</p>}
      {planError && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "12px",
            color: "var(--pm-critical)",
            marginBottom: "16px",
          }}
        >
          <span>{planError}</span>
          {/* Lỗi hay gặp nhất là "dự án chưa có lộ trình chuẩn" — đưa luôn nút sang đúng chỗ tạo,
              thay vì bắt PM tự mò xem phải làm gì tiếp. */}
          <PmButton
            size="sm"
            onClick={() => {
              setPlanError(null);
              goToView("plan");
            }}
          >
            Go to Onboarding Plan
          </PmButton>
        </div>
      )}

      {planFlow.stage === "choosing-start" && (
        <GenerateStartTimeModal
          memberName={planFlow.member.display_name}
          onConfirm={(startAt) => handleConfirmStartTime(planFlow.member, startAt)}
          onClose={backToMembers}
        />
      )}

      {planFlow.stage === "generating" && (
        <PlanGeneratingView
          job={planFlow.job}
          memberName={planFlow.member.display_name}
          onDone={(planId) => setPlanFlow({ stage: "review", member: planFlow.member, planId })}
          onCancel={backToMembers}
        />
      )}

      {planFlow.stage === "review" && (
        <PlanReviewView
          planId={planFlow.planId}
          projectId={selectedProjectId!}
          memberName={planFlow.member.display_name}
          onBack={backToMembers}
          onRegenerated={(job) =>
            setPlanFlow({ stage: "generating", member: planFlow.member, job })
          }
        />
      )}

      {planFlow.stage === "none" && (
        <>
          {activeNav === "overview" && (
            <DashboardView
              project={selectedProject}
              onGoToMembers={() => goToView("members")}
              onGoToBlockers={() => goToView("blockers")}
              onGoToDocs={() => goToView("docs")}
              onGoToTemplate={() => goToView("template")}
            />
          )}

          {activeNav === "projects" && (
            <ProjectListView projects={projects} loading={loadingProjects} />
          )}

          {activeNav === "members" && (
            <MembersView
              project={selectedProject}
              members={members}
              loading={loadingMembers}
              onGeneratePlan={handleGeneratePlan}
              onOpenPlan={(member, planId) => setPlanFlow({ stage: "review", member, planId })}
              focusMembershipId={focusMembershipId}
              focusTaskId={focusTaskId}
            />
          )}

          {activeNav === "notifications" && selectedProjectId !== null && (
            <PmNotificationsView projectId={selectedProjectId} currentUserId={user.user_id} />
          )}

          {activeNav === "template" && <TemplateView project={selectedProject} />}

          {activeNav === "plan" && (
            <ReferencePlanView
              project={selectedProject}
              onGoToTemplate={() => goToView("template")}
            />
          )}

          {activeNav === "docs" && <DocumentsView project={selectedProject} />}

          {activeNav === "rules" && <RuleReviewView project={selectedProject} />}

          {activeNav === "blockers" && (
            <BlockersView
              project={selectedProject}
              blockers={blockers}
              loading={loadingBlockers}
              onResolve={resolveBlocker}
            />
          )}
        </>
      )}
    </PmShell>
  );
}

export default function ProductManagerPage() {
  return (
    <Suspense fallback={null}>
      <ProductManagerContent />
    </Suspense>
  );
}
