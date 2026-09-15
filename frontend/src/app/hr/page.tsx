"use client";

import { useEffect } from "react";
import { useRouter } from "@/i18n/navigation";

import { HRPolicyLibrary } from "@/features/admin-console/HRPolicyLibrary";
import { useSession } from "@/features/auth/session";

export default function HrPage() {
  const router = useRouter();
  const { user, loading, error } = useSession();

  useEffect(() => {
    if (loading) return;
    if (!user) {
      if (error?.status === 401) router.replace("/login?next=/hr");
      return;
    }
    // ADMIN cũng vào được: cảnh báo chính sách thiếu ngày hiệu lực nằm ở trang tổng quan
    // Admin, và nút xử lý dẫn thẳng sang đây. Chặn ADMIN nghĩa là nút đó luôn đá người
    // dùng sang /access-denied. Backend đã dùng `require_hr_or_admin` cho mọi endpoint
    // chính sách, nên đây chỉ là chỉnh cho khớp lại.
    const allowed = user.system_role === "HR" || user.system_role === "ADMIN";
    if (!allowed) router.replace("/access-denied");
  }, [error, loading, router, user]);

  if (loading || !user || (user.system_role !== "HR" && user.system_role !== "ADMIN")) return null;
  return <HRPolicyLibrary />;
}
