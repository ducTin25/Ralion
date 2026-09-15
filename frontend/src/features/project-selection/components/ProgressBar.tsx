interface ProgressBarProps {
  done: number;
  total: number;
  projectName: string;
}

export function ProgressBar({ done, total, projectName }: ProgressBarProps) {
  const t = useTranslations("projectSelection");
  const percentage = total > 0 ? Math.round((done / total) * 100) : 0;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3 text-[13.5px] text-text-muted">
        <span>{t("requiredTasks")}</span>
        <span className="tabular-nums">
          {done}/{total} · {percentage}%
        </span>
      </div>
      <div
        role="progressbar"
        aria-label={t("progressLabel", { done, total, project: projectName })}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percentage}
        className="h-1.5 overflow-hidden rounded-[3px] bg-divider"
      >
        <div
          className={`h-full rounded-[3px] ${percentage === 100 ? "bg-success" : "bg-progress"}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
import { useTranslations } from "next-intl";
