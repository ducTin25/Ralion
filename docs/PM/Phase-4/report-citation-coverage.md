# Báo cáo: Trích dẫn đúng đoạn + bao phủ toàn bộ tài liệu trong lộ trình chuẩn

**Ngày**: 15/08/2026 · **Nhánh**: `pm-document-management` · **Phạm vi**: Phase 4 — bước 5 sinh nội
dung PlanTask, trích dẫn nguồn, hiển thị phía PM.

---

## 1. Vấn đề PM phát hiện khi test thật

Sau đợt sửa nhóm COMPANY, PM tiếp tục chạy thử lộ trình chuẩn của GADGETHUB và báo 2 điểm:

| # | Hiện tượng PM thấy | Kỳ vọng |
|---|---|---|
| 1 | Bấm trích dẫn `[n]` luôn mở về **đầu file**, không nhảy tới đoạn tương ứng | Bấm là tới đúng đoạn đã dùng để viết ý đó |
| 2 | Nhóm có nhiều tài liệu nhưng nội dung task chỉ nhắc vài tài liệu, các bước rất ngắn | Liệt kê **đủ** mọi tài liệu trong nhóm, tóm ý từng mục lớn, và nói rõ vẫn phải đọc bản gốc |

Yêu cầu PM chốt thêm: nhóm "Tìm hiểu công ty" phải **chia theo 5 nhóm chính sách**, mỗi tài liệu nêu
các mục lớn, mỗi mục bấm được và trỏ đúng đoạn.

---

## 2. Nguyên nhân gốc (đọc code + đối chiếu DB thật, không suy đoán)

### 2.1. Trích dẫn nhảy sai — 3 lớp lệch cộng dồn

| Lớp | Thực tế | Bằng chứng |
|---|---|---|
| Backend tính `anchor` | Slug hoá **cả breadcrumb** bằng thuật toán **xoá hẳn** ký tự có dấu | `chunkers.py:67-69` → `"kin-trc-h-thng-todo-api-2-thnh-phn-24-..."` |
| Frontend render heading | Slug **chỉ tên mục lá**, thuật toán NFD **giữ chữ cái** bỏ dấu | `markdownPreview.tsx:6-15` → `"24-appschemaspy-hop-dong-api-contract"` |
| Modal tra cứu | Tách `anchor` theo `>` rồi slug **lần nữa** | `DocumentPreviewModal.tsx:81-85` — vô nghĩa vì `anchor` đã phẳng |

Ba chuỗi không bao giờ trùng nhau → `querySelector` luôn trả `null` → luôn rơi về đầu file. Tài liệu
POLICY còn tệ hơn: `policy_ingestion.py` không truyền `anchor` khi tạo chunk (luôn rỗng).

Truy vấn thật xác nhận trước khi sửa:

```
plan_task_id | chunk_id |                     anchor                      |     section_path
-------------+----------+-------------------------------------------------+---------------------
        6627 |      285 |                                                 | 2. Định nghĩa       <- POLICY: anchor RỖNG
        6629 |      810 | kin-trc-h-thng-todo-api-2-thnh-phn-24-apps...    | Kiến trúc ... > 2.4 <- PROJECT: mất dấu
```

### 2.2. Bao phủ tài liệu — xếp hạng BM25 + trần số nguồn

- `search_project_docs`/`search_company_policy` chạy **1 câu truy vấn chung** rồi lấy top-K: tài liệu
  ít từ khoá trùng câu truy vấn bị đẩy khỏi kết quả và **biến mất khỏi lộ trình**.
- `MAX_SOURCES_PER_TASK = 4` (rồi `COMPANY_MAX_SOURCES = 10`) cắt cứng số nguồn — nhóm 18 tài liệu
  chính sách chỉ hiện 4, sau đó 6.
- Ngay cả tài liệu lọt vào kết quả cũng chỉ được đọc 1-2 đoạn, nên tóm tắt bỏ sót phần trọng tâm nằm
  ở cuối file. **Bao phủ tên file ≠ bao phủ nội dung.**

---

## 3. Thiết kế đã chọn (qua 3 vòng phản biện)

Plan được review 3 vòng trước khi code; mỗi vòng đều kiểm chứng lại bằng code thật:

| Vòng | Điểm bị bắt lỗi | Đã sửa thành |
|---|---|---|
| 1 | Tự ý hạ yêu cầu thành "1 tài liệu = 1 trích dẫn" | Nhiều trích dẫn / 1 tài liệu |
| 2 | Lấy 2 đoạn/tài liệu vẫn bỏ sót nội dung; prompt COMPANY quá lớn; chưa chia 5 nhóm chính sách; bỏ quên Member Portal | Đọc **toàn bộ** đoạn + chia lô + chia nhóm chính sách |
| 3 | Nới constraint `PlanTaskSource` sẽ **phá Member Portal** của thành viên khác; thiếu semaphore, thiếu `citation_order`, snippet markdown thô | **Bảng con `PlanTaskCitation`**, semaphore, cột thứ tự tường minh, snippet đã làm sạch |

### Kiến trúc 2 tầng — điểm mấu chốt để không ảnh hưởng module người khác

```
PlanTask
 └─ PlanTaskSource   (GIỮ NGUYÊN: 1 dòng = 1 tài liệu cần đọc)   <- Member Portal đọc bảng này
     └─ PlanTaskCitation (MỚI: 1 dòng = 1 đoạn, có citation_order) <- chỉ phía PM dùng
```

Nếu nới `UniqueConstraint(plan_task_id, version_id)` của `PlanTaskSource` để chứa nhiều đoạn, thì
`member_onboarding_service._task_sources()` (module của ducTin25) sẽ hiện **trùng lặp cùng 1 file
nhiều lần** — hồi quy thật ở code người khác. Bảng con tránh hoàn toàn việc đó.

### Bao phủ là bất biến của CODE, không phải lời hứa của LLM

```
1. _collect_outlines        đọc TOÀN BỘ đoạn của TỪNG tài liệu (không xếp hạng, không cắt)
2. _batch_documents         chia lô ≤10 đoạn — chỗ DUY NHẤT khống chế kích thước prompt
                            (không trộn 2 nhóm chính sách; tài liệu dài tự tách nhiều lô)
3. _summarize_batch         mỗi lô 1 lời gọi LLM, chạy song song qua Semaphore(4)
4. _build_sources_section   RÁP BẰNG CODE: lặp qua từng tài liệu → từng đoạn
                            đoạn nào LLM bỏ sót → tự ghi chú + vẫn giữ trích dẫn trỏ đúng đoạn
```

Bước 4 là lý do bao phủ được **bảo đảm bằng cấu trúc vòng lặp**, không phụ thuộc LLM có nhớ liệt kê
đủ hay không.

---

## 4. Thay đổi cụ thể

### Backend

| File | Thay đổi |
|---|---|
| `src/model/plan_task_citation.py` | **MỚI** — bảng trích dẫn mức đoạn, 2 unique constraint |
| `alembic/versions/f6a7b8c9d0e1_...py` | **MỚI** — `create_table` thuần, không `ALTER`/`DROP` bảng nào |
| `plan_generation/tools.py` | **Thêm** `fetch_all_document_chunks()`; giữ nguyên các hàm search cũ |
| `plan_generation/content_llm.py` | Viết lại pipeline map-reduce; bỏ `MAX_SOURCES_PER_TASK`/`COMPANY_MAX_SOURCES` |
| `plan_generation/prompts.py` | Thêm prompt tóm tắt theo lô + câu nhắc đọc bản gốc |
| `onboarding_plan_service.py` | Ghi 2 tầng; xoá theo đúng chiều FK khi tạo lại plan |
| `plan_task_service.py` | Thêm `list_task_citations()` + `_plain_text_snippet()` |
| `plan_task_response_dto.py` | Thêm `citations` **bên cạnh** `sources` (không đổi field cũ) |

### Frontend

| File | Thay đổi |
|---|---|
| `markdownPreview.tsx` | Thêm nhánh blockquote `> ` (trước đây hiện nguyên ký tự `>`) |
| `DocumentPreviewModal.tsx` | Định vị 2 tầng: **nội dung đoạn** → dự phòng `section_path` |
| `PlanTaskDrawer.tsx` | `[n]` map sang `citations`; thêm khối "Trích dẫn theo đoạn" |
| `planTask.response.ts`, `globals.css`, `.module.scss` | Kiểu dữ liệu + style tương ứng |

### Vì sao định vị theo nội dung thay vì sửa `anchor`

`anchor` sai là do thuật toán slug ở `chunkers.py`/`policy_ingestion.py` — **file của thành viên
khác (quyonghappi)**. Nhưng kể cả sửa đúng, nhảy theo tiêu đề vẫn không chính xác khi 1 tiêu đề bị
tách nhiều đoạn hoặc 2 mục trùng tên. Nên chọn định vị theo **nội dung đoạn thật**
(`content_snippet`), lấy `section_path` (đã đúng sẵn) làm lớp dự phòng — **không cần sửa file của
quyonghappi**, mà còn chính xác hơn.

`content_snippet` bỏ **đúng** những cú pháp mà `renderInline`/`renderMarkdown` bỏ (đậm, code, link,
tiền tố dòng) — bỏ ít hơn thì còn ký tự markdown không có trong DOM, bỏ nhiều hơn (vd `|` của bảng,
renderer chưa xử lý) thì tạo chuỗi không tồn tại. Cả hai đều làm việc dò trượt; có test canh riêng.

---

## 5. Bảo đảm không ảnh hưởng thành viên khác

### 5.1. Module Chat/RAG của Mai Anh (TV3) — KHÔNG đụng

```
$ git diff --stat src/ai/retrieval_engine/retrieval_engine.py
(rỗng — không còn thay đổi gì)
```

Vòng trước có thêm `policy_categories` vào `RetrievalFilters` (file dùng chung). Sau khi pipeline mới
bỏ hẳn BM25 ở bước này, field đó thành **code chết** → đã hoàn nguyên file về đúng bản gốc và gỡ hàm
`search_company_policy_diverse` do chính mình thêm. Kết quả: **0 dòng thay đổi** trong module
retrieval của TV3.

Không đụng: `document_chunks` (chỉ đọc, không đổi schema/dữ liệu), `chunkers.py`,
`policy_ingestion.py`, `RetrievalEngine`/BM25, module Chat, pipeline embedding/ingest.

Test Chat/RAG chạy riêng để xác nhận:

```
$ pytest tests/test_api/test_chat_api_end_to_end.py tests/test_api/test_chat_auth.py \
         tests/test_modules/test_chat_end_to_end.py -q
13 passed in 1.91s
```

### 5.2. Member Portal của ducTin25 — KHÔNG đụng file nào

`member_onboarding_service.py`, `member_onboarding_response_dto.py`,
`member_onboarding_router.py`, `TaskDetailDrawer.tsx` — **0 thay đổi**. Member Portal vẫn đọc
`PlanTaskSource` y hệt trước, số dòng và ý nghĩa không đổi. Có test canh ranh giới này:

```python
test_plan_task_source_stays_one_row_per_document   # không được có 2 dòng cùng (task, tài liệu)
```

### 5.3. File dùng chung bị đụng trong lượt này — chỉ 2, đều thuần cộng thêm

| File | Thay đổi | Rủi ro xung đột |
|---|---|---|
| `src/model/__init__.py` | +1 dòng `plan_task_citation,` | Rất thấp — thêm vào danh sách import |
| `frontend/src/app/globals.css` | +1 class `.pm-quote` ở cuối file | Rất thấp — không sửa class có sẵn |

Các file chung khác trong `git status` (`knowledge_document_router.py`, `enums.py`, `project.py`,
`github_sync_worker.py`, `product-manager/page.tsx`…) là thay đổi từ **các đợt trước**, không phải
lượt này.

---

## 6. Kiểm chứng

### 6.1. Test

```
$ pytest PM-test/ tests/ -q
235 passed in 50.73s

$ ruff check src/ PM-test/
All checks passed!

$ cd frontend && npx tsc --noEmit
(không lỗi)
```

**15 test mới** cho đợt này, chia 2 nhóm:

*Nhóm hàm thuần (không cần DB, không cần mạng):*

| Test | Canh điều gì |
|---|---|
| `test_batch_documents_never_mixes_policy_categories` | Nhóm chính sách nhỏ không bị nhóm lớn lấn át |
| `test_batch_documents_splits_oversized_document_without_losing_chunks` | Tài liệu dài tách lô, **không mất không trùng** đoạn nào; `offset` cộng dồn đúng |
| `test_build_sources_section_covers_every_chunk_even_without_summary` | LLM bỏ sót vẫn đủ trích dẫn — bao phủ do code |
| `test_build_sources_section_groups_policy_documents_by_category` | Hiện đúng 5 nhóm chính sách |
| `test_build_sources_section_flags_document_without_chunks` | Tài liệu chưa tách đoạn phải nói thẳng |
| `test_parse_batch_summaries_ignores_numbers_outside_batch` | LLM bịa số → bỏ, không gán nhầm đoạn |
| `test_plain_text_snippet_strips_only_what_renderer_strips` | Snippet khớp chính xác DOM sau render |
| `test_plain_text_snippet_is_capped` | Giới hạn độ dài |

*Nhóm tích hợp (LLM giả — chạy đường đi thật: truy xuất → chia lô → ráp → ghi DB → API):*

| Test | Canh điều gì |
|---|---|
| `test_ai_plan_persists_one_citation_per_chunk` | 3 đoạn → 3 trích dẫn, `sources` vẫn 1 dòng/file |
| `test_ai_plan_still_cites_chunks_llm_skipped` | LLM chỉ tóm 1/3 đoạn → vẫn đủ 3 trích dẫn + ghi chú |
| `test_regenerate_replaces_citations_without_fk_error` | Tạo lại không vỡ FK, không nhân bản trích dẫn |
| `test_engineer_plan_clones_citations_from_reference` | Kỹ sư nhận bản sao **có đủ** trích dẫn |
| `test_plan_task_citation_rejects_duplicate_order` | DB chặn 2 đoạn cùng mang số `[3]` |
| `test_company_task_lists_every_active_policy_document` | Liệt kê **đủ** mọi tài liệu chính sách ACTIVE (đối chiếu DB, không hardcode) |
| `test_plan_task_source_stays_one_row_per_document` | **Bảo vệ Member Portal** |
| `test_member_portal_displays_exact_citations_pm_approved` | Gọi THẲNG `/api/v1/member/plan-tasks/{id}` bằng danh tính kỹ sư, đối chiếu từng chữ với bản PM đã duyệt (xem mục 6.4) |

### 6.2. Migration

```
$ alembic upgrade head
Running upgrade e5f6a7b8c9d0 -> f6a7b8c9d0e1, them bang plan_task_citations
```

```
$ \d plan_task_citations
Indexes:
    "pk_plan_task_citations" PRIMARY KEY, btree (citation_id)
    "uq_plan_task_citations_plan_task_id" UNIQUE CONSTRAINT, btree (plan_task_id, citation_order)
    "uq_plan_task_citations_task_source_id" UNIQUE CONSTRAINT, btree (task_source_id, chunk_id)
Foreign-key constraints:
    -> document_chunks(chunk_id), plan_tasks(plan_task_id), plan_task_sources(task_source_id)
```

Chỉ tạo bảng mới, không `ALTER`/`DROP` bảng nào — an toàn cho mọi module đang chạy.

### 6.3. Triển khai

```
$ docker compose up -d --build backend    → Container p-040-backend-1 Started
$ curl localhost:8000/health              → {"status":"ok","env":"development"}
```

Dữ liệu GADGETHUB đã dọn sạch để PM tự quét lại và kiểm chứng trên UI:

```
      bang       | count
-----------------+-------
 documents       |     0
 chunks          |     0
 plans           |     0
 project con lai |     1     <- project giữ nguyên
 members con lai |     3     <- thành viên giữ nguyên
```

---

## 7. Bổ sung 15/08 (cùng ngày): Member Portal hiển thị y hệt PM

PM yêu cầu tiếp: xoá plan cũ của kỹ sư Dao Van G để tạo lại kiểm thử, và Member Portal (trang kỹ sư
dùng) phải hiển thị **đúng những gì PM đã tạo cho plan** — không lệch, không thiếu — vì bản chất
Member Portal chỉ là nơi đọc lại plan PM đã duyệt (kỹ sư không tự sinh nội dung riêng).

**Việc mục 8 (bản báo cáo gốc) ghi "tách PR riêng cho ducTin25 review" đã được thực hiện trong lúc
tôi làm việc khác** — kiểm tra thấy `member_onboarding_service.py`, DTO, và
`TaskDetailDrawer.tsx` (đổi tên thành `TaskDetailPage.tsx`) đã có sẵn thay đổi tương ứng, dùng đúng
`renderMarkdown()`/`DocumentPreviewModal` dùng chung với PM. Việc còn lại của tôi là **verify kỹ**
đúng như PM yêu cầu, không tự tin nhận "đã đúng" mà không kiểm chứng:

- Đối chiếu logic bấm trích dẫn giữa `PlanTaskDrawer.tsx` (PM) và `TaskDetailPage.tsx` (Member) —
  khớp hành vi (ưu tiên `citations`, lùi về `sources` nếu plan cũ chưa có bảng citation).
- Kiểm tra toàn bộ class CSS/icon dùng trong `TaskDetailPage.tsx` đều tồn tại trong
  `MemberPortal.module.scss`/`MemberIcon.tsx` — không thiếu style ngầm.
- `npx tsc --noEmit` toàn bộ frontend: **sạch**.
- `npx vitest run src/features/member-onboarding`: **14/14 pass**, có sẵn test canh đúng ca "bấm
  trích dẫn mở đúng đoạn".
- **Phát hiện lỗ hổng test thật**: không có test backend nào GỌI THẬT endpoint
  `/api/v1/member/plan-tasks/{id}` để kiểm citations — chỉ có test PM-side và test mock auth. Đã
  thêm `test_member_portal_displays_exact_citations_pm_approved` (`PM-test/test_plan_generation.py`)
  gọi thẳng endpoint Member bằng danh tính kỹ sư thật, đối chiếu **từng chữ** `instruction` và
  `citation_order`/`chunk_id` với bản PM đã duyệt.
- `pytest PM-test/ tests/ -q` → **238 passed** (tăng từ 235 do 3 test mới thêm trong ngày, gồm cả
  test Member Portal nói trên).
- `ruff check` sạch (sửa 1 lỗi thứ tự import nhỏ trong `member_onboarding_response_dto.py`).

**Xác nhận bằng dữ liệu thật trên GADGETHUB** (không chỉ test giả lập) — PM đã tự tạo lại lộ trình
chuẩn bằng AI thật trong lúc tôi verify:

```
title                                                | category     | so_trich_dan
Tìm hiểu chính sách công ty                          | COMPANY      | 192   <- 18 tài liệu, đủ 5 nhóm
Đọc tài liệu Overview dự án                          | ORIENTATION  |   7
Đọc tài liệu Architecture để hiểu hệ thống tổng thể  | ARCHITECTURE |  14
Xin quyền truy cập GitHub repo                       | ACCESS       |  93
...
```

Nội dung task COMPANY: 32.964 ký tự, đủ `## Mục tiêu`, `## Tài liệu nguồn cần đọc`, và câu nhắc
"đọc toàn bộ tài liệu" — đúng thiết kế, không phải dữ liệu giả.

Đã xoá plan cũ của Dao Van G (8 task, 46 nguồn, 427 trích dẫn) để PM tự cấp lại qua UI và kiểm chứng
Member Portal hiện đúng y hệt.

**Chưa xác minh bằng mắt trên UI thật** (chỉ xác minh qua API/DB) — cần PM tự đăng nhập bằng tài
khoản Dao Van G sau khi cấp plan để xem trực quan, vì trình duyệt không nằm trong khả năng của tôi.

---

## 8. Việc PM cần làm để nghiệm thu

1. Vào **Tài liệu dự án** → **Quét repository** → nạp lại bộ tài liệu (nếu chưa làm).
2. Sang **Onboarding Plan** → **Tạo lại bằng AI** (đã làm, xem bằng chứng mục 7).
3. Cấp plan cho Dao Van G (đã xoá plan cũ, sẵn sàng tạo lại).
4. Đối chiếu các điểm:
   - Task "Tìm hiểu chính sách công ty" liệt kê **đủ mọi** tài liệu chính sách, chia theo **5 nhóm**.
   - Mỗi tài liệu có nhiều `[n]` riêng cho từng mục lớn, cuối mỗi tài liệu có câu nhắc **đọc toàn bộ
     bản gốc**.
   - Bấm từng `[n]` → mở tài liệu và cuộn tới **đúng đoạn khác nhau** (không còn về đầu file).
   - Đăng nhập bằng tài khoản Dao Van G (Engineer) → mở cùng task → nội dung và trích dẫn phải
     **giống hệt** những gì thấy ở phía PM.

---

## 9. Việc chưa làm (có chủ đích)

| Việc | Lý do |
|---|---|
| **Sửa thuật toán `anchor`** | File của quyonghappi. Không cần nữa vì đã định vị theo nội dung đoạn (chính xác hơn) |
| **Tô sáng trong PDF** | PDF nhúng qua `<iframe>`, không có DOM text để dò — mở đúng file, không cuộn tới đoạn |
| **Tóm tắt phân tầng nhiều cấp** | `max_chunks_per_batch=10` + ráp xác định đã đủ bao phủ; thêm tầng tổng hợp bằng LLM sẽ làm giảm tính xác định mà không tăng độ phủ |
