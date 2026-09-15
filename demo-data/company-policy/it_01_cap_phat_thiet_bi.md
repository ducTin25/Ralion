# Chính sách Cấp phát và Quản lý Thiết bị

- **Mã tài liệu:** IT-POL-001
- **Phiên bản:** 3.1 — Ngày hiệu lực: 01/01/2026
- **Bộ phận ban hành:** Phòng CNTT (IT Department)
- **Phạm vi áp dụng:** Toàn bộ nhân viên sử dụng thiết bị do công ty cấp
- **Tài liệu liên quan:** HR-POL-003 (Onboarding/Offboarding), SEC-POL-002 (Phân loại dữ liệu)

## 1. Mục đích

Quy định tiêu chuẩn cấp phát, sử dụng, bảo quản, sửa chữa và thu hồi thiết bị CNTT, đảm bảo nhân viên có đủ công cụ làm việc và tài sản công ty được quản lý chặt chẽ.

## 2. Tiêu chuẩn cấp phát theo vị trí

| Vị trí | Thiết bị chuẩn | Chu kỳ thay mới |
|---|---|---|
| Nhân viên văn phòng | Laptop 16GB RAM/512GB SSD, 1 màn hình 24" | 4 năm |
| Kỹ sư phần mềm | Laptop 32GB RAM/1TB SSD, 2 màn hình 27" | 3 năm |
| Designer/Data | Laptop cấu hình cao hoặc workstation, màn hình màu chuẩn | 3 năm |
| Quản lý cấp trung trở lên | Laptop chuẩn + phụ cấp điện thoại | 3 năm |

Phụ kiện chuẩn kèm theo: chuột, bàn phím, tai nghe, balo/túi chống sốc, khóa màn hình (nếu làm tại văn phòng mở).

## 3. Quy trình cấp phát

### 3.1. Nhân viên mới

1. HR tạo yêu cầu cấp thiết bị trên IT Service Desk **trước ngày vào ít nhất 3 ngày làm việc**, ghi rõ vị trí và ngày bắt đầu.
2. IT chuẩn bị thiết bị theo tiêu chuẩn, cài đặt image chuẩn công ty (hệ điều hành, phần mềm bảo mật endpoint, MDM).
3. Ngày đầu tiên: IT bàn giao, nhân viên kiểm tra và **ký biên bản bàn giao thiết bị** (ghi serial, tình trạng, phụ kiện).

### 3.2. Cấp thêm / thay thế

1. Nhân viên tạo ticket trên IT Service Desk, chọn loại yêu cầu: cấp thêm phụ kiện, nâng cấp, thay thế do hỏng.
2. Phê duyệt: trong tiêu chuẩn → IT duyệt trực tiếp; ngoài tiêu chuẩn (vượt cấu hình/ngân sách) → cần Trưởng bộ phận phê duyệt.
3. SLA cấp phát: phụ kiện có sẵn **2 ngày làm việc**; thiết bị phải đặt mua **7–10 ngày làm việc**.

## 4. Trách nhiệm của người sử dụng

- Tự bảo quản thiết bị; **không** cho người ngoài công ty mượn hoặc sử dụng.
- Không tự ý tháo lắp, thay linh kiện, cài lại hệ điều hành hoặc gỡ phần mềm bảo mật endpoint/MDM.
- Thiết bị mang ra khỏi văn phòng phải bật mã hóa ổ đĩa (BitLocker/FileVault — mặc định trong image chuẩn) và khóa màn hình khi rời máy.
- Dữ liệu công việc lưu trên hệ thống lưu trữ công ty (drive nội bộ); **không lưu duy nhất trên máy cá nhân** — hỏng máy không phải lý do miễn trách nhiệm mất dữ liệu.
- Báo ngay IT khi thiết bị hỏng, chậm bất thường hoặc nghi nhiễm mã độc.

## 5. Sửa chữa, mất mát và bồi thường

### 5.1. Hỏng hóc

- Tạo ticket kèm mô tả và ảnh chụp; IT chẩn đoán trong **1 ngày làm việc**.
- Sửa chữa dự kiến quá 2 ngày: IT cấp **thiết bị mượn tạm** để không gián đoạn công việc.
- Hỏng do lỗi phần cứng/hao mòn tự nhiên: công ty chịu chi phí. Hỏng do sử dụng sai (đổ nước, rơi vỡ do bất cẩn): nhân viên chịu một phần chi phí theo đánh giá, tối đa theo HR-POL-005.

### 5.2. Mất mát / trộm cắp

1. Báo IT và Security **trong vòng 4 giờ** kể từ khi phát hiện (để khóa thiết bị từ xa qua MDM và vô hiệu hóa phiên đăng nhập).
2. Trình báo công an nếu bị trộm; nộp biên bản trình báo cho IT.
3. Hội đồng đánh giá mức bồi thường dựa trên hoàn cảnh và giá trị còn lại của thiết bị.

## 6. Thiết bị cá nhân (BYOD)

- Chỉ được dùng thiết bị cá nhân truy cập email và hệ thống nội bộ khi đã **đăng ký MDM** với IT.
- Không xử lý dữ liệu mức Confidential trở lên trên thiết bị cá nhân (xem SEC-POL-002).
- Công ty có quyền xóa từ xa (remote wipe) **phân vùng dữ liệu công ty** trên thiết bị đã đăng ký khi nhân viên nghỉ việc hoặc thiết bị bị mất.

## 7. Thu hồi thiết bị

- Nghỉ việc: bàn giao toàn bộ thiết bị và phụ kiện cho IT trong **ngày làm việc cuối cùng**; IT kiểm tra theo biên bản bàn giao ban đầu.
- Thiết bị thu hồi được xóa dữ liệu an toàn (secure wipe) trước khi cấp lại hoặc thanh lý.
- Chưa hoàn tất bàn giao thiết bị: HR tạm hoãn thanh toán các khoản cuối cho đến khi hoàn tất.

## 8. Kênh hỗ trợ và SLA

| Loại yêu cầu | Mức ưu tiên | SLA phản hồi | SLA xử lý |
|---|---|---|---|
| Thiết bị hỏng không làm việc được | P2 | 1 giờ | 1 ngày làm việc (kèm máy mượn) |
| Thiết bị lỗi một phần | P3 | 4 giờ | 2 ngày làm việc |
| Cấp phụ kiện có sẵn | P4 | 1 ngày | 2 ngày làm việc |
| Đặt mua thiết bị mới | P4 | 1 ngày | 7–10 ngày làm việc |
| Mất thiết bị (khóa từ xa) | P1 | 15 phút | 4 giờ |

**Từ khóa định tuyến về IT:** laptop, máy tính, màn hình, chuột, bàn phím, tai nghe, thiết bị, hỏng máy, sửa máy, mất laptop, bàn giao thiết bị, nâng cấp RAM, cấp phát, BYOD, MDM, thay thế thiết bị.


## 9. Vòng đời tài sản CNTT

Mỗi thiết bị có asset ID, serial, người chịu trách nhiệm, trạng thái và lịch sử bàn giao. Trạng thái chuẩn: **IN_STOCK → ASSIGNED → REPAIR/LOANER → RETURNED → RETIRED/DISPOSED**. IT không cấp thiết bị không có record tài sản trừ tình huống khẩn cấp; record phải bổ sung trong ngày làm việc kế tiếp.

## 10. Baseline bảo mật thiết bị

Thiết bị công ty phải được enrollment vào MDM/endpoint management, bật disk encryption, EDR/antimalware, screen lock, automatic patching và inventory agent theo chuẩn IT/Security. Người dùng không được tắt agent vì lý do hiệu năng; nếu agent gây lỗi, tạo ticket để IT xử lý/miễn trừ có thời hạn.

Thiết bị có quyền truy cập production/Restricted có thể áp dụng baseline cao hơn như FIDO2, không local admin, USB control và posture check.

## 11. Local admin và quyền cài đặt

Local admin không cấp mặc định. Kỹ sư cần quyền nâng cao dùng cơ chế tạm thời/JIT hoặc profile dev được kiểm soát. Việc có local admin không miễn trừ IT-POL-004 hoặc secret/data policy.

## 12. Repair và bảo vệ dữ liệu

Trước khi gửi máy ra nhà cung cấp sửa chữa, IT đánh giá việc xóa/khóa dữ liệu, encryption và chain-of-custody. Với ổ đĩa có dữ liệu Confidential/Restricted, ưu tiên giữ ổ hoặc secure wipe nếu tình trạng thiết bị cho phép. Nhà cung cấp không được nhận credential của nhân viên để “test máy”.

## 13. Mất thiết bị và response

Người dùng ưu tiên **báo ngay** thay vì tự đi tìm trong nhiều giờ. IT/Security có thể revoke session, khóa thiết bị, remote wipe vùng công ty và đánh giá dữ liệu có nguy cơ lộ. Nếu thiết bị được tìm lại sau khi đã báo mất, không tự kết nối lại trước khi IT xác minh trạng thái.

## 14. Thanh lý và tái sử dụng

Thiết bị chỉ được cấp lại sau secure wipe và kiểm tra baseline. Thiết bị thanh lý phải xóa dữ liệu theo phương pháp được Security/IT phê duyệt; vật mang tin không thể xóa an toàn phải phá hủy có biên bản.

## 15. Ngoại lệ cấu hình

Yêu cầu vượt chuẩn (RAM/GPU/thiết bị đặc thù) cần business justification, cost center và thời hạn sử dụng. Thiết bị cấu hình đặc thù vẫn phải đáp ứng baseline bảo mật; nếu không thể, Security phê duyệt compensating controls.
