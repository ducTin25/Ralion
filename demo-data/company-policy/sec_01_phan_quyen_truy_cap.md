# Chính sách Phân quyền Truy cập (Access Control)

- **Mã tài liệu:** SEC-POL-001
- **Phiên bản:** 3.0 — Ngày hiệu lực: 01/01/2026
- **Bộ phận ban hành:** Phòng An toàn Thông tin (Security Department)
- **Phạm vi áp dụng:** Mọi quyền truy cập vào hệ thống, dữ liệu, ứng dụng của công ty
- **Tài liệu tham chiếu:** ISO/IEC 27001:2022 (A.5.15–A.5.18, A.8.2–A.8.3); IT-POL-002 (Tài khoản)

## 1. Mục đích

Đảm bảo mỗi người chỉ truy cập đúng tài nguyên cần thiết cho công việc, quyền được cấp có kiểm soát, có thời hạn, có rà soát và thu hồi kịp thời.

## 2. Nguyên tắc nền tảng

- **Least Privilege (tối thiểu quyền):** mặc định không có quyền; chỉ cấp mức thấp nhất đủ để làm việc.
- **Need-to-know:** truy cập dữ liệu theo nhu cầu công việc thực tế, không theo chức danh đơn thuần.
- **RBAC (Role-Based Access Control):** quyền gán theo Role chuẩn hóa (ví dụ: Developer, QA, PM, Support) kết hợp phạm vi **Project/Module/Access Scope**; hạn chế cấp quyền lẻ theo cá nhân.
- **Segregation of Duties:** tách quyền để không cá nhân nào tự hoàn tất chu trình nhạy cảm một mình (ví dụ: người viết code không tự phê duyệt và tự deploy production).
- **Kiểm tra tại backend:** mọi kiểm soát truy cập phải thực thi ở tầng backend/API; lọc hiển thị ở frontend chỉ là bổ trợ, không phải kiểm soát.

## 3. Mô hình phân quyền theo dự án

| Thành phần | Mô tả | Ai quản lý |
|---|---|---|
| Project | Đơn vị phạm vi cao nhất | Project Owner |
| Role | Vai trò trong dự án (Owner, Member, Reviewer, Support) | Project Owner đề xuất, Security duyệt khuôn mẫu |
| Module | Phân vùng chức năng/kho tài liệu trong project | Project Owner |
| Access Scope | Tập quyền cụ thể: đọc/ghi tài liệu, môi trường, dữ liệu | Security phê duyệt |

Thành viên mới của dự án chỉ nhìn thấy và truy vấn được tài liệu, task, dữ liệu **trong Access Scope đã duyệt** — bao gồm cả câu trả lời từ hệ thống AI/RAG nội bộ (retrieval phải lọc theo ACL trước khi sinh câu trả lời).

## 4. Vòng đời quyền truy cập

### 4.1. Cấp quyền

1. Người yêu cầu (hoặc quản lý) tạo đề nghị: hệ thống/dữ liệu cần truy cập, mức quyền (read/write/admin), lý do, thời hạn.
2. Phê duyệt 2 cấp: **chủ tài nguyên** (Project Owner/Trưởng bộ phận) xác nhận nhu cầu → **Security** duyệt tính phù hợp.
3. IT thực thi cấp quyền theo phê duyệt; mọi thao tác cấp quyền được ghi log.
4. SLA: quyền chuẩn theo Role **2 ngày làm việc**; quyền đặc biệt/nhạy cảm **5 ngày làm việc**.

### 4.2. Quyền tạm thời và đặc quyền

- Quyền tạm thời (ví dụ hỗ trợ sự cố): cấp theo cơ chế **just-in-time**, tự hết hạn sau tối đa 24 giờ, gia hạn phải xin lại.
- Quyền admin/production: tách tài khoản riêng, phê duyệt theo phiên, ghi log phiên đầy đủ; rà soát danh sách người giữ đặc quyền **mỗi quý**.

### 4.3. Thay đổi và thu hồi

- Chuyển bộ phận/dự án: thu hồi toàn bộ quyền cũ **trước khi** cấp quyền mới (tránh tích lũy quyền — privilege creep).
- Nghỉ việc: thu hồi toàn bộ quyền trong **24 giờ** sau ngày cuối (phối hợp IT theo HR-POL-003).
- Quyền không sử dụng **90 ngày**: thu hồi tự động, có thông báo trước 7 ngày.

### 4.4. Rà soát định kỳ (Access Review)

- **Mỗi quý:** chủ tài nguyên xác nhận lại danh sách người có quyền trên hệ thống mình quản lý (attest).
- **Mỗi năm:** Security tổng rà soát toàn bộ quyền đặc quyền và quyền vào dữ liệu Restricted.
- Không xác nhận đúng hạn: quyền liên quan tự động tạm khóa cho đến khi hoàn tất rà soát.

## 5. Quy định với dữ liệu và hệ thống đặc biệt

- Dữ liệu **Restricted** (lương, dữ liệu cá nhân, secret): cấp quyền theo từng cá nhân cụ thể, không cấp theo group rộng; mọi truy cập được log và cảnh báo bất thường.
- Database production: chỉ truy cập qua công cụ có kiểm soát (bastion, query gateway); cấm kết nối trực tiếp từ máy cá nhân; câu lệnh thay đổi dữ liệu cần phê duyệt trước.
- Hệ thống AI nội bộ (RAG/chatbot): kiểm tra Membership và Access Scope **trước khi retrieval**; người dùng không có quyền trên tài liệu thì hệ thống không đưa nội dung tài liệu đó vào ngữ cảnh trả lời.

## 6. Trách nhiệm

| Vai trò | Trách nhiệm |
|---|---|
| Nhân viên | Chỉ dùng quyền cho công việc; không chia sẻ quyền/phiên đăng nhập; báo ngay khi thấy mình có quyền thừa |
| Project Owner / Trưởng bộ phận | Xác nhận nhu cầu, rà soát quyền định kỳ, yêu cầu thu hồi khi thành viên rời dự án |
| Security | Phê duyệt, giám sát, cảnh báo bất thường, tổng rà soát |
| IT | Thực thi cấp/thu hồi đúng phê duyệt, đúng SLA |

## 7. Vi phạm

- Truy cập vượt quyền có chủ đích, chia sẻ quyền cho người khác, che giấu quyền thừa: xử lý kỷ luật theo HR-POL-005; trường hợp gây lộ dữ liệu xử lý ở mức nghiêm trọng và có thể chịu trách nhiệm pháp lý.
- Phát hiện quyền cấp sai/thừa do quy trình: báo Security để điều chỉnh — người chủ động báo không bị xem là vi phạm.

## 8. Kênh hỗ trợ và SLA

| Loại yêu cầu | SLA |
|---|---|
| Cấp quyền chuẩn theo Role | 2 ngày làm việc |
| Quyền nhạy cảm / dữ liệu Restricted | 5 ngày làm việc |
| Quyền khẩn cấp just-in-time | 30 phút – 4 giờ |
| Khiếu nại bị chặn quyền sai | 2 ngày làm việc |
| Báo quyền thừa / bất thường | Xác nhận trong 4 giờ |

**Từ khóa định tuyến về Security:** quyền truy cập, access, ACL, phân quyền, RBAC, role, access scope, không có quyền, bị chặn quyền, xin quyền, cấp quyền, thu hồi quyền, permission, admin, đặc quyền, access review.


## 9. Mô hình Joiner–Mover–Leaver

Access lifecycle phải nhận tín hiệu tin cậy từ HR/project membership. Joiner chỉ nhận quyền chuẩn của role; Mover thu hồi quyền không còn cần trước/đồng thời cấp quyền mới; Leaver thu hồi theo thời điểm HR xác nhận, ưu tiên khóa ngay với trường hợp rủi ro.

## 10. RBAC, ABAC và entitlement

RBAC là baseline; ABAC/conditional access có thể bổ sung theo project, device posture, environment, data classification hoặc thời gian. Quyền thực tế (entitlement) phải đủ nhỏ để review được; group “super-user” rộng không được dùng để thay thế thiết kế quyền.

## 11. Privileged Access Management (PAM)

- admin/production account tách tài khoản thường;
- ưu tiên JIT/JEA, MFA chống phishing và session logging;
- không chia sẻ admin account giữa nhiều người;
- break-glass account được quản lý riêng, cảnh báo mọi lần sử dụng;
- privileged role có expiry/review date rõ ràng.

## 12. Access request quality

Yêu cầu phải nêu **tài nguyên + mức quyền + mục đích + thời hạn**. “Cần giống bạn A” không phải business justification đầy đủ. Chủ tài nguyên xác nhận nhu cầu; Security kiểm tra policy/risk; IT/platform thực thi đúng quyết định đã phê duyệt.

## 13. Access review

Reviewer phải nhìn thấy entitlement thực tế và last-used khi có. Ba kết quả hợp lệ: retain, modify, revoke. Không xác nhận hàng loạt nếu không hiểu quyền. Quyền nhạy cảm không có owner hoặc không xác minh được nhu cầu phải tạm khóa/escalate.

## 14. Non-human identities

Service account, bot, CI identity và integration token cũng thuộc access control. Mỗi identity cần owner, scope, environment, phương thức xác thực, rotation/expiry phù hợp và không được “mượn” quyền user rộng hơn nhu cầu.

## 15. Logging và anomaly detection

Ghi log tối thiểu cho grant/revoke, privileged session, access vào dữ liệu Restricted và thay đổi policy/role quan trọng. Tín hiệu bất thường chuyển SEC-POL-004 khi nghi compromise.

## 16. Deny và appeal

Yêu cầu bị từ chối phải có lý do ở mức đủ hành động: thiếu owner approval, vượt role, cần training, cần JIT hoặc tài nguyên không được phép. Người dùng có thể appeal qua Security; không tự tìm đường vòng bằng account khác.
