"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import type { ProjectResponseDTO } from "@/features/project-management/dto/responseDTO/project.response";
import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import shellStyles from "@/features/project-management/components/PmShell.module.scss";

import styles from "./ProjectSwitcher.module.scss";

type ProjectSwitcherProps = {
  projects: ProjectResponseDTO[];
  selectedProjectId: number | null;
  onSelect: (projectId: number) => void;
};

/** Dropdown chọn project — chỉ hiện ở topbar khi đang xem "Thành viên", vì cần biết đang xem project nào. */
export function ProjectSwitcher({ projects, selectedProjectId, onSelect }: ProjectSwitcherProps) {
  const t = useTranslations("pmUi");
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const selected = projects.find((p) => p.project_id === selectedProjectId);

  useEffect(() => {
    if (!open) return;
    const closeOutside = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      triggerRef.current?.focus();
    };
    document.addEventListener("mousedown", closeOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  if (projects.length === 0) return null;

  return (
    <div className={styles.wrap} ref={rootRef}>
      <button
        ref={triggerRef}
        type="button"
        className={shellStyles.projSwitch}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t("switchProject")}
        onClick={() => setOpen((v) => !v)}
      >
        <span className={shellStyles.projDot} />
        <span>{selected?.key ?? t("selectProject")}</span>
        <PmIcon name="chevron-down" size={12} />
      </button>

      {open && (
        <div className={styles.dropdown} role="menu" aria-label={t("switchProject")}>
          {projects.map((p) => (
            <button
              key={p.project_id}
              type="button"
              role="menuitem"
              className={styles.option}
              onClick={() => {
                onSelect(p.project_id);
                setOpen(false);
              }}
            >
              {p.key} — {p.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
