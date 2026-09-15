import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  approveRuleCandidate,
  listPendingRuleCandidates,
  listProjectApprovedConventions,
  reindexRuleCandidate,
  rejectRuleCandidate,
} from "@/features/conventions/api";
import type {
  RuleFamilyItemDTO,
  RuleFamilyListDTO,
} from "@/features/conventions/dto/ruleFamily.response";
import type { ProjectResponseDTO } from "@/features/project-management/dto/responseDTO/project.response";
import { RuleReviewView } from "@/features/project-management/components/rules/RuleReviewView";
import { ApiError } from "@/lib/api";

vi.mock("@/features/conventions/api", () => ({
  listPendingRuleCandidates: vi.fn(),
  listProjectApprovedConventions: vi.fn(),
  approveRuleCandidate: vi.fn(),
  rejectRuleCandidate: vi.fn(),
  reindexRuleCandidate: vi.fn(),
}));

const project: ProjectResponseDTO = {
  project_id: 7,
  key: "PROJ",
  name: "Project",
  primary_pm_membership_id: 1,
  created_by_admin_id: 1,
  status: "ACTIVE",
  sync_status: "SUCCESS",
  last_synced_at: null,
  created_at: "2026-08-01T00:00:00",
  github_repo: "thanos-io/thanos",
  default_branch: "main",
  github_credential_status: "VALID",
};

const candidate: RuleFamilyItemDTO = {
  rule_family_id: 11,
  rule_text: "Always guard nil pointers before dereferencing in the store gateway.",
  status: "PENDING",
  distinct_reviewer_count: 1,
  family_match_confidence: "HIGH",
  evidence: [
    {
      comment_snippet_snapshot: "Please nil-check before dereferencing here.",
      original_author: "GiedriusS",
      evidence_created_at: "2026-05-02T08:15:00",
      permalink: "https://github.com/thanos-io/thanos/pull/8792#discussion_r1",
      cluster_edge_cosine_similarity: null,
    },
    {
      comment_snippet_snapshot: "Same nil-check issue as the previous PR.",
      original_author: "GiedriusS",
      evidence_created_at: "2026-05-09T09:00:00",
      permalink: "https://github.com/thanos-io/thanos/pull/8801#discussion_r2",
      cluster_edge_cosine_similarity: 0.874,
    },
  ],
};

function page(items: RuleFamilyItemDTO[]): RuleFamilyListDTO {
  return { items, meta: { page: 1, page_size: 20, total: items.length } };
}

describe("PM Rule Review queue", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listPendingRuleCandidates).mockResolvedValue(page([candidate]));
    vi.mocked(listProjectApprovedConventions).mockResolvedValue(page([]));
  });

  it("shows the rule, its evidence permalinks and provenance separate from match confidence", async () => {
    render(<RuleReviewView project={project} />);

    expect(await screen.findByText(candidate.rule_text)).toBeInTheDocument();
    expect(screen.getByText("Khớp cao")).toBeInTheDocument();
    // Provenance đứng riêng, không bị gộp vào badge độ khớp.
    expect(
      screen.getByText("2 bằng chứng · 1 reviewer (GiedriusS x2)"),
    ).toBeInTheDocument();
    expect(screen.getByText("Độ khớp cosine=0.87")).toBeInTheDocument();

    const links = screen.getAllByRole("link");
    expect(links.map((link) => link.getAttribute("href"))).toEqual(
      candidate.evidence.map((evidence) => evidence.permalink),
    );
  });

  it("carries the fixed governance note that cannot be dismissed", async () => {
    render(<RuleReviewView project={project} />);
    await screen.findByText(candidate.rule_text);

    const note = screen.getByText(/repository mã nguồn mở công khai/);
    expect(note).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /dismiss|close/i })).not.toBeInTheDocument();
  });

  it("optimistically marks a rule APPROVED after the backend accepts the decision", async () => {
    vi.mocked(approveRuleCandidate).mockResolvedValue({
      rule_family_id: 11,
      status: "APPROVED",
      approved_by: 3,
      approved_at: "2026-08-21T02:00:00",
      rejected_by: null,
      rejected_at: null,
      retrieval_indexed: true,
    });

    render(<RuleReviewView project={project} />);
    await userEvent.click(await screen.findByRole("button", { name: "Duyệt" }));

    expect(approveRuleCandidate).toHaveBeenCalledWith(7, 11);
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Duyệt" })).not.toBeInTheDocument(),
    );
    // "Đã duyệt" cũng là nhãn của tab filter — chỉ lấy badge trạng thái trên thẻ candidate.
    const decidedBadges = screen
      .getAllByText("Đã duyệt")
      .filter((element) => element.getAttribute("role") !== "tab");
    expect(decidedBadges).toHaveLength(1);
  });

  it("explains a 409 optimistic-lock loss and refreshes instead of failing silently", async () => {
    vi.mocked(approveRuleCandidate).mockRejectedValue(
      new ApiError(409, "Rule candidate already reviewed"),
    );

    render(<RuleReviewView project={project} />);
    await userEvent.click(await screen.findByRole("button", { name: "Duyệt" }));

    expect(await screen.findByText(/vừa duyệt quy ước này/)).toBeInTheDocument();
    await waitFor(() => expect(listPendingRuleCandidates).toHaveBeenCalledTimes(2));
  });

  it("offers a retry when the approved rule did not reach the retrieval engine", async () => {
    vi.mocked(approveRuleCandidate).mockResolvedValue({
      rule_family_id: 11,
      status: "APPROVED",
      approved_by: 3,
      approved_at: "2026-08-21T02:00:00",
      rejected_by: null,
      rejected_at: null,
      retrieval_indexed: false,
    });
    vi.mocked(reindexRuleCandidate).mockResolvedValue({
      rule_family_id: 11,
      status: "APPROVED",
      approved_by: 3,
      approved_at: "2026-08-21T02:00:00",
      rejected_by: null,
      rejected_at: null,
      retrieval_indexed: true,
    });

    render(<RuleReviewView project={project} />);
    await userEvent.click(await screen.findByRole("button", { name: "Duyệt" }));

    await userEvent.click(await screen.findByRole("button", { name: "Đánh chỉ mục lại" }));
    expect(reindexRuleCandidate).toHaveBeenCalledWith(7, 11);
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Đánh chỉ mục lại" })).not.toBeInTheDocument(),
    );
  });

  it("reads the project-scoped approved tab when the filter switches, with no REJECTED tab", async () => {
    render(<RuleReviewView project={project} />);
    await screen.findByText(candidate.rule_text);

    await userEvent.click(screen.getByRole("tab", { name: "Đã duyệt" }));

    await waitFor(() => expect(listProjectApprovedConventions).toHaveBeenCalled());
    expect(screen.queryByRole("tab", { name: /từ chối/i })).not.toBeInTheDocument();
    expect(rejectRuleCandidate).not.toHaveBeenCalled();
  });
});
