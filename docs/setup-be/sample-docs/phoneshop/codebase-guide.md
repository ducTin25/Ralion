# PhoneShop API — Codebase Guide

## Cấu trúc thư mục (mỗi service, ví dụ `order-service/`)
```
order-service/
├── app/
│   ├── api/              # FastAPI routers, 1 file/resource, chỉ validate input + gọi service, KHÔNG chứa business logic
│   │   ├── orders.py
│   │   ├── health.py
│   │   └── deps.py         # FastAPI dependencies dùng chung (get_db, get_current_user...)
│   ├── domain/             # entity + business logic thuần, KHÔNG import SQLAlchemy/FastAPI/bất cứ thư viện infra nào
│   │   ├── order.py          # Order aggregate, toàn bộ rule tính giá/trạng thái
│   │   ├── promotion.py
│   │   └── exceptions.py      # domain exception riêng, không dùng HTTPException ở đây
│   ├── infra/              # SQLAlchemy models, repository implementation, HTTP client gọi service khác
│   │   ├── models.py
│   │   ├── order_repository.py
│   │   └── inventory_client.py  # gọi inventory-service qua REST
│   ├── services/            # orchestration logic — use case, gọi domain + infra theo đúng thứ tự
│   │   ├── checkout_service.py
│   │   └── order_status_service.py
│   ├── events/               # publisher/consumer RabbitMQ
│   │   ├── publisher.py
│   │   └── consumers/
│   ├── config.py               # Pydantic Settings, đọc từ biến môi trường
│   └── main.py                  # FastAPI app entrypoint
├── tests/
│   ├── unit/                 # test domain logic, mock repository — chạy nhanh, không cần DB thật
│   ├── integration/           # test API thật, DB thật qua testcontainers — chạy trong CI
│   └── conftest.py
├── migrations/                # Alembic, versioned theo thời gian
├── pyproject.toml
└── README.md
```

## Nguyên tắc kiến trúc (Clean Architecture nhẹ)
Chiều phụ thuộc luôn đi từ ngoài vào trong: `api -> services -> domain <- infra`. `domain/` là lớp lõi, không phụ thuộc bất cứ framework hay thư viện I/O nào (không import SQLAlchemy, không import FastAPI) — điều này giúp business logic có thể test cực nhanh (không cần DB, không cần mock phức tạp) và có thể tái sử dụng nếu sau này đổi framework hoặc thêm interface khác (ví dụ CLI, gRPC).

Quy trình thêm tính năng mới, theo đúng thứ tự khuyến nghị:
1. Viết logic ở `domain/` trước (pure Python, không I/O). Ví dụ: thêm rule "đơn hàng trên 5 triệu được miễn phí ship" thì code rule này trong `domain/order.py`.
2. Viết test unit cho logic đó ngay lập tức (mock mọi dependency), đảm bảo rule đúng trước khi nối dây phần còn lại.
3. Nối dây ở `services/` — gọi domain + infra theo đúng thứ tự nghiệp vụ (ví dụ: kiểm tra tồn kho trước, sau đó mới tính giá, sau đó mới tạo giao dịch thanh toán).
4. Expose qua `api/` — router chỉ nhận request, validate bằng Pydantic schema, gọi service, trả response. Không viết logic nghiệp vụ trực tiếp trong router dưới bất kỳ hình thức nào, kể cả logic tưởng chừng đơn giản.

## File quan trọng cần đọc trước khi bắt đầu code
- **`app/domain/order.py`** — toàn bộ rule tính giá, áp mã giảm giá, tính phí trả góp nằm ở đây. Đây là file có test coverage cao nhất hệ thống (95%+) vì đây là logic nhạy cảm nhất, ảnh hưởng trực tiếp tới doanh thu nếu tính sai.
- **`app/infra/inventory_repository.py`** — cách xử lý race condition khi nhiều người mua cùng lúc 1 sản phẩm sắp hết hàng (dùng `SELECT ... FOR UPDATE` để khoá pessimistic). Đọc kỹ comment giải thích trong file trước khi sửa bất cứ điều gì liên quan — đã từng có sự cố production nghiêm trọng do một thay đổi tưởng chừng vô hại ở đây (xem `overview.md` mục "Sự cố đáng chú ý").
- **`app/events/consumers/inventory_consumer.py`** — consumer RabbitMQ xử lý event trừ tồn kho, có logic retry với exponential backoff + dead-letter-queue khi xử lý thất bại 3 lần liên tiếp, tránh mất message vĩnh viễn.
- **`app/services/checkout_service.py`** — orchestrate toàn bộ luồng checkout từ đầu đến cuối, đây là nơi tốt nhất để đọc trước tiên nhằm hiểu "bức tranh lớn" trước khi đi sâu vào chi tiết từng module riêng lẻ.
- **`app/config.py`** — toàn bộ config hệ thống đọc từ biến môi trường qua Pydantic Settings, có validation nghiêm ngặt lúc startup (app sẽ fail-fast nếu thiếu biến môi trường bắt buộc, không chạy với config sai âm thầm).

## Testing strategy
- **Unit test**: mock toàn bộ I/O (DB, Redis, RabbitMQ, HTTP client gọi service khác), toàn bộ suite chạy dưới 5 giây, chạy được ngay cả khi không có Docker.
- **Integration test**: dùng thư viện `testcontainers-python` để tự động dựng Postgres + Redis thật trong Docker cho mỗi lần chạy CI, đảm bảo test sát với môi trường thật nhất có thể, tránh tình trạng "test pass nhưng production lỗi" do khác biệt giữa mock và DB thật.
- **Contract test** (giữa các service): dùng Pact framework, đảm bảo `order-service` và `inventory-service` không vô tình phá vỡ hợp đồng API khi một bên thay đổi — chạy tự động trong CI của cả 2 repo, nếu contract không khớp thì build fail ngay, không phải chờ tới khi deploy mới phát hiện.
- **Load test**: chạy định kỳ trước mỗi đợt flash sale lớn bằng k6, mô phỏng tải gấp 1.5-2 lần dự kiến để đảm bảo hệ thống chịu được, kết quả lưu lại để so sánh xu hướng theo thời gian.

## Feature flag
Tính năng mới có rủi ro cao hoặc thay đổi logic nhạy cảm (ví dụ: đổi thuật toán tính phí trả góp, đổi logic reservation) nên bọc qua feature flag (LaunchDarkly), bật dần theo phần trăm traffic (thường bắt đầu 5% → 25% → 50% → 100% qua vài ngày, theo dõi metric liên tục) thay vì release toàn bộ 1 lần cho tất cả người dùng. Cách làm này đã áp dụng thành công cho lần đổi logic reservation tháng 3/2025 sau sự cố race condition, giúp phát hiện sớm vấn đề còn sót ở mức 5% traffic thay vì ảnh hưởng toàn bộ khách hàng.
