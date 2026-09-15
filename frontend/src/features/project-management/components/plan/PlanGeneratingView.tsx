"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import { getPlanGenerationJob } from "@/features/project-management/api";
import type { PlanGenerationJobResponseDTO } from "@/features/project-management/dto/responseDTO/planGenerationJob.response";
import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import { PmButton } from "@/features/project-management/components/ui/PmButton";
import { PmCard, PmPageHead } from "@/features/project-management/components/ui/PmCard";

import styles from "./PlanGeneratingView.module.scss";

const POLL_INTERVAL_MS = 1000;

const STEP_LABEL_KEYS: Record<string, string> = {
  load_template: "generationLoadTemplate",
  merge_company_core: "generationMergeCore",
  collect_project_docs: "generationCollectDocuments",
  map_task_sources: "generationMapSources",
  generate_content: "generationWriteContent",
  validate_and_persist: "generationValidateSave",
};

const STEP_DETAIL_KEYS: Record<string, string> = {
  load_template: "generationLoadTemplateDetail",
  merge_company_core: "generationMergeCoreDetail",
  collect_project_docs: "generationCollectDocumentsDetail",
  map_task_sources: "generationMapSourcesDetail",
  generate_content: "generationWriteContentDetail",
  validate_and_persist: "generationValidateSaveDetail",
};

type PlanGeneratingViewProps = {
  job: PlanGenerationJobResponseDTO;
  memberName: string;
  onDone: (planId: number) => void;
  onCancel: () => void;
};

function formatDuration(ms: number | null): string {
  if (ms === null) return "";
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

/** Màn hình chờ khi hệ thống đang ghép Candidate Plan (mockup owner-plan-generating).
 *
 * Tiến độ là DỮ LIỆU THẬT chứ không phải animation: FE poll `/generate/{job_id}` mỗi giây, backend
 * trả về trạng thái + `duration_ms` thật của từng bước trong 6 bước. Vì bước gọi LLM mất ~30s nên
 * bắt buộc phải tách job nền + poll, không thể để 1 request đồng bộ treo màn hình. */
export function PlanGeneratingView({ job, memberName, onDone, onCancel }: PlanGeneratingViewProps) {
  const t = useTranslations("pmUi");
  const [current, setCurrent] = useState<PlanGenerationJobResponseDTO>(job);
  const [pollError, setPollError] = useState<string | null>(null);
  const notifiedRef = useRef(false);

  useEffect(() => {
    if (current.status !== "RUNNING") return;
    let cancelled = false;

    const timer = setInterval(async () => {
      try {
        const next = await getPlanGenerationJob(job.job_id);
        if (!cancelled) {
          setCurrent(next);
          setPollError(null);
        }
      } catch (err) {
        // Lỗi mạng 1 nhịp không nên giết cả màn hình — giữ nguyên tiến độ cũ, thử lại nhịp sau.
        if (!cancelled)
          setPollError(err instanceof Error ? err.message : t("temporarilyDisconnected"));
      }
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [current.status, job.job_id, t]);

  useEffect(() => {
    if (current.status === "DONE" && current.plan_id !== null && !notifiedRef.current) {
      notifiedRef.current = true;
      onDone(current.plan_id);
    }
  }, [current.status, current.plan_id, onDone]);

  const doneCount = current.steps.filter((s) => s.status === "DONE").length;

  return (
    <section>
      <PmPageHead
        icon="check-circle"
        title={t("generatingPlan")}
        subtitle={t("planFor", { member: memberName })}
      />

      <PmCard>
        <div className={styles.progressHead}>
          <span className={styles.progressCount}>
            {t("stepProgress", { done: doneCount, total: current.steps.length })}
          </span>
          {current.status === "RUNNING" && <span className={styles.runningNote}>{t("running")}</span>}
          {current.total_duration_ms !== null && (
            <span className={styles.totalTime}>
              {t("totalDuration", { duration: formatDuration(current.total_duration_ms) })}
            </span>
          )}
        </div>

        <ol className={styles.stepList}>
          {current.steps.map((step, index) => (
            <li key={step.key} className={`${styles.step} ${styles[step.status.toLowerCase()]}`}>
              <span className={styles.stepIcon}>
                {step.status === "DONE" && <PmIcon name="check2" size={13} />}
                {step.status === "FAILED" && <PmIcon name="alert" size={13} />}
                {step.status === "RUNNING" && <span className={styles.spinner} />}
                {step.status === "PENDING" && <span className={styles.dot}>{index + 1}</span>}
              </span>
              <div className={styles.stepBody}>
                <b>{STEP_LABEL_KEYS[step.key] ? t(STEP_LABEL_KEYS[step.key]) : step.label}</b>
                <span className={styles.stepDetail}>
                  {step.detail ?? (STEP_DETAIL_KEYS[step.key] ? t(STEP_DETAIL_KEYS[step.key]) : "")}
                </span>
                {step.status === "RUNNING" && step.progress_total !== null && step.progress_total > 0 && (
                  <div className={styles.taskProgress}>
                    <progress value={step.progress_done ?? 0} max={step.progress_total} />
                    <span>
                      {Math.round(((step.progress_done ?? 0) / step.progress_total) * 100)}%
                      {step.document_count !== null ? ` · ${step.document_count} tài liệu` : ""}
                      {` · ${step.progress_done ?? 0}/${step.progress_total} task`}
                    </span>
                  </div>
                )}
              </div>
              <span className={styles.stepTime}>{formatDuration(step.duration_ms)}</span>
            </li>
          ))}
        </ol>

        {current.status === "FAILED" && (
          <div className={styles.errorBox}>
            <b>{t("planGenerationFailed")}</b>
            <p>{current.error}</p>
            <PmButton onClick={onCancel}>{t("backToMembers")}</PmButton>
          </div>
        )}

        {pollError && current.status === "RUNNING" && (
          <p className={styles.pollNote}>{t("retryingConnection", { error: pollError })}</p>
        )}

        <p className={styles.correlation}>
          {t("traceId")}: <code>{current.correlation_id}</code>
        </p>
      </PmCard>
    </section>
  );
}
