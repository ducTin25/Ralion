"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import type { ProjectResponseDTO } from "@/features/project-management/dto/responseDTO/project.response";
import type { KnowledgeDocumentResponseDTO } from "@/features/project-management/dto/responseDTO/knowledgeDocument.response";
import type { OnboardingTemplateResponseDTO } from "@/features/project-management/dto/responseDTO/onboardingTemplate.response";
import type { TaskDependencyResponseDTO } from "@/features/project-management/dto/responseDTO/taskDependency.response";
import type {
  TaskCategory,
  TemplateTaskResponseDTO,
} from "@/features/project-management/dto/responseDTO/templateTask.response";
import type { TemplateVersionResponseDTO } from "@/features/project-management/dto/responseDTO/templateVersion.response";
import {
  approveTemplateVersion,
  createOnboardingTemplateForProject,
  createTemplateVersion,
  deleteTemplateTask,
  getTemplateByProject,
  listPolicyDocuments,
  listTaskDependencies,
  listTemplateTasks,
  listTemplateVersions,
} from "@/features/project-management/api";
import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import {
  PmCard,
  PmKpiRow,
  PmPageHead,
  PmSectionTitle,
} from "@/features/project-management/components/ui/PmCard";
import { PmButton } from "@/features/project-management/components/ui/PmButton";
import { PmConfirmModal } from "@/features/project-management/components/ui/PmConfirmModal";
import { PmTag } from "@/features/project-management/components/ui/PmPill";
import { pmToast } from "@/features/project-management/components/ui/PmToast";
import tableStyles from "@/features/project-management/components/ui/PmTable.module.scss";
import { ApiError } from "@/lib/api";

import { CategoryTaskDrawer } from "./CategoryTaskDrawer";
import { CompanyCoreDrawer } from "./CompanyCoreDrawer";
import { CATEGORY_OPTIONS, type CategoryVariant, TaskFormModal } from "./TaskFormModal";
import { TemplateTaskDetailModal } from "./TemplateTaskDetailModal";
import { VersionTable } from "./VersionTable";
import styles from "./TemplateView.module.scss";

type TemplateViewProps = {
  project: ProjectResponseDTO | null;
};

const VARIANT_ICON_CLASS: Record<CategoryVariant, string> = {
  accent: "iconAccent",
  success: "iconSuccess",
  warning: "iconWarning",
  violet: "iconViolet",
};

/**
 * View "Master Template" — project tạo sau Phase 2 tự có sẵn 1 template (fork từ Global Master
 * Template lúc tạo project, xem SoT §11.16). Project cũ hơn có thể chưa có (404 ở
 * getTemplateByProject) — khi đó hiển thị trạng thái rỗng với nút backfill qua
 * createOnboardingTemplateForProject thay vì để PM bị kẹt không có lối ra.
 * Bố cục: KPI → bảng lịch sử version (mỗi hàng tự có hành động Duyệt/Nhân bản/Xem phù hợp trạng
 * thái) → lưới category (6 thẻ khớp `CATEGORY_OPTIONS`, gồm cả "Tìm hiểu công ty"), bấm vào mở
 * drawer sửa TemplateTask. Từ drawer của "Tìm hiểu công ty" có thêm nút phụ mở danh sách đầy đủ
 * tài liệu Company Core (domain POLICY, PM chỉ xem — không có API ghi cho phần này).
 * Đổi version xem, duyệt version, xoá task đều đi qua modal xác nhận giải thích hậu quả trước
 * khi thực hiện — không đổi trạng thái/chuyển view ngay khi vừa bấm.
 */
export function TemplateView({ project }: TemplateViewProps) {
  const t = useTranslations("pmUi");
  const [template, setTemplate] = useState<OnboardingTemplateResponseDTO | null>(null);
  const [templateMissing, setTemplateMissing] = useState(false);
  const [creatingTemplate, setCreatingTemplate] = useState(false);
  const [versions, setVersions] = useState<TemplateVersionResponseDTO[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null);
  const [tasks, setTasks] = useState<TemplateTaskResponseDTO[]>([]);
  const [dependencies, setDependencies] = useState<TaskDependencyResponseDTO[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [confirmLoading, setConfirmLoading] = useState(false);

  const [policyDocuments, setPolicyDocuments] = useState<KnowledgeDocumentResponseDTO[]>([]);

  const [openCategory, setOpenCategory] = useState<TaskCategory | null>(null);
  const [showCompanyCore, setShowCompanyCore] = useState(false);
  const [modalMode, setModalMode] = useState<"create" | TemplateTaskResponseDTO | null>(null);
  const [viewingTask, setViewingTask] = useState<TemplateTaskResponseDTO | null>(null);

  const [confirmViewVersion, setConfirmViewVersion] = useState<TemplateVersionResponseDTO | null>(
    null,
  );
  const [confirmApproveVersion, setConfirmApproveVersion] =
    useState<TemplateVersionResponseDTO | null>(null);
  const [confirmDeleteTask, setConfirmDeleteTask] = useState<TemplateTaskResponseDTO | null>(null);

  async function loadVersionData(versionId: number) {
    const [taskData, depData] = await Promise.all([
      listTemplateTasks(versionId),
      listTaskDependencies(versionId),
    ]);
    setTasks(taskData);
    setDependencies(depData);
  }

  async function loadAll(projectId: number) {
    setLoading(true);
    setError(null);
    setTemplateMissing(false);
    try {
      const templateData = await getTemplateByProject(projectId);
      setTemplate(templateData);
      const versionData = await listTemplateVersions(templateData.template_id);
      setVersions(versionData);
      const nextSelected =
        versionData.find((v) => v.status === "APPROVED") ?? versionData[0] ?? null;
      setSelectedVersionId(nextSelected ? nextSelected.version_id : null);
      if (nextSelected) {
        await loadVersionData(nextSelected.version_id);
      } else {
        setTasks([]);
        setDependencies([]);
      }
    } catch (err) {
      setTemplate(null);
      setVersions([]);
      setSelectedVersionId(null);
      if (err instanceof ApiError && err.status === 404) {
        setTemplateMissing(true);
      } else {
        setError(err instanceof Error ? err.message : t("masterTemplateLoadError"));
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateTemplate() {
    if (!project) return;
    setCreatingTemplate(true);
    setError(null);
    try {
      await createOnboardingTemplateForProject(project.project_id);
      pmToast(t("masterTemplateCreated"));
      await loadAll(project.project_id);
    } catch (err) {
      setError(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : t("masterTemplateCreateError"),
      );
    } finally {
      setCreatingTemplate(false);
    }
  }

  // Reset khi đổi project — điều chỉnh state ngay trong render thay vì effect (theo
  // react.dev/learn/you-might-not-need-an-effect#adjusting-some-state-when-a-prop-changes).
  const [loadedProjectId, setLoadedProjectId] = useState<number | null>(null);
  if ((project?.project_id ?? null) !== loadedProjectId) {
    setLoadedProjectId(project?.project_id ?? null);
    setTemplate(null);
    setTemplateMissing(false);
    setVersions([]);
    setSelectedVersionId(null);
    setTasks([]);
    setDependencies([]);
    setViewingTask(null);
  }

  useEffect(() => {
    if (project === null) return;
    // Lỗi đã được setError bên trong loadAll, không cần catch riêng ở đây.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadAll(project.project_id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project?.project_id]);

  useEffect(() => {
    // Company Core dùng chung mọi project, không phụ thuộc project/version đang chọn — chỉ cần
    // tải 1 lần khi vào trang.
    listPolicyDocuments()
      .then(setPolicyDocuments)
      .catch(() => setPolicyDocuments([]));
  }, []);

  async function handleViewVersion(versionId: number) {
    setViewingTask(null);
    setSelectedVersionId(versionId);
    setLoading(true);
    try {
      await loadVersionData(versionId);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("versionLoadError"));
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateVersion(cloneFromVersionId?: number) {
    if (!template) return;
    const sourceVersionId = cloneFromVersionId ?? selectedVersionId ?? undefined;
    setActionLoading(true);
    setError(null);
    try {
      const newVersion = await createTemplateVersion(template.template_id, sourceVersionId);
      pmToast(t("versionCreated", { version: newVersion.version_no }));
      const versionData = await listTemplateVersions(template.template_id);
      setVersions(versionData);
      setSelectedVersionId(newVersion.version_id);
      await loadVersionData(newVersion.version_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("versionCreateError"));
    } finally {
      setActionLoading(false);
    }
  }

  async function handleApproveVersion(versionId: number) {
    if (!project) return;
    setActionLoading(true);
    setError(null);
    try {
      await approveTemplateVersion(versionId);
      pmToast(t("versionApproved"));
      await loadAll(project.project_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("versionApproveError"));
    } finally {
      setActionLoading(false);
    }
  }

  async function handleDeleteTask(taskId: number) {
    if (!selectedVersionId) return;
    try {
      await deleteTemplateTask(taskId);
      pmToast(t("taskDeleted"));
      await loadVersionData(selectedVersionId);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("taskDeleteError"));
    }
  }

  async function confirmView() {
    if (!confirmViewVersion) return;
    setConfirmLoading(true);
    await handleViewVersion(confirmViewVersion.version_id);
    setConfirmLoading(false);
    setConfirmViewVersion(null);
  }

  async function confirmApprove() {
    if (!confirmApproveVersion) return;
    setConfirmLoading(true);
    await handleApproveVersion(confirmApproveVersion.version_id);
    setConfirmLoading(false);
    setConfirmApproveVersion(null);
  }

  async function confirmDelete() {
    if (!confirmDeleteTask) return;
    setConfirmLoading(true);
    await handleDeleteTask(confirmDeleteTask.template_task_id);
    setConfirmLoading(false);
    setConfirmDeleteTask(null);
  }

  if (!project) {
    return (
      <section>
        <PmPageHead icon="book" title={t("masterTemplate")} />
        <PmCard>
          <p className={tableStyles.emptyNote}>{t("noManagedProject")}</p>
        </PmCard>
      </section>
    );
  }

  if (!loading && templateMissing) {
    return (
      <section>
        <PmPageHead icon="book" title={t("masterTemplate")} />
        {error && <p className={styles.errorBanner}>{error}</p>}
        <PmCard>
          <p className={tableStyles.emptyNote}>{t("noMasterTemplate")}</p>
          <PmButton
            variant="primary"
            className="mt-3"
            onClick={handleCreateTemplate}
            disabled={creatingTemplate}
          >
            <PmIcon name="plus" size={14} />
            {creatingTemplate ? t("creating") : t("createMasterTemplate")}
          </PmButton>
        </PmCard>
      </section>
    );
  }

  const selectedVersion = versions.find((v) => v.version_id === selectedVersionId) ?? null;
  const isDraft = selectedVersion?.status === "DRAFT";
  const currentlyApprovedVersion = versions.find((v) => v.status === "APPROVED") ?? null;

  const mandatoryCount = tasks.filter((t) => t.mandatory).length;
  const totalMinutes = tasks.reduce((sum, t) => sum + t.estimated_minutes, 0);
  const totalHours = (totalMinutes / 60).toFixed(1);

  const openCategoryMeta = openCategory
    ? CATEGORY_OPTIONS.find((opt) => opt.value === openCategory)
    : undefined;
  const openCategoryTasks = openCategory
    ? tasks
        .filter((t) => t.category === openCategory)
        .sort((a, b) => a.display_order - b.display_order)
    : [];

  return (
    <section>
      <PmPageHead icon="book" title={t("masterTemplate")} subtitle={t("masterTemplateSubtitle")} />

      {!loading && tasks.length > 0 && (
        <PmKpiRow
          items={[
            { label: t("tasks"), value: tasks.length, icon: "doc", variant: "accent" },
            { label: t("required"), value: mandatoryCount, icon: "check2", variant: "warning" },
            {
              label: t("estimatedTime"),
              value: t("hours", { count: totalHours }),
              icon: "check-circle",
              variant: "success",
            },
          ]}
        />
      )}

      {error && <p className={styles.errorBanner}>{error}</p>}

      <PmCard className={styles.versionCard}>
        <PmSectionTitle>{t("versionHistory")}</PmSectionTitle>
        {loading && versions.length === 0 ? (
          <p className={tableStyles.emptyNote}>{t("loading")}</p>
        ) : (
          <VersionTable
            versions={versions}
            selectedVersionId={selectedVersionId}
            actionLoading={actionLoading}
            onView={setConfirmViewVersion}
            onApprove={setConfirmApproveVersion}
            onCloneFrom={(version) => handleCreateVersion(version.version_id)}
          />
        )}
      </PmCard>

      <PmSectionTitle
        hint={<>{t("viewingVersion", { version: selectedVersion?.version_no ?? "-" })}</>}
      >
        {t("tasksByCategory")}
      </PmSectionTitle>
      <div className={styles.categoryGrid}>
        {CATEGORY_OPTIONS.map((opt) => {
          const count = tasks.filter((t) => t.category === opt.value).length;
          return (
            <button
              key={opt.value}
              type="button"
              className={styles.categoryCard}
              disabled={!selectedVersionId}
              onClick={() => setOpenCategory(opt.value)}
            >
              <div className={styles.categoryCardTop}>
                <div className={styles.categoryCardTitle}>
                  <span
                    className={`${styles.categoryIcon} ${styles[VARIANT_ICON_CLASS[opt.variant]]}`}
                  >
                    <PmIcon name={opt.icon} size={16} />
                  </span>
                  <b>{t(opt.labelKey)}</b>
                </div>
                <PmTag>{t("taskCount", { count })}</PmTag>
              </div>
              <p className={styles.categoryDesc}>{t(opt.descriptionKey)}</p>
            </button>
          );
        })}
      </div>

      {showCompanyCore && (
        <CompanyCoreDrawer documents={policyDocuments} onClose={() => setShowCompanyCore(false)} />
      )}

      {openCategory && openCategoryMeta && selectedVersion && (
        <CategoryTaskDrawer
          categoryLabel={t(openCategoryMeta.labelKey)}
          versionNo={selectedVersion.version_no}
          tasks={openCategoryTasks}
          isDraft={isDraft}
          onClose={() => setOpenCategory(null)}
          onEdit={(task) => setModalMode(task)}
          onDelete={(task) => setConfirmDeleteTask(task)}
          onView={setViewingTask}
          onAddNew={() => setModalMode("create")}
          secondaryAction={
            openCategory === "COMPANY"
              ? {
                  label: t("viewPolicySources", { count: policyDocuments.length }),
                  onClick: () => setShowCompanyCore(true),
                }
              : undefined
          }
        />
      )}

      {viewingTask && selectedVersion && openCategoryMeta && (
        <TemplateTaskDetailModal
          task={viewingTask}
          categoryLabel={t(openCategoryMeta.labelKey)}
          versionNo={selectedVersion.version_no}
          allTasks={tasks}
          dependencies={dependencies}
          onClose={() => setViewingTask(null)}
        />
      )}

      {modalMode && selectedVersionId && openCategory && (
        <TaskFormModal
          versionId={selectedVersionId}
          defaultCategory={openCategory}
          allTasks={tasks}
          dependencies={dependencies}
          editingTask={modalMode === "create" ? undefined : modalMode}
          onClose={() => setModalMode(null)}
          onSaved={() => loadVersionData(selectedVersionId)}
        />
      )}

      {confirmViewVersion && (
        <PmConfirmModal
          icon="eye"
          tone="primary"
          title={t("viewVersionTitle", { version: confirmViewVersion.version_no })}
          confirmLabel={t("viewThisVersion")}
          loading={confirmLoading}
          onClose={() => setConfirmViewVersion(null)}
          onConfirm={confirmView}
          description={
            confirmViewVersion.status === "DRAFT" ? (
              <p>{t("viewDraftVersionBody", { version: confirmViewVersion.version_no })}</p>
            ) : confirmViewVersion.status === "APPROVED" ? (
              <p>{t("viewApprovedVersionBody", { version: confirmViewVersion.version_no })}</p>
            ) : (
              <p>{t("viewArchivedVersionBody", { version: confirmViewVersion.version_no })}</p>
            )
          }
        />
      )}

      {confirmApproveVersion && (
        <PmConfirmModal
          icon="check2"
          tone="success"
          title={
            confirmApproveVersion.status === "ARCHIVED"
              ? t("reapproveVersionTitle", { version: confirmApproveVersion.version_no })
              : t("approveVersionTitle", { version: confirmApproveVersion.version_no })
          }
          confirmLabel={
            confirmApproveVersion.status === "ARCHIVED" ? t("reapproveNow") : t("approveNow")
          }
          loading={confirmLoading}
          onClose={() => setConfirmApproveVersion(null)}
          onConfirm={confirmApprove}
          description={
            <>
              <p>{t("approveVersionBody", { version: confirmApproveVersion.version_no })}</p>
              {currentlyApprovedVersion &&
                currentlyApprovedVersion.version_id !== confirmApproveVersion.version_id && (
                  <p>
                    {t("archiveCurrentVersion", {
                      version: currentlyApprovedVersion.version_no,
                    })}
                  </p>
                )}
              <p>{t("approvedVersionReadOnly", { version: confirmApproveVersion.version_no })}</p>
            </>
          }
        />
      )}

      {confirmDeleteTask && (
        <PmConfirmModal
          icon="trash"
          tone="danger"
          title={t("deleteTaskTitle")}
          confirmLabel={t("deleteTask")}
          loading={confirmLoading}
          onClose={() => setConfirmDeleteTask(null)}
          onConfirm={confirmDelete}
          description={
            <>
              <p>
                {t("deleteTaskBody", {
                  task: confirmDeleteTask.title_pattern,
                  version: selectedVersion?.version_no ?? "-",
                })}
              </p>
              <p>{t("deleteTaskDependencies")}</p>
            </>
          }
        />
      )}
    </section>
  );
}
