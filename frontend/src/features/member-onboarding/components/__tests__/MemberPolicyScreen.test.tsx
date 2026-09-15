import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MemberPolicyScreen } from "@/features/member-onboarding/components/MemberPolicyScreen";

const listPendingPolicies = vi.fn();
const getMemberPolicyContent = vi.fn();
const acknowledgePolicy = vi.fn();

function reachPolicyEnd() {
  const scrollContainer = screen.getByRole("main");
  Object.defineProperties(scrollContainer, {
    scrollTop: { configurable: true, value: 400 },
    clientHeight: { configurable: true, value: 600 },
    scrollHeight: { configurable: true, value: 1000 },
  });
  fireEvent.scroll(scrollContainer);
}

vi.mock("@/features/member-onboarding/api", () => ({
  listPendingPolicies: (...args: unknown[]) => listPendingPolicies(...args),
  getMemberPolicyContent: (...args: unknown[]) => getMemberPolicyContent(...args),
  acknowledgePolicy: (...args: unknown[]) => acknowledgePolicy(...args),
}));

vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/documents",
  Link: ({
    children,
    href,
    ...props
  }: AnchorHTMLAttributes<HTMLAnchorElement> & { children: ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/features/auth/session", () => ({
  useSession: () => ({
    user: {
      user_id: 1,
      display_name: "Test Member",
      email: "member@example.test",
      system_role: null,
      memberships: [
        {
          project_id: 7,
          project_role: "ENGINEER",
          status: "ACTIVE",
          project_status: "ACTIVE",
        },
      ],
    },
    loading: false,
    error: null,
    signOut: vi.fn(),
  }),
}));

describe("MemberPolicyScreen", () => {
  beforeEach(() => {
    window.localStorage.clear();
    listPendingPolicies.mockReset();
    getMemberPolicyContent.mockReset();
    acknowledgePolicy.mockReset();
    listPendingPolicies.mockResolvedValue({ items: [] });
    getMemberPolicyContent.mockResolvedValue({
      document_id: 1,
      title: "Leave policy",
      policy_category: "HR_POLICY",
      version_no: "3.2",
      effective_date: "2026-01-01",
      content: "## Annual leave\n\nEmployees receive 12 days.",
      source_url: "",
    });
    acknowledgePolicy.mockResolvedValue({
      document_id: 1,
      version_id: 9,
      acknowledged_at: "2026-08-01T09:00:00Z",
      already_acknowledged: false,
    });
  });

  it("uses the persisted Engineer theme on the policy reader", async () => {
    const user = userEvent.setup();
    const { container } = render(<MemberPolicyScreen />);

    await user.click(screen.getByRole("button", { name: "Đổi giao diện sáng tối" }));

    expect(container.querySelector('[data-theme="dark"]')).toBeInTheDocument();
    expect(window.localStorage.getItem("ralion-member-theme")).toBe("dark");
  });

  it("renders company policy in the shared Member sidebar with the policy item active", () => {
    render(<MemberPolicyScreen />);

    expect(screen.getByRole("heading", { name: "Chính sách công ty" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Chính sách công ty" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Chính sách công ty" })).toHaveAttribute(
      "href",
      "/documents",
    );
    expect(screen.getByRole("link", { name: "Ralion Chat" })).toHaveAttribute(
      "href",
      "/chat?project=7",
    );
    expect(screen.getByRole("link", { name: "Quy ước" })).toHaveAttribute(
      "href",
      "/user?project=7&view=conventions",
    );
  });

  it("reads a pending policy in place and records the acknowledgement", async () => {
    listPendingPolicies.mockResolvedValue({
      items: [
        {
          document_id: 1,
          title: "Leave policy",
          policy_category: "HR_POLICY",
          version_no: "3.2",
          effective_date: "2026-01-01",
          is_new_version: false,
        },
      ],
    });
    const user = userEvent.setup();
    render(<MemberPolicyScreen />);

    // The content is read in the app — the member never has to guess a question in Chat.
    expect(await screen.findByRole("heading", { name: "Leave policy" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/Employees receive 12 days/)).toBeInTheDocument());
    expect(getMemberPolicyContent).toHaveBeenCalledWith(1, expect.anything());

    reachPolicyEnd();
    await user.click(screen.getByRole("button", { name: "Tôi đã đọc chính sách này" }));

    await waitFor(() => expect(acknowledgePolicy).toHaveBeenCalledWith(1));
    // Acknowledged policies leave the pending list, so the empty state takes over.
    expect(
      await screen.findByText("Không có chính sách nào đang chờ bạn xác nhận."),
    ).toBeInTheDocument();
  });

  it("keeps the policy listed when the acknowledgement fails", async () => {
    listPendingPolicies.mockResolvedValue({
      items: [
        {
          document_id: 1,
          title: "Leave policy",
          policy_category: "HR_POLICY",
          version_no: "3.2",
          effective_date: "2026-01-01",
          is_new_version: true,
        },
      ],
    });
    acknowledgePolicy.mockRejectedValue(new Error("Policy is still being processed."));
    const user = userEvent.setup();
    render(<MemberPolicyScreen />);

    await screen.findByRole("heading", { name: "Leave policy" });
    reachPolicyEnd();
    await user.click(screen.getByRole("button", { name: "Tôi đã đọc chính sách này" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Policy is still being processed.");
    expect(screen.getByRole("button", { name: /Leave policy/ })).toBeInTheDocument();
  });
});
