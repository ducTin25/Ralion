/**
 * Data access cho F6 Rule Mining. Đây là nơi DUY NHẤT trong frontend biết URL/shape của
 * `/rule-candidates` và `/conventions` — PM (Rule Review) lẫn Member (Conventions) đều gọi
 * qua đây, không feature nào tự dựng fetch riêng.
 *
 * Không có logic mining/clustering/eligibility ở tầng này: backend đã lọc xong khi trả về,
 * client chỉ đọc và hiển thị.
 */

import { authHeaders } from "@/features/auth/session";
import {
  CONVENTIONS_ENDPOINT,
  PM_PROJECT_SCOPED_ENDPOINT,
  PROJECT_CONVENTIONS_ENDPOINT,
  requestJson,
} from "@/lib/api";
import type {
  RuleFamilyActionResultDTO,
  RuleFamilyListDTO,
} from "@/features/conventions/dto/ruleFamily.response";
import type { MemberConventionListDTO } from "@/features/conventions/dto/memberConvention.response";

/** Approve chạy embed + index vào retrieval engine ngay trong request nên chậm hơn CRUD
 * thường; dùng ngân sách riêng thay vì mặc định 12s của `requestJson`. */
const RULE_DECISION_TIMEOUT_MS = 30_000;

function pageQuery(page: number, pageSize: number) {
  return `?page=${page}&page_size=${pageSize}`;
}

/** `/pm/projects/{projectId}/rule-candidates` — scoped to the PM's own project's connected
 * GitHub repo server-side (see src/api/routers/rule_review_router.py's `_project_repo_or_404`).
 * A PM only ever sees/decides candidates mined from their own project's repo. */
function ruleCandidatesEndpoint(projectId: number): string {
  return `${PM_PROJECT_SCOPED_ENDPOINT}/${projectId}/rule-candidates`;
}

export function listPendingRuleCandidates(
  projectId: number,
  page: number,
  pageSize: number,
  signal?: AbortSignal,
): Promise<RuleFamilyListDTO> {
  return requestJson<RuleFamilyListDTO>(
    `${ruleCandidatesEndpoint(projectId)}/pending${pageQuery(page, pageSize)}`,
    { headers: authHeaders(), signal },
  );
}

/** PM's own "Đã duyệt" tab in the Review Queue — project-scoped, distinct from
 * `listApprovedConventions` below (company-wide, used by the chat Member Conventions panel). */
export function listProjectApprovedConventions(
  projectId: number,
  page: number,
  pageSize: number,
  signal?: AbortSignal,
): Promise<RuleFamilyListDTO> {
  return requestJson<RuleFamilyListDTO>(
    `${ruleCandidatesEndpoint(projectId)}/approved${pageQuery(page, pageSize)}`,
    { headers: authHeaders(), signal },
  );
}

/** Company-wide approved conventions. Used only by the chat Member Conventions panel, which has
 * no project in scope (a chat session can be company-scoped) — kept unscoped on purpose. */
export function listApprovedConventions(
  page: number,
  pageSize: number,
  signal?: AbortSignal,
): Promise<RuleFamilyListDTO> {
  return requestJson<RuleFamilyListDTO>(`${CONVENTIONS_ENDPOINT}${pageQuery(page, pageSize)}`, {
    headers: authHeaders(),
    signal,
  });
}

/** Handbook projection for one ACL-authorized Engineer project. This endpoint is a plain
 * approved-rule/evidence DB read; it does not invoke Chat, retrieval, or an LLM. */
export function listMemberConventions(
  projectId: number,
  signal?: AbortSignal,
): Promise<MemberConventionListDTO> {
  return requestJson<MemberConventionListDTO>(
    `${PROJECT_CONVENTIONS_ENDPOINT}/${projectId}/conventions?page=1&page_size=50`,
    { headers: authHeaders(), signal },
  );
}

/** 409 = optimistic-lock loss (người khác đã duyệt trước). Ném nguyên ApiError để tầng hook
 * xử lý, không nuốt lỗi ở đây. */
export function approveRuleCandidate(
  projectId: number,
  ruleFamilyId: number,
): Promise<RuleFamilyActionResultDTO> {
  return requestJson<RuleFamilyActionResultDTO>(
    `${ruleCandidatesEndpoint(projectId)}/${ruleFamilyId}/approve`,
    { method: "POST", headers: authHeaders() },
    { timeoutMs: RULE_DECISION_TIMEOUT_MS },
  );
}

export function rejectRuleCandidate(
  projectId: number,
  ruleFamilyId: number,
): Promise<RuleFamilyActionResultDTO> {
  return requestJson<RuleFamilyActionResultDTO>(
    `${ruleCandidatesEndpoint(projectId)}/${ruleFamilyId}/reject`,
    { method: "POST", headers: authHeaders() },
  );
}

/** Retry khi index lúc approve thất bại (`retrieval_indexed=false`). Idempotent phía backend. */
export function reindexRuleCandidate(
  projectId: number,
  ruleFamilyId: number,
): Promise<RuleFamilyActionResultDTO> {
  return requestJson<RuleFamilyActionResultDTO>(
    `${ruleCandidatesEndpoint(projectId)}/${ruleFamilyId}/reindex`,
    { method: "POST", headers: authHeaders() },
    { timeoutMs: RULE_DECISION_TIMEOUT_MS },
  );
}
