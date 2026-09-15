import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { connectGithubRepo, getGithubSyncStatus } from "@/features/project-management/api";
import type { ProjectResponseDTO } from "@/features/project-management/dto/responseDTO/project.response";
import { GithubSyncCard } from "@/features/project-management/components/documents/GithubSyncCard";
import { notifyProjectOperationCompleted } from "@/lib/projectOperationNotifications";

vi.mock("@/features/project-management/api", () => ({
  connectGithubRepo: vi.fn(),
  getGithubSyncStatus: vi.fn(),
  syncProjectFromGithub: vi.fn(),
}));

vi.mock("@/lib/projectOperationNotifications", () => ({
  notifyProjectOperationCompleted: vi.fn(),
}));

const baseProject: ProjectResponseDTO = {
  project_id: 7,
  key: "PROJ",
  name: "Project",
  primary_pm_membership_id: 1,
  created_by_admin_id: 1,
  status: "ACTIVE",
  sync_status: "SUCCESS",
  last_synced_at: "2026-08-20T10:00:00",
  created_at: "2026-08-01T00:00:00",
  github_repo: "thanos-io/thanos",
  default_branch: "main",
  github_credential_status: "VALID",
  github_sync_job: null,
};

describe("GithubSyncCard credential status", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getGithubSyncStatus).mockResolvedValue(baseProject);
  });

  it("shows a quiet verified indicator when the connected credential is VALID", () => {
    render(<GithubSyncCard project={baseProject} onProjectUpdated={vi.fn()} />);

    expect(screen.getByText("Token đã xác minh")).toBeInTheDocument();
    expect(screen.queryByText(/Kết nối lại|Kết nối token/)).not.toBeInTheDocument();
  });

  it("surfaces a reconnect banner and jumps into the connect form when the credential is INVALID", async () => {
    const project: ProjectResponseDTO = { ...baseProject, github_credential_status: "INVALID" };
    render(<GithubSyncCard project={project} onProjectUpdated={vi.fn()} />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Personal Access Token đã kết nối bị GitHub từ chối",
    );
    expect(screen.queryByText("Token đã xác minh")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Kết nối lại" }));

    expect(screen.getByLabelText("Personal Access Token")).toBeInTheDocument();
    // The repo/branch fields stay prefilled; only the token needs to be re-entered.
    expect(screen.getByDisplayValue("thanos-io/thanos")).toBeInTheDocument();
  });

  it("surfaces a distinct notice for a legacy repo with no per-project credential connected", () => {
    const project: ProjectResponseDTO = { ...baseProject, github_credential_status: null };
    render(<GithubSyncCard project={project} onProjectUpdated={vi.fn()} />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "chưa có Personal Access Token riêng cho project",
    );
    expect(screen.getByRole("button", { name: "Kết nối token" })).toBeInTheDocument();
  });

  it("reflects a fresh VALID status returned by connect without a page reload", async () => {
    const project: ProjectResponseDTO = { ...baseProject, github_credential_status: "INVALID" };
    const onProjectUpdated = vi.fn();
    vi.mocked(connectGithubRepo).mockResolvedValue({
      ...baseProject,
      github_credential_status: "VALID",
    });

    const { rerender } = render(
      <GithubSyncCard project={project} onProjectUpdated={onProjectUpdated} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Kết nối lại" }));
    await userEvent.type(screen.getByLabelText("Personal Access Token"), "ghp_newtoken");
    await userEvent.click(screen.getByRole("button", { name: "Kết nối repository" }));

    expect(connectGithubRepo).toHaveBeenCalledWith(7, "thanos-io/thanos", "main", "ghp_newtoken");
    expect(onProjectUpdated).toHaveBeenCalledWith(
      expect.objectContaining({ github_credential_status: "VALID" }),
    );

    rerender(
      <GithubSyncCard
        project={{ ...baseProject, github_credential_status: "VALID" }}
        onProjectUpdated={onProjectUpdated}
      />,
    );
    expect(screen.getByText("Token đã xác minh")).toBeInTheDocument();
  });

  it("clears an entered token when editing is cancelled", async () => {
    render(<GithubSyncCard project={baseProject} onProjectUpdated={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: "Đổi repository" }));
    await userEvent.type(screen.getByLabelText("Personal Access Token"), "github_pat_secret");
    await userEvent.click(screen.getByRole("button", { name: "Hủy" }));
    await userEvent.click(screen.getByRole("button", { name: "Đổi repository" }));

    expect(screen.getByLabelText("Personal Access Token")).toHaveValue("");
  });

  it("checks backend job state once on mount so refresh can recover a running sync", async () => {
    render(<GithubSyncCard project={baseProject} onProjectUpdated={vi.fn()} />);
    await vi.waitFor(() => expect(getGithubSyncStatus).toHaveBeenCalledTimes(1));
  });

  it("keeps Sync now disabled from the persisted backend job state", () => {
    const project: ProjectResponseDTO = {
      ...baseProject,
      github_sync_job: {
        ingestion_job_id: 91,
        status: "RUNNING",
        trigger_type: "MANUAL",
        started_at: "2026-08-20T10:01:00",
        finished_at: null,
        new_raw_evidence_count: 0,
        total_evidence_count: 0,
        processed_evidence_count: 0,
        extraction_failure_count: 0,
        eligible_count: 0,
        families_created_count: 0,
        families_updated_count: 0,
        error_summary: null,
      },
    };
    vi.mocked(getGithubSyncStatus).mockResolvedValue(project);

    render(<GithubSyncCard project={project} onProjectUpdated={vi.fn()} />);

    expect(screen.getByRole("button", { name: /\u0110ang \u0111\u1ed3ng b\u1ed9/ })).toBeDisabled();
  });

  it("re-enables Sync now after a backend job fails", () => {
    const project: ProjectResponseDTO = {
      ...baseProject,
      sync_status: "FAILED",
      github_sync_job: {
        ingestion_job_id: 92,
        status: "FAILED",
        trigger_type: "MANUAL",
        started_at: "2026-08-20T10:01:00",
        finished_at: "2026-08-20T10:02:00",
        new_raw_evidence_count: 0,
        total_evidence_count: 0,
        processed_evidence_count: 0,
        extraction_failure_count: 0,
        eligible_count: 0,
        families_created_count: 0,
        families_updated_count: 0,
        error_summary: "provider failed",
      },
    };
    vi.mocked(getGithubSyncStatus).mockResolvedValue(project);

    render(<GithubSyncCard project={project} onProjectUpdated={vi.fn()} />);

    expect(screen.getByRole("button", { name: /\u0110\u1ed3ng b\u1ed9 ngay/ })).toBeEnabled();
  });

  it("adds a notification-shell item when the background sync succeeds", async () => {
    const runningProject: ProjectResponseDTO = {
      ...baseProject,
      sync_status: "SYNCING",
      github_sync_job: {
        ingestion_job_id: 93,
        status: "RUNNING",
        trigger_type: "MANUAL",
        started_at: "2026-08-20T10:01:00",
        finished_at: null,
        new_raw_evidence_count: 0,
        total_evidence_count: 0,
        processed_evidence_count: 0,
        extraction_failure_count: 0,
        eligible_count: 0,
        families_created_count: 0,
        families_updated_count: 0,
        error_summary: null,
      },
    };
    const completedJob: NonNullable<ProjectResponseDTO["github_sync_job"]> = {
      ...runningProject.github_sync_job!,
      status: "SUCCEEDED",
      finished_at: "2026-08-20T10:02:00",
    };
    vi.mocked(getGithubSyncStatus).mockResolvedValue({
      ...baseProject,
      github_sync_job: completedJob,
    });

    render(<GithubSyncCard project={runningProject} onProjectUpdated={vi.fn()} />);

    await vi.waitFor(() =>
      expect(notifyProjectOperationCompleted).toHaveBeenCalledWith({
        projectId: 7,
        operation: "GITHUB_SYNC",
        status: "SUCCEEDED",
        completedAt: "2026-08-20T10:02:00",
        repo: "thanos-io/thanos",
        documentsImported: 0,
        errorSummary: null,
      }),
    );
  });
});
