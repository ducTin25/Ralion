"use client";

import type { ReactNode } from "react";
import { useTranslations } from "next-intl";

import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import { PmButton } from "@/features/project-management/components/ui/PmButton";
import { PmModal } from "@/features/project-management/components/ui/PmModal";

import styles from "./PmConfirmModal.module.scss";

type PmConfirmTone = "primary" | "success" | "danger";

type PmConfirmModalProps = {
  icon: Parameters<typeof PmIcon>[0]["name"];
  tone: PmConfirmTone;
  title: string;
  description: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  loading?: boolean;
  onConfirm: () => void;
  onClose: () => void;
};

/** Modal xác nhận dùng chung cho các hành động đổi trạng thái quan trọng (duyệt version, chuyển
 * version xem, xoá task...) — luôn giải thích rõ hậu quả trước khi cho bấm xác nhận, thay vì
 * chuyển/đổi ngay lập tức không báo trước. */
export function PmConfirmModal({
  icon,
  tone,
  title,
  description,
  confirmLabel,
  cancelLabel,
  loading = false,
  onConfirm,
  onClose,
}: PmConfirmModalProps) {
  const t = useTranslations("common");

  return (
    <PmModal
      title={title}
      icon={icon}
      tone={tone}
      onClose={onClose}
      footer={
        <>
          <PmButton onClick={onClose} disabled={loading}>
            {cancelLabel ?? t("cancel")}
          </PmButton>
          <PmButton
            variant={tone === "danger" ? "danger" : "primary"}
            onClick={onConfirm}
            disabled={loading}
          >
            {loading ? t("processing") : confirmLabel}
          </PmButton>
        </>
      }
    >
      <div className={styles.description}>{description}</div>
    </PmModal>
  );
}
