# Chính sách Mạng và Hạ tầng Văn phòng

- **Mã tài liệu:** IT-POL-007
- **Phiên bản:** 1.2 — Ngày hiệu lực: 01/01/2026
- **Bộ phận ban hành:** Phòng CNTT
- **Phạm vi áp dụng:** Toàn bộ hạ tầng mạng và thiết bị mạng dùng chung tại văn phòng công ty
- **Tài liệu tham chiếu:** IT-POL-003 (VPN và Truy cập Từ xa), IT-POL-005 (Sự cố hạ tầng), SEC-POL-001 (Phân quyền truy cập)

## 1. Mục đích

Đảm bảo hạ tầng mạng văn phòng (LAN, WiFi, thiết bị mạng dùng chung) hoạt động ổn định, phân vùng hợp lý theo mức độ tin cậy, và không trở thành điểm xâm nhập vào hệ thống nội bộ.

## 2. Phân vùng mạng (Network Segmentation)

| Vùng mạng (VLAN) | Đối tượng | Quyền truy cập |
|---|---|---|
| Corporate LAN | Máy tính nhân viên (dây/WiFi công ty) | Truy cập hệ thống nội bộ, drive, dev/staging theo Access Scope |
| Guest WiFi | Khách, đối tác đến làm việc | Chỉ ra Internet, không truy cập hệ thống nội bộ |
| IoT/Thiết bị dùng chung | Máy in, máy chiếu, camera, TV phòng họp | Cô lập, không truy cập Corporate LAN và ngược lại |
| Server nội bộ (on-prem, nếu có) | Server/thiết bị hạ tầng đặt tại văn phòng | Chỉ truy cập qua VPN/bastion theo IT-POL-003, không mở trực tiếp từ Corporate LAN |

## 3. WiFi khách (Guest WiFi)

- Cấp mật khẩu Guest WiFi tại lễ tân, đổi mật khẩu hằng tháng.
- **Không** dùng Guest WiFi để xử lý công việc công ty; nhân viên có khách cần demo hệ thống nội bộ dùng Corporate LAN qua thiết bị công ty.
- Guest WiFi giới hạn băng thông, tự ngắt phiên sau 8 giờ.

## 4. Thiết bị mạng dùng chung

- Máy in/máy chiếu/TV phòng họp: kết nối qua VLAN riêng, không cài phần mềm ngoài danh mục Approved (theo IT-POL-004) trên các thiết bị này.
- Nhân viên phát hiện thiết bị lạ kết nối vào mạng văn phòng (access point lạ, thiết bị không rõ nguồn gốc): báo IT ngay, không tự gỡ hoặc kết nối thử.
- Cấm tự ý cắm thêm access point/router cá nhân vào mạng văn phòng dưới mọi hình thức.

## 5. Bảo trì và giám sát hạ tầng

- Bảo trì mạng có kế hoạch tuân theo cửa sổ bảo trì chuẩn của IT-POL-005 (thứ Bảy 20h00–24h00).
- Hệ thống giám sát lưu lượng mạng cảnh báo bất thường (traffic spike, thiết bị lạ) tự động; Security được thông báo song song với IT.
- Log truy cập mạng lưu tối thiểu 12 tháng phục vụ điều tra sự cố.

## 6. Sự cố hạ tầng mạng

Phân loại và SLA theo IT-POL-005 (mất mạng toàn văn phòng = P1 hoặc P2 tùy phạm vi ảnh hưởng).

## 7. Kênh hỗ trợ và SLA

| Loại yêu cầu | Mức ưu tiên | SLA |
|---|---|---|
| Mất mạng toàn văn phòng | P1 | Theo IT-POL-005 (phản hồi 15 phút) |
| Mạng chậm một khu vực/tầng | P2 | Theo IT-POL-005 (phản hồi 1 giờ) |
| Cấp mật khẩu Guest WiFi | P4 | Tức thì tại lễ tân |
| Yêu cầu thêm access point/mở rộng vùng phủ sóng | P4 | 5 ngày làm việc (khảo sát + lắp đặt) |
| Báo thiết bị lạ kết nối mạng | Khẩn cấp | Chuyển Security xác minh trong 1 giờ |

**Từ khóa định tuyến về IT:** mạng, wifi, LAN, VLAN, guest wifi, máy in, máy chiếu, access point, mất mạng văn phòng, thiết bị mạng, hạ tầng mạng.


## 8. Network Access Control

Thiết bị vào Corporate LAN phải được nhận diện và đáp ứng baseline phù hợp. Thiết bị unmanaged/không rõ nguồn gốc được đưa vào guest/quarantine network thay vì cấp quyền nội bộ mặc định.

WiFi nhân viên ưu tiên xác thực theo danh tính/chứng thư thiết bị (enterprise authentication) thay cho mật khẩu dùng chung. Guest WiFi tách biệt hoàn toàn khỏi mạng nội bộ và có thời hạn phiên.

## 9. Firewall và luồng mạng

Nguyên tắc mặc định deny giữa các zone quan trọng; rule mở mới phải có source, destination, port/protocol, business owner, lý do và thời hạn nếu là tạm thời. Rule không còn traffic hoặc owner phải được review/cleanup định kỳ.

## 10. Hạ tầng quản trị

Switch, firewall, controller, AP và thiết bị hạ tầng dùng tài khoản quản trị tách biệt, MFA khi hỗ trợ, backup cấu hình và logging tập trung. Management interface không mở trực tiếp từ guest/general user VLAN.

## 11. Rogue device và physical security

Phát hiện rogue AP/router/bridge hoặc thiết bị cắm trái phép phải được cô lập theo quy trình IT/Security. Tủ mạng/server room chỉ người được phép tiếp cận; visitor/vendor phải có escort hoặc log vào/ra theo yêu cầu cơ sở.

## 12. Network change

Thay đổi routing, firewall, VLAN hoặc core network có khả năng ảnh hưởng dịch vụ phải theo IT-POL-006. Emergency network change trong incident vẫn cần ghi log và review sau sự kiện.

## 13. Monitoring và retention

Theo dõi availability, latency, packet loss, capacity, DNS/DHCP anomalies và security signals phù hợp. Log retention căn cứ mục đích vận hành/điều tra và SEC-POL-002; không thu thập payload người dùng rộng hơn mức cần thiết nếu không có căn cứ.


## 14. Capacity và resilience

IT theo dõi utilization và điểm lỗi đơn (single point of failure) của kết nối/thiết bị core. Văn phòng critical nên có phương án đường truyền dự phòng hoặc runbook failover phù hợp mức độ ảnh hưởng kinh doanh.
