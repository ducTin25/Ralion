import type { ReactNode } from "react";

import { PmIcon } from "@/features/project-management/components/PmIconSprite";

import styles from "./PmCard.module.scss";

type PmCardProps = {
  padded?: boolean;
  className?: string;
  children: ReactNode;
};

export function PmCard({ padded = true, className, children }: PmCardProps) {
  const classes = [styles.card, padded && styles.pad, className].filter(Boolean).join(" ");
  return <div className={classes}>{children}</div>;
}

type PmPageHeadProps = {
  title: string;
  icon?: Parameters<typeof PmIcon>[0]["name"];
  /** Only for state a user cannot read off the content below (e.g. which member a plan is for). */
  subtitle?: ReactNode;
  action?: ReactNode;
};

export function PmPageHead({ title, icon, subtitle, action }: PmPageHeadProps) {
  return (
    <div className={styles.pageHead}>
      <div className={styles.pageHeadInner}>
        <div className={styles.pageTitleBlock}>
          {icon && (
            <span className={styles.pageTitleIcon}>
              <PmIcon name={icon} size={20} />
            </span>
          )}
          <div>
            <h1>{title}</h1>
            {subtitle && <p className={styles.pageSub}>{subtitle}</p>}
          </div>
        </div>
        {action}
      </div>
    </div>
  );
}

export function PmSectionTitle({ children, hint }: { children: ReactNode; hint?: ReactNode }) {
  return (
    <div className={styles.sectionTitle}>
      <span>{children}</span>
      {hint && <span className={styles.sectionHint}>{hint}</span>}
    </div>
  );
}

type PmKpiVariant = "accent" | "success" | "warning" | "violet";

type PmKpiItem = {
  label: string;
  value: string | number;
  icon: Parameters<typeof PmIcon>[0]["name"];
  variant?: PmKpiVariant;
};

const KPI_VARIANT_CLASS: Record<PmKpiVariant, string> = {
  accent: "kpiAccent",
  success: "kpiSuccess",
  warning: "kpiWarning",
  violet: "kpiViolet",
};

/** Hàng KPI đầu trang — "surface the summary before the detail" cho màn hình dạng dashboard.
 * Mỗi item 1 màu riêng (variant) để dễ phân biệt bằng mắt, không dùng chung 1 màu cho tất cả. */
export function PmKpiRow({ items }: { items: PmKpiItem[] }) {
  return (
    <div className={styles.kpiRow}>
      {items.map((item) => {
        const variantClass = styles[KPI_VARIANT_CLASS[item.variant ?? "accent"]];
        return (
          <div key={item.label} className={`${styles.kpiCard} ${variantClass}`}>
            <div className={styles.kpi}>
              <div className={styles.kpiTop}>
                <span className={styles.kpiIcon}>
                  <PmIcon name={item.icon} size={15} />
                </span>
                <span className={styles.kpiLabel}>{item.label}</span>
              </div>
              <span className={styles.kpiValue}>{item.value}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
