"use client";

import { useCallback, useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { listMemberConventions } from "@/features/conventions/api";
import { EvidencePermalinkCard } from "@/features/conventions/components/EvidencePermalinkCard";
import type { MemberConventionItemDTO } from "@/features/conventions/dto/memberConvention.response";
import { MemberIcon } from "@/features/member-onboarding/components/MemberIcon";

import styles from "./MemberConventionsView.module.scss";

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}

type ConventionLoadResult = {
  projectId: number;
  items: MemberConventionItemDTO[];
  error: string | null;
};

function IllustrativeExample({ rule }: { rule: MemberConventionItemDTO }) {
  const t = useTranslations("conventions");
  if (!rule.illustrative_bad_example && !rule.illustrative_good_example) return null;
  return (
    <section
      className={styles.detailSection}
      aria-labelledby={`illustrative-${rule.rule_family_id}`}
    >
      <h3 id={`illustrative-${rule.rule_family_id}`}>{t("illustrativeExample")}</h3>
      <p className={styles.sectionHint}>{t("illustrativeHint")}</p>
      <div className={styles.examplePair}>
        {rule.illustrative_bad_example && (
          <div>
            <b>{t("avoid")}</b>
            <pre>
              <code>{rule.illustrative_bad_example}</code>
            </pre>
          </div>
        )}
        {rule.illustrative_good_example && (
          <div>
            <b>{t("prefer")}</b>
            <pre>
              <code>{rule.illustrative_good_example}</code>
            </pre>
          </div>
        )}
      </div>
    </section>
  );
}

function ConventionDetail({ rule }: { rule: MemberConventionItemDTO }) {
  const t = useTranslations("conventions");
  const locale = useLocale();
  return (
    <article className={styles.detail} aria-labelledby={`convention-${rule.rule_family_id}`}>
      <header className={styles.detailHeader}>
        <h2 id={`convention-${rule.rule_family_id}`}>{rule.rule_text}</h2>
      </header>

      {rule.how_to_apply && (
        <section className={styles.detailSection} aria-labelledby={`how-${rule.rule_family_id}`}>
          <h3 id={`how-${rule.rule_family_id}`}>{t("howToApply")}</h3>
          <p>{rule.how_to_apply}</p>
        </section>
      )}

      <section className={styles.detailSection} aria-labelledby={`why-${rule.rule_family_id}`}>
        <h3 id={`why-${rule.rule_family_id}`}>{t("why")}</h3>
        <p>{rule.rationale ?? t("noRationale")}</p>
      </section>

      {rule.actual_examples.length > 0 && (
        <section className={styles.detailSection} aria-labelledby={`actual-${rule.rule_family_id}`}>
          <h3 id={`actual-${rule.rule_family_id}`}>{t("actualExample")}</h3>
          {rule.actual_examples.map((example, index) => (
            <div className={styles.actualExample} key={`${example.pr_number}-${index}`}>
              <div>
                <b>PR #{example.pr_number}</b>
                <span>{t("quotedReview", { author: example.original_author })}</span>
              </div>
              <pre>
                <code>{example.code}</code>
              </pre>
              <a href={example.permalink} target="_blank" rel="noopener noreferrer">
                {t("openReviewComment")} <span aria-hidden="true">↗</span>
              </a>
            </div>
          ))}
        </section>
      )}

      <IllustrativeExample rule={rule} />

      <section className={styles.detailSection} aria-labelledby={`evidence-${rule.rule_family_id}`}>
        <h3 id={`evidence-${rule.rule_family_id}`}>{t("evidenceHistory")}</h3>
        <div className={styles.evidenceList}>
          {rule.evidence.map((evidence, index) => (
            <EvidencePermalinkCard
              key={`${rule.rule_family_id}-${index}`}
              evidence={evidence}
              prNumber={evidence.pr_number}
              locale={locale === "vi" ? "vi-VN" : "en-GB"}
              openLabel={t("openReviewComment")}
            />
          ))}
        </div>
      </section>
    </article>
  );
}

export function MemberConventionsView({ projectId }: { projectId: number }) {
  const t = useTranslations("conventions");
  const [result, setResult] = useState<ConventionLoadResult | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const response = await listMemberConventions(projectId, signal);
        if (signal?.aborted) return null;
        return { projectId, items: response.items, error: null };
      } catch (caught) {
        if (signal?.aborted || isAbortError(caught)) return null;
        return {
          projectId,
          items: [],
          error: caught instanceof Error ? caught.message : t("loadError"),
        };
      }
    },
    [projectId, t],
  );

  const applyResult = useCallback((nextResult: ConventionLoadResult | null) => {
    if (!nextResult) return;
    setResult(nextResult);
    setSelectedId((current) =>
      nextResult.items.some((item) => item.rule_family_id === current)
        ? current
        : (nextResult.items[0]?.rule_family_id ?? null),
    );
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal).then(applyResult);
    return () => controller.abort();
  }, [applyResult, load]);

  const activeResult = result?.projectId === projectId ? result : null;
  const items = activeResult?.items ?? [];
  const error = activeResult?.error ?? null;
  const loading = activeResult === null;
  const selected = items.find((item) => item.rule_family_id === selectedId) ?? null;
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.titleWithIcon}>
          <span>
            <MemberIcon name="book" size={20} />
          </span>
          {t("title")}
        </h1>
        <p className={styles.governance}>
          <MemberIcon name="shield" size={15} />
          {t("governance")}
        </p>
      </header>

      {error ? (
        <div className={styles.state} role="alert">
          <p>{error}</p>
          <button
            type="button"
            onClick={() => {
              setResult(null);
              void load().then(applyResult);
            }}
          >
            {t("retry")}
          </button>
        </div>
      ) : loading ? (
        <div className={styles.state} role="status">
          {t("loadingApproved")}
        </div>
      ) : items.length === 0 ? (
        <div className={styles.state}>
          <p>{t("emptyApproved")}</p>
        </div>
      ) : (
        <div className={styles.handbook}>
          <nav className={styles.list} aria-label={t("approvedLabel")}>
            {items.map((rule) => {
              const prCount = new Set(rule.evidence.map((evidence) => evidence.pr_number)).size;
              const selectedRule = rule.rule_family_id === selectedId;
              return (
                <button
                  type="button"
                  key={rule.rule_family_id}
                  className={selectedRule ? styles.listItemActive : styles.listItem}
                  aria-current={selectedRule ? "true" : undefined}
                  onClick={() => setSelectedId(rule.rule_family_id)}
                >
                  <b>{rule.rule_text}</b>
                  {rule.short_explanation && <span>{rule.short_explanation}</span>}
                  <small>{t("basedOnReviews", { count: prCount })}</small>
                  <MemberIcon name="chevron" size={15} />
                </button>
              );
            })}
          </nav>
          {selected && <ConventionDetail rule={selected} />}
        </div>
      )}
    </div>
  );
}
