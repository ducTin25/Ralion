# Chính sách Phát triển Phần mềm An toàn (Secure SDLC)

- **Mã tài liệu:** ENG-POL-001
- **Phiên bản:** 1.0 — Ngày hiệu lực: 01/01/2026
- **Bộ phận ban hành:** Engineering, thẩm định bởi Security
- **Phạm vi áp dụng:** Phần mềm/dịch vụ do công ty phát triển hoặc duy trì
- **Tài liệu tham chiếu:** NIST SSDF; OWASP secure development guidance; SEC-POL-003; IT-POL-006

## 1. Mục đích

Tích hợp security vào vòng đời phát triển thay vì chỉ kiểm tra trước production; tạo baseline rõ cho design, code, dependency, test và release.

## 2. Phân loại thay đổi theo rủi ro

- **Low:** UI/text/refactor không đổi trust boundary hoặc quyền.
- **Medium:** API/business logic, dependency mới, schema, integration.
- **High:** auth/ACL, payment, secret, crypto, dữ liệu Restricted, public upload/parser, privileged action, LLM tool/action, internet-facing admin.

Mức rủi ro quyết định depth của review/security testing; không phải mọi PR cần cùng quy trình.

## 3. Design phase

High-risk feature phải có threat assessment/threat model ở mức phù hợp trước implementation hoặc trước release. Xác định assets, actors, trust boundaries, abuse cases, data classification và failure modes.

## 4. Coding baseline

- Không hardcode secret; theo SEC-POL-003.
- Validate/normalize input ở trust boundary; encode output theo context.
- Authorization phải ở server/backend; không dựa vào UI để bảo vệ dữ liệu.
- Sử dụng library/framework được hỗ trợ; dependency phải pin/lock theo IT-POL-004.
- Không log credential, token hoặc Restricted data ngoài trường hợp được thiết kế và phê duyệt.

## 5. Pull request và review

- Merge vào protected branch cần ít nhất 1 reviewer độc lập; high-risk thay đổi cần reviewer có năng lực phù hợp hoặc Security review theo rule của repo.
- Tác giả không tự approve PR của mình khi hệ thống yêu cầu reviewer độc lập.
- Security-sensitive change phải có test cho negative/unauthorized path, không chỉ happy path.

## 6. Automated checks

Baseline CI theo stack có thể gồm: unit/integration test, SAST, secret scanning, SCA/dependency scan, IaC/container scan và license check. Waiver cho finding phải có lý do, owner và expiry.

## 7. Dependency và supply chain

- Chỉ dùng registry/source được phê duyệt.
- Không nâng dependency blindly khi release note có breaking/security implication.
- Build artifact production phải từ CI tin cậy, có traceability về source commit/version.

## 8. Release

Release theo IT-POL-006. High-risk feature cần evidence rằng required security checks pass hoặc exception còn hiệu lực. Không bypass branch protection chỉ vì deadline demo nếu không theo emergency process.

## 9. AI-assisted coding

AI-generated code được review/test như code người viết. Không đưa secret/dữ liệu cấm vào tool; quy tắc SEC-POL-005 áp dụng. AI suggestion không được coi là nguồn security authority.

## 10. Security defect

Vulnerability phát hiện sau merge/release chuyển ENG-POL-002; nếu có exploitation hoặc nghi lộ dữ liệu thì kích hoạt SEC-POL-004.

## 11. Tình huống thường gặp

- **PR đổi auth middleware 5 dòng:** vẫn high-risk vì trust boundary, cần security-aware review/test.
- **SAST false positive:** có thể waiver với evidence và expiry; không tắt scanner toàn repo.
- **Demo gấp:** vẫn phải giữ controls tối thiểu; emergency change theo IT-POL-006 nếu production.

## 12. Kênh và SLA

| Yêu cầu | SLA |
|---|---|
| Security design consultation | 3–5 ngày làm việc |
| High-risk PR review | Theo team SLA, mục tiêu 2 ngày làm việc |
| CI security finding support | 2 ngày làm việc |
| Exception | Security/Risk owner xem xét trước release |

**Từ khóa định tuyến:** secure SDLC, code review, threat model, SAST, SCA, dependency, branch protection, security review, CI, pull request, software security.
