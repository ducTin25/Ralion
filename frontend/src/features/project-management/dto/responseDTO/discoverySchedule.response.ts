export type DiscoveryMode = "MANUAL_ONLY" | "EVERY_N_HOURS" | "DAILY_AT" | "WEEKLY_AT";
export type IngestionJobStatus = "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED";
export type IngestionJobTriggerType = "MANUAL" | "SCHEDULED";

/** Run status/counts only — never model, concurrency, embedding batch size, cosine threshold,
 * or retry policy (backend DTO deliberately has no such field, see CLAUDE.md F6 playbook §5). */
export type IngestionJobResponseDTO = {
  ingestion_job_id: number;
  status: IngestionJobStatus;
  trigger_type: IngestionJobTriggerType;
  started_at: string | null;
  finished_at: string | null;
  new_raw_evidence_count: number;
  total_evidence_count: number;
  processed_evidence_count: number;
  extraction_failure_count: number;
  eligible_count: number;
  families_created_count: number;
  families_updated_count: number;
  error_summary: string | null;
};

export type DiscoveryScheduleResponseDTO = {
  project_id: number;
  discovery_mode: DiscoveryMode;
  discovery_interval_hours: number | null;
  discovery_time_of_day: string | null;
  discovery_day_of_week: number | null;
  discovery_timezone: string | null;
  discovery_next_run_at: string | null;
  last_run: IngestionJobResponseDTO | null;
};

export type DiscoveryScheduleUpdateInput = {
  discovery_mode: DiscoveryMode;
  discovery_interval_hours?: number | null;
  discovery_time_of_day?: string | null;
  discovery_day_of_week?: number | null;
  discovery_timezone?: string | null;
};
