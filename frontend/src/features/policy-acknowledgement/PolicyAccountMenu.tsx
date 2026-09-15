"use client";

import { useEffect, useState } from "react";

import { AccountMenu } from "@/components/auth/AccountMenu";

import { policyApi } from "./api";

/**
 * `AccountMenu` kèm các mục dành riêng cho kỹ sư: chính sách cần xác nhận (có badge số
 * lượng) và quyền truy cập của tôi.
 *
 * Tách khỏi `AccountMenu` để component nền không phải biết gì về hai miền này — nơi nào
 * không cần thì dùng `AccountMenu` trần.
 *
 * Cả hai mục đều nằm ở menu avatar vì đó là chỗ duy nhất kỹ sư có mặt trên mọi màn
 * hình. Không có mục ở đây thì cách duy nhất vào được là gõ tay URL.
 */
export function PolicyAccountMenu({
  displayName,
  roleLabel,
}: {
  displayName?: string | null;
  roleLabel?: string;
}) {
  const [pending, setPending] = useState(0);

  useEffect(() => {
    let alive = true;
    policyApi
      .pending()
      .then((response) => {
        if (alive) setPending(response.items.length);
      })
      // Menu tài khoản không được vỡ vì một API phụ trợ hỏng.
      .catch(() => {
        if (alive) setPending(0);
      });
    return () => {
      alive = false;
    };
  }, []);

  return (
    <AccountMenu
      displayName={displayName}
      roleLabel={roleLabel}
      items={[
        {
          label: "Chính sách cần xác nhận",
          href: "/policies",
          hint: pending > 0 ? "Bạn có quy định chưa đọc" : "Xem lại các quy định đã ban hành",
          badge: pending,
        },
        {
          label: "Quyền truy cập của tôi",
          href: "/access",
          hint: "Xem quyền đã có và đang chờ cấp",
        },
      ]}
    />
  );
}
