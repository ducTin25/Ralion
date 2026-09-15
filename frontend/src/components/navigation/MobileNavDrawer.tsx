"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { useTranslations } from "next-intl";

type MobileNavDrawerProps = {
  children: ReactNode;
  label: string;
  onClose: () => void;
  open: boolean;
};

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function MobileNavDrawer({ children, label, onClose, open }: MobileNavDrawerProps) {
  const panelRef = useRef<HTMLElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const t = useTranslations("common");

  useEffect(() => {
    if (!open) return;
    previousFocusRef.current = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const panel = panelRef.current;
    const first = panel?.querySelector<HTMLElement>(FOCUSABLE);
    first?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !panel) return;
      const focusable = [...panel.querySelectorAll<HTMLElement>(FOCUSABLE)];
      if (focusable.length === 0) return;
      const firstElement = focusable[0];
      const lastElement = focusable.at(-1)!;
      if (event.shiftKey && document.activeElement === firstElement) {
        event.preventDefault();
        lastElement.focus();
      } else if (!event.shiftKey && document.activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      previousFocusRef.current?.focus();
    };
  }, [onClose, open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 lg:hidden">
      <button
        aria-label={t("closeMenu")}
        className="absolute inset-0 min-h-11 w-full bg-black/35"
        onClick={onClose}
        type="button"
      />
      <aside
        aria-label={label}
        aria-modal="true"
        className="relative flex h-[100dvh] w-[min(86vw,320px)] flex-col overflow-y-auto border-r border-border bg-surface p-4 shadow-2xl"
        ref={panelRef}
        role="dialog"
      >
        <div className="mb-3 flex items-center justify-between gap-3">
          <strong className="truncate text-sm">{label}</strong>
          <button
            aria-label={t("closeMenu")}
            className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-md border border-border text-xl"
            onClick={onClose}
            type="button"
          >
            ×
          </button>
        </div>
        {children}
      </aside>
    </div>
  );
}
