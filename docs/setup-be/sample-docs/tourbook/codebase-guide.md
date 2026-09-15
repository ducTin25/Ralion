# TourBooking Service — Codebase Guide

## Cấu trúc package đầy đủ
```
src/main/java/com/tourbook/
  ├── tour/
  │   ├── domain/
  │   │   ├── Tour.java, TourDeparture.java          # JPA entity
  │   │   └── TourSearchCriteria.java                  # value object cho tìm kiếm
  │   ├── TourController.java                            # REST controller
  │   ├── TourService.java                                 # business logic
  │   ├── TourRepository.java                                # Spring Data JPA repository
  │   └── TourSearchService.java                              # sync sang Elasticsearch qua Spring Event
  ├── booking/
  │   ├── domain/Booking.java
  │   ├── BookingController.java
  │   ├── BookingService.java                # logic giữ chỗ, confirm, cancel
  │   ├── BookingRepository.java
  │   └── ReservationLockService.java          # wrapper quanh Redisson distributed lock
  ├── partner/  (cấu trúc tương tự tour/)
  ├── payment/  (cấu trúc tương tự, thêm PaymentWebhookController riêng)
  └── common/
      ├── config/SecurityConfig.java, RedisConfig.java, KafkaConfig.java
      ├── exception/GlobalExceptionHandler.java   # @ControllerAdvice, map exception -> HTTP status chuẩn
      └── audit/AuditLogAspect.java                  # AOP, tự động log thao tác nhạy cảm (đổi giá, huỷ booking...)
```

## Nguyên tắc kiến trúc
Theo layering chuẩn Spring Boot: `Controller -> Service -> Repository`. Controller chỉ validate input (`@Valid` + Bean Validation annotation) và gọi Service, tuyệt đối không chứa business logic dưới bất kỳ hình thức nào, kể cả logic tưởng chừng đơn giản như "nếu số lượng khách > 10 thì áp dụng giá đoàn" — logic này phải nằm trong `TourPricingService`, không viết trực tiếp trong controller.

Mọi rule nghiệp vụ quan trọng (giữ chỗ 15 phút, kiểm tra overbooking, tính phí huỷ theo thời gian) nằm ở Service layer, được test kỹ bằng unit test với Mockito mock toàn bộ repository/external call.

## File quan trọng cần đọc trước khi code
- **`BookingService.java`** — trung tâm của toàn bộ luồng booking: logic giữ chỗ tạm, xác nhận thanh toán, và job giải phóng chỗ hết hạn. Đây là class có nhiều bài học sau sự cố double booking tháng 02/2025 — đọc kỹ Javadoc comment giải thích tại sao dùng Redisson lock thay vì `@Transactional` đơn thuần.
- **`TourSearchService.java`** — cách sync dữ liệu Tour sang Elasticsearch mỗi khi có thay đổi. Quan trọng: KHÔNG đồng bộ trực tiếp trong cùng transaction lưu Postgres (dùng Spring `@TransactionalEventListener(phase = AFTER_COMMIT)` để đảm bảo chỉ đồng bộ sau khi transaction Postgres đã commit thành công, tránh Elasticsearch có dữ liệu "ảo" nếu transaction Postgres rollback).
- **`ReservationLockService.java`** — wrapper an toàn quanh Redisson, có logic retry với timeout ngắn (500ms) nếu không lấy được lock ngay, tránh block thread quá lâu khi tải cao.
- **`GlobalExceptionHandler.java`** — mọi exception nghiệp vụ (`TourNotFoundException`, `InsufficientSeatsException`, `BookingExpiredException`...) đều map về đúng HTTP status code chuẩn qua đây, controller không tự bắt exception và trả response lỗi thủ công.

## Testing strategy
- **Unit test**: Mockito mock repository và external service, test riêng logic nghiệp vụ trong Service layer — không cần Spring context, chạy cực nhanh.
- **Integration test** (`@SpringBootTest` + Testcontainers): dựng Postgres + Redis thật, test full luồng từ Controller xuống Repository, đảm bảo wiring Spring đúng và query JPA hoạt động chính xác.
- **Contract test với Partner Portal frontend**: dùng Spring Cloud Contract, đảm bảo response API không đổi bất ngờ làm vỡ Partner Portal.

## Lưu ý N+1 query
Vì dùng JPA/Hibernate, rủi ro N+1 query luôn hiện hữu khi load `Tour` kèm danh sách `TourDeparture`. Team có quy định bắt buộc: mọi query load entity có quan hệ `@OneToMany` phải dùng `@EntityGraph` hoặc `JOIN FETCH` tường minh, không được để Hibernate tự động lazy-load trong vòng lặp. CI có 1 test riêng dùng thư viện `db-util` để đếm số query SQL thực thi trong mỗi integration test quan trọng, fail nếu vượt ngưỡng dự kiến — cách này đã bắt được nhiều N+1 query tiềm ẩn trước khi lên production.

## AOP cho Audit Log
Mọi thao tác nhạy cảm (đối tác đổi giá tour, admin huỷ booking thay khách, thay đổi trạng thái thanh toán thủ công) được tự động ghi audit log qua `AuditLogAspect` (Spring AOP, đánh dấu bằng annotation `@Auditable` trên method), không cần developer tự viết code ghi log thủ công ở từng nơi — giảm rủi ro quên ghi log cho action nhạy cảm mới thêm sau này.
