"use client";

import { useEffect, useState } from "react";

import { consoleApi } from "./api";

// Bỏ các ký tự dễ đọc nhầm khi chép tay hoặc đọc qua điện thoại: 0/O, 1/l/I.
// Cùng bảng chữ với `user_import_service.PASSWORD_ALPHABET` ở backend.
const ALPHABET = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789";
const LENGTH = 12;

function generatePassword() {
  // crypto.getRandomValues thay vì Math.random: đây là mật khẩu thật của một tài khoản
  // thật, không phải giá trị trang trí.
  const bytes = new Uint32Array(LENGTH);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (value) => ALPHABET[value % ALPHABET.length]).join("");
}

/**
 * Đặt lại mật khẩu cho một tài khoản.
 *
 * Hệ thống chưa có luồng "quên mật khẩu" tự phục vụ, nên đây là đường duy nhất để một
 * nhân viên quên mật khẩu quay lại làm việc.
 *
 * Backend làm thêm hai việc mà màn hình này phải nói rõ, nếu không admin sẽ tưởng có lỗi:
 * bật lại cờ bắt đổi mật khẩu, và huỷ mọi phiên đăng nhập đang mở của người đó.
 */
export function ResetPasswordDialog({
  userId,
  displayName,
  onClose,
  onDone,
}: {
  userId: number;
  displayName: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const [password, setPassword] = useState(generatePassword);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const submit = async () => {
    if (password.length < 8) {
      setError("Mật khẩu phải có ít nhất 8 ký tự.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await consoleApi.resetUserPassword(userId, password);
      setSaved(true);
      onDone();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không đặt lại được mật khẩu.");
    } finally {
      setBusy(false);
    }
  };

  const copy = async () => {
    await navigator.clipboard.writeText(password);
    setCopied(true);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-6">
      <section
        role="dialog"
        aria-modal="true"
        aria-label="Đặt lại mật khẩu"
        className="w-full max-w-[480px] rounded-xl bg-surface p-6 shadow-2xl"
      >
        <h2 className="text-lg font-bold text-navy">Đặt lại mật khẩu</h2>
        <p className="mt-1 text-sm text-text-subtle">{displayName}</p>

        {saved ? (
          <>
            <div className="mt-5 rounded-lg border border-success-border bg-success-bg p-4">
              <p className="text-sm font-bold text-success-text">Đã đặt lại mật khẩu</p>
              <p className="mt-1 text-sm leading-6 text-success-text">
                Mật khẩu dưới đây <b>chỉ hiển thị một lần</b>. Hãy gửi cho người dùng ngay — hệ
                thống không lưu lại bản đọc được.
              </p>
              <p className="mt-3 rounded-md border border-border bg-surface px-3 py-2 font-mono text-[15px] font-bold tracking-wide text-navy">
                {password}
              </p>
              <button
                type="button"
                onClick={() => void copy()}
                className="mt-3 h-9 rounded-lg bg-navy px-4 text-sm font-bold text-white"
              >
                {copied ? "Đã sao chép" : "Sao chép"}
              </button>
            </div>
            <ul className="mt-4 space-y-1 text-xs leading-5 text-text-subtle">
              <li>· Người dùng sẽ phải đổi mật khẩu ngay ở lần đăng nhập kế tiếp.</li>
              <li>· Mọi phiên đăng nhập đang mở của tài khoản này đã bị huỷ.</li>
            </ul>
            <div className="mt-6 flex justify-end">
              <button
                type="button"
                onClick={onClose}
                className="h-10 rounded-md bg-navy px-4 text-sm font-semibold text-white"
              >
                Xong
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="mt-5 rounded-lg border border-warn-border bg-warn-bg p-3 text-xs leading-5 text-warn-text">
              Thao tác này sẽ <b>huỷ ngay phiên đăng nhập</b> của người dùng và bắt họ đổi mật
              khẩu ở lần đăng nhập kế tiếp.
            </div>

            <label className="mt-5 block text-sm font-semibold text-text-secondary">
              Mật khẩu mới
              <div className="mt-2 flex gap-2">
                <input
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  minLength={8}
                  className="h-10 flex-1 rounded-md border border-border-strong px-3 font-mono text-sm font-normal"
                />
                <button
                  type="button"
                  onClick={() => setPassword(generatePassword())}
                  className="h-10 shrink-0 rounded-md border border-border-strong px-3 text-sm font-semibold text-navy"
                >
                  Sinh lại
                </button>
              </div>
            </label>
            <p className="mt-2 text-xs leading-5 text-text-subtle">
              Mặc định là chuỗi ngẫu nhiên {LENGTH} ký tự, đã bỏ các ký tự dễ đọc nhầm (0/O,
              1/l/I). Bạn có thể tự nhập nếu muốn.
            </p>

            {error && (
              <p
                role="alert"
                className="mt-4 rounded-md border border-danger-border bg-danger-bg p-3 text-sm text-danger"
              >
                {error}
              </p>
            )}

            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={onClose}
                className="h-10 rounded-md border border-border-strong px-4 text-sm font-semibold text-navy"
              >
                Huỷ
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void submit()}
                className="h-10 rounded-md bg-navy px-4 text-sm font-semibold text-white disabled:opacity-50"
              >
                {busy ? "Đang lưu…" : "Đặt lại mật khẩu"}
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
