import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  getDiscoverySchedule,
  runDiscoveryNow,
  updateDiscoverySchedule,
} from "@/features/project-management/api";
import { DiscoveryScheduleCard } from "@/features/project-management/components/documents/DiscoveryScheduleCard";
import type {
  DiscoveryScheduleResponseDTO,
  IngestionJobResponseDTO,
} from "@/features/project-management/dto/responseDTO/discoverySchedule.response";
import { ApiError } from "@/lib/api";

vi.mock("@/features/project-management/api", () => ({
  getDiscoverySchedule: vi.fn(),
  updateDiscoverySchedule: vi.fn(),
  runDiscoveryNow: vi.fn(),
}));

const succeededRun: IngestionJobResponseDTO = {
  ingestion_job_id: 4,
  status: "SUCCEEDED",
  trigger_type: "SCHEDULED",
  started_at: "2026-08-20T01:00:00",
  finished_at: "2026-08-20T01:04:00",
  new_raw_evidence_count: 12,
  total_evidence_count: 12,
  processed_evidence_count: 12,
  extraction_failure_count: 0,
  eligible_count: 5,
  families_created_count: 3,
  families_updated_count: 2,
  error_summary: null,
};

const manualSchedule: DiscoveryScheduleResponseDTO = {
  project_id: 7,
  discovery_mode: "MANUAL_ONLY",
  discovery_interval_hours: null,
  discovery_time_of_day: null,
  discovery_day_of_week: null,
  discovery_timezone: null,
  discovery_next_run_at: null,
  last_run: succeededRun,
};

describe("PM discovery schedule section", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getDiscoverySchedule).mockResolvedValue(manualSchedule);
  });

  it("states the current mode and the last run as a delta summary", async () => {
    render(<DiscoveryScheduleCard projectId={7} />);

    // Nhãn này cũng là một <option> trong select Chế độ — chỉ lấy badge trạng thái hiện tại.
    const summaryBadges = (await screen.findAllByText("Chỉ chạy thủ công")).filter(
      (element) => element.tagName !== "OPTION",
    );
    expect(summaryBadges).toHaveLength(1);
    expect(screen.getByText("Thành công")).toBeInTheDocument();
    expect(
      screen.getByText("12 bằng chứng mới · 3 quy ước mới · 2 quy ước được bổ sung bằng chứng"),
    ).toBeInTheDocument();
  });

  it("sends only the fields the chosen mode requires", async () => {
    vi.mocked(updateDiscoverySchedule).mockResolvedValue({
      ...manualSchedule,
      discovery_mode: "EVERY_N_HOURS",
      discovery_interval_hours: 6,
    });

    render(<DiscoveryScheduleCard projectId={7} />);
    await screen.findByLabelText("Chế độ");

    await userEvent.selectOptions(screen.getByLabelText("Chế độ"), "EVERY_N_HOURS");
    await userEvent.click(screen.getByRole("button", { name: "Lưu lịch" }));

    expect(updateDiscoverySchedule).toHaveBeenCalledWith(7, {
      discovery_mode: "EVERY_N_HOURS",
      discovery_interval_hours: 6,
      discovery_time_of_day: null,
      discovery_day_of_week: null,
      discovery_timezone: null,
    });
  });

  it("disables Sync now while the backend already has a run in flight", async () => {
    vi.mocked(getDiscoverySchedule).mockResolvedValue({
      ...manualSchedule,
      last_run: { ...succeededRun, status: "RUNNING", finished_at: null },
    });

    render(<DiscoveryScheduleCard projectId={7} />);

    expect(await screen.findByRole("button", { name: "Chạy ngay" })).toBeDisabled();
  });

  it("reports the backend's 409 for an overlapping run and re-reads the real state", async () => {
    vi.mocked(runDiscoveryNow).mockRejectedValue(new ApiError(409, "discovery already running"));

    render(<DiscoveryScheduleCard projectId={7} />);
    await userEvent.click(await screen.findByRole("button", { name: "Chạy ngay" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/lượt quét chạy nền/);
    await waitFor(() => expect(getDiscoverySchedule).toHaveBeenCalledTimes(2));
  });

  it("reports a failed run at summary level only, never its technical reason", async () => {
    vi.mocked(getDiscoverySchedule).mockResolvedValue({
      ...manualSchedule,
      last_run: {
        ...succeededRun,
        status: "FAILED",
        error_summary: "GitHub API rate limit exceeded",
      },
    });

    render(<DiscoveryScheduleCard projectId={7} />);

    expect(await screen.findByText("Thất bại")).toBeInTheDocument();
    expect(screen.queryByText(/rate limit/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Ch\u1ea1y ngay/ })).toBeEnabled();
  });

  it("polls while a run is in flight and stops once it reaches a terminal status", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const runningRun = { ...succeededRun, status: "RUNNING" as const, finished_at: null };
    // The polling effect fires an immediate poll at mount (not gated by the interval), so the
    // exact call count at any given timer-advance point isn't stable to assert on — resolve
    // RUNNING for the first few calls, then flip to SUCCEEDED, and assert on the eventual
    // terminal state plus "no further calls once terminal" instead.
    let calls = 0;
    vi.mocked(getDiscoverySchedule).mockImplementation(async () => {
      calls += 1;
      return { ...manualSchedule, last_run: calls <= 3 ? runningRun : succeededRun };
    });

    render(<DiscoveryScheduleCard projectId={7} />);
    await screen.findByText("Đang chạy");

    await vi.advanceTimersByTimeAsync(10_000);
    await waitFor(() => expect(screen.getByText("Thành công")).toBeInTheDocument());

    // No further calls once the run is terminal — the polling effect stopped re-arming.
    const callsAtTerminal = vi.mocked(getDiscoverySchedule).mock.calls.length;
    await vi.advanceTimersByTimeAsync(5_000);
    expect(vi.mocked(getDiscoverySchedule)).toHaveBeenCalledTimes(callsAtTerminal);

    vi.useRealTimers();
  });
});
