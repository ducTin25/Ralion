"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import { PmButton } from "@/features/project-management/components/ui/PmButton";
import {
  renderMarkdown,
  slugifyHeading,
} from "@/features/project-management/components/ui/markdownPreview";
import { PmModal } from "@/features/project-management/components/ui/PmModal";

import styles from "./DocumentPreviewModal.module.scss";

type DocumentPreviewModalProps = {
  title: string;
  sourceUrl: string;
  /** Mục cần nhảy tới khi mở — lấy từ `section_path` của chunk đã trích dẫn. Chỉ dùng khi
   * `highlightSnippet` không tìm thấy. Bỏ trống thì mở từ đầu file như trước. */
  highlightSection?: string | null;
  /** Đoạn văn bản THUẦN của chunk đã trích dẫn (`content_snippet`). Đây là cách định vị CHÍNH:
   * chính xác tới từng đoạn kể cả khi 1 tiêu đề bị tách nhiều đoạn hoặc 2 mục trùng tên. */
  highlightSnippet?: string | null;
  /** Nguồn nội dung THAY THẾ việc tự tải `sourceUrl`. Dùng khi backend đã chuẩn hoá tài liệu về
   * markdown (mọi định dạng nguồn, kể cả `.docx`/`.pdf`): modal chỉ render, không cần biết định
   * dạng gốc và không phải fetch chéo domain. Không truyền thì giữ nguyên hành vi cũ — tự tải
   * `.md`/`.txt` từ `sourceUrl`, nhúng `.pdf`, còn lại thì mở tab ngoài. */
  fetchContent?: () => Promise<string>;
  onClose: () => void;
};

function getExtension(url: string): string {
  const path = url.split("?")[0];
  const dot = path.lastIndexOf(".");
  return dot === -1 ? "" : path.slice(dot + 1).toLowerCase();
}

// Mirrors the backend's `is_conventions_route` (convention_ingestion.py). An approved F6
// convention has no artifact file — `source_url` is this internal page route instead of a real
// document link, and there is no Next.js page mounted at it (Conventions lives as a tab inside
// ChatScreen, not a URL). Treat it like a suppressed link: render the already-fetched chunk
// content inline rather than trying to fetch/open a route that 404s.
const CONVENTIONS_ROUTE_PREFIX = "/conventions/";

function isConventionsRoute(url: string): boolean {
  return url.startsWith(CONVENTIONS_ROUTE_PREFIX);
}

const TEXT_EXTENSIONS = new Set(["md", "txt"]);
const HIGHLIGHT_MS = 2400;

/** Xem trước tài liệu ngay trong app — không bắt tải file về mới xem được:
 * - Có `fetchContent` (tài liệu dự án, xem DocumentsView) — backend đã chuẩn hoá MỌI định dạng
 *   nguồn về markdown, modal chỉ render. Đây là đường đọc chính, không phụ thuộc đuôi file.
 * - `.md`/`.txt` — tải nội dung text rồi render markdown đơn giản (heading/list/bold/code/link);
 *   `.txt` không có cú pháp markdown thì vẫn hiện đúng như văn bản thường (renderMarkdown coi
 *   phần không khớp cú pháp là đoạn văn bình thường).
 * - `.pdf` — nhúng thẳng qua iframe (trình duyệt tự render PDF).
 * - Định dạng khác (doc/docx...) hoặc tải lỗi — không có cách preview an toàn trong trình duyệt,
 *   chỉ còn cách mở tab mới/tải về.
 *
 * Khi mở từ 1 trích dẫn, `highlightSection` cho biết đoạn nào đã được dùng để viết nội dung task —
 * modal tự cuộn tới đúng heading đó và tô sáng vài giây, thay vì bắt người đọc dò cả file. */
/** Chuẩn hoá khoảng trắng trước khi so khớp: renderMarkdown nối các dòng của 1 đoạn văn bằng dấu
 * cách, nên xuống dòng trong file gốc không còn tồn tại trong DOM. */
function normalize(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

/** Tìm phần tử chứa đúng đoạn văn bản đã trích dẫn. Duyệt text node (không phải innerHTML) để so
 * đúng thứ người đọc nhìn thấy, không dính thẻ/thuộc tính. */
function findElementBySnippet(root: HTMLElement, snippet: string): HTMLElement | null {
  const needle = normalize(snippet);
  if (needle.length < 12) return null; // quá ngắn thì dễ khớp nhầm chỗ khác, thà không cuộn

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node = walker.nextNode();
  while (node) {
    if (node.textContent && normalize(node.textContent).includes(needle)) {
      return node.parentElement;
    }
    node = walker.nextNode();
  }
  return null;
}

export function DocumentPreviewModal({
  title,
  sourceUrl,
  highlightSection,
  highlightSnippet,
  fetchContent,
  onClose,
}: DocumentPreviewModalProps) {
  const t = useTranslations("pmUi");
  const commonT = useTranslations("common");
  const extension = getExtension(sourceUrl);
  // Có loader thì nội dung luôn là markdown do backend trả về, bất kể đuôi file của bản gốc.
  const isTextFormat = fetchContent !== undefined || TEXT_EXTENSIONS.has(extension);
  // Backend cố tình bỏ trống link với tài liệu HR upload khi người xem là Member: file gốc là bản
  // CHƯA redact. Không có link thì chỉ hiển thị đoạn đã trích (đã qua redaction), không fetch.
  const linkSuppressed = !sourceUrl && fetchContent === undefined;
  const isConventionRoute = isConventionsRoute(sourceUrl);
  const noArtifactToOpen = linkSuppressed || isConventionRoute;
  const [markdownText, setMarkdownText] = useState<string | null>(null);
  const [loading, setLoading] = useState(isTextFormat && !noArtifactToOpen);
  const [error, setError] = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isTextFormat || noArtifactToOpen) return;
    let cancelled = false;
    const load = fetchContent
      ? fetchContent()
      : fetch(sourceUrl).then((res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return res.text();
        });
    load
      .then((text) => {
        if (!cancelled) setMarkdownText(text);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isTextFormat, noArtifactToOpen, sourceUrl, fetchContent]);

  useEffect(() => {
    if (markdownText === null || !bodyRef.current) return;
    const root = bodyRef.current;

    // Tầng 1 (chính) — dò theo NỘI DUNG đoạn đã trích dẫn. Chính xác tới từng đoạn, kể cả khi một
    // tiêu đề bị tách thành nhiều đoạn hoặc file có 2 mục trùng tên.
    let target = highlightSnippet ? findElementBySnippet(root, highlightSnippet) : null;

    // Tầng 2 (dự phòng) — nội dung file đã trôi so với lúc tách đoạn thì lùi về nhảy theo tiêu đề.
    // `section_path` có thể nhiều cấp ("Setup > Yêu cầu hệ thống"), mục cần tới là cấp cuối cùng,
    // slug hoá bằng đúng hàm mà renderMarkdown dùng để gắn id nên hai đầu luôn khớp nhau.
    if (!target && highlightSection) {
      const leaf = highlightSection.split(/[>›]/).pop()?.trim() ?? "";
      if (leaf) {
        target = root.querySelector<HTMLElement>(`#${CSS.escape(slugifyHeading(leaf))}`);
      }
    }

    if (!target) return; // không định vị được thì mở từ đầu file, không nhảy lung tung
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    target.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
    target.classList.add(styles.highlighted);
    const timer = window.setTimeout(
      () => target.classList.remove(styles.highlighted),
      HIGHLIGHT_MS,
    );
    return () => window.clearTimeout(timer);
  }, [markdownText, highlightSection, highlightSnippet]);

  return (
    <PmModal
      title={title}
      icon="doc"
      tone="primary"
      size="reader"
      onClose={onClose}
      footer={
        <PmButton variant="primary" onClick={onClose}>
          {commonT("close")}
        </PmButton>
      }
    >
      <div className={styles.body} ref={bodyRef}>
        {noArtifactToOpen ? (
          <div className={styles.fallback}>
            <p className={styles.note}>
              {isConventionRoute
                ? t("previewConventionBody")
                : highlightSnippet
                  ? t("previewExcerptOnly")
                  : t("previewSourceUnavailable")}
            </p>
            {highlightSnippet && (
              <div className={styles.markdown}>{renderMarkdown(highlightSnippet)}</div>
            )}
          </div>
        ) : (
          <>
            {isTextFormat &&
              (loading ? (
                <p className={styles.note}>{t("loadingDocument")}</p>
              ) : error || markdownText === null ? (
                <div className={styles.fallback}>
                  <p className={styles.note}>{t("previewLoadError")}</p>
                  {sourceUrl && (
                    <PmButton
                      onClick={() => window.open(sourceUrl, "_blank", "noopener,noreferrer")}
                    >
                      {t("openNewTab")}
                    </PmButton>
                  )}
                </div>
              ) : (
                <div className={styles.markdown}>{renderMarkdown(markdownText)}</div>
              ))}

            {extension === "pdf" && (
              <iframe src={sourceUrl} title={title} className={styles.pdfFrame} />
            )}

            {!isTextFormat && extension !== "pdf" && (
              <div className={styles.fallback}>
                <p className={styles.note}>
                  {t("fileCannotPreview", {
                    type: extension ? `".${extension}"` : t("thisFileType"),
                  })}
                </p>
                <PmButton onClick={() => window.open(sourceUrl, "_blank", "noopener,noreferrer")}>
                  {t("openNewTab")}
                </PmButton>
              </div>
            )}
          </>
        )}
      </div>
    </PmModal>
  );
}
