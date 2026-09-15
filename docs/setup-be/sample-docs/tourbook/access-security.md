# TourBooking Service — Access & Security

## Đặc thù bảo mật của TourBooking
Khác với PhoneShop (chỉ có nội bộ công ty truy cập hệ thống), TourBooking có thêm 1 nhóm người dùng ngoài công ty truy cập trực tiếp vào hệ thống: **đối tác lữ hành** qua Partner Portal. Đây là bề mặt tấn công (attack surface) lớn hơn cần cân nhắc kỹ — mọi input từ Partner Portal đều được coi là **không tin cậy** ở mức độ tương đương input từ khách hàng thông thường, không có ngoại lệ dù đối tác đã được xác thực.

## Xin quyền truy cập
| Hệ thống | Cách xin | Ai duyệt | Thời gian xử lý |
|---|---|---|---|
| Repo GitHub (team `tourbook-backend`) | PM thêm qua GitHub Org settings | PM | Trong ngày làm việc đầu |
| AWS Console (read-only staging) | Xin qua IT theo form chuẩn, MFA bắt buộc | IT + Tech Lead | 1-2 ngày làm việc |
| Elasticsearch Kibana | Truy cập qua VPN nội bộ, credential riêng theo từng người (không dùng chung tài khoản) | Tech Lead | 1 ngày làm việc |
| Partner Portal (test account) | Tạo tài khoản test riêng qua script seed, KHÔNG dùng tài khoản đối tác thật để test | Tự làm, không cần duyệt | Ngay lập tức |
| Database production | Qua bastion host, audit log đầy đủ, chỉ Lead/on-call | Engineering Manager | Xét duyệt riêng |
| Opsgenie on-call access | Tự động khi vào lịch on-call rotation | Tech Lead | Theo lịch on-call |

## Quy tắc bảo mật
- Spring Security filter chain bắt buộc áp dụng trên mọi endpoint trừ `/auth/**` (login/register) và `/actuator/health` (health check cho load balancer) — không có ngoại lệ khác, kể cả endpoint tưởng chừng vô hại như `GET /api/tours` cũng qua filter (dù không yêu cầu login, vẫn qua rate limiting).
- **Xác thực đối tác tách biệt hoàn toàn với xác thực khách hàng**: dùng 2 loại JWT khác nhau với `audience` claim khác nhau, đảm bảo token của đối tác không thể dùng để gọi API dành cho khách hàng và ngược lại — tránh lỗi privilege escalation nếu 1 bên bị lộ token.
- Token API đối tác lữ hành (Partner API key, dùng cho tích hợp server-to-server nếu đối tác có hệ thống riêng) có thời hạn 90 ngày, tự động gửi email nhắc gia hạn trước 7 ngày, tự động vô hiệu hoá nếu không gia hạn (không gia hạn ngầm định vô thời hạn).
- Mọi input từ Partner Portal (giá tour, số chỗ, mô tả) đều validate nghiêm ngặt ở tầng Bean Validation (`@Valid`) VÀ validate lại lần nữa ở tầng service — không tin tưởng chỉ validation ở 1 lớp. Riêng thay đổi giá có chênh lệch bất thường (>50% so với giá hiện tại) yêu cầu xác nhận 2 bước, bài học rút ra từ sự cố tháng 06/2025 (xem `overview.md`).
- Không log thông tin thẻ thanh toán hay số CCCD/hộ chiếu (một số tour yêu cầu thông tin này để làm thủ tục) ra application log, kể cả ở log level DEBUG — các trường này được đánh dấu `@Sensitive` custom annotation, tự động mask khi serialize log qua Logback custom converter.
- Rate limiting riêng cho Partner Portal API (60 request/phút/đối tác) tách biệt với rate limiting cho khách hàng thông thường (120 request/phút/user), tránh 1 đối tác có hệ thống tích hợp lỗi (gọi API liên tục do bug) làm ảnh hưởng tới trải nghiệm khách hàng.

## Compliance
Thông tin CCCD/hộ chiếu khách hàng cung cấp cho một số tour (yêu cầu làm thủ tục xuất cảnh/vé máy bay) được mã hoá tại tầng ứng dụng và có thời hạn lưu trữ giới hạn (tự động xoá sau 90 ngày kể từ ngày kết thúc tour, trừ trường hợp có yêu cầu pháp lý khác). Tuân theo Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân.

## Liên hệ khi có sự cố bảo mật
Báo Security team qua kênh #security-incident kèm mức độ ảnh hưởng ước tính (bao nhiêu đối tác/khách hàng bị ảnh hưởng nếu biết), không tự xử lý âm thầm dưới bất kỳ hình thức nào — kể cả khi tưởng chừng đã khắc phục xong, vẫn cần báo cáo đầy đủ để Security team đánh giá có cần thông báo cho các bên liên quan hay không.
