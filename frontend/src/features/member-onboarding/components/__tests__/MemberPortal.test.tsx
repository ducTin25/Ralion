import { act, render, screen, waitFor, within } from "@testing-library/react";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MemberPortal } from "@/features/member-onboarding/components/MemberPortal";
import { buildMemberPortalHref } from "@/features/member-onboarding/hooks/useMemberPortalUrl";
import { ApiError } from "@/lib/api";

function navigateForTest(href: string, replace = false) {
  if (replace) window.history.replaceState(null, "", href);
  else window.history.pushState(null, "", href);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

vi.mock("next/navigation", () => ({
  useSearchParams: () => {
    const [search, setSearch] = useState(window.location.search);
    useEffect(() => {
      const update = () => setSearch(window.location.search);
      window.addEventListener("popstate", update);
      window.addEventListener("ralion:shallow-navigation", update);
      return () => {
        window.removeEventListener("popstate", update);
        window.removeEventListener("ralion:shallow-navigation", update);
      };
    }, []);
    return useMemo(() => new URLSearchParams(search), [search]);
  },
}));

vi.mock("@/features/auth/session", () => ({
  useSession: () => ({
    user: {
      user_id: 1,
      display_name: "Test Member",
      email: "member@example.test",
      system_role: null,
      status: "ACTIVE",
      memberships: [
        {
          membership_id: 1,
          project_id: 1,
          project_name: "Project One",
          project_key: "ONE",
          project_role: "ENGINEER",
          status: "ACTIVE",
          project_status: "ACTIVE",
        },
      ],
      expires_at: null,
    },
    loading: false,
    error: null,
    reload: vi.fn(),
    signOut: vi.fn(),
  }),
}));

vi.mock("@/features/chat/ChatScreen", () => ({
  ChatScreen: () => <h1>Embedded engineer chat</h1>,
}));

vi.mock("@/features/member-onboarding/components/MemberPolicyScreen", () => ({
  MemberPolicyScreen: () => <h1>Embedded engineer policies</h1>,
}));

vi.mock("@/i18n/navigation", () => ({
  usePathname: () => window.location.pathname,
  useRouter: () => ({
    push: (href: string) => navigateForTest(href),
    replace: (href: string) => navigateForTest(href, true),
  }),
  Link: ({
    href,
    children,
    onClick,
    ...props
  }: AnchorHTMLAttributes<HTMLAnchorElement> & { href: string; children: ReactNode }) => (
    <a
      href={href}
      {...props}
      onClick={(event) => {
        onClick?.(event);
        if (
          event.defaultPrevented ||
          event.button !== 0 ||
          event.metaKey ||
          event.ctrlKey ||
          event.shiftKey ||
          event.altKey
        ) {
          return;
        }
        event.preventDefault();
        navigateForTest(href);
      }}
    >
      {children}
    </a>
  ),
}));

const {
  listMemberProjects,
  getMemberChecklist,
  getMemberTask,
  updateMemberTaskStatus,
  listMemberBlockers,
  createMemberBlocker,
} = vi.hoisted(() => ({
  listMemberProjects: vi.fn(),
  getMemberChecklist: vi.fn(),
  getMemberTask: vi.fn(),
  updateMemberTaskStatus: vi.fn(),
  listMemberBlockers: vi.fn(),
  createMemberBlocker: vi.fn(),
}));

vi.mock("@/features/member-onboarding/api", () => ({
  listMemberProjects,
  getMemberChecklist,
  getMemberTask,
  updateMemberTaskStatus,
  listMemberBlockers,
  createMemberBlocker,
}));

const member = {
  user_id: 4,
  email: "engineer.phoneshop@onboarding.dev",
  display_name: "Nguyễn Văn A",
};

const task = {
  plan_task_id: 10,
  title: "Read the Architecture doc",
  category: "ORIENTATION" as const,
  display_order: 1,
  mandatory: true,
  estimated_minutes: 45,
  status: "IN_PROGRESS" as const,
  due_at: null,
  started_at: "2026-08-12T08:00:00",
  completed_at: null,
  dependencies_met: true,
  open_blocker_count: 0,
  source_count: 1,
  is_locked: false,
  lock_reason: null,
  can_start: false,
  can_complete: true,
};

const projectsResponse = {
  member,
  projects: [
    {
      project_id: 1,
      membership_id: 2,
      key: "PAY",
      name: "Payment API — Core Platform",
      project_role: "ENGINEER" as const,
      plan_id: 3,
      plan_status: "ACTIVE" as const,
    },
    {
      project_id: 2,
      membership_id: 4,
      key: "FRAUD",
      name: "Fraud Detection Service",
      project_role: "ENGINEER" as const,
      plan_id: 5,
      plan_status: "ACTIVE" as const,
    },
  ],
};

describe("MemberPortal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState(null, "", "/user?project=1");
    window.localStorage.clear();
    listMemberProjects.mockResolvedValue(projectsResponse);
    getMemberChecklist.mockResolvedValue({
      member,
      project: { project_id: 1, key: "PAY", name: "Payment API — Core Platform" },
      membership_id: 2,
      plan_id: 3,
      plan_status: "ACTIVE",
      approved_at: "2026-07-28T08:00:00",
      progress: { completed: 7, total: 10, percent: 70 },
      groups: [{ category: "ORIENTATION", tasks: [task] }],
    });
    getMemberTask.mockResolvedValue({
      ...task,
      plan_id: 3,
      plan_status: "ACTIVE",
      objective: "Understand the overall system architecture.",
      instruction: "Read the architecture diagram and note the main modules.",
      dependencies: [{ plan_task_id: 9, title: "Read the overview", status: "DONE" }],
      sources: [
        {
          document_id: 7,
          version_id: 8,
          title: "Architecture Guide",
          source_url: "https://example.test/architecture",
          citation_note: "Read sections 1-3",
        },
      ],
      citations: [],
    });
    updateMemberTaskStatus.mockResolvedValue({
      ...task,
      status: "DONE",
      can_complete: false,
      completed_at: "2026-08-12T09:00:00",
      plan_id: 3,
      plan_status: "ACTIVE",
      objective: "Understand the overall system architecture.",
      instruction: "Read the architecture diagram and note the main modules.",
      dependencies: [{ plan_task_id: 9, title: "Read the overview", status: "DONE" }],
      sources: [],
      citations: [],
    });
    listMemberBlockers.mockResolvedValue([]);
    createMemberBlocker.mockResolvedValue({
      blocker_id: 99,
      plan_task_id: 10,
      task_title: "Read the Architecture doc",
      category: "TECHNICAL",
      reason: "The local service cannot reach the dev database.",
      status: "OPEN",
      reported_at: "2026-08-12T10:00:00",
      resolved_at: null,
    });
  });

  it("redirects missing project context to the centralized selector", async () => {
    window.history.replaceState(null, "", "/user");
    render(<MemberPortal />);

    await waitFor(() => expect(window.location.pathname).toBe("/select-project"));
    expect(
      screen.queryByRole("heading", { name: "Choose the project you are working in" }),
    ).not.toBeInTheDocument();
  });

  it("renders checklist progress for the selected project and opens task detail", async () => {
    const user = userEvent.setup();
    render(<MemberPortal />);

    expect(
      await screen.findByRole("heading", { name: "Xin chào Nguyễn Văn A" }),
    ).toBeInTheDocument();
    expect(window.location.search).toBe("?project=1");
    expect(screen.getByRole("link", { name: "Chính sách công ty" })).toHaveAttribute(
      "href",
      "/user?project=1&view=policy",
    );
    expect(screen.getByRole("link", { name: "Ralion Chat" })).toHaveAttribute(
      "href",
      "/user?project=1&view=chat",
    );
    await user.click(screen.getByRole("link", { name: "Nhiệm vụ" }));
    expect(await screen.findByRole("heading", { name: "Nhiệm vụ của bạn" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ralion Chat" })).toHaveAttribute(
      "href",
      "/user?project=1&view=chat",
    );
    await user.click(screen.getByRole("link", { name: "Ralion Chat" }));
    expect(window.location.search).toBe("?project=1&view=chat");
    await user.click(screen.getByRole("link", { name: "Nhiệm vụ" }));
    await user.click(screen.getByRole("link", { name: /Tổng quan dự án/ }));
    expect(
      screen.getByRole("complementary", { name: "Hành trình onboarding" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Mở nhiệm vụ số 1 trong hành trình" })).toHaveAttribute(
      "href",
      "/user?project=1&category=ORIENTATION&task=10",
    );
    expect(screen.getByLabelText("Tiến độ 70%")).toHaveTextContent("7/10 task · 70%");
    expect(screen.getByRole("link", { name: "Tiếp tục task" })).toHaveAttribute(
      "href",
      "/user?project=1&category=ORIENTATION&task=10",
    );
    expect(screen.getByRole("link", { name: /Read the Architecture doc/i })).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: /Read the Architecture doc/i }));

    expect(
      await screen.findByRole("region", { name: "Read the Architecture doc" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Mở nhiệm vụ số 1 trong hành trình" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByText("Định hướng")).toBeInTheDocument();
    expect(screen.getByText("Understand the overall system architecture.")).toBeInTheDocument();
    const actionGroup = screen.getByRole("group", { name: "Thao tác task" });
    expect(actionGroup.closest("aside")).not.toBeNull();
    expect(
      within(actionGroup).getByRole("button", { name: "Đánh dấu hoàn thành" }),
    ).toBeInTheDocument();
    const tabList = screen.getByRole("tablist", { name: "Chi tiết task" });
    expect(within(tabList).getByRole("tab", { name: /Nội dung task/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await user.click(within(tabList).getByRole("tab", { name: /Tài liệu/ }));
    expect(screen.getByRole("tabpanel")).toHaveAttribute(
      "aria-labelledby",
      "task-10-documents-tab",
    );
    expect(screen.getByRole("button", { name: /Architecture Guide/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Đóng" })).not.toBeInTheDocument();
  });

  it("keeps the Engineer shell mounted when opening Chat and Policy", async () => {
    const user = userEvent.setup();
    render(<MemberPortal />);

    await screen.findByRole("heading", { name: "Xin chào Nguyễn Văn A" });
    await user.click(screen.getByRole("link", { name: "Ralion Chat" }));

    expect(window.location.pathname).toBe("/user");
    expect(window.location.search).toBe("?project=1&view=chat");
    const chatHeading = screen.getByRole("heading", { name: "Embedded engineer chat" });
    expect(chatHeading).toBeInTheDocument();
    expect(chatHeading.closest("main")?.className).toContain("contentChat");
    expect(screen.getByRole("navigation", { name: "Điều hướng Engineer Portal" })).toBeVisible();

    await user.click(screen.getByRole("link", { name: "Chính sách công ty" }));
    expect(window.location.pathname).toBe("/user");
    expect(window.location.search).toBe("?project=1&view=policy");
    const policyHeading = screen.getByRole("heading", { name: "Embedded engineer policies" });
    expect(policyHeading).toBeInTheDocument();
    expect(policyHeading.closest("main")?.className).not.toContain("contentChat");
  });

  it("renders COMPANY first and preserves each stage task order and source count", async () => {
    getMemberChecklist.mockResolvedValueOnce({
      member,
      project: { project_id: 1, key: "PAY", name: "Payment API — Core Platform" },
      membership_id: 2,
      plan_id: 3,
      plan_status: "ACTIVE",
      approved_at: "2026-07-28T08:00:00",
      progress: { completed: 0, total: 2, percent: 0 },
      groups: [
        {
          category: "COMPANY",
          tasks: [
            {
              ...task,
              plan_task_id: 11,
              title: "Learn the company policies",
              category: "COMPANY",
              display_order: 1,
              source_count: 5,
            },
          ],
        },
        { category: "ORIENTATION", tasks: [{ ...task, display_order: 2 }] },
      ],
    });
    render(<MemberPortal />);

    const user = userEvent.setup();
    await screen.findByRole("heading", { name: "Xin chào Nguyễn Văn A" });
    await user.click(screen.getByRole("link", { name: "Nhiệm vụ" }));
    const companyStage = await screen.findByRole("link", { name: /Tìm hiểu công ty/ });
    const orientationStage = screen.getByRole("link", { name: /Tổng quan dự án/ });
    expect(companyStage.compareDocumentPosition(orientationStage)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
    await user.click(companyStage);
    expect(await screen.findByRole("heading", { name: "Tìm hiểu công ty" })).toBeInTheDocument();
    const taskLinks = screen
      .getAllByRole("link")
      .filter(
        (link) => link.getAttribute("href")?.includes("task=") && !link.hasAttribute("aria-label"),
      );
    expect(taskLinks[0]).toHaveTextContent("Learn the company policies");
    expect(taskLinks[0]).toHaveTextContent("5 nguồn");
  });

  it("opens the exact document preview from an inline chunk citation", async () => {
    const user = userEvent.setup();
    getMemberTask.mockResolvedValueOnce({
      ...task,
      plan_id: 3,
      plan_status: "ACTIVE",
      objective: "Understand the overall system architecture.",
      instruction: "Read the key authentication section [1].",
      dependencies: [],
      sources: [
        {
          document_id: 7,
          version_id: 8,
          title: "Architecture Guide",
          source_url: "https://example.test/architecture.pdf",
          citation_note: null,
        },
      ],
      citations: [
        {
          citation_id: 101,
          plan_task_id: 10,
          citation_order: 1,
          version_id: 8,
          document_id: 7,
          document_title: "Architecture Guide",
          document_url: "https://example.test/architecture.pdf",
          chunk_id: 88,
          citation_note: "Authentication flow",
          section_path: "Architecture > Authentication",
          content_snippet: "The auth flow uses access tokens.",
        },
      ],
    });
    render(<MemberPortal />);
    await user.click(await screen.findByRole("link", { name: /Read the Architecture doc/i }));
    await user.click(await screen.findByRole("button", { name: "1" }));

    const preview = await screen.findByRole("dialog");
    expect(
      within(preview).getByRole("heading", { name: "Architecture Guide" }),
    ).toBeInTheDocument();
    expect(within(preview).getByTitle("Architecture Guide")).toHaveAttribute(
      "src",
      "https://example.test/architecture.pdf",
    );
  });

  it("renders a navigable outline with stable IDs for long task content", async () => {
    const user = userEvent.setup();
    const scrollIntoView = vi.fn();
    Object.defineProperty(Element.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });
    getMemberTask.mockResolvedValueOnce({
      ...task,
      plan_id: 3,
      plan_status: "ACTIVE",
      objective: "Understand the policies.",
      instruction: [
        "## Các bước thực hiện",
        "### Chính sách nhân sự",
        "Đọc nội dung A.",
        "## Tài liệu nguồn cần đọc",
        "### Chính sách nhân sự",
        "Đọc nội dung B.",
      ].join("\n"),
      dependencies: [],
      sources: [],
      citations: [],
    });

    render(<MemberPortal />);
    await user.click(await screen.findByRole("link", { name: /Read the Architecture doc/i }));

    const outline = await screen.findByRole("navigation", { name: "Trong task này" });
    const repeatedSections = within(outline).getAllByRole("button", {
      name: "Chính sách nhân sự",
    });
    expect(document.getElementById("chinh-sach-nhan-su")).toBeInTheDocument();
    expect(document.getElementById("chinh-sach-nhan-su-2")).toBeInTheDocument();
    expect(screen.getByLabelText("Đi đến mục")).toHaveValue("cac-buoc-thuc-hien");

    await user.click(repeatedSections[1]);
    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "start" });
    expect(repeatedSections[1]).toHaveAttribute("aria-current", "location");
  });

  it("completes an eligible task and refreshes checklist progress", async () => {
    const user = userEvent.setup();
    window.history.replaceState(null, "", "/user?project=1&task=10&category=ORIENTATION");
    render(<MemberPortal />);

    expect(screen.queryByText("First Task & First PR")).not.toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Đánh dấu hoàn thành" }));

    expect(updateMemberTaskStatus).toHaveBeenCalledWith(10, "DONE");
    expect(await screen.findByText("Task đã hoàn thành")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Đã đánh dấu task hoàn thành.");
    expect(getMemberChecklist).toHaveBeenCalledTimes(2);
  });

  it("reports a blocker without changing task status and shows it in My Blockers", async () => {
    const user = userEvent.setup();
    render(<MemberPortal />);

    await user.click(await screen.findByRole("link", { name: /Read the Architecture doc/i }));
    await user.click(await screen.findByRole("button", { name: "Báo blocker" }));

    const blockerDialog = await screen.findByRole("dialog", { name: "Tôi đang bị chặn" });
    expect(blockerDialog).toBeInTheDocument();
    await user.selectOptions(
      within(blockerDialog).getByRole("combobox", { name: "Loại blocker" }),
      "TECHNICAL",
    );
    await user.type(
      within(blockerDialog).getByRole("textbox", { name: "Mô tả vấn đề" }),
      "The local service cannot reach the dev database.",
    );
    await user.click(within(blockerDialog).getByRole("button", { name: "Báo blocker" }));

    // `attachments` là tham số mới của UC-08 (đính kèm ảnh/video minh chứng). Không gửi file thì
    // vẫn phải là mảng rỗng — form gửi multipart nên field luôn có mặt.
    expect(createMemberBlocker).toHaveBeenCalledWith(10, {
      category: "TECHNICAL",
      reason: "The local service cannot reach the dev database.",
      attachments: [],
    });
    expect(await screen.findByText("Đã ghi nhận blocker.")).toBeInTheDocument();
    expect(
      within(screen.getByRole("region", { name: "Read the Architecture doc" })).getAllByText(
        "Đang thực hiện",
      )[0],
    ).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "Tổng quan" }));
    await user.click(screen.getByRole("link", { name: /Blocker của tôi/i }));
    expect(screen.getByRole("heading", { name: "Blocker của tôi" })).toBeInTheDocument();
    expect(
      screen.getByText("The local service cannot reach the dev database."),
    ).toBeInTheDocument();
    expect(screen.getByText("Đang mở")).toBeInTheDocument();
  });
  it("supports keyboard dismissal and the dark theme toggle", async () => {
    const user = userEvent.setup();
    const { container } = render(<MemberPortal />);

    await user.click(await screen.findByRole("link", { name: /Read the Architecture doc/i }));
    expect(screen.getByRole("region", { name: "Read the Architecture doc" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Quay lại checklist" }));
    expect(
      screen.queryByRole("region", { name: "Read the Architecture doc" }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Đổi giao diện sáng tối" }));
    expect(container.querySelector('[data-theme="dark"]')).toBeInTheDocument();
    expect(window.localStorage.getItem("ralion-member-theme")).toBe("dark");
  });

  it("opens a project and task directly from URL without returning to the picker", async () => {
    window.history.replaceState(null, "", "/user?project=1&task=10");
    render(<MemberPortal />);

    expect(
      await screen.findByRole("region", { name: "Read the Architecture doc" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Choose the project you are working in" }),
    ).not.toBeInTheDocument();
    expect(
      await screen.findByRole("region", { name: "Read the Architecture doc" }),
    ).toBeInTheDocument();
  });

  it("does not let a stale project response overwrite the currently selected project", async () => {
    const checklistForProject = (projectId: number) => ({
      member,
      project: {
        project_id: projectId,
        key: projectId === 1 ? "PAY" : "FRAUD",
        name: projectId === 1 ? "Payment API — Core Platform" : "Fraud Detection Service",
      },
      membership_id: projectId === 1 ? 2 : 4,
      plan_id: projectId === 1 ? 3 : 5,
      plan_status: "ACTIVE" as const,
      approved_at: "2026-07-28T08:00:00",
      progress: { completed: 7, total: 10, percent: 70 },
      groups: [{ category: "ORIENTATION" as const, tasks: [task] }],
    });
    let resolveFirst: ((value: ReturnType<typeof checklistForProject>) => void) | undefined;
    let firstSignal: AbortSignal | undefined;
    getMemberChecklist.mockImplementation((projectId: number, signal?: AbortSignal) => {
      if (projectId === 1) {
        firstSignal = signal;
        return new Promise((resolve) => {
          resolveFirst = resolve;
        });
      }
      return Promise.resolve(checklistForProject(2));
    });

    const user = userEvent.setup();
    render(<MemberPortal />);
    await user.selectOptions(await screen.findByRole("combobox", { name: "Đổi dự án" }), "2");

    await waitFor(() => expect(firstSignal?.aborted).toBe(true));
    await waitFor(() =>
      expect(screen.getByRole("combobox", { name: "Đổi dự án" })).toHaveValue("2"),
    );
    expect(
      screen.getByRole("heading", { name: "Xin chào Nguyễn Văn A" }).parentElement,
    ).toHaveTextContent("Fraud Detection Service");
    await act(async () => resolveFirst?.(checklistForProject(1)));
    expect(
      screen.getByRole("heading", { name: "Xin chào Nguyễn Văn A" }).parentElement,
    ).toHaveTextContent("Fraud Detection Service");
    expect(window.location.search).toBe("?project=2");
  });

  it("applies a completed mutation to the project where the action started", async () => {
    let projectOneCompleted = false;
    let resolveUpdate: ((value: Record<string, unknown>) => void) | undefined;
    getMemberChecklist.mockImplementation((projectId: number) =>
      Promise.resolve({
        member,
        project: {
          project_id: projectId,
          key: projectId === 1 ? "PAY" : "FRAUD",
          name: projectId === 1 ? "Payment API — Core Platform" : "Fraud Detection Service",
        },
        membership_id: projectId === 1 ? 2 : 4,
        plan_id: projectId === 1 ? 3 : 5,
        plan_status: "ACTIVE",
        approved_at: "2026-07-28T08:00:00",
        progress: { completed: 7, total: 10, percent: 70 },
        groups: [
          {
            category: "ORIENTATION",
            tasks: [
              projectId === 1 && projectOneCompleted
                ? { ...task, status: "DONE", completed_at: "2026-08-12T09:00:00" }
                : task,
            ],
          },
        ],
      }),
    );
    updateMemberTaskStatus.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveUpdate = resolve;
        }),
    );

    const user = userEvent.setup();
    window.history.replaceState(null, "", "/user?project=1&category=ORIENTATION&task=10");
    render(<MemberPortal />);
    await user.click(await screen.findByRole("button", { name: "Đánh dấu hoàn thành" }));
    await waitFor(() => expect(updateMemberTaskStatus).toHaveBeenCalledTimes(1));

    await user.selectOptions(screen.getByRole("combobox", { name: "Đổi dự án" }), "2");
    await waitFor(() => expect(window.location.search).toBe("?project=2"));
    projectOneCompleted = true;
    await act(async () =>
      resolveUpdate?.({
        ...task,
        status: "DONE",
        can_complete: false,
        completed_at: "2026-08-12T09:00:00",
        plan_id: 3,
        plan_status: "ACTIVE",
        objective: "Understand the overall system architecture.",
        instruction: "Read the architecture diagram and note the main modules.",
        dependencies: [],
        sources: [],
      }),
    );

    await user.selectOptions(screen.getByRole("combobox", { name: "Đổi dự án" }), "1");
    await user.click(await screen.findByRole("link", { name: "Nhiệm vụ" }));
    await user.click(await screen.findByRole("link", { name: /Tổng quan dự án/ }));
    const taskLink = await screen.findByRole("link", { name: /Read the Architecture doc/i });
    expect(taskLink).toHaveTextContent("Hoàn thành");
  });

  it("starts deep-linked project queries before the projects request completes", async () => {
    let resolveProjects: ((value: typeof projectsResponse) => void) | undefined;
    listMemberProjects.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveProjects = resolve;
        }),
    );
    window.history.replaceState(null, "", "/user?project=1");
    render(<MemberPortal />);

    await waitFor(() =>
      expect(getMemberChecklist).toHaveBeenCalledWith(1, expect.any(AbortSignal)),
    );
    expect(listMemberProjects).toHaveBeenCalledTimes(1);
    await act(async () => resolveProjects?.(projectsResponse));
    expect(
      await screen.findByRole("heading", { name: "Xin chào Nguyễn Văn A" }),
    ).toBeInTheDocument();
  });

  it("serves a recently visited project from cache when switching back", async () => {
    const user = userEvent.setup();
    render(<MemberPortal />);

    await waitFor(() => expect(getMemberChecklist).toHaveBeenCalledTimes(1));
    await user.selectOptions(await screen.findByRole("combobox", { name: "Đổi dự án" }), "2");
    await waitFor(() => expect(getMemberChecklist).toHaveBeenCalledTimes(2));
    await user.selectOptions(screen.getByRole("combobox", { name: "Đổi dự án" }), "1");

    await waitFor(() => expect(window.location.search).toBe("?project=1"));
    expect(getMemberChecklist).toHaveBeenCalledTimes(2);
  });

  it("presents authentication errors separately from generic request failures", async () => {
    listMemberProjects.mockRejectedValue(new ApiError(401, "Unauthorized"));
    render(<MemberPortal />);

    expect(
      await screen.findByText("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."),
    ).toBeInTheDocument();
  });
});

describe("buildMemberPortalHref", () => {
  it("creates canonical project, view and task deep links", () => {
    expect(buildMemberPortalHref("/user", new URLSearchParams(), { projectId: 12 })).toBe(
      "/user?project=12",
    );
    expect(
      buildMemberPortalHref("/user", new URLSearchParams("project=12"), {
        view: "blockers",
        taskId: 99,
      }),
    ).toBe("/user?project=12&view=blockers");
    expect(
      buildMemberPortalHref("/user", new URLSearchParams("project=12&view=blockers"), {
        view: "tasks",
        taskId: 99,
      }),
    ).toBe("/user?project=12&task=99");
  });
});
