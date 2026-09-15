/** 1 task sắp/đã trễ hạn — cho dropdown chuông thông báo. Tính trên mỗi lần đọc, không có bảng
 * Notification/đã đọc-chưa đọc riêng (xem notification_response_dto.py phía backend). */
export type TaskNotificationResponseDTO = {
  plan_task_id: number;
  title: string;
  due_at: string;
  is_overdue: boolean;
  engineer_name: string | null;
  membership_id: number | null;
};
