"use client";

import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";

import { RalionBrand } from "@/components/brand/RalionBrand";
import { MemberIcon } from "@/features/member-onboarding/components/MemberIcon";
import { initials } from "@/features/member-onboarding/components/memberPortalUi";
import type { MemberProject } from "@/features/member-onboarding/types";

import styles from "./MemberPortal.module.scss";

type ProjectPickerProps = {
  projects: MemberProject[];
  memberName: string;
  hrefForProject: (projectId: number) => string;
};

export function ProjectPicker({ projects, hrefForProject }: ProjectPickerProps) {
  const t = useTranslations("member");

  return (
    <main className={styles.pickerPage}>
      <section className={styles.pickerCard} aria-labelledby="project-picker-title">
        <div className={styles.pickerBrand}>
          <div className={styles.pickerBrandLine} aria-hidden="true">
            <span />
            <i />
            <b />
          </div>
          <RalionBrand className={styles.brandRow} size={30} subtitle="future&tat" tone="inverse" />
          <p>{t("pickerBrandBody")}</p>
        </div>
        <div className={styles.pickerContent}>
          <h1 id="project-picker-title">{t("pickerTitle")}</h1>
          <p>{t("pickerBody")}</p>
          <div className={styles.projectOptions}>
            {projects.map((project) => (
              <Link
                key={project.project_id}
                href={hrefForProject(project.project_id)}
                className={styles.projectOption}
              >
                <span className={styles.projectInitials}>{initials(project.key)}</span>
                <span>
                  <b>{project.name}</b>
                  <small>{t("pickerProjectMeta", { key: project.key })}</small>
                </span>
                <MemberIcon name="arrow" size={17} />
              </Link>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
