import { useTranslations } from "next-intl";

import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import { PmModal } from "@/features/project-management/components/ui/PmModal";
import { PmPill, PmTag } from "@/features/project-management/components/ui/PmPill";
import type { TaskDependencyResponseDTO } from "@/features/project-management/dto/responseDTO/taskDependency.response";
import type { TemplateTaskResponseDTO } from "@/features/project-management/dto/responseDTO/templateTask.response";

import styles from "./TemplateTaskDetailModal.module.scss";

type TemplateTaskDetailModalProps = {
  task: TemplateTaskResponseDTO;
  categoryLabel: string;
  versionNo: number;
  allTasks: TemplateTaskResponseDTO[];
  dependencies: TaskDependencyResponseDTO[];
  onClose: () => void;
};

/** Read-only detail view used by every template version, including approved/archived history. */
export function TemplateTaskDetailModal({
  task,
  categoryLabel,
  versionNo,
  allTasks,
  dependencies,
  onClose,
}: TemplateTaskDetailModalProps) {
  const t = useTranslations("pmUi");
  const predecessorIds = new Set(
    dependencies
      .filter((dependency) => dependency.successor_task_id === task.template_task_id)
      .map((dependency) => dependency.predecessor_task_id),
  );
  const predecessors = allTasks
    .filter((candidate) => predecessorIds.has(candidate.template_task_id))
    .sort((a, b) => a.display_order - b.display_order);

  return (
    <PmModal title={t("taskDetails")} icon="eye" tone="primary" size="wide" onClose={onClose}>
      <div className={styles.heading}>
        <div>
          <div className={styles.eyebrow}>
            <PmTag>{t("masterTemplateVersion", { version: versionNo })}</PmTag>
            <span>{categoryLabel}</span>
          </div>
          <h4>{task.title_pattern}</h4>
        </div>
        <div className={styles.meta}>
          <PmPill variant={task.mandatory ? "warning" : "neutral"}>
            {task.mandatory ? t("required") : t("optional")}
          </PmPill>
          <span>
            <PmIcon name="flag" size={13} />
            {t("minutes", { count: task.estimated_minutes })}
          </span>
        </div>
      </div>

      <section className={styles.detailSection}>
        <h5>{t("objective")}</h5>
        <p>{task.objective}</p>
      </section>

      <section className={styles.detailSection}>
        <h5>{t("instructions")}</h5>
        <p className={styles.preWrap}>{task.instruction_template}</p>
      </section>

      <section className={styles.detailSection}>
        <h5>{t("dependsOn")}</h5>
        {predecessors.length > 0 ? (
          <ul className={styles.dependencies}>
            {predecessors.map((predecessor) => (
              <li key={predecessor.template_task_id}>
                <PmIcon name="check2" size={12} />
                {predecessor.title_pattern}
              </li>
            ))}
          </ul>
        ) : (
          <p className={styles.muted}>{t("noDependenciesToChoose")}</p>
        )}
      </section>
    </PmModal>
  );
}
