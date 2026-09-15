"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { getReferencePlan, startReferencePlanGeneration } from "@/features/project-management/api";
import type { OnboardingPlanResponseDTO } from "@/features/project-management/dto/responseDTO/onboardingPlan.response";
import type { PlanGenerationJobResponseDTO } from "@/features/project-management/dto/responseDTO/planGenerationJob.response";
import type { ProjectResponseDTO } from "@/features/project-management/dto/responseDTO/project.response";
import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import { PmButton } from "@/features/project-management/components/ui/PmButton";
import { PmCard, PmPageHead } from "@/features/project-management/components/ui/PmCard";
import { PmConfirmModal } from "@/features/project-management/components/ui/PmConfirmModal";
import { pmToast } from "@/features/project-management/components/ui/PmToast";
import tableStyles from "@/features/project-management/components/ui/PmTable.module.scss";

import { PlanGeneratingView } from "./PlanGeneratingView";
import { PlanReviewView } from "./PlanReviewView";
import styles from "./ReferencePlanView.module.scss";

type ReferencePlanViewProps = {
  project: ProjectResponseDTO | null;
  /** Chuyển sang tab Master Template — nơi DUY NHẤT thêm/xoá task (xem ghi chú trong banner). */
  onGoToTemplate?: () => void;
};

/** Trang "Onboarding Plan" — lộ trình CHUẨN của dự án, tài sản cấp project không thuộc kỹ sư nào.
 *
 * PM soạn ở đây 1 lần (AI sinh nội dung từ Master Template + tài liệu dự án + Company Core), sửa
 * tay thoải mái, tạo lại khi cần. Mỗi kỹ sư khi được cấp plan ở trang Thành viên sẽ nhận 1 BẢN SAO
 * riêng để chạy tiến độ — sửa ở đây KHÔNG đụng ai đã nhận plan, chỉ ảnh hưởng người nhận về sau
 * (SoT rule 11 — snapshot không đổi ngầm dưới chân người đang làm dở).
 *
 * Bản chuẩn luôn ở trạng thái Nháp và không có nút "Duyệt": duyệt là việc của từng plan đã cấp.
 *
 * Ở đây PM sửa được NỘI DUNG từng task, nhưng THÊM/XOÁ task thì làm ở Master Template rồi tạo lại
 * lộ trình — xem ghi chú trong banner để biết vì sao. */
export function ReferencePlanView({ project, onGoToTemplate }: ReferencePlanViewProps) {
  const t = useTranslations("pmUi");
  const [plan, setPlan] = useState<OnboardingPlanResponseDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<PlanGenerationJobResponseDTO | null>(null);
  const [confirmRegenerate, setConfirmRegenerate] = useState(false);
  const [starting, setStarting] = useState(false);

  const projectId = project?.project_id ?? null;

  // Reset khi đổi project — điều chỉnh state ngay trong render thay vì setState trong effect
  // (cùng pattern DocumentsView/MembersView đang dùng).
  const [loadedProjectId, setLoadedProjectId] = useState<number | null>(null);
  if (projectId !== loadedProjectId) {
    setLoadedProjectId(projectId);
    setPlan(null);
    setError(null);
    setJob(null);
    setLoading(projectId !== null);
  }

  useEffect(() => {
    if (projectId === null) return;
    let cancelled = false;
    getReferencePlan(projectId)
      .then((data) => {
        if (!cancelled) {
          setPlan(data);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setPlan(null);
          setError(err instanceof Error ? err.message : t("referencePlanLoadError"));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, t]);

  async function startGeneration() {
    if (projectId === null) return;
    setStarting(true);
    setError(null);
    setConfirmRegenerate(false);
    try {
      setJob(await startReferencePlanGeneration(projectId));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("planGenerationStartError"));
    } finally {
      setStarting(false);
    }
  }

  async function handleGenerated() {
    if (projectId === null) return;
    setJob(null);
    setLoading(true);
    try {
      setPlan(await getReferencePlan(projectId));
      pmToast(t("referencePlanReady"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("generatedPlanLoadError"));
    } finally {
      setLoading(false);
    }
  }

  if (!project) {
    return (
      <section>
        <PmPageHead icon="check-circle" title={t("onboardingPlan")} />
        <PmCard>
          <p className={tableStyles.emptyNote}>
            {t("noManagedProject")}
          </p>
        </PmCard>
      </section>
    );
  }

  // Đang sinh — tái dùng nguyên màn 6 bước của luồng tạo plan cho kỹ sư.
  if (job) {
    return (
      <PlanGeneratingView
        job={job}
        memberName={t("referencePlanFor", { project: project.key })}
        onDone={handleGenerated}
        onCancel={() => setJob(null)}
      />
    );
  }

  if (loading) {
    return (
      <section>
        <PmPageHead icon="check-circle" title={t("onboardingPlan")} />
        <PmCard>
          <p className={tableStyles.emptyNote}>{t("loadingReferencePlan")}</p>
        </PmCard>
      </section>
    );
  }

  if (plan === null) {
    return (
      <section>
        <PmPageHead icon="check-circle" title={t("onboardingPlan")} />
        <PmCard>
          <div className={styles.emptyState}>
            <span className={styles.emptyIcon}>
              <PmIcon name="check-circle" size={22} />
            </span>
            <b>{t("noReferencePlan")}</b>
            <p>{t("noReferencePlanBody")}</p>
            {error && <p className={styles.errorNote}>{error}</p>}
            <PmButton variant="primary" onClick={startGeneration} disabled={starting}>
              <PmIcon name="flag" size={13} />
              {starting ? t("starting") : t("generateReferencePlan")}
            </PmButton>
            <span className={styles.hint}>{t("generationTimeHint")}</span>
          </div>
        </PmCard>
      </section>
    );
  }

  return (
    <>
      {false && <div className={styles.banner}>
        <PmIcon name="alert" size={15} />
        <div>
          <b>{t("referencePlanBannerTitle")}</b>
          <span>{t("referencePlanBannerBody")}</span>
          {/* Danh sách task của lộ trình được sinh 1:1 từ TemplateTask của version đã duyệt (mỗi
              PlanTask bắt buộc trỏ về 1 TemplateTask, và category/thời lượng cũng nằm bên đó). Thêm
              task thẳng vào đây sẽ mất ngay khi tạo lại lộ trình, nên nơi đúng để thêm/xoá là Master
              Template. */}
          <span className={styles.bannerAction}>
            {t("referencePlanTaskHelp")}
            {onGoToTemplate && (
              <PmButton size="sm" onClick={onGoToTemplate}>
                {t("goToMasterTemplate")}
              </PmButton>
            )}
          </span>
        </div>
      </div>}

      {error && <p className={styles.errorNote}>{error}</p>}

      <PlanReviewView
        planId={plan.plan_id}
        projectId={project.project_id}
        memberName={project.key}
        title={t("projectReferencePlan")}
        subtitle={t("referenceSharedBy", { project: project.key })}
        showBackButton={false}
        showApproveButton={false}
        regenerateLabel={t("regenerateWithAi")}
        onRegenerate={() => setConfirmRegenerate(true)}
        onBack={() => undefined}
        onRegenerated={() => undefined}
      />

      {confirmRegenerate && (
        <PmConfirmModal
          icon="alert"
          tone="danger"
          title={t("regenerateReferencePlanTitle")}
          description={
            <>
              <p>{t("regenerateReferencePlanBody")}</p>
              <p>{t("regenerateReferencePlanImpact")}</p>
            </>
          }
          confirmLabel={t("regenerateWithAi")}
          loading={starting}
          onConfirm={startGeneration}
          onClose={() => setConfirmRegenerate(false)}
        />
      )}
    </>
  );
}
