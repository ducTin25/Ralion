# TourBooking Service — Architecture

## Tổng quan kiến trúc
TourBooking Service được xây dựng theo kiến trúc **modular monolith** (không phải microservice như PhoneShop) — quyết định có chủ đích dựa trên quy mô team (8 kỹ sư backend) và độ phức tạp nghiệp vụ ở giai đoạn hiện tại. Toàn bộ ứng dụng là 1 Spring Boot application duy nhất nhưng tổ chức code theo package rõ ràng theo domain (`tour`, `booking`, `partner`, `payment`), giữ khả năng tách thành microservice riêng trong tương lai nếu cần scale độc lập từng phần.

## Tech stack đầy đủ
| Thành phần | Công nghệ | Ghi chú |
|---|---|---|
| Backend framework | Java 21, Spring Boot 3.2 | Dùng Virtual Threads (Project Loom) cho I/O-bound endpoint, giảm đáng kể thread pool overhead |
| ORM | Spring Data JPA + Hibernate 6 | Flyway quản lý migration, không dùng `ddl-auto` ở bất kỳ môi trường nào kể cả dev |
| Database chính | PostgreSQL 15 (AWS RDS Multi-AZ) | `db.r6g.large`, có read replica riêng cho Partner Portal (đọc nhiều, ghi ít) |
| Search | Elasticsearch 8.x (AWS OpenSearch) | Tìm kiếm tour theo điểm đến/giá/ngày, đồng bộ qua Debezium CDC từ Postgres (không đồng bộ thủ công) |
| Cache | Redis 7 (AWS ElastiCache) | Cache kết quả tìm kiếm tour phổ biến (TTL 2 phút), distributed lock cho luồng giữ chỗ |
| Deploy | Docker, AWS ECS Fargate | Không dùng Kubernetes — team đánh giá ECS đủ dùng và ít vận hành hơn cho quy mô hiện tại |
| Observability | New Relic (APM), CloudWatch (log + alarm), Opsgenie (on-call) | |
| CI/CD | GitHub Actions + AWS CodeDeploy | Blue/green deployment, tự động rollback nếu health check fail sau deploy |

## Module chính (theo package, tất cả nằm trong 1 Spring Boot application)
```
com.tourbook
  ├── tour/          # entity Tour, TourDeparture, quản lý lịch khởi hành, tích hợp Elasticsearch
  ├── booking/        # BookingService, xử lý đặt chỗ, giữ chỗ tạm qua Redis distributed lock
  ├── partner/         # quản lý đối tác lữ hành, Partner Portal API, xác thực riêng cho đối tác
  ├── payment/          # tích hợp cổng thanh toán, xử lý webhook, logic hoàn tiền theo chính sách huỷ
  ├── notification/      # gửi email xác nhận, nhắc lịch khởi hành trước 3 ngày
  └── common/              # config, exception handler, security filter, audit logging
```

## Luồng đặt chỗ (booking) — chi tiết kỹ thuật
1. Khách chọn tour + lịch khởi hành → hệ thống kiểm tra số chỗ còn lại (query Postgres, có cache Redis TTL ngắn 10 giây để giảm tải trong giờ cao điểm).
2. Nếu còn chỗ → hệ thống **giữ chỗ tạm 15 phút** bằng Redis distributed lock (dùng thư viện Redisson, đảm bảo atomic operation, tránh race condition khi nhiều request cùng lúc tranh chỗ cuối cùng — đây chính là fix cho sự cố double booking tháng 02/2025).
3. Khách thanh toán trong 15 phút → webhook từ cổng thanh toán xác nhận → giữ chỗ chuyển thành `CONFIRMED`, trừ số chỗ thật trong Postgres (transaction).
4. Hết 15 phút chưa thanh toán → Redis key tự hết hạn (TTL), job định kỳ (Spring `@Scheduled`, chạy mỗi phút) quét và giải phóng chỗ đã hết hạn giữ, đồng thời publish event cập nhật lại cache số chỗ còn lại.

```
Client -> BookingController -> BookingService
                                    |
                                    v
                    Redisson distributed lock (giữ chỗ 15 phút)
                                    |
                    +---------------+---------------+
                    v                               v
        (thanh toán thành công)          (hết 15 phút, chưa thanh toán)
        BookingService.confirm()          ScheduledReleaseJob.release()
        -> Postgres transaction            -> giải phóng Redis key
        -> trừ chỗ thật                     -> cập nhật cache
```

## Database schema (rút gọn)
```sql
tours(id, partner_id, name, destination, description, base_price, created_at)
tour_departures(id, tour_id, departure_date, total_seats, available_seats, price_override)
bookings(id, customer_id, departure_id, num_travelers, status, total_amount, created_at)
partners(id, company_name, contact_email, commission_rate, status)
payment_transactions(id, booking_id, provider, provider_ref, status, amount)
```

## Đồng bộ Elasticsearch
Dùng **Debezium** (Change Data Capture) đọc trực tiếp từ Postgres WAL (write-ahead log), publish thay đổi qua Kafka, consumer riêng cập nhật Elasticsearch index. Cách tiếp cận này (thay vì đồng bộ trực tiếp trong code nghiệp vụ) đảm bảo Elasticsearch luôn nhất quán với Postgres kể cả khi có thay đổi dữ liệu không qua đường API thông thường (ví dụ sửa trực tiếp qua script vận hành khẩn cấp), và tách biệt hoàn toàn concern "đồng bộ search index" khỏi luồng nghiệp vụ chính — bài học rút ra sau sự cố Elasticsearch tháng 4/2025 khi cách đồng bộ đồng bộ trực tiếp trong code cũ gây coupling và khó debug.

## Quyết định thiết kế quan trọng
- **Modular monolith thay vì microservice**: với team 8 người và độ phức tạp nghiệp vụ hiện tại, chi phí vận hành nhiều service (network, observability, deployment riêng biệt) lớn hơn lợi ích. Ranh giới module rõ ràng theo package giữ khả năng tách ra sau này nếu cần — đã có 1 buổi kiến trúc riêng thảo luận và quyết định điều này vào đầu dự án, ghi lại trong ADR (Architecture Decision Record) `ADR-001`.
- **Redis distributed lock cho giữ chỗ, không dùng database lock đơn thuần**: database lock (`SELECT FOR UPDATE`) từng được dùng ban đầu nhưng gây nghẽn connection pool khi tải cao vì giữ transaction mở lâu; chuyển sang Redis lock giúp giải phóng connection Postgres ngay, chỉ mở transaction ngắn khi thực sự confirm booking.
- **ECS Fargate thay vì Kubernetes**: đội DevOps chỉ có 1 người phụ trách hạ tầng cho service này, Kubernetes đòi hỏi kiến thức vận hành sâu hơn đáng kể so với lợi ích mang lại ở quy mô hiện tại.

## Dashboard & alerting
- New Relic dashboard chính: `TourBook / Production Overview` — theo dõi response time theo endpoint, error rate, database connection pool usage.
- Alert quan trọng nhất: `Elasticsearch cluster status != green` → page on-call ngay (bài học từ sự cố tháng 4/2025, trước đó không có alert riêng cho việc này).
- Alert `booking confirmation rate < 95% trong 10 phút` → cảnh báo có thể đang xảy ra vấn đề ở luồng thanh toán hoặc webhook.
