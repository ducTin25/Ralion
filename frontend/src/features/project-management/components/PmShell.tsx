"use client";

import { useCallback, useState, type ReactNode } from "react";
import { useTranslations } from "next-intl";

import { BrandHomeLink } from "@/components/brand/BrandHomeLink";
import { RalionBrand } from "@/components/brand/RalionBrand";
import { LanguageSwitcher } from "@/components/i18n/LanguageSwitcher";
import { MobileNavDrawer } from "@/components/navigation/MobileNavDrawer";
import type { CurrentUser } from "@/features/auth/session";
import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import { PmNotificationBell } from "@/features/project-management/components/PmNotificationBell";
import { PmAvatar } from "@/features/project-management/components/ui/PmAvatar";
import { PmToastHost } from "@/features/project-management/components/ui/PmToast";
import { Link } from "@/i18n/navigation";

import styles from "./PmShell.module.scss";

export type PmNavKey =
  "overview" | "projects" | "template" | "plan" | "docs" | "members" | "notifications" | "blockers" | "rules";

const NAV_ITEMS: {
  key: PmNavKey;
  labelKey: PmNavKey;
  icon: Parameters<typeof PmIcon>[0]["name"];
  count?: number;
  enabled: boolean;
}[] = [
  { key: "overview", labelKey: "overview", icon: "grid", enabled: true },
  { key: "projects", labelKey: "projects", icon: "folder", enabled: true },
  { key: "template", labelKey: "template", icon: "book", enabled: true },
  // Đặt ngay sau Master Template: thứ tự phản ánh đúng luồng làm việc — Template (khung task) →
  // Onboarding Plan (nội dung chuẩn dùng chung) → Tài liệu (nguồn) → Thành viên (giao cho từng người).
  { key: "plan", labelKey: "plan", icon: "check-circle", enabled: true },
  { key: "docs", labelKey: "docs", icon: "doc", enabled: true },
  { key: "members", labelKey: "members", icon: "users", enabled: true },
  { key: "blockers", labelKey: "blockers", icon: "flag", enabled: true },
  // UI_SPEC B.2/B.6: đứng ngay sau Blockers vì cùng bản chất — hàng đợi vận hành mà PM là
  // người quyết định kết quả. F6 không scope theo project nên mục này không phụ thuộc dự án
  // đang chọn.
  { key: "rules", labelKey: "rules", icon: "shield", enabled: true },
  // "Support Requests" (placeholder chưa có backend) đã bỏ theo UI_SPEC.md §12/§13 — không giữ
  // route trỏ tới màn hình không tồn tại.
];

const COMPACT_NAV_ORDER: PmNavKey[] = [
  "overview",
  "docs",
  "template",
  "plan",
  "members",
  "blockers",
  "rules",
];

type PmShellProps = {
  active: PmNavKey;
  onNavigate: (key: PmNavKey) => void;
  crumb: string;
  currentUser: CurrentUser;
  onSignOut: () => void;
  projectSwitcher?: ReactNode;
  /** Link sang trang chọn dự án (TV3 thêm ở chore/ui-polish). Để tuỳ chọn: caller nào không truyền
   * thì đơn giản là không hiện mục "Đổi dự án", không vỡ kiểu. */
  switchProjectHref?: string;
  /** Dự án đang chọn — chuông thông báo cần biết để lấy đúng task sắp/đã trễ hạn. `null` khi
   * chưa có dự án nào được chọn (vd trước khi redirect gắn `?project=` xong). */
  projectId?: number | null;
  children: ReactNode;
};

/**
 * Khung sườn PM dùng chung token Ralion: sidebar trái cố định + topbar + content
 * scroll. Class CSS chỉ scope layout nội bộ của module; không tạo một design
 * system riêng theo role. Light Tritanopia là theme duy nhất.
 */
export function PmShell({
  active,
  onNavigate,
  crumb,
  currentUser,
  onSignOut,
  projectSwitcher,
  switchProjectHref,
  projectId = null,
  children,
}: PmShellProps) {
  const t = useTranslations("pm");
  const common = useTranslations("common");
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const closeMobileNav = useCallback(() => setMobileNavOpen(false), []);
  const activeNavItem = NAV_ITEMS.find((item) => item.key === active);
  const renderNavigation = (mobile = false) => (
    <nav className={styles.navGroup}>
      {NAV_ITEMS.filter((item) => COMPACT_NAV_ORDER.includes(item.key))
        .sort((a, b) => COMPACT_NAV_ORDER.indexOf(a.key) - COMPACT_NAV_ORDER.indexOf(b.key))
        .map((item) => {
          const itemCount = item.count;
          return (
          <button
            aria-label={t(item.labelKey)}
            key={item.key}
            type="button"
            disabled={!item.enabled}
            className={`${styles.navItem} ${active === item.key ? styles.active : ""}`}
            onClick={() => {
              if (!item.enabled) return;
              onNavigate(item.key);
              if (mobile) closeMobileNav();
            }}
          >
            <PmIcon name={item.icon} size={17} />
            <span className={styles.navLabel}>{t(item.labelKey)}</span>
            {item.enabled ? (
              itemCount !== undefined && itemCount > 0 && (
                <span
                  className={styles.navCount}
                  data-critical={item.key === "notifications" ? "true" : undefined}
                >
                  {itemCount > 9 ? "9+" : itemCount}
                </span>
              )
            ) : (
              <span className={styles.soonTag}>{t("soon")}</span>
            )}
          </button>
          );
        })}
    </nav>
  );

  return (
    <div className={`${styles.pmShell} ralion-workspace`} data-active-view={active}>
      <PmToastHost />

      <aside className={styles.sidebar}>
        <BrandHomeLink className={styles.sidebarBrand}>
          <RalionBrand size={28} />
        </BrandHomeLink>

        <p className={styles.navSectionLabel}>{t("workspace")}</p>

        {renderNavigation()}

        <div className={styles.sidebarFoot}>
          <PmAvatar seed={currentUser.email} label={currentUser.display_name} />
          <div className={styles.who}>
            <b>{currentUser.display_name}</b>
            <span>{currentUser.email}</span>
          </div>
          {/* Gộp 2 nhánh: link "Đổi dự án" là của chore/ui-polish (TV3), nút "Đăng xuất" là bản đã
              có sẵn ở nhánh PM. Không chọn 1 bỏ 1 vì mỗi bên là 1 chức năng khác nhau. Nhãn để
              tiếng Anh cho khớp toàn bộ shell PM (Overview / Projects / Master Template...). */}
          {switchProjectHref && (
            <div className={styles.accountActions}>
              <Link href={switchProjectHref} className={styles.accountAction}>
                {t("switchProject")}
              </Link>
            </div>
          )}
          <button
            aria-label={common("logout")}
            type="button"
            className={styles.logoutBtn}
            onClick={onSignOut}
          >
            <PmIcon name="logout" size={15} />
            <span>{common("logout")}</span>
          </button>
        </div>
      </aside>

      <MobileNavDrawer label={t("navigation")} onClose={closeMobileNav} open={mobileNavOpen}>
        <BrandHomeLink className={styles.sidebarBrand} onClick={closeMobileNav}>
          <RalionBrand size={28} />
        </BrandHomeLink>
        <div className={styles.roleBadge}>
          <span className={styles.roleDot} />
          <span>PM</span>
        </div>
        {renderNavigation(true)}
        <div className={styles.mobileDrawerFoot}>
          <LanguageSwitcher />
          {switchProjectHref && (
            <Link
              href={switchProjectHref}
              className={styles.accountAction}
              onClick={closeMobileNav}
            >
              {t("switchProject")}
            </Link>
          )}
          <button
            aria-label={common("logout")}
            type="button"
            className={styles.logoutBtn}
            onClick={onSignOut}
          >
            <PmIcon name="logout" size={15} />
            <span>{common("logout")}</span>
          </button>
        </div>
      </MobileNavDrawer>

      <div className={styles.main}>
        <div className={styles.topbar}>
          <button
            aria-label={common("openMenu")}
            className={styles.mobileMenuButton}
            onClick={() => setMobileNavOpen(true)}
            type="button"
          >
            <span aria-hidden="true">☰</span>
          </button>
          <div className={styles.crumb}>
            {activeNavItem && <PmIcon name={activeNavItem.icon} size={15} />}
            <b>{crumb}</b>
          </div>

          <div className={styles.topbarRight}>
            {projectSwitcher && (
              <>
                <span aria-hidden="true" className={styles.topbarDivider} />
                {projectSwitcher}
              </>
            )}
            <LanguageSwitcher className={styles.desktopLanguage} compact />
              <PmNotificationBell
                projectId={projectId}
                currentUserId={currentUser.user_id}
              />
          </div>
        </div>

        <div className={styles.content}>
          <div className={styles.contentInner}>{children}</div>
        </div>
      </div>
    </div>
  );
}
