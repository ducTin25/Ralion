# Chính sách Quản lý Thay đổi Hệ thống (Change Management)

- **Mã tài liệu:** IT-POL-006
- **Phiên bản:** 1.0 — Ngày hiệu lực: 01/01/2026
- **Bộ phận ban hành:** Phòng CNTT — Nhóm Vận hành (IT Operations)
- **Phạm vi áp dụng:** Mọi thay đổi cấu hình, triển khai (deploy), nâng cấp hệ thống/hạ tầng ảnh hưởng đến môi trường staging hoặc production
- **Tài liệu tham chiếu:** IT-POL-005 (Sự cố hạ tầng), SEC-POL-001 (Phân quyền truy cập)

## 1. Mục đích

Giảm thiểu rủi ro gián đoạn dịch vụ do thay đổi hệ thống không kiểm soát; đảm bảo mọi thay đổi được đánh giá, phê duyệt, kiểm thử và có thể hoàn tác (rollback) trước khi triển khai.

## 2. Định nghĩa "Thay đổi" (Change)

Bất kỳ điều chỉnh nào đến cấu hình, mã nguồn triển khai, hạ tầng, cơ sở dữ liệu, hoặc dịch vụ bên thứ ba tích hợp, có khả năng ảnh hưởng đến tính sẵn sàng, hiệu năng hoặc bảo mật của hệ thống staging/production. Không bao gồm thay đổi trong môi trường dev cá nhân.

## 3. Phân loại thay đổi

| Loại | Mô tả | Ví dụ | Phê duyệt |
|---|---|---|---|
| Standard | Đã định nghĩa trước, rủi ro thấp, lặp lại | Scale thêm instance theo template có sẵn, gia hạn cert tự động | Tự động (pre-approved), không cần CAB |
| Normal | Có kế hoạch, rủi ro trung bình đến cao | Deploy tính năng mới, nâng cấp phiên bản database, đổi schema | CAB duyệt trước ít nhất 2 ngày làm việc |
| Emergency | Khẩn cấp để khắc phục sự cố P1/P2 đang diễn ra | Hotfix production đang down, patch bảo mật khẩn cấp | Duyệt sau (retroactive) trong 24 giờ, cần 2 người xác nhận (four-eyes) tại thời điểm thực hiện |

## 4. Change Advisory Board (CAB)

Họp định kỳ 2 lần/tuần (thứ Ba, thứ Năm) xem xét các đề xuất Normal change; thành viên gồm đại diện IT Operations, Security, và Lead kỹ thuật của dự án liên quan.

## 5. Yêu cầu bắt buộc trước khi triển khai (Normal & Standard có rủi ro)

- Kế hoạch rollback rõ ràng, đã kiểm thử ở staging.
- Change window ngoài giờ cao điểm (khuyến nghị: sau 20h00 hoặc cuối tuần), trừ Standard change rủi ro thấp.
- Thông báo trước cho các bên liên quan tối thiểu 24 giờ (Normal) qua kênh #it-announcements.
- Người thực hiện và người xác nhận (approver) không được là cùng một người (segregation of duties, theo nguyên tắc tại SEC-POL-001).

## 6. Thay đổi khẩn cấp (Emergency Change)

- Được thực hiện ngay để khôi phục dịch vụ khi xử lý sự cố P1/P2 theo IT-POL-005, không chờ CAB.
- Bắt buộc có người thứ hai xác nhận trực tiếp (four-eyes) trước khi áp dụng, dù trong tình huống khẩn cấp.
- Ghi lại đầy đủ vào change log trong vòng **24 giờ** sau khi hệ thống ổn định: nội dung thay đổi, người thực hiện, người xác nhận, lý do khẩn cấp.
- CAB rà soát lại Emergency change trong kỳ họp gần nhất để rút kinh nghiệm.

## 7. Ghi log và audit

Toàn bộ thay đổi (Standard/Normal/Emergency) được ghi vào hệ thống change log tập trung, lưu tối thiểu 12 tháng, phục vụ audit và điều tra sự cố.

## 8. Vi phạm

Triển khai thay đổi production không qua quy trình (bỏ qua CAB, không có rollback plan, không four-eyes cho Emergency change) được coi là vi phạm nghiêm trọng, xử lý theo HR-POL-005; nếu gây sự cố production, phối hợp xử lý theo IT-POL-005.

## 9. Kênh hỗ trợ và SLA

| Loại yêu cầu | SLA |
|---|---|
| Đề xuất Normal change, đưa vào lịch CAB | Xem xét trong kỳ họp CAB gần nhất (≤ 3 ngày làm việc) |
| Đăng ký Standard change mới vào danh mục pre-approved | 5 ngày làm việc (đánh giá bởi IT Operations) |
| Ghi nhận Emergency change sau xử lý sự cố | Trong 24 giờ sau khi hệ thống ổn định |

**Từ khóa định tuyến về IT:** thay đổi hệ thống, change management, CAB, deploy, triển khai, rollback, change window, emergency change, hotfix, change log.


## 10. Đánh giá rủi ro thay đổi

Normal change được đánh giá theo phạm vi ảnh hưởng, khả năng rollback, dữ liệu/schema, security impact, dependency và thời điểm triển khai. Change có migration irreversible, quyền production mới hoặc dependency critical được xem xét ở mức rủi ro cao hơn dù diff code nhỏ.

## 11. Nội dung change record tối thiểu

- mô tả và business reason;
- service/environment bị ảnh hưởng;
- risk/impact và dependency;
- test evidence;
- implementation plan;
- rollback/backout plan và tiêu chí kích hoạt rollback;
- validation sau deploy;
- owner, implementer, approver, change window.

## 12. Deployment strategies

Khuyến khích giảm blast radius bằng feature flag, canary, blue/green, progressive rollout hoặc migration nhiều bước khi phù hợp. Feature flag không được dùng để bỏ qua approval; flag lâu dài phải có owner và kế hoạch cleanup.

## 13. Database và data migration

Migration production cần backup/restore hoặc rollback strategy phù hợp, kiểm tra lock/downtime, backward compatibility và validation dữ liệu. Thay đổi phá vỡ tương thích cần phối hợp consumer trước khi deploy.

## 14. Change freeze

IT có thể công bố freeze window trong giai đoạn kinh doanh cao điểm. Trong freeze chỉ Standard change được phép hoặc Normal/Emergency có phê duyệt ngoại lệ phù hợp.

## 15. Emergency change review

Emergency không đồng nghĩa “không cần quy trình”. Tối thiểu phải có ticket/incident liên quan, người thứ hai xác nhận, log thay đổi và validation. Retro review tập trung xem emergency có thực sự cần thiết và làm sao giảm khả năng phải dùng lại.

## 16. Change metrics

Theo dõi change success rate, change failure rate, rollback rate, emergency change ratio và incident do change. Mục tiêu là giảm rủi ro mà không biến CAB thành nút thắt cho thay đổi chuẩn, lặp lại và đã tự động hóa tốt.
