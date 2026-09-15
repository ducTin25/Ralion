# Ralion UI Design System

Đây là chuẩn UI cấp repository cho Ralion. Tài liệu
`docs/PM/RALION_UI_DESIGN_GUIDE.md` là nguồn thiết kế ban đầu; mọi màn hình mới
phải dùng các token và pattern dưới đây thay vì tạo một hệ style theo role.

## Nguyên tắc

- Light theme là mặc định; dark theme dùng cùng semantic token.
- Sidebar trái cố định, topbar gọn, content co giãn một cột. Không ẩn nội dung
  chính chỉ vì viewport hẹp.
- Bo góc nhỏ và phẳng: 5px cho control/tag/avatar, 6px cho input/bubble, 8px cho
  card/modal/drawer. Chỉ status dot nhỏ được tròn tuyệt đối.
- Mỗi trang có page icon, title, subtitle và action area. Drawer dùng cho chi
  tiết dài; modal dùng cho form/hành động ngắn.
- Màu accent chỉ thể hiện brand/selection/action. Trạng thái phải dùng success,
  warning hoặc critical riêng.

## Tokens

```css
--bg: #f5f6fa;
--surface: #ffffff;
--surface-2: #eef0f7;
--surface-3: #e4e7f1;
--border: #dee2ec;
--border-strong: #c7ccdc;
--ink: #171a22;
--ink-2: #5b6172;
--ink-3: #8b90a0;
--accent: #2657d9;
--accent-2: #5c8df6;
--accent-hover: #1d46b8;
--accent-bg: #e8effd;
--success: #157f53;
--success-bg: #e1f5ec;
--success-border: #b7e4ce;
--warning: #a8660a;
--warning-bg: #fcefda;
--warning-border: #f1d3a0;
--critical: #b23a3a;
--critical-bg: #fbe8e8;
--critical-border: #efc2c2;
--radius-sm: 5px;
--radius-md: 6px;
--radius-lg: 8px;
--sp-1: 4px;
--sp-2: 8px;
--sp-3: 12px;
--sp-4: 16px;
--sp-5: 20px;
--sp-6: 24px;
--sp-7: 32px;
--shadow-sm: 0 1px 2px rgba(23, 26, 34, 0.06);
--shadow-md:
  0 4px 16px rgba(23, 26, 34, 0.08), 0 1px 3px rgba(23, 26, 34, 0.06);
--shadow-lg: 0 16px 48px rgba(23, 26, 34, 0.18);
--ease: cubic-bezier(0.4, 0, 0.2, 1);
--font-ui:
  -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
```

Dark theme đổi surface/ink/border và tăng độ sáng semantic color theo guide gốc;
component không được hard-code màu theme-specific bên ngoài token.

## Typography và component

- Page title: `22px/700`; section title: `15px/700`; body: `13–13.5px`;
  caption: `11–12px`.
- Button có default, primary, ghost và danger; active scale `0.97`; disabled phải
  giải thích bằng text hoặc tooltip.
- Card dùng surface, border, radius 8px và shadow nhỏ. Table header dùng
  `surface-2`; row clickable có hover và keyboard focus.
- Pill là trạng thái semantic; tag là metadata trung tính. Avatar vuông bo 5px.
- Icon là SVG sprite stroke-based, 14–17px trong navigation/control; không dùng
  emoji hoặc icon font.
- Toast xác nhận mutation; lỗi liên quan form hiển thị gần field và có summary
  đọc được bởi screen reader.

## Engineer Portal

- Sidebar: vai trò “Kỹ sư tham gia dự án”; menu `Checklist & Plan`, `Ralion Chat`
  và `Blocker của tôi`.
- Project switcher xuất hiện trước portal nếu user có nhiều membership và tiếp
  tục hiện trong topbar để đổi project. Luồng chọn trước portal chỉ có một màn
  hình canonical là `/select-project`; sau khi đã chọn, portal nhận `project`
  context từ redirect và không hiển thị thêm picker chặn toàn trang.
- Checklist nhóm theo category, giữ thứ tự template. Progress dùng task bắt buộc;
  task tùy chọn có tag riêng.
- Task row thể hiện status, title, due date và dependency lock. Click mở Task
  Detail drawer có mục tiêu, hướng dẫn, tài liệu, dependency, deadline và action.
- Open blocker là trạng thái phụ của task, không thay thế task status. Trang
  Blocker hiển thị task, category, reason, reported time và canonical status;
  không hiển thị routing/SLA trong MVP.
- `FIRST_TASK` và `FIRST_PR` hiện không xuất hiện trong Engineer Portal; khi phạm
  vi được mở lại phải bổ sung flow, gate và trạng thái rõ ràng trước khi thêm menu.

## Responsive, motion và accessibility

- Desktop chuẩn: sidebar 224–240px, topbar 54–58px, content tối đa 1400px.
- Dưới 900px, sidebar có thể thành drawer nhưng navigation và project context
  vẫn truy cập được; không ẩn cột/nội dung mà không có đường mở lại.
- Interaction nhỏ 120–200ms; drawer/modal 250–350ms; mọi transition dùng
  `--ease`. Tắt animation không thiết yếu khi reduced motion.
- Focus ring phải nhìn rõ trên cả light/dark. Modal/drawer trap focus, đóng bằng
  Escape, trả focus về trigger và có accessible name.
