# TourBooking Service — First Task gợi ý cho engineer mới

## Mục đích
Trước khi động vào luồng `BookingService` (phần nhạy cảm nhất hệ thống, liên quan trực tiếp tới tiền và uy tín công ty), mọi engineer mới đều bắt đầu bằng 1-2 task nhỏ ở phần `tour` (chỉ đọc, ít rủi ro) để làm quen layering `Controller -> Service -> Repository` chuẩn Spring Boot, quy trình review PR, và pipeline CI/CD thật của team.

## Task khởi động #1: Thêm endpoint lọc tour theo khoảng giá

**Mục tiêu**: làm quen luồng `Controller -> Service -> Repository` chuẩn Spring Boot, không đụng logic giữ chỗ phức tạp.

**Các bước cụ thể**:
1. Đọc `TourController.java`, tìm endpoint `GET /api/tours`.
2. Thêm 2 query param `minPrice`, `maxPrice` (kiểu `BigDecimal`, optional, dùng `@RequestParam(required = false)`).
3. Cập nhật `TourService.searchTours(...)` truyền thêm điều kiện lọc giá xuống `TourRepository` (dùng JPA Specification, không viết `@Query` string thủ công để giữ khả năng compose điều kiện linh hoạt với các filter khác đã có sẵn như điểm đến, ngày khởi hành).
4. Viết test ở `TourControllerTest.java` (dùng `@WebMvcTest`, mock `TourService`) và `TourServiceTest.java` (dùng Mockito mock `TourRepository`) xác nhận lọc đúng khoảng giá, kể cả case chỉ có `minPrice` hoặc chỉ có `maxPrice`.
5. Cập nhật lại luôn cả filter tương ứng bên Elasticsearch (`TourSearchService`) nếu tính năng tìm kiếm chính đang dùng Elasticsearch thay vì query trực tiếp Postgres — hỏi Tech Lead nếu không chắc endpoint này dùng nguồn dữ liệu nào.
6. Tạo PR, gắn label `good-first-issue`, mã ticket Jira tương ứng (Tech Lead sẽ tạo sẵn ticket mẫu cho bạn).

Task này thường mất 0.5–1 ngày, giúp engineer mới quen cách viết query có điều kiện động trong JPA (Specification pattern) và cách team tổ chức test.

## Task khởi động #2 (sau khi hoàn thành task #1): Thêm endpoint xem chi tiết lịch khởi hành còn chỗ

**Mục tiêu**: làm quen việc đọc dữ liệu liên quan tới 2 entity có quan hệ (`Tour` và `TourDeparture`), và cách tránh N+1 query.

**Các bước gợi ý**:
1. Thêm endpoint `GET /api/tours/{tourId}/departures?onlyAvailable=true` trả về danh sách lịch khởi hành, có tuỳ chọn chỉ lấy lịch còn chỗ trống (`available_seats > 0`).
2. Dùng `@EntityGraph` hoặc `JOIN FETCH` để tránh N+1 query khi load kèm thông tin `Tour` cha (xem lưu ý về N+1 trong `codebase-guide.md`).
3. Viết integration test xác nhận số lượng query SQL thực thi đúng như dự kiến (dùng thư viện `db-util` team đã setup sẵn trong `pom.xml`).

## Sau 2 task khởi động
Sau khi hoàn thành, trao đổi với Tech Lead trong buổi 1-1 để nhận task nghiệp vụ thật — thường sẽ ở mảng `tour` hoặc `partner` trước, `booking`/`payment` chỉ giao sau khi bạn đã làm quen codebase ít nhất 2-3 tuần và được Tech Lead xác nhận đủ tự tin xử lý phần nhạy cảm nhất hệ thống.
