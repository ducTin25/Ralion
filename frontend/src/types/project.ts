export type ProjectRole = "PM" | "ENGINEER";
export type ProjectStatus = "ACTIVE" | "ARCHIVED";
export type MembershipStatus = "ACTIVE" | "INACTIVE";
export type SyncStatus = "NOT_STARTED" | "SYNCING" | "SUCCESS" | "PARTIAL" | "FAILED";
export type PlanStatus = "DRAFT" | "APPROVED" | "ACTIVE" | "PROJECT_READY" | "ONBOARDING_CLOSED";

export interface MembershipCard {
  membershipId: number;
  projectId: number;
  projectName: string;
  projectKey: string;
  projectStatus: ProjectStatus;
  projectRole: ProjectRole;
  joinedAt: string;
  syncStatus: SyncStatus;
  lastSyncedAt: string | null;
  plan: {
    status: PlanStatus;
    revision: number;
    requiredDone: number;
    requiredTotal: number;
    openBlockers: number;
  } | null;
}

export interface ActiveMembershipResponse {
  membershipId: number;
  projectId: number;
  projectName: string;
  projectKey: string;
  projectRole: ProjectRole;
  redirectPath: string;
}
