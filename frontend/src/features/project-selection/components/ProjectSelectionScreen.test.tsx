import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ProjectSelectionScreen } from "./ProjectSelectionScreen";

const { establishMembership, push, refetch, replace, signOut, useProjectMemberships, useSession } =
  vi.hoisted(() => ({
    establishMembership: vi.fn(),
    push: vi.fn(),
    refetch: vi.fn(),
    replace: vi.fn(),
    signOut: vi.fn(),
    useProjectMemberships: vi.fn(),
    useSession: vi.fn(),
  }));

vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ push, replace }),
  usePathname: () => "/select-project",
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/features/auth/session", () => ({
  useSession,
}));

vi.mock("@/features/project-selection/hooks/useProjectMemberships", () => ({
  MembershipApiError: class MembershipApiError extends Error {},
  useProjectMemberships,
}));

const engineerMembership = {
  membershipId: 51,
  projectId: 7,
  projectName: "Payments",
  projectKey: "PAY",
  projectStatus: "ACTIVE" as const,
  projectRole: "ENGINEER" as const,
  joinedAt: "2026-08-01T08:00:00Z",
  syncStatus: "SUCCESS" as const,
  lastSyncedAt: "2026-08-14T08:00:00Z",
  plan: null,
};

function membershipHook(data = [engineerMembership]) {
  return {
    data,
    isLoading: false,
    error: null,
    refetch,
    establishMembership,
  };
}

describe("ProjectSelectionScreen routing", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useSession.mockReturnValue({
      user: {
        user_id: 4,
        display_name: "Nguyễn Văn A",
        email: "engineer@onboarding.dev",
        system_role: null,
        status: "ACTIVE",
        memberships: [],
        expires_at: null,
      },
      loading: false,
      error: null,
      signOut,
    });
    useProjectMemberships.mockReturnValue(membershipHook());
    establishMembership.mockResolvedValue({
      membershipId: 51,
      projectId: 7,
      projectName: "Payments",
      projectKey: "PAY",
      projectRole: "ENGINEER",
      // Mô phỏng backend image cũ để bảo đảm frontend không làm rơi context.
      redirectPath: "/user",
    });
  });

  it("still requires an explicit choice with exactly one active membership", async () => {
    const user = userEvent.setup();
    const { container } = render(<ProjectSelectionScreen />);

    expect(await screen.findByRole("heading", { name: "Chọn dự án" })).toBeInTheDocument();
    expect(container.querySelector("main.ralion-workspace")).toBeInTheDocument();
    expect(establishMembership).not.toHaveBeenCalled();

    await user.click(
      screen.getByRole("button", { name: "Tiếp tục vào Payments với vai trò Kỹ sư" }),
    );
    await waitFor(() => expect(establishMembership).toHaveBeenCalledWith(51));
    expect(replace).toHaveBeenCalledWith("/user?project=7");
    expect(push).not.toHaveBeenCalled();
  });

  it("waits for an explicit choice when more than one membership is active", async () => {
    const secondMembership = {
      ...engineerMembership,
      membershipId: 52,
      projectId: 8,
      projectName: "Orders",
      projectKey: "ORD",
    };
    useProjectMemberships.mockReturnValue(membershipHook([engineerMembership, secondMembership]));
    const user = userEvent.setup();
    render(<ProjectSelectionScreen />);

    expect(await screen.findByRole("heading", { name: "Chọn dự án" })).toBeInTheDocument();
    expect(establishMembership).not.toHaveBeenCalled();

    await user.click(
      screen.getByRole("button", { name: "Tiếp tục vào Payments với vai trò Kỹ sư" }),
    );
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/user?project=7"));
  });
});
