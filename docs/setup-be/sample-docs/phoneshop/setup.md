# PhoneShop API — Setup môi trường dev

## Tổng quan môi trường
Hệ thống PhoneShop gồm 5 service backend độc lập (`catalog-service`, `order-service`, `inventory-service`, `payment-service`, `notification-service`), mỗi service là 1 repo riêng trên GitHub, nhưng đều dùng chung 1 bộ công cụ dev tiêu chuẩn để đảm bảo trải nghiệm nhất quán. Tài liệu này hướng dẫn setup cho `order-service` — service trung tâm và phức tạp nhất, các service khác setup tương tự (xem README riêng từng repo).

## Yêu cầu hệ thống
- **OS**: macOS, Linux, hoặc Windows với WSL2 (khuyến nghị mạnh — Docker trên Windows native chậm hơn đáng kể).
- **Python 3.11+** (dùng `pyenv` để quản lý version nếu máy có nhiều dự án Python khác version).
- **Docker + Docker Compose v2** (Docker Desktop hoặc Colima trên macOS).
- **Poetry** (quản lý dependency) — cài qua `pipx install poetry`, không dùng `pip install poetry` trực tiếp để tránh xung đột.
- **AWS CLI** đã config với credential được cấp (để pull secret từ SSM Parameter Store khi cần test tích hợp thật với các dịch vụ AWS).
- **direnv** (khuyến nghị, không bắt buộc) — tự động load biến môi trường khi `cd` vào thư mục project.

## Các bước setup từ đầu
```bash
git clone git@github.com:company/phoneshop-api.git
cd phoneshop-api
poetry install                        # cài toàn bộ dependency, bao gồm dev dependency (pytest, ruff, mypy...)
cp .env.example .env                  # điền DATABASE_URL, REDIS_URL, RABBITMQ_URL theo hướng dẫn comment trong file
docker compose up -d db redis rabbitmq  # khởi động 3 service phụ thuộc, KHÔNG khởi động app (chạy app trực tiếp để dễ debug + hot reload)
poetry run alembic upgrade head        # apply toàn bộ migration lên database local
poetry run uvicorn app.main:app --reload --port 8001
```

Lần đầu setup thường mất khoảng 10-15 phút (tuỳ tốc độ pull Docker image và cài dependency Poetry).

## Seed data mẫu
```bash
poetry run python scripts/seed_catalog.py    # tạo ~50 sản phẩm mẫu thuộc nhiều danh mục, 5 chi nhánh giả lập
poetry run python scripts/seed_promotions.py  # tạo vài mã giảm giá demo (WELCOME10, FLASH50, GIFT_EARPHONE)
poetry run python scripts/seed_customers.py    # tạo 10 tài khoản khách hàng demo với password chuẩn "Test@1234"
```
Sau khi seed xong, có thể đăng nhập storefront local (nếu chạy kèm frontend) bằng tài khoản `demo1@phoneshop.dev` / `Test@1234`.

## Kiểm tra chạy đúng
1. Mở `http://localhost:8001/docs` — thấy Swagger UI với các nhóm endpoint `catalog`, `orders`, `inventory`, `payments`.
2. Gọi thử `GET /health` phải trả `200 OK` với body `{"status": "ok", "dependencies": {"database": "ok", "redis": "ok"}}`.
3. Gọi `GET /api/v1/products?limit=5` phải trả về danh sách 5 sản phẩm vừa seed.
4. Thử luồng đầy đủ: tạo giỏ hàng → thêm sản phẩm → checkout (dùng payment method `COD` để không cần config cổng thanh toán thật) → xác nhận đơn hàng xuất hiện trong DB.

## Chạy test
```bash
poetry run pytest tests/unit -v                          # nhanh, không cần DB, chạy < 5 giây
poetry run pytest tests/integration -v                    # cần docker compose db/redis/rabbitmq đang chạy
poetry run pytest --cov=app --cov-report=term-missing     # coverage report, target team đặt ra: >80%
poetry run mypy app/ --strict                              # kiểm tra type hint đầy đủ
poetry run ruff check app/ tests/                            # lint
```

## Lỗi thường gặp
| Lỗi | Nguyên nhân | Cách fix |
|---|---|---|
| `sqlalchemy.exc.OperationalError: connection refused` | Container `db` chưa healthy | `docker compose ps`, đợi `db` chuyển `healthy` rồi retry, thường mất 5-10 giây sau khi start |
| `pika.exceptions.AMQPConnectionError` | RabbitMQ chưa sẵn sàng hoặc sai `RABBITMQ_URL` trong `.env` | Kiểm tra `docker compose logs rabbitmq`, RabbitMQ khởi động chậm hơn Postgres ~10-15 giây |
| Alembic báo "Target database is not up to date" | Có migration mới trên `main` chưa pull/apply | `git pull`, sau đó `poetry run alembic upgrade head` |
| Import lỗi `ModuleNotFoundError: app` | Chưa activate đúng virtualenv của Poetry | Dùng `poetry run` prefix cho mọi lệnh, hoặc `poetry shell` trước khi chạy trực tiếp |
| Docker Desktop trên Windows chạy rất chậm | Chưa dùng WSL2 backend | Bật WSL2 integration trong Docker Desktop settings, clone repo vào filesystem của WSL2 (không phải `/mnt/c/...`) |
| `RuntimeError: Event loop is closed` khi chạy test | Xung đột giữa pytest-asyncio và cách quản lý connection pool async | Đảm bảo dùng đúng fixture `db_session` có sẵn trong `tests/conftest.py`, không tự tạo session riêng trong test |

## CI/CD
Push lên nhánh bất kỳ → GitHub Actions chạy lint (`ruff`) + type check (`mypy`) + test unit + test integration (dùng service container Postgres/Redis/RabbitMQ thật trong CI runner). Toàn bộ pipeline mất khoảng 6-8 phút. Merge vào `main` → tự động build Docker image, push lên ECR, ArgoCD tự động sync lên môi trường staging trong vòng 2-3 phút. Deploy production cần approve thủ công từ Tech Lead trên GitHub Actions (environment protection rule), sau đó ArgoCD sync lên production theo chiến lược rolling update (không downtime).
