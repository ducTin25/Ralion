import { parseServerUtc } from "@/lib/datetime";

import styles from "./EvidencePermalinkCard.module.scss";

function formatEvidenceDate(value: string, locale: string) {
  return new Intl.DateTimeFormat(locale, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(parseServerUtc(value));
}

type EvidencePermalinkCardProps = {
  evidence: {
    comment_snippet_snapshot: string;
    code_snippet_snapshot?: string | null;
    code_before_snapshot?: string | null;
    code_after_snapshot?: string | null;
    original_author: string;
    evidence_created_at: string;
    permalink: string;
    cluster_edge_cosine_similarity?: number | null;
  };
  /**
   * PM (UI_SPEC B.2) thấy cosine của cạnh nối evidence này vào family; Member (B.3) không.
   * Cùng một component, khác prop — không tách thành hai cơ chế preview.
   */
  showMatchMetadata?: boolean;
  locale?: string;
  /** Nhãn cho link permalink, khác nhau giữa hai ngữ cảnh ngôn ngữ. */
  openLabel?: string;
  /** Nhãn đã bản địa hóa cho metadata độ khớp. */
  matchLabel?: string;
  prNumber?: number;
};

/**
 * Một evidence snapshot của F6: đoạn comment đã chụp lại lúc ingest + permalink tới PR gốc.
 *
 * Snippet là snapshot bất biến do backend trả về, KHÔNG fetch lại GitHub từ client — provenance
 * phải giữ nguyên nội dung tại thời điểm mining kể cả khi comment gốc bị sửa hoặc xoá.
 */
export function EvidencePermalinkCard({
  evidence,
  showMatchMetadata = false,
  locale = "en-GB",
  openLabel = "Open the original PR",
  matchLabel,
  prNumber,
}: EvidencePermalinkCardProps) {
  const cosine = evidence.cluster_edge_cosine_similarity;
  const hasBeforeAfter =
    evidence.code_before_snapshot != null && evidence.code_after_snapshot != null;
  const codeSnippet =
    evidence.code_snippet_snapshot ?? evidence.code_before_snapshot ?? evidence.code_after_snapshot;

  return (
    <figure className={styles.card}>
      <blockquote className={styles.snippet}>{evidence.comment_snippet_snapshot}</blockquote>
      {hasBeforeAfter ? (
        <div className={styles.codePair}>
          <section>
            <b>Before</b>
            <pre aria-label="Code before change">
              <code>{evidence.code_before_snapshot}</code>
            </pre>
          </section>
          <section>
            <b>After</b>
            <pre aria-label="Code after change">
              <code>{evidence.code_after_snapshot}</code>
            </pre>
          </section>
        </div>
      ) : (
        codeSnippet && (
          <pre className={styles.codeSnippet} aria-label="Code snippet">
            <code>{codeSnippet}</code>
          </pre>
        )
      )}
      <figcaption className={styles.meta}>
        <span className={styles.author}>@{evidence.original_author}</span>
        {prNumber !== undefined && (
          <>
            <span className={styles.dot} aria-hidden="true">
              ·
            </span>
            <span>PR #{prNumber}</span>
          </>
        )}
        <span className={styles.dot} aria-hidden="true">
          ·
        </span>
        <time dateTime={evidence.evidence_created_at}>
          {formatEvidenceDate(evidence.evidence_created_at, locale)}
        </time>
        {showMatchMetadata && cosine != null && (
          <>
            <span className={styles.dot} aria-hidden="true">
              ·
            </span>
            <span className={styles.cosine}>
              {matchLabel ?? `matched at cosine=${cosine.toFixed(2)}`}
            </span>
          </>
        )}
        {evidence.permalink && (
          <a
            className={styles.permalink}
            href={evidence.permalink}
            target="_blank"
            rel="noopener noreferrer"
          >
            {openLabel}
            <span aria-hidden="true">↗</span>
          </a>
        )}
      </figcaption>
    </figure>
  );
}
