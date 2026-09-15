"use client";

import { useTranslations } from "next-intl";

import { PmIcon } from "@/features/project-management/components/PmIconSprite";

import styles from "./PmSearchInput.module.scss";

type PmSearchInputProps = {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
};

/** Ô tìm kiếm dùng chung — đặt ngang hàng với bộ lọc trạng thái trên mỗi trang danh sách,
 * thay vì tách rời ở topbar như trước. */
export function PmSearchInput({ value, onChange, placeholder }: PmSearchInputProps) {
  const t = useTranslations("common");

  return (
    <div className={styles.box}>
      <PmIcon name="search" size={14} className={styles.icon} />
      <input
        type="text"
        className={styles.input}
        placeholder={placeholder ?? t("searchPlaceholder")}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
