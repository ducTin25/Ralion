# Chính sách Công nghệ Thông tin (IT Policy)

- **Mã tài liệu:** IT-POL-000
- **Phiên bản:** 3.0 — Hiệu lực: 01/01/2026
- **Bộ phận ban hành:** Phòng CNTT (IT Department)
- **Phạm vi áp dụng:** Toàn bộ nhân viên sử dụng thiết bị và hệ thống của công ty

## 1. Cấp phát thiết bị và tài khoản

- Nhân viên mới được cấp laptop, tài khoản email và tài khoản hệ thống nội bộ trong ngày làm việc đầu tiên.
- Yêu cầu cấp thêm thiết bị (màn hình, bàn phím, license phần mềm) gửi qua IT Service Desk, cần phê duyệt của Trưởng bộ phận nếu vượt ngân sách chuẩn.
- Khi nghỉ việc, tài sản và quyền truy cập được thu hồi theo **HR-POL-003**, **IT-POL-001** và **SEC-POL-001**; trường hợp nghỉ việc rủi ro cao có thể thu hồi quyền ngay tại thời điểm quyết định chấm dứt có hiệu lực.

## 2. Tài khoản, mật khẩu và VPN

- Tiêu chuẩn mật khẩu, MFA và vòng đời tài khoản tuân theo **IT-POL-002**. Tài khoản thường không bị buộc đổi mật khẩu theo chu kỳ nếu không có dấu hiệu lộ; tài khoản đặc quyền áp dụng kiểm soát mạnh hơn theo IT-POL-002.
- Quên mật khẩu / khóa tài khoản: reset qua IT Service Desk, SLA 4 giờ làm việc.
- Truy cập hệ thống nội bộ từ xa bắt buộc qua VPN công ty. Lỗi VPN báo IT Service Desk kèm ảnh chụp màn hình.

## 3. Phần mềm và môi trường phát triển

- Chỉ cài phần mềm trong danh mục được phê duyệt; phần mềm ngoài danh mục phải xin cấp phép qua IT.
- Yêu cầu quyền truy cập repository, CI/CD, database dev/staging: tạo ticket kèm tên project và xác nhận của Project Owner.
- Sự cố môi trường (build fail do hạ tầng, server dev down, hết dung lượng): báo IT với mức độ ưu tiên.

## 4. Phân loại mức độ ưu tiên sự cố

| Mức | Mô tả | SLA phản hồi | SLA xử lý |
|---|---|---|---|
| P1 | Hệ thống production ngừng hoạt động | 15 phút | 4 giờ |
| P2 | Ảnh hưởng nhóm (server dev, VPN toàn công ty) | 1 giờ | 1 ngày làm việc |
| P3 | Ảnh hưởng cá nhân (thiết bị, tài khoản, phần mềm) | 4 giờ | 2 ngày làm việc |
| P4 | Yêu cầu cấp phát, không khẩn cấp | 1 ngày | 5 ngày làm việc |

**Từ khóa định tuyến về IT:** laptop, thiết bị, tài khoản, mật khẩu, VPN, email, phần mềm, license, server, repository, CI/CD, mạng, wifi, máy in, IT Service Desk.


## 5. Nguyên tắc quản trị CNTT

IT-POL-000 là policy khung. Quy tắc chuyên biệt được ưu tiên theo thứ tự: policy chuyên biệt → standard/runbook được policy dẫn chiếu → tài liệu hướng dẫn người dùng. Tài liệu hướng dẫn không được tự tạo yêu cầu mới trái policy.

Các nguyên tắc:

- thiết bị, tài khoản và phần mềm được quản lý theo vòng đời và có owner;
- thay đổi production phải có kiểm soát và khả năng rollback;
- sự cố ưu tiên khôi phục dịch vụ, sau đó xử lý nguyên nhân gốc;
- quyền đặc quyền tách khỏi tài khoản dùng hằng ngày;
- mọi ngoại lệ kỹ thuật cần có risk owner, phê duyệt, thời hạn và kế hoạch đóng ngoại lệ.

## 6. Bản đồ policy IT

| Nhu cầu | Nguồn chuẩn |
|---|---|
| Laptop, phụ kiện, BYOD | IT-POL-001 |
| Account, password, MFA | IT-POL-002 |
| VPN/remote access | IT-POL-003 |
| Software/license/OSS | IT-POL-004 |
| Incident hạ tầng | IT-POL-005 |
| Change/deploy | IT-POL-006 |
| LAN/WiFi/network | IT-POL-007 |
| Backup/DR | IT-POL-008 |

## 7. Service ownership và support model

Mỗi dịch vụ quan trọng phải có Service Owner, technical owner/on-call (nếu cần), mức criticality và runbook tối thiểu. IT Service Desk là cửa vào chuẩn cho service request; incident khẩn cấp sử dụng kênh on-call tương ứng nhưng vẫn phải tạo incident record để theo dõi.

## 8. Quản trị tài liệu

- Owner: Head of IT.
- Rà soát: ít nhất hằng năm và sau major incident/thay đổi kiến trúc đáng kể.
- Metrics tối thiểu: SLA, backlog, incident trend, change failure rate, asset/license hygiene, backup restore success.
