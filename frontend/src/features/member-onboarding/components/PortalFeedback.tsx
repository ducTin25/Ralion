"use client";

import { useTranslations } from "next-intl";

import { MemberIcon } from "@/features/member-onboarding/components/MemberIcon";

import styles from "./MemberPortal.module.scss";

export function PortalError({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const t = useTranslations("member.portal");
  return (
    <div className={styles.errorBanner} role="alert">
      <span>!</span>
      <p>{message}</p>
      {onRetry && (
        <button type="button" className={styles.retryButton} onClick={onRetry}>
          <MemberIcon name="refresh" size={14} /> {t("retry")}
        </button>
      )}
    </div>
  );
}

export function ContentLoading({ label }: { label: string }) {
  return (
    <div className={styles.contentLoading}>
      <span className={styles.spinner} />
      <p>{label}</p>
    </div>
  );
}

export function LoadingScreen() {
  const t = useTranslations("member.portal");
  return (
    <main className={styles.loadingPage}>
      <span className={styles.spinner} />
      <p>{t("loadingPortal")}</p>
    </main>
  );
}
