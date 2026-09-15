# Chính sách Quản lý Rủi ro Nhà cung cấp và Bên thứ ba

- **Mã tài liệu:** TPRM-POL-001
- **Phiên bản:** 1.0 — Ngày hiệu lực: 01/01/2026
- **Bộ phận ban hành:** Security, Procurement và Legal
- **Phạm vi áp dụng:** Vendor, SaaS, consultant, processor, outsource, partner có quyền truy cập dữ liệu/hệ thống hoặc cung cấp dịch vụ quan trọng
- **Tài liệu liên quan:** FIN-POL-002; LEG-POL-002; SEC-POL-002; SEC-POL-005; SEC-POL-001

## 1. Mục đích

Đảm bảo rủi ro bên thứ ba được đánh giá theo mức độ trước onboarding, theo dõi trong thời gian hợp tác và xử lý khi offboard.

## 2. Phân tầng rủi ro vendor

| Tier | Tiêu chí điển hình | Review |
|---|---|---|
| Tier 1 — Critical | Production dependency, dữ liệu Restricted/khách hàng quy mô lớn, single point of failure | Security + Legal + BCP; hằng năm |
| Tier 2 — High | Confidential data, privileged integration, business-critical SaaS | Security/Privacy; 12–24 tháng |
| Tier 3 — Standard | Internal data hạn chế, dịch vụ thay thế được | Questionnaire/risk check |
| Tier 4 — Low | Không nhận dữ liệu nội bộ, hàng hóa thông thường | Procurement checks cơ bản |

## 3. Due diligence trước hợp đồng

Tùy tier, yêu cầu có thể gồm: security questionnaire, kiến trúc/data flow, certifications/audit report, breach history, subprocessor, data location, BCP/DR, vulnerability management, insurance, financial viability và integrity check.

Không yêu cầu mọi vendor cung cấp cùng một bộ bằng chứng; review phải risk-based.

## 4. Dữ liệu và quyền truy cập

- Chỉ chia sẻ dữ liệu tối thiểu cần thiết.
- Vendor account phải riêng biệt, có owner, thời hạn, MFA và log theo SEC-POL-001.
- Production privileged access dùng JIT/time-bound khi khả thi; shared account bị cấm trừ giải pháp legacy có compensating control được Security duyệt.

## 5. Hợp đồng

Vendor xử lý dữ liệu hoặc dịch vụ quan trọng cần điều khoản phù hợp về confidentiality, security, incident notification, return/deletion, subprocessor, audit/cooperation và termination theo Legal review.

## 6. Monitoring

- Tier 1/2 được reassess theo chu kỳ hoặc khi có trigger: breach, acquisition, major architecture change, service degradation, thay data region/subprocessor.
- Owner theo dõi SLA, renewal và issue; Security theo dõi risk findings.

## 7. Finding và exception

Risk finding phải có severity, owner, due date và remediation/acceptance. Risk acceptance có thời hạn; không coi questionnaire “đã điền” là đã xử lý rủi ro.

## 8. Offboarding vendor

Khi kết thúc: thu hồi account/API/OAuth, rotate secret liên quan, lấy xác nhận trả/xóa dữ liệu khi hợp đồng yêu cầu, chuyển ownership tài liệu và đóng recurring payment.

## 9. Vendor incident

Incident của vendor ảnh hưởng dữ liệu/dịch vụ công ty phải được báo Security theo SEC-POL-004. Contract Owner không tự giao tiếp với khách hàng/báo chí về breach nếu chưa có Incident/Legal coordination.

## 10. Tình huống thường gặp

- **SaaS nhỏ nhưng cần OAuth read toàn bộ Drive:** rủi ro cao hơn giá tiền; cần Security review.
- **Vendor có ISO 27001:** là bằng chứng hữu ích nhưng không tự miễn review data flow/contract.
- **Consultant cần prod 2 ngày:** cấp account riêng JIT, không cho mượn tài khoản nhân viên.

## 11. Kênh và SLA

| Yêu cầu | SLA mục tiêu |
|---|---|
| Tier 3 standard review | 5 ngày làm việc |
| Tier 1/2 review | 10–15 ngày làm việc |
| Emergency vendor access | Security triage trong ngày |
| Offboarding vendor | Access thu hồi chậm nhất ngày kết thúc |

**Từ khóa định tuyến:** vendor, nhà cung cấp, third party, SaaS, due diligence, SOC 2, ISO 27001, processor, subprocessor, vendor risk, outsource.
