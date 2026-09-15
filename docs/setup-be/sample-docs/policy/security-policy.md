# Security Policy — Chính sách bảo mật chung

## Phạm vi áp dụng
Áp dụng cho toàn bộ nhân viên có quyền truy cập vào bất kỳ hệ thống nào của công ty (source code, database, hạ tầng cloud, công cụ nội bộ), bất kể đang tham gia dự án nào. Đây là chính sách nền tảng — mỗi dự án (PhoneShop, TourBooking, FurniStore...) có thể có thêm quy định bảo mật riêng chi tiết hơn (xem tài liệu Access & Security của từng dự án), nhưng không được thấp hơn tiêu chuẩn chung này.

## Quản lý tài khoản và xác thực
- Bắt buộc bật xác thực 2 lớp (2FA/MFA) cho toàn bộ tài khoản công việc: email công ty, GitHub, AWS Console, các công cụ nội bộ có hỗ trợ. Không có ngoại lệ, kể cả tài khoản cấp thấp.
- Mật khẩu tối thiểu 12 ký tự, kết hợp chữ hoa/thường/số/ký tự đặc biệt, không dùng lại mật khẩu đã dùng cho dịch vụ cá nhân bên ngoài.
- Dùng password manager công ty cấp (1Password) để lưu trữ mọi credential liên quan công việc — nghiêm cấm lưu mật khẩu trong file text, note, hoặc gửi qua chat không mã hoá.
- Tài khoản không sử dụng quá 90 ngày tự động bị khoá, cần liên hệ IT để mở lại kèm xác minh danh tính.

## Nguyên tắc phân quyền (Principle of Least Privilege)
Mọi truy cập hệ thống chỉ cấp ở mức tối thiểu cần thiết cho công việc hiện tại, không cấp "phòng khi cần sau này". Quyền truy cập production (database, AWS Console, server) luôn hạn chế nghiêm ngặt hơn nhiều so với staging/dev, và luôn đi kèm audit log đầy đủ (ghi lại ai truy cập, khi nào, làm gì). Khi đổi vai trò/dự án, quyền truy cập cũ không còn cần thiết phải được thu hồi trong vòng 3 ngày làm việc (trách nhiệm của quản lý trực tiếp đề xuất thu hồi kịp thời, không phải tự động).

## Thiết bị làm việc
Laptop công ty cấp bắt buộc cài MDM (Mobile Device Management) để IT có thể quản lý và xoá dữ liệu từ xa nếu thiết bị bị mất/thất lạc. Mã hoá ổ cứng toàn bộ (FileVault trên macOS, BitLocker trên Windows) bắt buộc bật ngay khi nhận máy. Không cài phần mềm không rõ nguồn gốc, không tắt trình diệt virus/bảo mật do IT cài sẵn.

## Quy tắc xử lý dữ liệu nhạy cảm
- Không bao giờ lưu dữ liệu khách hàng thật (email, số điện thoại, địa chỉ, thông tin thanh toán) trên máy cá nhân hoặc môi trường dev/staging dưới dạng dữ liệu thật — dùng dữ liệu giả lập/đã ẩn danh hoá (anonymized) cho mục đích test.
- Không chia sẻ dữ liệu nội bộ (kể cả ảnh chụp màn hình dashboard, log, cấu hình hệ thống) ra ngoài kênh nội bộ công ty dưới bất kỳ hình thức nào, kể cả với mục đích "chỉ hỏi ý kiến" trên diễn đàn công khai.
- Credential (API key, mật khẩu, token) tuyệt đối không commit vào git, không gửi qua email/chat thông thường — dùng công cụ quản lý secret chuyên dụng (AWS Secrets Manager, 1Password, biến môi trường CI/CD được mã hoá).

## Báo cáo sự cố bảo mật
Phát hiện lỗ hổng, rò rỉ dữ liệu, hoặc nghi ngờ truy cập trái phép — báo ngay lập tức qua kênh #security-incident, không tự ý xử lý hoặc công khai thông tin trước khi Security team xác nhận và có hướng dẫn cụ thể. Việc báo cáo sớm và trung thực được khuyến khích, kể cả khi sự cố do chính mình vô tình gây ra — công ty ưu tiên xử lý và khắc phục nhanh hơn là quy trách nhiệm, miễn không phải hành vi cố ý.

SLA phản hồi của Security team: 15 phút trong giờ hành chính, tối đa 1 giờ ngoài giờ hành chính (qua hệ thống on-call PagerDuty/Opsgenie tuỳ dự án).

## Truy cập hệ thống production
Chỉ Lead/PM (hoặc engineer đang trong ca on-call theo lịch) được duyệt quyền truy cập production, và mọi truy cập đều có audit log đầy đủ, lưu trữ tối thiểu 1 năm. Engineer thường chỉ được cấp quyền truy cập production tạm thời (time-boxed access, tự động thu hồi sau khoảng thời gian xác định, thường 8 giờ) khi cần debug sự cố khẩn cấp, và phải có xác nhận từ Tech Lead hoặc Engineering Manager trước khi cấp.

## Đào tạo bảo mật định kỳ
Toàn bộ nhân viên kỹ thuật tham gia buổi đào tạo bảo mật cơ bản (nhận diện phishing, quy tắc xử lý dữ liệu, quy trình báo cáo sự cố) trong tuần đầu onboarding, và khoá refresh hàng năm. Security team tổ chức diễn tập phishing giả lập định kỳ (không báo trước) để đánh giá mức độ nhận thức của nhân viên — đây không phải để "bắt lỗi" cá nhân mà để cải thiện đào tạo nếu tỷ lệ mắc bẫy còn cao.
