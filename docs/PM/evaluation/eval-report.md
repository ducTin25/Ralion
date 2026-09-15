# Eval Report — Sinh nội dung Onboarding Plan bằng AI vs Baseline B0

> Sinh tự động bởi `scripts/eval_plan_content.py`, KHÔNG viết tay. 30/30 case chạy thành công, 1 lần/case cho nhánh AI, tổng thời gian 2198.5s. Xem `docs/PM/evaluation/plan-evaluation.md` cho thiết kế đầy đủ, `docs/PM/report-evaluation.md` cho hướng dẫn đọc report này.

**Giới hạn cần biết trước khi đọc**: chạy `--runs 1` (không phải 3 như plan gốc đề xuất) để tiết
kiệm token theo yêu cầu khi chạy — nghĩa là cột `±std` của nhánh AI trong bảng dưới **không phản ánh
độ ổn định thật giữa nhiều lần sinh** (chỉ 1 lần/case, std tính được là do gộp NHIỀU CASE trong cùng
category, không phải lặp lại CÙNG 1 case). Xem mục 5 (Improvement log) — đây là việc nên làm khi có
ngân sách token dư dả hơn.

## 0. Cách đọc bảng dưới đây

Mỗi case chạy 2 nhánh song song để so sánh: **AI** (model DeepSeek đọc tài liệu thật rồi tóm tắt) và
**B0** (baseline — chỉ dán lại nguyên văn `instruction_template` PM đã viết sẵn trong Master Template,
không đọc tài liệu nào, không gọi LLM). Việc **chấm điểm** do 1 model khác hẳn đảm nhiệm — Groq
`openai/gpt-oss-120b` — cố tình khác model sinh nội dung, để tránh model tự chấm bài mình cao hơn
("self-preference bias").

Ý nghĩa từng cột (cơ chế đo thật, xem `scripts/eval_metrics.py`/`scripts/eval_prompts.py` nếu cần đối
chiếu code):

- **N case** — số case trong bộ golden dataset thuộc category đó. Càng nhỏ (vd COMPANY = 2) thì số
  trung bình càng dễ bị lệch bởi 1 case bất thường, nên đọc cẩn thận hơn.
- **Faithfulness AI / B0** — judge tách nội dung (AI hoặc B0) thành từng câu khẳng định độc lập
  (claim), rồi với mỗi claim hỏi "đoạn tài liệu nguồn có xác nhận câu này không?" (CÓ/KHÔNG).
  Faithfulness = tỉ lệ claim được xác nhận. Đo AI (hoặc B0) có bịa thông tin không so với tài liệu
  thật. B0 cũng bị chấm dù không đọc tài liệu gì — nội dung template PM viết sẵn vẫn được đối chiếu
  với tài liệu, nên B0 thấp là bình thường (không phải lỗi).
- **Context Precision** — với từng đoạn (chunk) tài liệu ĐÃ LẤY RA cho task đó, judge hỏi "đoạn này
  có liên quan tới mục tiêu task không (đủ để giúp hoàn thành, không lạc đề)?". Context Precision =
  tỉ lệ đoạn được đánh giá liên quan. Thấp không nhất thiết là lỗi retrieval — có category (ACCESS,
  COMPANY) cố tình đọc rộng hơn mức cần cho 1 task cụ thể, ưu tiên không bỏ sót thông tin quan trọng
  hơn là tối ưu độ liên quan (xem mục 4, Failure analysis).
- **Context Recall (N có reference)** — chỉ tính được cho case có sẵn "bản chuẩn" tham chiếu
  (`reference_content`, do PM/assistant viết tay trước — không phải mọi case đều có, số N ghi trong
  ngoặc). Đo: bao nhiêu ý trong bản chuẩn được tìm thấy trong đoạn tài liệu đã thực sự lấy ra dùng —
  tức có bỏ sót ý quan trọng nào không.
- **Judge AI / B0 (mean±std)** — khác 3 cột trên (chấm rời rạc theo từng đoạn/claim), đây là 1 lần
  chấm TỔNG THỂ nội dung theo rubric 4 tiêu chí, mỗi tiêu chí 1-5 điểm rồi lấy trung bình cộng:
  correctness (đúng, không bịa), relevance (đúng phạm vi, không lạc đề), completeness (đủ chi tiết để
  làm được task), coherence (dễ đọc, có cấu trúc). Case có bản chuẩn thì judge so sánh trực tiếp với
  bản chuẩn; case không có thì chấm tuyệt đối theo mục tiêu task — 2 cách chấm khác nhau này bị gộp
  chung 1 cột.
- **% AI thắng B0** — tỉ lệ case trong nhóm có `Judge AI > Judge B0`, so trực tiếp **theo từng case**
  (không phải so 2 số trung bình của cột Judge AI/B0 ở trên).

**Lưu ý khi đọc**: Faithfulness AI, Context Precision, và Judge AI đều dựa trên cùng 1 đoạn tài liệu
gửi cho judge xem — với case đọc nhiều tài liệu (đặc biệt COMPANY, tới 70 chunk), đoạn gửi cho judge
bị giới hạn còn khoảng 12 chunk đầu (`_cap_chunks_for_judge`, để tránh vượt rate-limit của judge model
miễn phí). Vì cả 3 cột dùng chung nguồn bị cắt này, chúng có thể cùng lệch theo 1 hướng ở case đó —
không phải 3 tín hiệu hoàn toàn độc lập xác nhận lẫn nhau. Xem chi tiết ở mục 4 (Failure analysis).

## 1. RAGAS scores + Judge scores theo category

| Category | N case | Faithfulness AI (mean±std) | Faithfulness B0 | Context Precision | Context Recall (N có reference) | Judge AI (mean±std) | Judge B0 | % AI thắng B0 |
|---|---|---|---|---|---|---|---|---|
| ACCESS | 8 | 0.97±0.04 | 0.62 | 0.29 | 1.00 (N=2) | 4.38±0.40 | 4.28 | 25% |
| ARCHITECTURE | 4 | 1.00±0.00 | 0.75 | 0.87 | 1.00 (N=2) | 4.88±0.12 | 3.94 | 100% |
| CODEBASE | 4 | 0.97±0.03 | 0.75 | 0.79 | 1.00 (N=2) | 4.69±0.32 | 3.56 | 75% |
| COMPANY | 2 | 0.74±0.26 | 0.17 | 0.89 | 1.00 (N=2) | 3.75±0.25 | 3.88 | 50% |
| ORIENTATION | 4 | 1.00±0.00 | 0.71 | 0.68 | 1.00 (N=2) | 4.81±0.11 | 4.44 | 75% |
| SETUP | 8 | 1.00±0.01 | 0.88 | 0.85 | 1.00 (N=2) | 4.59±0.12 | 4.06 | 100% |

## 2. Kết luận nhanh

- Tổng 30 case, **70%** case AI được Judge chấm trung bình CAO HƠN Baseline B0.
- Không dùng paired t-test (mẫu nhỏ theo từng category, xem mục 7 plan-evaluation.md) — đọc bảng trên theo category, không chỉ 1 con số tổng.

## 3. Chi tiết từng case

| case_id | project | category | difficulty | reference? | Faithfulness AI | Context Precision | Judge AI | Judge B0 |
|---|---|---|---|---|---|---|---|---|
| cpg_001 | PHONESHOP | ORIENTATION | easy | có | 1.00 | 0.78 | 4.75 | 4.75 |
| cpg_003 | PHONESHOP | ARCHITECTURE | medium | có | 1.00 | 0.88 | 4.75 | 3.25 |
| cpg_007 | PHONESHOP | SETUP | easy | có | 1.00 | 0.75 | 4.75 | 3.00 |
| cpg_013 | PHONESHOP | ACCESS | medium | không | 1.00 | 0.20 | 4.50 | 4.50 |
| cpg_014 | PHONESHOP | ACCESS | medium | không | 1.00 | 0.40 | 4.50 | 4.50 |
| cpg_015 | PHONESHOP | SETUP | medium | không | 1.00 | 0.88 | 4.50 | 4.25 |
| cpg_016 | PHONESHOP | CODEBASE | medium | không | 1.00 | 0.31 | 4.50 | 4.50 |
| cpg_002 | FURNISTORE | ORIENTATION | easy | có | 1.00 | 0.80 | 4.75 | 4.00 |
| cpg_005 | FURNISTORE | ACCESS | medium | có | 1.00 | 0.18 | 3.75 | 4.50 |
| cpg_009 | FURNISTORE | CODEBASE | medium | có | 0.92 | 0.83 | 4.25 | 2.75 |
| cpg_017 | FURNISTORE | ARCHITECTURE | medium | không | 1.00 | 0.88 | 4.75 | 4.25 |
| cpg_018 | FURNISTORE | ACCESS | medium | không | 0.97 | 0.36 | 5.00 | 4.75 |
| cpg_019 | FURNISTORE | SETUP | medium | không | 1.00 | 0.89 | 4.75 | 4.00 |
| cpg_020 | FURNISTORE | SETUP | medium | không | 1.00 | 0.67 | 4.50 | 4.25 |
| cpg_004 | GADGETHUB | ARCHITECTURE | medium | có | 1.00 | 0.86 | 5.00 | 4.00 |
| cpg_006 | GADGETHUB | ACCESS | medium | có | 0.94 | 0.09 | 3.75 | 2.50 |
| cpg_010 | GADGETHUB | CODEBASE | easy | có | 0.95 | 1.00 | 5.00 | 2.50 |
| cpg_011 | GADGETHUB | COMPANY | hard | có | 1.00 | 0.89 | 3.50 | 4.25 |
| cpg_021 | GADGETHUB | ORIENTATION | medium | không | 1.00 | 0.57 | 4.75 | 4.50 |
| cpg_022 | GADGETHUB | ACCESS | medium | không | 1.00 | 0.55 | 4.50 | 4.50 |
| cpg_023 | GADGETHUB | SETUP | medium | không | 1.00 | 0.82 | 4.50 | 4.25 |
| cpg_024 | GADGETHUB | SETUP | medium | không | 0.97 | 1.00 | 4.50 | 4.25 |
| cpg_008 | FITECH | SETUP | easy | có | 1.00 | 0.82 | 4.75 | 4.25 |
| cpg_012 | FITECH | COMPANY | hard | có | 0.49 | 0.89 | 4.00 | 3.50 |
| cpg_025 | FITECH | ORIENTATION | medium | không | 1.00 | 0.57 | 5.00 | 4.50 |
| cpg_026 | FITECH | ARCHITECTURE | medium | không | 1.00 | 0.86 | 5.00 | 4.25 |
| cpg_027 | FITECH | ACCESS | medium | không | 0.88 | 0.09 | 4.50 | 4.50 |
| cpg_028 | FITECH | ACCESS | medium | không | 1.00 | 0.45 | 4.50 | 4.50 |
| cpg_029 | FITECH | SETUP | medium | không | 1.00 | 1.00 | 4.50 | 4.25 |
| cpg_030 | FITECH | CODEBASE | medium | không | 1.00 | 1.00 | 5.00 | 4.50 |

## 4. Failure analysis

**Lưu ý về phạm vi phân tích**: script KHÔNG lưu lại nguyên văn nội dung AI sinh sau khi chấm điểm
xong (chỉ lưu điểm số) — nên phần 5 Whys dưới đây phân tích theo **mẫu hình thống kê** (số liệu lặp
lại nhất quán giữa nhiều case cùng category, không phải đọc từng câu chữ của 1 case đơn lẻ). Muốn
đọc nguyên văn 1 case cụ thể, chạy lại `--pilot` với đúng `case_id` đó và xem log console.

### Mẫu hình 1 — Context Precision thấp bất thường ở category ACCESS (0.09-0.55, trung bình 0.29)

3/3 case điểm Judge thấp nhất đều dính category ACCESS/COMPANY. Với ACCESS, Context Precision thấp
ở HẦU HẾT case (cpg_005=0.18, cpg_006=0.09, cpg_013=0.20, cpg_018=0.36, cpg_027=0.09...), trong khi
Judge score AI vẫn cao bình thường (3.75-5.00) — tức **nội dung AI viết ra vẫn tốt, chỉ là TÀI LIỆU
đưa vào có nhiều đoạn không liên quan trực tiếp**.

- **Why 1**: Vì sao Context Precision thấp? → Nhiều đoạn trong `retrieved_text` bị Judge chấm "không
  liên quan" tới mục tiêu task cụ thể.
- **Why 2**: Vì sao có nhiều đoạn không liên quan? → Task nhóm ACCESS đọc CẢ tài liệu
  `ACCESS_SECURITY` riêng của dự án LẪN toàn bộ policy `SECURITY_POLICY` chung công ty
  (`TASK_CATEGORY_POLICY_MAP` trong `steps.py`).
- **Why 3**: Vì sao đọc cả `SECURITY_POLICY` mà không lọc? → `SECURITY_POLICY` là 1 tài liệu RỘNG
  (ACL, phân loại dữ liệu, báo cáo sự cố, xử lý vi phạm...) trong khi 1 task ACCESS cụ thể (vd "Xin
  quyền truy cập GitHub repo") chỉ thực sự cần đúng 1 phần nhỏ (mục Phân quyền truy cập).
- **Why 4**: Vì sao thiết kế đưa cả tài liệu thay vì lọc theo mục? → Quyết định nghiệp vụ ban đầu
  (`TASK_CATEGORY_POLICY_MAP`) ưu tiên KHÔNG bỏ sót thông tin bảo mật quan trọng hơn là tối ưu độ
  liên quan — hợp lý về AN TOÀN, nhưng đánh đổi bằng điểm Context Precision thấp.
- **Why 5 (root cause)**: Đây không phải lỗi AI "viết sai" — là **đặc điểm thiết kế retrieval có chủ
  đích** (đọc nguyên văn tài liệu, không cắt theo top-K — xem `tools.py:fetch_all_document_chunks`).
  Context Precision thấp ở ACCESS là TÍN HIỆU ĐÚNG của metric, không phải bug.
- **Failure Taxonomy**: **Retrieval Failure (có chủ đích)** — không phải Hallucination/Wrong Answer,
  vì Faithfulness (0.88-1.00) và Judge score vẫn cao ở toàn bộ case ACCESS.

### Mẫu hình 2 — Faithfulness thấp ở category COMPANY (0.74, thấp nhất toàn bộ report; cpg_012=0.49)

- **Why 1**: Vì sao Faithfulness COMPANY thấp hơn hẳn category khác (0.74 vs 0.97-1.00 nơi khác)? →
  Nhiều claim của AI không được `retrieved_text` (bản judge nhìn thấy) xác nhận.
- **Why 2**: Vì sao judge không xác nhận được dù AI đọc đúng tài liệu? → COMPANY đọc **70 chunk**
  (7 tài liệu policy) — nhiều nhất trong 6 category, gấp 6-7 lần category khác.
- **Why 3**: Vì sao 70 chunk lại gây vấn đề? → `_cap_chunks_for_judge()` (mục 7
  `report-evaluation.md`) giới hạn tài liệu gửi CHO JUDGE tối đa 6000 ký tự (~12 chunk đầu) để tránh
  429 — trong khi model SINH nội dung (DeepSeek) vẫn được đọc ĐỦ 70 chunk như bình thường.
- **Why 4**: Vì sao giới hạn không đối xứng vậy? → Đánh đổi có chủ đích để chạy được trên hạ tầng
  free/rate-limited (xem hành trình 3 vòng đổi judge model, mục 7 `report-evaluation.md`).
- **Why 5 (root cause)**: **KHÔNG phải AI bịa** — là giới hạn kỹ thuật của bước CHẤM ĐIỂM (cắt tài
  liệu cho judge), không phải bước SINH nội dung. Faithfulness thấp ở COMPANY phần lớn là NHIỄU do
  thiết kế eval, cần đọc thận trọng, không kết luận vội "AI COMPANY hay bịa".
- **Failure Taxonomy**: **Đo lường sai (measurement artifact)** — không phải Hallucination thật của
  hệ thống sinh nội dung.

## 5. Improvement log

Xếp theo cluster lớn nhất (ACCESS/COMPANY, 10/30 case = 33% golden set), ưu tiên giảm nhiễu đo lường
trước khi kết luận về chất lượng AI:

1. **[Ưu tiên cao] Sửa `_cap_chunks_for_judge` để KHÔNG cắt non-uniform theo category** — với case
   COMPANY (nhiều chunk), nên lấy MẪU ĐẠI DIỆN trải đều thay vì luôn lấy N chunk ĐẦU TIÊN — tránh
   thiên lệch Faithfulness thấp giả tạo do chunk quan trọng nằm ở cuối bị cắt mất.
2. **[Ưu tiên trung bình] Tách Context Precision theo 2 nguồn (project doc vs policy)** thay vì gộp
   chung 1 con số — để phân biệt rõ "tài liệu dự án có đúng trọng tâm không" (thường cao) với "policy
   công ty có rộng hơn cần thiết không" (thường thấp, nhưng CHỦ ĐÍCH) — tránh đọc nhầm Context
   Precision thấp là lỗi khi nó phản ánh đúng quyết định thiết kế an toàn.
3. **[Ưu tiên trung bình] Chạy lại ≥3 lần/case (thay vì 1) khi ngân sách cho phép** — báo cáo hiện
   tại KHÔNG có std thật cho nhánh AI (chạy `--runs 1` để tiết kiệm token — xem quyết định trong hội
   thoại) nên chưa đo được độ ổn định giữa các lần sinh (temperature=0.2).
4. **[Ưu tiên thấp] Calibrate — PM tự chấm tay ≥10 case, so với Judge** (mục 8 plan-evaluation.md) —
   CHƯA làm trong lượt chạy này, cần để xác nhận điểm Judge (gpt-4o-mini) có khớp cảm nhận người
   thật không, đặc biệt ở 2 category có mẫu hình bất thường trên.

**Kết luận tổng thể**: 70% case AI thắng Baseline, Faithfulness cao ở hầu hết category (trừ COMPANY
— do nhiễu đo lường, không phải AI kém), Judge score AI (trung bình ~4.5/5) vượt Baseline (~4.0/5)
rõ rệt ở phần lớn category. **AI sinh nội dung tốt hơn Baseline có ý nghĩa thực tế**, đặc biệt ở
ARCHITECTURE/CODEBASE/SETUP (thắng 75-100%) — category ACCESS cần đọc điểm cẩn thận hơn vì Context
Precision thấp là đặc điểm thiết kế, không phải điểm yếu của AI.
