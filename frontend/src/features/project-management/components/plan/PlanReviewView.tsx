"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useLocale, useTranslations } from "next-intl";

import { approvePlan, listPlanTasks, regeneratePlan } from "@/features/project-management/api";
import type { OnboardingPlanResponseDTO } from "@/features/project-management/dto/responseDTO/onboardingPlan.response";
import type { PlanGenerationJobResponseDTO } from "@/features/project-management/dto/responseDTO/planGenerationJob.response";
import type { PlanTaskResponseDTO } from "@/features/project-management/dto/responseDTO/planTask.response";
import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import { CATEGORY_OPTIONS } from "@/features/project-management/components/template/TaskFormModal";
import { PmButton } from "@/features/project-management/components/ui/PmButton";
import {
  PmCard,
  PmKpiRow,
  PmPageHead,
  PmSectionTitle,
} from "@/features/project-management/components/ui/PmCard";
import { PmConfirmModal } from "@/features/project-management/components/ui/PmConfirmModal";
import { PmPill, PmTag } from "@/features/project-management/components/ui/PmPill";
import { pmToast } from "@/features/project-management/components/ui/PmToast";
import tableStyles from "@/features/project-management/components/ui/PmTable.module.scss";

import { PlanTaskDrawer } from "./PlanTaskDrawer";
import styles from "./PlanReviewView.module.scss";

const VARIANT_ICON_CLASS: Record<string, string> = {
  accent: "iconAccent",
  success: "iconSuccess",
  warning: "iconWarning",
  violet: "iconViolet",
};

type PlanReviewViewProps = {
  planId: number;
  projectId: number;
  memberName: string;
  onBack: () => void;
  onRegenerated: (job: PlanGenerationJobResponseDTO) => void;
  /** Tiêu đề + mô tả tuỳ biến — trang "Onboarding Plan chuẩn" cần chữ khác vì không gắn 1 kỹ sư
   * cụ thể nào. Bỏ trống thì dùng chữ mặc định của luồng duyệt plan cho từng người. */
  title?: string;
  subtitle?: ReactNode;
  /** `false` khi nhúng làm 1 tab đứng độc lập (không có màn trước để quay lại). */
  showBackButton?: boolean;
  /** `false` cho lộ trình chuẩn của dự án — bản chuẩn không phát hành cho ai nên không có bước
   * duyệt (backend cũng trả 409 nếu cố duyệt). */
  showApproveButton?: boolean;
  /** Thay hành vi nút "Tạo lại" — trang lộ trình chuẩn gọi API sinh bản chuẩn (có AI) thay vì
   * regenerate của plan kỹ sư. Bỏ trống thì dùng regenerate mặc định. */
  onRegenerate?: () => void;
  /** Nhãn nút tạo lại; bản chuẩn ghi rõ "bằng AI" vì đó là lần gọi AI thật (~30s). */
  regenerateLabel?: string;
};

function formatDate(value: string | null, locale: string): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString(locale === "vi" ? "vi-VN" : "en-GB", {
    day: "2-digit",
    month: "2-digit",
  });
}

function formatHours(minutes: number, minuteSuffix: string): string {
  const hours = minutes / 60;
  return hours >= 1 ? `${hours.toFixed(hours % 1 === 0 ? 0 : 1)}h` : `${minutes}${minuteSuffix}`;
}

/** Candidate Plan Review (mockup owner-plan-review) — PM xem lộ trình AI vừa sinh, gom theo nhóm
 * task, thấy rõ task nào thiếu nguồn, sửa tay hoặc tạo lại, rồi Approve & phát hành.
 *
 * Chỉ khi plan còn DRAFT mới cho sửa/tạo lại/duyệt: sau khi APPROVED thì plan là snapshot Engineer
 * đang chạy theo (SoT rule 11), và trigger INV7 ở DB cũng không cho lùi trạng thái. */
export function PlanReviewView({
  planId,
  projectId,
  memberName,
  onBack,
  onRegenerated,
  title,
  subtitle,
  showBackButton = true,
  showApproveButton = true,
  onRegenerate,
  regenerateLabel,
}: PlanReviewViewProps) {
  const t = useTranslations("pmUi");
  const locale = useLocale();
  const [tasks, setTasks] = useState<PlanTaskResponseDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openTask, setOpenTask] = useState<PlanTaskResponseDTO | null>(null);
  const [confirmApprove, setConfirmApprove] = useState(false);
  const [approved, setApproved] = useState<OnboardingPlanResponseDTO | null>(null);
  const [busy, setBusy] = useState(false);

  async function loadTasks() {
    setLoading(true);
    setError(null);
    try {
      setTasks(await listPlanTasks(planId));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("planContentLoadError"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadTasks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [planId]);

  async function handleApprove() {
    setBusy(true);
    try {
      const plan = await approvePlan(planId);
      setApproved(plan);
      setConfirmApprove(false);
      pmToast(t("planApprovedToast"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("approvalFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function handleRegenerate() {
    // Trang lộ trình chuẩn truyền `onRegenerate` riêng (gọi API sinh bản chuẩn có AI); plan của kỹ
    // sư thì dùng regenerate mặc định.
    if (onRegenerate) {
      onRegenerate();
      return;
    }
    setBusy(true);
    try {
      onRegenerated(await regeneratePlan(planId));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("regenerationFailed"));
      setBusy(false);
    }
  }

  const missingSourceTasks = tasks.filter((t) => t.sources.length === 0);
  const totalMinutes = tasks.reduce((sum, t) => sum + t.estimated_minutes, 0);
  const isApproved = approved !== null;

  if (openTask) {
    return (
      <PlanTaskDrawer
        task={openTask}
        projectId={projectId}
        allTasks={tasks}
        onSelectTask={setOpenTask}
        editable={!isApproved}
        presentation="page"
        onClose={() => setOpenTask(null)}
        onSaved={(updated) => {
          setTasks((prev) =>
            prev.map((task) => (task.plan_task_id === updated.plan_task_id ? updated : task)),
          );
          setOpenTask(updated);
        }}
      />
    );
  }

  return (
    <section>
      <PmPageHead
        icon="check-circle"
        title={title ?? t("reviewOnboardingPlan")}
        subtitle={subtitle ?? <>{t("proposedPlanFor", { member: memberName })}</>}
        action={
          <div className={styles.headActions}>
            {showBackButton && <PmButton onClick={onBack}>{t("back")}</PmButton>}
            {!isApproved && (
              <>
                <PmButton onClick={handleRegenerate} disabled={busy}>
                  <PmIcon name="arrow" size={13} />
                  {regenerateLabel ?? t("regenerate")}
                </PmButton>
                {showApproveButton && (
                  <PmButton
                    variant="primary"
                    onClick={() => setConfirmApprove(true)}
                    disabled={busy || tasks.length === 0}
                  >
                    <PmIcon name="check2" size={13} />
                    {t("approveRelease")}
                  </PmButton>
                )}
              </>
            )}
          </div>
        }
      />

      {isApproved && (
        <div className={styles.approvedBanner}>
          <PmIcon name="check-circle" size={16} />
          <div>
            <b>{t("planApproved")}</b>
            <span>{t("planApprovedBody")}</span>
          </div>
        </div>
      )}

      {error && <p className={styles.errorBanner}>{error}</p>}

      {!loading && (
        <PmKpiRow
          items={[
            { label: t("tasks"), value: tasks.length, icon: "check-circle", variant: "accent" },
            {
              label: t("expectedDuration"),
              value: formatHours(totalMinutes, t("minuteSuffix")),
              icon: "flag",
              variant: "success",
            },
            {
              label: t("tasksMissingSources"),
              value: missingSourceTasks.length,
              icon: "alert",
              variant: missingSourceTasks.length > 0 ? "warning" : "success",
            },
          ]}
        />
      )}

      {missingSourceTasks.length > 0 && (
        <div className={styles.warningBox}>
          <PmIcon name="alert" size={14} />
          <div>
            <b>{t("missingSourcesTitle", { count: missingSourceTasks.length })}</b>
            <span>{t("missingSourcesBody")}</span>
          </div>
        </div>
      )}

      <PmSectionTitle>{t("planByCategory")}</PmSectionTitle>

      {loading ? (
        <p className={tableStyles.emptyNote}>{t("loadingPlan")}</p>
      ) : tasks.length === 0 ? (
        <PmCard>
          <p className={tableStyles.emptyNote}>{t("planHasNoTasks")}</p>
        </PmCard>
      ) : (
        <div className={styles.groupList}>
          {CATEGORY_OPTIONS.map((meta, categoryIndex) => {
            const groupTasks = tasks.filter((t) => t.category === meta.value);
            if (groupTasks.length === 0) return null;

            return (
              <div key={meta.value} className={styles.groupCard} data-variant={meta.variant}>
                <div className={styles.groupHead}>
                  <span className={styles.groupNumber}>
                    {String(categoryIndex + 1).padStart(2, "0")}
                  </span>
                  <span
                    className={`${styles.groupIcon} ${styles[VARIANT_ICON_CLASS[meta.variant]]}`}
                  >
                    <PmIcon name={meta.icon} size={14} />
                  </span>
                  <b>{t(meta.labelKey)}</b>
                  <PmTag>{t("taskCount", { count: groupTasks.length })}</PmTag>
                  <span className={styles.groupTrack}>
                    <i />
                  </span>
                </div>

                <div className={styles.groupTasks}>
                  {groupTasks.map((task) => (
                    <button
                      key={task.plan_task_id}
                      type="button"
                      className={styles.taskRow}
                      onClick={() => setOpenTask(task)}
                    >
                      <span className={styles.taskOrder}>{task.display_order}</span>
                      <span className={styles.taskTitle}>{task.title}</span>
                      <span className={styles.taskBadges}>
                        {task.sources.length === 0 ? (
                          <PmPill variant="warning">{t("missingSources")}</PmPill>
                        ) : (
                          <PmTag>{t("sourceCount", { count: task.sources.length })}</PmTag>
                        )}
                        {task.mandatory && <PmPill variant="neutral">{t("required")}</PmPill>}
                      </span>
                      <span className={styles.taskMeta}>
                        {formatHours(task.estimated_minutes, t("minuteSuffix"))} ·{" "}
                        {t("dueDate", { date: formatDate(task.due_at, locale) })}
                      </span>
                      <PmIcon name="chevron-down" size={12} className={styles.chevron} />
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {confirmApprove && (
        <PmConfirmModal
          icon="check-circle"
          tone="success"
          title={t("approvePlanTitle")}
          description={
            <>
              <p>{t("approvePlanBody")}</p>
              {missingSourceTasks.length > 0 && (
                <p className={styles.confirmWarning}>
                  {t("approveMissingSourcesWarning", { count: missingSourceTasks.length })}
                </p>
              )}
            </>
          }
          confirmLabel={t("approveRelease")}
          loading={busy}
          onConfirm={handleApprove}
          onClose={() => setConfirmApprove(false)}
        />
      )}
    </section>
  );
}
