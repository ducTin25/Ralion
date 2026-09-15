"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import { renderMarkdown } from "@/features/project-management/components/ui/markdownPreview";
import { PmModal } from "@/features/project-management/components/ui/PmModal";

import styles from "../ui/DocumentPreviewModal.module.scss";

type LocalFilePreviewModalProps = {
  file: File;
  onClose: () => void;
};

function getExtension(filename: string): string {
  const dot = filename.lastIndexOf(".");
  return dot === -1 ? "" : filename.slice(dot + 1).toLowerCase();
}

/** Xem trước NGAY 1 file local (chưa upload lên đâu cả) — dùng object URL, không đụng mạng.
 * Cùng cơ chế preview với ui/DocumentPreviewModal.tsx (đã dùng cho tài liệu đã import), chỉ khác
 * nguồn dữ liệu là File trên máy PM thay vì backend.
 *
 * Ranh giới CỐ Ý: `.docx` không xem trước được ở bước này. Việc bóc text DOCX là của backend
 * (`document_conversion_service`, dùng chung với luồng HR) — kéo thêm 1 bộ parse DOCX vào trình
 * duyệt chỉ để xem trước trước khi tải lên là nhân đôi logic cho một lợi ích rất nhỏ. Sau khi
 * upload, PM đọc được đầy đủ nội dung ngay trong app qua DocumentPreviewModal. */
export function LocalFilePreviewModal({ file, onClose }: LocalFilePreviewModalProps) {
  const t = useTranslations("pmUi");
  const extension = getExtension(file.name);
  const [markdownText, setMarkdownText] = useState<string | null>(null);
  // createObjectURL tính trực tiếp lúc render (không setState trong effect) — effect chỉ lo dọn
  // dẹp (revoke) khi file đổi/unmount, tránh rò rỉ bộ nhớ.
  const objectUrl = useMemo(
    () => (extension === "pdf" ? URL.createObjectURL(file) : null),
    [file, extension],
  );

  useEffect(() => {
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [objectUrl]);

  useEffect(() => {
    if (extension !== "md" && extension !== "txt") return;
    let cancelled = false;
    file.text().then((text) => {
      if (!cancelled) setMarkdownText(text);
    });
    return () => {
      cancelled = true;
    };
  }, [file, extension]);

  return (
    <PmModal title={file.name} icon="eye" tone="primary" size="wide" onClose={onClose}>
      <div className={styles.body}>
        {(extension === "md" || extension === "txt") &&
          (markdownText === null ? (
            <p className={styles.note}>{t("readingFile")}</p>
          ) : (
            <div className={styles.markdown}>{renderMarkdown(markdownText)}</div>
          ))}

        {extension === "pdf" && objectUrl !== null && (
          <iframe src={objectUrl} title={file.name} className={styles.pdfFrame} />
        )}

        {extension !== "md" && extension !== "txt" && extension !== "pdf" && (
          <p className={styles.note}>
            {t("localPreviewUnavailable", {
              type: extension ? `.${extension}` : t("thisFileType"),
            })}
          </p>
        )}
      </div>
    </PmModal>
  );
}
