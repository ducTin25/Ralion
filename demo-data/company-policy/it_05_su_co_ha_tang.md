# Chính sách Quản lý Sự cố Hạ tầng CNTT

- **Mã tài liệu:** IT-POL-005
- **Phiên bản:** 3.4 — Ngày hiệu lực: 01/01/2026
- **Bộ phận ban hành:** Phòng CNTT — Nhóm Vận hành (IT Operations)
- **Phạm vi áp dụng:** Mọi sự cố liên quan hạ tầng, hệ thống, dịch vụ CNTT nội bộ và production
- **Tài liệu tham chiếu:** ITIL 4 (Incident Management); SEC-POL-004 (Ứng phó sự cố ATTT)

## 1. Mục đích

Chuẩn hóa cách tiếp nhận, phân loại, xử lý và rút kinh nghiệm sự cố CNTT, giảm thiểu thời gian gián đoạn và tác động tới công việc, khách hàng.

## 2. Định nghĩa

- **Sự cố (Incident):** gián đoạn ngoài kế hoạch hoặc suy giảm chất lượng dịch vụ CNTT.
- **Yêu cầu dịch vụ (Service Request):** yêu cầu chuẩn không phải sự cố (cấp quyền, cài phần mềm) — theo SLA của chính sách tương ứng.
- **Vấn đề (Problem):** nguyên nhân gốc của một hoặc nhiều sự cố lặp lại.
- **MTTR:** thời gian trung bình khôi phục dịch vụ.

Lưu ý: sự cố nghi liên quan **an toàn thông tin** (tấn công, lộ dữ liệu, mã độc) chuyển ngay quy trình SEC-POL-004, không xử lý theo tài liệu này.

## 3. Phân loại mức độ ưu tiên

| Mức | Tên | Tiêu chí | Ví dụ |
|---|---|---|---|
| P1 | Nghiêm trọng | Production ngừng hoạt động, ảnh hưởng khách hàng, hoặc toàn công ty không làm việc được | Website sập, mất mạng toàn văn phòng, email toàn công ty tê liệt |
| P2 | Cao | Suy giảm nghiêm trọng một dịch vụ, ảnh hưởng một nhóm/bộ phận | Server dev down, VPN lỗi diện rộng, CI/CD tắc toàn bộ |
| P3 | Trung bình | Ảnh hưởng cá nhân hoặc có cách làm vòng (workaround) | Máy một người lỗi, một job CI fail do hạ tầng |
| P4 | Thấp | Phiền toái nhỏ, không chặn công việc | Máy in lỗi, màn hình phụ chập chờn |

## 4. SLA phản hồi và xử lý

| Mức | Phản hồi | Cập nhật tiến độ | Mục tiêu khôi phục |
|---|---|---|---|
| P1 | 15 phút, 24/7 | Mỗi 30 phút | 4 giờ |
| P2 | 1 giờ (giờ làm việc) | Mỗi 2 giờ | 1 ngày làm việc |
| P3 | 4 giờ | Hằng ngày | 2 ngày làm việc |
| P4 | 1 ngày | Khi có thay đổi | 5 ngày làm việc |

## 5. Quy trình xử lý sự cố

### 5.1. Tiếp nhận

- Kênh chính: **IT Service Desk** (portal/ticket); khẩn cấp P1: hotline on-call IT (trực 24/7).
- Ticket cần có: mô tả hiện tượng, thời điểm bắt đầu, phạm vi ảnh hưởng (một mình/cả nhóm), ảnh chụp màn hình/log, các bước đã tự thử.
- Hệ thống giám sát tự động (monitoring/alerting) cũng tạo sự cố tự động khi ngưỡng cảnh báo vượt mức.

### 5.2. Phân loại và điều phối

1. IT xác nhận tiếp nhận, gán mức ưu tiên (có thể điều chỉnh sau khi chẩn đoán).
2. P1/P2: chỉ định **Incident Commander** điều phối, mở kênh chat sự cố riêng, thông báo trên #it-announcements cho người bị ảnh hưởng.
3. Sự cố gửi nhầm kênh (thuộc HR/Security) được định tuyến lại trong 30 phút, người báo được thông báo.

### 5.3. Xử lý và khôi phục

- Ưu tiên **khôi phục dịch vụ** (kể cả bằng workaround) trước khi tìm nguyên nhân gốc.
- Thay đổi khẩn cấp trên production trong lúc xử lý P1 vẫn phải ghi lại (change log) và có người thứ hai xác nhận (four-eyes).
- Escalation: P1 quá 2 giờ chưa có hướng khôi phục → báo cáo Trưởng phòng IT; quá 4 giờ → báo Ban Giám đốc.

### 5.4. Đóng sự cố

- Xác nhận với người báo/bộ phận ảnh hưởng rằng dịch vụ đã bình thường.
- Ticket P3/P4 tự đóng sau 3 ngày không phản hồi từ người báo (có thông báo trước).

## 6. Rút kinh nghiệm (Post-Incident Review)

- **Bắt buộc với mọi sự cố P1/P2**: họp trong vòng 5 ngày làm việc sau khi khôi phục.
- Nguyên tắc **blameless** — tập trung vào nguyên nhân hệ thống, không đổ lỗi cá nhân.
- Báo cáo gồm: dòng thời gian, nguyên nhân gốc (root cause), tác động, việc đã làm tốt, hành động khắc phục (action item có người phụ trách và deadline).
- Sự cố lặp lại ≥ 2 lần/quý cùng nguyên nhân: mở Problem record, đưa vào kế hoạch cải tiến hạ tầng.

## 7. Bảo trì có kế hoạch

- Bảo trì gây gián đoạn thông báo trước **tối thiểu 3 ngày làm việc** trên #it-announcements, thực hiện ngoài giờ làm việc trừ trường hợp bất khả kháng.
- Cửa sổ bảo trì chuẩn: thứ Bảy 20h00–24h00.

## 8. Trách nhiệm người dùng

- Báo sự cố qua đúng kênh (ticket/hotline), không báo miệng/chat cá nhân với nhân viên IT — sự cố không ghi nhận sẽ không có SLA.
- Cung cấp thông tin trung thực, đầy đủ; phối hợp khi IT cần truy cập máy để chẩn đoán.
- Không tự ý can thiệp hệ thống chung (restart server, đổi cấu hình mạng) khi không có quyền.

**Từ khóa định tuyến về IT:** sự cố, lỗi hệ thống, server down, mạng chậm, mất mạng, wifi lỗi, máy in, email lỗi, hệ thống chậm, CI fail, build fail, monitoring, bảo trì, gián đoạn, khôi phục, on-call.


## 9. Major Incident Management

P1 và P2 có thể được nâng thành **Major Incident** khi tác động kinh doanh lớn, nhiều team tham gia hoặc cần communication cấp lãnh đạo. Incident Commander điều phối; technical lead tập trung khôi phục; communications lead cập nhật stakeholder. Một người không nên vừa debug sâu vừa chịu toàn bộ communication.

## 10. Impact × urgency

Priority được xác định từ **impact** (phạm vi, khách hàng, doanh thu/dữ liệu) và **urgency** (mức độ cần khôi phục). Không nâng P1 chỉ vì người báo là cấp quản lý; cũng không hạ mức vì chưa biết root cause.

## 11. Status communication

Update cần nêu: tác động hiện tại, việc đã biết, hành động đang làm, workaround (nếu có) và thời điểm cập nhật tiếp theo. Tránh suy đoán root cause trong thông báo rộng khi chưa xác minh.

## 12. Handoff với Security

Nếu có IOC/dấu hiệu tấn công, credential compromise, ransomware, data exfiltration hoặc truy cập trái phép, Incident Commander liên hệ Security và chuyển/ghép quy trình theo SEC-POL-004. IT không tự xóa log hoặc rebuild trước khi Security xác nhận yêu cầu bảo toàn bằng chứng.

## 13. Problem Management

Incident kết thúc khi dịch vụ khôi phục; problem có thể vẫn mở để xử lý nguyên nhân gốc. Repeated incident, workaround lặp hoặc near-miss nghiêm trọng phải tạo problem record với owner và target date.

## 14. PIR quality

PIR tối thiểu có timeline theo timestamp, detection gap, contributing factors, control đã hoạt động/không hoạt động và action item đo được. “Nhắc team cẩn thận hơn” không được coi là corrective action đủ mạnh nếu nguyên nhân là lỗ hổng hệ thống/quy trình.

## 15. Metrics

Theo dõi tối thiểu: MTTD, MTTA, MTTR, số P1/P2, tỷ lệ incident lặp, % PIR đúng hạn và action item overdue. Metrics dùng để cải tiến hệ thống, không để xếp hạng cá nhân on-call.
