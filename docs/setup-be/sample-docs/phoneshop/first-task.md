# PhoneShop API — First Task gợi ý cho engineer mới

## Mục đích của giai đoạn First Task
Trước khi giao bất kỳ task nghiệp vụ phức tạp nào, mọi engineer mới tại PhoneShop đều bắt đầu bằng 1-2 task nhỏ, rủi ro thấp nhưng đi qua đầy đủ luồng `api -> service -> domain -> infra` để làm quen codebase thật, quy trình review PR thật, và pipeline CI/CD thật — thay vì chỉ đọc tài liệu suông. Mục tiêu không phải tốc độ mà là hiểu đúng cách hệ thống vận hành trước khi động vào logic quan trọng như tính giá hay tồn kho.

## Task khởi động #1: Thêm filter tồn kho > 0 vào API tìm kiếm sản phẩm

**Mục tiêu**: giúp bạn làm quen luồng `api -> service -> repository` mà không cần đụng vào logic phức tạp (thanh toán, tồn kho race condition).

**Các bước cụ thể**:
1. Đọc `app/api/catalog_router.py` (trong `catalog-service`), tìm endpoint `GET /products`.
2. Thêm query param mới `in_stock_only: bool = False` vào Pydantic schema request.
3. Khi `True`, filter thêm điều kiện `stock_quantity > 0` ở tầng `app/infra/product_repository.py` — chú ý đây là query join với bảng `inventory` từ `inventory-service` qua replicated view, không phải join trực tiếp cross-database.
4. Viết 1 test integration ở `tests/integration/test_catalog.py` xác nhận filter hoạt động đúng với ít nhất 2 case: có sản phẩm hết hàng bị loại ra, sản phẩm còn hàng vẫn hiển thị.
5. Cập nhật OpenAPI description cho param mới (dùng `Query(..., description="...")` trong FastAPI).
6. Tạo PR, gắn label `good-first-issue`, tag Tech Lead review.

Task này thường mất 0.5–1 ngày cho engineer mới, đủ để làm quen codebase mà không rủi ro phá vỡ tính năng quan trọng đang chạy production.

## Task khởi động #2 (sau khi hoàn thành task #1): Thêm endpoint lấy lịch sử đơn hàng của khách hàng

**Mục tiêu**: làm quen với authentication/authorization (JWT), và cách một service gọi sang service khác.

**Các bước gợi ý**:
1. Thêm endpoint `GET /api/v1/customers/me/orders` trong `order-service`, yêu cầu JWT hợp lệ (dùng dependency `get_current_user` có sẵn trong `app/api/deps.py`).
2. Chỉ trả về đơn hàng thuộc về chính user đang đăng nhập (không cho phép xem đơn của người khác qua đổi ID — đây là lỗi bảo mật kinh điển IDOR, cần đặc biệt cẩn thận).
3. Hỗ trợ phân trang (`page`, `page_size`), mặc định sắp xếp theo `created_at DESC`.
4. Viết test đảm bảo user A không thể xem được đơn hàng của user B dù biết order ID (test case bảo mật quan trọng, sẽ được review kỹ).

## Sau 2 task khởi động
Sau khi hoàn thành cả 2 task trên và được Tech Lead xác nhận đã hiểu rõ luồng code, bạn sẽ được giao task nghiệp vụ thật theo sprint hiện tại của team, thường liên quan tới 1 trong các mảng: catalog, checkout flow, hoặc notification — tuỳ theo capacity và định hướng phát triển của bạn đã trao đổi với Tech Lead trong buổi 1-1 đầu tiên.
