import { afterEach, describe, expect, it, vi } from "vitest";

import {
  approvePlan,
  confirmProjectDocumentCategory,
  listProjectsManagedByPm,
} from "@/features/project-management/api";
import type { ProjectDocumentResponseDTO } from "@/features/project-management/dto/responseDTO/document.response";
import type { ProjectResponseDTO } from "@/features/project-management/dto/responseDTO/project.response";
import {
  CURRENT_PM_USER_ID,
  MEMBERSHIPS_ENDPOINT,
  PM_KNOWLEDGE_DOCUMENTS_ENDPOINT,
  PM_ONBOARDING_PLANS_ENDPOINT,
  PM_PROJECTS_ENDPOINT,
} from "@/lib/api";
import type { MembershipCard } from "@/types/project";

const memberships: MembershipCard[] = [
  {
    membershipId: 70,
    projectId: 7,
    projectName: "Managed Project",
    projectKey: "MANAGED",
    projectStatus: "ACTIVE",
    projectRole: "PM",
    joinedAt: "2026-08-01T00:00:00Z",
    syncStatus: "SUCCESS",
    lastSyncedAt: null,
    plan: null,
  },
  {
    membershipId: 80,
    projectId: 8,
    projectName: "Engineer Project",
    projectKey: "ENGINEER",
    projectStatus: "ACTIVE",
    projectRole: "ENGINEER",
    joinedAt: "2026-08-02T00:00:00Z",
    syncStatus: "SUCCESS",
    lastSyncedAt: null,
    plan: null,
  },
];

const managedProject: ProjectResponseDTO = {
  project_id: 7,
  key: "MANAGED",
  name: "Managed Project",
  primary_pm_membership_id: 70,
  created_by_admin_id: 1,
  status: "ACTIVE",
  sync_status: "SUCCESS",
  last_synced_at: null,
  created_at: "2026-08-01T00:00:00Z",
  github_repo: null,
  default_branch: null,
  github_credential_status: null,
  github_sync_job: null,
};

describe("PM project identity", () => {
  afterEach(() => vi.restoreAllMocks());

  it("loads projects from the signed-in user's PM memberships", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url === MEMBERSHIPS_ENDPOINT) {
        return new Response(JSON.stringify(memberships), { status: 200 });
      }
      if (url === `${PM_PROJECTS_ENDPOINT}/7`) {
        return new Response(JSON.stringify(managedProject), { status: 200 });
      }
      throw new Error(`Unexpected URL: ${url}`);
    });

    await expect(listProjectsManagedByPm()).resolves.toEqual([managedProject]);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls.map(([input]) => String(input))).toEqual([
      MEMBERSHIPS_ENDPOINT,
      `${PM_PROJECTS_ENDPOINT}/7`,
    ]);
    for (const [, init] of fetchMock.mock.calls) {
      expect(init).toEqual(expect.objectContaining({ credentials: "include" }));
    }
  });
});

describe("approvePlan", () => {
  afterEach(() => vi.restoreAllMocks());

  it("PATCHes the approve endpoint with the reviewer required by the backend contract", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ plan_id: 3470 }), { status: 200 }));

    await approvePlan(3470);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toBe(`${PM_ONBOARDING_PLANS_ENDPOINT}/3470/approve`);
    expect(init).toEqual(
      expect.objectContaining({
        method: "PATCH",
        credentials: "include",
        body: JSON.stringify({ approved_by_user_id: CURRENT_PM_USER_ID }),
      }),
    );
  });
});

describe("confirmProjectDocumentCategory (Document category HITL)", () => {
  afterEach(() => vi.restoreAllMocks());

  it("PATCHes the confirm-category endpoint and returns the classified document", async () => {
    const confirmed: ProjectDocumentResponseDTO = {
      document_id: 42,
      project_id: 7,
      document_category: "ARCHITECTURE",
      category_confirmed: true,
      category_classification_status: "CLASSIFIED",
      title: "docs/architecture/system-design.md",
      status: "ACTIVE",
      latest_version: null,
      created_at: "2026-08-01T00:00:00Z",
    };
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(confirmed), { status: 200 }));

    await expect(confirmProjectDocumentCategory(7, 42, "ARCHITECTURE")).resolves.toEqual(confirmed);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toBe(`${PM_KNOWLEDGE_DOCUMENTS_ENDPOINT}/projects/7/42/category`);
    expect(init).toEqual(
      expect.objectContaining({
        method: "PATCH",
        credentials: "include",
        body: JSON.stringify({ category: "ARCHITECTURE" }),
      }),
    );
  });
});
