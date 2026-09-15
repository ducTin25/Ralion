"use client";

import { useEffect, useId, useRef, useState } from "react";

import type { ResponseLength, ResponseTone } from "@/features/auth/session";
import { MemberIcon } from "@/features/member-onboarding/components/MemberIcon";

import styles from "./AccountChatPreferences.module.scss";

/**
 * Preset do backend định nghĩa (`src/model/enums.py`). Frontend chỉ ánh xạ enum → nhãn; không
 * có ô nhập tự do nào, vì tone/length đi thẳng vào prompt và chỉ được phép là preset tĩnh
 * (PERSONALIZE_CHATBOT_SPEC.md §3).
 */
const LENGTH_LABELS: Record<ResponseLength, string> = {
  CONCISE: "Concise",
  STANDARD: "Standard",
  DETAILED: "Detailed",
};

const TONE_LABELS: Record<ResponseTone, string> = {
  NEUTRAL: "Neutral",
  GUIDE: "Guide",
  MENTOR: "Mentor",
  BUDDY: "Friendly",
};

export type ChatPreferencesBinding = {
  responseLength: ResponseLength;
  responseTone: ResponseTone;
  /** Trả về CurrentUser đã cập nhật; state phiên được đồng bộ ở `useSession`, không giữ bản
   * sao cục bộ trong component này. */
  onUpdate: (patch: {
    response_length?: ResponseLength;
    response_tone?: ResponseTone;
  }) => Promise<unknown>;
};

/**
 * Tuỳ chỉnh câu trả lời của chatbot — đặt ở khu account/profile của application shell
 * (UI_SPEC B.5), cố ý KHÔNG đặt cạnh ô soạn tin nhắn.
 *
 * Lý do là ranh giới kiến trúc, không phải thẩm mỹ: input của người dùng trong Chat không được
 * ảnh hưởng trực tiếp tới tone/length. Đặt control ở đây giữ ranh giới đó rõ ràng ngay trong
 * cấu trúc UI. Đây thuần là presentation preference — không đụng tới retrieval, evidence
 * selection, citation, relevance gating hay fallback.
 */
export function AccountChatPreferences({
  binding,
  compact = false,
}: {
  binding: ChatPreferencesBinding;
  compact?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const panelId = useId();
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const closeOnOutside = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", closeOnOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  async function update(patch: Parameters<ChatPreferencesBinding["onUpdate"]>[0]) {
    setPending(true);
    setError(null);
    try {
      await binding.onUpdate(patch);
    } catch {
      setError("Couldn’t save your preferences. Try again.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className={`${styles.root} ${compact ? styles.composerRoot : ""}`} ref={rootRef}>
      <button
        type="button"
        className={styles.trigger}
        aria-expanded={open}
        aria-controls={panelId}
        aria-label="Response preferences"
        onClick={() => setOpen((value) => !value)}
      >
        {!compact && <MemberIcon name="settings" size={15} />}
        <span className={styles.triggerLabel}>
          {compact ? LENGTH_LABELS[binding.responseLength] : "Response style"}
        </span>
        <span className={`${styles.chevron} ${open ? styles.chevronOpen : ""}`} aria-hidden="true">
          <MemberIcon name="chevronDown" size={14} />
        </span>
      </button>

      {open && (
        <div className={styles.panel} id={panelId}>
          <p className={styles.panelTitle}>Response style</p>

          <label className={styles.field}>
            <span>Length</span>
            <select
              value={binding.responseLength}
              disabled={pending}
              onChange={(event) =>
                void update({ response_length: event.target.value as ResponseLength })
              }
            >
              {Object.entries(LENGTH_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>

          <label className={styles.field}>
            <span>Tone</span>
            <select
              value={binding.responseTone}
              disabled={pending}
              onChange={(event) =>
                void update({ response_tone: event.target.value as ResponseTone })
              }
            >
              {Object.entries(TONE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>

          {error ? (
            <p className={styles.errorCaption} role="alert">
              {error}
            </p>
          ) : (
            <p className={styles.caption} role="status">
              {pending ? "Saving…" : "Applies to your next Ralion Chat question."}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
