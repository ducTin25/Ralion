"use client";

import { useEffect, useState } from "react";

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
  createTemplateVersion,
  deleteTemplateTask,
  listPolicyDocuments,
  listTaskDependencies,
  listTemplateTasks,
  listTemplateVersions,
} from "@/features/project-management/api";
import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import {
  PmCard,
  PmKpiRow,
  PmSectionTitle,
} from "@/features/project-management/components/ui/PmCard";
import { PmConfirmModal } from "@/features/project-management/components/ui/PmConfirmModal";
import { PmTag } from "@/features/project-management/components/ui/PmPill";
import { PmToastHost, pmToast } from "@/features/project-management/components/ui/PmToast";
import tableStyles from "@/features/project-management/components/ui/PmTable.module.scss";
import { CategoryTaskDrawer } from "@/features/project-management/components/template/CategoryTaskDrawer";
import { CompanyCoreDrawer } from "@/features/project-management/components/template/CompanyCoreDrawer";
import {
  CATEGORY_OPTIONS,
  type CategoryVariant,
  TaskFormModal,
} from "@/features/project-management/components/template/TaskFormModal";
import { TemplateTaskDetailModal } from "@/features/project-management/components/template/TemplateTaskDetailModal";
import { VersionTable } from "@/features/project-management/components/template/VersionTable";
import styles from "@/features/project-management/components/template/TemplateView.module.scss";

import { ConsoleApiError, consoleApi } from "./api";
import pmTokenStyles from "./pmTokenScope.module.scss";

const VARIANT_ICON_CLASS: Record<CategoryVariant, string> = {
  accent: "iconAccent",
  success: "iconSuccess",
  warning: "iconWarning",
  violet: "iconViolet",
};

/**
 * Admin-side "Master Template" — cùng bố cục/hành vi với `TemplateView.tsx` bên PM (KPI → lịch sử
 * version → lưới category → drawer sửa task), nhưng thao tác trên đúng 1 bản GLOBAL áp dụng cho
 * MỌI project thay vì template riêng của 1 project. Viết component riêng thay vì tái dùng thẳng
 * `TemplateView` để không đụng vào code PM đang chạy ổn định — 2 component chia sẻ lại các mảnh UI
 * con (VersionTable/CategoryTaskDrawer/TaskFormModal/CompanyCoreDrawer, vốn đã thuần theo props,
 * không gắn với project) và toàn bộ API task/version (đã scope-agnostic từ trước).
 */
export function MasterTemplatePanel() {
  const [template, setTemplate] = useState<OnboardingTemplateResponseDTO | null>(null);
  const [versions, setVersions] = useState<TemplateVersionResponseDTO[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null);
  const [tasks, setTasks] = useState<TemplateTaskResponseDTO[]>([]);
  const [dependencies, setDependencies] = useState<TaskDependencyResponseDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
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

  async function loadAll() {
    setLoading(true);
    setError(null);
    setNotFound(false);
    try {
      const templateData = await consoleApi.masterTemplate();
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
      if (err instanceof ConsoleApiError && err.status === 404) {
        setNotFound(true);
      } else {
        setError(err instanceof Error ? err.message : "Không tải được Master Template");
      }
      setTemplate(null);
      setVersions([]);
      setSelectedVersionId(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // Fetch khi mount — pattern hợp lệ theo react.dev/learn/you-might-not-need-an-effect (đồng bộ
    // với external API), rule set-state-in-effect không theo dõi được setState gọi qua hàm tách
    // riêng (`loadAll`), chỉ nhận diện setState gọi trực tiếp trong thân effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    // Company Core dùng chung mọi project, không phụ thuộc template đang chọn — chỉ cần tải 1 lần.
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
      setError(err instanceof Error ? err.message : "Không tải được dữ liệu version");
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
      pmToast(`Đã tạo phiên bản v${newVersion.version_no}`);
      const versionData = await listTemplateVersions(template.template_id);
      setVersions(versionData);
      setSelectedVersionId(newVersion.version_id);
      await loadVersionData(newVersion.version_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tạo được version mới");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleApproveVersion(versionId: number) {
    setActionLoading(true);
    setError(null);
    try {
      await approveTemplateVersion(versionId);
      pmToast("Đã duyệt phiên bản");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không duyệt được version này");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleDeleteTask(taskId: number) {
    if (!selectedVersionId) return;
    try {
      await deleteTemplateTask(taskId);
      pmToast("Đã xoá task");
      await loadVersionData(selectedVersionId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không xoá được task");
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

  if (notFound) {
    return (
      <div className={pmTokenStyles.pmTokenScope}>
        <PmCard>
          <p className={tableStyles.emptyNote}>
            Chưa có Global Master Template nào — hệ thống chưa có bản chuẩn để các project mới fork
            theo. Liên hệ đội kỹ thuật để khởi tạo.
          </p>
        </PmCard>
      </div>
    );
  }

  if (error) {
    return (
      <div className={pmTokenStyles.pmTokenScope}>
        <PmCard>
          <p className={styles.errorBanner}>{error}</p>
        </PmCard>
      </div>
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
    <div className={pmTokenStyles.pmTokenScope}>
      {/* Admin không có PmShell nào mount PmToastHost sẵn — pmToast() cần đúng 1 host mới
          hiện được (xem PmToast.tsx: chỉ phát sự kiện, không tự vẽ gì nếu không có host). */}
      <PmToastHost />
      {!loading && tasks.length > 0 && (
        <PmKpiRow
          items={[
            { label: "Tổng task", value: tasks.length, icon: "doc", variant: "accent" },
            { label: "Bắt buộc", value: mandatoryCount, icon: "check2", variant: "warning" },
            {
              label: "Tuỳ chọn",
              value: tasks.length - mandatoryCount,
              icon: "life",
              variant: "violet",
            },
            {
              label: "Thời gian ước tính",
              value: `${totalHours} giờ`,
              icon: "check-circle",
              variant: "success",
            },
          ]}
        />
      )}

      <PmCard className={styles.versionCard}>
        <PmSectionTitle
          hint={
            <>
              Đang xem &amp; áp dụng cho project mới: <b>v{selectedVersion?.version_no ?? "-"}</b>
            </>
          }
        >
          Lịch sử version
        </PmSectionTitle>
        {loading && versions.length === 0 ? (
          <p className={tableStyles.emptyNote}>Đang tải...</p>
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
        hint={
          <>
            Đang xem <b>v{selectedVersion?.version_no ?? "-"}</b> — nhấn vào nhóm để xem / chỉnh sửa
            Template Task
          </>
        }
      >
        Nhóm task theo category
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
                  <b>{opt.label}</b>
                </div>
                <PmTag>{count} task</PmTag>
              </div>
              <p className={styles.categoryDesc}>{opt.description}</p>
            </button>
          );
        })}
      </div>

      {showCompanyCore && (
        <CompanyCoreDrawer documents={policyDocuments} onClose={() => setShowCompanyCore(false)} />
      )}

      {openCategory && openCategoryMeta && selectedVersion && (
        <CategoryTaskDrawer
          categoryLabel={openCategoryMeta.label}
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
                  label: `Xem ${policyDocuments.length} tài liệu chính sách nguồn`,
                  onClick: () => setShowCompanyCore(true),
                }
              : undefined
          }
        />
      )}

      {viewingTask && selectedVersion && openCategoryMeta && (
        <TemplateTaskDetailModal
          task={viewingTask}
          categoryLabel={openCategoryMeta.label}
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
          title={`Xem phiên bản v${confirmViewVersion.version_no}?`}
          confirmLabel="Xem phiên bản này"
          loading={confirmLoading}
          onClose={() => setConfirmViewVersion(null)}
          onConfirm={confirmView}
          description={
            confirmViewVersion.status === "DRAFT" ? (
              <p>
                Bạn sẽ chuyển sang xem nội dung phiên bản <b>v{confirmViewVersion.version_no}</b> —
                đang <b>Nháp</b>, chưa được duyệt. Vì chưa duyệt nên bạn có thể thêm/sửa/xoá task
                trong các nhóm category của phiên bản này.
              </p>
            ) : confirmViewVersion.status === "APPROVED" ? (
              <p>
                Bạn sẽ chuyển sang xem phiên bản <b>v{confirmViewVersion.version_no}</b> — đây là
                bản <b>đang áp dụng</b> cho MỌI project mới, dùng để fork Project Template khi tạo
                project. Phiên bản đã duyệt thì không sửa được nội dung nữa.
              </p>
            ) : (
              <p>
                Bạn sẽ chuyển sang xem phiên bản <b>v{confirmViewVersion.version_no}</b> — đã{" "}
                <b>lưu trữ</b>, chỉ xem chứ không sửa được. Muốn áp dụng lại đúng nội dung này, bấm
                &quot;Duyệt lại&quot; ở hàng của version đó; muốn sửa nội dung thì bấm &quot;Nhân
                bản&quot; để tạo 1 bản Nháp mới sao chép từ đây.
              </p>
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
              ? `Duyệt lại phiên bản v${confirmApproveVersion.version_no}?`
              : `Duyệt phiên bản v${confirmApproveVersion.version_no}?`
          }
          confirmLabel={
            confirmApproveVersion.status === "ARCHIVED" ? "Duyệt lại ngay" : "Duyệt ngay"
          }
          loading={confirmLoading}
          onClose={() => setConfirmApproveVersion(null)}
          onConfirm={confirmApprove}
          description={
            <>
              <p>
                Sau khi duyệt, <b>v{confirmApproveVersion.version_no}</b> sẽ trở thành phiên bản{" "}
                <b>đang áp dụng</b> — mọi project TẠO MỚI từ giờ trở đi sẽ fork checklist từ đúng
                phiên bản này. Đây chỉ là đổi trạng thái, <b>không tạo version mới</b>, và{" "}
                <b>không ảnh hưởng project đã tồn tại</b> (mỗi project giữ bản sao riêng của mình).
              </p>
              {currentlyApprovedVersion &&
                currentlyApprovedVersion.version_id !== confirmApproveVersion.version_id && (
                  <p>
                    Phiên bản <b>v{currentlyApprovedVersion.version_no}</b> đang áp dụng hiện tại sẽ
                    tự động chuyển sang <b>đã lưu trữ</b>.
                  </p>
                )}
              <p>
                Sau khi duyệt, bạn sẽ <b>không sửa/thêm/xoá</b> được task trong{" "}
                <b>v{confirmApproveVersion.version_no}</b> nữa — muốn sửa phải tạo 1 phiên bản Nháp
                mới (bấm &quot;Nhân bản&quot;).
              </p>
            </>
          }
        />
      )}

      {confirmDeleteTask && (
        <PmConfirmModal
          icon="trash"
          tone="danger"
          title="Xoá task này?"
          confirmLabel="Xoá task"
          loading={confirmLoading}
          onClose={() => setConfirmDeleteTask(null)}
          onConfirm={confirmDelete}
          description={
            <>
              <p>
                Task <b>&quot;{confirmDeleteTask.title_pattern}&quot;</b> sẽ bị xoá hẳn khỏi phiên
                bản <b>v{selectedVersion?.version_no ?? "-"}</b> — không thể khôi phục lại.
              </p>
              <p>
                Nếu task này có phụ thuộc (dependency) với task khác trong version, các liên kết đó
                cũng sẽ bị xoá theo.
              </p>
            </>
          }
        />
      )}
    </div>
  );
}
