"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { MarkdownView } from "@/components/MarkdownView";
import { LanguageSwitcher } from "@/components/i18n/LanguageSwitcher";
import { MobileNavDrawer } from "@/components/navigation/MobileNavDrawer";
import { useSession } from "@/features/auth/session";
import type { CurrentUser } from "@/features/auth/session";
import {
  acknowledgePolicy,
  getMemberPolicyContent,
  listPendingPolicies,
} from "@/features/member-onboarding/api";
import { MemberIcon } from "@/features/member-onboarding/components/MemberIcon";
import { MemberSidebar } from "@/features/member-onboarding/components/MemberSidebar";
import { usePersistentTheme } from "@/features/member-onboarding/hooks/usePersistentTheme";
import type { MemberPolicyContent, PendingPolicy } from "@/features/member-onboarding/types";
import { Link, useRouter } from "@/i18n/navigation";
import { ApiError } from "@/lib/api";

import styles from "./MemberPortal.module.scss";

const CATEGORY_LABEL_KEYS = {
  COMPANY_POLICY: "categoryCompanyPolicy",
  HR_POLICY: "categoryHr",
  SECURITY_POLICY: "categorySecurity",
  BENEFIT: "categoryBenefits",
  WORKING_RULE: "categoryWorkingRules",
  GENERAL: "categoryGeneral",
} as const;

const formatDate = (value: string | null, locale: string) =>
  value
    ? new Intl.DateTimeFormat(locale === "vi" ? "vi-VN" : "en-GB", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      }).format(new Date(value))
    : null;

function errorMessage(caught: unknown, fallback: string) {
  if (caught instanceof ApiError) return caught.message;
  return caught instanceof Error ? caught.message : fallback;
}

/**
 * Nơi kỹ sư ĐỌC chính sách công ty và xác nhận đã đọc.
 *
 * Trước đây màn này chỉ có tiêu đề + 1 link sang Chat, tức là bắt người ta tự đoán ra câu
 * hỏi thì mới gặp được nội dung — đúng cái vấn đề mà `policy_acknowledgement_service` được
 * viết ra để giải quyết ("kho chỉ-ghi"). Ba endpoint `/api/v1/me/policies*` đã có sẵn từ
 * backend nhưng không có chỗ nào gọi, nên HR bật "bắt buộc xác nhận" mà tỷ lệ xác nhận
 * không bao giờ nhúc nhích.
 *
 * Danh sách chỉ gồm chính sách CÒN PHẢI xác nhận: đó là toàn bộ những gì
 * `GET /me/policies` trả về. Xác nhận xong thì mục đó biến mất khỏi danh sách — hành vi
 * của backend, không phải lựa chọn của UI.
 */
export function MemberPolicyScreen({
  embedded = false,
  embeddedUser,
  projectId,
}: {
  embedded?: boolean;
  embeddedUser?: CurrentUser;
  projectId?: number;
} = {}) {
  const t = useTranslations("member.policy");
  const memberT = useTranslations("member");
  const common = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();
  const { theme, toggleTheme } = usePersistentTheme();
  const { user, loading, error, signOut } = useSession();
  const effectiveUser = user ?? embeddedUser ?? null;
  const membership = effectiveUser?.memberships.find(
    (item) =>
      item.project_role === "ENGINEER" &&
      item.status === "ACTIVE" &&
      item.project_status === "ACTIVE" &&
      (projectId === undefined || item.project_id === projectId),
  );

  const [items, setItems] = useState<PendingPolicy[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [content, setContent] = useState<MemberPolicyContent | null>(null);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [contentError, setContentError] = useState<string | null>(null);
  const [acking, setAcking] = useState(false);
  const [ackError, setAckError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  // Bấm "Try again" ở khối nội dung: selectedId không đổi nên cần một token để chạy lại effect.
  const [reloadContentToken, setReloadContentToken] = useState(0);
  // Mở khoá nút xác nhận khi người đọc đã cuộn tới cuối `.content` — cùng lý do và cùng
  // ngưỡng đã dùng ở PolicyAcknowledgementScreen: xác nhận được ngay từ dòng đầu thì số liệu
  // của HR chỉ đo được số lần bấm chuột.
  const [reachedEnd, setReachedEnd] = useState(false);
  const contentRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      if (error?.status === 401) router.replace("/login?next=/documents");
      return;
    }
    if (user.system_role !== null || !membership) router.replace("/select-project");
  }, [error, loading, membership, router, user]);

  const authorised =
    (!loading || Boolean(embeddedUser)) &&
    Boolean(effectiveUser) &&
    effectiveUser?.system_role === null &&
    Boolean(membership);

  const loadList = useCallback(
    async (signal?: AbortSignal) => {
      setListLoading(true);
      setListError(null);
      try {
        const result = await listPendingPolicies(signal);
        if (signal?.aborted) return;
        setItems(result.items);
        setSelectedId((current) =>
          result.items.some((item) => item.document_id === current)
            ? current
            : (result.items[0]?.document_id ?? null),
        );
      } catch (caught) {
        if (signal?.aborted) return;
        setListError(errorMessage(caught, t("listLoadError")));
      } finally {
        if (!signal?.aborted) setListLoading(false);
      }
    },
    [t],
  );

  // Hoãn sang macrotask để setState không chạy đồng bộ trong thân effect — cùng cách
  // AdminConsoleScreen/PolicyCoveragePanel đang làm cho lần nạp đầu tiên.
  useEffect(() => {
    if (!authorised) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => void loadList(controller.signal), 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [authorised, loadList]);

  // Nội dung tải theo tài liệu đang chọn. Huỷ request cũ khi đổi lựa chọn để không bị
  // response đến muộn ghi đè lên tài liệu người dùng vừa mở.
  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setContent(null);
      setContentError(null);
      setAckError(null);
      setReachedEnd(false);
      if (selectedId === null) return;
      getMemberPolicyContent(selectedId, controller.signal)
        .then((result) => {
          if (!controller.signal.aborted) setContent(result);
        })
        .catch((caught) => {
          if (controller.signal.aborted) return;
          setContentError(errorMessage(caught, t("contentLoadError")));
        });
    }, 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [selectedId, reloadContentToken, t]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 4000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  // Nội dung ngắn hơn khung nhìn không cần cuộn — mở khoá luôn, không bắt cuộn để "cuộn".
  useEffect(() => {
    const node = contentRef.current;
    if (node && node.scrollHeight <= node.clientHeight) setReachedEnd(true);
  }, [content]);

  const handleContentScroll = () => {
    const node = contentRef.current;
    if (!node) return;
    if (node.scrollTop + node.clientHeight >= node.scrollHeight - 24) setReachedEnd(true);
  };

  if (!authorised || !effectiveUser || !membership) return null;

  const checklistHref = `/user?project=${membership.project_id}`;
  const blockersHref = `/user?project=${membership.project_id}&view=blockers`;
  const conventionsHref = `/user?project=${membership.project_id}&view=conventions`;
  const selected = items.find((item) => item.document_id === selectedId) ?? null;
  const effectiveDate = content ? formatDate(content.effective_date, locale) : null;

  const confirmRead = async () => {
    if (!selected) return;
    setAcking(true);
    setAckError(null);
    try {
      await acknowledgePolicy(selected.document_id);
      setNotice(t("acknowledged", { title: selected.title }));
      const remaining = items.filter((item) => item.document_id !== selected.document_id);
      setItems(remaining);
      setSelectedId(remaining[0]?.document_id ?? null);
    } catch (caught) {
      setAckError(errorMessage(caught, t("acknowledgementError")));
    } finally {
      setAcking(false);
    }
  };

  return (
    <div
      className={`${embedded ? styles.embeddedPolicy : styles.portal} ralion-workspace`}
      data-theme={theme}
    >
      {!embedded && (
        <MemberSidebar
          member={{
            user_id: effectiveUser.user_id,
            email: effectiveUser.email,
            display_name: effectiveUser.display_name,
          }}
          activeView="policy"
          checklistHref={checklistHref}
          blockersHref={blockersHref}
          conventionsHref={conventionsHref}
          chatHref={`/chat?project=${membership.project_id}`}
          policyHref="/documents"
          blockerCount={0}
          switchProjectHref="/select-project"
          onSignOut={() => void signOut()}
        />
      )}

      {!embedded && (
        <MobileNavDrawer
          label={memberT("navigation")}
          onClose={() => setMobileNavOpen(false)}
          open={mobileNavOpen}
        >
          <nav className={styles.mobileDrawerNav}>
            <Link href={checklistHref} onClick={() => setMobileNavOpen(false)}>
              {memberT("checklist")}
            </Link>
            <Link
              href={`/chat?project=${membership.project_id}`}
              onClick={() => setMobileNavOpen(false)}
            >
              {memberT("chat")}
            </Link>
            <Link href="/documents" aria-current="page" onClick={() => setMobileNavOpen(false)}>
              {t("title")}
            </Link>
            <Link href={conventionsHref} onClick={() => setMobileNavOpen(false)}>
              {memberT("conventions")}
            </Link>
            <Link href={blockersHref} onClick={() => setMobileNavOpen(false)}>
              {memberT("blockers")}
            </Link>
            <Link href="/select-project" onClick={() => setMobileNavOpen(false)}>
              {memberT("switchProject")}
            </Link>
          </nav>
          <div className={styles.mobileDrawerFoot}>
            <LanguageSwitcher />
            <button type="button" onClick={toggleTheme}>
              {memberT("theme")}
            </button>
            <button
              type="button"
              onClick={() => {
                setMobileNavOpen(false);
                void signOut();
              }}
            >
              {common("logout")}
            </button>
          </div>
        </MobileNavDrawer>
      )}

      <div className={styles.main}>
        {!embedded && (
          <header className={styles.topbar}>
            <button
              aria-label={common("openMenu")}
              className={styles.mobileMenuButton}
              onClick={() => setMobileNavOpen(true)}
              type="button"
            >
              <span aria-hidden="true">☰</span>
            </button>
            <div className={styles.crumb}>
              <MemberIcon name="shield" size={15} />
              <b>{t("title")}</b>
            </div>
            <div className={styles.topbarSpacer} />
            <button
              type="button"
              className={styles.themeButton}
              aria-label={memberT("theme")}
              title={memberT("theme")}
              onClick={toggleTheme}
            >
              <MemberIcon name={theme === "dark" ? "sun" : "moon"} size={16} />
            </button>
          </header>
        )}

        <main className={styles.content} ref={contentRef} onScroll={handleContentScroll}>
          <section className={styles.policyPage}>
            <div className={styles.policyHead}>
              <h1 className={styles.pageTitleWithIcon}>
                <span>
                  <MemberIcon name="shield" size={20} />
                </span>
                {t("title")}
              </h1>
              <Link className={styles.policyAskLink} href="/chat">
                <MemberIcon name="chat" size={15} />
                {t("askAboutPolicy")}
              </Link>
            </div>

            {listLoading ? (
              <p className={styles.policyState} role="status">
                {t("loadingList")}
              </p>
            ) : listError ? (
              <div className={styles.policyState} role="alert">
                <p>{listError}</p>
                <button type="button" onClick={() => void loadList()}>
                  {t("retry")}
                </button>
              </div>
            ) : items.length === 0 ? (
              <p className={styles.policyState}>{t("empty")}</p>
            ) : (
              <div className={styles.policyLayout}>
                <nav className={styles.policyList} aria-label={t("listLabel")}>
                  {items.map((item) => {
                    const active = item.document_id === selectedId;
                    const categoryKey =
                      CATEGORY_LABEL_KEYS[item.policy_category as keyof typeof CATEGORY_LABEL_KEYS];
                    return (
                      <button
                        type="button"
                        key={item.document_id}
                        className={active ? styles.policyItemActive : styles.policyItem}
                        aria-current={active ? "true" : undefined}
                        onClick={() => setSelectedId(item.document_id)}
                      >
                        <b>{item.title}</b>
                        <span>
                          {categoryKey ? t(categoryKey) : item.policy_category}
                          {item.version_no ? ` · v${item.version_no}` : ""}
                        </span>
                        {item.is_new_version && <small>{t("updated")}</small>}
                      </button>
                    );
                  })}
                </nav>

                <article className={styles.policyReader} aria-live="polite">
                  {contentError ? (
                    <div className={styles.policyState} role="alert">
                      <p>{contentError}</p>
                      <button type="button" onClick={() => setReloadContentToken((n) => n + 1)}>
                        {t("retry")}
                      </button>
                    </div>
                  ) : !content ? (
                    <p className={styles.policyState} role="status">
                      {t("loadingContent")}
                    </p>
                  ) : (
                    <>
                      <header className={styles.policyReaderHead}>
                        <h2>{content.title}</h2>
                        <p>
                          {t("version", { version: content.version_no })}
                          {effectiveDate ? ` · ${t("effective", { date: effectiveDate })}` : ""}
                        </p>
                      </header>
                      <MarkdownView source={content.content} className={styles.policyBody} />
                      {ackError && (
                        <p className={styles.policyAckError} role="alert">
                          {ackError}
                        </p>
                      )}
                      <div className={styles.policyAckBar}>
                        {!reachedEnd && <p className={styles.policyAckHint}>{t("scrollHint")}</p>}
                        <button
                          type="button"
                          className={styles.primaryButton}
                          disabled={acking || !reachedEnd}
                          onClick={() => void confirmRead()}
                        >
                          {acking ? t("saving") : t("confirmRead")}
                        </button>
                      </div>
                    </>
                  )}
                </article>
              </div>
            )}
          </section>
        </main>
      </div>

      {notice && (
        <div className={styles.toast} role="status">
          <MemberIcon name="check" size={16} /> {notice}
        </div>
      )}
    </div>
  );
}
