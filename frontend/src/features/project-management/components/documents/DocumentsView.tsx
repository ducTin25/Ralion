"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import {
  confirmProjectDocumentCategory,
  deleteProjectDocument,
  getGithubSyncStatus,
  getProjectDocumentContent,
  listProjectDocuments,
} from "@/features/project-management/api";
import type { ProjectResponseDTO } from "@/features/project-management/dto/responseDTO/project.response";
import type {
  DocumentCategory,
  ProjectDocumentResponseDTO,
} from "@/features/project-management/dto/responseDTO/document.response";
import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import {
  PmCard,
  PmKpiRow,
  PmPageHead,
  PmSectionTitle,
} from "@/features/project-management/components/ui/PmCard";
import { PmButton } from "@/features/project-management/components/ui/PmButton";
import { PmSelect } from "@/features/project-management/components/ui/PmField";
import { PmPill, PmTag } from "@/features/project-management/components/ui/PmPill";
import { pmToast } from "@/features/project-management/components/ui/PmToast";
import { DocumentPreviewModal } from "@/features/project-management/components/ui/DocumentPreviewModal";
import tableStyles from "@/features/project-management/components/ui/PmTable.module.scss";

import { CategoryDocumentsDrawer } from "./CategoryDocumentsDrawer";
import { DiscoveryScheduleCard } from "./DiscoveryScheduleCard";
import { DOCUMENT_CATEGORY_META, REQUIRED_DOCUMENT_CATEGORIES } from "./documentCategoryMeta";
import { DocumentUploadModal } from "./DocumentUploadModal";
import { GithubSyncCard, isGithubRepoConfigured } from "./GithubSyncCard";
import { RepoScanWizard } from "./RepoScanWizard";
import styles from "./DocumentsView.module.scss";

const VARIANT_ICON_CLASS: Record<string, string> = {
  accent: "iconAccent",
  success: "iconSuccess",
  warning: "iconWarning",
  violet: "iconViolet",
};

type DocumentsViewProps = {
  project: ProjectResponseDTO | null;
};

/** View "Tài liệu dự án" (Phase 3, UC-04) — KPI (tổng tài liệu / đủ nhóm hay thiếu) → lưới 5
 * category chuẩn (khớp Master Template), mỗi card đếm số tài liệu thật trong nhóm (1 category có
 * thể chứa NHIỀU tài liệu — khớp pattern Master Template) hoặc báo MISSING. Bấm card mở
 * CategoryDocumentsDrawer liệt kê toàn bộ tài liệu trong nhóm. Nút "Quét repository" mở
 * RepoScanWizard (chọn folder → Coverage Report → Approve & Import); nút "Tải lên" mở
 * DocumentUploadModal cho từng nhóm. Version import xong ACTIVE ngay (TV3 đã nối chunk+activate
 * vào luồng import, xem docs/PM/Phase-4/plan-fix-onboarding-plan-quality.md mục 0). */
export function DocumentsView({ project }: DocumentsViewProps) {
  const t = useTranslations("pmUi");
  // GithubSyncCard cần phản ánh sync_status/github_repo mới ngay sau khi PM kết nối/đồng bộ —
  // `project` là prop từ parent (chỉ refetch khi đổi project ở ProjectSwitcher), nên giữ 1 bản
  // local để cập nhật lạc quan mà không phải đẩy state quản lý project lên component cha.
  const [projectState, setProjectState] = useState(project);
  const [documents, setDocuments] = useState<ProjectDocumentResponseDTO[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scanWizardOpen, setScanWizardOpen] = useState(false);
  const [uploadCategory, setUploadCategory] = useState<DocumentCategory | null>(null);
  const [drawerCategory, setDrawerCategory] = useState<DocumentCategory | null>(null);
  const [previewDoc, setPreviewDoc] = useState<ProjectDocumentResponseDTO | null>(null);
  const [reviewChoice, setReviewChoice] = useState<Record<number, DocumentCategory | "">>({});
  const [confirmingAll, setConfirmingAll] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);

  async function loadDocuments(projectId: number) {
    setLoading(true);
    setError(null);
    try {
      const data = await listProjectDocuments(projectId);
      setDocuments(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("documentsLoadError"));
      setDocuments([]);
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirmAllCategories() {
    if (!project) return;
    const resolved = needsReview.filter((doc) => Boolean(reviewChoice[doc.document_id]));
    if (resolved.length === 0) return;
    setConfirmingAll(true);
    setReviewError(null);
    try {
      await Promise.all(
        resolved.map((doc) =>
          confirmProjectDocumentCategory(
            project.project_id,
            doc.document_id,
            reviewChoice[doc.document_id] as DocumentCategory,
          ),
        ),
      );
      pmToast(t("categoriesConfirmed", { count: resolved.length }));
      setReviewChoice((prev) => {
        const next = { ...prev };
        resolved.forEach((doc) => delete next[doc.document_id]);
        return next;
      });
      const [updatedProject] = await Promise.all([
        getGithubSyncStatus(project.project_id),
        loadDocuments(project.project_id),
      ]);
      setProjectState(updatedProject);
    } catch (err) {
      setReviewError(err instanceof Error ? err.message : t("categoryConfirmError"));
    } finally {
      setConfirmingAll(false);
    }
  }

  // Reset khi đổi project — điều chỉnh state ngay trong render (cùng pattern với TemplateView).
  const [loadedProjectId, setLoadedProjectId] = useState<number | null>(null);
  if ((project?.project_id ?? null) !== loadedProjectId) {
    setLoadedProjectId(project?.project_id ?? null);
    setDocuments([]);
    setProjectState(project);
  }

  useEffect(() => {
    if (project === null) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadDocuments(project.project_id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project?.project_id]);

  // Đọc nội dung tài liệu qua backend (markdown đã chuẩn hoá cho mọi định dạng, kể cả .docx/.pdf
  // và tài liệu đến từ GitHub) thay vì để modal tự tải `storage_uri`: link Cloudinary vướng CORS,
  // còn link GitHub là trang blob HTML — cả hai đều đẩy PM ra tab ngoài thay vì đọc trong app.
  // useCallback vì `fetchContent` nằm trong dependency của effect tải nội dung bên trong modal.
  const previewDocumentId = previewDoc?.document_id ?? null;
  const loadPreviewContent = useCallback(async () => {
    if (!project || previewDocumentId === null) return "";
    const detail = await getProjectDocumentContent(project.project_id, previewDocumentId);
    return detail.content;
  }, [project, previewDocumentId]);

  if (!project) {
    return (
      <section>
        <PmPageHead icon="doc" title={t("projectDocuments")} />
        <PmCard>
          <p className={tableStyles.emptyNote}>{t("noManagedProject")}</p>
        </PmCard>
      </section>
    );
  }

  const foundCategories = new Set(documents.map((d) => d.document_category));
  const foundRequiredCount = REQUIRED_DOCUMENT_CATEGORIES.filter((c) =>
    foundCategories.has(c),
  ).length;
  const needsReview = documents.filter((d) => !d.category_confirmed);

  return (
    <section>
      <PmPageHead
        icon="doc"
        title={t("projectDocuments")}
        subtitle={t("projectDocumentsSubtitle")}
        action={
          <PmButton variant="primary" onClick={() => setScanWizardOpen(true)}>
            <PmIcon name="folder" size={14} />
            {t("scanRepository")}
          </PmButton>
        }
      />

      {!loading && (
        <PmKpiRow
          items={[
            { label: t("documents"), value: documents.length, icon: "doc", variant: "accent" },
            {
              label: t("categoriesCovered"),
              value: `${foundRequiredCount}/${REQUIRED_DOCUMENT_CATEGORIES.length}`,
              icon: "check-circle",
              variant: "success",
            },
            {
              label: t("categoryNeedsConfirming"),
              value: needsReview.length,
              icon: "alert",
              variant: needsReview.length > 0 ? "warning" : "success",
            },
          ]}
        />
      )}

      {error && <p className={styles.errorBanner}>{error}</p>}

      <GithubSyncCard
        key={project.project_id}
        project={projectState ?? project}
        onProjectUpdated={(updated) => {
          // GithubSyncCard calls this on every ~2.5s poll tick while syncing (to keep the
          // status pill live), not just when the sync finishes. Reloading documents on every
          // tick toggled `loading` the whole time, unmounting/remounting the KPI row and
          // category grid below every 2.5s for the full sync duration. Only refetch on the
          // actual SYNCING -> terminal transition, when the document list can really have
          // changed.
          const wasSyncing = (projectState ?? project).sync_status === "SYNCING";
          setProjectState(updated);
          if (wasSyncing && updated.sync_status !== "SYNCING") {
            void loadDocuments(project.project_id);
          }
        }}
      />

      {!loading && needsReview.length > 0 && (
        <>
          <PmSectionTitle hint={t("categoryReviewHint")}>
            {t("categoryNeedsConfirmingCount", { count: needsReview.length })}
          </PmSectionTitle>
          <PmCard padded={false} className={styles.reviewCard}>
            {reviewError && <p className={styles.reviewError}>{reviewError}</p>}
            {needsReview.map((doc) => (
              <div key={doc.document_id} className={styles.reviewRow}>
                <div className={styles.reviewInfo}>
                  <PmPill variant="warning">{t("needsReview")}</PmPill>
                  <span className={styles.reviewTitle}>{doc.title}</span>
                </div>
                <div className={styles.reviewActions}>
                  <PmButton
                    size="sm"
                    aria-label={t("previewDocument", { title: doc.title })}
                    onClick={() => setPreviewDoc(doc)}
                  >
                    <PmIcon name="eye" size={12} />
                    {t("preview")}
                  </PmButton>
                  <PmSelect
                    aria-label={t("pickCategoryFor", { title: doc.title })}
                    value={reviewChoice[doc.document_id] ?? ""}
                    onChange={(e) =>
                      setReviewChoice((prev) => ({
                        ...prev,
                        [doc.document_id]: e.target.value as DocumentCategory,
                      }))
                    }
                  >
                    <option value="" disabled>
                      {t("chooseCategory")}
                    </option>
                    {Object.entries(DOCUMENT_CATEGORY_META).map(([value, meta]) => (
                      <option key={value} value={value}>
                        {t(meta.labelKey)}
                      </option>
                    ))}
                  </PmSelect>
                </div>
              </div>
            ))}
            <div className={styles.reviewFooter}>
              <PmButton
                size="sm"
                variant="primary"
                disabled={confirmingAll || !needsReview.some((doc) => reviewChoice[doc.document_id])}
                onClick={() => void handleConfirmAllCategories()}
              >
                {confirmingAll ? t("saving") : t("confirmAll")}
              </PmButton>
            </div>
          </PmCard>
        </>
      )}

      {isGithubRepoConfigured((projectState ?? project).github_repo) && (
        <DiscoveryScheduleCard projectId={project.project_id} />
      )}

      <PmSectionTitle>{t("requiredDocumentCategories")}</PmSectionTitle>

      {loading ? (
        <p className={tableStyles.emptyNote}>{t("loading")}</p>
      ) : (
        <div className={styles.categoryGrid}>
          {REQUIRED_DOCUMENT_CATEGORIES.map((category) => {
            const meta = DOCUMENT_CATEGORY_META[category];
            const docsInCategory = documents.filter((d) => d.document_category === category);
            return (
              <PmCard key={category} className={styles.categoryCard}>
                <div className={styles.categoryTop}>
                  <div className={styles.categoryTitle}>
                    <span
                      className={`${styles.categoryIcon} ${styles[VARIANT_ICON_CLASS[meta.variant]]}`}
                    >
                      <PmIcon name={meta.icon} size={16} />
                    </span>
                    <b>{t(meta.labelKey)}</b>
                  </div>
                  <PmTag>{t("documentCount", { count: docsInCategory.length })}</PmTag>
                </div>

                {docsInCategory.length === 0 ? (
                  <p className={styles.missingNote}>{t("noDocumentsMissing")}</p>
                ) : (
                  <div className={styles.docInfo}>
                    <p className={styles.docTitle}>{docsInCategory[0].title}</p>
                    {docsInCategory.length > 1 && (
                      <span>{t("andMore", { count: docsInCategory.length - 1 })}</span>
                    )}
                  </div>
                )}

                <div className={styles.cardActions}>
                  <PmButton size="sm" onClick={() => setUploadCategory(category)}>
                    <PmIcon name="plus" size={12} />
                    {t("upload")}
                  </PmButton>
                  {docsInCategory.length > 0 && (
                    <PmButton size="sm" onClick={() => setDrawerCategory(category)}>
                      <PmIcon name="eye" size={12} />
                      {t("view")}
                    </PmButton>
                  )}
                </div>
              </PmCard>
            );
          })}
        </div>
      )}

      {scanWizardOpen && (
        <RepoScanWizard
          projectId={project.project_id}
          onClose={() => setScanWizardOpen(false)}
          onImported={() => loadDocuments(project.project_id)}
        />
      )}

      {uploadCategory && (
        <DocumentUploadModal
          projectId={project.project_id}
          defaultCategory={uploadCategory}
          existingDocuments={documents.filter((d) => d.document_category === uploadCategory)}
          onClose={() => setUploadCategory(null)}
          onSaved={() => loadDocuments(project.project_id)}
        />
      )}

      {drawerCategory && (
        <CategoryDocumentsDrawer
          categoryLabel={t(DOCUMENT_CATEGORY_META[drawerCategory].labelKey)}
          documents={documents.filter((d) => d.document_category === drawerCategory)}
          onClose={() => setDrawerCategory(null)}
          onPreview={(doc) => setPreviewDoc(doc)}
          onUploadNew={() => {
            setUploadCategory(drawerCategory);
            setDrawerCategory(null);
          }}
          onChangeCategory={async (doc, category) => {
            await confirmProjectDocumentCategory(project.project_id, doc.document_id, category);
            pmToast(
              t("documentMovedCategory", {
                title: doc.title,
                category: t(DOCUMENT_CATEGORY_META[category].labelKey),
              }),
            );
            await loadDocuments(project.project_id);
          }}
          onDelete={async (doc) => {
            await deleteProjectDocument(project.project_id, doc.document_id);
            pmToast(t("documentDeleted", { title: doc.title }));
            await loadDocuments(project.project_id);
          }}
        />
      )}

      {previewDoc && (
        <DocumentPreviewModal
          title={previewDoc.title}
          sourceUrl={previewDoc.latest_version?.storage_uri ?? ""}
          fetchContent={loadPreviewContent}
          onClose={() => setPreviewDoc(null)}
        />
      )}
    </section>
  );
}
