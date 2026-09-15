# TourBooking Service — Coding Convention

## Triết lý chung
Convention được thiết kế để mọi engineer, dù mới hay cũ, đọc code của người khác mà không cần hỏi "tại sao lại viết thế này" — nhất quán quan trọng hơn "cách hay nhất theo ý kiến cá nhân". Mọi bất đồng về style nên giải quyết bằng cách cập nhật rule chung (và tool tự động hoá), không phải tranh luận lặp lại trong từng PR.

## Java style
- Format theo Google Java Style Guide, kiểm tra tự động bằng Spotless trong Maven build (`./mvnw spotless:check` chạy trong CI, `./mvnw spotless:apply` để tự format trước khi commit).
- Đặt tên: `camelCase` cho method/biến, `PascalCase` cho class, hằng số `UPPER_SNAKE_CASE`. Package name toàn chữ thường, không gạch dưới.
- Interface không prefix `I` (ví dụ `TourRepository`, không phải `ITourRepository`) — theo convention chuẩn Java hiện đại, khác với 1 số codebase C#/cũ.
- Ưu tiên dùng `record` (Java 17+) cho DTO bất biến thay vì class thông thường với getter/setter — giảm boilerplate đáng kể.
- Không dùng `Optional` làm field trong entity JPA (Hibernate không hỗ trợ tốt), chỉ dùng `Optional` làm kiểu trả về của method ở tầng Service/Repository.
- Exception tự định nghĩa nên extend `RuntimeException` (unchecked), tránh checked exception gây "nhiễm" signature khắp nơi trong codebase — quyết định này khác với 1 số trường phái Java truyền thống, team đã thống nhất từ đầu dự án.

## Cấu trúc test
Đặt tên method test theo pattern `should_<kết quả mong đợi>_when_<điều kiện>`, ví dụ `should_throwInsufficientSeatsException_when_bookingExceedsAvailableSeats()`. Dùng AssertJ cho assertion (`assertThat(...)`), không dùng JUnit assertion cơ bản (`assertEquals`) vì AssertJ đọc tự nhiên hơn và có message lỗi rõ ràng hơn khi fail.

## Git
- Nhánh đặt tên `feature/TOUR-<số ticket Jira>-mo-ta-ngan`, ví dụ `feature/TOUR-456-fix-double-booking`.
- Commit message: bắt đầu bằng mã ticket Jira, ví dụ `TOUR-456: fix double booking khi 2 request cung luc dat cho cuoi`. Không bắt buộc Conventional Commits như PhoneShop (team này chọn convention riêng phù hợp với việc mọi thay đổi đều gắn với ticket Jira).
- PR bắt buộc 1 approve + build Maven xanh (test + Spotless) mới được merge, dùng **merge commit** thường (không squash) vì team muốn giữ lại lịch sử commit chi tiết trong quá trình phát triển 1 ticket lớn.
- Mọi PR liên quan tới `booking` hoặc `payment` package bắt buộc có ít nhất 1 approve từ Tech Lead, không được chỉ Senior thường approve — do đây là 2 package nhạy cảm nhất về tiền và uy tín.

## Review checklist
- [ ] Có test unit cho Service layer (Mockito), coverage không giảm.
- [ ] Không có N+1 query mới (kiểm tra bằng log SQL trong integration test, xem `codebase-guide.md`).
- [ ] Entity mới có Flyway migration kèm theo, đã test rollback (`./mvnw flyway:undo` trên môi trường local trước khi merge — lưu ý: Flyway Community Edition không hỗ trợ undo chính thức, team dùng migration riêng viết tay cho phần rollback quan trọng).
- [ ] Nếu thay đổi liên quan Partner Portal API, đã thông báo trước cho đội frontend Partner Portal (team riêng, không cùng team backend).
- [ ] Action nhạy cảm mới thêm đã gắn `@Auditable` annotation nếu cần ghi audit log.

## SLA review PR
Cam kết review trong 1 ngày làm việc (khác PhoneShop 4 giờ — team TourBook nhỏ hơn và có nhiều PR cần Tech Lead review kỹ do liên quan booking/payment). PR gắn label `urgent` (dùng cho hotfix production) được ưu tiên review trong 1 giờ.
