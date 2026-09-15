# FurniStore — Codebase Guide

## Cấu trúc thư mục
```
src/
  modules/<tên-module>/
    <module>.controller.js     # nhận request, gọi service, trả response — không chứa business logic
    <module>.service.js          # business logic chính
    <module>.routes.js             # định nghĩa route + JSDoc comment (tự sinh Swagger)
    <module>.schema.js               # zod schema validate input
    <module>.repository.js             # wrapper quanh Prisma Client hoặc Mongoose model (chỉ có ở module cần thiết)
  shared/
    middlewares/
      error-handler.js          # xử lý lỗi tập trung
      auth.js                     # verify JWT, phân biệt token khách hàng vs Delivery App
    config/
      prisma-client.js
      mongo-connection.js
    jobs/
      shipping-fee-worker.js    # BullMQ worker, chạy process riêng (pnpm run worker)
```

## Nguyên tắc kiến trúc: module tự chứa (self-contained)
Mỗi module tự chứa toàn bộ: route, controller, service, schema validate đều nằm chung 1 thư mục theo tên module — **không** tách route/controller/service ra các thư mục cấp cao riêng biệt (khác với style MVC truyền thống nhiều dự án Express khác dùng). Lý do: giúp dễ tìm toàn bộ code liên quan tới 1 tính năng chỉ trong 1 thư mục, giảm thời gian "nhảy file" khi debug hoặc thêm tính năng — quan trọng với team nhỏ (5 người) cần tốc độ phát triển nhanh.

## File quan trọng cần đọc trước khi code
- **`modules/shipping/shipping.service.js`** — logic tính phí ship theo bảng giá tỉnh/thành (tính sơ bộ, đồng bộ) + trigger job BullMQ tính lại giá chính xác hơn. Đọc kỹ để hiểu 2 giai đoạn tính phí (sơ bộ vs chính xác) trước khi sửa bất cứ gì liên quan.
- **`shared/jobs/shipping-fee-worker.js`** — worker xử lý job BullMQ, có timeout cứng + circuit breaker sau sự cố tháng 04/2025 (xem `overview.md`). Bất kỳ code mới nào gọi API bên ngoài trong file này BẮT BUỘC phải wrap qua helper `callExternalApiWithTimeout()` có sẵn, không tự viết `fetch`/`axios` trực tiếp không có timeout.
- **`shared/middlewares/error-handler.js`** — cách xử lý lỗi tập trung, mọi lỗi nghiệp vụ nên throw `AppError` (class tự định nghĩa, có `statusCode` và `code` riêng) thay vì lỗi thường (`throw new Error(...)`) để middleware xử lý đúng status code và format response lỗi nhất quán cho toàn bộ API.
- **`modules/delivery/delivery.service.js`** — logic đồng bộ giữa Postgres (Order) và MongoDB (DeliverySchedule), bao gồm job quét bù trừ định kỳ (xem giải thích trong `architecture.md` mục "vì sao 2 database").

## Testing strategy
- Unit test (Jest): mock Prisma Client bằng `jest-mock-extended`, mock Mongoose model bằng `mongodb-memory-server` cho trường hợp cần test logic MongoDB thật mà không cần Atlas thật.
- Integration test: dùng Supertest gọi thẳng vào Express app, với Postgres/MongoDB/Redis thật chạy trong Docker (service container trong CI).
- Không có contract test riêng (khác PhoneShop/TourBook) — team nhỏ, chỉ có API cho Delivery App là "khách hàng nội bộ" duy nhất cần đảm bảo backward-compatible, quản lý qua việc luôn giữ endpoint cũ hoạt động thêm ít nhất 1 tháng sau khi có endpoint mới thay thế (không breaking change đột ngột).

## Quy ước đặt tên biến môi trường
Mọi biến môi trường bắt buộc được validate lúc khởi động qua `zod` schema trong `shared/config/env.js` — app sẽ **crash ngay lúc start** với thông báo rõ ràng nếu thiếu biến bắt buộc, thay vì chạy với giá trị `undefined` gây lỗi khó hiểu ở đâu đó sau này lúc runtime.
