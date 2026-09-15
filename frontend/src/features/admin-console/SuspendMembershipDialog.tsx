"use client";

import { useEffect, useState } from "react";

import { consoleApi } from "./api";
import type { MembershipOffboardingPreview } from "./types";

/**
 * Xác nhận tạm ngừng một membership, kèm checklist quyền cần thu hồi.
 *
 * Đây là chỗ *access creep* thực sự phát sinh: người rời dự án nhưng quyền repo, Jira,
 * VPN vẫn còn vì không ai ghi lại đã cấp gì. Hộp thoại này liệt kê đúng danh sách đó.
 *
 * Hệ thống KHÔNG tự gỡ quyền trên các dịch vụ ngoài. Tick ở đây chỉ ghi nhận việc admin
 * đã gỡ tay — tự đánh dấu REVOKED sẽ tạo ra một danh sách sạch sẽ nói dối.
 */
export function SuspendMembershipDialog({
  membershipId,
  onClose,
  onConfirmed,
}: {
  membershipId: number;
  onClose: () => void;
  onConfirmed: () => void;
}) {
  const [preview, setPreview] = useState<MembershipOffboardingPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [alsoRevoke, setAlsoRevoke] = useState(false);

  useEffect(() => {
    consoleApi
      .membershipOffboardingPreview(membershipId)
      .then(setPreview)
      .catch((caught) =>
        setError(caught instanceof Error ? caught.message : "Không tải được thông tin."),
      );
  }, [membershipId]);

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
      await consoleApi.updateMembership(membershipId, { status: "INACTIVE" });
      // Đánh dấu thu hồi là hành động RIÊNG, phải admin chủ động tick. Chạy tự động
      // theo việc ngừng membership sẽ ghi "đã thu hồi" cho những quyền chưa ai gỡ.
      if (alsoRevoke) await consoleApi.revokeMembershipAccess(membershipId);
      onConfirmed();
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không ngừng được membership.");
      setBusy(false);
    }
  };

  const grants = preview?.granted_access ?? [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-6">
      <section
        role="dialog"
        aria-modal="true"
        aria-label="Xác nhận tạm ngừng membership"
        className="max-h-full w-full max-w-[520px] overflow-auto rounded-xl bg-surface p-6 shadow-2xl"
      >
        <h2 className="text-lg font-bold text-navy">Tạm ngừng membership?</h2>
        {preview && (
          <p className="mt-1 text-sm text-text-subtle">
            {preview.display_name} · {preview.project_name} ({preview.project_key})
          </p>
        )}

        {!preview && !error && (
          <p className="mt-6 text-sm text-text-subtle">Đang tính toán hậu quả…</p>
        )}

        {preview && (
          <div className="mt-5 space-y-4">
            <div className="rounded-lg border border-warn-border bg-warn-bg p-4">
              <p className="text-sm font-bold text-warn-text">Thao tác này sẽ:</p>
              <ul className="mt-2 space-y-1 text-sm leading-6 text-warn-text">
                <li>· Chặn người này mở workspace của dự án</li>
                {preview.is_primary_pm && (
                  <li className="font-bold">· Để trống vị trí PM phụ trách của dự án</li>
                )}
                <li>
                  · Để lại <b>{grants.length}</b> quyền cần bạn thu hồi bằng tay
                </li>
                {/* Phân biệt rõ với việc khoá tài khoản: rời một dự án không phải rời
                    công ty, nên phiên đăng nhập không bị đụng tới. */}
                <li>· KHÔNG huỷ phiên đăng nhập — người này vẫn làm việc ở dự án khác</li>
              </ul>
            </div>

            {grants.length > 0 && (
              <div>
                <h3 className="text-sm font-bold text-navy">Quyền cần thu hồi</h3>
                <ul className="mt-2 divide-y divide-divider rounded-lg border border-border">
                  {grants.map((access) => (
                    <li key={access.grant_id} className="px-3 py-2 text-sm">
                      {access.resource_label}
                      {access.resource_note && (
                        <span className="block font-mono text-[11px] text-text-subtle">
                          {access.resource_note}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
                <label className="mt-3 flex cursor-pointer items-start gap-2.5 text-sm">
                  <input
                    type="checkbox"
                    checked={alsoRevoke}
                    onChange={(event) => setAlsoRevoke(event.target.checked)}
                    className="mt-1"
                  />
                  <span>
                    Tôi đã gỡ những quyền trên ở GitHub, Jira, VPN… — đánh dấu là đã thu hồi.
                    <span className="mt-0.5 block text-xs leading-5 text-text-subtle">
                      Bỏ trống nếu chưa gỡ. Danh sách quyền vẫn được lưu trong lịch sử membership để
                      bạn xử lý sau.
                    </span>
                  </span>
                </label>
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
            className="h-10 rounded-md bg-navy px-4 text-sm font-semibold text-white disabled:opacity-50"
          >
            {busy ? "Đang xử lý…" : "Tạm ngừng"}
          </button>
        </div>
      </section>
    </div>
  );
}
