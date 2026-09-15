# PhoneShop API — Access & Security

## Triết lý bảo mật
PhoneShop xử lý dữ liệu thanh toán và thông tin cá nhân của hàng trăm nghìn khách hàng, nên bảo mật được xem là ưu tiên hàng đầu ngang với tính năng sản phẩm, không phải việc "làm sau". Mọi thay đổi liên quan tới auth, payment, hoặc dữ liệu cá nhân đều bắt buộc có review từ Security team trước khi merge, không chỉ review thông thường từ Tech Lead.

## Xin quyền truy cập
| Hệ thống | Cách xin | Ai duyệt | Thời gian xử lý |
|---|---|---|---|
| Repo GitHub (team `phoneshop-backend`) | PM thêm trực tiếp qua GitHub Org settings, dựa trên onboarding checklist | PM | Trong ngày làm việc đầu tiên |
| Database staging (read-only) | Xin qua kênh Slack #phoneshop-infra, kèm lý do cụ thể | Tech Lead | 1 ngày làm việc |
| Database production | KHÔNG cấp trực tiếp cho engineer thường — mọi truy cập qua bastion host có audit log đầy đủ, chỉ Lead/PM/on-call hiện tại mới có quyền | Engineering Manager | Xét duyệt riêng từng trường hợp, có thời hạn |
| VPN nội bộ | Form IT chuẩn (`it.company.com/vpn-request`), cần laptop công ty đã cài MDM | IT | 1-2 ngày làm việc |
| RabbitMQ Management UI / Datadog / Sentry | Tự động cấp khi vào team, SSO qua Google Workspace, không cần xin riêng | — | Ngay khi có tài khoản công ty |
| AWS Console (read-only staging) | Xin qua IT kèm xác nhận từ Tech Lead, MFA bắt buộc | IT + Tech Lead | 1-2 ngày làm việc |
| AWS Console production | Chỉ Engineering Manager, DevOps Lead, và on-call theo lịch mới có quyền tạm thời (time-boxed, tự động thu hồi sau 8 giờ) | Engineering Manager | Xét duyệt riêng, thường dùng khi xử lý sự cố |

## Quy tắc bảo mật cụ thể
- Không commit file `.env` hoặc bất kỳ credential nào lên git — dùng `git-secrets` hook đã cài sẵn để tự động chặn commit chứa pattern giống API key/token (`pre-commit` config trong repo, chạy tự động khi `poetry install` xong).
- API key cổng thanh toán (VNPay/Momo) và 3 đối tác trả góp chỉ lưu trong **AWS Secrets Manager**, service đọc qua IAM role gán cho pod Kubernetes lúc runtime — không inject qua biến môi trường plaintext ở production (khác với môi trường dev, nơi vẫn dùng `.env` cho tiện, nhưng dùng key sandbox/test riêng của từng đối tác, không phải key thật).
- Mọi endpoint liên quan tới đơn hàng/thanh toán bắt buộc có JWT hợp lệ (issued bởi Auth Service riêng, TTL 1 giờ, refresh token TTL 30 ngày, có cơ chế revoke khi phát hiện bất thường) cộng với rate limit 100 request/phút/user (Redis-backed sliding window algorithm, chặn ở tầng Kong trước khi vào tới service).
- PII khách hàng (số điện thoại, địa chỉ giao hàng, thông tin CCCD nếu có cho hồ sơ trả góp) được **mã hoá tại tầng ứng dụng** (application-level encryption dùng AWS KMS, không chỉ dựa vào encryption-at-rest của RDS) trước khi lưu Postgres — đảm bảo kể cả backup hoặc snapshot database bị lộ cũng không đọc được dữ liệu gốc.
- Log tuyệt đối không được chứa: số thẻ thanh toán, mã OTP, JWT token đầy đủ (chỉ log 6 ký tự đầu để phục vụ trace/debug), mật khẩu dưới bất kỳ hình thức nào kể cả đã hash.
- Mọi truy vấn database từ code phải dùng parameterized query (SQLAlchemy ORM tự đảm bảo điều này, nhưng nếu viết raw SQL cho tối ưu hiệu năng thì bắt buộc dùng bind parameter, tuyệt đối không string-format trực tiếp giá trị vào câu SQL).

## Compliance
Hệ thống thanh toán tuân theo checklist **PCI-DSS cấp độ SAQ-A** (không tự lưu trữ thông tin thẻ thanh toán trong hệ thống của mình, mọi giao dịch xử lý qua cổng thanh toán bên thứ 3 đã có chứng nhận PCI-DSS đầy đủ — VNPay và Momo đều đạt chuẩn này). Audit bảo mật định kỳ 6 tháng/lần do Security team nội bộ thực hiện, kèm penetration test hàng năm thuê bên thứ 3 độc lập thực hiện.

Về bảo vệ dữ liệu cá nhân, hệ thống tuân theo Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân — có cơ chế cho khách hàng yêu cầu xoá tài khoản và toàn bộ dữ liệu liên quan (quy trình xử lý trong vòng 30 ngày theo quy định).

## Xử lý sự cố bảo mật
Nếu phát hiện hoặc nghi ngờ có lỗ hổng bảo mật, dù nhỏ hay lớn:
1. Báo ngay cho Security team qua kênh #security-incident (response SLA: 15 phút trong giờ hành chính, 1 giờ ngoài giờ thông qua PagerDuty escalation).
2. Không tự ý public thông tin lỗ hổng ra ngoài dưới bất kỳ hình thức nào, kể cả trong Slack channel công khai nội bộ của công ty — kể cả khi đã fix xong, việc công bố (nếu cần) sẽ do Security team và Legal quyết định.
3. Không tự ý "thử nghiệm" khai thác lỗ hổng trên môi trường production để xác minh — báo cáo với đầy đủ thông tin tái hiện (nếu có) và để Security team xử lý.
