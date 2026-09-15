import type { ProjectRole } from "@/types/project";
import { useTranslations } from "next-intl";

export type RoleFilterValue = "all" | ProjectRole;

interface RoleFilterProps {
  value: RoleFilterValue;
  counts: Record<RoleFilterValue, number>;
  onChange: (value: RoleFilterValue) => void;
}

export function RoleFilter({ value, counts, onChange }: RoleFilterProps) {
  const t = useTranslations("projectSelection");
  const options: Array<{ value: RoleFilterValue; label: string }> = [
    { value: "all", label: t("filterAll") },
    { value: "PM", label: "PM" },
    { value: "ENGINEER", label: t("engineer") },
  ];
  return (
    <div
      role="group"
      aria-label={t("filterLabel")}
      className="flex h-10 shrink-0 overflow-x-auto rounded-md border border-border-strong bg-surface max-md:h-11 max-md:w-full"
    >
      {options.map((option, index) => {
        const selected = value === option.value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={selected}
            onClick={() => onChange(option.value)}
            className={`min-w-max border-l px-3.5 text-[13.5px] transition-colors first:border-l-0 focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-link ${
              selected
                ? "bg-tint-navy font-semibold text-navy"
                : "border-header-border bg-surface text-text-muted hover:bg-canvas"
            } ${index === 0 ? "border-l-transparent" : ""}`}
          >
            {option.label} <span className="tabular-nums">{counts[option.value]}</span>
          </button>
        );
      })}
    </div>
  );
}
