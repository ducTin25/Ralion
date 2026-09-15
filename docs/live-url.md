# URL trực tuyến — Sản phẩm bàn giao #5

## Các địa chỉ công khai

| Dịch vụ                    | URL                                                                   | Kết quả kiểm tra ngày 01/09/2026 |
| -------------------------- | --------------------------------------------------------------------- | --------------------------------- |
| Frontend chính thức        | [Ralion](https://www.ralion-team040.me/vi)                            | HTTP 200                          |
| Frontend dự phòng trên Vercel | [Bản triển khai Vercel](https://p040-frontend-1e93tlby8-t040.vercel.app/) | HTTP 200; chuyển hướng tới `/vi` |
| Trạng thái sẵn sàng của Backend | [FastAPI readiness](https://api-staging.34-21-198-43.sslip.io/ready) | HTTP 200                         |

Frontend sử dụng các request `/api` cùng origin và cơ chế rewrite phía máy chủ
của Vercel để chuyển tiếp tới Backend. Backend trả HTTP 404 tại đường dẫn gốc là
hành vi dự kiến; `/ready` là endpoint kiểm tra khả năng phục vụ của bản triển khai.

## Danh sách kiểm tra nhanh

- [x] Có thể truy cập Frontend mà không cần quyền repository hoặc cloud console.
- [x] Endpoint readiness của Backend trả HTTP 200.
- [x] Frontend chuyển hướng HTTPS và tải đúng route tiếng Việt.
- [x] Team P-040 cam kết duy trì dịch vụ đến hết Demo Day và thêm 7 ngày.

## Đơn vị chịu trách nhiệm vận hành

Team P-040 chịu trách nhiệm về khả năng truy cập. Quy trình triển khai và phục
hồi được mô tả trong [`deployment-vps-runbook.md`](deployment-vps-runbook.md).

## Cam kết duy trì dịch vụ

| Hạng mục              | Cam kết                                                                        |
| -------------------- | ------------------------------------------------------------------------------ |
| Đơn vị phụ trách     | Các thành viên duy trì repository của Team P-040                               |
| Thời gian duy trì    | Từ bản triển khai hiện tại đến hết Demo Day và thêm 7 ngày                     |
| Phạm vi dịch vụ      | Tên miền Frontend chính thức, bản Vercel và endpoint readiness của Backend     |
| Tần suất kiểm tra    | Ngay trước Demo Day và mỗi ngày một lần trong 7 ngày sau Demo Day              |
| Tài liệu phục hồi    | [`deployment-vps-runbook.md`](deployment-vps-runbook.md)                       |

Cam kết này được ghi nhận ngày 01/09/2026. Việc kiểm tra luồng chính có đăng
nhập lần cuối là bước vận hành được lên lịch ngay trước khi nộp bài, không phải
là một artifact URL trực tuyến còn thiếu.
