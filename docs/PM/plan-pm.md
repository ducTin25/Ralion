# Plan: Frontend cho Thành viên 1 — PM (Project Manager)

> Trạng thái: **CHỜ DUYỆT** — chưa code, chỉ để bạn xem thiết kế + thứ tự làm trước khi bắt đầu.

## Context

Theo Google Doc "chia task các thành viên" (tab task-division), bạn là **Thành viên 1**:

> **Thành viên 1 — PM, Template & Plan Generation**: "Enables PMs to prepare complete onboarding content and issue approved plans. PMs manage multiple projects; engineers only see data from their assigned projects."

Bạn xác nhận: **"tôi làm hết bên PM á"** — tức toàn bộ giao diện role PM (mockup gọi là `owner`), không chỉ phần Template/Plan hẹp. Đã đọc trực tiếp file HTML mockup "Ralion · BO-06" bạn gửi (lưu local, đọc hết ~1200 dòng) — xác nhận đủ **10 màn hình** thuộc PM:

| # | View (id trong mockup) | UC | Nội dung chính |
|---|---|---|---|
| 1 | `owner-overview` | UC-12 | PM Dashboard: KPI (đang onboarding, tiến độ TB, blocker mở, task quá hạn), bảng tiến độ từng thành viên, blocker cần chú ý, "Ralion Rule Proposals" |
| 2 | `owner-projects` | — | Danh sách project PM quản lý, chuyển project đang xem |
| 3 | `owner-template` | UC-02 | Master Template: lịch sử version, 8 nhóm task (Company Core, Orientation, Access & Security, Environment Setup, Architecture & Codebase, Convention & Workflow, First Task, First PR) |
| 4 | `owner-docs` | UC-02 | Tài liệu dự án: Company Core (do HR quản lý, chỉ xem) + tài liệu riêng dự án (loại, module, Access Scope/ACL, trạng thái APPROVED/NEEDS_REVIEW) |
| 5 | `owner-members` | UC-03 | Danh sách thành viên + Access Scope + trạng thái Plan (DRAFT/ACTIVE/PROJECT_READY/ONBOARDING_CLOSED) |
| 6 | `owner-addmember` | UC-03 | Wizard 3 bước: chọn user+project → Access Scope → xác nhận tạo Candidate Plan |
| 7 | `owner-plan-generating` | UC-04 | Màn hình chờ khi hệ thống ghép Candidate Plan từ Master Template (loading steps) |
| 8 | `owner-plan-review` | UC-04/05 | Candidate Plan Review: xem task theo nhóm, cảnh báo thiếu nguồn, checklist trước khi duyệt, nút Approve & phát hành |
| 9 | `owner-member-detail` | UC-12/13/14/15 | Chi tiết 1 thành viên: milestone rail (Plan Approved→Active→Project Ready→First PR Merged→Onboarding Closed), checklist readiness, giao First Task, đóng Onboarding |
| 10 | `owner-support` | UC-11 | Support Requests — blocker đã định tuyến (dùng chung với HR) |

## Đối chiếu với backend hiện có

Backend (`src/model/*.py`) đã có sẵn, khớp đúng phần lớn:
`OnboardingTemplate`, `TemplateVersion`, `TemplateTask`, `TaskDependency`, `OnboardingPlan`, `PlanTask` (đồng sở hữu với Thành viên 2), `KnowledgeDocument`, `DocumentVersion`, `ProjectMembership`, `Blocker`, `BlockerAttachment`, `Project`.

**2 điểm mockup có nhưng backend CHƯA có entity** (đã hỏi bạn, chưa thấy phản hồi cụ thể — mặc định chọn phương án an toàn hơn, có thể đổi sau):
- **Access Scope / ACL** — tag "Repo", "Secret Manager", "CI/CD", "Test Env" gán riêng từng thành viên (thấy ở `owner-members`, `owner-addmember`, `owner-docs`). Bản đặc tả gốc từng ghi rõ *"MVP không có... phân quyền tài liệu riêng theo từng kỹ sư"* — có thể mockup đã vượt phạm vi MVP ban đầu.
- **"Ralion Rule Proposals"** — AI tự phát hiện pattern và đề xuất sửa Master Template (thấy ở `owner-overview`). Không có entity nào trong backend hỗ trợ việc này.

→ **Quyết định cho lần này**: tạm **bỏ qua 2 phần trên** khi làm DTO — chỉ định nghĩa DTO cho phần backend đã có entity thật. 2 phần kia ghi chú lại là "cần thêm entity backend trước", bạn trao đổi với team/Tech Lead quyết định có làm không trước khi động vào.

**Cập nhật 12/08/2026 — merge nhánh `develop`**: teammate thêm 2 field vào `Project` (`sync_status`, `last_synced_at`) + **3 database trigger ép buộc bất biến kiến trúc** (migration `a1b2c3d4e5f6`), ảnh hưởng trực tiếp nhiều phase dưới đây:
- **INV1**: user có `system_role` (ADMIN/HR) không được có `ProjectMembership` — đã sửa ở Phase 1 (xem [Phase-1/plan-phase1-members.md](Phase-1/plan-phase1-members.md) mục 1.1).
- **INV2**: mỗi `KnowledgeDocument` phải có **đúng 1** `DocumentVersion` với `status=ACTIVE` tại mọi thời điểm (deferred constraint trigger) — **quan trọng cho Phase 3**: khi upload version mới, phải chuyển version cũ về khác `ACTIVE` **trong cùng transaction** trước khi transaction commit (deferred nên được phép "tạm sai" giữa các câu lệnh, nhưng phải đúng lúc commit).
- **INV7**: `OnboardingPlan.status` chỉ được đi **tới** theo thứ tự `DRAFT→APPROVED→ACTIVE→PROJECT_READY→ONBOARDING_CLOSED`, không được lùi — **quan trọng cho Phase 4/5**: nút "Regenerate" ở Candidate Plan Review không được implement bằng cách set status lùi về DRAFT nếu plan đã qua APPROVED, phải tạo bản ghi `OnboardingPlan` mới thay vì đổi ngược status bản cũ.

## Cấu trúc DTO (`frontend/src/features/project-management/dto/`)

Theo đúng yêu cầu: `requestDTO/` và `responseDTO/`, đặt `type` TypeScript (không dùng `interface`/`class`), giữ **snake_case** khớp JSON thật từ FastAPI (backend Pydantic mặc định snake_case, không đổi mapper cho đơn giản) — đúng convention đã có sẵn ở `src/types/chat.ts`.

```
frontend/src/features/project-management/dto/
  requestDTO/
    projectMembership.request.ts   # AddMemberRequestDTO (user_id, project_id, project_role)
    template.request.ts             # CreateTemplateRequestDTO, CreateTemplateVersionRequestDTO
    templateTask.request.ts          # CreateTemplateTaskRequestDTO, UpdateTemplateTaskRequestDTO, ReorderTemplateTaskRequestDTO
    taskDependency.request.ts         # CreateTaskDependencyRequestDTO
    plan.request.ts                    # GenerateCandidatePlanRequestDTO, ApproveCandidatePlanRequestDTO, ConfirmProjectReadyRequestDTO, CloseOnboardingRequestDTO, AssignFirstTaskRequestDTO
    planTask.request.ts                 # EditPlanTaskRequestDTO
    document.request.ts                  # UploadKnowledgeDocumentRequestDTO
    blocker.request.ts                    # ResolveBlockerRequestDTO
  responseDTO/
    project.response.ts              # ProjectResponseDTO
    projectMembership.response.ts     # ProjectMembershipResponseDTO
    template.response.ts               # TemplateResponseDTO, TemplateVersionResponseDTO
    templateTask.response.ts            # TemplateTaskResponseDTO, TaskDependencyResponseDTO
    plan.response.ts                     # OnboardingPlanResponseDTO (dùng chung cho cả Candidate Plan — chỉ là status=DRAFT)
    planTask.response.ts                  # PlanTaskResponseDTO
    document.response.ts                   # KnowledgeDocumentResponseDTO, DocumentVersionResponseDTO
    memberProgress.response.ts              # MemberProgressResponseDTO, MemberDetailResponseDTO (milestone rail)
    pmDashboard.response.ts                  # PmDashboardSummaryResponseDTO (4 KPI ở owner-overview)
    blocker.response.ts                       # BlockerResponseDTO, BlockerAttachmentResponseDTO
```

Field mỗi DTO lấy trực tiếp từ entity Python tương ứng trong `src/model/`, convert kiểu: `int`→`number`, `str`→`string`, `datetime`→`string` (ISO), enum→union string literal (ví dụ `status: "DRAFT" | "APPROVED" | "ACTIVE" | "PROJECT_READY" | "ONBOARDING_CLOSED"`).

## Thứ tự làm — **full-stack theo từng feature** (mỗi phase code cả BE lẫn FE, xong 1 phase là chạy thật được ngay, không tách "làm hết DTO/FE trước rồi BE sau")

Đã kiểm tra lại backend hiện có gì cho từng entity trước khi sắp thứ tự:

| Entity | Trạng thái backend hiện tại |
|---|---|
| `Project`, `ProjectMembership` | Đã có `service`/`router` dạng **khung** (chỉ comment, chưa code logic thật) |
| `KnowledgeDocument`, `DocumentVersion`, `DocumentChunk` | Đã có `service`/`router` dạng **khung** |
| `OnboardingTemplate`, `TemplateVersion`, `TemplateTask`, `TaskDependency` | **Chưa có file nào** — code mới hoàn toàn |
| `OnboardingPlan`, `PlanTask` | **Chưa có file nào** — code mới hoàn toàn (kể cả logic sinh Candidate Plan từ template) |
| `Blocker`, `BlockerAttachment` | **Chưa có file nào** — code mới hoàn toàn |

**Phase 1 — Thành viên & Add Member Wizard** (`owner-members`, `owner-addmember`)
- BE: hoàn thiện `project_membership_service.py`/`router.py` (đang khung → code thật CRUD), hoàn thiện `project_router.py` cho danh sách project (`owner-projects`).
- FE: `dto/requestDTO/projectMembership.request.ts` + `responseDTO/projectMembership.response.ts`, `project.response.ts` + UI 3 màn hình `owner-members`, `owner-addmember`, `owner-projects`.
- Làm trước tiên vì mọi phase sau đều cần đã có `ProjectMembership` thật để gắn Plan vào.

**Phase 2 — Master Template** (`owner-template`)
- BE: tạo mới hoàn toàn `onboarding_template_service.py`/`router.py`, `template_version_...`, `template_task_...`, `task_dependency_...`.
- FE: DTO + UI `owner-template` (version history, 7 nhóm task theo đúng `TaskCategory` — xem chi tiết lý do 8→7 trong plan riêng).
- Cần xong trước Phase 4 (Candidate Plan phải sinh từ 1 TemplateVersion đã APPROVED).
- **Kế hoạch chi tiết**: xem [Phase-2/plan-phase2-master-template.md](Phase-2/plan-phase2-master-template.md) — mô hình Template↔Version↔Task↔Dependency, migration cần thêm, toàn bộ endpoint + luồng UI, chưa code chờ duyệt.

**Phase 3 — Project Knowledge / Documents** (`owner-docs`)
- BE: hoàn thiện `knowledge_document_service.py`/`router.py` (đang khung), thêm route upload file thật (lưu Cloudinary — đã có sẵn helper từ script `upload_sample_docs_to_cloudinary.py`, tái dùng logic).
- FE: DTO + UI `owner-docs`.
- Độc lập, có thể làm song song Phase 2 nếu có 2 người.
- ⚠️ **INV2 (trigger mới từ develop)**: mỗi document phải có đúng 1 `DocumentVersion.status=ACTIVE`. Khi upload version mới, service phải chuyển version cũ sang trạng thái khác `ACTIVE` **trong cùng transaction** trước khi version mới được set `ACTIVE` — không tách 2 bước ra 2 request/transaction riêng.

**Phase 4 — Candidate Plan Generation & Review** (`owner-plan-generating`, `owner-plan-review`)
- BE: tạo mới `onboarding_plan_service.py`/`router.py`, `plan_task_...` — bao gồm **logic nghiệp vụ sinh Candidate Plan** (đọc TemplateVersion APPROVED → tạo OnboardingPlan + materialize PlanTask theo TemplateTask). Đây là phần backend phức tạp nhất trong scope Thành viên 1.
- FE: DTO + UI 2 màn hình.
- Phụ thuộc Phase 1 (có Membership) + Phase 2 (có TemplateVersion APPROVED).
- ⚠️ **INV7 (trigger mới từ develop)**: `OnboardingPlan.status` chỉ đi tới, không lùi (`DRAFT→APPROVED→ACTIVE→PROJECT_READY→ONBOARDING_CLOSED`). Nút **"Regenerate"** ở Candidate Plan Review **không được** set status của plan đã `APPROVED` lùi về `DRAFT` — phải tạo `OnboardingPlan` mới (bản DRAFT mới) thay thế, giữ bản cũ nguyên trạng hoặc archive theo cách riêng.
  - **Observability (áp dụng slide Day 13 — Monitoring/Logging/Observability)**: đây là bước duy nhất trong scope Thành viên 1 có luồng nhiều bước kiểu agent (mockup `owner-plan-generating` thể hiện đúng 6 bước tuần tự: tải TemplateVersion → gộp Company Core → lọc theo Access Scope → chọn nhóm task theo Role/Module → điền nội dung task → kiểm tra dependency/ACL) — cần trace để biết bước nào chậm/lỗi, không đoán mò. Cụ thể áp dụng:
  - **Tracing (Langfuse, MVP tier theo slide "Chọn công cụ nào khi nào")**: mỗi lần PM bấm "Tạo Candidate Plan" hoặc "Regenerate" → 1 trace, mỗi bước trong 6 bước trên → 1 span con (dùng decorator `@observe` của Langfuse SDK v4, không cần đổi kiến trúc). Đặt tên span theo chuẩn OTel GenAI semconv nếu bước đó gọi LLM (`gen_ai.operation.name`, `gen_ai.usage.input_tokens/output_tokens`) hoặc theo tên tool nếu là bước tra cứu dữ liệu thuần (`execute_tool template_load`, `execute_tool access_scope_filter`...).
  - **Correlation ID**: mỗi request sinh Candidate Plan có 1 `correlation_id` (map với `plan_id` sau khi tạo) xuyên suốt log — FE nhận `correlation_id` này trong response để sau này có thể hiển thị link trace debug (không bắt buộc phải làm UI cho việc này ở Phase 4, chỉ cần BE trả về field, tận dụng sau nếu cần).
  - **Structured logging**: log JSON tại mỗi bước (`event`, `correlation_id`, `plan_id`, `duration_ms`), input/output KHÔNG log nguyên văn nội dung tài liệu/task (tránh log PII/nội dung nhạy cảm — đúng nguyên tắc "chỉ log field cần, redact phần nhạy cảm" từ slide).
  - **Cost & latency metric tối thiểu**: ghi lại `duration_ms` tổng + theo từng bước, và nếu bước "điền nội dung task" có gọi LLM thật thì ghi thêm `input_tokens`/`output_tokens`/cost — dùng để hiển thị đúng UI mockup (6 bước loading tuần tự `active`→`done`) bằng dữ liệu thật thay vì animation giả lập.
  - **Không làm ở phase này** (out of scope, ghi chú cho sau): dashboard Grafana/Prometheus riêng, alert rule tự động, SLO chính thức — quy mô đồ án nhỏ, dùng Langfuse dashboard có sẵn (free tier self-host hoặc cloud) là đủ theo đúng khuyến nghị slide ("Cho lab: Langfuse dashboard đủ cho MVP, đừng tự build Grafana custom trước khi có đủ data").

### Phase 4 — Đánh giá chất lượng AI (Evaluation & Benchmarking, theo slide Day 14 + Day 2)

Áp dụng đúng phương pháp `D:\AI_Action_lythuyet\slide\day14-ai-evaluation-benchmarking.pdf` (evaluation là engineering discipline, không phải cảm tính — slide trang 6) và khung Problem Statement/Success Metric của `01-worksheet.md` (Day 2). **Chỉ áp dụng cho đúng 1 bước trong pipeline 6 bước ở mục trên**: bước 5 "điền nội dung task" — đây là bước **duy nhất** trong toàn bộ scope Thành viên 1 thật sự gọi LLM để *sinh nội dung* (5 bước còn lại — tải TemplateVersion, gộp Company Core, lọc Access Scope, chọn nhóm task, kiểm tra dependency/ACL — là business logic thuần, xác định bằng code, verify bằng `pytest` như mọi service khác, **không** cần eval kiểu AI). Tách rõ ranh giới này để tránh áp dụng sai chỗ (over-engineering eval cho code không có tính stochastic).

#### 4.1 Problem Statement & Baseline (bắt buộc trước khi kết luận AI đáng dùng)

| Field | Nội dung |
|---|---|
| **Vấn đề** | PM phải tự viết tay nội dung chi tiết (hướng dẫn, link tài liệu, checklist) cho từng `PlanTask` khi tạo Candidate Plan cho 1 Engineer mới — tốn thời gian, dễ thiếu sót, không cá nhân hoá theo đúng Access Scope/dự án |
| **AI làm gì** | Bước 5 trong pipeline: với mỗi `TemplateTask` cần vào Plan, LLM đọc `KnowledgeDocument`/`DocumentChunk` liên quan (đã lọc theo Access Scope ở bước 3) → sinh nội dung `PlanTask` cụ thể, gắn nguồn trích dẫn |
| **Input/Output** | Input: `TemplateTask` (mô tả khung) + danh sách `DocumentChunk` liên quan. Output: nội dung `PlanTask` (text) + `PlanTaskSource` (trích dẫn chunk nào) |
| **Baseline B0 (không dùng AI)** | PM copy nguyên văn `TemplateTask.description` làm `PlanTask` content, dùng chung cho mọi project/role — không đọc `KnowledgeDocument` riêng dự án, không cá nhân hoá. Đây là baseline **có sẵn, chi phí $0**, phải so sánh AI với chính baseline này (không phải so với "không làm gì cả") |
| **Success Metric (có số)** | ≥ 80% `PlanTask` do AI sinh được PM duyệt **không cần sửa tay** — đo qua tỉ lệ Approve thẳng vs Edit-then-approve ở màn `owner-plan-review` (Phase 4 UI) |
| **Guardrail** | Faithfulness ≥ 0.8 (không bịa nội dung ngoài `KnowledgeDocument`), P95 latency sinh 1 Candidate Plan ≤ ngưỡng chấp nhận được cho demo (đo thật ở Phase 4, ghi vào Langfuse — xem mục Observability ở trên), cost/Candidate Plan có trần rõ ràng |

Nếu sau khi đo, AI không vượt được baseline B0 theo Success Metric trên (đúng tinh thần slide Day 2: *"chỉ ra 3 điểm yếu... vì sao rule-based có thể giải quyết tốt hơn AI"*) — cân nhắc quay lại B0 (PM sửa tay từ template gốc) thay vì giữ 1 bước AI không tạo giá trị thật.

#### 4.2 3 lớp metric (North Star / Guardrail / Diagnostic — slide trang 18)

- **North Star**: `% PlanTask được PM duyệt không sửa tay` (approval-without-edit rate) — chính là Success Metric ở mục 4.1.
- **Guardrails** (không được xấu đi khi thử prompt/model mới): Faithfulness ≥ 0.8, P95 latency, cost/plan.
- **Diagnostics** (dùng khi có vấn đề, không phải theo dõi hàng ngày): 4 RAGAS-style metrics theo mục 4.3, breakdown theo `task_category` (8 nhóm đã liệt kê ở đầu file), breakdown theo role (PM tự thấy nhóm nào AI yếu để ưu tiên fix).

#### 4.3 Golden dataset — 20 test case (đúng số lượng deliverable Lab 14)

Schema (phỏng theo slide trang 26, đổi field cho đúng domain Candidate Plan):

```json
{
  "case_id": "cpg_001",
  "template_task_id": 12,
  "task_category": "ACCESS_SECURITY",
  "project_key": "PHONESHOP",
  "role": "ENGINEER",
  "reference_content": "Nội dung PlanTask chuẩn do PM viết tay...",
  "expected_source_chunks": ["doc_45#chunk_3"],
  "difficulty": "medium",
  "created_by": "pm_thu",
  "reviewed_by": "pm_thu_round2",
  "version": "v1"
}
```

- **Cách tạo**: lấy `TemplateTask` thật từ Approved Project TemplateVersion làm khung; PM viết `reference_content` chuẩn cho 7 nhóm `ORIENTATION`, `ACCESS`, `SETUP`, `CODEBASE`, `CONVENTION`, `FIRST_TASK`, `FIRST_PR`. POLICY/Company Core được đánh giá qua nguồn POLICY riêng, không tạo category thứ tám trong Project Template.
- **Stratified** theo `difficulty` (easy/medium/hard) + **≥ 2 edge case bắt buộc**: không có `DocumentVersion ACTIVE` hoặc retrieval không tìm được chunk phù hợp — hành vi đúng là trả cảnh báo thiếu nguồn để PM bổ sung, không bịa nội dung.
- **Giới hạn quy mô đồ án** (ghi rõ, không giả vờ đủ chuẩn production): slide khuyến nghị ≥ 2 expert review độc lập mỗi answer + Cohen's κ ≥ 0.6 (trang 19, 23) — team 4 người không đủ nhân lực làm việc này ở mức production, chỉ 1 PM (Thành viên 1) tự viết + tự review lại vòng 2, ghi rõ hạn chế này trong report thay vì bỏ qua không nhắc.

#### 4.4 Metric tự động — RAGAS-style cho bước generation (không dùng thư viện `ragas` trực tiếp vì domain tiếng Việt + input không phải dạng Q&A chuẩn, nhưng áp đúng công thức)

| Metric | Công thức (theo slide trang 15-16) | Đo cái gì |
|---|---|---|
| **Faithfulness** | claims trong `PlanTask` content được `DocumentChunk` support / tổng claims | AI có bịa nội dung ngoài tài liệu không |
| **Context Recall** | claims trong `reference_content` có mặt trong `DocumentChunk` đã retrieve / tổng claims trong reference | Bước retrieve (lọc Access Scope + tìm chunk liên quan) có đủ evidence không |
| **Context Precision** | % chunk retrieved thật sự liên quan, ưu tiên chunk liên quan đứng trước | Có retrieve thừa/nhiễu không |
| **Relevancy-analog** | LLM-Judge chấm riêng tiêu chí "đúng phạm vi `TemplateTask` yêu cầu, không lạc sang nhóm khác" | Nội dung có đúng đề bài không (thay Answer Relevancy vì đây không phải Q&A) |

#### 4.5 LLM-as-Judge — ≥ 10 response, rubric 1–5, reference-based (đúng deliverable Lab 14)

- Rubric **reference-based** (so `actual PlanTask content` với `reference_content` trong golden dataset — slide trang 31), chấm 4 tiêu chí đúng 4 chiều chất lượng output (slide trang 6): **correctness** (đúng thông tin, không hallucinate), **relevance** (đúng phạm vi task), **completeness** (đủ chi tiết PM cần), **coherence** (dễ đọc, có cấu trúc).
- **Chain-of-thought judging** (slide trang 33), `temperature=0` để reproducible, judge model **khác** model sinh nội dung để tránh self-preference bias (slide trang 34, vd sinh bằng GPT thì judge bằng Claude hoặc ngược lại).
- **Calibrate**: so judge score với 1 PM thật chấm tay trên cùng subset ≥ 10 case — quy mô đồ án không đủ 2 expert độc lập để tính Cohen's κ đúng chuẩn (slide trang 36), chỉ tính % agreement đơn giản (judge và PM lệch ≤ 1 điểm trên thang 5) làm proxy, ghi rõ đây là compromise do giới hạn nhân lực, không phải bỏ qua bước calibrate.

#### 4.6 Statistical rigor tối thiểu (slide mục 06, áp mức phù hợp quy mô đồ án)

- LLM sinh nội dung stochastic khi `temperature > 0` lúc chạy thật (khác baseline B0 vốn deterministic) → chạy mỗi test case **≥ 3 lần**, báo cáo `mean ± std` cho Faithfulness/Judge score, không chốt 1 con số duy nhất (slide trang 45).
- So AI vs Baseline B0: vì B0 không có variance (copy nguyên văn, luôn giống nhau), so sánh bằng **% case AI được Judge chấm cao hơn B0** (không cần paired t-test phức tạp ở quy mô 20 case) — nhưng ghi rõ trong report: **20 case chỉ đủ "sanity check"** (slide trang 19, 48), chưa đủ statistical power để khẳng định chắc chắn ở mức production, nếu triển khai thật cần mở rộng lên ≥ 50 case.

#### 4.7 Failure analysis + Improvement log (đúng deliverable Lab 14)

- Chọn **3 worst case** (Judge score thấp nhất hoặc Faithfulness thấp nhất) → áp **5 Whys** (slide trang 58) cho từng case, phân loại theo Failure Taxonomy (slide trang 57: Wrong Answer / Hallucination / Tool Failure / Refusal / Slow / Inconsistent / Bias) — thay "Tool Failure" bằng "Retrieval Failure" (không tìm đúng `DocumentChunk`) cho khớp domain.
- **Cluster** failures theo root cause trước khi fix (slide trang 60) — fix 1 root cause (vd re-chunk `DocumentChunk` nhỏ hơn) thường giải quyết nhiều case cùng lúc, hiệu quả hơn sửa từng case riêng lẻ.
- **Improvement log ≥ 3 action items**, ưu tiên theo impact (case cluster lớn nhất fix trước) — thêm case failure mới vào golden dataset mỗi sprint để benchmark tự "evolve" (slide trang 24, 61), tránh benchmark cũ dần mất tính đại diện.

#### 4.8 Deliverable & nơi lưu (build khi code Phase 4 thật — mục này vẫn là plan, chưa code)

`docs/PM/Phase-4/` (tạo khi bắt đầu code Phase 4):
- `eval-golden-dataset.jsonl` — 20 test case theo schema mục 4.3.
- `eval-report.md` — RAGAS-style scores (4.4) + LLM-Judge results (4.5) + failure analysis + improvement log (4.7), ~5–8 trang, đúng format deliverable slide trang 3.
- Script chạy eval đặt cùng chỗ với script sinh Candidate Plan thật (`src/services/onboarding_plan_service.py` khi code Phase 4), không tạo framework eval riêng tách biệt phức tạp — quy mô đồ án chỉ cần script Python đơn giản (tương tự `tools/eval_ragas.py`, `tools/eval_judge.py`, `tools/find_worst.py` ở slide trang 75, nhưng viết tối giản cho đúng nhu cầu, không copy nguyên cấu trúc lab).

**Phase 5 — Member Detail** (`owner-member-detail`)
- BE: thêm action endpoint trên `OnboardingPlan` (confirm PROJECT_READY, gán First Task — dùng field `first_pr_url`/`first_pr_confirmed_by_user_id` đã có sẵn trong model, đóng Onboarding).
- FE: DTO + UI milestone rail.
- Phụ thuộc Phase 4 đã có Plan thật.

**Phase 6 — Support/Blockers** (`owner-support`)
- BE: tạo mới `blocker_service.py`/`router.py` + `blocker_attachment_...`.
- FE: DTO + UI.
- Phụ thuộc Phase 4 (Blocker gắn vào PlanTask đã tồn tại).

**Phase 7 — PM Dashboard** (`owner-overview`)
- BE: 1 endpoint tổng hợp (aggregate) tính 4 KPI + bảng tiến độ từ dữ liệu các entity ở phase 1-6.
- FE: DTO + UI. Bỏ khối "Ralion Rule Proposals" (chưa có backend, xem mục trên).
- Làm **cuối cùng** vì cần dữ liệu thật từ mọi phase trước mới tính KPI đúng — làm sớm sẽ phải mock giả, mất công sửa lại.

## Dependency mới cần thêm (chỉ tới Phase 4)
- Backend: `langfuse` (Python SDK v4, MIT license, free self-host hoặc cloud free tier 50k units/tháng — theo slide Day 13 mục "Chọn công cụ nào khi nào") — thêm vào `requirements.txt`, cấu hình qua biến môi trường `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`/`LANGFUSE_HOST` (không hardcode, theo đúng convention bảo mật đã dùng cho Cloudinary trước đó).
- Không cần LangGraph/LangChain riêng cho luồng sinh Candidate Plan — đây là quy trình nghiệp vụ có thứ tự cố định (6 bước, không có nhánh rẽ động theo quyết định của LLM), nên code thẳng bằng Python thường (async function tuần tự) + `@observe` bọc từng bước là đủ, không cần thêm framework orchestration nặng cho use case này.

## Ngoài phạm vi lần này
- Access Scope/ACL và Ralion Rule Proposals — cần bàn với team/Tech Lead trước khi thêm entity backend.
- API client thật (`src/lib/api.ts`) — code cùng lúc với FE mỗi phase, không tách riêng.
- Dashboard Grafana/Prometheus, alert rule, SLO chính thức cho luồng sinh Candidate Plan — dùng Langfuse dashboard có sẵn là đủ ở quy mô đồ án hiện tại (xem ghi chú trong Phase 4).

## Verification (mỗi phase)
- Backend: `pytest tests/ -v`, `alembic check` (nếu phase có đổi model), test thử API qua Swagger `/docs`.
- Frontend: `cd frontend && npx tsc --noEmit` sạch, `npm run lint`, `npm run build` qua.
- Test tay: mở UI thật, thao tác đúng luồng (vd. Phase 1: thêm 1 member mới → thấy xuất hiện trong danh sách).
