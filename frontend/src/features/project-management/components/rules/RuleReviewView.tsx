"use client";

import { useMemo } from "react";
import { useLocale, useTranslations } from "next-intl";

import { EvidencePermalinkCard } from "@/features/conventions/components/EvidencePermalinkCard";
import {
  RULE_REVIEW_PAGE_SIZE,
  useRuleReviewQueue,
  type RuleReviewFilter,
  type RuleRowNotice,
} from "@/features/conventions/hooks/useRuleReviewQueue";
import type { RuleFamilyItemDTO } from "@/features/conventions/dto/ruleFamily.response";
import type { ProjectResponseDTO } from "@/features/project-management/dto/responseDTO/project.response";
import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import { PmButton } from "@/features/project-management/components/ui/PmButton";
import {
  PmCard,
  PmPageHead,
  PmSectionTitle,
} from "@/features/project-management/components/ui/PmCard";
import { PmPill, PmTag } from "@/features/project-management/components/ui/PmPill";
import { PmTableFooter } from "@/features/project-management/components/ui/PmTableFooter";

import styles from "./RuleReviewView.module.scss";

const FILTER_TABS: { key: RuleReviewFilter; labelKey: "pending" | "approved" }[] = [
  { key: "PENDING", labelKey: "pending" },
  { key: "APPROVED", labelKey: "approved" },
];

const CONFIDENCE_META: Record<
  string,
  { labelKey: "highMatch" | "mediumMatch"; variant: "success" | "warning" }
> = {
  HIGH: { labelKey: "highMatch", variant: "success" },
  MEDIUM: { labelKey: "mediumMatch", variant: "warning" },
};

/**
 * "2 bằng chứng · 1 reviewer (GiedriusS x2)" — provenance để PM tự đánh giá.
 *
 * `distinct_reviewer_count` lấy nguyên từ backend; phần trong ngoặc chỉ là cách trình bày lại
 * danh sách evidence đã có sẵn trong response. UI không diễn giải con số này thành score hay
 * thành filter ẩn — nó không phải điều kiện eligibility.
 */
function reviewerBreakdown(candidate: RuleFamilyItemDTO) {
  const counts = new Map<string, number>();
  for (const evidence of candidate.evidence) {
    counts.set(evidence.original_author, (counts.get(evidence.original_author) ?? 0) + 1);
  }
  const breakdown = [...counts.entries()]
    .map(([author, count]) => (count > 1 ? `${author} x${count}` : author))
    .join(", ");
  return breakdown ? ` (${breakdown})` : "";
}

function RuleCandidateCard({
  candidate,
  busy,
  notice,
  onDecide,
  onReindex,
}: {
  candidate: RuleFamilyItemDTO;
  busy: boolean;
  notice: RuleRowNotice | undefined;
  onDecide: (action: "approve" | "reject") => void;
  onReindex: () => void;
}) {
  const t = useTranslations("pmUi");
  const locale = useLocale();
  const confidence = candidate.family_match_confidence
    ? CONFIDENCE_META[candidate.family_match_confidence]
    : undefined;

  const noticeClass = [
    styles.notice,
    notice?.kind === "conflict" && styles.noticeConflict,
    notice?.kind === "error" && styles.noticeError,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <PmCard className={styles.candidate}>
      <div className={styles.candidateHead}>
        <p className={styles.ruleText}>{candidate.rule_text}</p>
        <div className={styles.badges}>
          {confidence ? (
            <PmPill variant={confidence.variant}>{t(confidence.labelKey)}</PmPill>
          ) : (
            <PmPill variant="neutral">{t("noMatchScore")}</PmPill>
          )}
          {/* Badge riêng, tách khỏi độ khớp: đây là provenance, không phải eligibility. */}
          <PmTag>
            {t("reviewerSummary", {
              evidence: candidate.evidence.length,
              reviewers: candidate.distinct_reviewer_count,
              breakdown: reviewerBreakdown(candidate),
            })}
          </PmTag>
          {candidate.status !== "PENDING" && (
            <PmPill variant={candidate.status === "APPROVED" ? "success" : "neutral"}>
              {candidate.status === "APPROVED" ? t("approved") : t("rejected")}
            </PmPill>
          )}
        </div>
      </div>

      <div className={styles.evidenceList}>
        {candidate.evidence.map((evidence, index) => (
          <EvidencePermalinkCard
            key={`${candidate.rule_family_id}-${index}`}
            evidence={evidence}
            showMatchMetadata
            locale={locale}
            openLabel={t("openOriginalPr")}
            matchLabel={t("cosineMatch", {
              score: evidence.cluster_edge_cosine_similarity?.toFixed(2) ?? "-",
            })}
          />
        ))}
      </div>

      {notice && (
        <div className={noticeClass} role="status">
          <PmIcon name="alert" size={14} />
          <span>{notice.message}</span>
          {notice.kind === "not-indexed" && (
            <PmButton size="sm" disabled={busy} onClick={onReindex}>
              {t("reindex")}
            </PmButton>
          )}
        </div>
      )}

      {candidate.status === "PENDING" && (
        <div className={styles.actions}>
          {/* Không có sửa-trước-khi-duyệt trong MVP: muốn rule khác đi thì Từ chối. */}
          <PmButton size="sm" disabled={busy} onClick={() => onDecide("reject")}>
            {t("reject")}
          </PmButton>
          <PmButton size="sm" variant="primary" disabled={busy} onClick={() => onDecide("approve")}>
            {busy ? t("sending") : t("approve")}
          </PmButton>
        </div>
      )}
    </PmCard>
  );
}

/**
 * PM Rule Review Queue (UI_SPEC B.2).
 *
 * Project-scoped: backend F6 candidates/conventions are filtered to `project.github_repo`
 * server-side (rule_review_router `_project_repo_or_404`), so this view only ever shows/decides
 * candidates mined from the PM's own project's repo.
 */
export function RuleReviewView({ project }: { project: ProjectResponseDTO | null }) {
  const t = useTranslations("pmUi");
  const queue = useRuleReviewQueue(true, project?.project_id ?? null);

  // Hooks above must run unconditionally on every render — the `!project` early return stays
  // below all of them, same ordering DocumentsView already uses for the same situation.
  const emptyLabel = useMemo(
    () =>
      queue.filter === "PENDING"
        ? t("ruleReviewEmptyPending")
        : t("ruleReviewEmptyApproved"),
    [queue.filter, t],
  );

  if (!project) {
    return (
      <section>
        <PmPageHead icon="shield" title={t("ruleReview")} />
        <PmCard>
          <p>{t("noManagedProject")}</p>
        </PmCard>
      </section>
    );
  }

  return (
    <section>
      <PmPageHead icon="shield" title={t("ruleReview")} subtitle={t("ruleReviewSubtitle")} />

      {/* Governance note cố định — không phải tip có thể tắt. */}
      <p className={styles.governance}>
        <PmIcon name="shield" size={15} />
        <span>
          {t("ruleReviewGovernance")}
        </span>
      </p>

      <div className={styles.toolbar} role="tablist" aria-label={t("filterByStatus")}>
        {FILTER_TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={queue.filter === tab.key}
            className={`${styles.filterTab} ${queue.filter === tab.key ? styles.filterActive : ""}`}
            onClick={() => queue.changeFilter(tab.key)}
          >
            {t(tab.labelKey)}
          </button>
        ))}
      </div>

      <PmSectionTitle hint={t("ruleEvidenceGuardrail")}>
        {queue.filter === "PENDING" ? t("waitingOnPm") : t("approvedConvention")}
      </PmSectionTitle>

      {queue.error ? (
        <PmCard className={styles.stateCard}>
          <p className={styles.errorText}>{queue.error}</p>
          <PmButton size="sm" onClick={() => void queue.refresh()}>
            {t("tryAgain")}
          </PmButton>
        </PmCard>
      ) : queue.loading ? (
        <PmCard className={styles.stateCard}>
          <p className={styles.mutedText}>{t("loading")}</p>
        </PmCard>
      ) : queue.items.length === 0 ? (
        <PmCard className={styles.stateCard}>
          <p className={styles.mutedText}>{emptyLabel}</p>
        </PmCard>
      ) : (
        <div className={styles.candidateList}>
          {queue.items.map((candidate) => (
            <RuleCandidateCard
              key={candidate.rule_family_id}
              candidate={candidate}
              busy={queue.busyId === candidate.rule_family_id}
              notice={queue.notices[candidate.rule_family_id]}
              onDecide={(action) => void queue.decide(candidate.rule_family_id, action)}
              onReindex={() => void queue.reindex(candidate.rule_family_id)}
            />
          ))}
        </div>
      )}

      <PmTableFooter
        total={queue.meta.total}
        page={queue.page}
        pageSize={RULE_REVIEW_PAGE_SIZE}
        onPageChange={queue.setPage}
      />
    </section>
  );
}
