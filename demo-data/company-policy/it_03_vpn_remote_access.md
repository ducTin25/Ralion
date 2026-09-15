# Chính sách VPN và Truy cập Từ xa

- **Mã tài liệu:** IT-POL-003
- **Phiên bản:** 2.7 — Ngày hiệu lực: 01/01/2026
- **Bộ phận ban hành:** Phòng CNTT, thẩm định bởi Phòng An toàn Thông tin
- **Phạm vi áp dụng:** Mọi truy cập hệ thống nội bộ từ ngoài mạng văn phòng
- **Tài liệu liên quan:** IT-POL-002 (Tài khoản), SEC-POL-002 (Phân loại dữ liệu), Chính sách WFH của HR

## 1. Mục đích

Đảm bảo nhân viên làm việc từ xa truy cập hệ thống nội bộ an toàn, ổn định; mọi kết nối từ ngoài đều được xác thực, mã hóa và ghi log.

## 2. Nguyên tắc chung

- Truy cập hệ thống nội bộ (mạng nội bộ, database, server dev/staging, công cụ quản trị) từ ngoài văn phòng **bắt buộc qua VPN công ty**.
- Các dịch vụ SaaS công ty (email, chat, drive) truy cập trực tiếp được nhưng phải từ thiết bị đã đăng ký (công ty cấp hoặc BYOD có MDM) và luôn kèm MFA.
- Nghiêm cấm: mở port công khai từ máy cá nhân vào hệ thống nội bộ, dùng VPN/proxy bên thứ ba để vượt kiểm soát, chia sẻ cấu hình VPN cho người khác.

## 3. Đăng ký và cấp quyền VPN

1. Quyền VPN cấp mặc định cho nhân viên chính thức khi onboarding; nhà thầu cần Project Owner đề xuất và Security duyệt.
2. IT gửi hướng dẫn cài client VPN chuẩn (không dùng client ngoài danh mục) và cấu hình profile theo nhóm quyền.
3. Phân vùng truy cập theo vai trò (split by group): nhân viên thường chỉ tới dải hệ thống văn phòng; kỹ sư tới môi trường dev/staging theo project; quyền tới production theo quy trình đặc quyền riêng.
4. Quyền VPN tự thu hồi khi nghỉ việc, hết hạn hợp đồng hoặc 90 ngày không sử dụng.

## 4. Yêu cầu đối với thiết bị và môi trường làm việc từ xa

- Thiết bị: bật mã hóa ổ đĩa, phần mềm endpoint đang chạy, hệ điều hành cập nhật bản vá trong 14 ngày kể từ khi phát hành.
- VPN client tự kiểm tra tuân thủ (posture check) trước khi cho kết nối; máy không đạt sẽ bị chặn kèm hướng dẫn khắc phục.
- Không làm việc với dữ liệu Confidential trở lên qua **Wi-Fi công cộng không mật khẩu**; nếu bắt buộc, dùng phát 4G/5G cá nhân hoặc VPN luôn-bật.
- Màn hình làm việc ở nơi công cộng: dùng phim chống nhìn trộm, khóa máy khi rời chỗ.

## 5. Sử dụng và giới hạn

- Phiên VPN tự ngắt sau **12 giờ** hoặc 30 phút không hoạt động; đăng nhập lại cần MFA.
- Không tải/chia sẻ dữ liệu dung lượng lớn không phục vụ công việc qua VPN (ảnh hưởng băng thông chung).
- Toàn bộ kết nối VPN được ghi log (thời gian, tài khoản, IP nguồn, tài nguyên truy cập) phục vụ điều tra sự cố; log lưu tối thiểu 12 tháng.

## 6. Xử lý sự cố VPN

### 6.1. Tự kiểm tra trước khi tạo ticket

1. Kiểm tra Internet (mở trang web bất kỳ).
2. Thoát hẳn VPN client và kết nối lại.
3. Khởi động lại máy.
4. Kiểm tra thông báo bảo trì trên kênh #it-announcements.

### 6.2. Tạo ticket

- Gửi IT Service Desk kèm: ảnh chụp màn hình lỗi, thời điểm lỗi, mạng đang dùng (nhà/công cộng/4G), đã thử các bước tự kiểm tra chưa.
- Phân mức: lỗi cá nhân → P3 (SLA 4 giờ); lỗi diện rộng nhiều người → P2 (SLA 1 giờ, thông báo trên kênh chung).

## 7. Truy cập đặc biệt

- **Truy cập production:** chỉ qua bastion host/jump server với tài khoản đặc quyền, phê duyệt theo phiên (just-in-time), ghi hình phiên thao tác.
- **Bên thứ ba (vendor):** truy cập qua tài khoản riêng có thời hạn, giới hạn đúng hệ thống cần thiết, có nhân viên công ty giám sát phiên đầu tiên.
- **Làm việc từ nước ngoài:** đăng ký trước với IT và quản lý ít nhất 3 ngày (một số quốc gia bị chặn theo chính sách rủi ro); công ty có thể từ chối với hệ thống nhạy cảm.

## 8. Kênh hỗ trợ và SLA

| Loại yêu cầu | Mức ưu tiên | SLA xử lý |
|---|---|---|
| Không kết nối được VPN (cá nhân) | P3 | 4 giờ làm việc |
| VPN lỗi diện rộng | P2 | 1 giờ |
| Cấp quyền VPN mới / mở rộng vùng truy cập | P4 | 2 ngày làm việc (kèm duyệt Security) |
| Truy cập production khẩn cấp | P1 | 30 phút (quy trình just-in-time) |
| Đăng ký làm việc từ nước ngoài | P4 | 3 ngày làm việc |

**Từ khóa định tuyến về IT:** VPN, remote, làm việc từ xa, WFH, kết nối, mạng, không vào được hệ thống, server dev, staging, bastion, wifi, truy cập từ xa, làm việc nước ngoài.


## 9. Kiến trúc truy cập từ xa

VPN là control mặc định cho hệ thống nội bộ legacy; hệ thống mới có thể dùng ZTNA/application proxy đã được Security phê duyệt. Dù dùng công nghệ nào, quyết định truy cập phải dựa trên danh tính, trạng thái thiết bị và Access Scope, không chỉ dựa trên việc “đã vào mạng nội bộ”.

## 10. Device posture

Posture check tối thiểu có thể gồm: MDM enrollment, disk encryption, EDR healthy, OS không quá hạn patch, screen lock và không có dấu hiệu jailbreak/root trái phép. Khi posture fail, hệ thống ưu tiên quarantine/remediation thay vì cho truy cập rộng rồi mới cảnh báo.

## 11. Split tunneling và traffic

Split tunnel chỉ bật theo thiết kế được IT/Security phê duyệt. Traffic tới hệ thống nhạy cảm luôn đi qua kênh kiểm soát của công ty. Không tự cài VPN/proxy cá nhân để thay đổi tuyến hoặc vượt web filtering.

## 12. Làm việc từ quốc gia/vùng rủi ro

Yêu cầu đi công tác/làm việc từ nước ngoài phải nêu quốc gia, thời gian, hệ thống cần truy cập. IT/Security có thể yêu cầu thiết bị “travel laptop”, hạn chế dữ liệu local, tăng MFA hoặc chặn một số hệ thống. Quyết định không chỉ dựa trên kỹ thuật mà có thể cần HR/Legal xác nhận.

## 13. Truy cập vendor

Vendor không dùng account của nhân viên. Tài khoản vendor phải định danh được cá nhân/tổ chức, có sponsor nội bộ, hết hạn tự động, giới hạn hệ thống và được log. Với quyền nhạy cảm, áp dụng JIT và session recording nếu nền tảng hỗ trợ.

## 14. Remote support

IT chỉ dùng công cụ remote support trong danh mục Approved. Người dùng được thông báo khi phiên support bắt đầu; quyền điều khiển kết thúc khi ticket hoàn tất. Không yêu cầu người dùng đọc mật khẩu/OTP cho kỹ thuật viên.
