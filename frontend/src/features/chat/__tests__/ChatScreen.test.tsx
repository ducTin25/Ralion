import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatScreen } from "@/features/chat/ChatScreen";
import { askChat, fetchConversation } from "@/features/chat/api";
import { useSession } from "@/features/auth/session";
import { useProjectMemberships } from "@/features/project-selection/hooks/useProjectMemberships";
import { useEmbeddingWarmup } from "@/hooks/useEmbeddingWarmup";
import { ApiError } from "@/lib/api";
import type { CurrentUser } from "@/features/auth/session";
import type { MembershipCard } from "@/types/project";

const replace = vi.fn();

vi.mock("@/i18n/navigation", () => ({
  Link: ({
    href,
    children,
    ...props
  }: AnchorHTMLAttributes<HTMLAnchorElement> & { href: string; children: ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
  useRouter: () => ({ replace }),
  usePathname: () => "/chat",
}));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/features/chat/api", () => ({ askChat: vi.fn(), fetchConversation: vi.fn() }));
vi.mock("@/hooks/useEmbeddingWarmup", () => ({ useEmbeddingWarmup: vi.fn() }));
vi.mock("@/features/auth/session", () => ({ useSession: vi.fn() }));
vi.mock("@/features/project-selection/hooks/useProjectMemberships", () => ({
  useProjectMemberships: vi.fn(),
}));

const userProfile: CurrentUser = {
  user_id: 7,
  display_name: "Minh Nguyen",
  email: "minh@example.test",
  system_role: null,
  status: "ACTIVE",
  response_length: "STANDARD",
  response_tone: "NEUTRAL",
  memberships: [],
  expires_at: null,
};

const cargoMembership: MembershipCard = {
  membershipId: 42,
  projectId: 9,
  projectName: "Cargo",
  projectKey: "CRG",
  projectStatus: "ACTIVE",
  projectRole: "ENGINEER",
  joinedAt: "2026-08-01T00:00:00Z",
  syncStatus: "SUCCESS",
  lastSyncedAt: null,
  plan: null,
};

function mockMemberships(data: MembershipCard[] = []) {
  vi.mocked(useProjectMemberships).mockReturnValue({
    data: [...data],
    isLoading: false,
    error: null,
    refetch: vi.fn(),
    establishMembership: vi.fn(),
  });
}

describe("Ralion Chat Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.sessionStorage.clear();
    window.localStorage.clear();
    vi.mocked(useSession).mockReturnValue({
      user: userProfile,
      loading: false,
      error: null,
      reload: vi.fn(),
      signOut: vi.fn(),
      updatePreferences: vi.fn().mockResolvedValue(userProfile),
    });
    vi.mocked(useEmbeddingWarmup).mockReturnValue("ready");
    mockMemberships();
  });

  it("persists the Engineer theme across Chat", async () => {
    const user = userEvent.setup();
    const { container } = render(<ChatScreen />);

    await user.click(screen.getByRole("button", { name: "Đổi giao diện sáng tối" }));

    expect(container.querySelector('[data-theme="dark"]')).toBeInTheDocument();
    expect(window.localStorage.getItem("ralion-member-theme")).toBe("dark");
  });

  it("shows preparation status and blocks submits until the embedder is ready", async () => {
    vi.mocked(useEmbeddingWarmup).mockReturnValue("preparing");
    render(<ChatScreen />);

    expect(screen.getByRole("status")).toHaveTextContent("Preparing your assistant…");
    const composer = screen.getByLabelText("Question for Ralion");
    await userEvent.type(composer, "What is the leave policy?");
    expect(screen.getByRole("button", { name: "Send question" })).toBeDisabled();

    fireEvent.keyDown(composer, { key: "Enter", code: "Enter" });
    expect(askChat).not.toHaveBeenCalled();
  });

  it("defaults a user without memberships to POLICY and exposes no project section", async () => {
    vi.mocked(askChat).mockResolvedValue({
      answer: "The policy allows remote work.",
      citations: [],
      fallback: true,
      fallback_reason: "no_evidence",
      trace_id: "trace-policy",
      answer_status: "fallback",
      validator_outcome: null,
      claims: [],
      conflict: null,
      conversation_id: "11111111-1111-4111-8111-111111111111",
    });
    render(<ChatScreen />);

    expect(screen.queryByText("Your projects")).not.toBeInTheDocument();
    const composer = screen.getByLabelText("Question for Ralion");
    await userEvent.type(composer, "What is the remote work policy?");
    fireEvent.keyDown(composer, { key: "Enter", code: "Enter" });

    await waitFor(() =>
      expect(askChat).toHaveBeenCalledWith(
        {
          mode: "policy",
          question: "What is the remote work policy?",
          conversationId: null,
        },
        expect.any(AbortSignal),
      ),
    );
  });

  it("sends the authorized membership id after an explicit project selection", async () => {
    mockMemberships([
      cargoMembership,
      {
        ...cargoMembership,
        membershipId: 43,
        projectId: 10,
        projectName: "Ralion",
        projectKey: "RAL",
      },
    ]);
    vi.mocked(askChat).mockResolvedValue({
      answer: "Run `cargo build`.",
      citations: [],
      fallback: true,
      fallback_reason: "no_evidence",
      trace_id: "trace-project",
      answer_status: "fallback",
      validator_outcome: null,
      claims: [],
      conflict: null,
      conversation_id: "22222222-2222-4222-8222-222222222222",
    });
    render(<ChatScreen />);

    expect(screen.getAllByRole("button", { name: /Company Policy/ })).toHaveLength(1);
    await userEvent.click(screen.getByRole("button", { name: /Company Policy/ }));
    expect(screen.getByRole("option", { name: /Ralion/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("option", { name: /Cargo/ }));
    const composer = screen.getByLabelText("Question for Ralion");
    await userEvent.type(composer, "How do I build the project?");
    fireEvent.keyDown(composer, { key: "Enter", code: "Enter" });

    await waitFor(() =>
      expect(askChat).toHaveBeenCalledWith(
        {
          mode: "project",
          membershipId: 42,
          question: "How do I build the project?",
          conversationId: null,
        },
        expect.any(AbortSignal),
      ),
    );
  });

  it("opens real citation evidence, switches citations, and closes without losing chat", async () => {
    vi.mocked(askChat).mockResolvedValue({
      answer: "Use the documented setup steps.",
      fallback: false,
      fallback_reason: null,
      trace_id: "trace-sources",
      conversation_id: "33333333-3333-4333-8333-333333333333",
      citations: [
        {
          chunk_id: 101,
          quote: "Install Rust first.",
          knowledge_domain: "PROJECT",
          relevance_score: 0.9,
          redacted: false,
          source_title: "README.md",
          section_heading: "Local development",
          source_content: "## Local development\n\nInstall Rust first.",
        },
        {
          chunk_id: 102,
          quote: "Run the tests.",
          knowledge_domain: "PROJECT",
          relevance_score: 0.86,
          redacted: false,
          source_title: "CONTRIBUTING.md",
          section_heading: "Testing",
          source_content: "## Testing\n\nRun the tests.",
        },
      ],
      answer_status: "verified",
      validator_outcome: "passed",
      conflict: null,
      claims: [
        {
          claim_index: 0,
          text: "Use the documented setup steps.",
          support_type: "inferred",
          verdict: "passed",
          redacted: false,
          citations: [
            {
              chunk_id: 101,
              quote: "Install Rust first.",
              knowledge_domain: "PROJECT",
              relevance_score: 0.9,
              redacted: false,
              source_title: "README.md",
              section_heading: "Local development",
              source_content: "## Local development\n\nInstall Rust first.",
            },
            {
              chunk_id: 102,
              quote: "Run the tests.",
              knowledge_domain: "PROJECT",
              relevance_score: 0.86,
              redacted: false,
              source_title: "CONTRIBUTING.md",
              section_heading: "Testing",
              source_content: "## Testing\n\nRun the tests.",
            },
          ],
        },
      ],
    });
    render(<ChatScreen />);
    const composer = screen.getByLabelText("Question for Ralion");
    await userEvent.type(composer, "How do I start?");
    fireEvent.keyDown(composer, { key: "Enter", code: "Enter" });

    await userEvent.click(await screen.findByRole("button", { name: "README.md" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("Install Rust first.");

    await userEvent.click(screen.getByRole("button", { name: "CONTRIBUTING.md" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("Run the tests.");

    await userEvent.click(screen.getByRole("button", { name: "Đóng" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByText("How do I start?")).toBeInTheDocument();
    expect(screen.getByLabelText("Question for Ralion")).toHaveValue("");
  });

  it("shows related evidence on an insufficient_evidence fallback and lets it be opened", async () => {
    vi.mocked(askChat).mockResolvedValue({
      answer:
        "I found documents related to this topic, but they do not answer your question directly, so I cannot give you a confident answer. Please confirm with the HR team.",
      fallback: true,
      fallback_reason: "insufficient_evidence",
      trace_id: "trace-related",
      conversation_id: "44444444-4444-4444-8444-444444444444",
      citations: [
        {
          chunk_id: 201,
          quote: "Remote work is permitted up to 3 days per week…",
          knowledge_domain: "POLICY",
          relevance_score: 0.4,
          redacted: false,
          source_title: "Remote Work Policy",
          section_heading: "Eligibility",
          source_content: "## Eligibility\n\nRemote work is permitted up to 3 days per week.",
        },
      ],
      answer_status: "fallback",
      validator_outcome: null,
      conflict: null,
      claims: [],
    });
    render(<ChatScreen />);
    const composer = screen.getByLabelText("Question for Ralion");
    await userEvent.type(composer, "What is the sabbatical policy?");
    fireEvent.keyDown(composer, { key: "Enter", code: "Enter" });

    expect(await screen.findByText(/HR team/)).toBeInTheDocument();
    const relatedSource = screen.getByRole("button", { name: "Remote Work Policy" });
    expect(relatedSource).toBeInTheDocument();

    await userEvent.click(relatedSource);
    expect(screen.getByRole("dialog")).toHaveTextContent(
      "Remote work is permitted up to 3 days per week.",
    );
  });

  it("renders only surviving claims and keeps multiple inferred sources attached to that claim", async () => {
    vi.mocked(askChat).mockResolvedValue({
      answer: "The setup uses Rust. Unsupported detail must not render.",
      fallback: false,
      fallback_reason: null,
      trace_id: "trace-degraded",
      conversation_id: "34333333-3333-4333-8333-333333333333",
      answer_status: "partially_verified",
      validator_outcome: "degraded",
      conflict: null,
      citations: [],
      claims: [
        {
          claim_index: 0,
          text: "The setup uses Rust.",
          support_type: "inferred",
          verdict: "passed",
          redacted: false,
          citations: [
            {
              chunk_id: 201,
              quote: "Install Rust.",
              knowledge_domain: "PROJECT",
              relevance_score: 0.91,
              redacted: false,
              source_title: "README.md",
            },
            {
              chunk_id: 202,
              quote: "Use the stable toolchain.",
              knowledge_domain: "PROJECT",
              relevance_score: 0.88,
              redacted: false,
              source_title: "rust-toolchain.toml",
            },
          ],
        },
      ],
    });
    render(<ChatScreen />);

    const composer = screen.getByLabelText("Question for Ralion");
    await userEvent.type(composer, "How is the toolchain configured?");
    fireEvent.keyDown(composer, { key: "Enter", code: "Enter" });

    expect(await screen.findByText("The setup uses Rust.")).toBeInTheDocument();
    expect(screen.queryByText(/Unsupported detail/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Some unsupported details were omitted/)).not.toBeInTheDocument();
    expect(screen.getByLabelText("Sources for claim 1")).toHaveTextContent("README.md");
    expect(screen.getByLabelText("Sources for claim 1")).toHaveTextContent("rust-toolchain.toml");
  });

  it("renders grounded claims and uncited general guidance in separate sections", async () => {
    vi.mocked(askChat).mockResolvedValue({
      answer: "Use the repository setup steps.\n\nGeneral guidance: create a virtualenv.",
      fallback: false,
      fallback_reason: null,
      trace_id: "trace-mixed",
      conversation_id: "36333333-3333-4333-8333-333333333333",
      answer_status: "verified",
      validator_outcome: "passed",
      conflict: null,
      citations: [],
      claims: [
        {
          claim_index: 0,
          text: "Use the repository setup steps.",
          support_type: "direct",
          verdict: "passed",
          redacted: false,
          citations: [],
        },
      ],
      general_guidance: [
        { text: "Create a virtualenv with `python -m venv .venv`.", kind: "instruction" },
      ],
      answer_shape: "mixed",
    });
    render(<ChatScreen />);

    const composer = screen.getByLabelText("Question for Ralion");
    await userEvent.type(composer, "How do I set up the project?");
    fireEvent.keyDown(composer, { key: "Enter", code: "Enter" });

    expect(await screen.findByText("Use the repository setup steps.")).toBeInTheDocument();
    const guidance = screen.getByLabelText("General technical guidance");
    expect(guidance).toHaveTextContent("Create a virtualenv");
    expect(guidance).toHaveTextContent("Suggested steps");
    expect(
      screen.getByText(
        "This section is common technical knowledge, not drawn from the project documents.",
      ),
    ).toBeInTheDocument();
  });

  it("shows conflict context without treating backend text as raw HTML", async () => {
    vi.mocked(askChat).mockResolvedValue({
      answer: "The sources specify different rollout dates.",
      fallback: false,
      fallback_reason: null,
      trace_id: "trace-conflict",
      conversation_id: "35333333-3333-4333-8333-333333333333",
      answer_status: "conflict",
      validator_outcome: "passed",
      conflict: "Policy A says June; Policy B says July. <img src=x onerror=alert(1)>",
      citations: [],
      claims: [
        {
          claim_index: 0,
          text: "The sources specify different rollout dates. <script>alert(1)</script>",
          support_type: "inferred",
          verdict: "passed",
          redacted: false,
          citations: [],
        },
      ],
    });
    render(<ChatScreen />);

    const composer = screen.getByLabelText("Question for Ralion");
    await userEvent.type(composer, "When does the policy start?");
    fireEvent.keyDown(composer, { key: "Enter", code: "Enter" });

    expect(await screen.findByText("Sources conflict")).toBeInTheDocument();
    expect(screen.getByText(/Policy A says June/)).toBeInTheDocument();
    expect(document.querySelector("script")).toBeNull();
    expect(document.querySelector("img[src='x']")).toBeNull();
  });

  it("continues the conversation on the follow-up question", async () => {
    const conversationId = "44444444-4444-4444-8444-444444444444";
    vi.mocked(askChat).mockResolvedValue({
      answer: "Employees receive 12 leave days.",
      citations: [],
      fallback: false,
      fallback_reason: null,
      trace_id: "trace-follow-up",
      answer_status: "verified",
      validator_outcome: "passed",
      claims: [],
      conflict: null,
      conversation_id: conversationId,
    });
    render(<ChatScreen />);
    const composer = screen.getByLabelText("Question for Ralion");

    await userEvent.type(composer, "How does annual leave work?");
    fireEvent.keyDown(composer, { key: "Enter", code: "Enter" });
    await screen.findByText("How does annual leave work?");
    await userEvent.type(composer, "cai do ap dung tu khi nao?");
    fireEvent.keyDown(composer, { key: "Enter", code: "Enter" });

    await waitFor(() =>
      expect(askChat).toHaveBeenLastCalledWith(
        {
          mode: "policy",
          question: "cai do ap dung tu khi nao?",
          conversationId,
        },
        expect.any(AbortSignal),
      ),
    );
  });

  it("rebuilds the thread from the server when the page is reloaded", async () => {
    const conversationId = "55555555-5555-4555-8555-555555555555";
    window.localStorage.setItem("ralion.chat.conversation.POLICY", conversationId);
    vi.mocked(fetchConversation).mockResolvedValue({
      conversation_id: conversationId,
      mode: "POLICY",
      membership_id: null,
      turns: [
        {
          turn_index: 0,
          question: "How does annual leave work?",
          answer: "Employees receive 12 leave days.",
          fallback: false,
          fallback_reason: null,
          trace_id: "trace-stored",
          citations: [],
          answer_status: "verified",
          validator_outcome: "passed",
          claims: [],
          conflict: null,
        },
        // A turn that never got an answer (crash between persisting the question and replying)
        // must not be replayed as if Ralion had responded.
        {
          turn_index: 1,
          question: "cai do ap dung tu khi nao?",
          answer: null,
          fallback: false,
          fallback_reason: null,
          trace_id: null,
          citations: [],
          answer_status: null,
          validator_outcome: null,
          claims: [],
          conflict: null,
        },
        {
          turn_index: 2,
          question: "How do I set up the project?",
          answer: "Use the repository setup steps.\n\nGeneral guidance: create a virtualenv.",
          fallback: false,
          fallback_reason: null,
          trace_id: "trace-stored-mixed",
          citations: [],
          answer_status: "verified",
          validator_outcome: "passed",
          claims: [
            {
              claim_index: 0,
              text: "Use the repository setup steps.",
              support_type: "direct",
              verdict: "passed",
              redacted: false,
              citations: [],
            },
          ],
          conflict: null,
          general_guidance: [
            { text: "Create a virtualenv with `python -m venv .venv`.", kind: "instruction" },
          ],
          answer_shape: "mixed",
        },
      ],
    });

    render(<ChatScreen />);

    await waitFor(() => expect(fetchConversation).toHaveBeenCalledWith(conversationId));
    await waitFor(() =>
      expect(screen.getByText("Employees receive 12 leave days.")).toBeInTheDocument(),
    );
    expect(screen.getByText("How does annual leave work?")).toBeInTheDocument();
    expect(screen.getByText("Use the repository setup steps.")).toBeInTheDocument();
    expect(screen.getByLabelText("General technical guidance")).toHaveTextContent(
      "Create a virtualenv",
    );
    expect(screen.queryByText("cai do ap dung tu khi nao?")).not.toBeInTheDocument();
  });

  it("forgets a stale conversation pointer instead of showing an error", async () => {
    window.localStorage.setItem(
      "ralion.chat.conversation.POLICY",
      "66666666-6666-4666-8666-666666666666",
    );
    vi.mocked(fetchConversation).mockRejectedValue(new ApiError(404, "Conversation not found"));
    vi.mocked(askChat).mockResolvedValue({
      answer: "The policy allows remote work.",
      citations: [],
      fallback: false,
      fallback_reason: null,
      trace_id: "trace-fresh",
      answer_status: "verified",
      validator_outcome: "passed",
      claims: [],
      conflict: null,
      conversation_id: "77777777-7777-4777-8777-777777777777",
    });
    render(<ChatScreen />);

    await waitFor(() =>
      expect(window.localStorage.getItem("ralion.chat.conversation.POLICY")).toBeNull(),
    );
    const composer = screen.getByLabelText("Question for Ralion");
    await userEvent.type(composer, "What is the remote work policy?");
    fireEvent.keyDown(composer, { key: "Enter", code: "Enter" });

    await waitFor(() =>
      expect(askChat).toHaveBeenCalledWith(
        {
          mode: "policy",
          question: "What is the remote work policy?",
          conversationId: null,
        },
        expect.any(AbortSignal),
      ),
    );
  });

  it("starts a new conversation when the user asks for one", async () => {
    vi.mocked(askChat).mockResolvedValue({
      answer: "Employees receive 12 leave days.",
      citations: [],
      fallback: false,
      fallback_reason: null,
      trace_id: "trace-reset",
      answer_status: "verified",
      validator_outcome: "passed",
      claims: [],
      conflict: null,
      conversation_id: "88888888-8888-4888-8888-888888888888",
    });
    render(<ChatScreen />);
    const composer = screen.getByLabelText("Question for Ralion");
    await userEvent.type(composer, "Which national holidays are observed?");
    fireEvent.keyDown(composer, { key: "Enter", code: "Enter" });
    await waitFor(() =>
      expect(screen.getByText("Employees receive 12 leave days.")).toBeInTheDocument(),
    );

    await userEvent.click(screen.getByRole("button", { name: "New conversation" }));

    expect(screen.queryByText("Which national holidays are observed?")).not.toBeInTheDocument();
    expect(window.localStorage.getItem("ralion.chat.conversation.POLICY")).toBeNull();
  });
});

describe("Ralion Chat navigation", () => {
  it("opens the Engineer Portal navigation from the mobile chat header", async () => {
    mockMemberships([cargoMembership]);
    render(<ChatScreen />);

    expect(screen.queryByRole("dialog", { name: "Điều hướng Engineer Portal" })).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Mở menu" }));

    const drawer = screen.getByRole("dialog", { name: "Điều hướng Engineer Portal" });
    expect(within(drawer).getByRole("link", { name: "Ralion Chat" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(within(drawer).getByRole("link", { name: "Checklist & Plan" })).toBeInTheDocument();
    expect(within(drawer).getByRole("button", { name: "Đăng xuất" })).toBeInTheDocument();
  });

  it("does not render a Conventions tab", () => {
    render(<ChatScreen />);

    expect(screen.queryByRole("tab", { name: "Conventions" })).not.toBeInTheDocument();
  });

  it("keeps chat personalization out of the chat surface entirely", () => {
    render(<ChatScreen />);

    expect(screen.queryByLabelText("Response length")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Response tone")).not.toBeInTheDocument();
  });
});
