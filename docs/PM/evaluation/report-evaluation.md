# Report: Evaluation cho bước sinh nội dung Onboarding Plan bằng AI — hàm nào, công dụng gì, dùng sao

> Trạng thái: **ĐÃ CODE + ĐÃ TEST ĐƠN VỊ (60 test, mutation-tested 6 lần) + ĐÃ CHẠY XONG ĐỦ 30/30
> CASE THẬT** (OpenAI `gpt-4o-mini` làm judge, DeepSeek sinh nội dung — không phải giả lập, 385/385
> test toàn hệ thống vẫn xanh sau mọi thay đổi). Đây là báo cáo giải thích **hàm nào làm gì, vì sao
> thiết kế vậy, và cách tự chạy lại** — xem `docs/PM/evaluation/plan-evaluation.md` cho lý do thiết
> kế/công thức từng metric, `docs/PM/Phase-4/eval-report.md` cho kết quả số liệu thật.

## 1. Bức tranh tổng thể — 4 file mới, vai trò riêng biệt

```
scripts/eval_prompts.py    ← THUẦN, không gọi mạng. Xây prompt + đọc kết quả LLM trả về.
scripts/eval_stats.py      ← THUẦN, không gọi mạng. mean±std, % thắng, % lệch calibrate.
scripts/eval_metrics.py    ← Gọi judge LLM thật (OpenAI), dùng 2 module trên.
scripts/eval_plan_content.py ← Điều phối: đọc golden set → gọi pipeline thật → gọi eval_metrics → ghi report.
```

Tách `eval_prompts.py`/`eval_stats.py` khỏi phần gọi mạng theo đúng nguyên tắc đã dùng cho
`content_llm.py` trong hệ thống chính: phần build-prompt/parse-response test được bằng pytest
thường, không cần key thật, không cần mock phức tạp — đây là 2 file có phần lớn trong 60 test đơn vị.

Ngoài 4 file trên, còn 2 thay đổi nhỏ trong hệ thống chính:
- `src/config.py` — thêm 3 field `groq_api_key`/`groq_api_base`/`groq_judge_model` (còn giữ lại dù
  cuối cùng KHÔNG dùng Groq nữa — xem mục 7 vì sao — để không mất công đã test, dễ quay lại nếu Groq
  ổn định hơn sau này). Judge model cuối cùng dùng thẳng `openai_api_key` đã có sẵn trong Settings.
- `src/services/llm.py` — thêm hàm `get_judge_llm()`, cùng pattern với `get_plan_content_llm()`
  (DeepSeek) và `get_classifier_llm()` (DeepSeek) đã có sẵn. Model cuối: **OpenAI `gpt-4o-mini`**.

## 2. `scripts/eval_prompts.py` — xây prompt + đọc kết quả (không gọi mạng)

| Hàm | Công dụng |
|---|---|
| `build_extract_claims_prompt(text)` | Prompt tách 1 đoạn văn thành list câu khẳng định độc lập (dùng cho cả Faithfulness lẫn Context Recall — 2 metric đều cần tách claim trước). |
| `parse_claims_response(text)` | Đọc kết quả trên: 1 dòng = 1 claim, tự bỏ số thứ tự/gạch đầu dòng nếu model lỡ thêm dù đã dặn không. |
| `build_batch_supported_check_prompt(claims, source_text)` | Gộp NHIỀU claim vào 1 lời gọi — hỏi "mỗi claim có được đoạn tài liệu xác nhận không", trả lời có đánh số. Thêm giữa chừng khi code (xem mục 7) để giảm số lời gọi. |
| `build_batch_relevance_check_prompt(chunks, task_objective)` | Biến thể gộp lô cho Context Precision — hỏi "mỗi đoạn tài liệu có liên quan mục tiêu task không". |
| `parse_batch_yes_no(text, count)` | Đọc kết quả 2 hàm trên — khớp theo SỐ THỨ TỰ ghi trong câu trả lời (không theo vị trí dòng, vì model đôi khi bỏ dòng trống/gộp dòng). Số nào thiếu mặc định KHÔNG. |
| `build_supported_check_prompt`/`build_relevance_check_prompt`/`parse_yes_no` | Biến thể 1-item (không gộp lô) — vẫn giữ, dùng làm hàm nền cho parse response đơn lẻ. |
| `build_judge_prompt_with_reference(reference_content, ai_content)` | Prompt Judge kiểu SO SÁNH — dùng cho 12/30 case có `reference_content` (xem mục 4 `plan-evaluation.md`). |
| `build_judge_prompt_no_reference(ai_content, task_objective)` | Biến thể Judge KHÔNG so sánh, chấm tuyệt đối theo mục tiêu task — dùng cho 18/30 case còn lại (KHÔNG có trong bản plan duyệt ban đầu, thêm khi code để golden set không cần 100% case có đáp án mẫu). |
| `parse_judge_response(text)` | Bóc JSON khỏi câu trả lời Judge (chịu được ```json bọc thừa), validate đủ 4 tiêu chí + điểm nằm trong 1-5, trả `None` nếu hỏng — không ném exception ở tầng thuần. |
| `judge_mean_score(parsed)` | Điểm trung bình 4 tiêu chí — 1 số để so nhanh AI vs Baseline. |

## 3. `scripts/eval_stats.py` — thống kê thuần

| Hàm | Công dụng |
|---|---|
| `mean_std(values)` | Trung bình + độ lệch chuẩn — `std=0.0` khi chỉ có 1 giá trị (Baseline B0 deterministic, chỉ chạy 1 lần/case, xem mục 6 plan). |
| `win_rate(ai_scores, baseline_scores)` | % case AI có điểm CAO HƠN (strict, hoà không tính) baseline. |
| `calibration_agreement_rate(human_scores, judge_scores, tolerance=1.0)` | % case điểm người và điểm Judge lệch ≤ tolerance — proxy cho Cohen's κ (mục 8 plan). |

## 4. `scripts/eval_metrics.py` — gọi judge model thật

5 hàm async, mỗi hàm ứng đúng 1 metric trong `plan-evaluation.md` mục 5, đều dùng bản GỘP LÔ (batch)
để giảm số lời gọi (`_batch_check_supported`/`_batch_check_relevant`, ≤20 item/lô):

| Hàm | Công thức | `None` khi nào |
|---|---|---|
| `faithfulness(llm, ai_content, source_text)` | % claim (tách từ nội dung AI) được nguồn xác nhận | Nội dung không tách được claim nào (case NO_HIT_NOTICE) |
| `context_recall(llm, reference_content, retrieved_text)` | % ý trong bản chuẩn có mặt trong tài liệu đã lấy | Case không có `reference_content` |
| `context_precision(llm, chunks_used, task_objective)` | % đoạn đã lấy thực sự liên quan | Không có chunk nào |
| `judge_score(llm, ai_content, reference_content, task_objective)` | Rubric 1-5 × 4 tiêu chí, tự chọn prompt so sánh/tuyệt đối tuỳ có `reference_content` hay không | Judge trả JSON hỏng sau khi thử |

`MAX_CONCURRENT_JUDGE_CALLS = 1` — di sản từ lúc dùng Groq (concurrency cao là nguyên nhân chính gây
429, xem mục 7), giữ nguyên vì tuần tự vẫn đủ nhanh với OpenAI, không cần đổi lại.

## 5. `scripts/eval_plan_content.py` — điều phối, chạy thật

Chạy theo 2 pha rõ ràng, **cố tình tách** để lỗi ở pha 2 (gọi judge chấm điểm) không làm mất dữ liệu
đã tốn tiền/thời gian sinh ở pha 1 (gọi DeepSeek):

**Pha 1 — sinh nội dung (mỗi dự án 1 lần, KHÔNG phải mỗi case)**
1. `load_golden_dataset(path)` — đọc `.jsonl` thành `list[GoldenCase]`.
2. `_build_project_context(db, project_key)` — dựng `GenerationContext` bằng ĐÚNG 4 hàm thật của
   `steps.py` (`load_template_for_project` → `merge_company_core` → `collect_project_docs` →
   `map_task_sources`), giống hệt `pipeline.py` làm khi PM bấm nút thật.
3. Với mỗi dự án: gọi `content_llm.generate_baseline_content(context)` (1 lần, deterministic) và
   `content_llm.generate_ai_content(db, context, project_key)` **N lần** (mặc định 3, vì
   `temperature=0.2` không deterministic — mục 7 plan). Vì 1 lần gọi sinh nội dung CHO CẢ dự án
   (7-8 task cùng lúc), 30 case chỉ cần **4 dự án × 3 lần = 12 lượt gọi pipeline**, không phải 30×3.
4. Với mỗi case: ráp `retrieved_text` = toàn bộ chunk mà task được phép đọc, **cắt ngắn qua
   `_cap_chunks_for_judge()`** (mỗi chunk ≤500 ký tự, tổng ≤6000 ký tự — giới hạn CHỈ áp dụng cho
   bước chấm điểm, KHÔNG ảnh hưởng tài liệu đưa cho model sinh nội dung — xem mục 7 vì sao cần).

**Pha 2 — chấm điểm (gọi `eval_metrics.py`, model judge)**

Với mỗi case: `context_precision` (1 lần), `context_recall` (1 lần, nếu có `reference_content`),
rồi với MỖI lần sinh AI: `faithfulness` + `judge_score`; cuối cùng `faithfulness`/`judge_score` cho
Baseline (1 lần). Mỗi case được bọc `try/except` riêng (`_score_case`) — case nào judge lỗi giữa
chừng chỉ đánh dấu `scoring_note`, KHÔNG làm hỏng kết quả case khác đã chấm xong.

**`write_report(...)`** — ghi `eval-report.md`: bảng theo category (Faithfulness/Precision/Recall/
Judge AI vs B0, % thắng), bảng chi tiết từng case, 3 case điểm Judge thấp nhất để PM tự điền 5 Whys
(script KHÔNG tự suy luận nguyên nhân — chỉ xếp hạng theo điểm, phần "vì sao" cần người đọc).

## 6. Cách tự chạy lại

```bash
# .env cần OPENAI_API_KEY (key thật, đã test — xem mục 7) và DEEPSEEK_API_KEY

# Chạy thử vài case trước (khuyến nghị luôn làm bước này trước khi chạy đủ)
PYTHONPATH=. .venv/Scripts/python.exe scripts/eval_plan_content.py --pilot 3 --runs 1

# Chạy đủ 30 case, 3 lần/case cho nhánh AI (mặc định)
PYTHONPATH=. .venv/Scripts/python.exe scripts/eval_plan_content.py

# Tuỳ chỉnh
PYTHONPATH=. .venv/Scripts/python.exe scripts/eval_plan_content.py --runs 3 --out docs/PM/Phase-4/eval-report.md
```

Yêu cầu: Docker đang chạy (`docker compose up -d`) vì script đọc DB thật qua `DATABASE_URL` trong
`.env`, và `DEEPSEEK_API_KEY`/`OPENAI_API_KEY` phải là key sống (không phải placeholder).

## 7. Bài học thật từ quá trình chạy pilot — hành trình đổi judge model 3 lần

Đây là phần quan trọng nhất để hiểu TẠI SAO code trông như hiện tại — mọi quyết định dưới đây đều
xuất phát từ lỗi THẬT gặp phải khi chạy, không phải thiết kế trước trên giấy.

**Vòng 1 — Groq `openai/gpt-oss-120b`** (lựa chọn ban đầu trong plan, đã test rate limit OK lúc lên
kế hoạch): khi chạy thật hàng loạt bị **429 dồn dập**, kể cả khi header báo còn dư quota (`remaining-
tokens: 7794/8000`). Đã thử 4 cách chữa: giảm concurrency, gộp nhiều claim/chunk vào 1 lời gọi (viết
thêm `build_batch_*`/`parse_batch_yes_no`), cắt ngắn tài liệu gửi cho judge (`_cap_chunks_for_judge`),
thêm giãn cách cố định giữa các lời gọi — vẫn không ổn định. Dò trên Groq dashboard
(console.groq.com/dashboard/logs) thấy các request 429 có `INPUT/OUTPUT TOKENS = 0`, `LATENCY ≈ 0` —
bị chặn NGAY, chưa xử lý gì — và luôn xảy ra khi 2+ request tới CÙNG LÚC. Kết luận: tier free giới
hạn **số request đồng thời** (có vẻ chỉ chịu 1), không phải token/phút như tài liệu ghi.

**Vòng 2 — Groq `openai/gpt-oss-20b`** (đổi model nhỏ hơn, cùng key, test 15/15 request liên tiếp
100% thành công): nhưng phát hiện bug KHÁC — model này là loại "reasoning" (tự suy luận trước khi
trả lời). Debug trực tiếp với nội dung task thật (~4000 ký tự) thấy `finish_reason: "length"` và
`response.content` RỖNG — model đốt hết ngân sách token mặc định vào phần suy luận nội bộ, chưa kịp
viết câu trả lời thì bị cắt. Sửa bằng `max_tokens=6000` — test lại: 26 claim tách đúng,
`finish_reason: "stop"`. Đúng lúc này Groq Developer tier (trả phí) cũng đang tạm khoá nâng cấp
("temporarily unavailable due to high demand").

**Vòng 3 — OpenAI `gpt-4o-mini`** (quyết định cuối): PM tạo key OpenAI + billing thật. Chạy pilot 3
case: **0 lỗi, 0 lần retry, tất cả metric đều ra số** (Faithfulness 1.00, Judge AI 4.25-5.00 vs
Baseline 3.25-4.50, 100% case AI thắng). Không phải model "reasoning" ẩn nên không cần `max_tokens`
đặc biệt như Groq. Chuyển hẳn sang dùng model này.

**Bài học chung, áp dụng được cho việc khác**: (1) header rate-limit của provider không phải lúc nào
cũng phản ánh đúng giới hạn thật — luôn kiểm bằng dashboard/log thật của provider khi nghi ngờ; (2)
model "reasoning" (suy luận ẩn trước khi trả lời) cần set `max_tokens` rộng rãi, không set là dễ mất
trắng câu trả lời mà không báo lỗi gì; (3) tách pha sinh/pha chấm + bọc try/except từng case là thứ
cứu được rất nhiều thời gian — không phải chạy lại từ đầu mỗi lần 1 phần bị lỗi.
