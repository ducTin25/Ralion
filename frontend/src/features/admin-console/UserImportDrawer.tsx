"use client";

import { useState } from "react";

import { consoleApi } from "./api";
import type { UserImportPreview, UserImportResult } from "./types";

const TEMPLATE =
  "display_name,email,system_role,start_date\nNguyễn Văn A,a@congty.vn,,01/09/2026\n";

/**
 * Nhập nhân sự hàng loạt từ CSV, hai bước: xem trước rồi mới tạo.
 *
 * Có bước xem trước vì import là thao tác hàng loạt không hoàn tác được — tạo nhầm 20
 * tài khoản thì phải xoá tay 20 lần.
 *
 * Mật khẩu do server sinh ngẫu nhiên và chỉ trả về đúng một lần trong response. Không
 * lưu ở đâu cả, nên màn hình kết quả phải cho admin sao chép ngay.
 */
export function UserImportDrawer({
  onClose,
  onImported,
}: {
  onClose: () => void;
  onImported: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<UserImportPreview | null>(null);
  const [result, setResult] = useState<UserImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const pickFile = async (picked: File) => {
    setFile(picked);
    setPreview(null);
    setResult(null);
    setError(null);
    setBusy(true);
    try {
      setPreview(await consoleApi.previewUserImport(picked));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không đọc được file.");
    } finally {
      setBusy(false);
    }
  };

  const runImport = async () => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await consoleApi.importUsers(file));
      onImported();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không import được.");
    } finally {
      setBusy(false);
    }
  };

  const copyCredentials = async () => {
    if (!result) return;
    const text = result.created.map((row) => `${row.email}\t${row.temporary_password}`).join("\n");
    await navigator.clipboard.writeText(text);
    setCopied(true);
  };

  const templateHref = `data:text/csv;charset=utf-8,${encodeURIComponent(TEMPLATE)}`;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-[#0b1c30]/30">
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Nhập nhân sự từ file CSV"
        className="flex h-full w-full max-w-[720px] flex-col bg-white shadow-2xl"
      >
        <header className="flex items-start justify-between border-b border-divider px-7 py-5">
          <div>
            <p className="text-xs font-bold tracking-[.1em] text-[#4f5f96]">NHẬP HÀNG LOẠT</p>
            <h2 className="mt-2 text-xl font-bold text-navy">Tạo tài khoản từ file CSV</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-3 py-2 text-sm font-semibold hover:bg-canvas"
          >
            Đóng
          </button>
        </header>

        <div className="flex-1 overflow-auto px-7 py-6">
          {result ? (
            <>
              <div className="rounded-xl border border-[#bcd9c6] bg-[#f2f9f4] p-4">
                <b className="text-[#1f7a4d]">Đã tạo {result.created.length} tài khoản</b>
                <p className="mt-1 text-sm text-[#2f6b47]">
                  Mật khẩu dưới đây <b>chỉ hiển thị một lần</b>. Hãy sao chép và gửi cho từng người
                  ngay — hệ thống không lưu lại. Người dùng sẽ phải đổi mật khẩu ở lần đăng nhập đầu
                  tiên.
                </p>
                <button
                  type="button"
                  onClick={copyCredentials}
                  className="mt-3 h-9 rounded-lg bg-navy px-4 text-sm font-bold text-white"
                >
                  {copied ? "Đã sao chép" : "Sao chép toàn bộ"}
                </button>
              </div>

              <table className="mt-5 w-full text-left text-sm">
                <thead className="border-b border-divider text-[11px] uppercase tracking-[.08em] text-text-subtle">
                  <tr>
                    <th className="py-2">Họ tên</th>
                    <th className="py-2">Email</th>
                    <th className="py-2">Mật khẩu tạm</th>
                  </tr>
                </thead>
                <tbody>
                  {result.created.map((row) => (
                    <tr key={row.user_id} className="border-b border-divider last:border-0">
                      <td className="py-2.5">{row.display_name}</td>
                      <td className="py-2.5 text-text-subtle">{row.email}</td>
                      <td className="py-2.5 font-mono text-[13px]">{row.temporary_password}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {result.skipped.length > 0 && (
                <section className="mt-7">
                  <h3 className="text-sm font-bold text-navy">
                    Bỏ qua {result.skipped.length} dòng
                  </h3>
                  <ul className="mt-3 divide-y divide-divider rounded-xl border border-border">
                    {result.skipped.map((row) => (
                      <li key={row.line} className="px-4 py-2.5 text-sm">
                        <b>Dòng {row.line}</b> · {row.email || row.display_name || "(trống)"} —{" "}
                        <span className="text-[#8f2f2d]">{row.error}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </>
          ) : (
            <>
              <label className="block text-sm font-semibold text-text-secondary">
                Tệp CSV
                <input
                  type="file"
                  accept=".csv,text/csv"
                  disabled={busy}
                  onChange={(event) => {
                    const picked = event.target.files?.[0];
                    if (picked) void pickFile(picked);
                  }}
                  className="mt-2 w-full rounded-lg border border-border-strong p-2.5 text-sm font-normal file:mr-3 file:rounded-md file:border-0 file:bg-navy file:px-3 file:py-1.5 file:text-xs file:font-bold file:text-white"
                />
              </label>
              <p className="mt-2 text-xs leading-5 text-text-subtle">
                Cột bắt buộc: <code>display_name</code>, <code>email</code>. Cột tuỳ chọn:{" "}
                <code>system_role</code> (trống / ADMIN / HR), <code>start_date</code> (DD/MM/YYYY).
                Tối đa 100 dòng.{" "}
                <a href={templateHref} download="mau-nhan-su.csv" className="text-link underline">
                  Tải file mẫu
                </a>
                .
              </p>
              <p className="mt-2 text-xs leading-5 text-text-subtle">
                Không có cột mật khẩu — hệ thống tự sinh cho từng người. Đặt mật khẩu trong file
                Excel là mời gọi việc file đó bị chia sẻ nguyên vẹn qua chat.
              </p>

              {busy && !preview && (
                <p className="mt-5 rounded-lg border border-border bg-canvas p-4 text-sm text-text-subtle">
                  Đang đọc file…
                </p>
              )}

              {preview && (
                <section className="mt-6">
                  <p className="text-sm">
                    <b className="text-[#1f7a4d]">{preview.valid_count} dòng hợp lệ</b>
                    {preview.invalid_count > 0 && (
                      <>
                        {" · "}
                        <b className="text-[#8f2f2d]">{preview.invalid_count} dòng sẽ bị bỏ qua</b>
                      </>
                    )}
                  </p>
                  <table className="mt-3 w-full text-left text-sm">
                    <thead className="border-b border-divider text-[11px] uppercase tracking-[.08em] text-text-subtle">
                      <tr>
                        <th className="py-2">Dòng</th>
                        <th className="py-2">Họ tên</th>
                        <th className="py-2">Email</th>
                        <th className="py-2">Trạng thái</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.rows.map((row) => (
                        <tr key={row.line} className="border-b border-divider last:border-0">
                          <td className="py-2.5 tabular-nums text-text-subtle">{row.line}</td>
                          <td className="py-2.5">{row.display_name || "—"}</td>
                          <td className="py-2.5 text-text-subtle">{row.email || "—"}</td>
                          <td className="py-2.5">
                            {row.error ? (
                              <span className="text-[#8f2f2d]">{row.error}</span>
                            ) : (
                              <span className="text-[#1f7a4d]">Sẽ tạo</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </section>
              )}
            </>
          )}

          {error && (
            <p
              role="alert"
              className="mt-5 rounded-lg border border-[#e3bcbb] bg-[#fdf3f3] p-3 text-sm leading-6 text-[#8f2f2d]"
            >
              {error}
            </p>
          )}
        </div>

        <footer className="flex items-center justify-end gap-3 border-t border-divider px-7 py-5">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="h-10 rounded-lg border border-border-strong px-4 text-sm font-bold text-navy"
          >
            {result ? "Xong" : "Hủy"}
          </button>
          {!result && (
            <button
              type="button"
              onClick={runImport}
              disabled={busy || !preview || preview.valid_count === 0}
              className="h-10 rounded-lg bg-navy px-4 text-sm font-bold text-white disabled:opacity-50"
            >
              {busy ? "Đang tạo…" : `Tạo ${preview?.valid_count ?? 0} tài khoản`}
            </button>
          )}
        </footer>
      </aside>
    </div>
  );
}
