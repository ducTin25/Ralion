"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import { PmButton } from "@/features/project-management/components/ui/PmButton";
import { PmErrorText, PmField, PmInput } from "@/features/project-management/components/ui/PmField";
import { PmModal } from "@/features/project-management/components/ui/PmModal";
import {
  recommendedPlanStartVietnamLocal,
  vietnamLocalInputToBackendString,
} from "@/features/project-management/lib/formatDateTime";

type GenerateStartTimeModalProps = {
  memberName: string;
  onConfirm: (startAt: string | undefined) => void;
  onClose: () => void;
};

/** Modal chọn giờ bắt đầu, mở ra ngay khi PM bấm "Sinh plan" cho 1 thành viên — trước khi gọi API.
 *
 * Ô ngày giờ pre-fill sẵn giờ ĐỀ XUẤT (giờ hiện tại nếu đang trong giờ hành chính, hoặc 09:00 ngày
 * làm việc kế tiếp nếu bấm ngoài giờ/cuối tuần — xem `recommendedPlanStartVietnamLocal`). PM không
 * sửa gì thì bấm "Sinh plan" là dùng luôn giá trị đề xuất đó, đúng yêu cầu gốc: "mặc định thì giống
 * recommend, nếu không sửa thì tiến hành sinh plan theo giờ đó".
 *
 * Mỗi task sau đó có hạn = mốc này cộng dồn `estimated_minutes` theo `display_order` (xem
 * `compute_due_dates` ở backend) — đây chính là giờ BẮT ĐẦU của task đầu tiên trong plan.
 */
export function GenerateStartTimeModal({
  memberName,
  onConfirm,
  onClose,
}: GenerateStartTimeModalProps) {
  const t = useTranslations("pmUi");
  const [startAtInput, setStartAtInput] = useState(() => recommendedPlanStartVietnamLocal());
  const [error, setError] = useState<string | null>(null);

  function handleConfirm() {
    const startAt = vietnamLocalInputToBackendString(startAtInput);
    if (startAtInput && startAt === null) {
      setError(t("invalidStartTime"));
      return;
    }
    onConfirm(startAt ?? undefined);
  }

  return (
    <PmModal
      title={t("chooseStartTime")}
      icon="check-circle"
      tone="primary"
      onClose={onClose}
      footer={
        <>
          <PmButton onClick={onClose}>{t("cancel")}</PmButton>
          <PmButton variant="primary" onClick={handleConfirm}>
            {t("generatePlan")}
          </PmButton>
        </>
      }
    >
      <p>{t("startTimeHelp", { member: memberName })}</p>
      <PmField label={t("startTimeVietnam")}>
        <PmInput
          type="datetime-local"
          value={startAtInput}
          onChange={(e) => {
            setStartAtInput(e.target.value);
            setError(null);
          }}
        />
      </PmField>
      {error && <PmErrorText>{error}</PmErrorText>}
    </PmModal>
  );
}
