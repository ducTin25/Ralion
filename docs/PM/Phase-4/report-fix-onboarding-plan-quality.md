# Báo cáo: Sửa 6 lỗi chất lượng Onboarding Plan + tích hợp lõi ingest chung (15/08)

Thực hiện theo `plan-fix-onboarding-plan-quality.md` (đã cập nhật thứ tự sau review). Báo cáo này
ghi lại **kết quả thật đo được**, không phải mô tả ý định — mỗi mục đều kèm lệnh/SQL/log để kiểm
chứng lại.

---

## 0. Tóm tắt kết quả

| Hạng mục | Trước | Sau |
|---|---|---|
| Tài liệu PROJECT có chunk | **0 chunk** (mọi project) | **37 chunk** cho GADGETHUB, đều có embedding |
| Task có nguồn khi sinh plan | 4/8 "Thiếu nguồn" | **8/8 task có nguồn** |
| Nội dung do AI viết | 0/8 (âm thầm rơi baseline) | **8/8 task do AI viết** (41–45s, có gọi LLM thật) |
| Trích dẫn | dồn 1 danh sách cuối trang | **18 trích dẫn, 18/18 có `chunk_id`**, `[n]` gắn ngay tại bước |
| Nhóm "Tìm hiểu công ty" | không có trong plan | **có, đứng đầu** (1 công ty + 5 nhóm dự án) |
| PM tạo project mới | **lỗi 409 giả** (không tạo được) | tạo được bình thường |

Kiểm chứng chất lượng: `pytest tests/ PM-test/ -q` → **219 passed**; `ruff check` → **All checks
passed**; `tsc --noEmit` + `eslint src` (frontend) → **sạch**; `alembic heads` → **1 head duy nhất**
(`e5f6a7b8c9d0`).

---

## 1. Bug chặn: PM không tạo được project mới (mục 0a)

**Hiện tượng**: mọi `POST /api/v1/projects/pm` trả `409 {"detail":"Project key already exists"}` dù
key chưa tồn tại. 55 test fail dây chuyền vì hầu hết đều bắt đầu bằng bước tạo project.

**Nguyên nhân thật** (không phải trùng key): migration `3e4f5a6b7c8d` (nhánh Backstage Sub-flow A)
đặt `projects.github_repo`/`default_branch` **NOT NULL** và chỉ backfill placeholder cho project
CŨ. API tạo project của PM không gửi 2 field này → vi phạm NOT NULL → `IntegrityError` bị
`except IntegrityError` bắt và dịch nhầm thành "key trùng".

```
$ docker exec p-040-db-1 psql -U app -d pgonboarding -c "\d projects"
 github_repo    | character varying |  | not null |
 default_branch | character varying |  | not null |
```

**Cách sửa** — giữ nguyên hướng đồng bộ GitHub của TV3, chỉ nới ràng buộc:
- Migration `b1c2d3e4f5a6`: 2 cột thành `nullable=True` + CHECK `ck_projects_github_target_paired`
  ép **đi theo cặp** (cùng NULL hoặc cùng có giá trị) — tránh trạng thái nửa vời có repo mà thiếu
  nhánh, khiến `sync_docs` không biết đọc nhánh nào.
- `github_sync_worker.resolve_github_token()`: guard báo lỗi rõ ràng khi project chưa cấu hình
  GitHub, thay vì crash `.partition()` trên `None` giữa luồng đồng bộ.

**Bằng chứng sau khi sửa**:
```
$ curl -X POST .../projects/pm -d '{"key":"ZZVERIFY0A",...}'
{"project_id":1750,"key":"ZZVERIFY0A","status":"ACTIVE","sync_status":"NOT_STARTED",...}
```
(Dữ liệu verify đã xoá sạch sau khi lấy bằng chứng.)

---

## 2. Gốc rễ "Thiếu nguồn": Folder Scan dùng chung lõi ingest của TV3 (mục 3.1)

**Nguyên nhân**: `bm25_search()` tìm trong bảng `document_chunks`, nhưng tài liệu PROJECT **chưa
từng được chunk** — `_import_one()` chỉ tạo `DocumentVersion` rồi dừng. Mai Anh (TV3) đã viết lõi
ingest thật (`modules/knowledge/ingestion/versioning.ingest_or_update()`: chunk theo cấu trúc →
embed có cache → archive version cũ → activate version mới → ghi `DocumentChunk` kèm
`anchor`/`section_path`), nhưng nối vào luồng **đồng bộ GitHub tự động**, không chạy khi PM tự tải
tay/quét thư mục.

**Cách sửa (đã đổi so với bản nháp đầu)**: KHÔNG tự viết pipeline chunk thứ hai — coi luồng "PM tải
tay/quét thư mục" là **một adapter khác của cùng lõi ingest**:
- `knowledge_document_service._import_one()` dựng `ProjectIngestRequest` rồi gọi thẳng
  `ingest_or_update()`; bỏ hẳn đoạn tự tạo `DocumentVersion` viết tạm hôm trước.
- `build_upload_source_key(project_id, category, title)` — định danh ổn định, gồm cả `title` để giữ
  đúng quyết định "1 category chứa NHIỀU document".
- Migration `c3d4e5f6a7b8` backfill `source_key` cho tài liệu PROJECT cũ (trước đây NULL) theo đúng
  công thức trên, nếu không PM tải lại đúng file cũ sẽ sinh document trùng.
- `embedder` inject qua `Depends(get_embedder)` ở router — cùng pattern `admin_console_router` đang
  dùng, không tạo embedder riêng trong service.

**Bằng chứng — upload 5 tài liệu thật qua API có đăng nhập**:
```
OVERVIEW: version=ACTIVE id=2582     ARCHITECTURE: version=ACTIVE id=2583
SETUP: version=ACTIVE id=2584        ACCESS_SECURITY: version=ACTIVE id=2585
CODEBASE_GUIDE: version=ACTIVE id=2586
```
```sql
SELECT kd.document_category, dv.status, count(dc.chunk_id) chunks, count(dc.embedding) with_embedding
FROM knowledge_documents kd JOIN document_versions dv ON dv.document_id=kd.document_id
LEFT JOIN document_chunks dc ON dc.version_id=dv.version_id
WHERE kd.project_id=136 GROUP BY 1,2;

 document_category | status | chunks | with_embedding
-------------------+--------+--------+----------------
 OVERVIEW          | ACTIVE |      7 |              7
 ARCHITECTURE      | ACTIVE |      9 |              9
 SETUP             | ACTIVE |      9 |              9
 ACCESS_SECURITY   | ACTIVE |      6 |              6
 CODEBASE_GUIDE    | ACTIVE |      6 |              6
```
Trước đó cùng câu lệnh này trả `0 chunk` cho toàn bộ tài liệu PROJECT của mọi project.

---

## 3. Nhóm "Tìm hiểu công ty" thành task thật (mục 3.2)

**Nguyên nhân**: `TaskCategory` không có giá trị nào cho chính sách công ty. Khối "Tìm hiểu công ty"
ở trang Master Template chỉ là UI đọc thẳng danh sách `KnowledgeDocument` POLICY, **không phải
`TemplateTask`**, nên không bao giờ chảy vào `generate_candidate_plan`.

**Cách sửa**:
- `TaskCategory.COMPANY` + migration `d4e5f6a7b8c0` (`ALTER TYPE ... ADD VALUE`, khớp pattern
  `766d77208fd9` đã có trong repo).
- `TASK_CATEGORY_POLICY_MAP[COMPANY] = None` (đọc toàn bộ policy). Cố tình **không** thêm vào
  `TASK_CATEGORY_DOCUMENT_MAP` — nhóm này không đọc tài liệu riêng của dự án.
- Task được thêm qua **đúng luồng Master Template** (tạo version DRAFT clone từ bản APPROVED → thêm
  task → reorder lên đầu → duyệt), **không ghi thẳng DB**: `template_task_service` chỉ cho sửa task
  khi version còn DRAFT, ghi tắt là phá đúng bất biến mình đang bảo vệ. Đã áp dụng cho cả GLOBAL
  Master Template (project mới tự kế thừa) và GADGETHUB.

**Bằng chứng** — thứ tự task trong version đã duyệt:
```
1 COMPANY        Tìm hiểu chính sách công ty
2 ORIENTATION    Đọc tài liệu Overview dự án
3 ARCHITECTURE   ...    4-5 ACCESS    6-7 SETUP    8 CODEBASE
```
Test `test_company_task_reads_policy_and_appears_in_plan` khẳng định thêm: nguồn của nhóm COMPANY
**chỉ được là tài liệu POLICY** (`project_id IS NULL`), không lẫn tài liệu dự án.

---

## 4. Không bịa nội dung khi thiếu bằng chứng (mục 3.3)

**Nguyên nhân**: `generate_baseline_content()` luôn đổ `instruction_template` (khung mẫu PM soạn
trong Master Template) ra dưới tiêu đề "## Các bước thực hiện" bất kể có nguồn hay không — nên task
hiện "TÀI LIỆU NGUỒN (0)" mà vẫn trông như đã có hướng dẫn được tài liệu xác nhận.

**Cách sửa** — phân biệt **2 tình huống khác nhau**, vì việc PM cần làm khác hẳn:

| Tình huống | Thông báo | PM cần làm |
|---|---|---|
| Nhóm tài liệu rỗng | `NO_SOURCE_NOTICE` | Bổ sung tài liệu vào nhóm |
| Có tài liệu nhưng truy xuất không khớp đoạn nào | `NO_HIT_NOTICE` (mới) | Sửa nội dung tài liệu / mô tả task — upload thêm cũng vô ích |

Cả 2 dùng `_no_evidence_instruction()`: chỉ hiện "## Trạng thái" + "## Mục tiêu (tham khảo — chưa
được tài liệu xác nhận)", **không dựng mục "Các bước thực hiện"**.

Test `test_task_without_document_does_not_fabricate_steps` assert đúng điều đó.

---

## 5. Trích dẫn theo `chunk_id`, có validator, mở đúng đoạn (mục 3.4)

**Cách sửa**:
- `PlanTaskSource.chunk_id` (FK → `document_chunks`, nullable) + migration `e5f6a7b8c9d0`. Nullable
  vì plan cũ chỉ có `version_id`, và nhánh baseline/no-hit gắn tài liệu làm tham chiếu cả file.
- `SYSTEM_PROMPT` thêm quy tắc 5: chèn `[n]` ngay cuối câu của bước dùng nguồn đó.
- **Validator** `_citations_within_range()`: `[n]` trỏ ra ngoài phạm vi nguồn thật → coi như output
  hỏng, rơi về nội dung không-AI (không tự ý xoá số thừa để khỏi che lỗi khi đo eval).
- `plan_task_service` outerjoin `DocumentChunk` lấy `section_path`/`anchor`; FE bấm `[n]` mở
  `DocumentPreviewModal` cuộn tới đúng heading + tô sáng 2,4s.

**Một bug thật phát hiện khi kiểm chứng end-to-end** (không có trong plan ban đầu): lần sinh đầu
tiên cho ra task chỉ có **1 nguồn nhưng AI trích dẫn tới `[5]`**. Nguyên nhân: prompt đánh số theo
từng *chunk*, trong khi `PlanTaskSource` bị `UniqueConstraint(plan_task_id, version_id)` ép gộp
nguồn theo *file* — nên `[3]` không trỏ tới đâu cả. Đã sửa: `_build_sources_block()` đánh số theo
**đúng danh sách nguồn đã gộp** (nhiều đoạn cùng file nằm chung 1 số), và validator đối chiếu với
`len(sources)` thay vì `len(hits)`.

**Bằng chứng sau khi sửa** — mọi citation đều nằm trong phạm vi nguồn thật:
```
#1 [COMPANY     ] nguon=4 cite=[1, 2, 3, 4] -> OK
#2 [ORIENTATION ] nguon=4 cite=[1, 2]       -> OK
#3 [ARCHITECTURE] nguon=1 cite=[1]          -> OK
#4 [ACCESS      ] nguon=3 cite=[1, 2]       -> OK
#5 [ACCESS      ] nguon=3 cite=[1, 2, 3]    -> OK
#6 [SETUP       ] nguon=1 cite=[1]          -> OK
#7 [SETUP       ] nguon=1 cite=[1]          -> OK
#8 [CODEBASE    ] nguon=1 cite=[1]          -> OK

KET LUAN: TAT CA citation deu tro toi nguon co that
```
```sql
-- 18/18 nguồn đều trỏ tới đúng 1 đoạn tài liệu
SELECT tt.category, count(pts.task_source_id) sources, count(pts.chunk_id) with_chunk ...
 ORIENTATION |  4 | 4      ACCESS   | 6 | 6      SETUP    | 2 | 2
 CODEBASE    |  1 | 1      ARCHITECTURE | 1 | 1   COMPANY | 4 | 4
```

**Bug thứ hai phát hiện khi chạy thật**: `bm25_search()` ném `ValueError: too many values to unpack
(expected 5)` ở MỌI task → nuốt vào `except` rồi âm thầm rơi baseline (log:
`plan_generation: sinh nội dung AI lỗi cho task ... (ValueError) — dùng baseline`). Nguyên nhân:
`_ScopedRetriever.base_statement()` của TV3 đã thêm cột (`title`/`source_url`/`effective_date`),
trong khi code unpack theo **vị trí**. Đã sửa sang đọc theo **tên cột** để lần sau bên đó mở rộng
select không làm vỡ im lặng nữa.

---

## 6. Markdown renderer (mục 3.6)

`renderMarkdown()` trước chỉ xử lý heading và bullet `- ` — dòng `1. `, `2. ` rơi vào nhánh đoạn văn
nên bị nối thành **một cục chữ liền** (đúng ảnh PM chụp). Đã thêm:
- `<ol>` cho danh sách đánh số (`1. ` / `2) `).
- Checkbox `- [ ]` / `- [x]` → `<input type="checkbox" disabled>` (chỉ hiển thị trạng thái:
  `PlanTask` lưu status của cả task, không lưu từng dòng checklist).
- `[n]` → nút bấm mở đúng nguồn; `slugifyHeading()` gắn `id` cho heading (bỏ dấu tiếng Việt trước
  khi slug hoá, nếu không "Cài đặt môi trường" và "Cai dat moi truong" ra 2 id khác nhau).

Thứ tự kiểm tra quan trọng: checkbox phải thử **trước** bullet thường vì cùng mở đầu `- `.

---

## 7. Thêm/xoá task: qua Master Template, không tạo `PlanTask` tự do (mục 3.5)

**Đổi hướng so với ý định ban đầu.** Bản nháp định thêm `POST/DELETE /plan-tasks` để PM thêm/xoá
task thẳng trên lộ trình chuẩn. Kiểm chứng lại bằng code cho thấy hướng đó sai:
- `PlanTask.template_task_id` là **NOT NULL** (`src/model/plan_task.py:16`) — task tạo tự do không
  có `TemplateTask` để trỏ về.
- `category`/`estimated_minutes` nằm ở `TemplateTask`, không có ở `PlanTask`.
- Regenerate lộ trình sẽ xoá sạch task thêm tay.

**Cách làm đúng**: PM thêm/xoá task ở **Master Template** (tạo version DRAFT → sửa → duyệt) rồi tạo
lại lộ trình. Hạ tầng này **đã có sẵn** — `template_task_service` đủ `create/update/delete/reorder`,
đều qua `_require_draft_version()`. Phần bổ sung chỉ là chỉ đường trong UI: banner ở trang Onboarding
Plan giải thích vì sao + nút "Sang Master Template".

---

## 8. Kiểm chứng cuối

```
$ pytest tests/ PM-test/ -q
219 passed in 42.92s

$ ruff check src/ tests/ PM-test/
All checks passed!

$ cd frontend && npx tsc --noEmit && npx eslint src
(sạch, không lỗi)

$ docker compose exec backend python -m alembic heads
e5f6a7b8c9d0 (head)          # 1 head duy nhất, không còn nhánh phân kỳ
```

**Test mới thêm** (mỗi cái map đúng 1 mục):
| Test | Mục |
|---|---|
| `test_upload_single_document_creates_active_version` (mở rộng: assert có chunk) | 3.1 |
| `test_company_task_reads_policy_and_appears_in_plan` | 3.2 |
| `test_task_without_document_does_not_fabricate_steps` | 3.3 |
| `test_citation_validator_rejects_out_of_range_reference` | 3.4 |

**Test có sẵn phải sửa theo thiết kế mới** (không phải test hỏng):
- `test_onboarding_templates`: `categories` giờ gồm cả `COMPANY` (1 công ty + 5 dự án).
- `test_template_versions::test_approve_version_fails_on_cycle`: trước đây dựa vào việc template
  fork sẵn có cạnh A→B giữa đúng 2 task đầu — giả định đó vỡ khi COMPANY chen lên đầu. Đã sửa để
  test tự chèn cả 2 chiều, không phụ thuộc thứ tự task trong seed.
- `PM-test/conftest.py` + `tests/conftest.py`: thêm fixture `allow_header_user_context` (mặc định
  của setting này giờ là `False` — đúng cho production, nhưng test gọi qua ASGITransport không có
  trình duyệt giữ cookie). Đồng thời teardown phải xoá `DocumentChunk` trước `DocumentVersion` vì
  giờ tài liệu PROJECT đã có chunk thật.

---

## 9. Trạng thái GADGETHUB (sẵn sàng để PM test tay)

- 5 tài liệu ACTIVE, 37 chunk, đều có embedding.
- Master Template version 5 APPROVED, 8 task: 1 COMPANY + 7 nhóm dự án.
- Lộ trình chuẩn `plan_id=689`: 8 task, 18 trích dẫn, 8/8 do AI viết.
- Lộ trình chuẩn **cũ** (sinh bằng code lỗi, nội dung bịa) đã xoá — chưa cấp cho kỹ sư nào nên xoá
  an toàn, không ảnh hưởng ai.

**Lưu ý khi test trên UI**: các user seed trước đây chưa có mật khẩu (seed cũ ra đời trước tính năng
auth), đã backfill bằng đúng `auth_service.hash_password` — mật khẩu chung: `ralionralion`.
Ví dụ `pm.phoneshop@onboarding.dev` / `ralionralion`.

---

## 10. Việc chưa làm / cần bàn tiếp

- **Trích dẫn của lộ trình đã cấp cho kỹ sư**: plan kỹ sư là bản sao của lộ trình chuẩn, nên tự có
  `chunk_id` khi lộ trình chuẩn được sinh lại. Plan cấp **trước** đợt này vẫn chỉ có `version_id` —
  không lỗi, chỉ là bấm trích dẫn mở nguyên file như cũ.
- **`source_key` khi bật GitHub sync**: tài liệu PM tải tay dùng tiền tố `upload:...`, còn GitHub
  sync dùng định danh riêng của TV3. Nếu sau này bật sync cho project đã có tài liệu tải tay, cùng
  1 file có thể tồn tại thành 2 document. Cần thống nhất `source_key` với TV3 trước khi bật.
- **`alembic check` còn báo lệch kiểu nhỏ** (`TEXT`→`String`, `TIMESTAMP`→`DateTime`) trên 2 cột
  `knowledge_documents.last_ingest_error*` — code có sẵn của develop, không phải do đợt này, không
  đụng tới.
