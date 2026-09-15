import { afterEach, describe, expect, it, vi } from "vitest";

import {
  approveRuleCandidate,
  listApprovedConventions,
  listMemberConventions,
  listPendingRuleCandidates,
  listProjectApprovedConventions,
  reindexRuleCandidate,
  rejectRuleCandidate,
} from "@/features/conventions/api";
import type { RuleFamilyListDTO } from "@/features/conventions/dto/ruleFamily.response";
import {
  ApiError,
  CONVENTIONS_ENDPOINT,
  PM_PROJECT_SCOPED_ENDPOINT,
  PROJECT_CONVENTIONS_ENDPOINT,
} from "@/lib/api";

const emptyPage: RuleFamilyListDTO = {
  items: [],
  meta: { page: 2, page_size: 20, total: 0 },
};

/** Response mới cho từng call: một Response chỉ đọc được body đúng một lần. */
function mockFetch(body: unknown, status = 200) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async () => new Response(JSON.stringify(body), { status }));
}

describe("F6 rule-review data access", () => {
  afterEach(() => vi.restoreAllMocks());

  it("reads the pending queue from the project-scoped rule-candidates route with paging", async () => {
    const fetchMock = mockFetch(emptyPage);
    await listPendingRuleCandidates(7, 2, 20);
    expect(String(fetchMock.mock.calls[0][0])).toBe(
      `${PM_PROJECT_SCOPED_ENDPOINT}/7/rule-candidates/pending?page=2&page_size=20`,
    );
  });

  it("reads the PM's own project-scoped approved tab", async () => {
    const fetchMock = mockFetch(emptyPage);
    await listProjectApprovedConventions(7, 1, 20);
    expect(String(fetchMock.mock.calls[0][0])).toBe(
      `${PM_PROJECT_SCOPED_ENDPOINT}/7/rule-candidates/approved?page=1&page_size=20`,
    );
  });

  it("reads company-wide approved conventions from /conventions for the chat Member panel", async () => {
    const fetchMock = mockFetch(emptyPage);
    await listApprovedConventions(1, 20);
    expect(String(fetchMock.mock.calls[0][0])).toBe(`${CONVENTIONS_ENDPOINT}?page=1&page_size=20`);
  });

  it("reads the handbook from the server-authorized project route", async () => {
    const fetchMock = mockFetch(emptyPage);
    await listMemberConventions(17);
    expect(String(fetchMock.mock.calls[0][0])).toBe(
      `${PROJECT_CONVENTIONS_ENDPOINT}/17/conventions?page=1&page_size=50`,
    );
  });

  it("posts approve/reject/reindex to the project-scoped per-candidate endpoints", async () => {
    const fetchMock = mockFetch({ rule_family_id: 5, status: "APPROVED" });
    await approveRuleCandidate(7, 5);
    await rejectRuleCandidate(7, 5);
    await reindexRuleCandidate(7, 5);

    const calls = fetchMock.mock.calls.map(([input, init]) => [
      String(input),
      (init as RequestInit).method,
    ]);
    expect(calls).toEqual([
      [`${PM_PROJECT_SCOPED_ENDPOINT}/7/rule-candidates/5/approve`, "POST"],
      [`${PM_PROJECT_SCOPED_ENDPOINT}/7/rule-candidates/5/reject`, "POST"],
      [`${PM_PROJECT_SCOPED_ENDPOINT}/7/rule-candidates/5/reindex`, "POST"],
    ]);
  });

  it("surfaces the optimistic-lock conflict as ApiError 409 instead of swallowing it", async () => {
    mockFetch({ detail: "Rule candidate already reviewed" }, 409);
    await expect(approveRuleCandidate(7, 9)).rejects.toMatchObject({ status: 409 });
    await expect(approveRuleCandidate(7, 9)).rejects.toBeInstanceOf(ApiError);
  });
});
