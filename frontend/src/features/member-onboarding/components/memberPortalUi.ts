import type {
  BlockerCategory,
  BlockerStatus,
  TaskCategory,
  TaskStatus,
} from "@/features/member-onboarding/types";

export const CATEGORY_LABELS: Record<TaskCategory, string> = {
  COMPANY: "Get to know the company",
  ORIENTATION: "Project overview",
  ACCESS: "Access & security",
  SETUP: "Environment setup",
  CODEBASE: "Get to know the codebase",
  CONVENTION: "Development conventions",
};

export const CATEGORY_LABEL_KEYS: Record<TaskCategory, string> = {
  COMPANY: "categoryCompany",
  ORIENTATION: "categoryOrientation",
  ACCESS: "categoryAccess",
  SETUP: "categorySetup",
  CODEBASE: "categoryCodebase",
  CONVENTION: "categoryConvention",
};

export const STATUS_LABELS: Record<TaskStatus, string> = {
  NOT_STARTED: "Not started",
  IN_PROGRESS: "In progress",
  DONE: "Completed",
  BLOCKED: "Blocked",
};

export const STATUS_LABEL_KEYS: Record<TaskStatus, string> = {
  NOT_STARTED: "statusNotStarted",
  IN_PROGRESS: "statusInProgress",
  DONE: "statusDone",
  BLOCKED: "statusBlocked",
};

export const BLOCKER_CATEGORY_LABEL_KEYS: Record<BlockerCategory, string> = {
  ACCESS: "categoryAccess",
  SETUP: "categorySetup",
  DOCUMENT: "categoryDocument",
  TECHNICAL: "categoryTechnical",
  OTHER: "categoryOther",
};

export const BLOCKER_STATUS_LABEL_KEYS: Record<BlockerStatus, string> = {
  OPEN: "statusOpen",
  ROUTED: "statusRouted",
  RESOLVED: "statusResolved",
};

export function initials(value: string) {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .slice(-2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export function formatDate(value: string | null, locale = "vi-VN") {
  if (!value) return null;
  return new Intl.DateTimeFormat(locale, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}
