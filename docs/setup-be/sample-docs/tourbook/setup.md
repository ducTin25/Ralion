# TourBooking Service — Setup môi trường dev

## Tổng quan
TourBooking Service là 1 Spring Boot application duy nhất (modular monolith), khác với PhoneShop là hệ nhiều microservice — nghĩa là setup đơn giản hơn nhiều, chỉ cần clone 1 repo và chạy.

## Yêu cầu hệ thống
- **JDK 21** (khuyến nghị dùng SDKMAN để quản lý version: `sdk install java 21-tem`).
- **Maven 3.9+** (dự án dùng Maven Wrapper `./mvnw`, không cần cài Maven riêng nếu không muốn).
- **Docker + Docker Compose**.
- **IntelliJ IDEA** (khuyến nghị, team dùng chung 1 bộ code style export sẵn trong `.idea/codeStyles/` — import vào IDE để tự động format đúng chuẩn).

## Các bước setup từ đầu
```bash
git clone git@github.com:company/tourbooking-service.git
cd tourbooking-service
cp application-example.yml src/main/resources/application-local.yml
# điền datasource.url, redis.host, elasticsearch.uris trong file vừa copy

docker compose up -d postgres redis elasticsearch kafka  # Kafka cần cho Debezium CDC

./mvnw flyway:migrate
./mvnw spring-boot:run -Dspring-boot.run.profiles=local
```

Lần đầu build Maven có thể mất 5-10 phút để tải toàn bộ dependency. Các lần sau nhanh hơn nhiều nhờ cache local (`~/.m2/repository`).

## Bật đồng bộ Elasticsearch (tuỳ chọn, chỉ cần nếu đang làm việc liên quan tìm kiếm)
```bash
docker compose up -d debezium-connector
curl -X POST http://localhost:8083/connectors -H "Content-Type: application/json" -d @debezium/postgres-connector-config.json
```
Nếu không cần test tính năng search, có thể bỏ qua bước này — các tính năng khác (booking, partner) không phụ thuộc Elasticsearch.

## Seed data mẫu
```bash
./mvnw exec:java -Dexec.mainClass="com.tourbook.tools.SeedDataRunner"
```
Tạo ~20 tour mẫu với nhiều điểm đến (Đà Nẵng, Phú Quốc, Sapa, Hạ Long...), mỗi tour có 3-5 lịch khởi hành trong 2 tháng tới, và 5 đối tác lữ hành demo.

## Kiểm tra chạy đúng
1. Mở `http://localhost:8080/swagger-ui.html` — thấy đủ nhóm API `tours`, `bookings`, `partners`.
2. Gọi `GET /actuator/health` phải trả `{"status":"UP"}` (Spring Boot Actuator, đã bật sẵn health indicator cho Postgres, Redis, Elasticsearch).
3. Gọi `GET /api/tours?destination=Đà Nẵng` phải trả về danh sách tour đã seed.
4. Thử luồng đặt chỗ đầy đủ: tạo booking → xác nhận giữ chỗ xuất hiện trong Redis (`redis-cli KEYS "booking:hold:*"`) → giả lập thanh toán thành công (endpoint test `/api/test/simulate-payment/{bookingId}`, chỉ có ở môi trường local/staging) → xác nhận `available_seats` giảm đúng.

## Chạy test
```bash
./mvnw test                              # unit test, chạy nhanh
./mvnw verify -Pintegration-test          # integration test, dùng Testcontainers tự dựng Postgres/Redis
./mvnw jacoco:report                       # coverage report, xem tại target/site/jacoco/index.html
```

## Lỗi thường gặp
| Lỗi | Nguyên nhân | Cách fix |
|---|---|---|
| `Connection to localhost:5432 refused` | Container `postgres` chưa healthy | `docker compose ps`, đợi container `healthy` |
| `FlywayException: Validate failed` | Có migration mới trên `main` chưa pull hoặc migration local bị sửa tay sau khi đã chạy | `git pull`, KHÔNG BAO GIỜ sửa file migration đã merge — luôn tạo migration mới |
| Elasticsearch connection timeout | Elasticsearch cần nhiều RAM hơn Docker Desktop mặc định cấp | Tăng RAM cho Docker Desktop lên tối thiểu 4GB trong Settings |
| IntelliJ báo lỗi "cannot resolve symbol" dù build Maven OK | IDE chưa reimport Maven project sau khi đổi `pom.xml` | Chuột phải `pom.xml` → Maven → Reload Project |
| Virtual Threads gây lỗi lạ với thư viện cũ | Một số thư viện dùng `ThreadLocal` không tương thích tốt với Virtual Threads | Đã ghi danh sách thư viện biết có vấn đề trong `docs/virtual-threads-caveats.md` nội bộ repo |

## CI/CD
Push lên nhánh bất kỳ → GitHub Actions chạy `./mvnw verify` (bao gồm unit + integration test) + Spotless check. Merge vào `main` → build Docker image, push ECR, AWS CodeDeploy triển khai blue/green lên staging tự động. Production cần approve thủ công, sau đó CodeDeploy chuyển traffic dần sang phiên bản mới (canary 10% → 50% → 100%, tự động rollback nếu error rate tăng bất thường trong quá trình chuyển).
