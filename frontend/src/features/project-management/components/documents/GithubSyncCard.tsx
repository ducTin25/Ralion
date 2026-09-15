"use client";

import { useEffect, useId, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import {
  connectGithubRepo,
  getGithubSyncStatus,
  syncProjectFromGithub,
} from "@/features/project-management/api";
import type { ProjectResponseDTO } from "@/features/project-management/dto/responseDTO/project.response";
import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import { PmCard, PmSectionTitle } from "@/features/project-management/components/ui/PmCard";
import { PmButton } from "@/features/project-management/components/ui/PmButton";
import { PmField, PmInput } from "@/features/project-management/components/ui/PmField";
import { PmPill } from "@/features/project-management/components/ui/PmPill";
import { pmToast } from "@/features/project-management/components/ui/PmToast";
import { ApiError } from "@/lib/api";
import { notifyProjectOperationCompleted } from "@/lib/projectOperationNotifications";

import styles from "./GithubSyncCard.module.scss";

type SyncStatus = ProjectResponseDTO["sync_status"];

const STATUS_META: Record<
  SyncStatus,
  {
    labelKey:
      "statusNotStarted" | "statusSyncing" | "statusSuccess" | "statusPartial" | "statusFailed";
    variant: "neutral" | "progress" | "success" | "warning" | "critical";
  }
> = {
  NOT_STARTED: { labelKey: "statusNotStarted", variant: "neutral" },
  SYNCING: { labelKey: "statusSyncing", variant: "progress" },
  SUCCESS: { labelKey: "statusSuccess", variant: "success" },
  PARTIAL: {
    labelKey: "statusPartial",
    variant: "warning",
  },
  FAILED: { labelKey: "statusFailed", variant: "critical" },
};

/** `github_repo` luôn có giá trị "pending/<key>" ngay từ lúc tạo project (xem
 * project_service.create_project) — đây KHÔNG phải một repo thật, chỉ là chỗ giữ chỗ chờ PM kết
 * nối repo thật qua form dưới đây. */
export function isGithubRepoConfigured(githubRepo: string | null): boolean {
  return !!githubRepo && !githubRepo.startsWith("pending/");
}

function formatSyncedAt(value: string | null, locale: string): string | null {
  if (!value) return null;
  return new Intl.DateTimeFormat(locale === "vi" ? "vi-VN" : "en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

type GithubSyncCardProps = {
  project: ProjectResponseDTO;
  onProjectUpdated: (project: ProjectResponseDTO) => void;
};

/** Đường đồng bộ tài liệu dự án thứ 2 — bên cạnh "Quét repository" (chọn thư mục local) và "Tải
 * lên" (từng file) đã có trong DocumentsView. Đồng bộ thẳng từ 1 nhánh GitHub qua
 * `github_sync_worker.sync_docs` (đã có sẵn ở backend, trước đây chưa có endpoint nào gọi tới).
 * Không viết pipeline import thứ hai: cả 3 đường đều đổ vào cùng knowledge_document_service. */
export function GithubSyncCard({ project, onProjectUpdated }: GithubSyncCardProps) {
  const t = useTranslations("pm.githubSync");
  const locale = useLocale();
  const fieldId = useId();
  const repoFieldId = `${fieldId}-repo`;
  const branchFieldId = `${fieldId}-branch`;
  const tokenFieldId = `${fieldId}-token`;
  const configured = isGithubRepoConfigured(project.github_repo);
  const [editing, setEditing] = useState(!configured);
  const [repoInput, setRepoInput] = useState(configured ? (project.github_repo ?? "") : "");
  const [branchInput, setBranchInput] = useState(project.default_branch ?? "main");
  const [tokenInput, setTokenInput] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const announcedSyncRef = useRef<number | null>(null);
  const onProjectUpdatedRef = useRef(onProjectUpdated);

  useEffect(() => {
    onProjectUpdatedRef.current = onProjectUpdated;
  }, [onProjectUpdated]);

  const statusMeta = STATUS_META[project.sync_status];
  const syncJobInFlight =
    project.github_sync_job?.status === "RUNNING" || project.github_sync_job?.status === "PENDING";
  const busy = connecting || syncing || syncJobInFlight;

  // The project-list endpoint does not carry operation history. Re-read the dedicated status
  // endpoint on mount so a refreshed page immediately recovers an in-flight backend job.
  useEffect(() => {
    let cancelled = false;
    void getGithubSyncStatus(project.project_id)
      .then((updated) => {
        if (!cancelled) onProjectUpdatedRef.current(updated);
      })
      .catch(() => {
        // Status remains backend-owned; a transient read error is retried by a later mount/action.
      });
    return () => {
      cancelled = true;
    };
  }, [project.project_id]);

  useEffect(() => {
    if (!syncJobInFlight) return;

    let cancelled = false;
    const poll = async () => {
      try {
        const updated = await getGithubSyncStatus(project.project_id);
        if (cancelled) return;
        onProjectUpdatedRef.current(updated);
        const completedJob = updated.github_sync_job;
        if (
          (completedJob?.status === "SUCCEEDED" || completedJob?.status === "FAILED") &&
          completedJob.ingestion_job_id !== announcedSyncRef.current
        ) {
          announcedSyncRef.current = completedJob.ingestion_job_id;
          const status = completedJob.status;
          const errorSummary = completedJob.error_summary ?? null;
          notifyProjectOperationCompleted({
            projectId: updated.project_id,
            operation: "GITHUB_SYNC",
            status,
            completedAt: completedJob.finished_at ?? updated.last_synced_at ?? new Date().toISOString(),
            repo: updated.github_repo,
            documentsImported: completedJob.processed_evidence_count,
            errorSummary,
          });
          if (status === "SUCCEEDED") {
            pmToast(t("finished", { repo: updated.github_repo ?? t("repository") }));
          } else {
            setError(errorSummary ?? t("failedHelp"));
          }
        }
      } catch {
        // The job continues on the server. Keep the current status and retry on the next poll.
      }
    };

    void poll();
    const timer = window.setInterval(() => void poll(), 2_500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [project.project_id, project.github_sync_job?.ingestion_job_id, syncJobInFlight, t]);

  async function handleConnect() {
    const repo = repoInput.trim();
    const token = tokenInput.trim();
    if (!repo || !token) return;
    setConnecting(true);
    setError(null);
    try {
      const updated = await connectGithubRepo(
        project.project_id,
        repo,
        branchInput.trim() || "main",
        token,
      );
      pmToast(t("connected", { repo: updated.github_repo ?? repo }));
      setEditing(false);
      setTokenInput("");
      onProjectUpdated(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("connectError"));
    } finally {
      setConnecting(false);
    }
  }

  async function handleSyncNow() {
    setSyncing(true);
    setError(null);
    try {
      const updated = await syncProjectFromGithub(project.project_id);
      pmToast(t("started"));
      onProjectUpdated(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("syncError"));
    } finally {
      setSyncing(false);
    }
  }

  function handleCancelEditing() {
    setRepoInput(project.github_repo ?? "");
    setBranchInput(project.default_branch ?? "main");
    setTokenInput("");
    setError(null);
    setEditing(false);
  }

  return (
    <>
      <PmSectionTitle>{t("title")}</PmSectionTitle>
      <PmCard className="mb-4">
        {error && (
          <p className="mb-3 text-[13px] leading-5 text-critical" role="alert">
            {error}
          </p>
        )}

        {editing ? (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-3">
              <PmField label={t("repository")} htmlFor={repoFieldId}>
                <PmInput
                  id={repoFieldId}
                  value={repoInput}
                  onChange={(e) => setRepoInput(e.target.value)}
                  placeholder="octocat/Hello-World"
                  disabled={connecting}
                />
              </PmField>
              <PmField label={t("defaultBranch")} htmlFor={branchFieldId}>
                <PmInput
                  id={branchFieldId}
                  value={branchInput}
                  onChange={(e) => setBranchInput(e.target.value)}
                  placeholder="main"
                  disabled={connecting}
                />
              </PmField>
              <div className="min-w-[260px] flex-1">
                <PmField label={t("accessToken")} htmlFor={tokenFieldId}>
                  <PmInput
                    id={tokenFieldId}
                    type="password"
                    autoComplete="off"
                    value={tokenInput}
                    onChange={(e) => setTokenInput(e.target.value)}
                    placeholder={t("accessTokenPlaceholder")}
                    disabled={connecting}
                  />
                </PmField>
              </div>
              <PmButton
                variant="primary"
                disabled={connecting || !repoInput.trim() || !tokenInput.trim()}
                onClick={handleConnect}
              >
                {connecting ? t("connecting") : t("connect")}
              </PmButton>
              {configured && (
                <PmButton onClick={handleCancelEditing} disabled={connecting}>
                  {t("cancel")}
                </PmButton>
              )}
            </div>
            <p className="text-[12.5px] leading-5 text-text-subtle">{t("accessTokenHint")}</p>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2.5 text-[13.5px]">
                <PmPill variant={statusMeta.variant}>{t(statusMeta.labelKey)}</PmPill>
                <span className="font-medium text-text">
                  {project.github_repo} @ {project.default_branch}
                </span>
                {project.github_credential_status === "VALID" && (
                  <span className="inline-flex items-center gap-1 text-success">
                    <PmIcon name="check-circle" size={12} />
                    {t("credentialValid")}
                  </span>
                )}
                <span className="text-text-subtle">
                  {t("lastSynced", {
                    value: formatSyncedAt(project.last_synced_at, locale) ?? t("never"),
                  })}
                </span>
              </div>
              <div className="flex gap-2">
                <PmButton size="sm" onClick={() => setEditing(true)} disabled={busy}>
                  {t("changeRepository")}
                </PmButton>
                <PmButton size="sm" variant="primary" disabled={busy} onClick={handleSyncNow}>
                  {syncing || syncJobInFlight ? t("syncing") : t("syncNow")}
                </PmButton>
              </div>
            </div>

            {project.github_credential_status === "INVALID" && (
              <div className={`${styles.notice} ${styles.noticeCritical}`} role="alert">
                <PmIcon name="alert" size={14} />
                <span>{t("credentialInvalid")}</span>
                <PmButton size="sm" disabled={busy} onClick={() => setEditing(true)}>
                  {t("reconnect")}
                </PmButton>
              </div>
            )}
            {project.github_credential_status === null && (
              <div className={styles.notice} role="status">
                <PmIcon name="key" size={14} />
                <span>{t("credentialMissing")}</span>
                <PmButton size="sm" disabled={busy} onClick={() => setEditing(true)}>
                  {t("connectToken")}
                </PmButton>
              </div>
            )}
          </div>
        )}
      </PmCard>
    </>
  );
}
