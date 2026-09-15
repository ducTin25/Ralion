# Chính sách Quản lý Lỗ hổng và Vá lỗi

- **Mã tài liệu:** ENG-POL-002
- **Phiên bản:** 1.0 — Ngày hiệu lực: 01/01/2026
- **Bộ phận ban hành:** Security Engineering & IT Operations
- **Phạm vi áp dụng:** Ứng dụng, server, endpoint, container, cloud resource và dependency do công ty quản lý
- **Tài liệu liên quan:** ENG-POL-001; IT-POL-006; SEC-POL-004; IT-POL-005

## 1. Mục đích

Đảm bảo vulnerability được triage theo rủi ro thực tế, remediation trong thời hạn rõ ràng và exception không trở thành trì hoãn vô thời hạn.

## 2. Nguồn phát hiện

Scanner, penetration test, bug bounty/responsible disclosure, vendor advisory, dependency alert, code review, incident hoặc nhân viên phát hiện.

## 3. Triage

Severity không chỉ dựa CVSS; xem thêm exposure, exploitability, asset criticality, dữ liệu, privilege và compensating controls.

| Priority | Ví dụ | Mục tiêu remediation |
|---|---|---|
| Critical | Exploited/internet-facing RCE, auth bypass nghiêm trọng | 24–72 giờ tùy exposure; có thể emergency change |
| High | Khả năng khai thác cao, impact lớn | 14 ngày |
| Medium | Impact/exploitability trung bình | 30–60 ngày |
| Low | Rủi ro thấp | Theo backlog, mục tiêu ≤ 90 ngày |

Security có thể rút ngắn/điều chỉnh deadline dựa trên threat intelligence hoặc business context.

## 4. Patch endpoint/hạ tầng

- Critical security patch có exploit active: ưu tiên accelerated deployment sau test tối thiểu.
- Patch thường: theo maintenance cadence; thiết bị người dùng phải giữ OS trong support window.
- Không trì hoãn patch chỉ vì “chưa thấy exploit” nếu deadline remediation đã áp dụng.

## 5. Application vulnerability

Owner service chịu trách nhiệm fix/mitigate. Security xác nhận closure dựa trên rescan/test/evidence phù hợp; ticket “Done” của team không tự đồng nghĩa vulnerability đã đóng.

## 6. Exception/Risk acceptance

Khi không thể fix đúng hạn, cần documented acceptance: lý do, business impact, compensating control, owner, expiry và kế hoạch fix. Critical exploited issue không được accepted dài hạn chỉ vì chi phí.

## 7. Emergency và incident

Nếu vulnerability đang bị khai thác hoặc có dấu hiệu compromise, xử lý như incident theo SEC-POL-004 song song với remediation. Production hotfix theo IT-POL-006 Emergency Change.

## 8. Public disclosure

Không tự public vulnerability của hệ thống công ty khi chưa theo responsible disclosure/Legal/Communications. Báo cáo từ researcher ngoài được Security tiếp nhận và phối hợp.

## 9. Metrics

Theo dõi: open findings theo severity, aging, SLA breach, recurrence, mean time to remediate và exception expiry. Metric dùng cải tiến hệ thống, không dùng đơn thuần để quy lỗi cá nhân.

## 10. Tình huống thường gặp

- **Dependency Critical nhưng code path không reachable:** có thể downgrade/exception nếu có evidence, không auto-ignore.
- **CVE medium trên internet-facing auth service:** Security có thể tăng priority do context.
- **Patch cần restart prod:** phối hợp change window; nếu active exploit thì emergency path.

## 11. Kênh và SLA

| Yêu cầu | SLA |
|---|---|
| Báo vulnerability mới | Security triage 1 ngày làm việc; Critical ưu tiên ngay |
| Exception | Review trước remediation deadline |
| External disclosure | Security acknowledgement mục tiêu 3 ngày làm việc |
| Critical exploited | Incident response ngay |

**Từ khóa định tuyến:** lỗ hổng, vulnerability, CVE, patch, vá lỗi, CVSS, exploit, SAST finding, pentest, remediation, risk acceptance.
