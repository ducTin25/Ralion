import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listMemberConventions } from "@/features/conventions/api";
import { MemberConventionsView } from "@/features/conventions/components/MemberConventionsView";
import type {
  MemberConventionEvidenceDTO,
  MemberConventionListDTO,
} from "@/features/conventions/dto/memberConvention.response";

vi.mock("@/features/conventions/api", () => ({
  listMemberConventions: vi.fn(),
}));

const evidence = {
  comment_snippet_snapshot: "Please use the project context.",
  original_author: "reviewer",
  pr_number: 42,
  evidence_created_at: "2026-08-01T00:00:00",
  permalink: "https://github.com/acme/widgets/pull/42#discussion_r1",
};

function response(overrides: Partial<MemberConventionEvidenceDTO>): MemberConventionListDTO {
  return {
    items: [
      {
        rule_family_id: 8,
        rule_text: "Use the explicit project context.",
        short_explanation: null,
        how_to_apply: null,
        rationale: null,
        illustrative_bad_example: null,
        illustrative_good_example: null,
        actual_examples: [],
        evidence: [{ ...evidence, ...overrides }],
      },
    ],
    meta: { page: 1, page_size: 50, total: 1 },
  };
}

describe("Member conventions evidence", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders a single code snapshot from Member evidence", async () => {
    vi.mocked(listMemberConventions).mockResolvedValue(
      response({ code_snippet_snapshot: "const context = project.context;" }),
    );

    render(<MemberConventionsView projectId={17} />);

    expect(await screen.findByLabelText("Code snippet")).toHaveTextContent(
      "const context = project.context;",
    );
  });

  it("renders before and after code context from Member evidence", async () => {
    vi.mocked(listMemberConventions).mockResolvedValue(
      response({
        code_snippet_snapshot: "const context = project.context;",
        code_before_snapshot: "const context = undefined;",
        code_after_snapshot: "const context = project.context;",
      }),
    );

    render(<MemberConventionsView projectId={17} />);

    expect(await screen.findByLabelText("Code before change")).toHaveTextContent(
      "const context = undefined;",
    );
    expect(screen.getByLabelText("Code after change")).toHaveTextContent(
      "const context = project.context;",
    );
    expect(screen.queryByLabelText("Code snippet")).not.toBeInTheDocument();
  });

  it("keeps legacy evidence with no code context readable", async () => {
    vi.mocked(listMemberConventions).mockResolvedValue(response({}));

    render(<MemberConventionsView projectId={17} />);

    expect(await screen.findByText(evidence.comment_snippet_snapshot)).toBeInTheDocument();
    expect(screen.queryByLabelText("Code snippet")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Code before change")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Code after change")).not.toBeInTheDocument();
  });
});
