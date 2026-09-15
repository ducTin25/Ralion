"use client";

import { useSearchParams } from "next/navigation";

import { useRouter } from "@/i18n/navigation";
import { FormEvent, useState } from "react";

import { authApi, signOutCurrentSession } from "./session";

/**
 * Đổi mật khẩu, phục vụ hai kịch bản trên cùng một màn hình:
 *
 * - **Bắt buộc** (`?required=1`): mật khẩu hiện tại do admin đặt. Không có nút bỏ qua,
 *   vì mọi endpoint nghiệp vụ đang trả 403 cho tới khi đổi xong.
 * - **Tự nguyện**: người dùng chủ động vào, có nút quay lại.
 *
 * Đổi xong backend xoá cookie phiên (`/auth/change-password` cố ý làm vậy), nên phải
 * đăng nhập lại — đó là hành vi đúng, không phải lỗi.
 */
export function ChangePasswordScreen() {
  const router = useRouter();
  const required = useSearchParams().get("required") === "1";

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const current = String(form.get("current_password") ?? "");
    const next = String(form.get("new_password") ?? "");
    const confirm = String(form.get("confirm_password") ?? "");

    if (next.length < 8) {
      setError("Mật khẩu mới phải có ít nhất 8 ký tự.");
      return;
    }
    if (next !== confirm) {
      setError("Hai ô mật khẩu mới không khớp.");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await authApi.changePassword(current, next);
      setDone(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không đổi được mật khẩu.");
      setSaving(false);
    }
  };

  if (done) {
    return (
      <main className="ralion-console flex min-h-screen items-center justify-center bg-canvas p-6">
        <section className="w-full max-w-[440px] rounded-2xl border border-border bg-white p-8 text-center">
          <h1 className="text-xl font-bold text-navy">Đã đổi mật khẩu</h1>
          <p className="mt-3 text-sm leading-6 text-text-subtle">
            Phiên đăng nhập cũ đã kết thúc để đảm bảo an toàn. Hãy đăng nhập lại bằng mật khẩu mới.
          </p>
          <button
            type="button"
            onClick={() => router.replace("/login")}
            className="mt-6 h-10 w-full rounded-lg bg-navy text-sm font-bold text-white"
          >
            Đăng nhập lại
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className="ralion-console flex min-h-screen items-center justify-center bg-canvas p-6">
      <section className="w-full max-w-[440px] rounded-2xl border border-border bg-white p-8">
        <p className="text-[11px] font-bold tracking-[.12em] text-[#4f5f96]">TÀI KHOẢN</p>
        <h1 className="mt-2 text-[26px] font-bold tracking-[-.03em] text-navy">
          {required ? "Đặt mật khẩu mới" : "Đổi mật khẩu"}
        </h1>
        <p className="mt-2 text-sm leading-6 text-text-subtle">
          {required
            ? "Mật khẩu hiện tại do quản trị viên đặt. Hãy chọn mật khẩu của riêng bạn trước khi tiếp tục."
            : "Chọn mật khẩu mới cho tài khoản của bạn."}
        </p>

        <form onSubmit={submit} className="mt-6 space-y-4">
          <label className="block text-sm font-semibold text-text-secondary">
            Mật khẩu hiện tại
            <input
              name="current_password"
              type="password"
              required
              autoComplete="current-password"
              className="mt-2 h-11 w-full rounded-lg border border-border-strong px-3 font-normal"
            />
          </label>
          <label className="block text-sm font-semibold text-text-secondary">
            Mật khẩu mới
            <input
              name="new_password"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              className="mt-2 h-11 w-full rounded-lg border border-border-strong px-3 font-normal"
            />
          </label>
          <label className="block text-sm font-semibold text-text-secondary">
            Nhập lại mật khẩu mới
            <input
              name="confirm_password"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              className="mt-2 h-11 w-full rounded-lg border border-border-strong px-3 font-normal"
            />
          </label>

          {error && (
            <p
              role="alert"
              className="rounded-lg border border-[#e3bcbb] bg-[#fdf3f3] p-3 text-sm leading-6 text-[#8f2f2d]"
            >
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={saving}
            className="h-11 w-full rounded-lg bg-navy text-sm font-bold text-white disabled:opacity-50"
          >
            {saving ? "Đang lưu…" : "Đổi mật khẩu"}
          </button>
        </form>

        {/* Ở chế độ bắt buộc không có nút "Để sau" — nhưng vẫn phải cho đăng xuất, nếu
            không người dùng đăng nhập nhầm tài khoản sẽ không có đường ra. */}
        <button
          type="button"
          onClick={() => (required ? void signOutCurrentSession() : router.back())}
          className="mt-4 h-10 w-full rounded-lg border border-border-strong text-sm font-bold text-navy"
        >
          {required ? "Đăng xuất" : "Quay lại"}
        </button>
      </section>
    </main>
  );
}
