# Bằng chứng đánh giá Ralion — Báo cáo tóm tắt

> Sản phẩm bàn giao #10. Phương pháp và phần diễn giải chi tiết được trình bày
> trong [`RALION_CHATBOT_EVALUATION_REPORT.md`](RALION_CHATBOT_EVALUATION_REPORT.md).

## Phạm vi và phương pháp

Bản đánh giá phát hành sử dụng bộ dữ liệu chuẩn đã được rà soát gồm **147 tình
huống**, bao phủ tri thức `PROJECT` và `POLICY`, câu hỏi có/không có đủ bằng
chứng, câu hỏi tiếp nối, chuyển chủ đề, tổng hợp, định tuyến, guardrail và đầu
vào đối kháng.

Mỗi lần chạy kết hợp kiểm tra có tính xác định với đánh giá chất lượng ngữ nghĩa
bằng LLM. Các kiểm tra có tính xác định quyết định những ngưỡng bắt buộc khi
phát hành, gồm rò rỉ chéo dự án, rò rỉ bí mật, trích dẫn giả, tuyên bố nghiêm
trọng không có bằng chứng và lỗi dừng chương trình. Bộ chấm đo độ trung thực và
độ đầy đủ của câu trả lời nhưng không thể ghi đè một ngưỡng bắt buộc bị trượt.

## Kết quả lần chạy đầy đủ mới nhất

Tài liệu nguồn: [`full_eval_20260830T182314Z.md`](full_eval_20260830T182314Z.md)

| Chỉ số | Kết quả | Mục tiêu | Trạng thái |
|---|---:|---:|:---:|
| Tỷ lệ đạt tổng thể | 59.9% | Tham khảo | — |
| Độ trung thực trung bình | 80.9% | ≥95.0% | KHÔNG ĐẠT |
| Độ chính xác ngữ cảnh | 72.3% | Tham khảo | — |
| Khả năng thu hồi ngữ cảnh | 83.3% | Tham khảo | — |
| Từ chối đúng khi thiếu bằng chứng | 100.0% | ≥95.0% | ĐẠT |
| Tỷ lệ trả lời sai | 0.0% | 0.0% | ĐẠT |
| Độ chính xác định tuyến | 92.2% | ≥95.0% | KHÔNG ĐẠT |
| Tỷ lệ đạt kiểm tra an toàn | 100.0% | 100.0% | ĐẠT |
| Tỷ lệ tấn công nghiêm trọng thành công | 26.3% | 0.0% | KHÔNG ĐẠT |
| Độ trễ p50 / p95 | 4.99s / 10.38s | ≤3.0s / ≤6.0s | KHÔNG ĐẠT |

Lần chạy mới nhất vượt qua cả sáu ngưỡng an toàn bắt buộc:

- không rò rỉ dữ liệu chéo dự án;
- không rò rỉ bí mật;
- không có tấn công injection nghiêm trọng thành công theo định nghĩa ngưỡng bắt buộc;
- không có trích dẫn giả;
- không có tuyên bố nghiêm trọng thiếu bằng chứng;
- không có lỗi dừng guardrail.

Chỉ số tấn công nghiêm trọng tổng quát vẫn có thể lớn hơn 0 dù các ngưỡng bắt
buộc đều đạt, vì chỉ số này bao phủ nhiều dạng thất bại đối kháng hơn nhóm điều
kiện chặn phát hành. Khác biệt này là có chủ đích và được giải thích trong báo
cáo chi tiết.

## Mức cải thiện giữa hai lần chạy đầy đủ

| Chỉ số | Lần chạy 15:17 UTC | Lần chạy 18:23 UTC | Thay đổi |
|---|---:|---:|---:|
| Tỷ lệ đạt tổng thể | 38.8% | 59.9% | +21.1 điểm % |
| Độ trung thực | 73.7% | 80.9% | +7.2 điểm % |
| Khả năng thu hồi ngữ cảnh | 66.9% | 83.3% | +16.4 điểm % |
| Tỷ lệ từ chối sai | 28.6% | 10.8% | −17.8 điểm % |
| Độ chính xác định tuyến | 85.3% | 92.2% | +6.9 điểm % |
| Tỷ lệ tấn công nghiêm trọng thành công | 60.5% | 26.3% | −34.2 điểm % |

Hai lần chạy có thể dùng để so sánh xu hướng nhưng không phải phép thử A/B chỉ
thay đổi model, vì prompt và hành vi runtime cũng thay đổi. Thử nghiệm A/B có
kiểm soát cho `AnswerGenerator` được lưu trong một tài liệu riêng.

## Thử nghiệm A/B có kiểm soát cho AnswerGenerator

[`answer_generator_capability_ab_20260830T165315Z.md`](answer_generator_capability_ab_20260830T165315Z.md)
so sánh GPT-4o mini với Luna trên một nhóm tình huống dùng bằng chứng cố định.
Luna cải thiện độ đầy đủ trung bình từ 0.556 lên 0.753 và độ trung thực từ 0.920
lên 0.989, nhưng có độ trễ và độ dài đầu ra cao hơn, đồng thời làm giảm hiệu quả
của bước kiểm tra/sửa câu trả lời.

## Tài liệu có thể tái lập

- Lần chạy 1: [tóm tắt](full_eval_20260830T151752Z_Summary.md),
  [báo cáo](full_eval_20260830T151752Z.md),
  [JSON](full_eval_20260830T151752Z.json),
  [CSV theo từng tình huống](full_eval_20260830T151752Z_Eval_Runs.csv).
- Lần chạy 2: [tóm tắt](full_eval_20260830T182314Z_Summary.md),
  [báo cáo](full_eval_20260830T182314Z.md),
  [JSON](full_eval_20260830T182314Z.json),
  [CSV theo từng tình huống](full_eval_20260830T182314Z_Eval_Runs.csv).
- Bộ dữ liệu chuẩn và định tuyến công cụ chạy: [`../README.md`](../README.md).

## Kết luận mức độ sẵn sàng

**Theo định nghĩa hiện tại, Ralion chưa sẵn sàng cho môi trường production.**
Các ngưỡng an toàn bắt buộc đều đạt, nhưng độ trung thực, độ chính xác định
tuyến và độ trễ vẫn dưới SLO; hai lần chạy đầy đủ được nộp chưa đo độ ổn định
hành vi. Bộ bằng chứng phù hợp để đánh giá minh bạch tại Demo Day và ưu tiên
công việc cho vòng cải thiện tiếp theo.
