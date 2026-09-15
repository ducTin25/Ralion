export type SystemRole = "ADMIN" | "HR" | null;

export type UserStatus = "ACTIVE" | "INACTIVE";

export type AdminUser = {
  id: string;
  displayName: string;
  email: string;
  systemRole: SystemRole;
  status: UserStatus;
  projectCount: number;
  createdAt: string;
  createdAtLabel: string;
  createdBy: string;
};
