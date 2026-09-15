import type { ReactNode } from "react";

import styles from "./PmPill.module.scss";

type PmPillProps = {
  variant?: "neutral" | "progress" | "success" | "warning" | "critical";
  children: ReactNode;
};

/** Pill = trạng thái nghiệp vụ (màu semantic). Dùng PmTag cho nhãn phân loại trung tính. */
export function PmPill({ variant = "neutral", children }: PmPillProps) {
  return <span className={`${styles.pill} ${styles[variant]}`}>{children}</span>;
}

export function PmTag({ children }: { children: ReactNode }) {
  return <span className={styles.tag}>{children}</span>;
}
