# PhoneShop API — Architecture

## Tổng quan kiến trúc
PhoneShop API được thiết kế theo kiến trúc **microservice**, tách theo domain nghiệp vụ (catalog, order, inventory, payment, notification), giao tiếp với nhau qua kết hợp **REST đồng bộ** (khi cần phản hồi ngay, ví dụ kiểm tra tồn kho lúc checkout) và **event bất đồng bộ qua RabbitMQ** (khi không cần chờ phản hồi ngay, ví dụ gửi email xác nhận). Quyết định tách service được đưa ra sau khi hệ thống monolith cũ (Rails, viết từ 2019) gặp giới hạn scale nghiêm trọng vào cuối 2023, không đáp ứng nổi tải flash sale.

## Tech stack đầy đủ
| Thành phần | Công nghệ | Ghi chú |
|---|---|---|
| Backend framework | Python 3.11, FastAPI | Async-first, tự sinh OpenAPI docs |
| ORM | SQLAlchemy 2.0 (async) + Alembic | Migration versioned, review bắt buộc trước khi apply production |
| Database chính | PostgreSQL 15 (AWS RDS Multi-AZ) | `db.r6g.xlarge`, read replica riêng cho báo cáo |
| Cache | Redis 7 (AWS ElastiCache) | Session, giỏ hàng tạm, rate limit counter, cache catalog phổ biến (TTL 5 phút) |
| Message queue | RabbitMQ 3.12 (self-host, EKS, cluster 3 node) | Quorum queue để đảm bảo không mất message khi 1 node chết |
| Search | Postgres GIN index (`products.search_vector`) | Chưa dùng Elasticsearch riêng — đủ tải ở quy mô hiện tại (~3.200 SKU) |
| Object storage | Cloudinary | Ảnh sản phẩm, tài liệu nội bộ |
| API Gateway | Kong | Rate limiting, auth middleware, request routing tới đúng service |
| Container orchestration | Kubernetes (AWS EKS) | Mỗi service 1 Deployment riêng, HPA theo CPU + custom metric (queue depth) |
| CI/CD | GitHub Actions + ArgoCD (GitOps) | Merge main → build image → ArgoCD tự sync lên staging, production cần approve thủ công |
| Observability | Datadog (APM + log + synthetic), Sentry (error), PagerDuty (on-call) | Dashboard riêng theo từng service |

## Sơ đồ luồng đặt hàng (chi tiết)
```
Client (Web/App/POS)
   |
   v
API Gateway (Kong) -- auth middleware, rate limit --> Order Service
   |
   |-- (đồng bộ, REST) --> Inventory Service: kiểm tra + giữ chỗ tồn kho (reservation TTL 10 phút)
   |-- (đồng bộ, REST) --> Payment Service: khởi tạo giao dịch thanh toán
   |
   v (sau khi thanh toán thành công, webhook callback)
Order Service --> publish "OrderConfirmed" event --> RabbitMQ
                                                         |
                    +------------------------------------+------------------------------+
                    v                                    v                              v
        Inventory Service                    Notification Service              Analytics Service
        (trừ tồn kho thật,                    (gửi email + SMS                  (ghi nhận sự kiện
         giải phóng reservation)                xác nhận đơn)                    cho báo cáo BI)
```

## Module chính và trách nhiệm
- **`catalog-service`**: quản lý sản phẩm, danh mục, thuộc tính kỹ thuật (RAM, dung lượng, màu sắc, bảo hành). Đồng bộ ảnh sản phẩm qua Cloudinary, cache danh sách sản phẩm phổ biến trong Redis để giảm tải Postgres.
- **`order-service`**: tạo đơn, tính giá (bao gồm áp mã giảm giá, tính phí trả góp nếu có), orchestrate toàn bộ luồng thanh toán, quản lý trạng thái đơn hàng (state machine: `PENDING -> CONFIRMED -> PACKING -> SHIPPING -> DELIVERED`, hoặc `CANCELLED`/`REFUNDED` ở bất kỳ bước nào trước `DELIVERED`).
- **`inventory-service`**: theo dõi tồn kho theo 35 chi nhánh + 2 kho trung tâm, xử lý đặt trước (reservation) khi khách thêm vào giỏ, đồng bộ 2 chiều với SAP ERP.
- **`payment-service`**: tích hợp cổng thanh toán (VNPay, Momo), 3 đối tác trả góp, xử lý webhook callback (idempotent qua `transaction_id` unique constraint, tránh xử lý trùng khi đối tác gửi lại webhook do timeout).
- **`notification-service`**: gửi email (SendGrid) + SMS (eSMS) xác nhận đơn, nhắc lịch thanh toán trả góp, thông báo thay đổi trạng thái giao hàng.

## Database schema (rút gọn, các bảng quan trọng nhất)
```sql
-- catalog-service
products(id, sku, name, category_id, price, attributes JSONB, search_vector TSVECTOR, created_at, updated_at)
categories(id, name, parent_id)

-- inventory-service
inventory(product_id, branch_id, quantity_available, quantity_reserved, updated_at)
reservations(id, product_id, branch_id, quantity, expires_at, order_id)

-- order-service
orders(id, customer_id, status, total_amount, payment_method, shipping_address JSONB, created_at)
order_items(order_id, product_id, quantity, unit_price, discount_amount)
promotions(id, code, discount_type, discount_value, valid_from, valid_to, usage_limit)

-- payment-service
transactions(id, order_id, provider, provider_transaction_id, status, amount, created_at)
installment_applications(id, order_id, partner, status, approved_amount, term_months)
```
Full schema và mối quan hệ chi tiết xem trong `catalog-service/migrations/`, `order-service/migrations/`, v.v. (mỗi service tự quản lý migration riêng — đúng nguyên tắc "database per service" của microservice).

## Quyết định thiết kế quan trọng và lý do
- **Microservice thay vì monolith**: catalog đọc nhiều (~95% traffic), inventory ghi nhiều lúc flash sale — tách riêng để scale độc lập theo tải thực tế, tránh 1 service nghẽn kéo cả hệ thống chậm theo. Đây là bài học rút ra từ hệ thống monolith Rails cũ, đã chính thức ngừng dùng từ đầu 2024 sau khi hoàn tất migration.
- **Reservation TTL 10 phút thay vì trừ kho ngay khi thêm giỏ**: cân bằng giữa trải nghiệm khách hàng (không mất hàng ngay khi vừa thêm vào giỏ, đủ thời gian cân nhắc) và tránh giữ chỗ vô thời hạn gây ra tình trạng "ảo" hết hàng khi khách bỏ giỏ hàng không mua. Con số 10 phút được A/B test và chọn dựa trên hành vi thực tế của khách hàng PhoneShop.
- **Không dùng saga pattern phức tạp cho luồng thanh toán**: với quy mô giao dịch hiện tại (dưới 10.000 đơn/ngày kể cả đỉnh điểm), orchestration đơn giản (Order Service gọi tuần tự các service khác, có compensate action rõ ràng khi 1 bước lỗi) đủ dùng và dễ debug hơn nhiều so với choreography-based saga đầy đủ. Sẽ đánh giá lại nếu quy mô tăng gấp 5-10 lần.
- **Database per service**: mỗi service có schema Postgres riêng (cùng 1 instance RDS nhưng khác database logic), tránh coupling chặt qua shared database — đổi lại phải chấp nhận một số dữ liệu bị denormalize nhẹ giữa các service (ví dụ `order-service` lưu snapshot giá sản phẩm tại thời điểm đặt hàng, không query ngược `catalog-service` mỗi lần cần).
- **Kong làm API Gateway thay vì tự viết middleware**: giảm thời gian phát triển, tận dụng plugin rate-limiting, JWT validation có sẵn, cộng đồng lớn hỗ trợ tốt.

## Dashboard & alerting
- Datadog dashboard chính: `PhoneShop / Production Overview` — theo dõi latency p50/p95/p99 theo từng service, error rate, queue depth RabbitMQ, connection pool Postgres.
- Dashboard riêng: `PhoneShop / Inventory Sync Health` — theo dõi độ trễ đồng bộ giữa các chi nhánh, số lượng reservation đang active, tỷ lệ reservation hết hạn không convert thành đơn (chỉ số quan trọng để tối ưu UX giỏ hàng).
- Alert quan trọng nhất: `order-service error rate > 2% trong 5 phút` → page on-call ngay qua PagerDuty, không chờ business hours. Các alert mức thấp hơn (warning) chỉ post vào Slack, không page.

## Chi phí hạ tầng (tham khảo, cập nhật hàng quý)
Chi phí AWS trung bình ~$8.500/tháng cho toàn bộ hạ tầng production (RDS, EKS, ElastiCache, S3/Cloudinary, data transfer), tăng khoảng 15-20% vào các tháng có flash sale lớn do auto-scaling. Team đang đánh giá Reserved Instance cho RDS để tối ưu chi phí cố định.
