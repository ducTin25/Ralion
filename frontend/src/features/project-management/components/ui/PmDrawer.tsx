"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";
import { useTranslations } from "next-intl";

import { PmIcon } from "@/features/project-management/components/PmIconSprite";

import styles from "./PmDrawer.module.scss";

type PmDrawerProps = {
  eyebrow?: ReactNode;
  title: ReactNode;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  variant?: "drawer" | "workspace" | "page";
};

/** Drawer trượt từ phải (khác PmModal — dùng cho nội dung dài, có ngữ cảnh cha vẫn cần thấy
 * mờ phía sau, ví dụ sửa danh sách task trong 1 nhóm category). Đóng khi bấm overlay hoặc Esc. */
export function PmDrawer({
  eyebrow,
  title,
  onClose,
  children,
  footer,
  variant = "drawer",
}: PmDrawerProps) {
  const t = useTranslations("common");
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    previousFocus.current = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    return () => previousFocus.current?.focus();
  }, []);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const isPage = variant === "page";

  return (
    <div
      className={isPage ? styles.pageRoot : styles.overlay}
      onClick={isPage ? undefined : onClose}
    >
      <div
        className={`${styles.drawer} ${variant === "workspace" ? styles.workspace : ""} ${isPage ? styles.page : ""}`}
        onClick={(e) => e.stopPropagation()}
        role={isPage ? "region" : "dialog"}
        aria-modal={isPage ? undefined : "true"}
        aria-labelledby={titleId}
      >
        <div className={styles.head}>
          <div>
            {eyebrow && <div className={styles.eyebrow}>{eyebrow}</div>}
            <h3 id={titleId}>{title}</h3>
          </div>
          <button
            ref={closeRef}
            type="button"
            className={styles.closeBtn}
            onClick={onClose}
            aria-label={t("close")}
          >
            <PmIcon name={isPage ? "arrow" : "x"} size={16} />
          </button>
        </div>
        <div className={styles.body}>{children}</div>
        {footer && <div className={styles.foot}>{footer}</div>}
      </div>
    </div>
  );
}
