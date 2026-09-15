import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import { useTranslations } from "next-intl";
import { PmButton } from "@/features/project-management/components/ui/PmButton";
import { PmDrawer } from "@/features/project-management/components/ui/PmDrawer";
import { PmPill, PmTag } from "@/features/project-management/components/ui/PmPill";
import type { TemplateTaskResponseDTO } from "@/features/project-management/dto/responseDTO/templateTask.response";

import styles from "./CategoryTaskDrawer.module.scss";

type CategoryTaskDrawerProps = {
  categoryLabel: string;
  versionNo: number;
  tasks: TemplateTaskResponseDTO[];
  isDraft: boolean;
  onClose: () => void;
  onEdit: (task: TemplateTaskResponseDTO) => void;
  onDelete: (task: TemplateTaskResponseDTO) => void;
  onView?: (task: TemplateTaskResponseDTO) => void;
  onAddNew: () => void;
  // Nút phụ trong header — dùng riêng cho category "Tìm hiểu công ty" để mở xem đầy đủ tài liệu
  // Company Core (domain POLICY) mà không cần 1 thẻ category riêng gây trùng tên ngoài lưới chính.
  secondaryAction?: { label: string; onClick: () => void };
};

/** Drawer liệt kê toàn bộ task trong 1 category của 1 version — sửa/xoá từng task (mở
 * TaskFormModal đè lên trên), chỉ cho phép khi version đang DRAFT (đọc-thoải mái khi không). */
export function CategoryTaskDrawer({
  categoryLabel,
  versionNo,
  tasks,
  isDraft,
  onClose,
  onEdit,
  onDelete,
  onView,
  onAddNew,
  secondaryAction,
}: CategoryTaskDrawerProps) {
  const t = useTranslations("pmUi");
  return (
    <PmDrawer
      eyebrow={
        <div className={styles.eyebrowRow}>
          <PmTag>{t("masterTemplateVersion", { version: versionNo })}</PmTag>
          {secondaryAction && (
            <button
              type="button"
              className={styles.secondaryActionBtn}
              onClick={secondaryAction.onClick}
            >
              <PmIcon name="doc" size={12} />
              {secondaryAction.label}
            </button>
          )}
        </div>
      }
      title={categoryLabel}
      onClose={onClose}
      footer={
        isDraft ? (
          <PmButton className={styles.addBtn} onClick={onAddNew}>
            <PmIcon name="plus" size={14} />
            {t("addTemplateTask")}
          </PmButton>
        ) : (
          <p className={styles.readOnlyNote}>{t("versionReadOnly")}</p>
        )
      }
    >
      {tasks.length === 0 ? (
        <p className={styles.emptyNote}>{t("categoryHasNoTasks")}</p>
      ) : (
        tasks.map((task) => (
          <div
            key={task.template_task_id}
            className={`${styles.taskCard} ${onView ? styles.taskCardClickable : ""}`}
            role={onView ? "button" : undefined}
            tabIndex={onView ? 0 : undefined}
            onClick={() => onView?.(task)}
            onKeyDown={(event) => {
              if (!onView) return;
              if (event.currentTarget !== event.target) return;
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onView(task);
              }
            }}
          >
            <div className={styles.taskCardTop}>
              <span className={styles.taskTitle}>{task.title_pattern}</span>
              {isDraft && (
                <div className={styles.taskCardActions}>
                  <button
                    type="button"
                    className={styles.iconBtn}
                    onClick={(event) => {
                      event.stopPropagation();
                      onEdit(task);
                    }}
                    title={t("edit")}
                  >
                    <PmIcon name="pencil" size={13} />
                  </button>
                  <button
                    type="button"
                    className={`${styles.iconBtn} ${styles.iconBtnDanger}`}
                    onClick={(event) => {
                      event.stopPropagation();
                      onDelete(task);
                    }}
                    title={t("delete")}
                  >
                    <PmIcon name="trash" size={13} />
                  </button>
                </div>
              )}
            </div>
            <p className={styles.taskObjective}>{task.objective}</p>
            <div className={styles.taskMetaRow}>
              <PmPill variant={task.mandatory ? "warning" : "neutral"}>
                {task.mandatory ? t("required") : t("optional")}
              </PmPill>
              <span className={styles.taskDuration}>
                {t("minutes", { count: task.estimated_minutes })}
              </span>
            </div>
          </div>
        ))
      )}
    </PmDrawer>
  );
}
