# FurniStore — Setup môi trường dev

## Tổng quan
FurniStore cần **2 database chạy song song** (Postgres + MongoDB) cho local dev, khác với 2 dự án còn lại chỉ cần 1 database quan hệ — đọc kỹ phần cấu hình `.env` để tránh nhầm lẫn connection string giữa 2 loại database.

## Yêu cầu hệ thống
- **Node.js 20+** (khuyến nghị dùng `nvm` để quản lý version, repo có sẵn file `.nvmrc`).
- **pnpm** (package manager chính thức của dự án, không dùng `npm`/`yarn` — lockfile chỉ commit `pnpm-lock.yaml`).
- **Docker + Docker Compose**.

## Các bước setup từ đầu
```bash
git clone git@github.com:company/furnistore-api.git
cd furnistore-api
nvm use              # đảm bảo đúng Node version theo .nvmrc
pnpm install
cp .env.example .env   # điền DATABASE_URL (Postgres), MONGO_URL, REDIS_URL

docker compose up -d postgres mongo redis
pnpm prisma migrate dev    # apply migration Postgres + tự sinh Prisma Client
pnpm run seed                # tạo ~30 sản phẩm nội thất mẫu, 12 showroom demo

pnpm run dev                  # chạy dev server có hot reload (nodemon), mặc định port 3000
```

## Kiểm tra chạy đúng
1. Mở `http://localhost:3000/api-docs` (Swagger tự sinh từ JSDoc comment trong route) — thấy nhóm endpoint `catalog`, `cart`, `orders`, `shipping`, `delivery`.
2. Gọi `GET /health` phải trả `{"status":"ok","postgres":"connected","mongo":"connected","redis":"connected"}` — health check kiểm tra cả 3 kết nối, không chỉ trả OK chung chung.
3. Gọi `GET /api/products?limit=5` phải trả về danh sách sản phẩm đã seed.
4. Thử luồng đặt lịch giao hàng: tạo đơn hàng → gọi `POST /api/delivery/schedule` → xác nhận document xuất hiện trong MongoDB (`mongosh`, `db.deliverySchedules.find()`).

## Chạy test
```bash
pnpm test                        # unit test (Jest), mock Prisma Client + Mongoose
pnpm test:integration              # cần docker compose db đang chạy, test qua Supertest
pnpm run test:coverage              # coverage report, mở tại coverage/lcov-report/index.html
```

## Lỗi thường gặp
| Lỗi | Nguyên nhân | Cách fix |
|---|---|---|
| `pnpm prisma migrate dev` báo lỗi kết nối | Container `postgres` chưa healthy | `docker compose ps`, Prisma cần Postgres sẵn sàng trước khi migrate, đợi vài giây rồi retry |
| `MongoServerError: connection timed out` | Container `mongo` chưa khởi động xong (chậm hơn Postgres) | Đợi thêm 10-15 giây, hoặc kiểm tra `docker compose logs mongo` |
| Job BullMQ không chạy dù đã đẩy vào queue | Chưa chạy worker process riêng (`pnpm run worker`), server chính (`pnpm run dev`) không tự chạy worker | Chạy song song 2 terminal: 1 cho `pnpm run dev`, 1 cho `pnpm run worker` |
| `EADDRINUSE: port 3000 already in use` | Có process cũ chưa tắt hẳn | `lsof -ti:3000 \| xargs kill -9` (macOS/Linux) hoặc tắt qua Task Manager (Windows) |
| Prisma Client báo type không khớp sau khi đổi schema | Chưa regenerate Prisma Client | `pnpm prisma generate` sau mỗi lần đổi `schema.prisma` |

## Cấu trúc `.env` cần lưu ý
```
DATABASE_URL=postgresql://user:pass@localhost:5432/furnistore    # Prisma dùng
MONGO_URL=mongodb://localhost:27017/furnistore_delivery            # Mongoose dùng, KHÁC connection string với Postgres
REDIS_URL=redis://localhost:6379
SHIPPING_PARTNER_API_KEY=<lấy từ 1Password vault "FurniStore Dev">
```

## CI/CD
Push lên nhánh bất kỳ → GitHub Actions chạy ESLint + Jest (unit + integration với service container Postgres/MongoDB/Redis). Merge vào `main` → Render tự động deploy (Render tích hợp trực tiếp với GitHub, không cần bước build/push image thủ công như 2 dự án kia). Không có staging riêng biệt hoàn toàn — Render dùng Preview Environment tự động cho mỗi PR để test trước khi merge, xem được ở comment tự động trên PR.
