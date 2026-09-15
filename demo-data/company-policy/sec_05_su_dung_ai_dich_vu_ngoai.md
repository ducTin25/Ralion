# Chính sách Sử dụng AI và Dịch vụ Bên ngoài

- **Mã tài liệu:** SEC-POL-005
- **Phiên bản:** 1.5 — Ngày hiệu lực: 01/01/2026
- **Bộ phận ban hành:** Phòng An toàn Thông tin, phối hợp Phòng CNTT và Pháp chế
- **Phạm vi áp dụng:** Mọi việc sử dụng công cụ AI (chatbot, trợ lý code, dịch vụ sinh nội dung) và dịch vụ SaaS bên ngoài cho công việc
- **Tài liệu liên quan:** SEC-POL-002 (Phân loại dữ liệu), SEC-POL-003 (Secret), IT-POL-004 (Phần mềm)

## 1. Mục đích

Cho phép nhân viên khai thác công cụ AI để tăng năng suất, đồng thời kiểm soát rủi ro lộ dữ liệu, sai lệch thông tin và vi phạm pháp lý khi dùng dịch vụ bên ngoài.

## 2. Nguyên tắc chung

- Công ty **khuyến khích dùng AI** cho công việc, với điều kiện dùng **công cụ trong danh mục phê duyệt** và tuân thủ quy tắc dữ liệu dưới đây.
- Dùng công cụ AI ngoài danh mục cho công việc: phải đăng ký đánh giá theo quy trình IT-POL-004 mục 3 trước khi dùng.
- Người dùng chịu trách nhiệm cuối cùng về sản phẩm công việc — AI là công cụ hỗ trợ, không thay thế trách nhiệm kiểm tra.

## 3. Quy tắc dữ liệu khi dùng AI bên ngoài

| Mức dữ liệu | Được đưa vào AI công cộng (bản free/cá nhân) | Được đưa vào AI doanh nghiệp đã phê duyệt* |
|---|---|---|
| Public | Được | Được |
| Internal | Không | Được |
| Confidential | **Không** | Chỉ khi hợp đồng có cam kết không train trên dữ liệu và đã được Security duyệt cho loại dữ liệu đó |
| Restricted | **Không** | **Không**, trừ phê duyệt riêng từng trường hợp |

\* AI doanh nghiệp đã phê duyệt: phiên bản có hợp đồng doanh nghiệp, cam kết bảo mật, không dùng dữ liệu khách hàng để huấn luyện.

Cấm tuyệt đối đưa vào bất kỳ công cụ AI bên ngoài nào: secret/API key, mật khẩu, dữ liệu cá nhân nhạy cảm, thông tin lương, tài liệu M&A, dữ liệu khách hàng chưa ẩn danh.

## 4. AI trong phát triển phần mềm

- Trợ lý code (Copilot, Claude Code...) dùng bản doanh nghiệp công ty cấp; bật chế độ không lưu/không train nếu có.
- Code do AI sinh ra: **bắt buộc review như code người viết** — kiểm tra bảo mật, license của đoạn mã gợi ý, và không copy nguyên văn code có bản quyền không rõ nguồn.
- Không dán toàn bộ file cấu hình, schema database production, hoặc log chứa dữ liệu thật vào prompt; trích phần cần thiết và thay giá trị nhạy cảm bằng placeholder.
- Ứng dụng công ty tích hợp LLM: khóa API chỉ ở backend (SEC-POL-003); đầu vào người dùng phải được kiểm soát chống prompt injection; đầu ra hiển thị cho khách hàng phải có kiểm duyệt phù hợp.

## 5. Hệ thống AI nội bộ (chatbot/RAG công ty)

- Hệ thống AI nội bộ truy xuất tài liệu phải kiểm tra **quyền của người hỏi trước khi retrieval** (theo SEC-POL-001): người không có quyền trên tài liệu thì câu trả lời không được chứa nội dung tài liệu đó.
- Câu trả lời phải kèm **trích dẫn nguồn (citation)**; khi không đủ nguồn tin cậy, hệ thống trả lời "không đủ dữ liệu" thay vì suy đoán.
- AI nội bộ **không được tự thực hiện** các hành động thay đổi trạng thái quan trọng: ghi database, cấp quyền, phê duyệt, đóng quy trình — các hành động này luôn cần con người xác nhận.
- Log hội thoại với AI nội bộ được lưu phục vụ kiểm toán; không nhập nội dung cá nhân riêng tư không liên quan công việc.

## 6. Rủi ro cần nhận thức khi dùng AI

- **Ảo giác (hallucination):** AI có thể trả lời sai với giọng tự tin — luôn kiểm chứng số liệu, điều khoản pháp lý, API/thư viện có thật không trước khi dùng.
- **Bản quyền:** nội dung AI sinh ra có thể trùng nguồn có bản quyền; nội dung đối ngoại (marketing, hợp đồng) phải qua rà soát của người có trách nhiệm.
- **Deepfake/lừa đảo bằng AI:** cảnh giác cuộc gọi/video giả giọng lãnh đạo yêu cầu chuyển tiền, cung cấp OTP — luôn xác minh qua kênh thứ hai đã biết trước; nghi ngờ → báo Security theo SEC-POL-004.

## 7. Dịch vụ SaaS bên ngoài (ngoài AI)

- Đăng ký dịch vụ SaaS mới cho công việc (form khảo sát, công cụ quản lý, lưu trữ...) bằng **email công ty** và phải nằm trong danh mục phê duyệt; dịch vụ chưa có → quy trình IT-POL-004.
- Cấm dùng tài khoản cá nhân cho dữ liệu công việc từ mức Internal trở lên.
- Trước khi kết nối SaaS với hệ thống công ty (OAuth, webhook, API): tạo ticket Security đánh giá phạm vi quyền xin cấp; thu hồi kết nối không dùng sau 90 ngày.
- Nhà cung cấp xử lý dữ liệu Confidential trở lên: cần thỏa thuận xử lý dữ liệu (DPA) do Pháp chế rà soát.

## 8. Vi phạm và xử lý

- Đưa dữ liệu Confidential/Restricted vào AI công cộng: xử lý như sự cố lộ dữ liệu theo SEC-POL-004 — báo ngay trong 1 giờ, người chủ động báo được xem xét giảm nhẹ.
- Dùng dịch vụ ngoài danh mục kéo dài sau cảnh báo: xử lý kỷ luật theo HR-POL-005.

## 9. Kênh hỗ trợ và SLA

| Loại yêu cầu | SLA |
|---|---|
| Hỏi công cụ AI nào được phép dùng | 2 ngày làm việc (danh mục công khai trên cổng nội bộ) |
| Đánh giá công cụ AI/SaaS mới | 10–15 ngày làm việc |
| Duyệt kết nối OAuth/API với SaaS | 5 ngày làm việc |
| Báo lỡ đưa dữ liệu nhạy cảm vào AI | **Khẩn cấp — trong 1 giờ, theo SEC-POL-004** |

**Từ khóa định tuyến về Security:** AI, ChatGPT, Claude, Copilot, chatbot, LLM, prompt, RAG, đưa dữ liệu vào AI, SaaS, dịch vụ ngoài, OAuth, deepfake, hallucination, citation, prompt injection, DPA, công cụ bên ngoài.


## 10. Phân tầng công cụ AI

| Tier | Ví dụ sử dụng | Điều kiện |
|---|---|---|
| Public AI | brainstorm với dữ liệu Public | không login bằng account cá nhân để xử lý dữ liệu công việc nhạy cảm; không nhập Internal+ |
| Enterprise Approved AI | trợ lý văn bản/code được công ty ký hợp đồng | SSO/MFA, cấu hình privacy, data use terms và loại dữ liệu được Security phê duyệt |
| Internal AI/RAG | chatbot nội bộ trên dữ liệu công ty | ACL trước retrieval, citation, logging/audit, data retention phù hợp |
| Restricted/Unapproved | công cụ chưa đánh giá hoặc có điều khoản không phù hợp | không dùng cho dữ liệu/công việc công ty cho đến khi được duyệt |

## 11. Allowed / prohibited use cases

**Được phép khi đáp ứng data rule:** tóm tắt tài liệu được phép, hỗ trợ viết, sinh test, giải thích code, brainstorming, dịch nội dung và tìm phương án kỹ thuật.

**Không được giao hoàn toàn cho AI:** quyết định tuyển dụng/kỷ luật, phê duyệt quyền, thay đổi production, ký kết pháp lý, xác nhận số liệu tài chính, quyết định ảnh hưởng quyền lợi cá nhân hoặc gửi thông tin đối ngoại nhạy cảm mà không có human review phù hợp.

## 12. Prompt/data minimization

Trước khi gửi nội dung vào AI: bỏ secret, token, PII không cần thiết, customer identifiers, production dump và internal URL/architecture không liên quan. Dùng đoạn code/log nhỏ nhất đủ chẩn đoán và placeholder cho giá trị nhạy cảm.

## 13. AI coding assistants

Code sinh bởi AI phải qua cùng quality gate như code người viết: test, code review, SAST/secret scan, dependency/license check và review kiến trúc. Developer chịu trách nhiệm hiểu thay đổi trước merge; “AI tạo ra” không phải lý do miễn trách nhiệm.

Không cho agent tự chạy lệnh destructive/production hoặc truy cập secret rộng nếu chưa có approval/control. Tool permission nên giới hạn workspace, command và environment cần thiết.

## 14. Prompt injection và untrusted content

Ứng dụng LLM phải coi prompt từ người dùng, web, email, tài liệu retrieved và tool output là dữ liệu có thể không tin cậy. Không để nội dung retrieved tự nâng quyền, thay system policy, tiết lộ secret hoặc gọi tool nhạy cảm. Tool action quan trọng cần policy check và human confirmation khi phù hợp.

## 15. Grounding và citation cho RAG

- ACL/project membership lọc trước retrieval.
- Answer factual từ policy/project cần citation tới nguồn có quyền truy cập.
- Khi evidence không đủ, hệ thống nêu thiếu dữ liệu thay vì “điền” bằng kiến thức ngoài phạm vi.
- External/general guidance nếu được sản phẩm cho phép phải được tách rõ khỏi policy-grounded answer để người dùng không nhầm là quy định công ty.

## 16. Vendor assessment cho AI/SaaS

Đánh giá tối thiểu: dữ liệu có dùng để train không, retention, model/provider subprocessors, region, encryption, SSO/MFA, admin controls, export/delete, incident notification, DPA, IP/license terms và khả năng disable connector/tool. Approval có thể giới hạn theo loại dữ liệu/use case thay vì “duyệt toàn bộ sản phẩm”.

## 17. Output validation và human oversight

Nội dung AI dùng cho quyết định quan trọng phải có người có chuyên môn kiểm tra. Đối với code/config, validation ưu tiên test và static checks; đối với số liệu/policy, kiểm tra nguồn; đối với nội dung pháp lý/HR nhạy cảm, chuyển owner chuyên môn khi cần.

## 18. Logging và privacy

Log AI phải đủ cho security/audit nhưng không thu thập dư thừa. Prompt/response có thể chứa dữ liệu nhạy cảm nên áp dụng retention và access control theo SEC-POL-002. Không dùng toàn bộ chat log làm dataset training nội bộ mặc định nếu chưa có purpose/approval phù hợp.
