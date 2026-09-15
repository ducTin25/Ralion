# BO-06 — PROJECT ONBOARDING BUDDY

## Product, Business, UX, AI and Technical Source of Truth

> Tài liệu này là nguồn yêu cầu thống nhất để Claude và các thành viên triển khai BO-06. Khi tài liệu cũ mâu thuẫn với tài liệu này, ưu tiên tài liệu này. Không tự mở rộng phạm vi nếu chưa được nhóm phê duyệt.

---

## 1. Tóm tắt sản phẩm

BO-06 là hệ thống hỗ trợ **kỹ sư phần mềm lần đầu tham gia một dự án đang được phát triển hoặc duy trì tích cực**. Hệ thống giúp Project Manager/Project Owner chuẩn bị tài liệu và lộ trình onboarding, tạo Candidate Plan từ template đã duyệt, hướng dẫn kỹ sư thực hiện từng task và cung cấp RAG Chat trả lời dựa trên tài liệu có nguồn trích dẫn.

Phạm vi kết thúc khi kỹ sư:

1. Hiểu bối cảnh, sản phẩm và quy trình làm việc của dự án.
2. Có đủ quyền truy cập cần thiết.
3. Thiết lập và chạy được môi trường dự án.
4. Hiểu kiến trúc, codebase và convention ở mức đủ để bắt đầu đóng góp.
5. Hoàn thành First Task.
6. First Pull Request được review/merge theo quy trình thật.
7. Không còn blocker bắt buộc và PM xác nhận `ONBOARDING_CLOSED`.

BO-06 **không cam kết kỹ sư hiểu toàn bộ codebase**. Mục tiêu là rút ngắn thời gian từ lúc vào dự án tới lúc đóng góp đầu tiên có hướng dẫn.

---

## 2. Nguyên tắc sản phẩm đã chốt

- Problem-first, không xây Agent chỉ để demo AI.
- Một dự án có nhiều kỹ sư và nhiều tài liệu; một kỹ sư có thể tham gia nhiều dự án.
- Trong MVP không còn `Module`. Tất cả kỹ sư onboarding trong cùng một dự án dùng chung bộ tài liệu và cấu trúc lộ trình đã được PM duyệt.
- Mỗi kỹ sư vẫn có một `OnboardingPlan`/checklist snapshot riêng để lưu tiến độ, deadline và blocker.
- Agent tạo `Candidate Plan` từ template và nguồn đã duyệt; PM phải kiểm tra trước khi phát hành.
- Agent không tự cấp quyền, tự approve plan, tự đánh dấu task `DONE`, tự merge PR hoặc tự đóng onboarding.
- Không yêu cầu nộp hay chấm bằng chứng thủ công cho từng task.
- Project RAG Chat chỉ dùng tài liệu người hỏi được phép truy cập và phải có citation hoặc fallback.
- Human-in-the-loop ở các quyết định: import tài liệu, approve plan, xác nhận First PR và đóng onboarding.

---

## 3. Persona và actor

### 3.1. Persona chính — New Project Engineer

Kỹ sư lần đầu tham gia một dự án cụ thể, có thể là:

- Nhân viên mới vào công ty và dự án.
- Nhân viên nội bộ chuyển sang dự án khác.
- Contractor/kỹ sư thuê ngoài được thêm vào dự án.

Điểm chung: chưa tham gia dự án từ đầu, chưa biết lịch sử, kiến trúc, cách setup, quy trình và convention của dự án.

### 3.2. Project Manager/Project Onboarding Owner

PM, Tech Lead hoặc Senior Engineer hiểu dự án và được Admin gán role `PM` trong `ProjectMembership`.

PM chịu trách nhiệm:

- Quản lý tài liệu PROJECT.
- Chuẩn hóa project template.
- Tạo, review, edit, regenerate và approve Candidate Plan.
- Theo dõi tiến độ và blocker.
- Xác nhận First PR và đóng onboarding.

### 3.3. Admin

- Tạo và khóa tài khoản.
- Tạo dự án.
- Thêm PM/Engineer vào dự án qua `ProjectMembership`.
- Không quản lý nội dung onboarding thay PM.

### 3.4. HR

- Quản lý tài liệu/chính sách công ty thuộc domain `POLICY`.
- Không tạo dự án, không thêm người vào dự án và không duyệt plan.

### 3.5. Quy tắc role

- `User.system_role`: `ADMIN`, `HR` hoặc `NULL`.
- PM/Engineer là role theo dự án, đọc từ `ProjectMembership.project_role` (`PM`, `ENGINEER`).
- Không lưu PM/ENGINEER như role toàn hệ thống.

---

## 4. Bối cảnh và Problem Statement

Kỹ sư lần đầu tham gia một dự án thường không biết bắt đầu từ đâu. Tài liệu có thể nằm rải rác trong README, wiki, ADR, runbook và các file trong repository; một phần bị thiếu hoặc lỗi thời. Họ phải tự đọc code, hỏi PM/Senior hoặc chờ PR review mới biết convention thật.

Điều này dẫn đến:

- Mất thời gian tìm đúng tài liệu và thứ tự cần đọc.
- Chờ quyền truy cập hoặc hỗ trợ nhưng không biết báo cho ai.
- Setup môi trường chậm hoặc sai.
- Senior/PM bị gián đoạn bởi các câu hỏi lặp lại.
- Lỗi convention chỉ được phát hiện muộn trong review.
- Không có tiêu chí thống nhất để biết onboarding đã kết thúc hay chưa.

### Problem Statement chuẩn

> Kỹ sư lần đầu tham gia một dự án phần mềm đang phát triển gặp khó khăn trong việc xác định nơi bắt đầu, tìm tài liệu chính xác, thiết lập môi trường, hiểu codebase và áp dụng convention của dự án. Hiện họ phải tự tìm kiếm, hỏi trực tiếp hoặc chờ PR review, khiến thời gian đóng góp đầu tiên kéo dài và PM/Senior phải hỗ trợ lặp lại. BO-06 cần tạo một lộ trình đã được PM duyệt, hướng dẫn từng task, trả lời có nguồn và theo dõi tới First Pull Request.

---

## 5. Giải pháp hiện tại và hạn chế

| Giải pháp hiện tại | Giá trị | Hạn chế |
|---|---|---|
| Email/Drive/README | Dễ triển khai | Không chỉ rõ thứ tự, tiến độ và điều kiện hoàn thành |
| Wiki nội bộ | Tập trung kiến thức | Dễ lỗi thời; người mới vẫn phải tự tìm |
| Mentor 1:1 | Chính xác theo ngữ cảnh | Không mở rộng; gián đoạn nguồn lực senior |
| Jira/checklist thủ công | Theo dõi task | Không giải thích nội dung và không kết nối tri thức |
| Linter/CI | Bắt rule đã mã hóa | Không giải thích rationale hoặc tri thức ngầm |
| Chatbot RAG đơn giản | Hỏi đáp nhanh | Wiki sai thì chatbot có thể trả lời sai; thiếu ACL/citation |

BO-06 không thay thế Jira, wiki, Git hoặc mentor. BO-06 ghép chúng thành một **onboarding journey có thứ tự, nguồn, trạng thái và người chịu trách nhiệm**.

---

## 6. Baseline cần đo trước pilot

Không được trình bày các số dưới đây như dữ liệu thật nếu chưa khảo sát. Claude phải coi đây là biến đo hoặc mục tiêu pilot.

### 6.1. Baseline vận hành

Thu thập cho 5–10 ca onboarding gần nhất nếu có:

- `time_to_project_run`: giờ từ lúc bắt đầu tới khi chạy được dự án local.
- `time_to_first_task_started`: giờ/ngày tới khi bắt đầu task thật đầu tiên.
- `time_to_first_pr_opened` và `time_to_first_pr_merged`.
- `senior_support_hours`: số giờ PM/Senior hỗ trợ một người mới.
- `repeated_questions`: số câu hỏi lặp lại.
- `blocked_duration`: tổng giờ task ở trạng thái BLOCKED.
- `documentation_search_time`: thời gian tự tìm tài liệu.
- `onboarding_completion_clarity`: tỷ lệ người biết rõ điều kiện kết thúc onboarding.
- `first_pr_rework`: số vòng review do thiếu hiểu biết về convention/setup.

### 6.2. Khảo sát New Engineer

Thang điểm 1–5, bổ sung lựa chọn thời gian khi phù hợp:

1. Tôi biết rõ phải bắt đầu onboarding từ đâu.
2. Các task được sắp theo thứ tự hợp lý.
3. Hướng dẫn trong từng task đủ rõ để thực hiện.
4. Tôi tìm được đúng tài liệu khi cần.
5. Tôi biết hỏi ai khi bị chặn.
6. Thời gian phản hồi khi hỏi hỗ trợ là bao lâu?
7. Tôi chạy được dự án local sau bao lâu?
8. Tôi hiểu kiến trúc và luồng chính ở mức đủ làm task đầu tiên.
9. Tôi hiểu convention về branch, commit và Pull Request.
10. Sau onboarding, tôi sẵn sàng nhận task trong dự án.
11. Nếu có lộ trình và chat có nguồn như BO-06, tôi có muốn sử dụng không?

### 6.3. Khảo sát PM/Senior

1. Mỗi tuần anh/chị dành bao nhiêu giờ hỗ trợ một người mới?
2. Những câu hỏi nào bị lặp lại nhiều nhất?
3. Tài liệu dự án hiện đầy đủ và cập nhật ở mức nào?
4. Người mới thường bị chặn lâu nhất ở bước nào?
5. Khi nào anh/chị xem một người đã hoàn thành onboarding?
6. Có checklist chuẩn dùng lại hay mỗi lần phải tạo mới?
7. Anh/chị có biết task nào đang trễ/BLOCKED không?
8. First PR thường phải sửa bao nhiêu vòng vì convention?
9. Anh/chị có sẵn sàng duyệt Candidate Plan do Agent đề xuất không?
10. Điều kiện bảo mật/quyền nào bắt buộc trước khi dùng AI?

---

## 7. Giá trị và giả thuyết cần kiểm chứng

### 7.1. Giá trị cho Engineer

- Biết bước tiếp theo thay vì tự đoán.
- Giảm thời gian tìm tài liệu và chờ hỗ trợ.
- Nhận câu trả lời có citation.
- Thấy rõ tiến độ và điều kiện kết thúc.

### 7.2. Giá trị cho PM/Senior

- Tái sử dụng template và tài liệu.
- Giảm câu hỏi lặp lại.
- Theo dõi blocker tập trung.
- Không phải viết lộ trình từ đầu cho từng người.

### 7.3. Giá trị cho doanh nghiệp

- Giảm thời gian tới đóng góp đầu tiên.
- Giảm giờ hỗ trợ của nhân sự senior.
- Chuẩn hóa onboarding dự án.
- Giảm rủi ro trả lời không có nguồn và truy cập sai tài liệu.

### 7.4. Mô hình ROI pilot

`Monthly benefit = saved senior hours × senior hourly cost + reduced engineer idle hours × engineer hourly cost`

`Monthly cost = infrastructure + object storage + vector DB + LLM tokens + maintenance hours`

`ROI = (benefit - cost) / cost`

Chỉ kết luận doanh nghiệp sẵn sàng mua sau khi pilot chứng minh lợi ích lớn hơn chi phí và đạt guardrail bảo mật.

---

## 8. Phạm vi MVP

### 8.1. Trong phạm vi

1. Authentication và RBAC.
2. Admin quản lý user, project và membership.
3. HR quản lý POLICY documents.
4. PM tải repository ZIP hoặc file tài liệu dự án.
5. Hệ thống quét file hỗ trợ, đề xuất category, báo file lỗi và nhóm tài liệu thiếu.
6. PM xác nhận import.
7. Object Storage lưu file gốc; PostgreSQL lưu metadata/version/status.
8. Pipeline extract → normalize → chunk → embedding → vector store.
9. Global Master Template và Project Template Version.
10. Agent tạo Candidate Plan `DRAFT`.
11. PM Edit/Regenerate/Approve plan.
12. Engineer xem plan, task detail và cập nhật trạng thái.
13. BLOCKED kèm lý do và attachment tùy chọn.
14. RAG Chat theo PROJECT/POLICY, ACL và citation.
15. First Task và First PR.
16. PM đóng onboarding.

### 8.2. Ngoài phạm vi

- Đánh giá năng lực hoặc cá nhân hóa theo background.
- Phân onboarding theo module.
- Chấm bằng chứng/quiz cho từng task.
- Agent tự cấp quyền hoặc sửa code.
- SupportDepartment/SupportRequest và ticket liên phòng ban.
- Notification chủ động, email reminder, Audit Log UI.
- GitHub/GitLab webhook bắt buộc; MVP có thể nhập First PR URL thủ công.
- Rule mining, Review Digest và cảnh báo code convention tự động.
- Hỗ trợ kỹ sư dài hạn sau `ONBOARDING_CLOSED`.

---

## 9. Hành trình onboarding chuẩn

### Phase 1 — Project Readiness

1. Định hướng dự án: mục tiêu, sản phẩm, team và đầu mối.
2. Quyền truy cập: repository, tài liệu, Jira, secrets và môi trường.
3. Setup: clone, env, dependencies, database, test/smoke test.
4. Kiến trúc/codebase: entry point, luồng chính và khu vực quan trọng.
5. Convention/workflow: branch, commit, coding, security, CI/CD và PR.
6. PM xác nhận `PROJECT_READY` khi task bắt buộc hoàn tất và blocker bắt buộc đã xử lý.

### Phase 2 — Guided First Contribution

7. PM giao First Task thật, nhỏ và rủi ro thấp.
8. Engineer thực hiện, hỏi RAG khi cần.
9. Engineer mở First Pull Request.
10. Reviewer review theo quy trình thật; Engineer sửa comment.
11. PR được merge hoặc PM xác nhận mốc tương đương đã chốt.
12. PM đóng onboarding.

Hai phase là một hành trình liên tục, không phải hai sản phẩm độc lập.

---

## 10. Use case MVP

### UC-01 — Authentication

- Actor: Admin, HR, PM, Engineer.
- Đăng nhập, đăng xuất, refresh token và `/auth/me`.
- Hệ thống trả `system_role` và các `ProjectMembership` đang active.

### UC-02 — Admin quản lý User/Project/Membership

- Admin tạo user và project.
- Admin gán PM/Engineer vào project.
- Một user có thể có nhiều memberships; mỗi cặp `(user_id, project_id)` là duy nhất.

### UC-03 — HR quản lý Policy Documents

- HR upload/update/archive tài liệu POLICY.
- HR không quản lý project hoặc approve plan.

### UC-04 — PM nhập tài liệu dự án

- PM upload repository ZIP hoặc file `PDF/DOCX/MD/TXT`.
- Scanner chỉ phát hiện file ứng viên; không tự import tất cả code.
- Hệ thống đề xuất category dựa trên path, filename và nội dung.
- Báo file không đọc được, trùng checksum, sai định dạng và nhóm tài liệu thiếu.
- PM chọn/bỏ chọn, sửa category rồi xác nhận import.

### UC-05 — Quản lý Template

- Có một Global Master Template mặc định dùng làm khung chung.
- Mỗi project có thể tạo một hoặc nhiều version dựa trên global template.
- Template task gồm category, title pattern, objective, mandatory, estimated minutes và dependency.
- Template không chứa tiến độ cá nhân.

### UC-06 — Tạo Candidate Plan bằng AI

- Đầu vào: Project, Engineer membership, Approved TemplateVersion và DocumentVersion `ACTIVE`.
- Agent giữ task bắt buộc, điền nội dung/hướng dẫn/nguồn, sắp dependency.
- Kết quả luôn là `DRAFT`.
- PM Edit, Regenerate hoặc Approve.

### UC-07 — Engineer thực hiện checklist

- Xem Approved Plan và Task Detail.
- Trạng thái: `NOT_STARTED`, `IN_PROGRESS`, `DONE`, `BLOCKED`.
- Dependency chưa DONE thì không bắt đầu task phụ thuộc.
- Engineer tự đánh dấu DONE; PM không duyệt từng task.

### UC-08 — Báo Blocker

- Chọn category, nhập lý do và có thể tải attachment.
- File attachment lưu Object Storage, DB chỉ lưu storage key/metadata.
- PM cùng dự án nhìn thấy và xử lý qua kênh hiện có.
- Không tạo Support Ticket platform trong MVP.

### UC-09 — Project/Policy RAG Chat

- Chat chung hoặc mở từ Task Detail với `context_plan_task_id`.
- PROJECT chat yêu cầu membership active vào project.
- POLICY chat dành cho user được phép theo rule hệ thống.
- Retrieval chỉ dùng version ACTIVE và metadata đúng domain/project.
- Câu trả lời có citation; thiếu nguồn thì fallback.

### UC-10 — First Task/First PR và đóng onboarding

- First Task là task bắt buộc cuối hành trình.
- First PR URL/trạng thái có thể nhập tay trong MVP.
- PM ghi nhận `first_pr_merged_at`/người xác nhận.
- Chỉ PM được đóng onboarding.

---

## 11. Quy tắc nghiệp vụ

1. Chỉ Admin tạo project và membership.
2. PM chỉ quản lý project mà họ có membership active với `project_role=PM`.
3. Engineer chỉ xem plan/task của chính mình trong project có membership active.
4. Một project có nhiều tài liệu; tài liệu PROJECT bắt buộc có `project_id`.
5. Tài liệu POLICY không thuộc project, vì vậy `project_id=NULL`.
6. Một KnowledgeDocument có nhiều DocumentVersion; không ghi đè version cũ.
7. Chỉ version `ACTIVE` được dùng cho plan generation và RAG.
8. Candidate Plan phải lưu template version và nguồn đã dùng.
9. Chỉ plan `APPROVED/ACTIVE` được phát cho Engineer.
10. Agent không được xóa task mandatory.
11. PlanTask là snapshot thực thi; thay TemplateTask không làm đổi plan đang chạy.
12. Câu trả lời grounded phải có ít nhất một Citation hợp lệ.
13. ACL phải được kiểm tra trước retrieval và kiểm tra lại trước khi trả nội dung/link.
14. `ONBOARDING_CLOSED` cần PM xác nhận; không để Agent tự chuyển.
15. Hệ thống có đúng một Global Master Template làm khung mặc định cho toàn hệ thống.
16. Khi Admin tạo project, hệ thống tạo Project Template ban đầu từ Global Master Template. Nếu global template chưa sẵn sàng, hệ thống phải báo lỗi rõ ràng; không tạo template rỗng âm thầm.
17. Mỗi project chỉ có một Project Template; lịch sử thay đổi nằm trong `TemplateVersion`, không tạo nhiều template song song cho cùng project.
18. Mỗi template chỉ có tối đa một version `APPROVED` tại một thời điểm. Khi duyệt version mới, hệ thống phải archive version cũ và approve version mới trong cùng transaction.
19. Chỉ PM có membership `ACTIVE` trong đúng project mới được sửa template, tạo Candidate Plan và approve plan/version của project đó.
20. Không sửa trực tiếp version đã `APPROVED`; muốn thay đổi phải clone thành version `DRAFT`, chỉnh sửa rồi duyệt lại.
21. Không hard-delete `TemplateTask` đã được `PlanTask` tham chiếu. Task nháp chưa được dùng có thể xóa; dữ liệu đã đi vào plan phải được giữ để bảo toàn lịch sử.
22. Việc đổi thứ tự task phải bảo đảm `display_order` duy nhất trong version và không làm hỏng dependency graph.

---

## 12. Template, checklist và plan khác nhau thế nào

| Khái niệm | Dùng để làm gì | Có trạng thái tiến độ? | Ví dụ |
|---|---|---:|---|
| Global Master Template | Khung chung tái sử dụng | Không | Orientation → Access → Setup → Codebase → First Task → First PR |
| Project Template Version | Phiên bản khung của một project | Không | Điền convention và cách setup của Project Payment |
| Candidate/Onboarding Plan | Lộ trình đã materialize cho một Engineer | Có trạng thái plan | Plan của engineer A tại Project Payment |
| PlanTask/Checklist item | Task thực thi trong plan | Có | “Chạy Payment service local” đang `IN_PROGRESS` |

Kỹ sư cùng một dự án nhận cấu trúc và nội dung giống nhau tại thời điểm plan được tạo, nhưng mỗi người có `PlanTask.status`, deadline và blocker riêng.

---

## 13. Nhóm tài liệu chuẩn

### PROJECT

- `OVERVIEW`: mục tiêu, sản phẩm, team, đầu mối.
- `ARCHITECTURE`: system diagram, ADR, dependency.
- `SETUP`: README, runbook, env mẫu, chạy local.
- `ACCESS_SECURITY`: xin quyền, secret và bảo mật.
- `CODEBASE_GUIDE`: cấu trúc repository, entry point, luồng chính.
- `CONVENTION`: branch, commit, coding, review, CI/CD và PR mẫu.
- `FIRST_TASK`: mô tả task nhỏ và acceptance criteria.

### POLICY

- `COMPANY_POLICY`, `HR_POLICY`, `SECURITY_POLICY`, `BENEFIT`, `WORKING_RULE`, `GENERAL`.

Không tạo bảng riêng cho từng nhóm tài liệu. Dùng một bảng `KnowledgeDocument` và phân biệt bằng domain/category.

---

## 14. Luồng dữ liệu tài liệu và RAG

1. TV1/PM tải repository ZIP hoặc file PROJECT; TV4/HR tải file POLICY.
2. Backend kiểm tra quyền, định dạng, kích thước và checksum.
3. Scanner lập danh sách candidate files và category đề xuất.
4. Coverage validator so sánh với nhóm tài liệu chuẩn, báo thiếu hoặc file không nhận diện.
5. PM/HR xác nhận import.
6. File gốc được lưu vào Object Storage riêng tư.
7. PostgreSQL tạo `KnowledgeDocument` và `DocumentVersion(status=PROCESSING)`.
8. Worker của TV3 đọc đúng version, extract/normalize text và chia chunk.
9. PostgreSQL lưu `DocumentChunk` metadata; vector store lưu embedding với `vector_id`.
10. Thành công: version `ACTIVE`; thất bại: `FAILED` và lưu lý do.
11. Plan generation/RAG chỉ đọc version ACTIVE.
12. Khi file thay đổi, tạo version mới; không ghi đè version cũ.

Object Storage có thể là Cloudinary raw/private, S3, R2 hoặc MinIO. Không lưu toàn bộ binary trong PostgreSQL và không dùng public URL cho tài liệu nội bộ.

---

## 15. AI leverage

### 15.1. Candidate Plan Generation

AI nhận template task và các đoạn tài liệu ACTIVE, sau đó:

- Điền title/objective/instruction.
- Chọn tài liệu tham chiếu.
- Ước lượng thời lượng ở mức hỗ trợ.
- Sắp dependency có kiểm tra deterministic.

AI không được thay đổi quyền hoặc phê duyệt kết quả.

### 15.2. Grounded RAG Chat

- Query rewriting có project/task context.
- Metadata-filtered vector retrieval.
- LLM tổng hợp từ context đã lọc.
- Citation validator.
- Fallback khi không đủ bằng chứng.

### 15.3. Phần deterministic, không cần AI

- Authentication/RBAC.
- State transition.
- Dependency validation.
- Kiểm tra loại file/checksum.
- Điều kiện đóng onboarding.
- Tính progress/deadline.

---

## 16. Mô hình dữ liệu cốt lõi

### Identity/Project

- `User(user_id, email, display_name, system_role, status, created_at)`
- `Project(project_id, key, name, created_by_admin_id, status, created_at)`
- `ProjectMembership(membership_id, user_id, project_id, project_role, status, joined_at)`

### Knowledge

- `KnowledgeDocument(document_id, knowledge_domain, project_id?, category fields, title, source_url, status, created_by_user_id)`
- `DocumentVersion(version_id, document_id, version_no, storage_uri/key, checksum, status, created_at)`
- `DocumentChunk(chunk_id, version_id, heading, content, chunk_index, token_count, vector_id)`

### Template/Plan

- `OnboardingTemplate(template_id, project_id?, source_template_id?, scope, name, status)`
- `TemplateVersion(version_id, template_id, version_no, status, approved_by, approved_at)`
- `TemplateTask(template_task_id, version_id, category, title_pattern, objective, mandatory, estimated_minutes)`
- `TaskDependency(predecessor_task_id, successor_task_id)`
- `OnboardingPlan(plan_id, membership_id, template_version_id, revision, status, created_at, approved_by_user_id, approved_at, first_pr_url, first_pr_merged_at, first_pr_confirmed_by_user_id, closed_at)`
- `PlanTask(plan_task_id, plan_id, template_task_id, title, instruction, mandatory, due_at, status)`
- `PlanTaskSource(plan_task_id, version_id, chunk_id?, citation_note)`
- `Blocker(blocker_id, plan_task_id, reported_by_membership_id, category, reason, status, reported_at, resolved_at)`
- `BlockerAttachment(attachment_id, blocker_id, storage_key, file_name, mime_type, uploaded_at)`

### Chat

- `ChatSession(session_id, user_id, membership_id?, knowledge_domain, project_id?, context_plan_task_id?, created_at)`
- `ChatMessage(message_id, session_id, role, content, grounded, confidence, created_at)`
- `Citation(citation_id, message_id, chunk_id, quote, relevance_score, knowledge_domain?)`

`Citation.knowledge_domain` là field denormalized tùy chọn để hiển thị nhãn nhanh; source of truth vẫn là `DocumentChunk → DocumentVersion → KnowledgeDocument`.

---

## 17. Chức năng hệ thống và trách nhiệm triển khai

Mục này mô tả **hành vi nghiệp vụ**, không quy định tên endpoint. Nhóm được quyền tổ chức router/service theo convention của repository, nhưng không được thay đổi actor, quyền hạn, đầu vào, đầu ra và quy tắc dữ liệu dưới đây.

### 17.1. TV4 — Authentication, Admin và HR

**Authentication**

- Cho phép đăng nhập, đăng xuất, làm mới phiên và lấy thông tin người dùng hiện tại.
- Kết quả xác thực phải cho biết `system_role` và các `ProjectMembership` đang `ACTIVE` để giao diện xác định đúng phạm vi làm việc.
- PM/Engineer lấy quyền theo project từ membership; không suy ra PM/Engineer từ `User.system_role`.

**Admin**

- Tạo, cập nhật trạng thái và tra cứu tài khoản.
- Tạo project và thêm PM/Engineer vào project với đúng `project_role`.
- Bảo đảm một user không có hai membership trong cùng một project.
- Không quản lý tài liệu dự án, template hoặc approve onboarding thay PM.

**HR**

- Tạo, cập nhật phiên bản và archive tài liệu thuộc domain `POLICY`.
- Tài liệu policy không gắn `project_id` và không làm thay đổi template/plan của project nếu PM chưa chọn sử dụng.

### 17.2. TV1 — PM, tài liệu dự án, template và plan

**Nhập tài liệu dự án**

- PM đưa repository ZIP hoặc từng file tài liệu vào khu vực import tạm.
- Hệ thống quét file hỗ trợ, tính checksum, đọc metadata/nội dung và đề xuất nhóm tài liệu.
- PM xem file ứng viên, file trùng, file lỗi và nhóm tài liệu còn thiếu; PM được chọn/bỏ chọn và sửa category trước khi xác nhận.
- Chỉ sau khi PM xác nhận, file gốc mới trở thành phiên bản tài liệu chính thức; metadata được lưu trong PostgreSQL và file gốc được lưu trong Object Storage.
- Bản ghi tài liệu mới bắt đầu ở trạng thái xử lý và được bàn giao cho pipeline RAG. PM không tự ghi chunk hoặc embedding.

**Quản lý template**

- Xem và quản lý Project Template được tạo từ Global Master Template khi project được khởi tạo.
- Tạo version nháp từ version đã duyệt; thêm, sửa, xóa hoặc sắp xếp task khi version còn `DRAFT`.
- Kiểm tra task bắt buộc, `display_order` và dependency trước khi gửi duyệt.
- Duyệt version mới theo transaction: khóa dữ liệu liên quan, archive version cũ rồi approve version mới; không để hai version cùng `APPROVED`.
- Nếu task/version đã được plan sử dụng, phải giữ snapshot và lịch sử; không sửa ngược nội dung plan đang chạy.

**Tạo và quản lý Candidate Plan**

- Chọn Engineer membership, Approved TemplateVersion và các DocumentVersion `ACTIVE` thuộc đúng project.
- Tạo Candidate Plan ở trạng thái `DRAFT`; task bắt buộc phải được giữ, nội dung phải có nguồn và dependency hợp lệ.
- PM có thể edit hoặc regenerate khi plan còn nháp; chỉ PM đúng project được approve và phát hành.
- Theo dõi tiến độ, deadline và blocker của từng plan; xác nhận First PR và đóng onboarding khi đủ điều kiện.

### 17.3. TV2 — Engineer checklist, First Task và First PR

- Xem plan đã được PM duyệt và hướng dẫn chi tiết của từng task.
- Cập nhật task theo vòng đời `NOT_STARTED → IN_PROGRESS → DONE`; khi không thể tiếp tục thì chuyển `BLOCKED` và ghi rõ lý do.
- Không cho bắt đầu task nếu dependency bắt buộc chưa `DONE`.
- Cho phép đính kèm file minh họa blocker; file lưu ở Object Storage, cơ sở dữ liệu chỉ giữ storage key và metadata.
- Thực hiện First Task, nhập First PR URL và theo dõi trạng thái; PM là người xác nhận mốc PR và đóng onboarding.
- Engineer chỉ xem và thao tác plan của chính membership đang active.

### 17.4. TV3 — Document pipeline và RAG Chat

**Xử lý tài liệu**

- Nhận DocumentVersion ở trạng thái xử lý sau khi TV1 hoặc HR xác nhận import.
- Tải file gốc từ Object Storage, extract text, normalize, chunk, tạo embedding và lưu vector cùng metadata domain/project/document/version.
- Chuyển version sang `ACTIVE` khi toàn bộ pipeline thành công; chuyển `FAILED` và lưu lỗi có thể chẩn đoán khi thất bại.
- Không tạo version mới nếu nội dung trùng checksum với version hiện có.

**RAG Chat**

- Tạo phiên chat chung hoặc phiên có ngữ cảnh từ một PlanTask.
- Kiểm tra quyền trước retrieval; PROJECT chat chỉ truy xuất tài liệu `ACTIVE` của đúng project mà user có membership active.
- Trả lời dựa trên chunk được truy xuất và tạo citation trỏ về nguồn thật.
- Nếu không đủ nguồn, phải fallback minh bạch; không suy đoán hoặc dựng citation.
- TV3 không quyết định quyền truy cập, không approve tài liệu và không thay đổi trạng thái checklist.

### 17.5. Contract phối hợp giữa các thành viên

1. TV4 cung cấp identity, system role và project membership làm nguồn kiểm tra quyền cho TV1–TV3.
2. TV1 tạo metadata tài liệu/version và lưu file gốc; TV3 xử lý version thành chunk/vector rồi cập nhật `ACTIVE` hoặc `FAILED`.
3. TV1 chỉ dùng DocumentVersion `ACTIVE` để tạo plan; `PlanTaskSource` lưu chính xác version/chunk đã dùng.
4. TV1 phát hành Approved Plan; TV2 đọc và thực thi snapshot đó, không đọc trực tiếp TemplateTask để chạy checklist.
5. TV2 tạo tiến độ và blocker; TV1 theo dõi, xác nhận First PR và đóng onboarding.
6. TV2 truyền `context_plan_task_id` khi hỏi từ Task Detail; TV3 dùng context đó để ưu tiên nguồn nhưng vẫn phải lọc đúng project và quyền.

---

## 18. Kiến trúc kỹ thuật

- Frontend: Next.js.
- Backend: FastAPI.
- Workflow/Agent: LangGraph.
- Relational DB: PostgreSQL + SQLAlchemy + Alembic.
- Vector store: ChromaDB cho MVP hoặc pgvector nếu nhóm thống nhất.
- Object Storage: Cloudinary private/raw, S3/R2 hoặc MinIO.
- Dịch vụ LLM/Embedding: cấu hình qua environment variables.
- Background processing: worker/job queue tối giản; không chạy ingestion dài trong request đồng bộ.

Luồng: `Next.js → FastAPI → service/domain → PostgreSQL/Object Storage`; AI flow: `FastAPI → LangGraph → ACL retrieval → Vector DB → LLM → Citation → response`.

---

## 19. Security và guardrails

- Password hash hoặc SSO; JWT access/refresh.
- Kiểm tra membership ở backend, không tin projectId từ frontend.
- Object key/private URL; signed URL có hạn sau authorization.
- Không gửi secret, binary hoặc toàn repository vào LLM.
- Chunk metadata phải có domain/project/document/version.
- Chặn cross-project retrieval.
- Validate MIME type, size và chống path traversal khi giải nén ZIP.
- Không log token, password, secrets hoặc nội dung nhạy cảm.
- Prompt injection trong tài liệu được coi là dữ liệu, không phải system instruction.

---

## 20. Metric

### North Star Metric

`Median time from approved onboarding plan to First PR merged`.

### Outcome metrics

- Giảm `time_to_first_pr_merged` so với baseline.
- Giảm `senior_support_hours`.
- Giảm thời gian BLOCKED.
- Tăng tỷ lệ Engineer đánh giá “biết bước tiếp theo” ≥ 4/5.
- Tăng tỷ lệ plan hoàn thành đúng thời gian mục tiêu.

### AI quality metrics

- Citation precision/validity.
- Grounded answer rate trên câu hỏi có nguồn.
- Correct fallback rate trên câu hỏi thiếu nguồn.
- Không có cross-project leakage trong test.
- Candidate Plan mandatory-task recall = 100%.

### Guardrail metrics

- Unauthorized document access = 0.
- Agent tự approve/close/DONE = 0.
- Hallucinated source link = 0 trong bộ eval.

### Mục tiêu pilot đề xuất, chưa phải số liệu thật

- Giảm ≥20% median time tới First PR.
- Giảm ≥25% giờ hỗ trợ lặp lại của PM/Senior.
- ≥90% câu trả lời có nguồn trong bộ câu hỏi answerable.
- ≥90% fallback đúng với câu thiếu nguồn.
- Điểm hài lòng Engineer/PM ≥4/5.

---

## 21. Phân công bốn thành viên

### TV1 — PM, Repository Import, Template và Plan

- Giao diện và chức năng nghiệp vụ dành cho PM.
- Scan/confirm repository documents.
- Template/version/task/dependency.
- Candidate Plan generation workflow và approval.
- Progress dashboard và close onboarding.

### TV2 — Engineer Checklist và First Contribution

- Engineer dashboard/plan/task detail.
- Task transition/dependency.
- Blocker + attachment.
- First Task/First PR.

### TV3 — Knowledge Pipeline và RAG

- Object Storage interface dùng chung.
- DocumentVersion processing.
- Extract/chunk/embed/vector.
- Chat, retrieval, ACL filter, citation và fallback.

### TV4 — Authentication, Admin và HR

- Login/logout/refresh/me.
- User, Project, ProjectMembership.
- RBAC dependencies.
- HR Policy Library.

### Contract bàn giao

- TV4 bàn giao identity/membership contract cho TV1–TV3.
- TV1 tạo document metadata/version PROCESSING; TV3 xử lý tới ACTIVE/FAILED.
- TV1 phát Approved Plan; TV2 chỉ đọc và thực thi.
- TV2 tạo blocker/progress; TV1 theo dõi và đóng onboarding.
- TV2 truyền task context; TV3 trả ChatMessage/Citation.

---

## 22. Definition of Done Gate 2

- Demo end-to-end với LLM thật, không mock luồng chính.
- Architecture diagram có components và data flow.
- Use case, data flow và contract dữ liệu thống nhất.
- Alembic migration chạy sạch; `alembic check` không drift.
- README có setup, env vars và sample request.
- Ít nhất 10 PR nhỏ đã merge trong repo nhóm.
- Ít nhất 5 test case thủ công với output thực tế; thêm automated tests cho rule quan trọng.
- Demo 3 phút: Admin tạo project/membership → PM import tài liệu và approve plan → Engineer thực hiện task, hỏi RAG và báo blocker → PM xác nhận First PR và đóng onboarding.

---

## 23. GO / PIVOT / STOP

### GO

- Pilot cho thấy giảm thời gian/giờ hỗ trợ.
- RAG citation và ACL đạt guardrail.
- PM sẵn sàng duyệt và tái sử dụng plan.

### PIVOT

- Q&A có giá trị nhưng plan generation không ổn: giữ RAG + checklist deterministic.
- Tài liệu quá thiếu: tập trung document coverage/maintenance trước AI.
- Chi phí LLM cao: dùng model nhỏ, cache và giới hạn context.

### STOP

- Không tiếp cận được dữ liệu/tập người dùng pilot.
- Không giảm thời gian hoặc công sức so với Jira/wiki hiện tại.
- Không bảo đảm tách dữ liệu dự án.
- PM không tin hoặc không sử dụng Candidate Plan.

---

## 24. Chỉ dẫn bắt buộc cho Claude khi code

1. Đọc tài liệu này và model/migration hiện tại trước khi sửa.
2. Không khôi phục Module, SupportRequest, Notification hoặc Audit UI vào MVP.
3. Không lưu PM/ENGINEER trong `User.system_role`.
4. Không trộn TemplateTask với PlanTask.
5. Không gọi LLM cho validation/state transition deterministic.
6. Mọi thay đổi schema phải có Alembic migration và test.
7. Không xóa dữ liệu hoặc drop table nếu chưa nêu rõ migration/data handling.
8. Mỗi PR chỉ giải quyết một vertical slice nhỏ, có test và ví dụ sử dụng tương ứng trong README.
9. Nếu code hiện tại mâu thuẫn với quyết định này, lập bảng “Current → Target → Migration impact” trước khi code.
10. Nếu yêu cầu còn mơ hồ, dừng ở mức plan và hỏi nhóm; không tự phát minh nghiệp vụ.

### 24.1. Khoảng cách hiện tại cần xử lý ở Phase Template/Plan

- Model `OnboardingTemplate`, `TemplateVersion`, `TemplateTask`, `TaskDependency`, `OnboardingPlan` và `PlanTask` đã tồn tại; sự tồn tại của model không đồng nghĩa chức năng template/approval đã hoàn thành.
- Constraint hiện tại mới giới hạn một Project Template `APPROVED` cho mỗi project; target của sản phẩm là **một Project Template duy nhất cho mỗi project**, còn lịch sử nằm ở `TemplateVersion`.
- `TemplateVersion` hiện mới unique theo `(template_id, version_no)`; cần bổ sung cơ chế bảo đảm tối đa một version `APPROVED` cho mỗi template.
- Luồng tạo project hiện phải được kiểm tra và bổ sung bước materialize Project Template từ Global Master Template. Không tạo project template rỗng nếu thiếu global seed.
- Luồng approve version phải có authorization theo PM membership, transaction và xử lý cạnh tranh; không chỉ cập nhật một field status riêng lẻ.
- Mọi migration bổ sung constraint phải có bước kiểm tra/chuẩn hóa dữ liệu cũ trước khi tạo unique index để tránh migration thất bại.
