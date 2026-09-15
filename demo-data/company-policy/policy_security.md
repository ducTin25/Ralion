# Chính sách An toàn Thông tin (Security Policy)

- **Mã tài liệu:** SEC-POL-000
- **Phiên bản:** 2.4 — Hiệu lực: 01/01/2026
- **Bộ phận ban hành:** Phòng An toàn Thông tin (Security Department)
- **Phạm vi áp dụng:** Toàn bộ nhân viên, nhà thầu và bên thứ ba có truy cập hệ thống

## 1. Phân quyền tssruy cập (Access Control / ACL)

- Áp dụng nguyên tắc tối thiểu quyền (least privilege): chỉ cấp quyền cần thiết cho vai trò (Role) và module được giao.
- Yêu cầu cấp quyền truy cập dữ liệu, hệ thống hoặc project mới phải qua quy trình phê duyệt: Project Owner xác nhận → Security duyệt Access Scope.
- Rà soát quyền truy cập định kỳ mỗi quý; quyền không sử dụng 90 ngày bị thu hồi tự động.

## 2. Phân loại dữ liệu

> Chi tiết phân loại, xử lý, lưu trữ, chia sẻ, hủy và bảo vệ dữ liệu cá nhân được quy định tại **SEC-POL-002**. Khi có khác biệt, SEC-POL-002 là nguồn chuyên biệt được ưu tiên.

| Mức          | Ví dụ                                  | Quy định                               |
| ------------ | -------------------------------------- | -------------------------------------- |
| Public       | Tài liệu marketing                     | Được chia sẻ tự do                     |
| Internal     | Quy trình nội bộ, tài liệu dự án       | Chỉ chia sẻ trong công ty              |
| Confidential | Hợp đồng, dữ liệu khách hàng           | Cần phê duyệt khi chia sẻ              |
| Restricted   | Lương, dữ liệu cá nhân, secret/API key | Cấm sao chép ra ngoài, mã hóa bắt buộc |

## 3. Bảo mật dữ liệu và secret

- Cấm lưu secret, API key, mật khẩu trong source code hoặc tài liệu chia sẻ; chỉ dùng secret manager của công ty.
- Dữ liệu Confidential trở lên không được đưa vào công cụ AI/dịch vụ bên ngoài chưa được phê duyệt.
- Thiết bị cá nhân truy cập hệ thống phải đăng ký MDM.

## 4. Báo cáo sự cố an toàn thông tin

- Nghi ngờ lộ dữ liệu, tài khoản bị chiếm, email lừa đảo (phishing): báo ngay Security qua kênh khẩn cấp, **trong vòng 1 giờ** kể từ khi phát hiện.
- Không tự xóa dấu vết hoặc tự xử lý; giữ nguyên hiện trường số.
- Security phản hồi và điều phối theo mức SEV tại **SEC-POL-004**. Nghĩa vụ thông báo cho cơ quan/đối tượng bên ngoài do Security và Pháp chế đánh giá theo pháp luật hiện hành; không mặc định mọi sự cố đều áp dụng cùng một mốc thông báo.

## 5. Vi phạm và xử lý

- Vi phạm lần đầu không gây hậu quả: nhắc nhở và đào tạo lại.
- Vi phạm gây lộ dữ liệu Confidential/Restricted: lập hội đồng xử lý kỷ luật, phối hợp HR.

**Từ khóa định tuyến về Security:** quyền truy cập, access, ACL, phân quyền, lộ dữ liệu, phishing, lừa đảo, secret, API key, mã hóa, bảo mật, tài khoản bị chiếm, VPN bất thường, dữ liệu khách hàng.


## 6. Nguyên tắc quản trị an toàn thông tin

SEC-POL-000 là policy khung. Policy chuyên biệt là nguồn chuẩn khi có chi tiết khác nhau:

| Chủ đề | Nguồn chuẩn |
|---|---|
| Access control | SEC-POL-001 |
| Data classification & privacy | SEC-POL-002 |
| Secret & cryptographic key | SEC-POL-003 |
| Security incident response | SEC-POL-004 |
| AI & external services | SEC-POL-005 |

Các nguyên tắc xuyên suốt: least privilege, defense in depth, secure-by-default, need-to-know, separation of duties, logging/auditability và risk-based exception.

## 7. Security by design

Hệ thống mới hoặc thay đổi lớn cần xem xét threat model, authentication/authorization, data classification, logging, secret handling, dependency/supply-chain và incident response trước production. Security review tập trung vào rủi ro thực tế, không thay thế trách nhiệm kỹ thuật của service owner.

## 8. Exception management

Ngoại lệ security cần: control không thể đáp ứng, lý do kinh doanh, rủi ro, compensating controls, risk owner, approver và expiry date. Ngoại lệ hết hạn mà chưa gia hạn hợp lệ được coi là không còn hiệu lực.

## 9. Awareness và trách nhiệm

Mọi nhân viên phải hoàn thành security awareness bắt buộc, báo phishing/sự cố, bảo vệ credential và xử lý dữ liệu đúng nhãn. Security cung cấp control, giám sát và tư vấn; không biến Security thành bên duy nhất chịu trách nhiệm bảo mật.

## 10. Metrics và review

Security theo dõi tối thiểu: access review completion, privileged access, data/secret incidents, phishing trend, vulnerability remediation, security exception overdue và incident response SLA. Policy được rà soát ít nhất hằng năm hoặc sau thay đổi pháp lý/major incident đáng kể.
