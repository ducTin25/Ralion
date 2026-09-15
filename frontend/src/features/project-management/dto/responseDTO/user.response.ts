/** Response body trả về từ GET /api/v1/users — dùng để chọn user có sẵn khi thêm thành viên. */
export type UserResponseDTO = {
  user_id: number;
  email: string;
  display_name: string;
  system_role: "ADMIN" | "HR" | null;
  status: "ACTIVE" | "INACTIVE";
  created_by_admin_id: number | null;
  created_at: string;
};
