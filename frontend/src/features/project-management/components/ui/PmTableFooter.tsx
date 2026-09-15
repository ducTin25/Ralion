"use client";

import { useTranslations } from "next-intl";

import { PmIcon } from "@/features/project-management/components/PmIconSprite";

import styles from "./PmTableFooter.module.scss";

type PmTableFooterProps = {
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
};

/** Footer phân trang dùng chung cho bảng Dự án / Thành viên — page size cố định (Phase 1). */
export function PmTableFooter({ total, page, pageSize, onPageChange }: PmTableFooterProps) {
  const t = useTranslations("pmUi");

  if (total === 0) return null;

  const lastPage = Math.max(1, Math.ceil(total / pageSize));
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  return (
    <div className={styles.footer}>
      <span className={styles.summary}>
        {t("showing")} <b>{start}–{end}</b> {t("ofResults", { total })}
      </span>
      <div className={styles.nav}>
        <button
          type="button"
          className={styles.navBtn}
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          <PmIcon name="arrow" size={13} className={styles.iconPrev} />
          {t("previous")}
        </button>
        <button
          type="button"
          className={styles.navBtn}
          disabled={page >= lastPage}
          onClick={() => onPageChange(page + 1)}
        >
          {t("next")}
          <PmIcon name="arrow" size={13} />
        </button>
      </div>
    </div>
  );
}
