"use client";

import { FormEvent, useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import {
  ArrowRightIcon,
  BookIcon,
  KeyIcon,
  LinkExternalIcon,
  MailIcon,
  PlayIcon,
  QuestionIcon,
} from "@primer/octicons-react";

import styles from "./page.module.css";
import { LanguageSwitcher } from "@/components/i18n/LanguageSwitcher";
import { RalionBrand } from "@/components/brand/RalionBrand";
import { resolvePostLoginPath } from "@/features/auth/routing";
import { authApi } from "@/features/auth/session";
import { Link, useRouter } from "@/i18n/navigation";

const TEST_ACCOUNT_GUIDE_URL =
  "https://docs.google.com/document/d/1dEuJ5dLvXXm8esvwbvrxKgABAFuTjTYW30x1NfNYx1s/edit?tab=t.0";
const RALION_DEMO_VIDEO_URL =
  "https://drive.google.com/file/d/1HBQRfdPjs04os6Jf5cpsWOEExv6TkDZe/preview";

export default function LoginPage() {
  const t = useTranslations("login");
  const landing = useTranslations("landing");
  const common = useTranslations("common");
  const locale = useLocale();
  const copy =
    locale === "vi"
      ? {
          eyebrow: "Onboarding thông minh theo dự án",
          welcomeTitle: "Hiểu dự án nhanh hơn. Bắt đầu tự tin hơn.",
          welcomeDescription:
            "Ralion kết nối tài liệu, codebase và quy ước đội ngũ thành một hành trình onboarding rõ ràng cho từng kỹ sư.",
          benefits: [
            "Tri thức dự án tập trung và có nguồn kiểm chứng",
            "Kế hoạch onboarding phù hợp với từng vai trò",
            "Trợ lý AI hỗ trợ xuyên suốt quá trình làm việc",
          ],
          watchDemo: "Xem video Ralion hoạt động",
          watchDemoHint: "Video demo sản phẩm · xem ngay tại đây",
          formEyebrow: "Chào mừng trở lại",
          formDescription: "Đăng nhập để tiếp tục hành trình onboarding của bạn.",
          videoEyebrow: "Ralion product tour",
          videoTitle: "Ralion hoạt động như thế nào?",
          videoDescription:
            "Video được phát với chất lượng gốc từ Google Drive. Bạn có thể bật toàn màn hình để xem rõ hơn.",
        }
      : {
          eyebrow: "Project-aware intelligent onboarding",
          welcomeTitle: "Understand faster. Start with confidence.",
          welcomeDescription:
            "Ralion connects documents, codebases, and team conventions into a clear onboarding journey for every engineer.",
          benefits: [
            "Centralized, source-grounded project knowledge",
            "Onboarding plans tailored to each role",
            "AI assistance throughout the working journey",
          ],
          watchDemo: "Watch Ralion in action",
          watchDemoHint: "Product demo · watch without leaving this page",
          formEyebrow: "Welcome back",
          formDescription: "Sign in to continue your onboarding journey.",
          videoEyebrow: "Ralion product tour",
          videoTitle: "How does Ralion work?",
          videoDescription:
            "The video is streamed in its original quality from Google Drive. Use fullscreen for the clearest view.",
        };
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [videoOpen, setVideoOpen] = useState(false);

  useEffect(() => {
    if (!videoOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setVideoOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [videoOpen]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);

    // Read directly from the submitted form so password-manager autofill is respected.
    const form = new FormData(event.currentTarget);
    const emailValue = String(form.get("email") ?? "").trim();
    const passwordValue = String(form.get("password") ?? "");

    if (!/^\S+@\S+\.\S+$/.test(emailValue)) {
      setError(t("invalidEmail"));
      return;
    }
    if (passwordValue.length < 8) {
      setError(t("shortPassword"));
      return;
    }

    setLoading(true);
    try {
      const result = await authApi.login({ email: emailValue, password: passwordValue });
      window.localStorage.setItem("ralion-demo-user-id", String(result.user_id));

      // A newly created or admin-reset account is authenticated, but its current
      // password is temporary. Route it to the only allowed workflow before loading
      // profile data or resolving a role-based landing page.
      if (result.outcome === "MUST_CHANGE_PASSWORD") {
        router.replace("/change-password?required=1");
        return;
      }

      const sessionUser = await authApi.me().catch(() => {
        throw new Error(t("sessionError"));
      });

      if (result.outcome === "NO_ACTIVE_PROJECT") {
        router.replace("/select-project");
        return;
      }
      // Project-scoped users always land on Select Project, even with exactly one
      // membership — the portal is only opened once they explicitly pick it there.
      const requested = new URLSearchParams(window.location.search).get("next");
      router.replace(resolvePostLoginPath(sessionUser, requested));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("unknownError"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.loginPage}>
      <header className={styles.header}>
        <nav aria-label={landing("navLabel")} className={styles.nav}>
          <span className={styles.headerBrand}>
            <RalionBrand href="/#hero" size={24} />
          </span>
          <div className={styles.navLinks}>
            <Link href="/">{landing("whatWeDo")}</Link>
            <Link href="/#how-it-works">{landing("howItWorks")}</Link>
            <Link href="/#roles">{landing("roles")}</Link>
          </div>
          <LanguageSwitcher className={styles.languageSwitcher} compact />
        </nav>
      </header>

      <main className={styles.loginMain}>
        <section className={styles.storyPanel} aria-labelledby="ralion-intro-title">
          <div aria-hidden="true" className={styles.storyGlow} />
          <div className={styles.storyContent}>
            <span className={styles.eyebrow}>{copy.eyebrow}</span>
            <h1 id="ralion-intro-title">{copy.welcomeTitle}</h1>
            <p>{copy.welcomeDescription}</p>
            <ul className={styles.benefits}>
              <li>
                <span>✓</span>
                {copy.benefits[0]}
              </li>
              <li>
                <span>✓</span>
                {copy.benefits[1]}
              </li>
              <li>
                <span>✓</span>
                {copy.benefits[2]}
              </li>
            </ul>
            <button className={styles.videoButton} onClick={() => setVideoOpen(true)} type="button">
              <span className={styles.videoArtwork} aria-hidden="true">
                <span className={styles.videoWindowBar}>
                  <i />
                  <i />
                  <i />
                </span>
                <span className={styles.videoMockContent}>
                  <i />
                  <i />
                  <i />
                  <i />
                </span>
                <span className={styles.playIcon}>
                  <PlayIcon size={20} />
                </span>
              </span>
              <span className={styles.videoMeta}>
                <span>
                  <strong>{copy.watchDemo}</strong>
                  <small>{copy.watchDemoHint}</small>
                </span>
                <ArrowRightIcon className={styles.arrowIcon} size={20} />
              </span>
            </button>
          </div>
        </section>

        <section aria-labelledby="login-title" className={styles.formContent}>
          <div className={styles.formHeading}>
            <span className={styles.mobileBrand}>
              <RalionBrand size={26} />
            </span>
            <div className={styles.formTitleRow}>
              <span className={styles.formTitleIcon} aria-hidden="true">
                <KeyIcon size={18} />
              </span>
              <h2 id="login-title">{t("title")}</h2>
            </div>
            <span>{copy.formDescription}</span>
          </div>
          <div className={styles.card}>
            {error && (
              <div className={styles.error} role="alert">
                <span aria-hidden="true">!</span>
                <span>{error}</span>
              </div>
            )}
            <form className={styles.form} onSubmit={submit}>
              <label className={styles.field}>
                <span>{t("email")}</span>
                <span className={styles.inputControl}>
                  <MailIcon aria-hidden="true" size={17} />
                  <input
                    autoComplete="username"
                    className={styles.input}
                    disabled={loading}
                    name="email"
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="name@company.com"
                    required
                    suppressHydrationWarning
                    type="email"
                    value={email}
                  />
                </span>
              </label>
              <label className={styles.field}>
                <span>{t("password")}</span>
                <span className={styles.inputControl}>
                  <KeyIcon aria-hidden="true" size={17} />
                  <input
                    autoComplete="current-password"
                    className={styles.input}
                    disabled={loading}
                    minLength={8}
                    name="password"
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="••••••••"
                    required
                    suppressHydrationWarning
                    type="password"
                    value={password}
                  />
                </span>
              </label>
              <button
                className={styles.submit}
                disabled={loading}
                suppressHydrationWarning
                type="submit"
              >
                {loading && <i className={styles.spinner} />}
                {loading ? t("submitting") : t("submit")}
                {!loading && <ArrowRightIcon size={17} />}
              </button>
            </form>
            <aside aria-labelledby="test-account-guide-title" className={styles.demoGuide}>
              <div className={styles.demoGuideCopy}>
                <span aria-hidden="true" className={styles.demoGuideIcon}>
                  <QuestionIcon size={15} />
                </span>
                <div>
                  <strong id="test-account-guide-title">{t("demoTitle")}</strong>
                  <p>{t("demoDescription")}</p>
                </div>
              </div>
              <a
                aria-label={t("demoLinkLabel")}
                className={styles.demoGuideLink}
                href={TEST_ACCOUNT_GUIDE_URL}
                rel="noreferrer"
                target="_blank"
              >
                <span>{t("demoLink")}</span>
                <span className={styles.guideLinkIcons} aria-hidden="true">
                  <BookIcon size={15} />
                  <LinkExternalIcon size={14} />
                </span>
              </a>
            </aside>
          </div>
          <p className={styles.legal}>{t("legal")}</p>
        </section>
      </main>

      {videoOpen && (
        <div
          className={styles.videoOverlay}
          role="presentation"
          onMouseDown={() => setVideoOpen(false)}
        >
          <section
            aria-labelledby="demo-video-title"
            aria-modal="true"
            className={styles.videoModal}
            onMouseDown={(event) => event.stopPropagation()}
            role="dialog"
          >
            <header>
              <div>
                <span>{copy.videoEyebrow}</span>
                <h2 id="demo-video-title">{copy.videoTitle}</h2>
              </div>
              <button
                aria-label={common("close")}
                onClick={() => setVideoOpen(false)}
                type="button"
              >
                ×
              </button>
            </header>
            <div className={styles.videoFrame}>
              <iframe
                allow="autoplay; encrypted-media; picture-in-picture"
                allowFullScreen
                loading="eager"
                src={RALION_DEMO_VIDEO_URL}
                title={copy.videoTitle}
              />
            </div>
            <p>{copy.videoDescription}</p>
          </section>
        </div>
      )}
    </div>
  );
}
