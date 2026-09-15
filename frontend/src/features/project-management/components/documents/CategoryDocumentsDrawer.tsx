import { useState } from "react";

import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import { useTranslations } from "next-intl";
import { PmButton } from "@/features/project-management/components/ui/PmButton";
import { PmDrawer } from "@/features/project-management/components/ui/PmDrawer";
import { PmSelect } from "@/features/project-management/components/ui/PmField";
import { PmPill } from "@/features/project-management/components/ui/PmPill";
import type {
  DocumentCategory,
  ProjectDocumentResponseDTO,
} from "@/features/project-management/dto/responseDTO/document.response";

import { DOCUMENT_CATEGORY_META } from "./documentCategoryMeta";
import styles from "./CategoryDocumentsDrawer.module.scss";

type CategoryDocumentsDrawerProps = {
  categoryLabel: string;
  documents: ProjectDocumentResponseDTO[];
  onClose: () => void;
  onPreview: (doc: ProjectDocumentResponseDTO) => void;
  onUploadNew: () => void;
  onChangeCategory: (doc: ProjectDocumentResponseDTO, category: DocumentCategory) => Promise<void>;
  onDelete: (doc: ProjectDocumentResponseDTO) => Promise<void>;
};

/** Drawer liệt kê toàn bộ document trong 1 category — 1 category giờ có thể chứa NHIỀU tài liệu
 * (khớp pattern `CategoryTaskDrawer` bên Master Template: 1 category nhiều task/mục). Mỗi document
 * hiện title + trạng thái version mới nhất, nút Xem mở DocumentPreviewModal.
 *
 * "Move to category" cho phép PM sửa lại category sau khi đã import — dùng chung endpoint HITL
 * (`confirmProjectDocumentCategory`) với luồng xác nhận tài liệu AMBIGUOUS, chỉ khác chỗ tài liệu
 * ở đây đã CLASSIFIED sẵn. Sau khi đổi, document rời khỏi danh sách này (parent lọc lại theo
 * category mới) nên không cần tự xoá row thủ công. */
export function CategoryDocumentsDrawer({
  categoryLabel,
  documents,
  onClose,
  onPreview,
  onUploadNew,
  onChangeCategory,
  onDelete,
}: CategoryDocumentsDrawerProps) {
  const t = useTranslations("pmUi");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [pendingCategory, setPendingCategory] = useState<DocumentCategory | "">("");
  const [savingId, setSavingId] = useState<number | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [deleteErrorId, setDeleteErrorId] = useState<number | null>(null);

  async function deleteDocument(doc: ProjectDocumentResponseDTO) {
    if (!window.confirm(t("deleteDocumentConfirm", { title: doc.title }))) return;
    setDeletingId(doc.document_id);
    setDeleteErrorId(null);
    setRowError(null);
    try {
      await onDelete(doc);
    } catch (err) {
      setRowError(err instanceof Error ? err.message : t("deleteDocumentError"));
      setDeleteErrorId(doc.document_id);
    } finally {
      setDeletingId(null);
    }
  }

  function startEdit(doc: ProjectDocumentResponseDTO) {
    setEditingId(doc.document_id);
    setPendingCategory(doc.document_category ?? "");
    setRowError(null);
  }

  async function saveEdit(doc: ProjectDocumentResponseDTO) {
    if (!pendingCategory || pendingCategory === doc.document_category) {
      setEditingId(null);
      return;
    }
    setSavingId(doc.document_id);
    setRowError(null);
    try {
      await onChangeCategory(doc, pendingCategory);
      setEditingId(null);
    } catch (err) {
      setRowError(err instanceof Error ? err.message : t("categoryUpdateError"));
    } finally {
      setSavingId(null);
    }
  }

  return (
    <PmDrawer
      title={categoryLabel}
      onClose={onClose}
      footer={
        <PmButton className={styles.addBtn} onClick={onUploadNew}>
          <PmIcon name="plus" size={14} />
          {t("uploadDocument")}
        </PmButton>
      }
    >
      {documents.length === 0 ? (
        <p className={styles.emptyNote}>{t("categoryHasNoDocuments")}</p>
      ) : (
        documents.map((doc) => (
          <div key={doc.document_id} className={styles.docCard}>
            <div className={styles.docCardTop}>
              <span className={styles.docTitle}>{doc.title}</span>
              {doc.latest_version && (
                <PmPill variant={doc.latest_version.status === "ACTIVE" ? "success" : "progress"}>
                  {t(`documentStatus${doc.latest_version.status}`)}
                </PmPill>
              )}
            </div>
            <div className={styles.docMetaRow}>
              <span>
                {doc.latest_version ? `v${doc.latest_version.version_no}` : t("noVersions")}
              </span>
              <div className={styles.docActions}>
                {doc.latest_version && (
                  <button
                    type="button"
                    className={styles.iconBtn}
                    onClick={() => onPreview(doc)}
                    title={t("viewContent")}
                  >
                    <PmIcon name="eye" size={13} />
                  </button>
                )}
                <button
                  type="button"
                  className={styles.iconBtn}
                  onClick={() => startEdit(doc)}
                  title={t("moveToAnotherCategory")}
                >
                  <PmIcon name="folder" size={13} />
                </button>
                <button
                  type="button"
                  className={`${styles.iconBtn} ${styles.deleteBtn}`}
                  disabled={deletingId === doc.document_id}
                  onClick={() => deleteDocument(doc)}
                  title={t("deleteDocument")}
                >
                  <PmIcon name="trash" size={13} />
                </button>
              </div>
            </div>

            {editingId === doc.document_id && (
              <div className={styles.editRow}>
                <PmSelect
                  aria-label={t("moveDocumentToCategory", { title: doc.title })}
                  value={pendingCategory}
                  onChange={(e) => setPendingCategory(e.target.value as DocumentCategory)}
                >
                  {Object.entries(DOCUMENT_CATEGORY_META).map(([value, meta]) => (
                    <option key={value} value={value}>
                      {t(meta.labelKey)}
                    </option>
                  ))}
                </PmSelect>
                <PmButton
                  size="sm"
                  variant="primary"
                  disabled={savingId === doc.document_id}
                  onClick={() => saveEdit(doc)}
                >
                  {savingId === doc.document_id ? t("saving") : t("save")}
                </PmButton>
                <PmButton
                  size="sm"
                  onClick={() => setEditingId(null)}
                  disabled={savingId === doc.document_id}
                >
                  {t("cancel")}
                </PmButton>
              </div>
            )}
            {editingId === doc.document_id && rowError && (
              <p className={styles.rowError}>{rowError}</p>
            )}
            {deleteErrorId === doc.document_id && rowError && (
              <p className={styles.rowError}>{rowError}</p>
            )}
          </div>
        ))
      )}
    </PmDrawer>
  );
}
