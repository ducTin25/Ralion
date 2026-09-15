"use client";

import { Link } from "@/i18n/navigation";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";

import { signOutCurrentSession } from "@/features/auth/session";

/** Chữ cái đầu của tên, dùng cho avatar tròn. */
function initials(name?: string | null) {
  return (
    (name ?? "")
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .slice(-2)
      .map((part) => part[0]?.toUpperCase() ?? "")
      .join("") || "?"
  );
}

export type AccountMenuItem = {
  label: string;
  href: string;
  /** Mô tả ngắn dưới nhãn — bỏ trống nếu nhãn đã đủ rõ. */
  hint?: string;
  /** Số hiển thị bên phải, ví dụ số chính sách chưa xác nhận. */
  badge?: number;
};

/**
 * Menu tài khoản mở từ avatar.
 *
 * Gom các hành động thuộc về *người dùng* (đổi mật khẩu, chính sách của tôi, đăng xuất)
 * vào một chỗ, thay vì rải thành nút rời trên header. Header là nơi đặt hành động của
 * *màn hình đang xem*; trộn hai loại vào nhau khiến thanh trên cùng dài ra theo mỗi
 * tính năng mới.
 *
 * Đóng bằng Esc và bằng click ra ngoài — menu nổi mà không có hai đường thoát đó thì
 * người dùng phải bấm lại đúng nút vừa mở.
 */
export function AccountMenu({
  displayName,
  roleLabel,
  items = [],
  children,
}: {
  displayName?: string | null;
  /** Nhãn vai trò hiển thị dưới tên, ví dụ "Quản trị viên". */
  roleLabel?: string;
  items?: AccountMenuItem[];
  /** Mục tuỳ biến chèn thêm phía trên nhóm mặc định. */
  children?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("mousedown", onPointerDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("mousedown", onPointerDown);
    };
  }, [open]);

  const allItems: AccountMenuItem[] = [
    ...items,
    { label: "Đổi mật khẩu", href: "/change-password" },
  ];

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        className="flex items-center gap-2.5 rounded-lg px-1.5 py-1 transition hover:bg-[#f0f2f8]"
      >
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[#e9ecf4] text-xs font-bold text-navy">
          {initials(displayName)}
        </span>
        <span className="hidden text-sm font-semibold text-navy sm:block">
          {displayName ?? "…"}
        </span>
        <span aria-hidden="true" className="text-[10px] text-text-subtle">
          ▾
        </span>
      </button>

      {open && (
        <div
          id={menuId}
          role="menu"
          className="absolute right-0 z-50 mt-2 w-[268px] overflow-hidden rounded-xl border border-border bg-white shadow-[0_12px_32px_rgba(11,28,48,.14)]"
        >
          <div className="border-b border-divider px-4 py-3">
            <p className="truncate text-sm font-bold text-navy">{displayName ?? "…"}</p>
            {roleLabel && <p className="mt-0.5 text-xs text-text-subtle">{roleLabel}</p>}
          </div>

          <div className="py-1.5">
            {children}
            {allItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                role="menuitem"
                onClick={() => setOpen(false)}
                className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm text-text transition hover:bg-canvas"
              >
                <span className="min-w-0">
                  <span className="block font-semibold text-navy">{item.label}</span>
                  {item.hint && (
                    <span className="mt-0.5 block text-xs text-text-subtle">{item.hint}</span>
                  )}
                </span>
                {item.badge !== undefined && item.badge > 0 && (
                  <span className="shrink-0 rounded-full bg-[#fdf3e6] px-2 py-0.5 text-[11px] font-bold text-[#b3721b]">
                    {item.badge}
                  </span>
                )}
              </Link>
            ))}
          </div>

          {/* Đăng xuất tách hẳn xuống dưới đường kẻ: nó là hành động khác loại với
              phần còn lại, và bấm nhầm thì mất cả phiên làm việc. */}
          <div className="border-t border-divider py-1.5">
            <button
              type="button"
              role="menuitem"
              disabled={signingOut}
              onClick={() => {
                setSigningOut(true);
                void signOutCurrentSession();
              }}
              className="w-full px-4 py-2.5 text-left text-sm font-semibold text-[#8f2f2d] transition hover:bg-[#fdf3f3] disabled:opacity-60"
            >
              {signingOut ? "Đang đăng xuất…" : "Đăng xuất"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
