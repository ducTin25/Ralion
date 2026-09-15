"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import {
  createTaskDependency,
  createTemplateTask,
  deleteTaskDependency,
  updateTemplateTask,
  type TemplateTaskFormInput,
} from "@/features/project-management/api";
import type { TaskDependencyResponseDTO } from "@/features/project-management/dto/responseDTO/taskDependency.response";
import type {
  TaskCategory,
  TemplateTaskResponseDTO,
} from "@/features/project-management/dto/responseDTO/templateTask.response";
import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import { PmButton } from "@/features/project-management/components/ui/PmButton";
import {
  PmField,
  PmErrorText,
  PmInput,
  PmSelect,
  PmTextarea,
} from "@/features/project-management/components/ui/PmField";
import { PmModal } from "@/features/project-management/components/ui/PmModal";
import { pmToast } from "@/features/project-management/components/ui/PmToast";

import styles from "./TaskFormModal.module.scss";

export type CategoryVariant = "accent" | "success" | "warning" | "violet";

// Đúng 5 category chuẩn, khớp 1:1 tên với 5 giá trị đầu của DocumentCategory (tài liệu dự án —
// OVERVIEW/ARCHITECTURE/SETUP/ACCESS_SECURITY/CODEBASE_GUIDE) để sau này Phase 4 (agent sinh
// PlanTask) nối đúng 1 task ↔ 1 tài liệu theo category trùng tên. CONVENTION/FIRST_TASK/FIRST_PR
// tạm ẩn (mở rộng làm sau — xem DEFERRED_TASK_CATEGORIES ở backend `src/model/enums.py`), vẫn còn
// trong type TaskCategory vì dữ liệu cũ có thể còn nhưng không cho chọn mới ở đây.
export const CATEGORY_OPTIONS: {
  value: TaskCategory;
  label: string;
  description: string;
  labelKey: string;
  descriptionKey: string;
  icon: Parameters<typeof PmIcon>[0]["name"];
  variant: CategoryVariant;
}[] = [
  {
    value: "COMPANY",
    label: "Get to know the company",
    description: "HR, security and benefits policies — shared across every project",
    labelKey: "categoryCompany",
    // Nhóm duy nhất đọc chính sách chung (domain POLICY) thay vì tài liệu riêng của dự án — đứng
    // đầu danh sách vì lộ trình chuẩn là "1 phần công ty rồi tới 5 phần dự án".
    descriptionKey: "categoryCompanyDescription",
    icon: "shield",
    variant: "accent",
  },
  {
    value: "ORIENTATION",
    label: "Project overview",
    description: "Business context, goals and operating numbers — matches the Overview doc",
    labelKey: "categoryOrientation",
    descriptionKey: "categoryOrientationDescription",
    icon: "doc",
    variant: "success",
  },
  {
    value: "ARCHITECTURE",
    label: "System architecture",
    description:
      "Overall architecture, tech stack and main data flows — matches the Architecture doc",
    labelKey: "categoryArchitecture",
    descriptionKey: "categoryArchitectureDescription",
    icon: "grid",
    variant: "violet",
  },
  {
    value: "SETUP",
    label: "Environment setup",
    description: "Install tooling and run the service locally — matches the Setup doc",
    labelKey: "categorySetup",
    descriptionKey: "categorySetupDescription",
    icon: "flag",
    variant: "warning",
  },
  {
    value: "ACCESS",
    label: "Access & security",
    description:
      "Repository access, environments and internal tooling — matches the Access & Security doc",
    labelKey: "categoryAccess",
    descriptionKey: "categoryAccessDescription",
    icon: "key",
    variant: "accent",
  },
  {
    value: "CODEBASE",
    label: "Codebase guide",
    description: "Folder structure, main modules and key files — matches the Codebase Guide",
    labelKey: "categoryCodebase",
    descriptionKey: "categoryCodebaseDescription",
    icon: "book",
    variant: "success",
  },
];

const STEPS: { n: 1 | 2 | 3; labelKey: string }[] = [
  { n: 1, labelKey: "basicInformation" },
  { n: 2, labelKey: "content" },
  { n: 3, labelKey: "dependencies" },
];

type TaskFormModalProps = {
  versionId: number;
  defaultCategory: TaskCategory;
  allTasks: TemplateTaskResponseDTO[];
  dependencies: TaskDependencyResponseDTO[];
  editingTask?: TemplateTaskResponseDTO;
  onClose: () => void;
  onSaved: () => void;
};

/** Form tạo/sửa 1 TemplateTask, chia 3 bước (Thông tin cơ bản → Nội dung → Phụ thuộc) — chỉ mở
 * khi version đang DRAFT (đã chặn ở nơi gọi). Chỉ submit thật ở bước cuối, dữ liệu giữ nguyên
 * khi qua lại giữa các bước (1 form state chung, không tách form riêng từng bước). */
export function TaskFormModal({
  versionId,
  defaultCategory,
  allTasks,
  dependencies,
  editingTask,
  onClose,
  onSaved,
}: TaskFormModalProps) {
  const t = useTranslations("pmUi");
  const isEdit = editingTask !== undefined;
  const currentPredecessorIds = editingTask
    ? dependencies
        .filter((d) => d.successor_task_id === editingTask.template_task_id)
        .map((d) => d.predecessor_task_id)
    : [];

  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [category, setCategory] = useState<TaskCategory>(editingTask?.category ?? defaultCategory);
  const [titlePattern, setTitlePattern] = useState(editingTask?.title_pattern ?? "");
  const [objective, setObjective] = useState(editingTask?.objective ?? "");
  const [instructionTemplate, setInstructionTemplate] = useState(
    editingTask?.instruction_template ?? "",
  );
  const [mandatory, setMandatory] = useState(editingTask?.mandatory ?? true);
  const [estimatedMinutes, setEstimatedMinutes] = useState(editingTask?.estimated_minutes ?? 30);
  const [selectedPredecessorIds, setSelectedPredecessorIds] =
    useState<number[]>(currentPredecessorIds);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const candidatePredecessors = allTasks.filter(
    (t) => t.template_task_id !== editingTask?.template_task_id,
  );

  function togglePredecessor(taskId: number) {
    setSelectedPredecessorIds((prev) =>
      prev.includes(taskId) ? prev.filter((id) => id !== taskId) : [...prev, taskId],
    );
  }

  function handleNext() {
    if (step === 1 && !titlePattern.trim()) {
      setError(t("taskTitleRequired"));
      return;
    }
    if (step === 2 && (!objective.trim() || !instructionTemplate.trim())) {
      setError(t("objectiveInstructionsRequired"));
      return;
    }
    setError(null);
    setStep((s) => (s === 1 ? 2 : 3));
  }

  function handleBack() {
    setError(null);
    setStep((s) => (s === 3 ? 2 : 1));
  }

  async function handleSubmit() {
    if (!titlePattern.trim() || !objective.trim() || !instructionTemplate.trim()) {
      setError(t("taskFieldsRequired"));
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const input: TemplateTaskFormInput = {
        category,
        title_pattern: titlePattern.trim(),
        objective: objective.trim(),
        instruction_template: instructionTemplate.trim(),
        mandatory,
        estimated_minutes: estimatedMinutes,
      };

      const savedTaskId = isEdit
        ? (await updateTemplateTask(editingTask.template_task_id, input)).template_task_id
        : (await createTemplateTask(versionId, input)).template_task_id;

      const toAdd = selectedPredecessorIds.filter((id) => !currentPredecessorIds.includes(id));
      const toRemove = currentPredecessorIds.filter((id) => !selectedPredecessorIds.includes(id));

      await Promise.all(
        toAdd.map((predecessorId) => createTaskDependency(predecessorId, savedTaskId)),
      );
      await Promise.all(
        toRemove.map((predecessorId) => {
          const dep = dependencies.find(
            (d) => d.predecessor_task_id === predecessorId && d.successor_task_id === savedTaskId,
          );
          return dep ? deleteTaskDependency(dep.dependency_id) : Promise.resolve();
        }),
      );

      pmToast(isEdit ? t("taskSaved") : t("taskAdded"));
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("genericRetryError"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <PmModal
      title={isEdit ? t("editTask") : t("addTask")}
      icon={isEdit ? "pencil" : "plus"}
      tone="primary"
      size="wide"
      onClose={onClose}
      footer={
        <>
          {step === 1 ? (
            <PmButton onClick={onClose} disabled={saving}>
              {t("cancel")}
            </PmButton>
          ) : (
            <PmButton onClick={handleBack} disabled={saving}>
              <PmIcon name="arrow" size={12} className={styles.backIcon} />
              {t("back")}
            </PmButton>
          )}
          {step < 3 ? (
            <PmButton variant="primary" onClick={handleNext}>
              {t("continue")}
              <PmIcon name="arrow" size={12} />
            </PmButton>
          ) : (
            <PmButton variant="primary" onClick={handleSubmit} disabled={saving}>
              {saving ? t("saving") : t("save")}
            </PmButton>
          )}
        </>
      }
    >
      <div className={styles.stepper}>
        {STEPS.map((s, idx) => (
          <div key={s.n} className={styles.stepperItem}>
            <div className={styles.stepperNode}>
              <span
                className={`${styles.stepDot} ${step === s.n ? styles.stepCurrent : ""} ${step > s.n ? styles.stepDone : ""}`}
              >
                {step > s.n ? <PmIcon name="check2" size={11} /> : s.n}
              </span>
              <span className={step >= s.n ? styles.stepLabelActive : styles.stepLabel}>
                {t(s.labelKey)}
              </span>
            </div>
            {idx < STEPS.length - 1 && (
              <div className={`${styles.stepLine} ${step > s.n ? styles.stepLineDone : ""}`} />
            )}
          </div>
        ))}
      </div>

      <div className={styles.form}>
        {step === 1 && (
          <>
            <div className={styles.row}>
              <PmField label={t("category")}>
                <PmSelect
                  value={category}
                  onChange={(e) => setCategory(e.target.value as TaskCategory)}
                >
                  {CATEGORY_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {t(opt.labelKey)}
                    </option>
                  ))}
                </PmSelect>
              </PmField>
              <PmField label={t("estimatedMinutes")}>
                <PmInput
                  type="number"
                  min={1}
                  value={estimatedMinutes}
                  onChange={(e) => setEstimatedMinutes(Number(e.target.value))}
                />
              </PmField>
            </div>

            <PmField label={t("taskTitle")}>
              <PmInput value={titlePattern} onChange={(e) => setTitlePattern(e.target.value)} />
            </PmField>

            <label className={styles.checkboxRow}>
              <input
                type="checkbox"
                checked={mandatory}
                onChange={(e) => setMandatory(e.target.checked)}
              />
              {t("requiredTask")}
            </label>
          </>
        )}

        {step === 2 && (
          <>
            <PmField label={t("objective")}>
              <PmTextarea value={objective} onChange={(e) => setObjective(e.target.value)} />
            </PmField>

            <PmField label={t("instructions")}>
              <PmTextarea
                value={instructionTemplate}
                onChange={(e) => setInstructionTemplate(e.target.value)}
              />
            </PmField>
          </>
        )}

        {step === 3 &&
          (candidatePredecessors.length > 0 ? (
            <PmField label={t("dependsOn")}>
              <div className={styles.dependencyList}>
                {candidatePredecessors.map((t) => (
                  <label key={t.template_task_id} className={styles.dependencyItem}>
                    <input
                      type="checkbox"
                      checked={selectedPredecessorIds.includes(t.template_task_id)}
                      onChange={() => togglePredecessor(t.template_task_id)}
                    />
                    {t.title_pattern}
                  </label>
                ))}
              </div>
            </PmField>
          ) : (
            <p className={styles.noDeps}>
              {t("noDependenciesToChoose")}
            </p>
          ))}

        {error && <PmErrorText>{error}</PmErrorText>}
      </div>
    </PmModal>
  );
}
