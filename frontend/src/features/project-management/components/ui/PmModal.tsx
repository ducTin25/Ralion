"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useTranslations } from "next-intl";

import { PmIcon } from "@/features/project-management/components/PmIconSprite";

import styles from "./PmModal.module.scss";

type PmModalTone = "default" | "primary" | "success" | "warning" | "danger";

const TONE_CLASS: Record<PmModalTone, string> = {
  default: "toneDefault",
  primary: "tonePrimary",
  success: "toneSuccess",
  warning: "toneWarning",
  danger: "toneDanger",
};

type PmModalProps = {
  title: string;
  icon?: Parameters<typeof PmIcon>[0]["name"];
  tone?: PmModalTone;
  size?: "default" | "wide" | "reader";
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
};

/**
 * Modal tự dựng — theo quy tắc mục 1.3 trong RALION_UI_DESIGN_GUIDE.md:
 * không dùng alert()/confirm()/prompt() gốc trình duyệt, mọi hành động ngắn dùng modal.
 * Đóng khi bấm overlay nền hoặc phím Esc. `icon`/`tone` tô màu badge đầu modal theo ngữ nghĩa
 * hành động (primary/success/danger...), `size="wide"` dùng cho form nhiều trường.
 */
export function PmModal({
  title,
  icon,
  tone = "default",
  size = "default",
  onClose,
  children,
  footer,
}: PmModalProps) {
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

  const portalTarget =
    typeof document === "undefined"
      ? null
      : document.querySelector<HTMLElement>(".ralion-workspace") ?? document.body;
  if (!portalTarget) return null;

  return createPortal(
    <div className={styles.overlay} onClick={onClose}>
      <div
        className={`${styles.modal} ${size === "wide" ? styles.wide : ""} ${size === "reader" ? styles.reader : ""}`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <div className={styles.head}>
          {icon && (
            <span className={`${styles.headIcon} ${styles[TONE_CLASS[tone]]}`}>
              <PmIcon name={icon} size={18} />
            </span>
          )}
          <h3 id={titleId} className={styles.headTitle}>
            {title}
          </h3>
          <button
            ref={closeRef}
            type="button"
            className={styles.closeBtn}
            onClick={onClose}
            aria-label={t("closeDialog")}
          >
            <PmIcon name="x" size={16} />
          </button>
        </div>
        <div className={styles.body}>{children}</div>
        {footer && <div className={styles.foot}>{footer}</div>}
      </div>
    </div>,
    portalTarget,
  );
}
