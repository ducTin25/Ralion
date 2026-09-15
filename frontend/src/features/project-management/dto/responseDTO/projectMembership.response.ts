export type ProjectMembershipResponseDTO = {
  membership_id: number;
  user_id: number;
  project_id: number;
  project_role: "PM" | "ENGINEER";
  status: "ACTIVE" | "INACTIVE";
  assigned_by_admin_id: number;
  joined_at: string;
};

/** Membership kèm sẵn thông tin User (email/tên) — trả về từ GET /project-memberships/pm?project_id=. */
export type ProjectMembershipDetailResponseDTO = {
  membership_id: number;
  user_id: number;
  email: string;
  display_name: string;
  project_id: number;
  project_role: "PM" | "ENGINEER";
  status: "ACTIVE" | "INACTIVE";
  joined_at: string;
};
