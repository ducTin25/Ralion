"use client";

import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useTranslations } from "next-intl";

import { MemberIcon } from "@/features/member-onboarding/components/MemberIcon";
import type { BlockerCategory } from "@/features/member-onboarding/types";

import styles from "./MemberPortal.module.scss";

const CATEGORIES: { value: BlockerCategory; labelKey: string; hintKey: string }[] = [
  {
    value: "ACCESS",
    labelKey: "categoryAccess",
    hintKey: "hintAccess",
  },
  {
    value: "SETUP",
    labelKey: "categorySetup",
    hintKey: "hintSetup",
  },
  {
    value: "DOCUMENT",
    labelKey: "categoryDocument",
    hintKey: "hintDocument",
  },
  {
    value: "TECHNICAL",
    labelKey: "categoryTechnical",
    hintKey: "hintTechnical",
  },
  {
    value: "OTHER",
    labelKey: "categoryOther",
    hintKey: "hintOther",
  },
];

// Khớp giới hạn phía backend (member_onboarding_service.py) — chặn sớm ở FE để người dùng thấy lỗi
// ngay khi chọn file, không phải đợi gửi lên server mới biết.
const MAX_ATTACHMENTS = 5;
const MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024;
const ACCEPTED_ATTACHMENT_TYPES = "image/*,video/*";

function isAllowedAttachment(file: File): boolean {
  return file.type.startsWith("image/") || file.type.startsWith("video/");
}

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

type BlockerModalProps = {
  taskTitle: string;
  submitting: boolean;
  requestError: string | null;
  onClose: () => void;
  onSubmit: (payload: {
    category: BlockerCategory;
    reason: string;
    attachments: File[];
  }) => Promise<boolean>;
};

export function BlockerModal({
  taskTitle,
  submitting,
  requestError,
  onClose,
  onSubmit,
}: BlockerModalProps) {
  const t = useTranslations("member.blockerModal");
  const [category, setCategory] = useState<BlockerCategory>("TECHNICAL");
  const [reason, setReason] = useState("");
  const [attachments, setAttachments] = useState<File[]>([]);
  const [validationError, setValidationError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const reasonRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const activeCategory = CATEGORIES.find((item) => item.value === category);

  function addFiles(files: FileList | null) {
    if (!files) return;
    const incoming = Array.from(files);
    const invalid = incoming.find((file) => !isAllowedAttachment(file));
    if (invalid) {
      setValidationError(t("invalidAttachment", { name: invalid.name }));
      return;
    }
    const oversized = incoming.find((file) => file.size > MAX_ATTACHMENT_BYTES);
    if (oversized) {
      setValidationError(
        t("attachmentTooLarge", {
          name: oversized.name,
          size: formatBytes(MAX_ATTACHMENT_BYTES),
        }),
      );
      return;
    }
    setAttachments((current) => {
      const merged = [...current, ...incoming];
      if (merged.length > MAX_ATTACHMENTS) {
        setValidationError(t("tooManyAttachments", { max: MAX_ATTACHMENTS }));
        return current;
      }
      setValidationError(null);
      return merged;
    });
  }

  function removeAttachment(index: number) {
    setAttachments((current) => current.filter((_, i) => i !== index));
  }

  useEffect(() => {
    const returnTarget = document.activeElement as HTMLElement | null;
    reasonRef.current?.focus();
    const handleEscape = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape" && !submitting) onClose();
    };
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("keydown", handleEscape);
      returnTarget?.focus();
    };
  }, [onClose, submitting]);

  const trapFocus = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "Tab" || !dialogRef.current) return;
    const controls = dialogRef.current.querySelectorAll<HTMLElement>(
      'button:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    if (controls.length === 0) return;
    const first = controls[0];
    const last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const normalizedReason = reason.trim();
    if (normalizedReason.length < 10) {
      setValidationError(t("reasonTooShort"));
      return;
    }
    setValidationError(null);
    if (await onSubmit({ category, reason: normalizedReason, attachments })) onClose();
  };

  return (
    <div className={styles.modalLayer} role="presentation">
      <div
        ref={dialogRef}
        className={styles.blockerModal}
        role="dialog"
        aria-modal="true"
        aria-labelledby="blocker-modal-title"
        onKeyDown={trapFocus}
      >
        <header>
          <div>
            <h2 id="blocker-modal-title">{t("title")}</h2>
            <p>{taskTitle}</p>
          </div>
          <button
            type="button"
            className={styles.iconButton}
            onClick={onClose}
            disabled={submitting}
            aria-label={t("close")}
          >
            <MemberIcon name="close" />
          </button>
        </header>

        <form onSubmit={submit}>
          <label className={styles.formField}>
            <span>{t("type")}</span>
            {/* aria-label tường minh: <label> này bọc cả dòng gợi ý bên dưới, nếu để tên suy ra từ
                label thì accessible name sẽ dính luôn text gợi ý và đổi theo từng loại đang chọn. */}
            <select
              aria-label={t("type")}
              value={category}
              onChange={(event) => setCategory(event.target.value as BlockerCategory)}
              disabled={submitting}
            >
              {CATEGORIES.map((item) => (
                <option key={item.value} value={item.value}>
                  {t(item.labelKey)}
                </option>
              ))}
            </select>
            {/* Gợi ý đổi theo loại đang chọn — "Other" cần mô tả rõ hơn vì PM không đoán được vấn đề
                từ tên nhóm chung chung. */}
            {activeCategory && (
              <small className={styles.categoryHint}>{t(activeCategory.hintKey)}</small>
            )}
          </label>
          <label className={styles.formField}>
            <span>{t("reason")}</span>
            <textarea
              ref={reasonRef}
              rows={5}
              maxLength={1000}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder={t("reasonPlaceholder")}
              disabled={submitting}
              aria-label={t("reason")}
              aria-describedby="blocker-reason-help"
            />
            <small id="blocker-reason-help">{t("reasonHelp", { count: reason.length })}</small>
          </label>

          <label className={styles.formField}>
            <span>{t("evidence")}</span>
            <button
              type="button"
              className={styles.attachButton}
              onClick={() => fileInputRef.current?.click()}
              disabled={submitting || attachments.length >= MAX_ATTACHMENTS}
            >
              <MemberIcon name="document" size={15} />
              {t("chooseEvidence")}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_ATTACHMENT_TYPES}
              multiple
              hidden
              disabled={submitting}
              onChange={(event) => {
                addFiles(event.target.files);
                event.target.value = ""; // cho chọn lại đúng file đó lần nữa nếu vừa gỡ ra
              }}
            />
            <small>
              {t("evidenceHelp", {
                max: MAX_ATTACHMENTS,
                size: formatBytes(MAX_ATTACHMENT_BYTES),
              })}
            </small>
            {attachments.length > 0 && (
              <ul className={styles.attachmentList}>
                {attachments.map((file, index) => (
                  <li key={`${file.name}-${index}`}>
                    <MemberIcon
                      name={file.type.startsWith("video/") ? "flag" : "document"}
                      size={14}
                    />
                    <span className={styles.attachmentName}>{file.name}</span>
                    <span className={styles.attachmentSize}>{formatBytes(file.size)}</span>
                    <button
                      type="button"
                      className={styles.attachmentRemove}
                      onClick={() => removeAttachment(index)}
                      disabled={submitting}
                      aria-label={t("removeAttachment", { name: file.name })}
                    >
                      <MemberIcon name="close" size={13} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </label>

          {(validationError || requestError) && (
            <p className={styles.formError} role="alert">
              {validationError ?? requestError}
            </p>
          )}
          <footer>
            <button
              type="button"
              className={styles.secondaryButton}
              onClick={onClose}
              disabled={submitting}
            >
              {t("cancel")}
            </button>
            <button type="submit" className={styles.dangerButton} disabled={submitting}>
              <MemberIcon name="flag" size={15} />
              {submitting ? t("sending") : t("submit")}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}
