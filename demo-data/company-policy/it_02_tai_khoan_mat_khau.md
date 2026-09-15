# Chính sách Tài khoản và Mật khẩu

- **Mã tài liệu:** IT-POL-002
- **Phiên bản:** 4.0 — Ngày hiệu lực: 01/01/2026
- **Bộ phận ban hành:** Phòng CNTT, thẩm định bởi Phòng An toàn Thông tin
- **Phạm vi áp dụng:** Mọi tài khoản trên hệ thống công ty (nhân viên, nhà thầu, tài khoản dịch vụ)
- **Tài liệu tham chiếu:** NIST SP 800-63B; SEC-POL-001 (Phân quyền truy cập)

## 1. Mục đích

Quy định vòng đời tài khoản và tiêu chuẩn xác thực nhằm giảm rủi ro chiếm đoạt tài khoản — nguyên nhân hàng đầu của các sự cố an toàn thông tin.

## 2. Vòng đời tài khoản

### 2.1. Tạo tài khoản

- Tài khoản chỉ được tạo theo yêu cầu từ HR (nhân viên mới) hoặc quản lý dự án (nhà thầu), qua IT Service Desk.
- Định dạng chuẩn: `ten.ho@congty.com`; trùng tên thêm số thứ tự.
- Tài khoản mới cấp kèm mật khẩu tạm **bắt buộc đổi ngay lần đăng nhập đầu** và bắt buộc bật MFA trước khi truy cập bất kỳ hệ thống nào khác.
- Nhà thầu/cộng tác viên: tài khoản có **ngày hết hạn** theo thời hạn hợp đồng, tự động vô hiệu hóa khi đến hạn.

### 2.2. Thay đổi và tạm khóa

- Chuyển bộ phận: IT cập nhật group/quyền theo yêu cầu đã được Security duyệt trong 2 ngày làm việc.
- Nghỉ dài hạn (thai sản, nghỉ không lương trên 30 ngày): tài khoản chuyển trạng thái tạm khóa, kích hoạt lại khi đi làm.

### 2.3. Thu hồi

- Nghỉ việc: vô hiệu hóa toàn bộ tài khoản trong **24 giờ** sau ngày làm việc cuối; email chuyển tiếp về quản lý trong 30 ngày rồi xóa theo quy trình lưu trữ.
- Tài khoản không đăng nhập **90 ngày** liên tục: tự động tạm khóa, cần IT xác minh trước khi mở lại.

## 3. Tiêu chuẩn mật khẩu

- Độ dài tối thiểu **12 ký tự** (khuyến nghị dùng passphrase — cụm từ dài dễ nhớ khó đoán).
- Không chứa tên đăng nhập, tên công ty, ngày sinh; không trùng 5 mật khẩu gần nhất.
- Chu kỳ đổi: **90 ngày** với tài khoản đặc quyền (admin); tài khoản thường không bắt buộc đổi định kỳ nếu bật MFA, nhưng **bắt buộc đổi ngay** khi có nghi ngờ lộ.
- Nghiêm cấm: dùng chung mật khẩu công ty cho dịch vụ cá nhân, ghi mật khẩu ra giấy/file không mã hóa, chia sẻ mật khẩu cho bất kỳ ai — kể cả IT (IT không bao giờ hỏi mật khẩu của bạn).
- Khuyến nghị dùng trình quản lý mật khẩu công ty cấp (password manager) cho mọi tài khoản công việc.

## 4. Xác thực đa yếu tố (MFA)

- **Bắt buộc** với: email, VPN, hệ thống nội bộ, cloud console, repository.
- Phương thức chấp nhận theo thứ tự ưu tiên: khóa bảo mật vật lý (FIDO2) → ứng dụng authenticator → OTP qua SMS (chỉ khi không có lựa chọn khác).
- Mất thiết bị MFA: báo IT ngay để thu hồi và đăng ký lại; xác minh danh tính trực tiếp hoặc qua video call với camera bật.
- Cảnh giác **MFA fatigue**: nếu nhận yêu cầu phê duyệt MFA mà bạn không thao tác — từ chối và báo Security ngay.

## 5. Tài khoản đặc quyền (Privileged Account)

- Tài khoản admin tách riêng tài khoản làm việc hằng ngày; chỉ dùng khi thao tác quản trị.
- Cấp phát theo quy trình phê duyệt của Security, rà soát mỗi quý, ghi log toàn bộ phiên thao tác.
- Tài khoản dịch vụ (service account): không dùng để đăng nhập tương tác; credential lưu trong secret manager (xem SEC-POL-003), gán owner chịu trách nhiệm và luân chuyển khóa định kỳ.

## 6. Khóa tài khoản và khôi phục

- Nhập sai mật khẩu **5 lần liên tiếp**: khóa tạm 15 phút; sai tiếp 5 lần: khóa cứng, phải qua IT mở.
- Quy trình reset mật khẩu: tạo ticket hoặc gọi hotline IT → xác minh danh tính (thông tin nhân sự + xác nhận của quản lý nếu cần) → cấp mật khẩu tạm một lần → bắt buộc đổi ngay.
- SLA reset: **4 giờ làm việc**; trường hợp khẩn (đang on-call, sự cố production) xử lý ưu tiên trong 30 phút.

## 7. Giám sát và cảnh báo

- Hệ thống giám sát đăng nhập bất thường: sai giờ, sai vị trí địa lý, thiết bị lạ — tự động yêu cầu xác thực bổ sung hoặc khóa phiên.
- Nhân viên nhận cảnh báo đăng nhập lạ: kiểm tra và báo Security nếu không phải mình thao tác.
- IT/Security có quyền thu hồi phiên đăng nhập và buộc đổi mật khẩu khi phát hiện rủi ro, thông báo cho người dùng sau khi xử lý.

## 8. Kênh hỗ trợ và SLA

| Loại yêu cầu | Mức ưu tiên | SLA xử lý |
|---|---|---|
| Quên mật khẩu / khóa tài khoản | P3 | 4 giờ làm việc |
| Khẩn cấp (on-call, production) | P1 | 30 phút |
| Mất thiết bị MFA | P2 | 4 giờ |
| Tạo tài khoản nhân viên mới | P4 | Trước ngày vào làm |
| Nghi ngờ tài khoản bị chiếm | P1 → chuyển Security | 15 phút |

**Từ khóa định tuyến về IT:** tài khoản, mật khẩu, password, reset mật khẩu, khóa tài khoản, đăng nhập, MFA, OTP, authenticator, email công ty, quên mật khẩu, đăng nhập lạ, tài khoản mới.


## 9. Chuẩn mật khẩu hiện đại

Đối với hệ thống mới do công ty quản lý, ưu tiên password/passphrase dài và blocklist mật khẩu phổ biến hoặc đã lộ thay vì ép quy tắc ký tự phức tạp. Mật khẩu dùng như yếu tố duy nhất nên đặt ngưỡng tối thiểu cao hơn; hệ thống có MFA vẫn phải hỗ trợ passphrase đủ dài và password manager.

Không yêu cầu đổi mật khẩu định kỳ cho tài khoản thường chỉ vì “đủ 90 ngày”. Bắt buộc đổi khi có dấu hiệu lộ/compromise, sau reset khẩn cấp hoặc theo yêu cầu đặc biệt của hệ thống legacy đã được chấp thuận rủi ro. Tài khoản privileged tuân theo control tăng cường và ưu tiên passwordless/phishing-resistant MFA.

## 10. MFA và phishing-resistant authentication

- Ưu tiên passkey/FIDO2/security key cho admin, production và hệ thống rủi ro cao.
- Push MFA cần number matching hoặc biện pháp chống MFA fatigue khi nền tảng hỗ trợ.
- Recovery code được coi như secret; lưu trong password manager/secure vault, không để trong email/chat.
- Thay đổi phương thức MFA phải qua re-authentication và/hoặc identity verification phù hợp.

## 11. Break-glass account

Hệ thống critical có thể có tài khoản break-glass để khôi phục khi IdP/MFA lỗi. Tài khoản này:

- không dùng vận hành thường ngày;
- credential được bảo vệ trong vault với kiểm soát nhiều người;
- mọi lần truy cập phát cảnh báo và phải review sau sự kiện;
- được kiểm thử định kỳ nhưng không làm lộ secret.

## 12. Service account và workload identity

Ưu tiên managed identity/workload identity thay cho static key. Service account phải có owner, purpose, scope, environment, expiry/review date và không dùng chung giữa ứng dụng không liên quan. Interactive login bị tắt trừ trường hợp kỹ thuật có phê duyệt.

## 13. Joiner–Mover–Leaver và session control

Tạo/đổi/khóa tài khoản phải đồng bộ với HR-POL-003 và SEC-POL-001. Khi phát hiện compromise, IT/Security có quyền revoke toàn bộ session/token, reset authenticator và yêu cầu đăng nhập lại ngay, không chờ SLA request thông thường.

## 14. Monitoring

Các tín hiệu đăng nhập rủi ro gồm impossible travel, thiết bị mới, token reuse, repeated MFA deny, credential stuffing và đăng nhập admin bất thường. Alert severity và response theo SEC-POL-004 khi có dấu hiệu tấn công.
