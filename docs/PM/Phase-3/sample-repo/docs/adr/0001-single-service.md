# ADR 0001: Giữ 1 service duy nhất thay vì tách nhỏ thành nhiều phần

## Bối cảnh

Nhóm cân nhắc giữa việc giữ nguyên toàn bộ nghiệp vụ trong 1 tiến trình duy nhất, hay tách thành
nhiều phần riêng biệt giao tiếp với nhau qua mạng ngay từ đầu.

## Quyết định

Giữ nguyên 1 tiến trình duy nhất. Phần nhận request, phần xử lý nghiệp vụ và phần lưu trữ dữ liệu
vẫn nằm chung 1 chỗ, gọi hàm trực tiếp với nhau trong cùng bộ nhớ, không qua hàng đợi hay gọi mạng
nội bộ nào cả.

## Lý do

- Nhóm còn nhỏ, khối lượng request thấp — tách sớm chỉ tốn thêm công vận hành mà chưa mang lại lợi
  ích rõ ràng.
- Mọi thứ chạy chung 1 tiến trình nên dễ triển khai, dễ theo dõi log, dễ dò lỗi khi có sự cố.
- Có thể tách phần nào đó ra riêng sau này, khi thực sự cần mở rộng độc lập phần đó.

## Hệ quả

Không dùng hàng đợi message, không cần cơ chế tự dò tìm dịch vụ giữa các phần. Khi cần tách sau
này, phải định nghĩa lại ranh giới giữa các phần cho thật rõ ràng trước khi tách, tránh phụ thuộc
chồng chéo.

## Trạng thái

Đã áp dụng, chưa có kế hoạch xem lại.
