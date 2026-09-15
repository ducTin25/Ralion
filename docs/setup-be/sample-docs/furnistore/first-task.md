# FurniStore — First Task gợi ý cho engineer mới

## Mục đích
Team nhỏ (5 người) nên engineer mới thường được giao việc thật khá sớm, nhưng vẫn bắt đầu bằng 1 task nhỏ ở module `catalog` (ít rủi ro nhất) để làm quen cấu trúc module tự chứa và quy trình PR trước khi động vào `shipping`/`delivery` (2 phần đã từng có sự cố, xem `overview.md`).

## Task khởi động #1: Thêm filter theo khoảng giá cho API danh sách sản phẩm

**Mục tiêu**: làm quen cấu trúc module tự chứa (`controller -> service -> Prisma`), không đụng vào logic tính phí ship phức tạp.

**Các bước cụ thể**:
1. Đọc `modules/catalog/catalog.routes.js`, tìm route `GET /api/products`.
2. Thêm query param `minPrice`, `maxPrice` vào `catalog.schema.js` (zod schema) — chú ý dùng `z.coerce.number()` vì query param luôn là string, cần coerce sang number.
3. Cập nhật `catalog.service.js` truyền điều kiện lọc giá vào Prisma `where` clause (dùng object spread có điều kiện, tránh viết nhiều nhánh `if` lặp lại — xem ví dụ pattern có sẵn trong hàm `buildProductFilter()` cùng file).
4. Viết test ở `catalog.service.test.js` xác nhận lọc đúng, kể cả case chỉ có 1 trong 2 giá trị min/max.
5. Cập nhật JSDoc comment trên route để Swagger tự sinh docs đúng cho param mới.
6. Tạo PR, gắn label `good-first-issue`.

Task này thường mất 0.5–1 ngày, giúp engineer mới quen cách viết schema validate + query Prisma có điều kiện động.

## Task khởi động #2 (sau khi hoàn thành task #1): Thêm endpoint xem lịch sử đơn hàng của khách

**Mục tiêu**: làm quen middleware auth (`shared/middlewares/auth.js`) và cách phân biệt token khách hàng vs token Delivery App.

**Các bước gợi ý**:
1. Thêm endpoint `GET /api/customers/me/orders` trong module `order`, yêu cầu JWT khách hàng hợp lệ (không chấp nhận token Delivery App — kiểm tra bằng field `type` trong JWT payload).
2. Chỉ trả về đơn hàng thuộc về đúng khách đang đăng nhập.
3. Viết test xác nhận: (a) không có token → 401, (b) token Delivery App gọi vào → 403 (sai loại token), (c) token khách hàng đúng → trả đúng dữ liệu, (d) không xem được đơn của khách khác dù biết `orderId`.

## Sau 2 task khởi động
Trao đổi với Tech Lead để nhận task nghiệp vụ thật — với team nhỏ, khả năng cao bạn sẽ được giao việc ở nhiều module khác nhau khá sớm thay vì chỉ chuyên 1 mảng như 2 dự án lớn hơn, đây cũng là điểm nhiều engineer thích khi làm ở team FurniStore.
