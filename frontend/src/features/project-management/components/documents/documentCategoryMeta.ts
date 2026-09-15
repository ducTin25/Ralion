import type { PmIcon } from "@/features/project-management/components/PmIconSprite";
import type { DocumentCategory } from "@/features/project-management/dto/responseDTO/document.response";

export type CategoryVariant = "accent" | "success" | "warning" | "violet";

/** Đúng 5 category bắt buộc của tài liệu dự án — khớp 1:1 tên/icon/màu với 5 category Master
 * Template (xem components/template/TaskFormModal.tsx CATEGORY_OPTIONS) để nhất quán trực quan. */
export const DOCUMENT_CATEGORY_META: Record<
  DocumentCategory,
  { labelKey: string; icon: Parameters<typeof PmIcon>[0]["name"]; variant: CategoryVariant }
> = {
  OVERVIEW: { labelKey: "categoryOrientation", icon: "doc", variant: "success" },
  ARCHITECTURE: { labelKey: "categoryArchitecture", icon: "grid", variant: "violet" },
  SETUP: { labelKey: "categorySetup", icon: "flag", variant: "warning" },
  ACCESS_SECURITY: { labelKey: "categoryAccess", icon: "key", variant: "accent" },
  CODEBASE_GUIDE: { labelKey: "categoryCodebase", icon: "book", variant: "success" },
  CONVENTION: { labelKey: "categoryConventionFuture", icon: "doc", variant: "accent" },
  FIRST_TASK: { labelKey: "categoryFirstTaskFuture", icon: "doc", variant: "accent" },
};

export const REQUIRED_DOCUMENT_CATEGORIES: DocumentCategory[] = [
  "OVERVIEW",
  "ARCHITECTURE",
  "SETUP",
  "ACCESS_SECURITY",
  "CODEBASE_GUIDE",
];
