# Chính sách Sao lưu và Khôi phục Dữ liệu (Backup & Disaster Recovery)

- **Mã tài liệu:** IT-POL-008
- **Phiên bản:** 1.1 — Ngày hiệu lực: 01/01/2026
- **Bộ phận ban hành:** Phòng CNTT — Nhóm Vận hành (IT Operations), phối hợp Phòng An toàn Thông tin
- **Phạm vi áp dụng:** Toàn bộ hệ thống, cơ sở dữ liệu và dịch vụ do công ty vận hành
- **Tài liệu tham chiếu:** SEC-POL-002 (Phân loại và Bảo vệ Dữ liệu), IT-POL-005 (Sự cố hạ tầng)

## 1. Mục đích

Đảm bảo dữ liệu và hệ thống có thể khôi phục đúng hạn khi xảy ra sự cố, lỗi thao tác hoặc thảm họa, giới hạn thời gian gián đoạn và mất mát dữ liệu ở mức chấp nhận được.

## 2. Định nghĩa

- **RPO (Recovery Point Objective):** lượng dữ liệu tối đa chấp nhận mất, tính theo thời gian kể từ lần backup gần nhất.
- **RTO (Recovery Time Objective):** thời gian tối đa chấp nhận để khôi phục dịch vụ sau sự cố.
- **Backup đầy đủ (Full)** và **Backup gia tăng (Incremental)**.

## 3. Phân loại hệ thống và mục tiêu khôi phục

| Tier | Mô tả | Tần suất backup | RPO | RTO | Kiểm tra khôi phục |
|---|---|---|---|---|---|
| Tier 1 | Hệ thống production ảnh hưởng khách hàng trực tiếp | Incremental mỗi 4 giờ, Full hằng ngày | 4 giờ | 4 giờ | Hằng quý |
| Tier 2 | Hệ thống nội bộ quan trọng (HRM, hệ thống dự án) | Full hằng ngày | 24 giờ | 1 ngày làm việc | Tối thiểu 6 tháng/lần (theo SEC-POL-002) |
| Tier 3 | Hệ thống hỗ trợ, môi trường dev/staging | Full hằng tuần | 7 ngày | 3 ngày làm việc | Hằng năm |

## 4. Quy trình sao lưu

- Backup tự động theo lịch, giám sát bởi hệ thống monitoring; backup lỗi liên tiếp 2 lần tạo cảnh báo P2 theo IT-POL-005.
- Nơi lưu backup tách biệt vật lý/logic khỏi hệ thống gốc; backup Tier 1 lưu thêm 1 bản sao ở vùng địa lý khác (offsite).
- Mã hóa backup **bắt buộc như dữ liệu gốc** theo phân loại tại SEC-POL-002 — backup của dữ liệu Confidential/Restricted phải mã hóa at-rest.
- Thời gian lưu trữ bản backup: Tier 1–2 tối thiểu 90 ngày, Tier 3 tối thiểu 30 ngày, trừ yêu cầu lưu trữ dài hạn theo quy định pháp luật (kế toán, nhân sự).

## 5. Kiểm tra khôi phục định kỳ

- Thực hiện đúng tần suất theo Tier ở mục 3; đây là cụ thể hóa yêu cầu tối thiểu 6 tháng/lần đã nêu tại SEC-POL-002 mục 5.
- Người phụ trách: IT Operations thực hiện; Security xác nhận kết quả cho hệ thống xử lý dữ liệu Confidential/Restricted.
- Kết quả kiểm tra (thành công/thất bại, thời gian khôi phục thực tế) ghi vào báo cáo quý gửi Trưởng phòng IT.
- Kiểm tra khôi phục thất bại: mở ticket khắc phục ưu tiên P2, không chờ đến chu kỳ kiểm tra tiếp theo.

## 6. Kích hoạt khôi phục khi có sự cố (DR Invocation)

- Sự cố hạ tầng thông thường (server lỗi, mất dữ liệu cục bộ): khôi phục theo quy trình IT-POL-005, IT Operations tự quyết định khôi phục từ backup gần nhất.
- Sự cố nghi ngờ liên quan tấn công/mã độc/ransomware: **không tự khôi phục ngay**; phối hợp Security theo quy trình SEC-POL-004 (giai đoạn Recovery) để đảm bảo backup dùng để khôi phục không bị nhiễm.
- Thảm họa ảnh hưởng toàn bộ hạ tầng chính (mất trung tâm dữ liệu): Trưởng phòng IT quyết định kích hoạt kế hoạch DR toàn diện, báo cáo Ban Giám đốc.

## 7. Trách nhiệm

- **IT Operations:** vận hành backup, kiểm tra khôi phục định kỳ, đề xuất Tier cho hệ thống mới.
- **Chủ hệ thống (System Owner/Project Owner):** xác nhận Tier phù hợp với mức độ quan trọng nghiệp vụ, tham gia kiểm tra khôi phục khi cần.
- **Security:** xác nhận mã hóa đúng phân loại dữ liệu, tham gia quyết định khôi phục khi sự cố liên quan an toàn thông tin.

## 8. Kênh hỗ trợ và SLA

| Loại yêu cầu | SLA |
|---|---|
| Đăng ký hệ thống mới vào lịch backup, xác định Tier | 5 ngày làm việc |
| Yêu cầu khôi phục dữ liệu (không phải sự cố khẩn) | 2 ngày làm việc |
| Backup lỗi liên tiếp / cảnh báo giám sát | P2 theo IT-POL-005 |
| Khôi phục khẩn cấp (sự cố P1 đang diễn ra) | Theo IT-POL-005 (mục tiêu khôi phục 4 giờ với Tier 1) |

**Từ khóa định tuyến về IT:** backup, sao lưu, khôi phục, restore, RTO, RPO, disaster recovery, DR, mất dữ liệu, kiểm tra khôi phục, offsite backup.


## 9. Nguyên tắc 3-2-1-1-0

Đối với Tier 1 và dữ liệu quan trọng, thiết kế backup hướng tới: ít nhất 3 bản dữ liệu, trên 2 loại/miền lưu trữ phù hợp, 1 bản offsite, 1 bản immutable/offline khi khả thi, và **0 lỗi chưa được xử lý trong kiểm tra backup/restore**. Đây là nguyên tắc thiết kế; kiến trúc cụ thể do Service Owner và IT Operations phê duyệt.

## 10. Backup không đồng nghĩa DR

Backup bảo vệ khả năng khôi phục dữ liệu; DR bao gồm cả compute, network, dependency, secret, DNS, runbook và thứ tự khởi động dịch vụ. Service Tier 1 phải có DR runbook nêu dependency và người có quyền kích hoạt.

## 11. Immutability và ransomware

Backup của hệ thống critical cần tách credential/control plane khỏi production và dùng object lock/immutable mechanism khi nền tảng hỗ trợ. Account production bị compromise không được mặc nhiên có quyền xóa toàn bộ backup.

## 12. Restore testing

Restore test phải kiểm chứng **dữ liệu sử dụng được**, không chỉ job “restore success”. Bài test ghi actual RPO/RTO, checksum/consistency check, dependency cần khôi phục và gap so với mục tiêu. Tier 1 nên có ít nhất một bài exercise có yếu tố mất vùng/mất credential theo kế hoạch DR.

## 13. Backup coverage

Service Owner chịu trách nhiệm khai báo dữ liệu/state cần backup. Source code đã ở Git không thay thế backup cho artifact registry, database, object storage, SaaS configuration hoặc encryption key metadata cần thiết cho recovery.

## 14. Retention và deletion

Retention backup phải tương thích với legal hold, data retention và quyền xóa theo SEC-POL-002. Việc xóa dữ liệu ở hệ thống chính có thể cần cơ chế hết hạn trong backup thay vì chỉnh sửa từng bản backup, tùy yêu cầu pháp lý và thiết kế kỹ thuật.

## 15. DR exercise và governance

Sau exercise/DR thật, mở action item cho dependency thiếu, runbook lỗi, quyền truy cập không hoạt động hoặc RTO/RPO không đạt. Không tuyên bố hệ thống “DR ready” chỉ dựa trên việc backup job chạy xanh.
