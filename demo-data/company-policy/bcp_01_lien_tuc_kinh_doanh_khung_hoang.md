# Chính sách Liên tục Kinh doanh và Quản lý Khủng hoảng

- **Mã tài liệu:** BCP-POL-001
- **Phiên bản:** 1.0 — Ngày hiệu lực: 01/01/2026
- **Bộ phận ban hành:** Enterprise Risk / Business Operations, phối hợp IT, Security và HR
- **Phạm vi áp dụng:** Các chức năng và dịch vụ thiết yếu của công ty
- **Tài liệu liên quan:** IT-POL-008; IT-POL-005; SEC-POL-004; CORP-POL-003

## 1. Mục đích

Đảm bảo công ty duy trì hoặc khôi phục hoạt động quan trọng khi xảy ra gián đoạn lớn như mất văn phòng, mất nhà cung cấp trọng yếu, thiên tai, dịch bệnh, cyber incident hoặc thiếu nhân sự chủ chốt.

## 2. Business Impact Analysis (BIA)

Mỗi chức năng trọng yếu phải xác định:
- Critical process/service.
- Maximum tolerable disruption.
- Dependencies: people, office, system, vendor, data.
- Minimum staffing/resources.
- Manual workaround và communication path.

BIA review tối thiểu hằng năm hoặc khi có thay đổi đáng kể.

## 3. Priority tiers

- **Tier A — Essential:** gián đoạn ảnh hưởng khách hàng/pháp lý/an toàn nghiêm trọng; cần phương án continuity cụ thể.
- **Tier B — Important:** có thể gián đoạn ngắn với workaround.
- **Tier C — Deferrable:** có thể tạm dừng trong crisis.

RTO/RPO kỹ thuật của hệ thống tham chiếu IT-POL-008 nhưng business continuity không chỉ là backup/DR.

## 4. Kích hoạt Crisis Management

Crisis Lead/Executive Sponsor có thể kích hoạt khi tác động vượt khả năng xử lý của một team hoặc nhiều domain cùng bị ảnh hưởng. Crisis room có decision log, owner, cadence update và single source of truth.

## 5. Continuity strategies

Có thể gồm: remote work, alternate site, cross-training, secondary vendor, manual process, inventory buffer, failover system hoặc prioritized service degradation.

## 6. Truyền thông khủng hoảng

Internal update phải nêu điều đã biết, tác động, hành động người dùng cần làm và thời điểm cập nhật tiếp theo. External statement theo CORP-POL-003; không để nhiều team phát thông điệp mâu thuẫn.

## 7. Nhân sự và an toàn

An toàn con người ưu tiên trước continuity. Không yêu cầu nhân viên tới văn phòng khi cơ quan chức năng/công ty xác định không an toàn chỉ để đáp ứng SLA thông thường.

## 8. Diễn tập

- Tier A: tabletop hoặc functional exercise tối thiểu hằng năm.
- DR test kỹ thuật theo IT-POL-008 không tự thay thế BCP exercise; cần kiểm tra cả con người/quy trình/vendor.
- Findings có owner và deadline.

## 9. Supplier continuity

Vendor Tier 1 theo TPRM-POL-001 cần xem xét BCP/DR và exit/alternative strategy khi feasible.

## 10. Tình huống thường gặp

- **Mất văn phòng nhưng cloud hoạt động:** kích hoạt remote continuity nếu con người/an toàn cho phép; không nhất thiết kích hoạt DR.
- **Cloud region down:** IT-POL-008/incident xử lý kỹ thuật; BCP quản lý ưu tiên business/customer communication.
- **Vendor critical phá sản:** continuity có thể kích hoạt dù không có “IT incident”.

## 11. Kênh và trách nhiệm

| Vai trò | Trách nhiệm |
|---|---|
| Business Owner | BIA, minimum viable operation |
| IT/Security | Technical DR/incident |
| HR | People safety/availability |
| Communications | Internal/external messaging |
| Crisis Lead | Quyết định và điều phối tổng thể |

**Từ khóa định tuyến:** business continuity, BCP, crisis, khủng hoảng, BIA, mất văn phòng, thiên tai, alternate site, continuity, critical process.
