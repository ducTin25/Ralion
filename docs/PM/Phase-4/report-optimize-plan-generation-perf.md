# Report: Tối ưu tốc độ + chi phí LLM sinh Onboarding Plan (đã code xong)

> Trạng thái: **ĐÃ CODE + ĐÃ TEST**, chưa commit. Thực hiện theo
> [plan-optimize-plan-generation-perf.md](plan-optimize-plan-generation-perf.md) (bản v3).
> Mọi con số trong báo cáo này đều **đo thật hoặc chạy thật**, chỗ nào chưa đo được thì ghi rõ là
> chưa đo — xem mục 7 (những thứ báo cáo này KHÔNG chứng minh được)

## 1. Đã làm gì

Viết lại bước 5 (`generate_content`) theo kiến trúc 3 pha đúng như plan v3:

| Pha | Làm gì | Đụng DB? | Gọi LLM? | Song song? |
|---|---|---|---|---|
| **A** `_phase_a_collect` | Đọc outline cho MỌI task, nhớ theo `version_id`; gom tập `chunk_id` duy nhất | Có | Không | Không (an toàn `AsyncSession`) |
| **B** `_phase_b_evidence_cards` | Sinh Evidence Card cho từng đoạn DUY NHẤT, xác minh quote | Không | Có | Có, trần 4 |
| **C** `_phase_c_task_content` | Mỗi task tự đánh số `[n]` cục bộ + viết nội dung, sửa 1 lần nếu sai | Không | Có | Có, chung trần 4 |

Điểm cốt lõi: **số `[n]` không nằm trong Evidence Card**. Card khoá theo `chunk_id`, số thứ tự do
từng task tự đếm ở `_build_sources_section`. Nhờ vậy 1 card dùng chung cho nhiều task mà không thể
kéo theo số trích dẫn của task đã tính nó.

### Các thay đổi cụ thể

| File | Thay đổi |
|---|---|
| `src/services/plan_generation/content_llm.py` | 3 pha; `EvidenceCard`; `LlmUsage`; `_build_evidence_block` thay `_build_citation_index_block`; `_build_sources_section` khoá theo `chunk_id`; sửa-1-lần |
| `src/services/plan_generation/prompts.py` | `EVIDENCE_CARD_SYSTEM_PROMPT` (JSON, **bỏ** `task_title`/`task_objective`); quy tắc 6 chia nhóm `###`; `build_repair_prompt` |
| `src/services/plan_generation/text_verification.py` | **Mới** — `verified_substring` xác minh quote nguyên văn |
| `src/services/plan_generation/pipeline.py` | Truyền callback tiến độ vào bước 5 |
| `src/services/plan_generation/job_store.py` | `update_step_detail()` — đổi riêng mô tả, không đụng `status`/`duration_ms` |
| `src/config.py` | 2 setting đơn giá DeepSeek (thuần thêm mới) |
| FE: `markdownPreview.tsx` | Thêm tuỳ chọn `headingPrefix` (**tuỳ chọn** — nơi gọi cũ không đổi) |
| FE: `PlanTaskDrawer.tsx` + `.module.scss` | Gắn icon/màu nhóm chính sách cho tiêu đề `###` |
| FE: `policyCategoryMeta.ts` | `POLICY_META_BY_LABEL` — tra ngược nhãn → icon/màu |

## 2. Không đụng vào code của thành viên khác

Đây là ràng buộc được nhắc giữa chừng, và **có 1 chỗ đã phải hoàn tác**:

- ❌ **Đã lỡ sửa `src/ai/orchestration/answer_generator.py`** (module chat — TV3/quyonghappi sở hữu)
  để 2 luồng dùng chung 1 hàm xác minh, đúng như plan v3 mô tả. → **Đã `git checkout` hoàn tác hoàn
  toàn**, file này giờ **không có 1 dòng nào thay đổi** (xác nhận bằng `git status`).
- ❌ **Đã lỡ tạo file trong `src/ai/`** → **đã chuyển** sang `src/services/plan_generation/text_verification.py`,
  thư mục `src/ai/` giờ sạch.
- ✅ **Member Portal** (`TaskDetailPage.tsx` — ducTin25) gọi chung `renderMarkdown`. Tham số mới là
  **tuỳ chọn**, không truyền thì render y hệt trước → có test riêng chốt điều này (mục 4).
- ✅ `src/config.py` là file dùng chung nhưng chỉ **thêm 2 dòng setting mới**, không sửa dòng nào có
  sẵn — đúng cách team vẫn làm (mỗi người thêm setting của mình, merge cơ học).

**Hệ quả của việc hoàn tác cần PM biết**: giờ có **2 bản** cùng một luật xác minh trích dẫn — bản của
PM và `answer_generator._verified_substring` của chat. Để 2 bên không lệch nhau mà vẫn không đụng file
của họ, `test_text_verification.py` có 1 test **đối chiếu 1000 ca ngẫu nhiên** giữa 2 thuật toán; hôm
nào chat đổi luật thì test đỏ ngay. Nếu sau này muốn gộp thật thì phải trao đổi với TV3 trước.

Toàn bộ 15 file thay đổi đều nằm trong: `src/services/plan_generation/`, `PM-test/`,
`frontend/src/features/project-management/`, `docs/PM/Phase-4/`, cộng 2 dòng ở `src/config.py`.

## 3. Kết quả chạy test

```
ruff check src tests PM-test              -> All checks passed
pytest PM-test/ tests/                    -> 314 passed (7 phút 30)
frontend: npx tsc --noEmit                -> sạch
frontend: npx eslint (3 file đã sửa)      -> sạch
frontend: npx vitest run                  -> 42 passed (37 cũ + 5 mới)
docker compose up -d --build backend      -> /health 200, /docs 200
```

Test mới viết: **24 test backend** (14 file `test_plan_generation_phases.py` + 10 file
`test_text_verification.py`) + **5 test frontend**. Test cũ sửa lại: 4 (do `_build_sources_section`
đổi từ khoá-theo-số-thứ-tự sang khoá-theo-`chunk_id`, và `_parse_batch_summaries` bị thay bằng
`_parse_evidence_cards` — đây là đổi hợp đồng có chủ đích, không phải sửa test cho xanh).

## 4. Test có thật sự bắt lỗi không (mutation testing)

Test xanh ngay lần đầu **chưa chứng minh được gì**. Nên đã cố tình phá từng bất biến rồi xem test có
đỏ không:

| Cố tình phá | Test bắt được? |
|---|---|
| Bỏ dedup — tóm tắt lại theo từng task (như bản cũ) | ✅ đỏ |
| Đánh số `[n]` toàn cục thay vì cục bộ theo task | ✅ đỏ |
| Chạy pha C tuần tự (mất song song) | ✅ đỏ |
| Bỏ semaphore ở lời gọi viết nội dung (như bản cũ) | ✅ đỏ |
| Bỏ nhánh sửa 1 lần | ✅ đỏ |
| Bỏ xác minh quote (tin thẳng LLM) | ✅ đỏ |
| Không lọc `chunk_id` lạ | ✅ đỏ |
| Bỏ cách ly lỗi từng task | ✅ đỏ |

**Lần chạy đầu chỉ 7/8 bị bắt** — test sửa-1-lần khi đó dựa vào "lần gọi thứ 2" nên vẫn xanh kể cả
khi nhánh sửa bị gỡ. Đã sửa lại để bản giả chỉ trả kết quả đúng khi **nhìn thấy lời nhắc sửa trong
hội thoại**, chạy lại thì đủ 8/8. Ghi lại đây vì đó đúng là kiểu "test tưởng có canh mà không canh gì".

Ngoài ra `test_text_verification.py` có 1 test viết sai kỳ vọng (quên chữ "phải" trong câu trích) —
**code đúng, test sai**, đã sửa test.

## 5. Đo thật: prompt to lên bao nhiêu

Đưa trích dẫn nguyên văn vào prompt là **điều kiện bắt buộc** để có grounding thật (bản cũ chỉ đưa
tên tài liệu nên LLM không có chữ nào của tài liệu để trích). Cái giá phải trả, đo trên hình dạng
nhóm COMPANY thật (18 tài liệu × 6 đoạn = 108 đoạn):

| | Khối NGUỒN cũ | Khối NGUỒN mới |
|---|---|---|
| Ký tự | 4.481 | 35.282 |
| Token (ước lượng /4) | ~1.120 | ~8.820 |
| | | **gấp ~7,9 lần** |

Đánh giá: ~8.800 token vẫn **thoải mái trong 64k context của DeepSeek**, chi phí input cho lời gọi
đó ≈ 8.820 × 0,27$/1M ≈ **0,0024 USD** — nhỏ về tuyệt đối. Nhưng đây đúng là rủi ro reviewer đã cảnh
báo, nên: cần vặn thì sửa `MAX_QUOTE_CHARS` (đang 240) trong `content_llm.py`, đã tách sẵn thành hằng
số riêng.

Đổi lại, số **lời gọi** LLM giảm: 108 đoạn dùng chung giữa nhiều task giờ chỉ tóm tắt 1 lần (12 lô),
thay vì lặp lại cho từng task tham chiếu.

## 6. Những chỗ làm KHÁC plan (có lý do, cần PM xác nhận)

1. **`summary` giữ ~30 từ, không phải 80-150 từ như plan ghi.** Lý do: `summary` render thành **1 gạch
   đầu dòng cho MỖI đoạn** trong mục "Tài liệu nguồn cần đọc". Nhóm COMPANY có 108 đoạn — 108 đoạn ×
   100 từ = một bức tường chữ, phá đúng cái mục nguồn mà Phase 4 trước đã sửa cho gọn. Trần 80-150 từ
   của reviewer nhắm vào việc **chặn prompt phình**, và việc đó đã được xử lý bằng `MAX_QUOTE_CHARS`
   (quote 240 ký tự) — đúng chỗ tốn nhiều ký tự nhất. **Nếu PM muốn đúng 80-150 từ thì nói, sửa 1
   hằng số là xong**, nhưng nên xem mục nguồn trên UI trước khi quyết.
2. **Không gộp hàm xác minh dùng chung với luồng chat** — vì ràng buộc không đụng code người khác
   (mục 2). Thay bằng test đối chiếu chống lệch.
3. **Không làm cache xuyên-plan** — đúng như plan (ticket riêng).
4. **Không làm tab UI cho nhóm chính sách** — đúng như plan (task FE riêng). Phần đã làm chỉ là icon +
   màu cho tiêu đề `###` trong nội dung, dùng lại đúng badge/token màu của `CompanyCoreDrawer` nên PM
   thấy cùng ngôn ngữ hình ảnh với Master Template, **không đặt thêm màu/font mới nào**.

## 7. Báo cáo này KHÔNG chứng minh được gì (phải nói rõ)

- **Chưa chạy với LLM thật.** Toàn bộ test dùng LLM giả. Nghĩa là **chưa biết** DeepSeek có chịu trả
  đúng JSON theo `EVIDENCE_CARD_SYSTEM_PROMPT` không, và **tỉ lệ quote khớp nguyên văn thực tế là bao
  nhiêu**. Đây là ẩn số lớn nhất còn lại: nếu model hay diễn giải thay vì chép, tỉ lệ card không có
  quote sẽ cao và nội dung mất trích dẫn thật (đã có sẵn log đếm 2 con số này).
- **Chưa có số latency trước/sau trên dữ liệu thật.** Con số 34.427 mili-giây trong plan là của lần
  đo cũ; **chưa chạy lại** sau khi sửa. Muốn có số thật phải bấm "Tạo lại bằng AI" trên project có
  template nhiều task rồi đọc `duration_ms` bước `generate_content`.
- **Chưa đo tỉ lệ dedup trên template thật** — mức giảm phụ thuộc template có bao nhiêu category >1
  task, mỗi dự án một khác.
- **Chưa nhìn bằng mắt trên UI thật** phần icon nhóm chính sách trong nội dung task (mới chỉ có test
  render + tsc/eslint/vitest xanh).

## 8. Việc tiếp theo đề xuất

1. **Chạy thử thật 1 lượt** trên project có đủ 5 nhóm policy, với `PLAN_GENERATION_USE_AI=true` +
   `DEEPSEEK_API_KEY` thật. Đọc log dòng `plan_generation: N lời gọi LLM, ... ~X USD` (đã có sẵn) và
   so `duration_ms` với 34.427 mili-giây cũ.
2. Mở PlanTaskDrawer xem icon nhóm chính sách hiển thị đúng chưa.
3. Nếu tỉ lệ quote không khớp cao → vặn prompt quy tắc 4 (`EVIDENCE_CARD_SYSTEM_PROMPT`), không phải
   nới lỏng hàm xác minh.
4. Sau khi có số thật → cân nhắc cache xuyên-plan (mục 3.4 của plan) và bộ eval Day-14 vẫn đang thiếu.

## 9. Cách kiểm chứng lại (chạy được ngay)

```bash
# Backend
.venv/Scripts/python.exe -m ruff check src tests PM-test
.venv/Scripts/python.exe -m pytest PM-test/ tests/ -q

# Chỉ phần mới
.venv/Scripts/python.exe -m pytest PM-test/test_plan_generation_phases.py PM-test/test_text_verification.py -q

# Frontend
cd frontend && npx tsc --noEmit && npx vitest run

# Docker
docker compose up -d --build backend && curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health
```
