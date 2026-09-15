# PhoneShop API — Overview

## Giới thiệu chung
PhoneShop API là hệ thống backend trung tâm cho toàn bộ nền tảng bán điện thoại và phụ kiện trực tuyến của công ty, ra đời từ nhu cầu thay thế hệ thống bán hàng tại quầy (POS) cũ vốn không hỗ trợ bán online. Dự án khởi động tháng 9/2024 với đội ngũ 6 kỹ sư backend, 4 kỹ sư frontend, 1 QA lead, 1 DevOps, dưới sự dẫn dắt của 1 Product Manager và 1 Engineering Manager. Sau 6 tháng phát triển, hệ thống chính thức lên production vào tháng 3/2025 và từ đó liên tục được mở rộng theo từng sprint 2 tuần.

Hệ thống phục vụ đồng thời 3 kênh bán hàng: **website** (storefront Next.js, SSR để tối ưu SEO), **ứng dụng di động** (React Native, publish trên cả App Store và Google Play), và **hệ thống bán tại quầy** (POS terminal tại 35 chi nhánh, giao tiếp qua cùng bộ API này để đảm bảo tồn kho luôn nhất quán giữa online và offline).

## Bối cảnh kinh doanh
Thị trường bán lẻ điện thoại tại Việt Nam có mức độ cạnh tranh rất cao với các đối thủ lớn đã có hệ thống online trưởng thành. Ban lãnh đạo xác định chiến lược khác biệt hoá bằng: (1) tốc độ giao hàng nhanh hơn nhờ tối ưu tồn kho theo khu vực, (2) chính sách trả góp linh hoạt qua nhiều đối tác tài chính, (3) trải nghiệm mua hàng liền mạch giữa online và tại quầy (đặt online, nhận tại cửa hàng gần nhất trong 2 giờ).

Doanh thu online hiện chiếm khoảng 35% tổng doanh thu công ty và có xu hướng tăng đều ~5%/quý. Ban lãnh đạo đặt mục tiêu đạt 50% vào cuối năm 2026, kéo theo áp lực hệ thống phải scale tốt và ổn định hơn nữa.

## Trạng thái vận hành hiện tại
PhoneShop API đang **chạy production ổn định từ tháng 3/2025**, các chỉ số vận hành chính (tính đến kỳ báo cáo gần nhất):

| Chỉ số | Giá trị |
|---|---|
| Lượt truy cập trung bình/ngày | ~40.000 phiên |
| Đơn hàng trung bình/ngày | ~1.200 (ngày thường), ~9.000 (đỉnh flash sale) |
| Uptime SLA nội bộ | 99.9% cam kết, thực tế đạt 99.94% quý gần nhất |
| Latency API đặt hàng (p95) | 420ms |
| Tỷ lệ huỷ đơn do hết hàng | 1.8% (mục tiêu: dưới 1.5%) |
| Số chi nhánh đồng bộ tồn kho | 35 chi nhánh + 2 kho trung tâm (Hà Nội, TP.HCM) |
| Số lượng SKU đang active | ~3.200 sản phẩm |

## Mục tiêu kinh doanh chi tiết
- Cho phép khách hàng tìm kiếm, so sánh, và mua điện thoại online với trải nghiệm nhanh (mục tiêu LCP < 2.5s trên storefront, hiện đạt 2.1s trung bình).
- Đồng bộ tồn kho real-time giữa 35 chi nhánh và 2 kho trung tâm, độ trễ đồng bộ tối đa 5 giây (đo qua RabbitMQ consumer lag).
- Hỗ trợ khuyến mãi, mã giảm giá theo nhiều hình thức (giảm %, giảm tiền cố định, tặng kèm phụ kiện), và trả góp qua 3 đối tác tài chính hiện tại: Home Credit, FE Credit, Kredivo — đang đàm phán thêm đối tác thứ 4 (Fundiin) cho Q3/2025.
- Giảm tỷ lệ huỷ đơn do hết hàng xuống dưới 1.5% thông qua cải thiện cơ chế reservation và dự báo nhu cầu.
- Hỗ trợ mô hình "mua online, nhận tại cửa hàng" (BOPIS — Buy Online Pick-up In Store) với cam kết chuẩn bị hàng trong 2 giờ.

## Người dùng chính và vai trò
- **Khách hàng** (mua hàng qua web/app): ~250.000 tài khoản đã đăng ký tính đến hiện tại, ~60.000 hoạt động/tháng (đặt ít nhất 1 đơn hoặc đăng nhập). Phân khúc chính: 25-40 tuổi, khu vực thành thị, ưu tiên thanh toán online và trả góp.
- **Nhân viên bán hàng tại chi nhánh**: sử dụng Admin Portal riêng (`admin.phoneshop.internal`), thao tác xử lý đơn hàng tại quầy, xác nhận đơn BOPIS, xử lý đổi trả trong 7 ngày theo chính sách công ty.
- **Quản lý kho**: thao tác qua Inventory Portal, cập nhật số lượng nhập/xuất kho, đồng bộ 2 chiều với hệ thống ERP nội bộ (SAP) qua batch job chạy mỗi 15 phút — đây là điểm tích hợp phức tạp nhất hệ thống vì SAP không hỗ trợ webhook, phải dùng polling.
- **Đối tác tài chính**: tích hợp qua webhook một chiều (họ gọi vào hệ thống để cập nhật trạng thái duyệt hồ sơ trả góp), không có tài khoản đăng nhập trong hệ thống PhoneShop.
- **Bộ phận Marketing**: quản lý mã giảm giá, chương trình khuyến mãi qua Admin Portal, có quyền hạn chế (không thấy được thông tin cá nhân khách hàng chi tiết, chỉ thấy dữ liệu tổng hợp).

## Phạm vi hiện tại (đã lên production)
Catalog sản phẩm đầy đủ, giỏ hàng, đặt hàng, thanh toán COD/chuyển khoản ngân hàng/VNPay/Momo, trả góp qua 3 đối tác, mô hình BOPIS tại 35 chi nhánh, hệ thống mã giảm giá và khuyến mãi theo chương trình.

## Roadmap sắp tới
- **Q3/2025**: Tối ưu tuyến giao hàng tự động (đang POC với đối tác giao hàng GHTK, mục tiêu giảm 20% thời gian giao trung bình).
- **Q3/2025**: Gợi ý sản phẩm bằng AI dựa trên lịch sử mua hàng + hành vi duyệt web (đang làm việc với team Data Science nội bộ).
- **Q4/2025**: Mở rộng mô hình BOPIS ra toàn bộ 60 chi nhánh dự kiến mở mới.
- **2026**: Đánh giá tách search catalog ra Elasticsearch riêng khi số lượng SKU vượt 500.000 (dự kiến khi mở rộng sang bán đồ điện tử khác ngoài điện thoại).

## Sự cố đáng chú ý gần đây (để tránh lặp lại)
- **Tháng 03/2025**: Race condition khi 2 request cùng mua sản phẩm cuối cùng trong kho dẫn đến âm tồn kho, ảnh hưởng 47 đơn hàng trong 3 giờ trước khi phát hiện. Nguyên nhân gốc: thiếu khoá pessimistic khi kiểm tra và trừ tồn kho đồng thời. Đã fix bằng `SELECT ... FOR UPDATE` ở `inventory-service` (chi tiết kỹ thuật xem `codebase-guide.md`). Đã viết postmortem đầy đủ, lưu tại Confluence nội bộ `PHONE-INCIDENT-2025-03`.
- **Tháng 11/2024 (flash sale 11/11)**: RabbitMQ queue bị nghẽn do consumer xử lý chậm hơn tốc độ publish trong giờ cao điểm, khiến đơn hàng bị delay xác nhận đến ~10 phút, gây một lượng khách hàng khiếu nại qua hotline. Đã fix bằng cơ chế auto-scaling consumer theo queue depth (Kubernetes HPA custom metric từ RabbitMQ Prometheus exporter).
- **Tháng 01/2025**: Đối tác thanh toán Momo có downtime 45 phút ngoài kế hoạch, hệ thống chưa có cơ chế fallback tự động sang cổng khác → khách hàng không thanh toán được trong thời gian đó. Đã bổ sung circuit breaker + thông báo tạm ẩn phương thức thanh toán lỗi trên UI thay vì để khách gặp lỗi khi bấm thanh toán.

## Liên hệ đội ngũ
- **Engineering Manager**: phụ trách roadmap kỹ thuật tổng thể, quyết định kiến trúc lớn.
- **Tech Lead backend**: chịu trách nhiệm code quality, review kiến trúc từng service, mentor engineer mới.
- **Kênh Slack chính**: #phoneshop-backend (thảo luận kỹ thuật hàng ngày), #phoneshop-infra (vấn đề hạ tầng/deploy), #phoneshop-incidents (chỉ dùng khi có sự cố production).
