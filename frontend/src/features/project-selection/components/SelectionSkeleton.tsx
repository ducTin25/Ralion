"use client";

import { useTranslations } from "next-intl";

function Bar({ className }: { className: string }) {
  return (
    <div
      className={`animate-[project-skeleton_1.4s_ease-in-out_infinite] rounded bg-skeleton ${className}`}
    />
  );
}

export function SelectionSkeleton() {
  const t = useTranslations("projectSelection");

  return (
    <div className="project-grid" aria-label={t("loadingProjects")} aria-busy="true">
      {Array.from({ length: 3 }, (_, index) => (
        <div key={index} className="h-full rounded-lg border border-border bg-surface p-5">
          <div className="flex gap-3">
            <Bar className="h-[38px] w-[38px] shrink-0" />
            <div className="flex-1 space-y-2">
              <Bar className="h-4 w-3/5" />
              <Bar className="h-3.5 w-2/5 bg-skeleton-soft" />
            </div>
            <Bar className="h-6 w-20 bg-skeleton-soft" />
          </div>
          <div className="my-4 h-px bg-divider" />
          <div className="space-y-3">
            <Bar className="h-3.5 w-4/5 bg-skeleton-soft" />
            <Bar className="h-3.5 w-3/4 bg-skeleton-soft" />
            <Bar className="h-3.5 w-2/3 bg-skeleton-soft" />
          </div>
          <div className="mt-5 space-y-2">
            <Bar className="h-3.5 w-full bg-skeleton-soft" />
            <Bar className="h-1.5 w-full bg-skeleton-faint" />
          </div>
          <div className="mt-6 flex items-center justify-between border-t border-divider-soft pt-4">
            <Bar className="h-3.5 w-2/5 bg-skeleton-soft" />
            <Bar className="h-10 w-[120px]" />
          </div>
        </div>
      ))}
    </div>
  );
}
