"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import type { ProjectResponseDTO } from "@/features/project-management/dto/responseDTO/project.response";
import { PmAvatar } from "@/features/project-management/components/ui/PmAvatar";
import { PmCard, PmKpiRow, PmPageHead } from "@/features/project-management/components/ui/PmCard";
import { PmField, PmSelect } from "@/features/project-management/components/ui/PmField";
import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import { PmPill } from "@/features/project-management/components/ui/PmPill";
import { PmSearchInput } from "@/features/project-management/components/ui/PmSearchInput";
import { PmTableFooter } from "@/features/project-management/components/ui/PmTableFooter";
import tableStyles from "@/features/project-management/components/ui/PmTable.module.scss";

import styles from "./ProjectListView.module.scss";

const PAGE_SIZE = 10;

type StatusFilter = "ALL" | ProjectResponseDTO["status"];

const STATUS_FILTER_OPTIONS: { value: StatusFilter; labelKey: string }[] = [
  { value: "ALL", labelKey: "allStatuses" },
  { value: "ACTIVE", labelKey: "statusActive" },
  { value: "ARCHIVED", labelKey: "statusArchived" },
];

const SYNC_LABEL_KEYS: Record<ProjectResponseDTO["sync_status"], string> = {
  NOT_STARTED: "syncNotStarted",
  SYNCING: "syncing",
  SUCCESS: "syncSuccess",
  PARTIAL: "syncPartial",
  FAILED: "syncFailed",
};

type ProjectListViewProps = {
  projects: ProjectResponseDTO[];
  loading: boolean;
};

/**
 * View "Dự án" (UC owner-projects) — chỉ XEM danh sách project PM đang phụ trách + chọn 1 project
 * để xem thành viên. Tạo project thuộc về Admin (TV4), không có action tạo ở trang này.
 */
export function ProjectListView({ projects, loading }: ProjectListViewProps) {
  const t = useTranslations("pmUi");
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("ALL");
  const activeCount = projects.filter((p) => p.status === "ACTIVE").length;

  const query = search.trim().toLowerCase();
  const filtered = projects.filter((p) => {
    if (query && !p.name.toLowerCase().includes(query) && !p.key.toLowerCase().includes(query)) {
      return false;
    }
    if (statusFilter !== "ALL" && p.status !== statusFilter) return false;
    return true;
  });

  // Reset về trang 1 khi search/filter/danh sách đổi — điều chỉnh state ngay trong render thay vì
  // effect (theo react.dev/learn/you-might-not-need-an-effect#adjusting-some-state-when-a-prop-changes).
  const [pageResetKey, setPageResetKey] = useState(`${search}|${statusFilter}|${projects.length}`);
  const nextPageResetKey = `${search}|${statusFilter}|${projects.length}`;
  if (pageResetKey !== nextPageResetKey) {
    setPageResetKey(nextPageResetKey);
    setPage(1);
  }

  const pageItems = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <section>
      <PmPageHead icon="folder" title={t("projectsTitle")} subtitle={t("projectsSubtitle")} />

      {!loading && projects.length > 0 && (
        <PmKpiRow
          items={[
            { label: t("statusActive"), value: activeCount, icon: "check2", variant: "success" },
            {
              label: t("statusArchived"),
              value: projects.length - activeCount,
              icon: "doc",
              variant: "violet",
            },
          ]}
        />
      )}

      <PmCard>
        <div className={styles.filterRow}>
          <PmField label={t("search")}>
            <PmSearchInput
              value={search}
              onChange={setSearch}
              placeholder={t("searchProjects")}
            />
          </PmField>
          <PmField label={t("filterByStatus")}>
            <PmSelect
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
            >
              {STATUS_FILTER_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {t(opt.labelKey)}
                </option>
              ))}
            </PmSelect>
          </PmField>
        </div>

        {loading ? (
          <p className={tableStyles.emptyNote}>{t("loadingProjects")}</p>
        ) : projects.length === 0 ? (
          <p className={tableStyles.emptyNote}>
            {t("noManagedProject")}
          </p>
        ) : filtered.length === 0 ? (
          <p className={tableStyles.emptyNote}>{t("noProjectsMatch")}</p>
        ) : (
          <>
            <div className={tableStyles.tableWrap}>
              <table className={tableStyles.table}>
                <thead>
                  <tr>
                    <th>{t("project")}</th>
                    <th>{t("syncStatus")}</th>
                    <th>{t("status")}</th>
                  </tr>
                </thead>
                <tbody>
                  {pageItems.map((p) => (
                    <tr key={p.project_id}>
                      <td data-label={t("project")}>
                        <div className={styles.projectCell}>
                          <PmAvatar seed={p.key} label={p.key} size="md" />
                          <div>
                            <div className={tableStyles.cellMain}>{p.name}</div>
                            <div className={tableStyles.cellSub}>{p.key}</div>
                          </div>
                        </div>
                      </td>
                      <td data-label={t("syncStatus")}>
                        <PmPill variant="neutral">{t(SYNC_LABEL_KEYS[p.sync_status])}</PmPill>
                      </td>
                      <td data-label={t("status")}>
                        <PmPill variant={p.status === "ACTIVE" ? "success" : "neutral"}>
                          {p.status === "ACTIVE" && <PmIcon name="check2" size={11} />}
                          {p.status === "ACTIVE" ? t("statusActive") : t("statusArchived")}
                        </PmPill>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className={styles.caption}>
              {t("projectStatusHelp")}
            </p>

            <PmTableFooter
              total={filtered.length}
              page={page}
              pageSize={PAGE_SIZE}
              onPageChange={setPage}
            />
          </>
        )}
      </PmCard>
    </section>
  );
}
