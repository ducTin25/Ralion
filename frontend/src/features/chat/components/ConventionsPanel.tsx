"use client";

import { EvidencePermalinkCard } from "@/features/conventions/components/EvidencePermalinkCard";
import { CONVENTIONS_PAGE_SIZE, useConventions } from "@/features/conventions/hooks/useConventions";
import { MemberIcon } from "@/features/member-onboarding/components/MemberIcon";
import { useLocale, useTranslations } from "next-intl";

import styles from "./ConventionsPanel.module.scss";

/**
 * Member Conventions tab (UI_SPEC B.3).
 *
 * Cho phép Member chủ động duyệt qua tập convention đã được PM xác nhận, thay vì chỉ gặp chúng
 * khi retrieval tình cờ trả về. Read-only, và cố ý KHÔNG hiển thị provenance nội bộ
 * (`distinct_reviewer_count`, `family_match_confidence`) — đó là công cụ đánh giá của PM.
 */
export function ConventionsPanel({ active }: { active: boolean }) {
  const t = useTranslations("conventions");
  const locale = useLocale();
  const { items, meta, page, setPage, loading, error, reload } = useConventions(
    active,
    t("loadError"),
  );
  const lastPage = Math.max(1, Math.ceil(meta.total / CONVENTIONS_PAGE_SIZE));

  return (
    <section className={styles.panel} aria-label={t("confirmedTitle")}>
      <div className={styles.scroll}>
        <div className={styles.column}>
          <header className={styles.intro}>
            <h2>{t("confirmedTitle")}</h2>
            <p>{t("confirmedIntro")}</p>
          </header>

          {/* Governance note cố định, giống Rule Review của PM. */}
          <p className={styles.governance}>
            <MemberIcon name="shield" size={14} />
            <span>{t("governance")}</span>
          </p>

          {error ? (
            <div className={styles.stateCard} role="alert">
              <p>{error}</p>
              <button type="button" onClick={() => void reload()}>
                {t("retry")}
              </button>
            </div>
          ) : loading ? (
            <p className={styles.stateNote}>{t("loading")}</p>
          ) : items.length === 0 ? (
            <div className={styles.stateCard}>
              <p>{t("emptyConfirmed")}</p>
              <span>{t("emptyConfirmedBody")}</span>
            </div>
          ) : (
            <ul className={styles.ruleList}>
              {items.map((rule) => (
                <li key={rule.rule_family_id} className={styles.rule}>
                  <p className={styles.ruleText}>{rule.rule_text}</p>
                  <div className={styles.evidence}>
                    {rule.evidence.map((evidence, index) => (
                      <EvidencePermalinkCard
                        key={`${rule.rule_family_id}-${index}`}
                        evidence={evidence}
                        locale={locale === "vi" ? "vi-VN" : "en-GB"}
                        openLabel={t("openPullRequest")}
                      />
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          )}

          {meta.total > CONVENTIONS_PAGE_SIZE && (
            <nav className={styles.pager} aria-label={t("pages")}>
              <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                {t("previous")}
              </button>
              <span>
                {t("pageOf", { page, total: lastPage })}
              </span>
              <button type="button" disabled={page >= lastPage} onClick={() => setPage(page + 1)}>
                {t("next")}
              </button>
            </nav>
          )}
        </div>
      </div>
    </section>
  );
}
