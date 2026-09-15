import type { TemplateVersionResponseDTO } from "@/features/project-management/dto/responseDTO/templateVersion.response";
import { useLocale, useTranslations } from "next-intl";
import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import { PmButton } from "@/features/project-management/components/ui/PmButton";
import { PmPill } from "@/features/project-management/components/ui/PmPill";
import tableStyles from "@/features/project-management/components/ui/PmTable.module.scss";

import styles from "./VersionTable.module.scss";

function formatDate(iso: string, locale: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString(locale === "vi" ? "vi-VN" : "en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

type VersionTableProps = {
  versions: TemplateVersionResponseDTO[];
  selectedVersionId: number | null;
  actionLoading: boolean;
  onView: (version: TemplateVersionResponseDTO) => void;
  onApprove: (version: TemplateVersionResponseDTO) => void;
  onCloneFrom: (version: TemplateVersionResponseDTO) => void;
};

/** Bảng lịch sử version — mỗi hàng có sẵn hành động phù hợp trạng thái, không cần nút "Tạo phiên
 * bản mới" rời ở đầu trang nữa:
 * - DRAFT: Duyệt (chuyển DRAFT -> APPROVED) + Nhân bản + Xem
 * - APPROVED: Nhân bản + Xem (đã là bản đang áp dụng, không cần duyệt)
 * - ARCHIVED: Duyệt lại (chuyển thẳng ARCHIVED -> APPROVED tại chỗ, KHÔNG tạo version mới — cùng
 *   API `approve` với DRAFT, backend đã cho phép cả 2 nguồn trạng thái) + Nhân bản + Xem
 * Xem/Duyệt/Duyệt lại đều báo lên component cha để mở modal xác nhận trước, không đổi trạng
 * thái/chuyển view ngay lập tức. */
export function VersionTable({
  versions,
  selectedVersionId,
  actionLoading,
  onView,
  onApprove,
  onCloneFrom,
}: VersionTableProps) {
  const t = useTranslations("pmUi");
  const locale = useLocale();
  if (versions.length === 0) return null;

  return (
    <div className={tableStyles.tableWrap}>
      <table className={tableStyles.table}>
        <thead>
          <tr>
            <th>{t("version")}</th>
            <th>{t("status")}</th>
            <th>{t("created")}</th>
            <th>{t("actions")}</th>
          </tr>
        </thead>
        <tbody>
          {versions.map((v) => {
            const isSelected = v.version_id === selectedVersionId;
            const canApprove = v.status === "DRAFT" || v.status === "ARCHIVED";
            return (
              <tr key={v.version_id} className={isSelected ? styles.selectedRow : undefined}>
                <td className={tableStyles.cellMain} data-label={t("version")}>
                  v{v.version_no}
                </td>
                <td data-label={t("status")}>
                  {v.status === "DRAFT" && <PmPill variant="progress">{t("statusDraft")}</PmPill>}
                  {v.status === "APPROVED" && (
                    <PmPill variant="success">
                      <PmIcon name="check2" size={11} />
                      {t("statusInUse")}
                    </PmPill>
                  )}
                  {v.status === "ARCHIVED" && (
                    <PmPill variant="neutral">{t("statusArchived")}</PmPill>
                  )}
                </td>
                <td className={tableStyles.cellSub} data-label={t("created")}>
                  {formatDate(v.created_at, locale)}
                </td>
                <td data-label={t("actions")}>
                  <div className={styles.rowActions}>
                    {canApprove && (
                      <PmButton
                        size="sm"
                        variant="ghost"
                        className={styles.approveBtn}
                        disabled={actionLoading}
                        onClick={() => onApprove(v)}
                      >
                        <PmIcon name="check2" size={12} />
                        {v.status === "ARCHIVED" ? t("reapprove") : t("approve")}
                      </PmButton>
                    )}
                    <PmButton
                      size="sm"
                      variant="ghost"
                      disabled={actionLoading}
                      onClick={() => onCloneFrom(v)}
                    >
                      <PmIcon name="plus" size={12} />
                      {t("duplicate")}
                    </PmButton>
                    <PmButton size="sm" variant="ghost" onClick={() => onView(v)}>
                      <PmIcon name="eye" size={13} />
                      {t("view")}
                    </PmButton>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
