# Chính sách Truy cập Dữ liệu Khách hàng trong Hỗ trợ và Vận hành

- **Mã tài liệu:** CUST-POL-001
- **Phiên bản:** 1.0 — Ngày hiệu lực: 01/01/2026
- **Bộ phận ban hành:** Customer Operations, Security và Privacy/Legal
- **Phạm vi áp dụng:** Nhân viên hỗ trợ, SRE, Engineering, Data và bất kỳ ai có thể truy cập dữ liệu tenant/khách hàng
- **Tài liệu liên quan:** SEC-POL-001; SEC-POL-002; SEC-POL-004; ENG-POL-001

## 1. Mục đích

Cho phép hỗ trợ khách hàng hiệu quả nhưng giới hạn truy cập dữ liệu theo ticket, mục đích, thời gian và mức quyền; ngăn “curiosity access”.

## 2. Nguyên tắc

- Không truy cập tenant/dữ liệu khách hàng chỉ vì có khả năng kỹ thuật.
- Mỗi truy cập phải có mục đích công việc hợp lệ và traceable tới ticket/incident/request.
- Chỉ xem lượng dữ liệu tối thiểu cần để chẩn đoán.
- Không export dữ liệu về máy cá nhân/local file nếu không cần thiết và chưa được phép.

## 3. Support access

- Tool hỗ trợ ưu tiên masked/read-only view.
- Access nâng cao cần role phù hợp và có thể yêu cầu ticket/customer consent tùy contract/product.
- Impersonation/login-as phải hiển thị rõ đang impersonate, được log và không dùng cho hoạt động ngoài ticket.

## 4. Production database

Direct DB access là ngoại lệ, theo SEC-POL-001/JIT. Query ưu tiên read-only và giới hạn tenant. Thao tác write/correction dữ liệu cần approval/runbook và audit trail.

## 5. Screenshot và attachment

- Screenshot dùng trong ticket phải che dữ liệu không cần thiết.
- Attachment khách hàng gửi được xem là dữ liệu theo classification phù hợp; không upload sang AI/public pastebin/tool ngoài danh mục.

## 6. Data correction/deletion

Support không tự xóa/sửa dữ liệu khách hàng khi request có thể là data-subject/legal/contractual request. Chuyển privacy/account owner workflow khi cần xác minh authority và retention/legal hold.

## 7. Break-glass

Trong SEV1, break-glass access có thể được dùng để khôi phục dịch vụ nếu runbook cho phép; phải có logging, incident reference và retrospective review.

## 8. Customer credential

Nhân viên không yêu cầu khách hàng gửi mật khẩu, MFA code, private key hoặc full secret qua ticket. Nếu khách hàng gửi secret, coi là exposed và hướng dẫn rotate; xử lý attachment theo Security.

## 9. Monitoring

Privileged support access được log; pattern bất thường như truy cập nhiều tenant, ngoài giờ không có ticket hoặc export lớn có thể bị alert/review.

## 10. Tình huống thường gặp

- **Bạn biết customer ID và muốn xem account để “hiểu sản phẩm”:** không được nếu không có support/business purpose.
- **Khách gửi API key trong ticket:** báo/che phù hợp và yêu cầu rotate; không copy key vào chat nội bộ rộng.
- **Bug chỉ tái hiện với dữ liệu thật:** ưu tiên synthetic/minimized repro; production access chỉ khi cần và được kiểm soát.

## 11. Kênh và SLA

| Yêu cầu | SLA |
|---|---|
| Standard support access | Theo role, tức thời nếu đã cấp |
| Elevated/JIT access | 30 phút–4 giờ tùy mức độ |
| Data subject/privacy request | Chuyển Privacy/Legal ngay |
| Nghi truy cập trái phép | Security incident ngay |

**Từ khóa định tuyến:** khách hàng, customer data, tenant, support access, impersonate, login as, production database, ticket, export, customer secret.
