"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import type {
  KnowledgeDocumentResponseDTO,
  PolicyCategory,
} from "@/features/project-management/dto/responseDTO/knowledgeDocument.response";
import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import { DocumentPreviewModal } from "@/features/project-management/components/ui/DocumentPreviewModal";
import { PmDrawer } from "@/features/project-management/components/ui/PmDrawer";
import { PmTag } from "@/features/project-management/components/ui/PmPill";

import { POLICY_CATEGORY_META } from "./policyCategoryMeta";
import drawerStyles from "./CategoryTaskDrawer.module.scss";
import styles from "./CompanyCoreDrawer.module.scss";

type CompanyCoreDrawerProps = {
  documents: KnowledgeDocumentResponseDTO[];
  onClose: () => void;
};

// 5 nhóm chính sách chuẩn (không tính GENERAL — chỉ là nhóm dự phòng, chỉ hiện khi thật sự có
// tài liệu rơi vào đó) — luôn hiện đủ 5 nhóm dù nhóm nào chưa có tài liệu, cùng cách làm với
// REQUIRED_DOCUMENT_CATEGORIES bên trang "Tài liệu dự án" để 2 nơi nhất quán.
const POLICY_CATEGORY_ORDER: PolicyCategory[] = [
  "COMPANY_POLICY",
  "HR_POLICY",
  "SECURITY_POLICY",
  "BENEFIT",
  "WORKING_RULE",
];

const VARIANT_ICON_CLASS: Record<string, string> = {
  accent: "iconAccent",
  success: "iconSuccess",
  warning: "iconWarning",
  violet: "iconViolet",
};

/** Drawer "Tìm hiểu công ty" — chính sách (KnowledgeDocument domain POLICY) gom theo 5 nhóm
 * chuẩn (COMPANY/HR/SECURITY/BENEFIT/WORKING_RULE) thay vì 1 danh sách phẳng — trước đây 18+
 * tài liệu dồn chung 1 cục rất khó quét mắt. Mỗi nhóm có header icon màu + đếm số lượng riêng,
 * bên trong chỉ còn title + nút đọc (bỏ dòng mô tả lặp lại y hệt ở mọi thẻ — không mang thêm
 * thông tin). LUÔN chỉ xem (không Sửa/Xoá/Thêm — do HR quản lý qua Phase 3, không phải
 * TemplateTask của PM). Bấm "Đọc tài liệu" mở modal xem trước ngay trong app. */
export function CompanyCoreDrawer({ documents, onClose }: CompanyCoreDrawerProps) {
  const t = useTranslations("pmUi");
  const [previewDoc, setPreviewDoc] = useState<KnowledgeDocumentResponseDTO | null>(null);

  const extraCategories = Array.from(new Set(documents.map((d) => d.policy_category))).filter(
    (c) => !POLICY_CATEGORY_ORDER.includes(c),
  );
  const orderedCategories = [...POLICY_CATEGORY_ORDER, ...extraCategories];

  return (
    <>
      <PmDrawer
        eyebrow={<PmTag>{t("companyCore")}</PmTag>}
        title={t("categoryCompany")}
        onClose={onClose}
        footer={
          <p className={drawerStyles.readOnlyNote}>
            HR owns this category and it applies to every project — PMs have read-only access.
          </p>
        }
      >
        {documents.length === 0 ? (
          <p className={drawerStyles.emptyNote}>{t("noPolicyDocuments")}</p>
        ) : (
          orderedCategories.map((category) => {
            const meta = POLICY_CATEGORY_META[category];
            const docsInCategory = documents.filter((d) => d.policy_category === category);
            return (
              <section key={category} className={styles.group}>
                <div className={styles.groupHead}>
                  <span
                    className={`${styles.groupIcon} ${styles[VARIANT_ICON_CLASS[meta.variant]]}`}
                  >
                    <PmIcon name={meta.icon} size={14} />
                  </span>
                  <b>{t(meta.labelKey)}</b>
                  <PmTag>{docsInCategory.length} documents</PmTag>
                </div>

                {docsInCategory.length === 0 ? (
                  <p className={drawerStyles.emptyNote}>{t("noPoliciesInCategory")}</p>
                ) : (
                  docsInCategory.map((doc) => (
                    <div key={doc.document_id} className={styles.docCard}>
                      <span className={styles.docTitle}>{doc.title}</span>
                      <button
                        type="button"
                        className={styles.readLink}
                        onClick={() => setPreviewDoc(doc)}
                      >
                        <PmIcon name="doc" size={12} />
                        Read document
                      </button>
                    </div>
                  ))
                )}
              </section>
            );
          })
        )}
      </PmDrawer>

      {previewDoc && (
        <DocumentPreviewModal
          title={previewDoc.title}
          sourceUrl={previewDoc.source_url}
          onClose={() => setPreviewDoc(null)}
        />
      )}
    </>
  );
}
