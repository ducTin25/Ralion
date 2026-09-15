"use client";

import { useLocale, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";

import { usePathname, useRouter } from "@/i18n/navigation";
import type { Locale } from "@/i18n/routing";
import styles from "./LanguageSwitcher.module.css";

type LanguageSwitcherProps = {
  className?: string;
  compact?: boolean;
};

function FlagIcon({ locale }: { locale: Locale }) {
  if (locale === "vi") {
    return (
      <svg aria-hidden="true" className={styles.flag} viewBox="0 0 30 20">
        <rect width="30" height="20" rx="2" fill="#da251d" />
        <path
          d="m15 3.3 1.76 5.42h5.7l-4.61 3.35 1.76 5.42L15 14.14l-4.61 3.35 1.76-5.42-4.61-3.35h5.7L15 3.3Z"
          fill="#ff0"
        />
      </svg>
    );
  }

  return (
    <svg aria-hidden="true" className={styles.flag} viewBox="0 0 30 20">
      <defs>
        <clipPath id="uk-flag-clip">
          <rect width="30" height="20" rx="2" />
        </clipPath>
      </defs>
      <g clipPath="url(#uk-flag-clip)">
        <rect width="30" height="20" fill="#012169" />
        <path d="M0 0 30 20M30 0 0 20" stroke="#fff" strokeWidth="4" />
        <path d="M0 0 30 20M30 0 0 20" stroke="#c8102e" strokeWidth="2" />
        <path d="M15 0v20M0 10h30" stroke="#fff" strokeWidth="6" />
        <path d="M15 0v20M0 10h30" stroke="#c8102e" strokeWidth="3.4" />
      </g>
    </svg>
  );
}

export function LanguageSwitcher({ className = "" }: LanguageSwitcherProps) {
  const locale = useLocale() as Locale;
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const t = useTranslations("common");

  const changeLocale = (nextLocale: Locale) => {
    if (nextLocale === locale) return;
    const query = searchParams.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { locale: nextLocale });
  };

  const currentLabel = locale === "vi" ? t("vietnamese") : t("english");

  return (
    <details className={`${styles.switcher} ${className}`}>
      <summary aria-label={`${t("language")}: ${currentLabel}`} className={styles.trigger}>
        <FlagIcon locale={locale} />
        <span className={styles.current}>{locale === "vi" ? "Việt Nam" : "English"}</span>
        <svg aria-hidden="true" className={styles.chevron} viewBox="0 0 16 16">
          <path
            d="m4 6 4 4 4-4"
            fill="none"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="1.8"
          />
        </svg>
      </summary>
      <div aria-label={t("language")} className={styles.menu} role="menu">
        {(["vi", "en"] as const).map((option) => (
          <button
            aria-current={locale === option ? "true" : undefined}
            className={styles.option}
            key={option}
            onClick={(event) => {
              changeLocale(option);
              event.currentTarget.closest("details")?.removeAttribute("open");
            }}
            role="menuitem"
            type="button"
          >
            <FlagIcon locale={option} />
            <span>{option === "vi" ? "Việt Nam" : "English"}</span>
            {locale === option && (
              <span aria-hidden="true" className={styles.check}>
                ✓
              </span>
            )}
          </button>
        ))}
      </div>
    </details>
  );
}
