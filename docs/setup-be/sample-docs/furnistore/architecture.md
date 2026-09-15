# FurniStore — Architecture

## Tổng quan kiến trúc
FurniStore dùng kiến trúc **modular monolith** (giống TourBook, khác PhoneShop) nhưng với 1 điểm đặc biệt: dùng **2 database khác loại** (PostgreSQL + MongoDB) trong cùng 1 application — quyết định xuất phát từ đặc thù dữ liệu lịch giao hàng/lắp đặt có cấu trúc thay đổi liên tục theo nhu cầu vận hành thực tế (khác hẳn dữ liệu đơn hàng/catalog cần tính toàn vẹn quan hệ chặt).

## Tech stack đầy đủ
| Thành phần | Công nghệ | Ghi chú |
|---|---|---|
| Backend framework | Node.js 20 (LTS), Express 4 | Team đang đánh giá migrate dần sang Fastify cho các endpoint mới do hiệu năng tốt hơn, chưa quyết định migrate toàn bộ |
| ORM/ODM | Prisma (Postgres), Mongoose (MongoDB) | Prisma dùng cho catalog/order/cart, Mongoose cho delivery scheduling |
| Database quan hệ | PostgreSQL 15 (Render managed database) | Đơn hàng, catalog, tồn kho theo showroom |
| Database phi quan hệ | MongoDB Atlas (M10 tier) | Lịch giao hàng/lắp đặt, log thao tác của đội giao hàng qua Delivery App |
| Cache/Queue | Redis (Render managed) + BullMQ | Cache session, giỏ hàng tạm; BullMQ xử lý tính phí ship bất đồng bộ |
| Deploy | Docker, Render | Chọn Render thay vì AWS để giảm chi phí vận hành ở giai đoạn team nhỏ, chưa cần độ phức tạp của AWS |
| Observability | Better Stack (log + uptime monitoring), Sentry (error tracking) | Bộ công cụ nhẹ hơn 2 dự án kia, phù hợp quy mô team 5 người |

## Module chính (theo thư mục)
```
src/
  modules/
    catalog/           # product, category — Prisma models
    cart/
    order/
    shipping/            # tính phí ship, đặt lịch giao hàng ban đầu (trigger job BullMQ)
    delivery/              # theo dõi trạng thái giao hàng chi tiết, MongoDB models, API cho Delivery App
    showroom/                # quản lý 12 showroom, tồn kho theo showroom (chuẩn bị cho tích hợp Q4/2025)
  shared/
    middlewares/
      error-handler.js
      auth.js
    config/
      prisma-client.js
      mongo-connection.js
    jobs/
      shipping-fee-worker.js   # BullMQ worker
```

## Luồng tính phí giao hàng — chi tiết kỹ thuật
1. Khách checkout → `shipping` module tính phí **sơ bộ ngay lập tức** (đồng bộ) dựa trên bảng giá tỉnh/thành + tổng khối lượng ước tính từ catalog — đủ nhanh để hiển thị cho khách trước khi đặt hàng.
2. Sau khi đặt hàng, nếu đơn có từ 2 sản phẩm lớn trở lên (tủ, giường, sofa) → hệ thống đẩy job vào BullMQ để **tính lại phí chính xác hơn** (gọi API đối tác vận chuyển thật, tính khối lượng thể tích chính xác thay vì ước tính).
3. Job chạy trong vài phút, nếu giá cuối khác giá sơ bộ quá 10% → gửi email báo khách xác nhận lại trước khi xử lý tiếp (khách có thể huỷ đơn miễn phí nếu không đồng ý giá mới).
4. **Bài học từ sự cố tháng 04/2025**: mọi HTTP call ra đối tác bên ngoài trong job đều có timeout cứng 10 giây + retry tối đa 3 lần với exponential backoff + circuit breaker (dùng thư viện `opossum`) để tự động ngắt gọi tạm thời nếu đối tác đang lỗi liên tục, tránh làm nghẽn toàn bộ queue.

```
Checkout -> tính phí sơ bộ (sync, bảng giá tĩnh) -> hiển thị khách -> Đặt hàng
                                                                          |
                                          (nếu đơn có sản phẩm lớn)      v
                                                                  BullMQ Queue
                                                                          |
                                                          shipping-fee-worker.js
                                                          (gọi API đối tác, timeout 10s,
                                                           circuit breaker, retry 3 lần)
                                                                          |
                                              +---------------------------+---------------------------+
                                              v                                                       v
                                  (giá không đổi nhiều)                                  (giá đổi > 10%)
                                  cập nhật đơn, không cần báo khách                       gửi email xác nhận lại
```

## Vì sao 2 database (Postgres + MongoDB)
Lịch giao hàng/lắp đặt có đặc thù: cấu trúc dữ liệu thay đổi thường xuyên theo yêu cầu vận hành thực tế (ví dụ: thêm field "yêu cầu đặc biệt của khách", "ảnh xác nhận lắp đặt", "đánh giá của đội giao hàng về khó khăn khi lắp đặt"...) — mỗi thay đổi này nếu dùng Postgres sẽ cần migration, gây chậm trễ khi đội vận hành cần thêm field mới gấp. MongoDB (schema-less) phù hợp hơn nhiều cho phần này. Ngược lại, đơn hàng/catalog cần tính toàn vẹn quan hệ chặt (không được có `order_item` trỏ tới `product` không tồn tại) — Postgres phù hợp hơn.

Đánh đổi: phải chấp nhận không có transaction xuyên suốt giữa 2 database (nếu tạo `Order` ở Postgres thành công nhưng tạo `DeliverySchedule` tương ứng ở MongoDB thất bại, cần cơ chế bù trừ riêng — hiện xử lý bằng cách: `delivery` module có job quét định kỳ mỗi 5 phút tìm đơn hàng đã `CONFIRMED` ở Postgres nhưng chưa có lịch giao hàng tương ứng ở MongoDB, tự động tạo bù).

## Quyết định thiết kế quan trọng
- **Render thay vì AWS**: team 5 người, không có DevOps chuyên trách — Render giảm đáng kể gánh nặng vận hành hạ tầng (managed database, auto-deploy từ Git, ít config hơn AWS) dù chi phí/instance cao hơn AWS một chút ở cùng cấu hình.
- **BullMQ (Redis-backed) thay vì RabbitMQ/Kafka**: khối lượng job không lớn (vài trăm job/ngày), BullMQ đơn giản hơn nhiều để vận hành và đã có sẵn Redis dùng cho cache, không cần thêm hạ tầng message queue riêng.
- **Prisma cho Postgres**: type-safe query, migration tự động sinh từ schema, phù hợp team quen TypeScript hơn viết raw SQL hoặc dùng ORM nặng hơn như TypeORM.

## Dashboard & alerting
- Better Stack dashboard: theo dõi uptime từng endpoint quan trọng (`/health`, `/api/checkout`), response time.
- Sentry: alert ngay khi có exception mới chưa từng thấy (không phải lỗi đã biết và đang track riêng), đặc biệt theo dõi sát `shipping-fee-worker.js` sau sự cố tháng 04/2025.
- Alert MongoDB: theo dõi qua Atlas built-in alerting, cảnh báo khi replica set có vấn đề (bài học từ sự cố tháng 06/2025).
