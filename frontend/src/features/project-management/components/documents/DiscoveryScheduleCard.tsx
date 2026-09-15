"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import {
  getDiscoverySchedule,
  runDiscoveryNow,
  updateDiscoverySchedule,
} from "@/features/project-management/api";
import type {
  DiscoveryMode,
  DiscoveryScheduleResponseDTO,
  IngestionJobResponseDTO,
} from "@/features/project-management/dto/responseDTO/discoverySchedule.response";
import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import { PmCard, PmSectionTitle } from "@/features/project-management/components/ui/PmCard";
import { PmButton } from "@/features/project-management/components/ui/PmButton";
import { PmField, PmInput, PmSelect } from "@/features/project-management/components/ui/PmField";
import { PmPill } from "@/features/project-management/components/ui/PmPill";
import { pmToast } from "@/features/project-management/components/ui/PmToast";
import { ApiError } from "@/lib/api";
import { formatServerDateTime } from "@/lib/datetime";
import { notifyProjectOperationCompleted } from "@/lib/projectOperationNotifications";

import styles from "./DiscoveryScheduleCard.module.scss";

const MODE_LABEL_KEYS = {
  MANUAL_ONLY: "modeManual",
  EVERY_N_HOURS: "modeHourly",
  DAILY_AT: "modeDaily",
  WEEKLY_AT: "modeWeekly",
} as const satisfies Record<DiscoveryMode, string>;

/** Backend dùng 0 = Thứ Hai (`discovery_day_of_week` 0..6, xem CHECK constraint trên `projects`). */
const WEEKDAY_LABEL_KEYS = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday",
] as const;

const JOB_STATUS_META: Record<
  IngestionJobResponseDTO["status"],
  {
    labelKey: "statusPending" | "statusRunning" | "statusSucceeded" | "statusFailed";
    variant: "neutral" | "progress" | "success" | "critical";
  }
> = {
  PENDING: { labelKey: "statusPending", variant: "neutral" },
  RUNNING: { labelKey: "statusRunning", variant: "progress" },
  SUCCEEDED: { labelKey: "statusSucceeded", variant: "success" },
  FAILED: { labelKey: "statusFailed", variant: "critical" },
};

/** Danh sách IANA của trình duyệt; nếu runtime không hỗ trợ thì rơi về ô nhập tay để không
 * chặn PM lưu lịch. Nhập sai tên vùng sẽ bị backend trả 422. */
function supportedTimezones(): string[] | null {
  const supportedValuesOf = (
    Intl as typeof Intl & { supportedValuesOf?: (key: string) => string[] }
  ).supportedValuesOf;
  if (typeof supportedValuesOf !== "function") return null;
  try {
    return supportedValuesOf("timeZone");
  } catch {
    return null;
  }
}

function isInFlight(lastRun: IngestionJobResponseDTO | null) {
  return lastRun?.status === "RUNNING" || lastRun?.status === "PENDING";
}

/**
 * F6 Scheduled Incremental Convention Discovery (UI_SPEC B.4) — section trong màn Tài liệu dự
 * án, không phải page riêng.
 *
 * Chỉ 4 chế độ backend hỗ trợ (MANUAL_ONLY/EVERY_N_HOURS/DAILY_AT/WEEKLY_AT): không nhập cron
 * thô, không hiện model/concurrency/embedding batch/ngưỡng cosine/retry policy (DTO backend
 * không có field đó). Cũng không có sync history/log — chỉ tóm tắt lần chạy gần nhất, đúng
 * ranh giới đã chốt.
 *
 * Tính idempotent khi 2 trigger chồng nhau là trách nhiệm của backend (`AlreadyRunningError` →
 * HTTP 409); ở đây chỉ vô hiệu hoá nút khi đã biết có lượt chạy in-flight và hiển thị đúng khi
 * backend từ chối. Không mô phỏng lại logic đó ở client.
 */
export function DiscoveryScheduleCard({ projectId }: { projectId: number }) {
  const t = useTranslations("pm.discovery");
  const locale = useLocale();
  const [schedule, setSchedule] = useState<DiscoveryScheduleResponseDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [runningNow, setRunningNow] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [mode, setMode] = useState<DiscoveryMode>("MANUAL_ONLY");
  const [intervalHours, setIntervalHours] = useState(6);
  const [timeOfDay, setTimeOfDay] = useState("09:00");
  const [dayOfWeek, setDayOfWeek] = useState(0);
  const [timezone, setTimezone] = useState(
    Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
  );
  const [timezoneOptions] = useState(supportedTimezones);

  const fieldId = useId();
  const modeId = `${fieldId}-mode`;
  const intervalId = `${fieldId}-interval`;
  const timeId = `${fieldId}-time`;
  const timezoneId = `${fieldId}-timezone`;
  const weekdayId = `${fieldId}-weekday`;
  const dateLocale = locale === "vi" ? "vi-VN" : "en-GB";

  const scheduleSummary = (value: DiscoveryScheduleResponseDTO) => {
    const time = (value.discovery_time_of_day ?? "").slice(0, 5);
    const zone = value.discovery_timezone ?? "UTC";
    switch (value.discovery_mode) {
      case "EVERY_N_HOURS":
        return t("summaryHourly", { hours: value.discovery_interval_hours ?? "?" });
      case "DAILY_AT":
        return t("summaryDaily", { time, zone });
      case "WEEKLY_AT":
        return t("summaryWeekly", {
          day: t(WEEKDAY_LABEL_KEYS[value.discovery_day_of_week ?? 0]),
          time,
          zone,
        });
      default:
        return t("modeManual");
    }
  };

  const lastRunSummary = (lastRun: IngestionJobResponseDTO) => {
    if (lastRun.status === "FAILED") return t("lastRunFailed");
    if (lastRun.status === "RUNNING" || lastRun.status === "PENDING") {
      return t("scanning");
    }
    return t("lastRunDelta", {
      evidence: lastRun.new_raw_evidence_count,
      created: lastRun.families_created_count,
      updated: lastRun.families_updated_count,
    });
  };

  const applySchedule = useCallback((data: DiscoveryScheduleResponseDTO) => {
    setSchedule(data);
    setMode(data.discovery_mode);
    if (data.discovery_interval_hours) setIntervalHours(data.discovery_interval_hours);
    if (data.discovery_time_of_day) setTimeOfDay(data.discovery_time_of_day.slice(0, 5));
    if (data.discovery_day_of_week !== null) setDayOfWeek(data.discovery_day_of_week);
    if (data.discovery_timezone) setTimezone(data.discovery_timezone);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      applySchedule(await getDiscoverySchedule(projectId));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("loadError"));
    } finally {
      setLoading(false);
    }
  }, [applySchedule, projectId, t]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  // `run-now` returns as soon as the run is RUNNING (background job, CHANGE_LOG.md — a real
  // repo's ingest+mining can take minutes) — poll until it reaches a terminal status, exactly
  // the pattern GithubSyncCard already uses for `POST .../github-sync`. Because `load()` above
  // already re-fetches `last_run` on mount, a page reload while a run is in flight resumes
  // polling on its own; no extra "was it running before I left" state is needed.
  const announcedRunIdRef = useRef<number | null>(null);
  const shouldPoll = isInFlight(schedule?.last_run ?? null);
  useEffect(() => {
    if (!shouldPoll) return;

    let cancelled = false;
    const poll = async () => {
      try {
        const updated = await getDiscoverySchedule(projectId);
        if (cancelled) return;
        applySchedule(updated);
        const finished = updated.last_run;
        if (
          finished &&
          !isInFlight(finished) &&
          finished.ingestion_job_id !== announcedRunIdRef.current
        ) {
          announcedRunIdRef.current = finished.ingestion_job_id;
          if (finished.status === "SUCCEEDED") {
            pmToast(
              t("finished", {
                created: finished.families_created_count,
                updated: finished.families_updated_count,
              }),
            );
            notifyProjectOperationCompleted({
              projectId,
              operation: "CONVENTION_DISCOVERY",
              status: "SUCCEEDED",
              completedAt: finished.finished_at ?? new Date().toISOString(),
              familiesCreated: finished.families_created_count,
              familiesUpdated: finished.families_updated_count,
            });
          } else if (finished.status === "FAILED") {
            const errorSummary = finished.error_summary ?? null;
            setError(errorSummary ?? t("failedSummary"));
            notifyProjectOperationCompleted({
              projectId,
              operation: "CONVENTION_DISCOVERY",
              status: "FAILED",
              completedAt: finished.finished_at ?? new Date().toISOString(),
              errorSummary,
            });
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
  }, [applySchedule, projectId, shouldPoll, t]);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const scheduled = mode === "DAILY_AT" || mode === "WEEKLY_AT";
      applySchedule(
        await updateDiscoverySchedule(projectId, {
          discovery_mode: mode,
          discovery_interval_hours: mode === "EVERY_N_HOURS" ? intervalHours : null,
          discovery_time_of_day: scheduled ? `${timeOfDay}:00` : null,
          discovery_day_of_week: mode === "WEEKLY_AT" ? dayOfWeek : null,
          discovery_timezone: scheduled ? timezone : null,
        }),
      );
      pmToast(t("saved"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("saveError"));
    } finally {
      setSaving(false);
    }
  }

  async function handleRunNow() {
    setRunningNow(true);
    setError(null);
    try {
      applySchedule(await runDiscoveryNow(projectId));
      pmToast(t("started"));
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        // Backend đã có một lượt chạy in-flight và từ chối trigger thứ hai. Tải lại trước để
        // UI phản ánh đúng trạng thái thật, rồi mới đặt thông báo — `load()` tự xoá error nên
        // đảo thứ tự sẽ nuốt mất thông báo này.
        await load();
        setError(t("alreadyRunning"));
        return;
      }
      setError(err instanceof Error ? err.message : t("startError"));
    } finally {
      setRunningNow(false);
    }
  }

  const lastRun = schedule?.last_run ?? null;
  const inFlight = shouldPoll;
  const statusMeta = lastRun ? JOB_STATUS_META[lastRun.status] : null;

  return (
    <>
      <PmSectionTitle hint={t("hint")}>{t("title")}</PmSectionTitle>
      <PmCard className={styles.card}>
        {loading ? (
          <p className={styles.mutedText}>{t("loading")}</p>
        ) : (
          <>
            <div className={styles.summaryRow}>
              <PmPill variant={schedule?.discovery_mode === "MANUAL_ONLY" ? "neutral" : "success"}>
                <PmIcon name="check-circle" size={13} />
                {schedule ? scheduleSummary(schedule) : t("modeManual")}
              </PmPill>
              {schedule?.discovery_mode !== "MANUAL_ONLY" && (
                <span>
                  {t("nextRun")}:{" "}
                  <strong>
                    {formatServerDateTime(schedule?.discovery_next_run_at ?? null, dateLocale)}
                  </strong>
                </span>
              )}
            </div>

            {error && (
              <p className={styles.errorText} role="alert">
                {error}
              </p>
            )}

            <div className={styles.row}>
              <div className={styles.field}>
                <PmField label={t("mode")} htmlFor={modeId}>
                  <PmSelect
                    id={modeId}
                    value={mode}
                    onChange={(e) => setMode(e.target.value as DiscoveryMode)}
                  >
                    {Object.entries(MODE_LABEL_KEYS).map(([value, labelKey]) => (
                      <option key={value} value={value}>
                        {t(labelKey)}
                      </option>
                    ))}
                  </PmSelect>
                </PmField>
              </div>

              {mode === "EVERY_N_HOURS" && (
                <div className={styles.field}>
                  <PmField label={t("everyHours")} htmlFor={intervalId}>
                    <PmInput
                      id={intervalId}
                      type="number"
                      min={1}
                      value={intervalHours}
                      onChange={(e) => setIntervalHours(Number(e.target.value) || 1)}
                    />
                  </PmField>
                </div>
              )}

              {(mode === "DAILY_AT" || mode === "WEEKLY_AT") && (
                <>
                  <div className={styles.field}>
                    <PmField label={t("runTime")} htmlFor={timeId}>
                      <PmInput
                        id={timeId}
                        type="time"
                        value={timeOfDay}
                        onChange={(e) => setTimeOfDay(e.target.value)}
                      />
                    </PmField>
                  </div>
                  <div className={styles.fieldWide}>
                    <PmField label={t("timeZone")} htmlFor={timezoneId}>
                      {timezoneOptions ? (
                        <PmSelect
                          id={timezoneId}
                          value={timezone}
                          onChange={(e) => setTimezone(e.target.value)}
                        >
                          {timezoneOptions.map((zone) => (
                            <option key={zone} value={zone}>
                              {zone}
                            </option>
                          ))}
                        </PmSelect>
                      ) : (
                        <PmInput
                          id={timezoneId}
                          value={timezone}
                          placeholder="Asia/Ho_Chi_Minh"
                          onChange={(e) => setTimezone(e.target.value)}
                        />
                      )}
                    </PmField>
                  </div>
                </>
              )}

              {mode === "WEEKLY_AT" && (
                <div className={styles.field}>
                  <PmField label={t("dayOfWeek")} htmlFor={weekdayId}>
                    <PmSelect
                      id={weekdayId}
                      value={dayOfWeek}
                      onChange={(e) => setDayOfWeek(Number(e.target.value))}
                    >
                      {WEEKDAY_LABEL_KEYS.map((labelKey, index) => (
                        <option key={labelKey} value={index}>
                          {t(labelKey)}
                        </option>
                      ))}
                    </PmSelect>
                  </PmField>
                </div>
              )}

              <div className={styles.actions}>
                <PmButton variant="primary" size="sm" disabled={saving} onClick={handleSave}>
                  {saving ? t("saving") : t("save")}
                </PmButton>
                <PmButton
                  size="sm"
                  disabled={runningNow || inFlight}
                  title={inFlight ? t("runningHint") : undefined}
                  onClick={handleRunNow}
                >
                  {runningNow ? t("running") : t("runNow")}
                </PmButton>
              </div>
            </div>

            <div className={styles.statusRow}>
              {lastRun && statusMeta ? (
                <>
                  <span className={styles.statusLabel}>{t("lastRun")}</span>
                  <PmPill variant={statusMeta.variant}>{t(statusMeta.labelKey)}</PmPill>
                  <span>
                    {formatServerDateTime(lastRun.finished_at ?? lastRun.started_at, dateLocale)}
                  </span>
                  <span className={styles.delta}>{lastRunSummary(lastRun)}</span>
                </>
              ) : (
                <span className={styles.mutedText}>{t("noScans")}</span>
              )}
            </div>
          </>
        )}
      </PmCard>
    </>
  );
}
