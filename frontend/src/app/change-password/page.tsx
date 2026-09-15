import { Suspense } from "react";

import { ChangePasswordScreen } from "@/features/auth/ChangePasswordScreen";

export const metadata = { title: "Đổi mật khẩu" };

export default function ChangePasswordPage() {
  // useSearchParams cần Suspense khi build tĩnh.
  return (
    <Suspense>
      <ChangePasswordScreen />
    </Suspense>
  );
}
