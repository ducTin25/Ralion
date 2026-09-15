import type { PolicyCategory } from "@/features/project-management/dto/responseDTO/knowledgeDocument.response";
import type { PmIcon } from "@/features/project-management/components/PmIconSprite";

import type { CategoryVariant } from "./TaskFormModal";

export const POLICY_CATEGORY_META: Record<
  PolicyCategory,
  {
    label: string;
    labelKey: string;
    icon: Parameters<typeof PmIcon>[0]["name"];
    variant: CategoryVariant;
  }
> = {
  COMPANY_POLICY: { label: "General company policy", labelKey: "policyCompany", icon: "shield", variant: "accent" },
  HR_POLICY: { label: "HR policy", labelKey: "policyHr", icon: "users", variant: "warning" },
  SECURITY_POLICY: { label: "Security policy", labelKey: "policySecurity", icon: "lock", variant: "violet" },
  BENEFIT: { label: "Benefits", labelKey: "policyBenefits", icon: "check-circle", variant: "success" },
  WORKING_RULE: { label: "Working rules", labelKey: "policyWorkingRules", icon: "doc", variant: "accent" },
  GENERAL: { label: "Other policies", labelKey: "policyOther", icon: "doc", variant: "accent" },
};

/** Tra ngược nhãn -> meta. Nội dung task do AI sinh chỉ có TÊN nhóm dạng chữ (`### Chính sách nhân
 * sự`) chứ không mang mã enum, nên muốn gắn đúng icon/màu cho tiêu đề đó thì phải dò lại từ nhãn.
 * Nhãn này khớp `POLICY_CATEGORY_LABELS` bên backend (content_llm.py) — 2 bên phải sửa cùng nhau. */
export const POLICY_META_BY_LABEL = new Map(
  Object.values(POLICY_CATEGORY_META).map((meta) => [meta.label, meta]),
);
