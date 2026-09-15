import type { PlanStatus } from "@/types/project";
import { useTranslations } from "next-intl";

const statusStyles: Record<PlanStatus | "NONE", { labelKey: string; className: string }> = {
  DRAFT: { labelKey: "statusDraft", className: "border-border bg-canvas text-text-muted" },
  APPROVED: {
    labelKey: "statusApproved",
    className: "border-tint-navy-border bg-tint-navy text-link",
  },
  ACTIVE: {
    labelKey: "statusActive",
    className: "border-tint-navy-border bg-tint-navy text-link",
  },
  PROJECT_READY: {
    labelKey: "statusReady",
    className: "border-success-border bg-success-bg text-success-text",
  },
  ONBOARDING_CLOSED: {
    labelKey: "statusClosed",
    className: "border-border bg-canvas text-text-muted",
  },
  NONE: {
    labelKey: "statusNone",
    className: "border-warn-border bg-warn-bg text-warn-text",
  },
};

export function StatusBadge({ status }: { status: PlanStatus | null }) {
  const t = useTranslations("projectSelection");
  const style = statusStyles[status ?? "NONE"];
  return (
    <span
      className={`inline-flex h-6 items-center gap-1.5 rounded-sm border px-2 text-[12.5px] font-semibold whitespace-nowrap ${style.className}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {t(style.labelKey)}
    </span>
  );
}
