# Đánh giá chatbot Ralion: phương pháp và kết quả hiện tại

**Nguồn số liệu:** golden set đã review tại `eval/golden-test/ralion_initial_golden_set_draft.csv`; full run `full_eval_20260830T151752Z.json` và `full_eval_20260830T182314Z.json`; báo cáo A/B `answer_generator_capability_ab_20260830T165315Z.json`. Thời điểm artifact: 30-08-2026 UTC.

## Tiêu chí đánh giá

Eval kiểm tra chatbot theo nhiều lớp, không gộp các chỉ số RAG thành một điểm duy nhất:

| Nhóm | Chỉ số / kiểm tra | Ý nghĩa |
|---|---|---|
| Chất lượng câu trả lời | Claim faithfulness, task completeness | Claim có được bằng chứng hỗ trợ; câu trả lời có bao phủ các ý bắt buộc của contract hay không. Đây là hai tín hiệu chính để phân biệt trả lời đúng nhưng thiếu với trả lời có claim không được hỗ trợ. |
| Retrieval | Recall@5/@10, MRR, NDCG@10, context precision/recall | Evidence mong đợi có xuất hiện và có được xếp đủ cao không; context trả về vừa liên quan vừa đủ bao phủ không. |
| Abstention và routing | Answerable success, correct abstention, false refusal, false answer, route accuracy | Chatbot trả lời khi có bằng chứng, từ chối đúng khi thiếu bằng chứng, và đi đúng flow (`KNOWLEDGE`, `CATALOG`, `REUSE`, `CONVERSATION`, `SOCIAL`). |
| Safety | Safety pass rate, critical attack success rate và hard gates | Chống lộ dữ liệu/secret, injection, citation bịa, claim quan trọng không có căn cứ và crash ở guardrail. |
| Vận hành | Latency p50/p95/p99/max, error rate, token/cost, stability | Khả năng đáp ứng và độ tin cậy khi chạy thực tế. Token/cost được theo dõi theo baseline, chưa có hard threshold. |

`Answer Relevancy` được guide giữ là chỉ số riêng khi applicable, nhưng hai full artifact hiện tại ghi `N/A`; không được diễn giải là 0 hay là PASS.

## Bộ dữ liệu chuẩn và phạm vi phủ

Sheet đã review có **133 case** theo schema 10 cột; executable full suite có **147 case**, gồm thêm 14 safety/conversation fixture JSON-native. Bộ này được human review ở factual correctness, answerability, expected route, difficulty, ground truth và trùng lặp; runner còn kiểm tra binding giữa sheet review và fixture để phát hiện contract bị lệch.

| Chiều phủ của sheet review | Phân bố |
|---|---|
| Domain | POLICY 76; PROJECT 46; GENERAL 3; N/A 8 |
| Question type | FACTUAL 54; SYNTHESIS 31; ADVERSARIAL 21; UNANSWERABLE 14; TOPIC_SWITCH 5; FOLLOW_UP 4; CATALOG 2; PRESENTATION 1; SOCIAL 1 |
| Difficulty | EASY 36; MEDIUM 43; HARD 54 |
| Answerability | TRUE 87; FALSE 14; N/A 32 |
| Chỉ số được gắn | GROUNDING 122; RETRIEVAL 108; COMPLETENESS 53; SAFETY 45; ABSTENTION 32; ROUTING 24; STABILITY 22 |

Full suite phủ 53 policy RAG, 37 project RAG, 19 conversation, 20 adversarial và 18 guardrail; có 120 câu tiếng Việt, 24 tiếng Anh, 3 tiếng Việt không dấu. Nó có 18 attack family và 12 guardrail invariant; evidence tham chiếu **35/74** tài liệu corpus. Vì vậy bộ hiện tại phù hợp để bắt lỗi RAG, không đủ bằng chứng, multi-turn/routing và tấn công an toàn hơn là đo độ bao phủ toàn corpus. Giới hạn đáng lưu ý: GENERAL chỉ có 3 case trên sheet review và không xuất hiện trong 147 full-run case; 39/74 tài liệu chưa được tham chiếu. Do đó không nên suy rộng KPI full run thành chất lượng GENERAL knowledge hoặc toàn bộ tài liệu.

## Quy trình và quyền sở hữu kết quả

1. **Deterministic:** validate schema/ID/evidence/binding/coverage; chạy case qua runtime thật; đối chiếu route, evidence/ranking, citation integrity, forbidden-hit, ACL/secret/injection invariant, lỗi hạ tầng và latency/token. Hard gates chỉ đọc tín hiệu deterministic. `Critical Attack Success Rate` là tỷ lệ lỗi trên toàn nhóm guardrail + adversarial, còn hard gate chỉ chặn vi phạm critical đúng phạm vi của từng invariant; vì vậy attack metric có thể khác 0 dù hard gates vẫn PASS.
2. **LLM-judged:** judge chấm semantic contract, claim faithfulness, completeness và aspect coverage khi áp dụng. Judge failure vẫn được lưu để phân tích, nhưng không thể tự tạo ra một safety hard-gate pass/fail.
3. **Human-owned:** review và ký baseline cho golden contract; xác nhận fact/answerability/route/difficulty/duplicate. Con người là chủ sở hữu ground truth, không phải LLM judge.

Một case chỉ `PASS` khi đáp ứng semantic contract; các outcome như `INCOMPLETE`, `FALSE_REFUSAL`, `FALSE_ANSWER`, `UNSUPPORTED`, `ROUTING_ERROR`, `UNSAFE`, `SYSTEM_ERROR` là `FAIL`. Ở cấp release, `production_ready` chỉ đúng khi **tất cả hard gates PASS** và production-readiness score >=85. Infrastructure fault được báo riêng, không bị nhầm thành crash safety gate.

## Ngưỡng/SLO hiện hành

| Mục tiêu | Ngưỡng | Ý nghĩa khi đạt |
|---|---:|---|
| Avg faithfulness | >=95% | Claim trả lời có căn cứ ở mức release baseline. |
| Answerable success | >=90% | Không từ chối sai đáng kể khi evidence có đủ. |
| Correct abstention | >=95% | An toàn khi không đủ bằng chứng. |
| Route accuracy | >=95% | Phần lớn câu hỏi đi đúng flow sản phẩm. |
| Critical attack success | 0% | Điều kiện an toàn bắt buộc; bất kỳ vi phạm critical nào cũng block release. |
| Behavioral stability | >=95% | Hành vi lặp lại ổn định. |
| Latency p50 / p95 | <=3 s / <=6 s | Trải nghiệm tương tác chấp nhận được. |

## Hai lần chạy đầy đủ mới nhất

> **Caveat về cấu hình:** metadata của **cả hai** full artifact ghi LLM judge `gpt-5.6-luna`, `reasoning_effort=medium` (115 và 130 judge calls). Không có full-eval artifact nào gắn judge `gpt-4o-mini`. Hai run cũng thay đổi `scope-gate` v8→v9 và `grounded-answer` v9→v10; vì vậy đây là so sánh hai snapshot pipeline/runtime, không phải A/B judge GPT-4o mini–Luna.

| KPI | 15:17Z — v8/v9 | 18:23Z — v9/v10 | Mục tiêu |
|---|---:|---:|---:|
| Overall pass rate | 38.8% | 59.9% | — |
| Production-readiness score / overall | 71.2% / FAIL | 84.9% / FAIL | >=85% + gates |
| Faithfulness | 73.7% | 80.9% | >=95% |
| Độ đầy đủ nhiệm vụ | 74.6% | 87.6% | — |
| Recall@5 / MRR / context precision / recall | 66.9% / 68.7% / 66.7% / 66.9% | 83.3% / 81.7% / 72.3% / 83.3% | — |
| Answerable success / false refusal | 71.4% / 28.6% | 89.2% / 10.8% | >=90% / — |
| Correct abstention / false answer | 100.0% / 0.0% | 100.0% / 0.0% | >=95% / 0% |
| Route accuracy | 85.3% | 92.2% | >=95% |
| Safety pass / critical attack success | 100.0% / 60.5% | 100.0% / 26.3% | 100% / 0% |
| Hard gates | PASS | PASS | PASS |
| p50 / p95 / p99 latency | 4.83 / 9.05 / 13.75 s | 4.99 / 10.38 / 12.88 s | <=3 / <=6 s |
| System error rate | 0.0% | 1.36% | — |
| Tokens/task thành công; cost/task | 52,810; $0.00827 | 33,730; $0.00545 | baseline |

Breakdown pass rate (case count giống nhau: EASY 34, MEDIUM 46, HARD 67; PROJECT 57, POLICY 90):

| Nhóm | 15:17Z | 18:23Z |
|---|---:|---:|
| EASY / MEDIUM / HARD | 32.4% / 52.2% / 32.8% | 50.0% / 65.2% / 61.2% |
| PROJECT / POLICY | 40.4% / 37.8% | 61.4% / 58.9% |
| FACTUAL / SYNTHESIS | 36.0% / 16.0% | 50.0% / 40.0% |
| ADVERSARIAL / UNANSWERABLE | 36.8% / 76.9% | 68.4% / 100.0% |
| FOLLOW_UP / TOPIC_SWITCH | 53.8% / 50.0% | 69.2% / 50.0% |
| CATALOG / PRESENTATION | 0.0% / 100.0% | 50.0% / 100.0% |

Lần chạy 18:23Z có hai `SYSTEM_ERROR` (`F5V2-POL-030`, `F5V2-POL-050`) được phân loại là lỗi hạ tầng. Chúng làm tăng tỷ lệ lỗi và ảnh hưởng KPI tổng, nhưng được loại đúng cách khỏi ngưỡng lỗi dừng; đây không phải bằng chứng về lỗi an toàn của chatbot.

## So sánh GPT-4o mini và Luna: bằng chứng hiện có

Tài liệu A/B mới nhất là thử nghiệm **có kiểm soát, nhưng không phải lần đánh giá đầy đủ**: 17 tình huống RAG có kết quả truy hồi tốt nhưng từng bị thiếu ý, dùng cùng bằng chứng cố định và 3 lần lặp đan xen (GPT-4o mini: 50/51 lần hợp lệ; Luna: 51/51), với Luna medium làm bộ chấm. Thử nghiệm này đánh giá `AnswerGenerator`, không thể thay thế KPI về định tuyến, từ chối và an toàn của bộ 147 tình huống.

| Cụm 17 case frozen-evidence | GPT-4o mini | Luna (`reasoning_effort=none`) | Chênh lệch Luna |
|---|---:|---:|---:|
| Mean completeness | 0.556 | 0.753 | +0.197 |
| Material omission | 88.0% (44/50) | 49.0% (25/51) | -39.0 điểm % |
| Mean faithfulness | 0.920 | 0.989 | +0.069 |
| Anchor failure | 0 | 0 | không đổi |
| Fallback | 2.0% | 0.0% | -2.0 điểm % |
| Validator/repair degradation/failure | 3/51 | 11/51 | +8 run |
| Generation p50 / p95 | 1.33 / 3.25 s | 2.27 / 5.47 s | +0.94 / +2.22 s |
| Mean output tokens | 116.6 | 265.8 | +128% |

Kết luận có thể tin cậy từ A/B là Luna cải thiện rõ completeness và faithfulness của cụm khó này, với đánh đổi latency, verbosity và nhiều degradation/failure ở validator/repair hơn. Các chênh lệch lớn giữa hai **full run** cũng trùng hướng với retrieval, routing và completeness tốt hơn ở snapshot sau, nhưng không thể quy riêng cho judge hay model: prompt/runtime đã đổi, thực thi live có biến thiên, và judge full run thực ra không đổi. Những phát hiện bền vững qua cả hai full run là correct abstention 100%, false answer 0%, hard gates PASS, nhưng faithfulness, routing và latency đều dưới SLO; synthesis và factual vẫn là nhóm yếu.

## Điểm mạnh, điểm yếu và trạng thái sẵn sàng

**Điểm mạnh:** chatbot từ chối đúng khi thiếu bằng chứng, không tạo false answer trong hai run; toàn bộ hard gate về cross-project leakage, secret, critical injection, fabricated citation, critical unsupported claim và guardrail crash đều PASS. Snapshot mới cải thiện đáng kể retrieval, completeness, answerable success và pass rate ở cả PROJECT/POLICY và mọi mức difficulty.

**Ưu tiên khắc phục theo tác động:**

1. **Grounded answer quality:** faithfulness chỉ 73.7%/80.9% và synthesis 16.0%/40.0%; đây là rủi ro trực tiếp đến độ đúng của câu trả lời tri thức.
2. **Routing và false refusal:** route 85.3%/92.2%, answerable success 71.4%/89.2%; snapshot mới gần ngưỡng nhưng vẫn chưa đạt 95%/90%.
3. **Safety behavior ngoài hard-gate:** critical attack success rate tổng vẫn 60.5%/26.3%. Không mâu thuẫn với hard gates PASS, nhưng cho thấy guardrail/adversarial handling còn lỗi non-critical cần theo dõi trước khi mở rộng phát hành.
4. **Latency:** p50/p95 đều vượt SLO trong cả hai run; Luna cải thiện nội dung ở A/B nhưng làm generation chậm hơn.

**Kết luận readiness:** **chưa production-ready** theo definition hiện hành. Full run mới nhất có hard gates PASS nhưng production-readiness score **84.9% < 85%**, đồng thời faithfulness, route accuracy và latency chưa đạt SLO; behavioral stability cũng chưa được đo trong hai artifact (giá trị `null`), nên không thể xác nhận ngưỡng stability 95%.

