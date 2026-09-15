# FurniStore — Coding Convention

## Triết lý chung
Team nhỏ (5 kỹ sư), ưu tiên tốc độ phát triển và giảm boilerplate hơn là quy trình phức tạp — nhưng vẫn giữ nghiêm ngặt ở những chỗ ảnh hưởng trực tiếp tới tiền/dữ liệu khách hàng (thanh toán, thông tin giao hàng).

## JavaScript/Node.js style
- Format + lint bằng ESLint (config `airbnb-base` tuỳ chỉnh thêm vài rule) + Prettier, chạy tự động qua Husky pre-commit hook.
- Đặt tên file: `kebab-case` (`shipping-fee.service.js`), biến/hàm `camelCase`, class `PascalCase`, hằng số `UPPER_SNAKE_CASE`.
- Bắt buộc dùng `async/await`, không dùng `.then()` chain trong code mới (code cũ còn sót lại đang dọn dần, không bắt buộc sửa hết ngay khi không liên quan tới task đang làm).
- Không dùng `var`, chỉ `const`/`let`. Ưu tiên `const` mặc định, chỉ dùng `let` khi thực sự cần reassign.
- Destructuring object/array khi hợp lý để code ngắn gọn hơn, nhưng không lạm dụng tới mức khó đọc (nested destructuring quá 2 cấp nên tách ra biến trung gian).

## TypeScript hoá dần (đang chuyển đổi)
Dự án khởi đầu bằng JavaScript thuần, từ Q2/2025 team quyết định chuyển dần sang TypeScript cho module mới (đã áp dụng cho `delivery` và `showroom`), module cũ (`catalog`, `cart`, `order`) vẫn JavaScript, sẽ chuyển dần khi có thời gian refactor — không bắt buộc convert toàn bộ ngay lập tức, ưu tiên tính năng mới dùng TypeScript trước.

## Git
- Nhánh đặt tên `feature/FURNI-<số ticket>-mo-ta-ngan`.
- Commit message theo Conventional Commits (`feat:`, `fix:`, `chore:`, `refactor:`).
- PR bắt buộc 1 approve + CI xanh (lint + test) mới merge, dùng squash merge.
- Riêng PR liên quan `shipping` hoặc `delivery` module (2 phần có sự cố từng xảy ra) nên có thêm 1 approve thứ 2 nếu thay đổi lớn (>200 dòng), dù không bắt buộc cứng qua branch protection — team tự giác áp dụng dựa trên bài học từ 2 sự cố đã xảy ra.

## Review checklist
- [ ] Input từ client có schema `zod` validate chưa.
- [ ] Lỗi nghiệp vụ throw `AppError`, không throw string/lỗi thường.
- [ ] Nếu đổi Prisma schema, đã tạo migration và test cả 2 chiều (up/down) chưa.
- [ ] Nếu gọi API bên ngoài mới (đối tác vận chuyển, dịch vụ khác), đã có timeout + xử lý lỗi rõ ràng chưa (xem bài học sự cố tháng 04/2025 trong `overview.md`).
- [ ] Nếu thêm field mới cho MongoDB document, đã cân nhắc dữ liệu cũ không có field này sẽ được xử lý thế nào (MongoDB không tự thêm default value cho document đã tồn tại như migration Postgres).

## SLA review PR
Team nhỏ nên không có SLA cứng bằng giờ như 2 dự án kia — quy ước chung: cố gắng review trong ngày làm việc, PR gắn label `urgent` (hotfix) thì review ngay khi thấy thông báo, bất kể đang làm gì.
