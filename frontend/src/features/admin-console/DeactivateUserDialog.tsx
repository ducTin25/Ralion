"use client";

import { useEffect, useState } from "react";

import { consoleApi } from "./api";
import type { UserDeactivationPreview } from "./types";

/**
 * Hộp thoại xác nhận khoá tài khoản, có nêu hậu quả cụ thể.
 *
 * Trước đây nút khoá tài khoản không hỏi gì cả: admin bấm xong không biết vừa cắt đứt
 * những gì. Màn hình xác nhận chỉ có giá trị khi nó nói được con số cụ thể — "sẽ ngừng
 * 3 membership và 5 quyền cần thu hồi tay" khác hẳn "bạn có chắc không".
 *
 * Danh sách quyền là checklist THỦ CÔNG. Hệ thống không gỡ được quyền trên GitHub hay
 * VPN, nên nó liệt kê ra để admin tự làm, thay vì tự đánh dấu đã thu hồi và tạo ra một
 * danh sách sạch sẽ nói dối.
 */
export function DeactivateUserDialog({
  userId,
  onClose,
  onConfirmed,
}: {
  userId: number;
  onClose: () => void;
  onConfirmed: () => void;
}) {
  const [preview, setPreview] = useState<UserDeactivationPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [checked, setChecked] = useState<Set<number>>(new Set());

  useEffect(() => {
    consoleApi
      .deactivationPreview(userId)
      .then(setPreview)
      .catch((caught) =>
        setError(caught instanceof Error ? caught.message : "Không tải được thông tin."),
      );
  }, [userId]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await consoleApi.changeUserStatus(userId, "INACTIVE");
      onConfirmed();
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không khoá được tài khoản.");
      setBusy(false);
    }
  };

  const toggle = (grantId: number) =>
    setChecked((current) => {
      const next = new Set(current);
      if (next.has(grantId)) next.delete(grantId);
      else next.add(grantId);
      return next;
    });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-6">
      <section
        role="dialog"
        aria-modal="true"
        aria-label="Xác nhận khoá tài khoản"
        className="max-h-full w-full max-w-[560px] overflow-auto rounded-xl bg-surface p-6 shadow-2xl"
      >
        <h2 className="text-lg font-bold text-navy">
          Khoá tài khoản {preview?.display_name ?? "…"}?
        </h2>
        <p className="mt-1 text-sm text-text-subtle">{preview?.email}</p>

        {!preview && !error && (
          <p className="mt-6 text-sm text-text-subtle">Đang tính toán hậu quả…</p>
        )}

        {preview && (
          <div className="mt-5 space-y-4">
            <div className="rounded-lg border border-warn-border bg-warn-bg p-4">
              <p className="text-sm font-bold text-warn-text">Thao tác này sẽ:</p>
              <ul className="mt-2 space-y-1 text-sm leading-6 text-warn-text">
                <li>
                  · Ngừng <b>{preview.memberships.length}</b> membership dự án
                </li>
                {preview.will_revoke_sessions && (
                  <li>· Huỷ ngay phiên đăng nhập hiện tại của người này</li>
                )}
                {preview.is_primary_pm_of.length > 0 && (
                  <li className="font-bold">
                    · Để trống vị trí PM phụ trách ở{" "}
                    {preview.is_primary_pm_of.map((p) => p.project_name).join(", ")}
                  </li>
                )}
                <li>
                  · Để lại <b>{preview.granted_access.length}</b> quyền cần bạn thu hồi bằng tay
                </li>
              </ul>
            </div>

            {preview.memberships.length > 0 && (
              <div>
                <h3 className="text-sm font-bold text-navy">Membership sẽ ngừng</h3>
                <ul className="mt-2 divide-y divide-divider rounded-lg border border-border">
                  {preview.memberships.map((membership) => (
                    <li key={membership.membership_id} className="px-3 py-2 text-sm">
                      {membership.project_name}{" "}
                      <span className="text-text-subtle">
                        · {membership.project_role === "PM" ? "PM" : "Kỹ sư"}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {preview.granted_access.length > 0 && (
              <div>
                <h3 className="text-sm font-bold text-navy">
                  Checklist thu hồi ({checked.size}/{preview.granted_access.length})
                </h3>
                <p className="mt-1 text-xs leading-5 text-text-subtle">
                  Hệ thống không gỡ được quyền trên GitHub, Jira hay VPN. Hãy gỡ tay rồi tick lại
                  đây để ghi nhận. Không tick hết vẫn khoá được — checklist là ghi chép, không
                  phải rào chặn.
                </p>
                <ul className="mt-2 divide-y divide-divider rounded-lg border border-border">
                  {preview.granted_access.map((access) => (
                    <li key={access.grant_id} className="px-3 py-2">
                      <label className="flex cursor-pointer items-start gap-2.5 text-sm">
                        <input
                          type="checkbox"
                          checked={checked.has(access.grant_id)}
                          onChange={() => toggle(access.grant_id)}
                          className="mt-1"
                        />
                        <span>
                          {access.resource_label}
                          {access.project_name && (
                            <span className="text-text-subtle"> · {access.project_name}</span>
                          )}
                          {access.resource_note && (
                            <span className="block font-mono text-[11px] text-text-subtle">
                              {access.resource_note}
                            </span>
                          )}
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

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
            disabled={busy || !preview}
            onClick={() => void confirm()}
            className="h-10 rounded-md bg-danger px-4 text-sm font-semibold text-white disabled:opacity-50"
          >
            {busy ? "Đang khoá…" : "Khoá tài khoản"}
          </button>
        </div>
      </section>
    </div>
  );
}
