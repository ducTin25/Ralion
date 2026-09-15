import { Link } from "@/i18n/navigation";

/**
 * Lối vào trang đổi mật khẩu, đặt cạnh nút Đăng xuất ở mọi shell.
 *
 * Tách thành component dùng chung như `LogoutButton` để mọi khu vực (Admin, HR, Engineer)
 * cùng một nhãn và cùng một đường dẫn. Trước đó `/change-password` chỉ tới được bằng
 * redirect sau khi đăng nhập với mật khẩu tạm — người muốn chủ động đổi thì không có
 * đường nào ngoài gõ URL.
 */
export function ChangePasswordLink({ className }: { className?: string }) {
  return (
    <Link href="/change-password" className={className}>
      Đổi mật khẩu
    </Link>
  );
}
