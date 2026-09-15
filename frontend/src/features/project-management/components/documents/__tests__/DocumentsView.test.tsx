import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  confirmProjectDocumentCategory,
  getGithubSyncStatus,
  listProjectDocuments,
} from "@/features/project-management/api";
import { DocumentsView } from "@/features/project-management/components/documents/DocumentsView";
import type { ProjectResponseDTO } from "@/features/project-management/dto/responseDTO/project.response";

vi.mock("@/features/project-management/api", () => ({
  confirmProjectDocumentCategory: vi.fn(),
  deleteProjectDocument: vi.fn(),
  getGithubSyncStatus: vi.fn(),
  getProjectDocumentContent: vi.fn(),
  listProjectDocuments: vi.fn(),
}));
vi.mock("@/features/project-management/components/documents/GithubSyncCard", () => ({
  GithubSyncCard: () => null,
  isGithubRepoConfigured: () => false,
}));
vi.mock("@/features/project-management/components/documents/DiscoveryScheduleCard", () => ({
  DiscoveryScheduleCard: () => null,
}));
vi.mock("@/features/project-management/components/documents/RepoScanWizard", () => ({
  RepoScanWizard: () => null,
}));
vi.mock("@/features/project-management/components/documents/DocumentUploadModal", () => ({
  DocumentUploadModal: () => null,
}));
vi.mock("@/features/project-management/components/documents/CategoryDocumentsDrawer", () => ({
  CategoryDocumentsDrawer: () => null,
}));
vi.mock("@/features/project-management/components/ui/DocumentPreviewModal", () => ({
  DocumentPreviewModal: ({ title, onClose }: { title: string; onClose: () => void }) => (
    <div role="dialog">
      {title}
      <button type="button" onClick={onClose}>Close</button>
    </div>
  ),
}));

const project: ProjectResponseDTO = {
  project_id: 9,
  key: "RAL",
  name: "Ralion",
  primary_pm_membership_id: 1,
  created_by_admin_id: 1,
  status: "ACTIVE",
  sync_status: "PARTIAL",
  last_synced_at: null,
  created_at: "2026-08-01T00:00:00",
  github_repo: "owner/repo",
  default_branch: "main",
  github_credential_status: "VALID",
};

const ambiguousDocuments = [
  {
    document_id: 10,
    project_id: 9,
    document_category: null,
    category_confirmed: false,
    category_classification_status: "AMBIGUOUS" as const,
    title: "Architecture notes",
    status: "ACTIVE" as const,
    latest_version: null,
    created_at: "2026-08-01T00:00:00",
  },
  {
    document_id: 11,
    project_id: 9,
    document_category: null,
    category_confirmed: false,
    category_classification_status: "AMBIGUOUS" as const,
    title: "Setup notes",
    status: "ACTIVE" as const,
    latest_version: null,
    created_at: "2026-08-01T00:00:00",
  },
];

describe("DocumentsView category review", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listProjectDocuments).mockResolvedValue(ambiguousDocuments);
    vi.mocked(confirmProjectDocumentCategory).mockResolvedValue({
      ...ambiguousDocuments[0],
      document_category: "ARCHITECTURE",
      category_confirmed: true,
    });
    vi.mocked(getGithubSyncStatus).mockResolvedValue({ ...project, sync_status: "SUCCESS" });
  });

  it("lets PM preview rows and confirm every resolved category in one action", async () => {
    const user = userEvent.setup();
    render(<DocumentsView project={project} />);

    await screen.findByText("Architecture notes");
    await user.click(screen.getByRole("button", { name: "Xem trước Architecture notes" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("Architecture notes");
    await user.click(screen.getByRole("button", { name: "Close" }));

    const selects = screen.getAllByRole("combobox");
    fireEvent.change(selects[0], { target: { value: "ARCHITECTURE" } });
    fireEvent.change(selects[1], { target: { value: "SETUP" } });
    await user.click(screen.getByRole("button", { name: "Xác nhận tất cả" }));

    await waitFor(() =>
      expect(confirmProjectDocumentCategory).toHaveBeenCalledTimes(2),
    );
    expect(confirmProjectDocumentCategory).toHaveBeenCalledWith(9, 10, "ARCHITECTURE");
    expect(confirmProjectDocumentCategory).toHaveBeenCalledWith(9, 11, "SETUP");
    expect(getGithubSyncStatus).toHaveBeenCalledWith(9);
  });
});
