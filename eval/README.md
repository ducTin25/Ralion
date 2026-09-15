# eval/

Toàn bộ tài sản đánh giá chất lượng AI của repo (chatbot F5 + rule mining F6): golden test
dataset, script chạy eval (harness), và báo cáo kết quả. Trước đây nằm rải rác ở
`eval_suite/` (gốc repo) + `golden-test/` (gốc repo); đã gộp về `eval/` trong lần dọn dẹp này.

**Chưa chạy live lần nào với API/DB thật** (xem mục "run_mode" bên dưới) — mọi
threshold/assertion cần được review trước khi dùng làm CI gate chính thức.

---

## 1. File nào phục vụ domain nào — chatbot (F5) vs rule mining (F6)

Domain được tách theo **thư mục con cấp 1**, không trộn lẫn:

| Thư mục | Domain | Phục vụ | Input thật lấy từ đâu |
| --- | --- | --- | --- |
| `eval/project_knowledge/` | **F5 — RAG chatbot** | Trả lời câu hỏi có citation trên tài liệu project đã ingest | `raw-data/thanos-io_project-knowledge/` (snapshot thật từ `thanos-io/thanos`, xem Phase 8b) |
| `eval/rule_mining/` | **F6 — LLM rule extraction** | Trích xuất `rule_text_draft`/`rationale`/`evidence_type` từ PR comment | `golden-test/f6_eval_fixture.json` gốc (Phase 4) → đã chuyển vào `eval/golden-test/f6_eval_fixture.json` |

Mỗi domain lại chia thành đúng 3 loại eval giống nhau (song song, không trộn):

```
eval/{project_knowledge,rule_mining}/
├── ragas/             # faithfulness / hallucination-avoidance
├── guardrails/         # LLM safety & behavior (KHÁC nghĩa với "guardrail" của F6 mining — xem mục 4)
└── prompt_injection/   # injection nhúng trong nội dung được xử lý bởi LLM
```

`eval/shared/` (`schemas.py`, `report_format.py`) — code Python dùng chung cho cả 6 harness,
không thuộc riêng domain nào, **không phải là 1 eval type thứ ba**.

`eval/golden-test/`, `eval/results/`, và `eval/test_golden_set_f5.py` — không thuộc riêng 1 domain
theo nghĩa Phase 9 (`test_golden_set_f5.py` là F5 chat nhưng domain POLICY, không phải PROJECT —
xem mục 2 và mục 3).

---

## 2. Golden test (dataset) vs script chạy (harness) vs báo cáo kết quả (report)

### 2.1 Golden test / dataset — dữ liệu case, KHÔNG có logic chạy

| File | Domain | Eval type | Số case | Nguồn gốc |
| --- | --- | --- | --- | --- |
| `project_knowledge/ragas/golden_dataset.jsonl` | F5 | ragas | 20 (12 answerable / 8 unanswerable) | Viết mới, trích dẫn thật từ `raw-data/thanos-io_project-knowledge/` |
| `project_knowledge/guardrails/test_cases.jsonl` | F5 | guardrails | 12 (4 violation_type × 3) | Viết mới |
| `project_knowledge/prompt_injection/test_cases.jsonl` | F5 | prompt_injection | 6 (3 injection_location) | Viết mới, `source_file` trỏ file thật, `fixture_copy` là bản sao đã chèn injection |
| `rule_mining/ragas/golden_dataset.jsonl` | F6 | ragas | 25 | Transform trực tiếp từ `eval/golden-test/f6_eval_fixture.json` (Phase 4), không viết mới |
| `rule_mining/guardrails/test_cases.jsonl` | F6 | guardrails | 12 (3 violation_type × 4) | Viết mới |
| `rule_mining/prompt_injection/test_cases.jsonl` | F6 | prompt_injection | 6 | Port + mở rộng từ `tests/test_modules/test_f6_injection_fixture.py` (Phase 8, gốc chỉ có 3 variant) |

Đi kèm dataset của `project_knowledge/prompt_injection/` là
`fixture_copies/*.md` — **bản sao** của file thật trong `raw-data/` đã chèn thêm 1 dòng injection
để test. File gốc trong `raw-data/` không bao giờ bị sửa; harness tự kiểm tra điều này ở mỗi lần
chạy (case fail nếu injected text lọt vào bản gốc).

`eval/golden-test/` — dataset **gốc**, không phải sản phẩm của Phase 9, được các dataset ở trên
tham chiếu/transform từ đó (không sửa):
- `golden_test_f5_70_samples.json` — golden set gốc cho F5 domain POLICY (70 case), dùng bởi
  `eval/test_golden_set_f5.py` (xem mục 3).
- `golden_test_50_samples.json` — golden set gốc khác (F5, kiểm tra thêm nếu cần dùng).
- `f6_eval_fixture.json` — fixture gốc F6 (Phase 4), nguồn của `rule_mining/ragas/golden_dataset.jsonl`.
- `f6_eval_fixture_measurement_report.json`, `f6_mining_pipeline_fixture_report.json` — báo cáo đo
  đạc có sẵn từ Phase 4, không phải output của harness trong `eval/`.

### 2.2 Script chạy (harness) — logic, không chứa case

Mỗi cặp domain × eval-type có đúng 1 `harness.py`, tổng cộng 6 file, tất cả theo cùng 1 khuôn:

```
python eval/<domain>/<eval_type>/harness.py            # --dry-run mặc định
python eval/<domain>/<eval_type>/harness.py --live      # xem bảng dưới
```

| Harness | `--dry-run` (mặc định) làm gì | `--live` làm gì |
| --- | --- | --- |
| `project_knowledge/ragas/harness.py` | Kiểm tra `expected_citations` trỏ đúng file thật trong `raw-data/` | `NotImplementedError` — cần wiring `ChatService.ask()` thật |
| `project_knowledge/guardrails/harness.py` | Kiểm tra schema case + `violation_type` hợp lệ | `NotImplementedError` — cần `ChatService.ask()` + LLM-judge |
| `project_knowledge/prompt_injection/harness.py` | Kiểm tra `fixture_copy` chứa injection, bản gốc `raw-data/` sạch | `NotImplementedError` — cần ingest fixture vào project throwaway rồi gọi chat |
| `rule_mining/ragas/harness.py` | Kiểm tra `context_for_ragas` không rỗng, cảnh báo nếu fixture Phase 4 bị thiếu | `NotImplementedError` — cần `extract_rule_candidate()` + RAGAS thật |
| `rule_mining/guardrails/harness.py` | Kiểm tra schema case + `violation_type` hợp lệ | `NotImplementedError` — cần `extract_rule_candidate()` thật |
| `rule_mining/prompt_injection/harness.py` | Kiểm tra schema case | **Chạy thật** — dùng stub LLM in-process (không mạng, không DB), gọi thẳng `extract_rule_candidate()`, y hệt logic `tests/test_modules/test_f6_injection_fixture.py` |

`--dry-run` không bao giờ gọi LLM/DB thật — chỉ validate cấu trúc dataset (field bắt buộc, giá trị
enum, đường dẫn file có tồn tại trên đĩa) rồi báo mỗi case là `skipped`.

### 2.3 Báo cáo kết quả (report) — output, được sinh ra mỗi lần chạy harness

Mỗi harness ghi `report.json` ngay cạnh nó, theo đúng 1 shape dùng chung định nghĩa ở
`eval/shared/report_format.py`:

```json
{"domain": "...", "eval_type": "...", "run_mode": "dry_run|live",
 "total_cases": 0, "results": [{"case_id": "...", "status": "pass|fail|skipped", "detail": "...", "score": null}],
 "summary": {"pass": 0, "fail": 0, "skipped": 0}}
```

`report.json` **không được commit** (đã thêm `eval/**/report.json` vào `.gitignore`) — đây là
build artifact, sinh lại được bất cứ lúc nào bằng cách chạy harness, không phải nguồn sự thật.

`eval/results/report.md` là 1 thứ khác hẳn: template báo cáo tổng hợp thủ công (metrics/demo/user
feedback) theo tiêu chí BTC, không phải output tự động của bất kỳ harness nào ở trên và không do
Phase 9 tạo ra — điền tay khi cần nộp báo cáo.

---

## 3. `tests/evals/` → đã chuyển thành `eval/test_golden_set_f5.py`

Ban đầu tôi đề xuất giữ nguyên trong `tests/` vì lý do CI (xem lịch sử bên dưới), nhưng theo yêu
cầu tường minh sau đó là chuyển vào `eval/` cho đồng bộ, đã thực hiện:

- File chuyển từ `tests/evals/test_golden_set_f5.py` → **`eval/test_golden_set_f5.py`** (đặt
  thẳng ở gốc `eval/`, không có subdirectory riêng — nó không thuộc domain `project_knowledge`
  hay `rule_mining` theo nghĩa Phase 9 (đây là golden set cho domain POLICY của F5 chat, không
  phải domain PROJECT), và không đặt tên thư mục `eval/tests/` để tránh trùng tên package Python
  với `tests/` gốc (`tests/__init__.py` đã tồn tại — nếu tạo thêm `eval/tests/__init__.py`, pytest
  ở chế độ import mặc định (`prepend`, không có `--import-mode=importlib` trong `pytest.ini`) sẽ
  coi 2 thư mục vật lý khác nhau là cùng 1 package `tests`, gây lỗi collection). File cũng bỏ
  `__init__.py` (không cần, không có file trùng tên `test_golden_set_f5.py` nào khác trong repo).
- `REPO_ROOT = Path(__file__).resolve().parents[N]` phải đổi từ `parents[2]` (khi còn ở
  `tests/evals/`, sâu 2 cấp) thành `parents[1]` (ở `eval/`, sâu 1 cấp) — quên bước này ban đầu làm
  `GOLDEN_PATH` trỏ sai hẳn ra ngoài repo (`E:\eval\...` thay vì `E:\P-040\eval\...`); đã phát hiện
  và sửa qua `pytest -v` thật, không suy đoán.
- `pytest.ini`: `testpaths = tests PM-test` → thêm `eval` (`testpaths = tests PM-test eval`) để
  `pytest` (không tham số) ở máy local vẫn tự động thấy file này.
- **CI KHÔNG được cập nhật theo yêu cầu tường minh của bạn** — `.github/workflows/ci.yml` và
  `release.yml` vẫn chạy đúng `pytest tests/ -v --tb=short` (không quét `eval/`), nên
  `eval/test_golden_set_f5.py` **sẽ không chạy trong CI** kể từ bây giờ, dù chạy pass 16/16 khi
  gọi trực tiếp (`pytest eval/test_golden_set_f5.py -v` hoặc `pytest` không tham số ở local). Đây
  là đánh đổi đã được xác nhận, không phải sơ suất — nếu sau này muốn CI phủ lại file này, chỉ cần
  sửa 2 dòng lệnh đó thành `pytest tests/ eval/ -v --tb=short`.
- `src/ai/evaluation/README.md` (quy ước "fixtures belong in `tests/evals`") và
  `eval/shared/schemas.py` (docstring trỏ `tests/evals/test_golden_set_f5.py`) đã cập nhật theo
  vị trí mới. Metadata tự mô tả bên trong chính `golden_test_f5_70_samples.json`
  (`evidence_rule`, `harness_status`) cũng đã cập nhật 2 chỗ trỏ tới path cũ.
- Đã verify bằng `pytest eval/test_golden_set_f5.py -v` (16/16 pass) và
  `pytest eval/ --collect-only -q` (16 test collected, không lỗi/không trùng tên package với
  `tests/`).

## 4. Cảnh báo thuật ngữ — "guardrail" mang 2 nghĩa khác nhau

- `*/guardrails/` trong `eval/` = kiểm tra an toàn hành vi LLM (chặn output có hại, lộ system
  prompt, bị chiếm quyền role).
- "guardrail" trong `F6_RULE_MINING_PLAN.md` = gate chất lượng dữ liệu ≥2-evidence trong
  `rule_mining_worker.py`. Khái niệm hoàn toàn khác, trùng từ tiếng Anh — không được nhầm lẫn.

## 5. Việc đã sửa trong 2 lần dọn dẹp (`eval_suite/`→`eval/` rồi `tests/evals/`→`eval/`)

Khi rà lại sau khi `eval_suite/` → `eval/` và `golden-test/` → `eval/golden-test/` được chuyển
thủ công, phát hiện và đã sửa các chỗ tham chiếu đường dẫn cũ bị gãy:

- `shared/` bị chuyển nhầm vào `docs/shared/` thay vì `eval/shared/` → đã chuyển lại đúng chỗ, sửa
  cả 6 dòng `import` trong `harness.py` từ `docs.shared.*` → `eval.shared.*`.
- `rule_mining/ragas/harness.py` còn trỏ `golden-test/f6_eval_fixture.json` (đường cũ, gốc repo) →
  sửa thành `eval/golden-test/f6_eval_fixture.json`.
- `project_knowledge/prompt_injection/test_cases.jsonl`: 6 field `fixture_copy` còn trỏ
  `eval_suite/...` (đường cũ) → sửa thành `eval/...`.
- `tests/evals/test_golden_set_f5.py` (trước khi được chuyển hẳn vào `eval/`, xem mục 3) từng bị
  gãy vì cùng lý do: hardcode `golden-test/golden_test_f5_70_samples.json` (đường gốc repo, không
  tiền tố `eval/`) — đã sửa trước khi chuyển tiếp file này vào `eval/`.

Đã chạy dry-run cả 6 harness trong `eval/` sau mỗi lần sửa — tất cả pass cấu trúc (0 fail), và đã
chạy thử `--live` cho `rule_mining/prompt_injection` (6/6 pass, không cần mạng/DB) và
`pytest eval/test_golden_set_f5.py -v` (16/16 pass) để xác nhận việc chuyển thư mục không phá
logic.
