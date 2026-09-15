"use client";

import { useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { uploadProjectDocumentWithProgress } from "@/features/project-management/api";
import type {
  DocumentCategory,
  ProjectDocumentResponseDTO,
} from "@/features/project-management/dto/responseDTO/document.response";
import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import { PmButton } from "@/features/project-management/components/ui/PmButton";
import { PmErrorText, PmField, PmInput } from "@/features/project-management/components/ui/PmField";
import { PmModal } from "@/features/project-management/components/ui/PmModal";
import { pmToast } from "@/features/project-management/components/ui/PmToast";
import { notifyProjectOperationCompleted } from "@/lib/projectOperationNotifications";

import { DOCUMENT_CATEGORY_META, REQUIRED_DOCUMENT_CATEGORIES } from "./documentCategoryMeta";
import { LocalFilePreviewModal } from "./LocalFilePreviewModal";
import styles from "./DocumentUploadModal.module.scss";

type DocumentUploadModalProps = {
  projectId: number;
  defaultCategory?: DocumentCategory;
  existingDocuments?: ProjectDocumentResponseDTO[];
  onClose: () => void;
  onSaved: () => void;
};

/** Upload 1 file tài liệu đơn lẻ — dùng khi Coverage Report báo MISSING 1 category, hoặc tài liệu
 * nằm ngoài repository PM đã quét. Luôn mở từ đúng 1 card category cụ thể (xem DocumentsView) nên
 * nhóm tài liệu KHOÁ CỨNG theo card đã bấm, không cho đổi sang nhóm khác trong modal này — muốn
 * tài liệu cho nhóm khác thì đóng modal, bấm "Tải lên" ở đúng card đó. */
export function DocumentUploadModal({
  projectId,
  defaultCategory,
  existingDocuments = [],
  onClose,
  onSaved,
}: DocumentUploadModalProps) {
  const t = useTranslations("pmUi");
  const locale = useLocale();
  const copy = locale === "vi"
    ? {
        duplicate: "Đã tìm thấy tài liệu trùng tên",
        chooseTarget: "Chọn đúng tài liệu hiện có cần thay thế:",
        choosePlaceholder: "— Chọn tài liệu —",
        replace: "Tạo phiên bản mới từ tệp vừa chọn và thay thế tài liệu trên",
        confirm: "Hãy chọn tài liệu cần thay thế và xác nhận trước khi tải lên.",
        uploading: (percent: number) => `Đang tải tệp lên — ${percent}%`,
        processing: "Đã tải xong — đang chuyển đổi, tạo chunk và embedding…",
      }
    : {
        duplicate: "Documents with the same file name were found",
        chooseTarget: "Choose the existing document to replace:",
        choosePlaceholder: "— Choose a document —",
        replace: "Create a new version from this file and replace the document above",
        confirm: "Choose the document to replace and confirm before uploading.",
        uploading: (percent: number) => `Uploading file — ${percent}%`,
        processing: "Upload complete — converting, chunking and embedding…",
      };
  const category = defaultCategory ?? REQUIRED_DOCUMENT_CATEGORIES[0];
  const categoryMeta = DOCUMENT_CATEGORY_META[category];
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [title, setTitle] = useState("");
  // Tiêu đề tự điền theo tên file CHO TỚI KHI PM tự gõ. Trước đây chỉ điền khi tiêu đề còn rỗng,
  // nên đổi file (pet_project.docx -> thesis.md) vẫn để lại tên file cũ trên form.
  const [titleEdited, setTitleEdited] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadPercent, setUploadPercent] = useState(0);
  const [processing, setProcessing] = useState(false);
  const [replaceConfirmed, setReplaceConfirmed] = useState(false);
  const [replacementDocumentId, setReplacementDocumentId] = useState<number | null>(null);

  const normalizedTitle = title.trim().replaceAll("\\", "/").toLocaleLowerCase();
  const titleBasename = normalizedTitle.split("/").pop() ?? normalizedTitle;
  const matchingDocuments = file
    ? existingDocuments.filter((document) => {
        const existingTitle = document.title.replaceAll("\\", "/").toLocaleLowerCase();
        const existingBasename = existingTitle.split("/").pop() ?? existingTitle;
        return existingTitle === normalizedTitle || existingBasename === titleBasename;
      })
    : [];
  const matchingDocument = matchingDocuments.find(
    (document) => document.document_id === replacementDocumentId,
  );

  async function handleSubmit() {
    if (!file) {
      setError(t("pickDocumentFirst"));
      return;
    }
    if (!title.trim()) {
      setError(t("enterDocumentTitle"));
      return;
    }
    if (matchingDocuments.length > 0 && (!matchingDocument || !replaceConfirmed)) {
      setError(copy.confirm);
      return;
    }
    setSaving(true);
    setUploadPercent(0);
    setProcessing(false);
    setError(null);
    try {
      const replacementTitle = matchingDocument?.title ?? title.trim();
      await uploadProjectDocumentWithProgress(
        projectId,
        { category, title: replacementTitle, file },
        (percent) => {
          setUploadPercent(percent);
          if (percent === 100) setProcessing(true);
        },
      );
      pmToast(t("documentUploaded"));
      notifyProjectOperationCompleted({
        projectId,
        operation: "DOCUMENT_UPLOAD",
        status: "SUCCEEDED",
        completedAt: new Date().toISOString(),
        title: replacementTitle,
      });
      onSaved();
      onClose();
    } catch (err) {
      const errorSummary = err instanceof Error ? err.message : null;
      setError(errorSummary ?? t("uploadFailed"));
      notifyProjectOperationCompleted({
        projectId,
        operation: "DOCUMENT_UPLOAD",
        status: "FAILED",
        completedAt: new Date().toISOString(),
        title: title.trim(),
        errorSummary,
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <PmModal
        title={t("uploadDocument")}
        icon="plus"
        tone="primary"
        onClose={onClose}
        footer={
          <>
            <PmButton onClick={onClose} disabled={saving}>
              {t("cancel")}
            </PmButton>
            <PmButton
              variant="primary"
              onClick={handleSubmit}
              disabled={saving || Boolean(matchingDocuments.length > 0 && (!matchingDocument || !replaceConfirmed))}
            >
              {saving ? t("uploading") : t("upload")}
            </PmButton>
          </>
        }
      >
        <PmField label={t("documentCategory")}>
          <div className={styles.lockedCategory}>
            <span className={styles.lockedIcon}>
              <PmIcon name={categoryMeta.icon} size={14} />
            </span>
            <b>{t(categoryMeta.labelKey)}</b>
            <span className={styles.lockedHint}>
              <PmIcon name="lock" size={11} /> {t("lockedCategoryHint")}
            </span>
          </div>
        </PmField>

        <PmField label={t("documentTitle")}>
          <PmInput
            value={title}
            onChange={(e) => {
              setTitle(e.target.value);
              setTitleEdited(true);
              setReplaceConfirmed(false);
              setReplacementDocumentId(null);
            }}
            placeholder={t("documentTitlePlaceholder")}
          />
        </PmField>

        <PmField label={t("supportedFileLabel")}>
          <input
            ref={fileInputRef}
            type="file"
            accept=".md,.txt,.pdf,.docx"
            className={styles.hiddenInput}
            onChange={(e) => {
              const picked = e.target.files?.[0] ?? null;
              setFile(picked);
              setError(null);
              setReplaceConfirmed(false);
              setReplacementDocumentId(null);
              if (picked && !titleEdited) setTitle(picked.name);
              // Xoá value của input: chọn LẠI ĐÚNG file vừa chọn vẫn phải bắn `change` (trình duyệt
              // bỏ qua nếu value không đổi) — cần thiết khi PM sửa file trên ổ đĩa rồi chọn lại.
              e.target.value = "";
            }}
          />
          <div className={styles.filePickRow}>
            <PmButton onClick={() => fileInputRef.current?.click()}>
              <PmIcon name="folder" size={13} />
              {file ? t("chooseAnotherFile") : t("chooseFile")}
            </PmButton>
            {file && (
              <>
                <span className={styles.fileName}>{file.name}</span>
                <button
                  type="button"
                  className={styles.previewBtn}
                  title={t("previewContent")}
                  onClick={() => setPreviewing(true)}
                >
                  <PmIcon name="eye" size={13} />
                </button>
              </>
            )}
          </div>
        </PmField>

        {matchingDocuments.length > 0 && (
          <div className={styles.duplicateWarning}>
            <b>{copy.duplicate}</b>
            <span>{copy.chooseTarget}</span>
            <select
              value={replacementDocumentId ?? ""}
              disabled={saving}
              onChange={(event) => {
                setReplacementDocumentId(Number(event.target.value));
                setReplaceConfirmed(false);
                setError(null);
              }}
            >
              <option value="">{copy.choosePlaceholder}</option>
              {matchingDocuments.map((document) => (
                <option key={document.document_id} value={document.document_id}>
                  {document.title}
                </option>
              ))}
            </select>
            <label>
              <input
                type="checkbox"
                checked={replaceConfirmed}
                disabled={saving || !matchingDocument}
                onChange={(event) => {
                  setReplaceConfirmed(event.target.checked);
                  setError(null);
                }}
              />
              {copy.replace}
            </label>
          </div>
        )}

        {saving && (
          <div className={styles.uploadProgress} role="status" aria-live="polite">
            <span className={styles.spinner} aria-hidden="true" />
            <div>
              <b>
                {processing
                  ? copy.processing
                  : copy.uploading(uploadPercent)}
              </b>
              <progress value={uploadPercent} max={100} />
            </div>
          </div>
        )}

        {error && <PmErrorText>{error}</PmErrorText>}
      </PmModal>

      {previewing && file && (
        <LocalFilePreviewModal file={file} onClose={() => setPreviewing(false)} />
      )}
    </>
  );
}
