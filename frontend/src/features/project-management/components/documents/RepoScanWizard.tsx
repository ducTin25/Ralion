"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { flushSync } from "react-dom";

import {
  getScanImportStatus,
  importScanSelection,
  scanRepository,
} from "@/features/project-management/api";
import type { IngestionJobResponseDTO } from "@/features/project-management/dto/responseDTO/discoverySchedule.response";
import type { DocumentCategory } from "@/features/project-management/dto/responseDTO/document.response";
import type {
  CoverageReportResponseDTO,
  ScanCandidateResponseDTO,
} from "@/features/project-management/dto/responseDTO/repoScan.response";
import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import { PmButton } from "@/features/project-management/components/ui/PmButton";
import { PmErrorText } from "@/features/project-management/components/ui/PmField";
import { PmModal } from "@/features/project-management/components/ui/PmModal";
import { PmPill } from "@/features/project-management/components/ui/PmPill";
import { pmToast } from "@/features/project-management/components/ui/PmToast";
import { requestEmbeddingWarmup } from "@/lib/embeddingWarmup";
import { notifyProjectOperationCompleted } from "@/lib/projectOperationNotifications";

import { filterCandidateFilesInBatches, getFileRelativePath } from "./clientFileFilter";
import { DOCUMENT_CATEGORY_META, REQUIRED_DOCUMENT_CATEGORIES } from "./documentCategoryMeta";
import { LocalFilePreviewModal } from "./LocalFilePreviewModal";
import styles from "./RepoScanWizard.module.scss";

type RepoScanWizardProps = {
  projectId: number;
  onClose: () => void;
  onImported: () => void;
};

type WizardStep = "select" | "scanning" | "review";

/** Mỗi category có thể chọn NHIỀU candidate (khớp backend: 1 category chứa nhiều document) —
 * danh sách candidate_id đã tick cho từng category, rỗng/không có key = chưa chọn gì. */
type SelectedByCategory = Partial<Record<DocumentCategory, string[]>>;

const STATUS_LABEL_KEYS: Record<ScanCandidateResponseDTO["status"], string> = {
  FOUND: "scanDetected",
  UNCLASSIFIED: "scanUncategorised",
  DUPLICATE_OR_STALE: "scanDuplicate",
};

const STATUS_TONE: Record<ScanCandidateResponseDTO["status"], "success" | "warning" | "critical"> =
  {
    FOUND: "success",
    UNCLASSIFIED: "warning",
    DUPLICATE_OR_STALE: "critical",
  };

function pickDefaultCandidateIds(candidates: ScanCandidateResponseDTO[]): string[] {
  return candidates.filter((c) => c.status === "FOUND").map((c) => c.candidate_id);
}

/** Wizard "Quét repository" (UC-04) — PM chọn thẳng folder dự án (không cần nén ZIP), lọc file
 * ứng viên NGAY Ở CLIENT trước khi upload (xem clientFileFilter.ts) nên chọn folder to vẫn nhẹ.
 * 3 bước: chọn folder → đang quét → Coverage Report → Approve & Import.
 *
 * Coverage Report chia đúng theo 5 card category (không phải danh sách phẳng) — mỗi category có
 * thể tick NHIỀU candidate (checkbox), khớp luật backend "1 category chứa nhiều document/project".
 * File không thuộc rõ category nào (UNCLASSIFIED) nằm ở mục riêng, PM gán thủ công vào 1 trong 5
 * nhóm nếu muốn dùng (có thể gán nhiều file khác nhau vào cùng 1 nhóm).
 *
 * Lưu ý: khi bấm "Chọn thư mục", trình duyệt (Chrome/Edge) sẽ tự hiện 1 hộp thoại xác nhận riêng
 * ("Upload N files to this site?") — đây là hộp thoại BẢO MẬT CỦA TRÌNH DUYỆT khi cấp quyền đọc cả
 * thư mục cho web app, không phải giao diện của hệ thống nên không thể thay bằng modal tự thiết kế
 * được (trình duyệt chặn không cho web app can thiệp vào hộp thoại này). */
export function RepoScanWizard({ projectId, onClose, onImported }: RepoScanWizardProps) {
  const t = useTranslations("pmUi");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState<WizardStep>("select");
  const [totalPickedCount, setTotalPickedCount] = useState(0);
  const [candidateFiles, setCandidateFiles] = useState<File[]>([]);
  const [report, setReport] = useState<CoverageReportResponseDTO | null>(null);
  const [selectedByCategory, setSelectedByCategory] = useState<SelectedByCategory>({});
  const [unclassifiedTarget, setUnclassifiedTarget] = useState<Record<string, DocumentCategory>>(
    {},
  );
  const [previewFile, setPreviewFile] = useState<File | null>(null);
  const [preparingFiles, setPreparingFiles] = useState(false);
  const [filtering, setFiltering] = useState(false);
  const [filteredCount, setFilteredCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [importJob, setImportJob] = useState<IngestionJobResponseDTO | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void requestEmbeddingWarmup(controller.signal).catch(() => undefined);
    return () => controller.abort();
  }, []);

  const filesByPath = new Map(candidateFiles.map((file) => [getFileRelativePath(file), file]));

  async function handleFolderPicked(fileList: FileList | null) {
    setPreparingFiles(false);
    if (!fileList || fileList.length === 0) return;
    // `onChange` chỉ chạy sau khi người dùng xác nhận Upload ở hộp thoại bảo mật của trình duyệt.
    // Commit ngay trạng thái này để spinner hiện đúng lúc app bắt đầu lọc, không hiện khi picker còn mở.
    flushSync(() => {
      setTotalPickedCount(fileList.length);
      setFilteredCount(0);
      setFiltering(true);
      setError(null);
    });
    try {
      const filtered = await filterCandidateFilesInBatches(fileList, setFilteredCount);
      setCandidateFiles(filtered);
    } finally {
      setFiltering(false);
    }
  }

  function handleChooseFolder() {
    setError(null);
    // The browser does not expose the click on its black security confirmation dialog.
    // Focus returning is the earliest signal available while Edge is still building a huge
    // FileList. Show feedback then; `onChange` replaces it with real filtering progress.
    window.addEventListener(
      "focus",
      () => {
        setPreparingFiles(true);
        // There is no native cancel event. Avoid leaving the indicator stuck if selection
        // was cancelled; a successful onChange clears this state itself.
        window.setTimeout(() => setPreparingFiles(false), 10_000);
      },
      { once: true },
    );
    fileInputRef.current?.click();
  }

  async function handleScan() {
    if (candidateFiles.length === 0) {
      setError(t("noSupportedFiles"));
      return;
    }
    setStep("scanning");
    setError(null);
    try {
      const result = await scanRepository(projectId, candidateFiles);
      setReport(result);
      const initial: SelectedByCategory = {};
      for (const category of REQUIRED_DOCUMENT_CATEGORIES) {
        const candidatesInGroup = result.candidates.filter(
          (c) => c.suggested_category === category,
        );
        const defaultIds = pickDefaultCandidateIds(candidatesInGroup);
        if (defaultIds.length > 0) initial[category] = defaultIds;
      }
      setSelectedByCategory(initial);
      setUnclassifiedTarget({});
      setStep("review");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("scanFailed"));
      setStep("select");
    }
  }

  function toggleSelection(category: DocumentCategory, candidateId: string) {
    setSelectedByCategory((prev) => {
      const current = prev[category] ?? [];
      const next = current.includes(candidateId)
        ? current.filter((id) => id !== candidateId)
        : [...current, candidateId];
      return { ...prev, [category]: next };
    });
  }

  /** PM đổi ý về category AI gợi ý cho 1 candidate — chuyển candidate_id từ mảng của category cũ
   * sang mảng của category mới, giữ nguyên trạng thái "đã tick" (candidate luôn có mặt ở đúng 1
   * category tại một thời điểm). Dùng chung 1 shape state với `selectedFromUnclassified` nên
   * candidate sẽ tự hiện ở group mới trong lần render kế tiếp, không cần state riêng. */
  function moveSelection(
    fromCategory: DocumentCategory,
    toCategory: DocumentCategory,
    candidateId: string,
  ) {
    if (fromCategory === toCategory) return;
    setSelectedByCategory((prev) => {
      const from = (prev[fromCategory] ?? []).filter((id) => id !== candidateId);
      const to = (prev[toCategory] ?? []).includes(candidateId)
        ? (prev[toCategory] ?? [])
        : [...(prev[toCategory] ?? []), candidateId];
      return { ...prev, [fromCategory]: from, [toCategory]: to };
    });
  }

  async function handleImport() {
    if (!report) return;
    const payload = (Object.entries(selectedByCategory) as [DocumentCategory, string[]][]).flatMap(
      ([category, ids]) =>
        ids.map((candidateId) => ({ candidate_id: candidateId, include: true, category })),
    );
    if (payload.length === 0) {
      setError(t("noFilesSelected"));
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const importResult = await importScanSelection(projectId, report.scan_session_id, payload);
      setImportJob(importResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("importFailed"));
    }
  }

  useEffect(() => {
    if (!importJob || !["PENDING", "RUNNING"].includes(importJob.status)) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const updated = await getScanImportStatus(projectId, importJob.ingestion_job_id);
        if (cancelled) return;
        setImportJob(updated);
        if (updated.status === "SUCCEEDED") {
          pmToast(t("documentsImported", { count: updated.processed_evidence_count }));
          notifyProjectOperationCompleted({
            projectId,
            operation: "REPOSITORY_IMPORT",
            status: "SUCCEEDED",
            completedAt: updated.finished_at ?? new Date().toISOString(),
            documentsImported: updated.processed_evidence_count,
          });
          onImported();
          onClose();
        } else if (updated.status === "FAILED") {
          const errorSummary = updated.error_summary ?? null;
          setError(errorSummary ?? t("importFailed"));
          notifyProjectOperationCompleted({
            projectId,
            operation: "REPOSITORY_IMPORT",
            status: "FAILED",
            completedAt: updated.finished_at ?? new Date().toISOString(),
            errorSummary,
          });
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : t("importFailed"));
          setLoading(false);
        }
      }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 1_500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [importJob, onClose, onImported, projectId, t]);

  if (!report) {
    return (
      <PmModal
        title={t("scanRepository")}
        icon="folder"
        tone="primary"
        size="wide"
        onClose={onClose}
        footer={
          <>
            <PmButton onClick={onClose}>{t("cancel")}</PmButton>
            {step === "select" && (
              <PmButton
                variant="primary"
                onClick={handleScan}
                disabled={filtering || candidateFiles.length === 0}
              >
                {t("startScan")}
              </PmButton>
            )}
          </>
        }
      >
        {step === "select" && (
          <div className={styles.pickArea}>
            <p className={styles.pickHint}>
              Pick the repository root — no archive needed. Only document files
              (.md/.txt/.pdf/.docx) are filtered in the browser before anything is uploaded; code,{" "}
              <code>.git</code>,<code>node_modules</code> and sensitive files are skipped, so large
              folders stay cheap.
            </p>

            <input
              ref={fileInputRef}
              type="file"
              multiple
              className={styles.hiddenInput}
              onChange={(e) => handleFolderPicked(e.target.files)}
              {...({ webkitdirectory: "true", directory: "true" } as Record<string, string>)}
            />
            <PmButton onClick={handleChooseFolder} disabled={preparingFiles || filtering}>
              <PmIcon name="folder" size={14} />
              {t("chooseProjectFolder")}
            </PmButton>
            <p className={styles.browserNote}>
              Your browser will ask permission to read the folder — that dialog comes from the
              browser, not from Ralion.
            </p>

            {filtering && (
              <div className={styles.pickSummary}>
                <span>Filtering {totalPickedCount} files in the folder…</span>
              </div>
            )}
            {!preparingFiles && !filtering && totalPickedCount > 0 && (
              <div className={styles.pickSummary}>
                <span>
                  Scanned {totalPickedCount} files — <b>{candidateFiles.length}</b> are supported
                  documents.
                </span>
                {candidateFiles.length === 0 && <span>{t("noSupportedFilesInFolder")}</span>}
              </div>
            )}
            {error && <PmErrorText>{error}</PmErrorText>}
          </div>
        )}

        {step === "scanning" && (
          <div className={styles.loadingState}>
            <span className={styles.spinner} aria-hidden="true" />
            <p>{t("scanningFiles", { count: candidateFiles.length })}</p>
          </div>
        )}
      </PmModal>
    );
  }

  const unclassifiedCandidates = report.candidates.filter(
    (c) =>
      c.suggested_category === null || !REQUIRED_DOCUMENT_CATEGORIES.includes(c.suggested_category),
  );
  const selectedCount = Object.values(selectedByCategory).reduce(
    (sum, ids) => sum + (ids?.length ?? 0),
    0,
  );

  function candidateById(id: string): ScanCandidateResponseDTO | undefined {
    return report?.candidates.find((c) => c.candidate_id === id);
  }

  function addSelection(category: DocumentCategory, candidateId: string) {
    setSelectedByCategory((prev) => {
      const current = prev[category] ?? [];
      if (current.includes(candidateId)) return prev;
      return { ...prev, [category]: [...current, candidateId] };
    });
  }

  function renderCandidateRow(category: DocumentCategory, candidate: ScanCandidateResponseDTO) {
    const localFile = filesByPath.get(candidate.relative_path);
    return (
      <div key={candidate.candidate_id} className={styles.candidateRow}>
        <label className={styles.candidateRowMain}>
          <input
            type="checkbox"
            checked={(selectedByCategory[category] ?? []).includes(candidate.candidate_id)}
            onChange={() => toggleSelection(category, candidate.candidate_id)}
          />
          <div className={styles.candidatePath}>
            <b>{candidate.relative_path}</b>
            <span>
              {Math.round(candidate.size_bytes / 1024)} KB · {candidate.reason}
            </span>
          </div>
          <PmPill variant={STATUS_TONE[candidate.status]}>
            {t(STATUS_LABEL_KEYS[candidate.status])}
          </PmPill>
        </label>
        <select
          className={styles.categorySelectSm}
          value={category}
          title="AI suggested category — change it if it's wrong"
          onChange={(e) =>
            moveSelection(category, e.target.value as DocumentCategory, candidate.candidate_id)
          }
        >
          {REQUIRED_DOCUMENT_CATEGORIES.map((value) => (
            <option key={value} value={value}>
              {t(DOCUMENT_CATEGORY_META[value].labelKey)}
            </option>
          ))}
        </select>
        {localFile && (
          <button
            type="button"
            className={styles.previewBtn}
            title={t("previewContent")}
            onClick={() => setPreviewFile(localFile)}
          >
            <PmIcon name="eye" size={13} />
          </button>
        )}
      </div>
    );
  }

  return (
    <>
      <PmModal
        title="Repository scan — coverage report"
        icon="folder"
        tone="primary"
        size="wide"
        onClose={onClose}
        footer={
          <>
            <PmButton onClick={onClose} disabled={loading}>
              {t("cancel")}
            </PmButton>
            <PmButton variant="primary" onClick={handleImport} disabled={loading}>
              {loading ? t("importing") : t("approveImport", { count: selectedCount })}
            </PmButton>
          </>
        }
      >
        <p className={styles.reviewHint}>
          Each category can take <b>several files</b> — tick the ones to import, and preview any
          file with the eye icon before you decide.
        </p>

        <div className={styles.categoryGroups}>
          {REQUIRED_DOCUMENT_CATEGORIES.map((category) => {
            const meta = DOCUMENT_CATEGORY_META[category];
            const ownCandidates = report.candidates.filter(
              (c) => c.suggested_category === category,
            );
            const selectedIds = selectedByCategory[category] ?? [];
            const selectedFromUnclassified = selectedIds
              .filter((id) => !ownCandidates.some((c) => c.candidate_id === id))
              .map((id) => candidateById(id))
              .filter((c): c is ScanCandidateResponseDTO => c !== undefined);

            return (
              <div key={category} className={styles.categoryGroup}>
                <div className={styles.categoryGroupHead}>
                  <span className={styles.categoryGroupIcon}>
                    <PmIcon name={meta.icon} size={13} />
                  </span>
                  <b>{t(meta.labelKey)}</b>
                  <PmPill variant={selectedIds.length > 0 ? "success" : "critical"}>
                    {selectedIds.length > 0
                      ? t("toImport", { count: selectedIds.length })
                      : t("missing")}
                  </PmPill>
                </div>

                {ownCandidates.length === 0 && selectedFromUnclassified.length === 0 && (
                  <p className={styles.emptyNote}>
                    No file was found for this category — assign one from &quot;Uncategorised&quot;
                    below if there is a match.
                  </p>
                )}

                {ownCandidates.map((candidate) => renderCandidateRow(category, candidate))}

                {selectedFromUnclassified.map((candidate) => (
                  <label key={candidate.candidate_id} className={styles.candidateRow}>
                    <input
                      type="checkbox"
                      checked
                      onChange={() => toggleSelection(category, candidate.candidate_id)}
                    />
                    <div className={styles.candidatePath}>
                      <b>{candidate.relative_path}</b>
                      <span>
                        {candidate.suggested_category === null
                          ? t("assignedFromUncategorised")
                          : t("movedFromCategory", {
                              category: t(
                                DOCUMENT_CATEGORY_META[candidate.suggested_category].labelKey,
                              ),
                            })}
                      </span>
                    </div>
                  </label>
                ))}
              </div>
            );
          })}
        </div>

        {unclassifiedCandidates.length > 0 && (
          <div className={styles.unclassifiedBlock}>
            <p className={styles.unclassifiedTitle}>
              {t("uncategorisedCount", { count: unclassifiedCandidates.length })}
            </p>
            {unclassifiedCandidates.map((candidate) => {
              const localFile = filesByPath.get(candidate.relative_path);
              const target =
                unclassifiedTarget[candidate.candidate_id] ?? REQUIRED_DOCUMENT_CATEGORIES[0];
              return (
                <div key={candidate.candidate_id} className={styles.unclassifiedRow}>
                  <div className={styles.candidatePath}>
                    <b>{candidate.relative_path}</b>
                    <span>
                      {Math.round(candidate.size_bytes / 1024)} KB · {candidate.reason}
                    </span>
                  </div>
                  {localFile && (
                    <button
                      type="button"
                      className={styles.previewBtn}
                      title={t("previewContent")}
                      onClick={() => setPreviewFile(localFile)}
                    >
                      <PmIcon name="eye" size={13} />
                    </button>
                  )}
                  <select
                    className={styles.categorySelectSm}
                    value={target}
                    onChange={(e) =>
                      setUnclassifiedTarget((prev) => ({
                        ...prev,
                        [candidate.candidate_id]: e.target.value as DocumentCategory,
                      }))
                    }
                  >
                    {REQUIRED_DOCUMENT_CATEGORIES.map((value) => (
                      <option key={value} value={value}>
                        {t(DOCUMENT_CATEGORY_META[value].labelKey)}
                      </option>
                    ))}
                  </select>
                  <PmButton size="sm" onClick={() => addSelection(target, candidate.candidate_id)}>
                    {t("useForCategory")}
                  </PmButton>
                </div>
              );
            })}
          </div>
        )}

        {error && <PmErrorText>{error}</PmErrorText>}
      </PmModal>

      {previewFile && (
        <LocalFilePreviewModal file={previewFile} onClose={() => setPreviewFile(null)} />
      )}
    </>
  );
}
