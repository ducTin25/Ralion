-- Auto-generated bởi scripts/upload_sample_docs_to_cloudinary.py — KHÔNG sửa tay.
-- Chạy SAU khi đã chạy scripts/seed_dev_data.py (cần sẵn users + projects).
-- Không cần tài khoản Cloudinary để chạy file này — URL đã upload sẵn.
BEGIN;

-- PHONESHOP: PhoneShop API — Overview
WITH doc AS (
  INSERT INTO knowledge_documents
    (project_id, created_by_user_id, knowledge_domain, document_category, policy_category,
     source_key, category_confirmed, category_classification_status,
     title, source_url, status, created_at, updated_at)
  VALUES (
    (SELECT project_id FROM projects WHERE key = 'PHONESHOP'),
    (SELECT user_id FROM users WHERE email = 'pm.phoneshop@onboarding.dev'),
    'PROJECT', 'OVERVIEW', NULL,
    'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/phoneshop/overview', true, 'CLASSIFIED',
    'PhoneShop API — Overview', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/phoneshop/overview', 'ACTIVE', now(), now()
  )
  RETURNING document_id
),
ver AS (
  INSERT INTO document_versions
    (document_id, version_no, revision_no, embedding_model_version,
     storage_uri, checksum, status, created_at)
  SELECT document_id, 1, 1, 'pending', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/phoneshop/overview', '4be3affba542b36255364bf54910c6bfca920925d83cf2365b510def573f068d', 'ACTIVE', now() FROM doc
  RETURNING version_id
)
INSERT INTO document_chunks (version_id, heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical)
SELECT ver.version_id, c.heading, c.content, c.chunk_index, c.token_count, c.embedding_text, c.content_hash, c.embedding_model_version, c.lexical_identifiers, c.lexical_technical
FROM ver, (VALUES
    (NULL::text, '# PhoneShop API — Overview', 0, 5, '# PhoneShop API — Overview', '8f7bad0330fea2b3fef904f8c8c317416564a7849638a6f5cccbb0aaa5314026', 'pending', '', '# PhoneShop API — Overview'),
    ('Giới thiệu chung'::text, 'PhoneShop API là hệ thống backend trung tâm cho toàn bộ nền tảng bán điện thoại và phụ kiện trực tuyến của công ty, ra đời từ nhu cầu thay thế hệ thống bán hàng tại quầy (POS) cũ vốn không hỗ trợ bán online. Dự án khởi động tháng 9/2024 với đội ngũ 6 kỹ sư backend, 4 kỹ sư frontend, 1 QA lead, 1 DevOps, dưới sự dẫn dắt của 1 Product Manager và 1 Engineering Manager. Sau 6 tháng phát triển, hệ thống chính thức lên production vào tháng 3/2025 và từ đó liên tục được mở rộng theo từng sprint 2 tuần.

Hệ thống phục vụ đồng thời 3 kênh bán hàng: **website** (storefront Next.js, SSR để tối ưu SEO), **ứng dụng di động** (React Native, publish trên cả App Store và Google Play), và **hệ thống bán tại quầy** (POS terminal tại 35 chi nhánh, giao tiếp qua cùng bộ API này để đảm bảo tồn kho luôn nhất quán giữa online và offline).', 1, 169, 'PhoneShop API là hệ thống backend trung tâm cho toàn bộ nền tảng bán điện thoại và phụ kiện trực tuyến của công ty, ra đời từ nhu cầu thay thế hệ thống bán hàng tại quầy (POS) cũ vốn không hỗ trợ bán online. Dự án khởi động tháng 9/2024 với đội ngũ 6 kỹ sư backend, 4 kỹ sư frontend, 1 QA lead, 1 DevOps, dưới sự dẫn dắt của 1 Product Manager và 1 Engineering Manager. Sau 6 tháng phát triển, hệ thống chính thức lên production vào tháng 3/2025 và từ đó liên tục được mở rộng theo từng sprint 2 tuần.

Hệ thống phục vụ đồng thời 3 kênh bán hàng: **website** (storefront Next.js, SSR để tối ưu SEO), **ứng dụng di động** (React Native, publish trên cả App Store và Google Play), và **hệ thống bán tại quầy** (POS terminal tại 35 chi nhánh, giao tiếp qua cùng bộ API này để đảm bảo tồn kho luôn nhất quán giữa online và offline).', '1b3b00b8dbf321f2b144ddfbe7882304b0daf88100fceb05444ab1167634ddd1', 'pending', '', 'PhoneShop API là hệ thống backend trung tâm cho toàn bộ nền tảng bán điện thoại và phụ kiện trực tuyến của công ty, ra đời từ nhu cầu thay thế hệ thống bán hàng tại quầy (POS) cũ vốn không hỗ trợ bán online. Dự án khởi động tháng 9/2024 với đội ngũ 6 kỹ sư backend, 4 kỹ sư frontend, 1 QA lead, 1 DevOps, dưới sự dẫn dắt của 1 Product Manager và 1 Engineering Manager. Sau 6 tháng phát triển, hệ thống chính thức lên production vào tháng 3/2025 và từ đó liên tục được mở rộng theo từng sprint 2 tuần.

Hệ thống phục vụ đồng thời 3 kênh bán hàng: **website** (storefront Next.js, SSR để tối ưu SEO), **ứng dụng di động** (React Native, publish trên cả App Store và Google Play), và **hệ thống bán tại quầy** (POS terminal tại 35 chi nhánh, giao tiếp qua cùng bộ API này để đảm bảo tồn kho luôn nhất quán giữa online và offline).'),
    ('Bối cảnh kinh doanh'::text, 'Thị trường bán lẻ điện thoại tại Việt Nam có mức độ cạnh tranh rất cao với các đối thủ lớn đã có hệ thống online trưởng thành. Ban lãnh đạo xác định chiến lược khác biệt hoá bằng: (1) tốc độ giao hàng nhanh hơn nhờ tối ưu tồn kho theo khu vực, (2) chính sách trả góp linh hoạt qua nhiều đối tác tài chính, (3) trải nghiệm mua hàng liền mạch giữa online và tại quầy (đặt online, nhận tại cửa hàng gần nhất trong 2 giờ).

Doanh thu online hiện chiếm khoảng 35% tổng doanh thu công ty và có xu hướng tăng đều ~5%/quý. Ban lãnh đạo đặt mục tiêu đạt 50% vào cuối năm 2026, kéo theo áp lực hệ thống phải scale tốt và ổn định hơn nữa.', 2, 135, 'Thị trường bán lẻ điện thoại tại Việt Nam có mức độ cạnh tranh rất cao với các đối thủ lớn đã có hệ thống online trưởng thành. Ban lãnh đạo xác định chiến lược khác biệt hoá bằng: (1) tốc độ giao hàng nhanh hơn nhờ tối ưu tồn kho theo khu vực, (2) chính sách trả góp linh hoạt qua nhiều đối tác tài chính, (3) trải nghiệm mua hàng liền mạch giữa online và tại quầy (đặt online, nhận tại cửa hàng gần nhất trong 2 giờ).

Doanh thu online hiện chiếm khoảng 35% tổng doanh thu công ty và có xu hướng tăng đều ~5%/quý. Ban lãnh đạo đặt mục tiêu đạt 50% vào cuối năm 2026, kéo theo áp lực hệ thống phải scale tốt và ổn định hơn nữa.', '878c463c3f9a4b7ec8c215922584b8c12175c79cd8eb48449cf0fe33bb6637c5', 'pending', '', 'Thị trường bán lẻ điện thoại tại Việt Nam có mức độ cạnh tranh rất cao với các đối thủ lớn đã có hệ thống online trưởng thành. Ban lãnh đạo xác định chiến lược khác biệt hoá bằng: (1) tốc độ giao hàng nhanh hơn nhờ tối ưu tồn kho theo khu vực, (2) chính sách trả góp linh hoạt qua nhiều đối tác tài chính, (3) trải nghiệm mua hàng liền mạch giữa online và tại quầy (đặt online, nhận tại cửa hàng gần nhất trong 2 giờ).

Doanh thu online hiện chiếm khoảng 35% tổng doanh thu công ty và có xu hướng tăng đều ~5%/quý. Ban lãnh đạo đặt mục tiêu đạt 50% vào cuối năm 2026, kéo theo áp lực hệ thống phải scale tốt và ổn định hơn nữa.'),
    ('Trạng thái vận hành hiện tại'::text, 'PhoneShop API đang **chạy production ổn định từ tháng 3/2025**, các chỉ số vận hành chính (tính đến kỳ báo cáo gần nhất):

| Chỉ số | Giá trị |
|---|---|
| Lượt truy cập trung bình/ngày | ~40.000 phiên |
| Đơn hàng trung bình/ngày | ~1.200 (ngày thường), ~9.000 (đỉnh flash sale) |
| Uptime SLA nội bộ | 99.9% cam kết, thực tế đạt 99.94% quý gần nhất |
| Latency API đặt hàng (p95) | 420ms |
| Tỷ lệ huỷ đơn do hết hàng | 1.8% (mục tiêu: dưới 1.5%) |
| Số chi nhánh đồng bộ tồn kho | 35 chi nhánh + 2 kho trung tâm (Hà Nội, TP.HCM) |
| Số lượng SKU đang active | ~3.200 sản phẩm |', 3, 128, 'PhoneShop API đang **chạy production ổn định từ tháng 3/2025**, các chỉ số vận hành chính (tính đến kỳ báo cáo gần nhất):

| Chỉ số | Giá trị |
|---|---|
| Lượt truy cập trung bình/ngày | ~40.000 phiên |
| Đơn hàng trung bình/ngày | ~1.200 (ngày thường), ~9.000 (đỉnh flash sale) |
| Uptime SLA nội bộ | 99.9% cam kết, thực tế đạt 99.94% quý gần nhất |
| Latency API đặt hàng (p95) | 420ms |
| Tỷ lệ huỷ đơn do hết hàng | 1.8% (mục tiêu: dưới 1.5%) |
| Số chi nhánh đồng bộ tồn kho | 35 chi nhánh + 2 kho trung tâm (Hà Nội, TP.HCM) |
| Số lượng SKU đang active | ~3.200 sản phẩm |', 'aea639636046a7f69253d59ea1423d841f040d8cd39f5f2f4abb3f36ff96ee19', 'pending', '', 'PhoneShop API đang **chạy production ổn định từ tháng 3/2025**, các chỉ số vận hành chính (tính đến kỳ báo cáo gần nhất):

| Chỉ số | Giá trị |
|---|---|
| Lượt truy cập trung bình/ngày | ~40.000 phiên |
| Đơn hàng trung bình/ngày | ~1.200 (ngày thường), ~9.000 (đỉnh flash sale) |
| Uptime SLA nội bộ | 99.9% cam kết, thực tế đạt 99.94% quý gần nhất |
| Latency API đặt hàng (p95) | 420ms |
| Tỷ lệ huỷ đơn do hết hàng | 1.8% (mục tiêu: dưới 1.5%) |
| Số chi nhánh đồng bộ tồn kho | 35 chi nhánh + 2 kho trung tâm (Hà Nội, TP.HCM) |
| Số lượng SKU đang active | ~3.200 sản phẩm |'),
    ('Mục tiêu kinh doanh chi tiết'::text, '- Cho phép khách hàng tìm kiếm, so sánh, và mua điện thoại online với trải nghiệm nhanh (mục tiêu LCP < 2.5s trên storefront, hiện đạt 2.1s trung bình).
- Đồng bộ tồn kho real-time giữa 35 chi nhánh và 2 kho trung tâm, độ trễ đồng bộ tối đa 5 giây (đo qua RabbitMQ consumer lag).
- Hỗ trợ khuyến mãi, mã giảm giá theo nhiều hình thức (giảm %, giảm tiền cố định, tặng kèm phụ kiện), và trả góp qua 3 đối tác tài chính hiện tại: Home Credit, FE Credit, Kredivo — đang đàm phán thêm đối tác thứ 4 (Fundiin) cho Q3/2025.
- Giảm tỷ lệ huỷ đơn do hết hàng xuống dưới 1.5% thông qua cải thiện cơ chế reservation và dự báo nhu cầu.
- Hỗ trợ mô hình "mua online, nhận tại cửa hàng" (BOPIS — Buy Online Pick-up In Store) với cam kết chuẩn bị hàng trong 2 giờ.', 4, 159, '- Cho phép khách hàng tìm kiếm, so sánh, và mua điện thoại online với trải nghiệm nhanh (mục tiêu LCP < 2.5s trên storefront, hiện đạt 2.1s trung bình).
- Đồng bộ tồn kho real-time giữa 35 chi nhánh và 2 kho trung tâm, độ trễ đồng bộ tối đa 5 giây (đo qua RabbitMQ consumer lag).
- Hỗ trợ khuyến mãi, mã giảm giá theo nhiều hình thức (giảm %, giảm tiền cố định, tặng kèm phụ kiện), và trả góp qua 3 đối tác tài chính hiện tại: Home Credit, FE Credit, Kredivo — đang đàm phán thêm đối tác thứ 4 (Fundiin) cho Q3/2025.
- Giảm tỷ lệ huỷ đơn do hết hàng xuống dưới 1.5% thông qua cải thiện cơ chế reservation và dự báo nhu cầu.
- Hỗ trợ mô hình "mua online, nhận tại cửa hàng" (BOPIS — Buy Online Pick-up In Store) với cam kết chuẩn bị hàng trong 2 giờ.', '2c3d7be93fd794d790c52a531aa580a074bd2d6b09a48b87ced02b006adc4c53', 'pending', '', '- Cho phép khách hàng tìm kiếm, so sánh, và mua điện thoại online với trải nghiệm nhanh (mục tiêu LCP < 2.5s trên storefront, hiện đạt 2.1s trung bình).
- Đồng bộ tồn kho real-time giữa 35 chi nhánh và 2 kho trung tâm, độ trễ đồng bộ tối đa 5 giây (đo qua RabbitMQ consumer lag).
- Hỗ trợ khuyến mãi, mã giảm giá theo nhiều hình thức (giảm %, giảm tiền cố định, tặng kèm phụ kiện), và trả góp qua 3 đối tác tài chính hiện tại: Home Credit, FE Credit, Kredivo — đang đàm phán thêm đối tác thứ 4 (Fundiin) cho Q3/2025.
- Giảm tỷ lệ huỷ đơn do hết hàng xuống dưới 1.5% thông qua cải thiện cơ chế reservation và dự báo nhu cầu.
- Hỗ trợ mô hình "mua online, nhận tại cửa hàng" (BOPIS — Buy Online Pick-up In Store) với cam kết chuẩn bị hàng trong 2 giờ.'),
    ('Người dùng chính và vai trò'::text, '- **Khách hàng** (mua hàng qua web/app): ~250.000 tài khoản đã đăng ký tính đến hiện tại, ~60.000 hoạt động/tháng (đặt ít nhất 1 đơn hoặc đăng nhập). Phân khúc chính: 25-40 tuổi, khu vực thành thị, ưu tiên thanh toán online và trả góp.
- **Nhân viên bán hàng tại chi nhánh**: sử dụng Admin Portal riêng (`admin.phoneshop.internal`), thao tác xử lý đơn hàng tại quầy, xác nhận đơn BOPIS, xử lý đổi trả trong 7 ngày theo chính sách công ty.
- **Quản lý kho**: thao tác qua Inventory Portal, cập nhật số lượng nhập/xuất kho, đồng bộ 2 chiều với hệ thống ERP nội bộ (SAP) qua batch job chạy mỗi 15 phút — đây là điểm tích hợp phức tạp nhất hệ thống vì SAP không hỗ trợ webhook, phải dùng polling.
- **Đối tác tài chính**: tích hợp qua webhook một chiều (họ gọi vào hệ thống để cập nhật trạng thái duyệt hồ sơ trả góp), không có tài khoản đăng nhập trong hệ thống PhoneShop.
- **Bộ phận Marketing**: quản lý mã giảm giá, chương trình khuyến mãi qua Admin Portal, có quyền hạn chế (không thấy được thông tin cá nhân khách hàng chi tiết, chỉ thấy dữ liệu tổng hợp).', 5, 209, '- **Khách hàng** (mua hàng qua web/app): ~250.000 tài khoản đã đăng ký tính đến hiện tại, ~60.000 hoạt động/tháng (đặt ít nhất 1 đơn hoặc đăng nhập). Phân khúc chính: 25-40 tuổi, khu vực thành thị, ưu tiên thanh toán online và trả góp.
- **Nhân viên bán hàng tại chi nhánh**: sử dụng Admin Portal riêng (`admin.phoneshop.internal`), thao tác xử lý đơn hàng tại quầy, xác nhận đơn BOPIS, xử lý đổi trả trong 7 ngày theo chính sách công ty.
- **Quản lý kho**: thao tác qua Inventory Portal, cập nhật số lượng nhập/xuất kho, đồng bộ 2 chiều với hệ thống ERP nội bộ (SAP) qua batch job chạy mỗi 15 phút — đây là điểm tích hợp phức tạp nhất hệ thống vì SAP không hỗ trợ webhook, phải dùng polling.
- **Đối tác tài chính**: tích hợp qua webhook một chiều (họ gọi vào hệ thống để cập nhật trạng thái duyệt hồ sơ trả góp), không có tài khoản đăng nhập trong hệ thống PhoneShop.
- **Bộ phận Marketing**: quản lý mã giảm giá, chương trình khuyến mãi qua Admin Portal, có quyền hạn chế (không thấy được thông tin cá nhân khách hàng chi tiết, chỉ thấy dữ liệu tổng hợp).', '19a1f3c9eb1bc6a19506f0c93146b7b958368ed5a1c1fdda53e38e995754df21', 'pending', '', '- **Khách hàng** (mua hàng qua web/app): ~250.000 tài khoản đã đăng ký tính đến hiện tại, ~60.000 hoạt động/tháng (đặt ít nhất 1 đơn hoặc đăng nhập). Phân khúc chính: 25-40 tuổi, khu vực thành thị, ưu tiên thanh toán online và trả góp.
- **Nhân viên bán hàng tại chi nhánh**: sử dụng Admin Portal riêng (`admin.phoneshop.internal`), thao tác xử lý đơn hàng tại quầy, xác nhận đơn BOPIS, xử lý đổi trả trong 7 ngày theo chính sách công ty.
- **Quản lý kho**: thao tác qua Inventory Portal, cập nhật số lượng nhập/xuất kho, đồng bộ 2 chiều với hệ thống ERP nội bộ (SAP) qua batch job chạy mỗi 15 phút — đây là điểm tích hợp phức tạp nhất hệ thống vì SAP không hỗ trợ webhook, phải dùng polling.
- **Đối tác tài chính**: tích hợp qua webhook một chiều (họ gọi vào hệ thống để cập nhật trạng thái duyệt hồ sơ trả góp), không có tài khoản đăng nhập trong hệ thống PhoneShop.
- **Bộ phận Marketing**: quản lý mã giảm giá, chương trình khuyến mãi qua Admin Portal, có quyền hạn chế (không thấy được thông tin cá nhân khách hàng chi tiết, chỉ thấy dữ liệu tổng hợp).'),
    ('Phạm vi hiện tại (đã lên production)'::text, 'Catalog sản phẩm đầy đủ, giỏ hàng, đặt hàng, thanh toán COD/chuyển khoản ngân hàng/VNPay/Momo, trả góp qua 3 đối tác, mô hình BOPIS tại 35 chi nhánh, hệ thống mã giảm giá và khuyến mãi theo chương trình.', 6, 39, 'Catalog sản phẩm đầy đủ, giỏ hàng, đặt hàng, thanh toán COD/chuyển khoản ngân hàng/VNPay/Momo, trả góp qua 3 đối tác, mô hình BOPIS tại 35 chi nhánh, hệ thống mã giảm giá và khuyến mãi theo chương trình.', '78e3a02e0170d77fa67b46813c4dcf5761a372318780b10c9d25a2aabfd40545', 'pending', '', 'Catalog sản phẩm đầy đủ, giỏ hàng, đặt hàng, thanh toán COD/chuyển khoản ngân hàng/VNPay/Momo, trả góp qua 3 đối tác, mô hình BOPIS tại 35 chi nhánh, hệ thống mã giảm giá và khuyến mãi theo chương trình.'),
    ('Roadmap sắp tới'::text, '- **Q3/2025**: Tối ưu tuyến giao hàng tự động (đang POC với đối tác giao hàng GHTK, mục tiêu giảm 20% thời gian giao trung bình).
- **Q3/2025**: Gợi ý sản phẩm bằng AI dựa trên lịch sử mua hàng + hành vi duyệt web (đang làm việc với team Data Science nội bộ).
- **Q4/2025**: Mở rộng mô hình BOPIS ra toàn bộ 60 chi nhánh dự kiến mở mới.
- **2026**: Đánh giá tách search catalog ra Elasticsearch riêng khi số lượng SKU vượt 500.000 (dự kiến khi mở rộng sang bán đồ điện tử khác ngoài điện thoại).', 7, 101, '- **Q3/2025**: Tối ưu tuyến giao hàng tự động (đang POC với đối tác giao hàng GHTK, mục tiêu giảm 20% thời gian giao trung bình).
- **Q3/2025**: Gợi ý sản phẩm bằng AI dựa trên lịch sử mua hàng + hành vi duyệt web (đang làm việc với team Data Science nội bộ).
- **Q4/2025**: Mở rộng mô hình BOPIS ra toàn bộ 60 chi nhánh dự kiến mở mới.
- **2026**: Đánh giá tách search catalog ra Elasticsearch riêng khi số lượng SKU vượt 500.000 (dự kiến khi mở rộng sang bán đồ điện tử khác ngoài điện thoại).', '204db47247b2df9b5cfd46f49b5f92eef053cff000358e095331b56adeafa7da', 'pending', '', '- **Q3/2025**: Tối ưu tuyến giao hàng tự động (đang POC với đối tác giao hàng GHTK, mục tiêu giảm 20% thời gian giao trung bình).
- **Q3/2025**: Gợi ý sản phẩm bằng AI dựa trên lịch sử mua hàng + hành vi duyệt web (đang làm việc với team Data Science nội bộ).
- **Q4/2025**: Mở rộng mô hình BOPIS ra toàn bộ 60 chi nhánh dự kiến mở mới.
- **2026**: Đánh giá tách search catalog ra Elasticsearch riêng khi số lượng SKU vượt 500.000 (dự kiến khi mở rộng sang bán đồ điện tử khác ngoài điện thoại).'),
    ('Sự cố đáng chú ý gần đây (để tránh lặp lại)'::text, '- **Tháng 03/2025**: Race condition khi 2 request cùng mua sản phẩm cuối cùng trong kho dẫn đến âm tồn kho, ảnh hưởng 47 đơn hàng trong 3 giờ trước khi phát hiện. Nguyên nhân gốc: thiếu khoá pessimistic khi kiểm tra và trừ tồn kho đồng thời. Đã fix bằng `SELECT ... FOR UPDATE` ở `inventory-service` (chi tiết kỹ thuật xem `codebase-guide.md`). Đã viết postmortem đầy đủ, lưu tại Confluence nội bộ `PHONE-INCIDENT-2025-03`.
- **Tháng 11/2024 (flash sale 11/11)**: RabbitMQ queue bị nghẽn do consumer xử lý chậm hơn tốc độ publish trong giờ cao điểm, khiến đơn hàng bị delay xác nhận đến ~10 phút, gây một lượng khách hàng khiếu nại qua hotline. Đã fix bằng cơ chế auto-scaling consumer theo queue depth (Kubernetes HPA custom metric từ RabbitMQ Prometheus exporter).
- **Tháng 01/2025**: Đối tác thanh toán Momo có downtime 45 phút ngoài kế hoạch, hệ thống chưa có cơ chế fallback tự động sang cổng khác → khách hàng không thanh toán được trong thời gian đó. Đã bổ sung circuit breaker + thông báo tạm ẩn phương thức thanh toán lỗi trên UI thay vì để khách gặp lỗi khi bấm thanh toán.', 8, 199, '- **Tháng 03/2025**: Race condition khi 2 request cùng mua sản phẩm cuối cùng trong kho dẫn đến âm tồn kho, ảnh hưởng 47 đơn hàng trong 3 giờ trước khi phát hiện. Nguyên nhân gốc: thiếu khoá pessimistic khi kiểm tra và trừ tồn kho đồng thời. Đã fix bằng `SELECT ... FOR UPDATE` ở `inventory-service` (chi tiết kỹ thuật xem `codebase-guide.md`). Đã viết postmortem đầy đủ, lưu tại Confluence nội bộ `PHONE-INCIDENT-2025-03`.
- **Tháng 11/2024 (flash sale 11/11)**: RabbitMQ queue bị nghẽn do consumer xử lý chậm hơn tốc độ publish trong giờ cao điểm, khiến đơn hàng bị delay xác nhận đến ~10 phút, gây một lượng khách hàng khiếu nại qua hotline. Đã fix bằng cơ chế auto-scaling consumer theo queue depth (Kubernetes HPA custom metric từ RabbitMQ Prometheus exporter).
- **Tháng 01/2025**: Đối tác thanh toán Momo có downtime 45 phút ngoài kế hoạch, hệ thống chưa có cơ chế fallback tự động sang cổng khác → khách hàng không thanh toán được trong thời gian đó. Đã bổ sung circuit breaker + thông báo tạm ẩn phương thức thanh toán lỗi trên UI thay vì để khách gặp lỗi khi bấm thanh toán.', 'd468f272302dff595fc4586e0d00487755463aae53fec2d73d2a08908370349a', 'pending', '', '- **Tháng 03/2025**: Race condition khi 2 request cùng mua sản phẩm cuối cùng trong kho dẫn đến âm tồn kho, ảnh hưởng 47 đơn hàng trong 3 giờ trước khi phát hiện. Nguyên nhân gốc: thiếu khoá pessimistic khi kiểm tra và trừ tồn kho đồng thời. Đã fix bằng `SELECT ... FOR UPDATE` ở `inventory-service` (chi tiết kỹ thuật xem `codebase-guide.md`). Đã viết postmortem đầy đủ, lưu tại Confluence nội bộ `PHONE-INCIDENT-2025-03`.
- **Tháng 11/2024 (flash sale 11/11)**: RabbitMQ queue bị nghẽn do consumer xử lý chậm hơn tốc độ publish trong giờ cao điểm, khiến đơn hàng bị delay xác nhận đến ~10 phút, gây một lượng khách hàng khiếu nại qua hotline. Đã fix bằng cơ chế auto-scaling consumer theo queue depth (Kubernetes HPA custom metric từ RabbitMQ Prometheus exporter).
- **Tháng 01/2025**: Đối tác thanh toán Momo có downtime 45 phút ngoài kế hoạch, hệ thống chưa có cơ chế fallback tự động sang cổng khác → khách hàng không thanh toán được trong thời gian đó. Đã bổ sung circuit breaker + thông báo tạm ẩn phương thức thanh toán lỗi trên UI thay vì để khách gặp lỗi khi bấm thanh toán.'),
    ('Liên hệ đội ngũ'::text, '- **Engineering Manager**: phụ trách roadmap kỹ thuật tổng thể, quyết định kiến trúc lớn.
- **Tech Lead backend**: chịu trách nhiệm code quality, review kiến trúc từng service, mentor engineer mới.
- **Kênh Slack chính**: #phoneshop-backend (thảo luận kỹ thuật hàng ngày), #phoneshop-infra (vấn đề hạ tầng/deploy), #phoneshop-incidents (chỉ dùng khi có sự cố production).', 9, 56, '- **Engineering Manager**: phụ trách roadmap kỹ thuật tổng thể, quyết định kiến trúc lớn.
- **Tech Lead backend**: chịu trách nhiệm code quality, review kiến trúc từng service, mentor engineer mới.
- **Kênh Slack chính**: #phoneshop-backend (thảo luận kỹ thuật hàng ngày), #phoneshop-infra (vấn đề hạ tầng/deploy), #phoneshop-incidents (chỉ dùng khi có sự cố production).', 'e1556bcee41cc103bd0e7ed01935d72bc38a647bd63b0d413a63bbdb5cf9789d', 'pending', '', '- **Engineering Manager**: phụ trách roadmap kỹ thuật tổng thể, quyết định kiến trúc lớn.
- **Tech Lead backend**: chịu trách nhiệm code quality, review kiến trúc từng service, mentor engineer mới.
- **Kênh Slack chính**: #phoneshop-backend (thảo luận kỹ thuật hàng ngày), #phoneshop-infra (vấn đề hạ tầng/deploy), #phoneshop-incidents (chỉ dùng khi có sự cố production).')
) AS c(heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical);

-- PHONESHOP: PhoneShop API — Architecture
WITH doc AS (
  INSERT INTO knowledge_documents
    (project_id, created_by_user_id, knowledge_domain, document_category, policy_category,
     source_key, category_confirmed, category_classification_status,
     title, source_url, status, created_at, updated_at)
  VALUES (
    (SELECT project_id FROM projects WHERE key = 'PHONESHOP'),
    (SELECT user_id FROM users WHERE email = 'pm.phoneshop@onboarding.dev'),
    'PROJECT', 'ARCHITECTURE', NULL,
    'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/phoneshop/architecture', true, 'CLASSIFIED',
    'PhoneShop API — Architecture', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/phoneshop/architecture', 'ACTIVE', now(), now()
  )
  RETURNING document_id
),
ver AS (
  INSERT INTO document_versions
    (document_id, version_no, revision_no, embedding_model_version,
     storage_uri, checksum, status, created_at)
  SELECT document_id, 1, 1, 'pending', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/phoneshop/architecture', 'e6ef8512fbced5859e288eba059fc93220cbd569116cf083d1da6d9b84c3689c', 'ACTIVE', now() FROM doc
  RETURNING version_id
)
INSERT INTO document_chunks (version_id, heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical)
SELECT ver.version_id, c.heading, c.content, c.chunk_index, c.token_count, c.embedding_text, c.content_hash, c.embedding_model_version, c.lexical_identifiers, c.lexical_technical
FROM ver, (VALUES
    (NULL::text, '# PhoneShop API — Architecture', 0, 5, '# PhoneShop API — Architecture', '81001721089fb0f78e01d57305082f4eee143cc47aed1be80f58ac3620169a91', 'pending', '', '# PhoneShop API — Architecture'),
    ('Tổng quan kiến trúc'::text, 'PhoneShop API được thiết kế theo kiến trúc **microservice**, tách theo domain nghiệp vụ (catalog, order, inventory, payment, notification), giao tiếp với nhau qua kết hợp **REST đồng bộ** (khi cần phản hồi ngay, ví dụ kiểm tra tồn kho lúc checkout) và **event bất đồng bộ qua RabbitMQ** (khi không cần chờ phản hồi ngay, ví dụ gửi email xác nhận). Quyết định tách service được đưa ra sau khi hệ thống monolith cũ (Rails, viết từ 2019) gặp giới hạn scale nghiêm trọng vào cuối 2023, không đáp ứng nổi tải flash sale.', 1, 95, 'PhoneShop API được thiết kế theo kiến trúc **microservice**, tách theo domain nghiệp vụ (catalog, order, inventory, payment, notification), giao tiếp với nhau qua kết hợp **REST đồng bộ** (khi cần phản hồi ngay, ví dụ kiểm tra tồn kho lúc checkout) và **event bất đồng bộ qua RabbitMQ** (khi không cần chờ phản hồi ngay, ví dụ gửi email xác nhận). Quyết định tách service được đưa ra sau khi hệ thống monolith cũ (Rails, viết từ 2019) gặp giới hạn scale nghiêm trọng vào cuối 2023, không đáp ứng nổi tải flash sale.', 'dadf7214a635843132fa0b9881fc064c40c8bb61b800c0dd793965299b737b15', 'pending', '', 'PhoneShop API được thiết kế theo kiến trúc **microservice**, tách theo domain nghiệp vụ (catalog, order, inventory, payment, notification), giao tiếp với nhau qua kết hợp **REST đồng bộ** (khi cần phản hồi ngay, ví dụ kiểm tra tồn kho lúc checkout) và **event bất đồng bộ qua RabbitMQ** (khi không cần chờ phản hồi ngay, ví dụ gửi email xác nhận). Quyết định tách service được đưa ra sau khi hệ thống monolith cũ (Rails, viết từ 2019) gặp giới hạn scale nghiêm trọng vào cuối 2023, không đáp ứng nổi tải flash sale.'),
    ('Tech stack đầy đủ'::text, '| Thành phần | Công nghệ | Ghi chú |
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
| Observability | Datadog (APM + log + synthetic), Sentry (error), PagerDuty (on-call) | Dashboard riêng theo từng service |', 2, 231, '| Thành phần | Công nghệ | Ghi chú |
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
| Observability | Datadog (APM + log + synthetic), Sentry (error), PagerDuty (on-call) | Dashboard riêng theo từng service |', 'd6533d2249afbc4e2aa278c84db260a703b193eefc0db6727148e75cc1209d9e', 'pending', '', '| Thành phần | Công nghệ | Ghi chú |
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
| Observability | Datadog (APM + log + synthetic), Sentry (error), PagerDuty (on-call) | Dashboard riêng theo từng service |'),
    ('Sơ đồ luồng đặt hàng (chi tiết)'::text, '```
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
```', 3, 100, '```
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
```', '58342a5b983db1fbc4f7620d122bbb02a6c6fe8e19059e7f3e8733d8779bec90', 'pending', '', '```
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
```'),
    ('Module chính và trách nhiệm'::text, '- **`catalog-service`**: quản lý sản phẩm, danh mục, thuộc tính kỹ thuật (RAM, dung lượng, màu sắc, bảo hành). Đồng bộ ảnh sản phẩm qua Cloudinary, cache danh sách sản phẩm phổ biến trong Redis để giảm tải Postgres.
- **`order-service`**: tạo đơn, tính giá (bao gồm áp mã giảm giá, tính phí trả góp nếu có), orchestrate toàn bộ luồng thanh toán, quản lý trạng thái đơn hàng (state machine: `PENDING -> CONFIRMED -> PACKING -> SHIPPING -> DELIVERED`, hoặc `CANCELLED`/`REFUNDED` ở bất kỳ bước nào trước `DELIVERED`).
- **`inventory-service`**: theo dõi tồn kho theo 35 chi nhánh + 2 kho trung tâm, xử lý đặt trước (reservation) khi khách thêm vào giỏ, đồng bộ 2 chiều với SAP ERP.
- **`payment-service`**: tích hợp cổng thanh toán (VNPay, Momo), 3 đối tác trả góp, xử lý webhook callback (idempotent qua `transaction_id` unique constraint, tránh xử lý trùng khi đối tác gửi lại webhook do timeout).
- **`notification-service`**: gửi email (SendGrid) + SMS (eSMS) xác nhận đơn, nhắc lịch thanh toán trả góp, thông báo thay đổi trạng thái giao hàng.', 4, 181, '- **`catalog-service`**: quản lý sản phẩm, danh mục, thuộc tính kỹ thuật (RAM, dung lượng, màu sắc, bảo hành). Đồng bộ ảnh sản phẩm qua Cloudinary, cache danh sách sản phẩm phổ biến trong Redis để giảm tải Postgres.
- **`order-service`**: tạo đơn, tính giá (bao gồm áp mã giảm giá, tính phí trả góp nếu có), orchestrate toàn bộ luồng thanh toán, quản lý trạng thái đơn hàng (state machine: `PENDING -> CONFIRMED -> PACKING -> SHIPPING -> DELIVERED`, hoặc `CANCELLED`/`REFUNDED` ở bất kỳ bước nào trước `DELIVERED`).
- **`inventory-service`**: theo dõi tồn kho theo 35 chi nhánh + 2 kho trung tâm, xử lý đặt trước (reservation) khi khách thêm vào giỏ, đồng bộ 2 chiều với SAP ERP.
- **`payment-service`**: tích hợp cổng thanh toán (VNPay, Momo), 3 đối tác trả góp, xử lý webhook callback (idempotent qua `transaction_id` unique constraint, tránh xử lý trùng khi đối tác gửi lại webhook do timeout).
- **`notification-service`**: gửi email (SendGrid) + SMS (eSMS) xác nhận đơn, nhắc lịch thanh toán trả góp, thông báo thay đổi trạng thái giao hàng.', 'b026f0de74370f39166152d6f9a2b5109712ce60fc8019b3a087d4ac26d41b06', 'pending', '', '- **`catalog-service`**: quản lý sản phẩm, danh mục, thuộc tính kỹ thuật (RAM, dung lượng, màu sắc, bảo hành). Đồng bộ ảnh sản phẩm qua Cloudinary, cache danh sách sản phẩm phổ biến trong Redis để giảm tải Postgres.
- **`order-service`**: tạo đơn, tính giá (bao gồm áp mã giảm giá, tính phí trả góp nếu có), orchestrate toàn bộ luồng thanh toán, quản lý trạng thái đơn hàng (state machine: `PENDING -> CONFIRMED -> PACKING -> SHIPPING -> DELIVERED`, hoặc `CANCELLED`/`REFUNDED` ở bất kỳ bước nào trước `DELIVERED`).
- **`inventory-service`**: theo dõi tồn kho theo 35 chi nhánh + 2 kho trung tâm, xử lý đặt trước (reservation) khi khách thêm vào giỏ, đồng bộ 2 chiều với SAP ERP.
- **`payment-service`**: tích hợp cổng thanh toán (VNPay, Momo), 3 đối tác trả góp, xử lý webhook callback (idempotent qua `transaction_id` unique constraint, tránh xử lý trùng khi đối tác gửi lại webhook do timeout).
- **`notification-service`**: gửi email (SendGrid) + SMS (eSMS) xác nhận đơn, nhắc lịch thanh toán trả góp, thông báo thay đổi trạng thái giao hàng.'),
    ('Database schema (rút gọn, các bảng quan trọng nhất)'::text, '```sql
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
Full schema và mối quan hệ chi tiết xem trong `catalog-service/migrations/`, `order-service/migrations/`, v.v. (mỗi service tự quản lý migration riêng — đúng nguyên tắc "database per service" của microservice).', 5, 97, '```sql
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
Full schema và mối quan hệ chi tiết xem trong `catalog-service/migrations/`, `order-service/migrations/`, v.v. (mỗi service tự quản lý migration riêng — đúng nguyên tắc "database per service" của microservice).', '4ef54e4204aa38b6d8bd368babc6d0669e08a3e3bd8594d264869673ad618314', 'pending', '', '```sql
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
Full schema và mối quan hệ chi tiết xem trong `catalog-service/migrations/`, `order-service/migrations/`, v.v. (mỗi service tự quản lý migration riêng — đúng nguyên tắc "database per service" của microservice).'),
    ('Quyết định thiết kế quan trọng và lý do'::text, '- **Microservice thay vì monolith**: catalog đọc nhiều (~95% traffic), inventory ghi nhiều lúc flash sale — tách riêng để scale độc lập theo tải thực tế, tránh 1 service nghẽn kéo cả hệ thống chậm theo. Đây là bài học rút ra từ hệ thống monolith Rails cũ, đã chính thức ngừng dùng từ đầu 2024 sau khi hoàn tất migration.
- **Reservation TTL 10 phút thay vì trừ kho ngay khi thêm giỏ**: cân bằng giữa trải nghiệm khách hàng (không mất hàng ngay khi vừa thêm vào giỏ, đủ thời gian cân nhắc) và tránh giữ chỗ vô thời hạn gây ra tình trạng "ảo" hết hàng khi khách bỏ giỏ hàng không mua. Con số 10 phút được A/B test và chọn dựa trên hành vi thực tế của khách hàng PhoneShop.
- **Không dùng saga pattern phức tạp cho luồng thanh toán**: với quy mô giao dịch hiện tại (dưới 10.000 đơn/ngày kể cả đỉnh điểm), orchestration đơn giản (Order Service gọi tuần tự các service khác, có compensate action rõ ràng khi 1 bước lỗi) đủ dùng và dễ debug hơn nhiều so với choreography-based saga đầy đủ. Sẽ đánh giá lại nếu quy mô tăng gấp 5-10 lần.
- **Database per service**: mỗi service có schema Postgres riêng (cùng 1 instance RDS nhưng khác database logic), tránh coupling chặt qua shared database — đổi lại phải chấp nhận một số dữ liệu bị denormalize nhẹ giữa các service (ví dụ `order-service` lưu snapshot giá sản phẩm tại thời điểm đặt hàng, không query ngược `catalog-service` mỗi lần cần).
- **Kong làm API Gateway thay vì tự viết middleware**: giảm thời gian phát triển, tận dụng plugin rate-limiting, JWT validation có sẵn, cộng đồng lớn hỗ trợ tốt.', 6, 294, '- **Microservice thay vì monolith**: catalog đọc nhiều (~95% traffic), inventory ghi nhiều lúc flash sale — tách riêng để scale độc lập theo tải thực tế, tránh 1 service nghẽn kéo cả hệ thống chậm theo. Đây là bài học rút ra từ hệ thống monolith Rails cũ, đã chính thức ngừng dùng từ đầu 2024 sau khi hoàn tất migration.
- **Reservation TTL 10 phút thay vì trừ kho ngay khi thêm giỏ**: cân bằng giữa trải nghiệm khách hàng (không mất hàng ngay khi vừa thêm vào giỏ, đủ thời gian cân nhắc) và tránh giữ chỗ vô thời hạn gây ra tình trạng "ảo" hết hàng khi khách bỏ giỏ hàng không mua. Con số 10 phút được A/B test và chọn dựa trên hành vi thực tế của khách hàng PhoneShop.
- **Không dùng saga pattern phức tạp cho luồng thanh toán**: với quy mô giao dịch hiện tại (dưới 10.000 đơn/ngày kể cả đỉnh điểm), orchestration đơn giản (Order Service gọi tuần tự các service khác, có compensate action rõ ràng khi 1 bước lỗi) đủ dùng và dễ debug hơn nhiều so với choreography-based saga đầy đủ. Sẽ đánh giá lại nếu quy mô tăng gấp 5-10 lần.
- **Database per service**: mỗi service có schema Postgres riêng (cùng 1 instance RDS nhưng khác database logic), tránh coupling chặt qua shared database — đổi lại phải chấp nhận một số dữ liệu bị denormalize nhẹ giữa các service (ví dụ `order-service` lưu snapshot giá sản phẩm tại thời điểm đặt hàng, không query ngược `catalog-service` mỗi lần cần).
- **Kong làm API Gateway thay vì tự viết middleware**: giảm thời gian phát triển, tận dụng plugin rate-limiting, JWT validation có sẵn, cộng đồng lớn hỗ trợ tốt.', '8cc901d1b542d0520a36b6424815780b81d60f1c78e60d51e94ea18c362ba4ad', 'pending', '', '- **Microservice thay vì monolith**: catalog đọc nhiều (~95% traffic), inventory ghi nhiều lúc flash sale — tách riêng để scale độc lập theo tải thực tế, tránh 1 service nghẽn kéo cả hệ thống chậm theo. Đây là bài học rút ra từ hệ thống monolith Rails cũ, đã chính thức ngừng dùng từ đầu 2024 sau khi hoàn tất migration.
- **Reservation TTL 10 phút thay vì trừ kho ngay khi thêm giỏ**: cân bằng giữa trải nghiệm khách hàng (không mất hàng ngay khi vừa thêm vào giỏ, đủ thời gian cân nhắc) và tránh giữ chỗ vô thời hạn gây ra tình trạng "ảo" hết hàng khi khách bỏ giỏ hàng không mua. Con số 10 phút được A/B test và chọn dựa trên hành vi thực tế của khách hàng PhoneShop.
- **Không dùng saga pattern phức tạp cho luồng thanh toán**: với quy mô giao dịch hiện tại (dưới 10.000 đơn/ngày kể cả đỉnh điểm), orchestration đơn giản (Order Service gọi tuần tự các service khác, có compensate action rõ ràng khi 1 bước lỗi) đủ dùng và dễ debug hơn nhiều so với choreography-based saga đầy đủ. Sẽ đánh giá lại nếu quy mô tăng gấp 5-10 lần.
- **Database per service**: mỗi service có schema Postgres riêng (cùng 1 instance RDS nhưng khác database logic), tránh coupling chặt qua shared database — đổi lại phải chấp nhận một số dữ liệu bị denormalize nhẹ giữa các service (ví dụ `order-service` lưu snapshot giá sản phẩm tại thời điểm đặt hàng, không query ngược `catalog-service` mỗi lần cần).
- **Kong làm API Gateway thay vì tự viết middleware**: giảm thời gian phát triển, tận dụng plugin rate-limiting, JWT validation có sẵn, cộng đồng lớn hỗ trợ tốt.'),
    ('Dashboard & alerting'::text, '- Datadog dashboard chính: `PhoneShop / Production Overview` — theo dõi latency p50/p95/p99 theo từng service, error rate, queue depth RabbitMQ, connection pool Postgres.
- Dashboard riêng: `PhoneShop / Inventory Sync Health` — theo dõi độ trễ đồng bộ giữa các chi nhánh, số lượng reservation đang active, tỷ lệ reservation hết hạn không convert thành đơn (chỉ số quan trọng để tối ưu UX giỏ hàng).
- Alert quan trọng nhất: `order-service error rate > 2% trong 5 phút` → page on-call ngay qua PagerDuty, không chờ business hours. Các alert mức thấp hơn (warning) chỉ post vào Slack, không page.', 7, 102, '- Datadog dashboard chính: `PhoneShop / Production Overview` — theo dõi latency p50/p95/p99 theo từng service, error rate, queue depth RabbitMQ, connection pool Postgres.
- Dashboard riêng: `PhoneShop / Inventory Sync Health` — theo dõi độ trễ đồng bộ giữa các chi nhánh, số lượng reservation đang active, tỷ lệ reservation hết hạn không convert thành đơn (chỉ số quan trọng để tối ưu UX giỏ hàng).
- Alert quan trọng nhất: `order-service error rate > 2% trong 5 phút` → page on-call ngay qua PagerDuty, không chờ business hours. Các alert mức thấp hơn (warning) chỉ post vào Slack, không page.', '9076c8cfa5c86929370649339e415da937a54859cb1506197644c91bfeac642a', 'pending', '', '- Datadog dashboard chính: `PhoneShop / Production Overview` — theo dõi latency p50/p95/p99 theo từng service, error rate, queue depth RabbitMQ, connection pool Postgres.
- Dashboard riêng: `PhoneShop / Inventory Sync Health` — theo dõi độ trễ đồng bộ giữa các chi nhánh, số lượng reservation đang active, tỷ lệ reservation hết hạn không convert thành đơn (chỉ số quan trọng để tối ưu UX giỏ hàng).
- Alert quan trọng nhất: `order-service error rate > 2% trong 5 phút` → page on-call ngay qua PagerDuty, không chờ business hours. Các alert mức thấp hơn (warning) chỉ post vào Slack, không page.'),
    ('Chi phí hạ tầng (tham khảo, cập nhật hàng quý)'::text, 'Chi phí AWS trung bình ~$8.500/tháng cho toàn bộ hạ tầng production (RDS, EKS, ElastiCache, S3/Cloudinary, data transfer), tăng khoảng 15-20% vào các tháng có flash sale lớn do auto-scaling. Team đang đánh giá Reserved Instance cho RDS để tối ưu chi phí cố định.', 8, 45, 'Chi phí AWS trung bình ~$8.500/tháng cho toàn bộ hạ tầng production (RDS, EKS, ElastiCache, S3/Cloudinary, data transfer), tăng khoảng 15-20% vào các tháng có flash sale lớn do auto-scaling. Team đang đánh giá Reserved Instance cho RDS để tối ưu chi phí cố định.', '66d5e25c417b75f258dbce595c57ada9da0e1b5066eb232fc5e77689df066bd2', 'pending', '', 'Chi phí AWS trung bình ~$8.500/tháng cho toàn bộ hạ tầng production (RDS, EKS, ElastiCache, S3/Cloudinary, data transfer), tăng khoảng 15-20% vào các tháng có flash sale lớn do auto-scaling. Team đang đánh giá Reserved Instance cho RDS để tối ưu chi phí cố định.')
) AS c(heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical);

-- PHONESHOP: PhoneShop API — Setup môi trường dev
WITH doc AS (
  INSERT INTO knowledge_documents
    (project_id, created_by_user_id, knowledge_domain, document_category, policy_category,
     source_key, category_confirmed, category_classification_status,
     title, source_url, status, created_at, updated_at)
  VALUES (
    (SELECT project_id FROM projects WHERE key = 'PHONESHOP'),
    (SELECT user_id FROM users WHERE email = 'pm.phoneshop@onboarding.dev'),
    'PROJECT', 'SETUP', NULL,
    'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/phoneshop/setup', true, 'CLASSIFIED',
    'PhoneShop API — Setup môi trường dev', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/phoneshop/setup', 'ACTIVE', now(), now()
  )
  RETURNING document_id
),
ver AS (
  INSERT INTO document_versions
    (document_id, version_no, revision_no, embedding_model_version,
     storage_uri, checksum, status, created_at)
  SELECT document_id, 1, 1, 'pending', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/phoneshop/setup', '5e80855649eafbe6d89f49b7170a95f6d5c8cb3dc0a56ca8168bc93c5466632a', 'ACTIVE', now() FROM doc
  RETURNING version_id
)
INSERT INTO document_chunks (version_id, heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical)
SELECT ver.version_id, c.heading, c.content, c.chunk_index, c.token_count, c.embedding_text, c.content_hash, c.embedding_model_version, c.lexical_identifiers, c.lexical_technical
FROM ver, (VALUES
    (NULL::text, '# PhoneShop API — Setup môi trường dev', 0, 8, '# PhoneShop API — Setup môi trường dev', 'f5631699317e9ad97522330abb51fd9824fcaa0e790eca0a95e5db74399b38cc', 'pending', '', '# PhoneShop API — Setup môi trường dev'),
    ('Tổng quan môi trường'::text, 'Hệ thống PhoneShop gồm 5 service backend độc lập (`catalog-service`, `order-service`, `inventory-service`, `payment-service`, `notification-service`), mỗi service là 1 repo riêng trên GitHub, nhưng đều dùng chung 1 bộ công cụ dev tiêu chuẩn để đảm bảo trải nghiệm nhất quán. Tài liệu này hướng dẫn setup cho `order-service` — service trung tâm và phức tạp nhất, các service khác setup tương tự (xem README riêng từng repo).', 1, 67, 'Hệ thống PhoneShop gồm 5 service backend độc lập (`catalog-service`, `order-service`, `inventory-service`, `payment-service`, `notification-service`), mỗi service là 1 repo riêng trên GitHub, nhưng đều dùng chung 1 bộ công cụ dev tiêu chuẩn để đảm bảo trải nghiệm nhất quán. Tài liệu này hướng dẫn setup cho `order-service` — service trung tâm và phức tạp nhất, các service khác setup tương tự (xem README riêng từng repo).', '80c9b7b3d4ea66146f738afbf2a766944e3334609928dcdb2348ff3cba8a76fe', 'pending', '', 'Hệ thống PhoneShop gồm 5 service backend độc lập (`catalog-service`, `order-service`, `inventory-service`, `payment-service`, `notification-service`), mỗi service là 1 repo riêng trên GitHub, nhưng đều dùng chung 1 bộ công cụ dev tiêu chuẩn để đảm bảo trải nghiệm nhất quán. Tài liệu này hướng dẫn setup cho `order-service` — service trung tâm và phức tạp nhất, các service khác setup tương tự (xem README riêng từng repo).'),
    ('Yêu cầu hệ thống'::text, '- **OS**: macOS, Linux, hoặc Windows với WSL2 (khuyến nghị mạnh — Docker trên Windows native chậm hơn đáng kể).
- **Python 3.11+** (dùng `pyenv` để quản lý version nếu máy có nhiều dự án Python khác version).
- **Docker + Docker Compose v2** (Docker Desktop hoặc Colima trên macOS).
- **Poetry** (quản lý dependency) — cài qua `pipx install poetry`, không dùng `pip install poetry` trực tiếp để tránh xung đột.
- **AWS CLI** đã config với credential được cấp (để pull secret từ SSM Parameter Store khi cần test tích hợp thật với các dịch vụ AWS).
- **direnv** (khuyến nghị, không bắt buộc) — tự động load biến môi trường khi `cd` vào thư mục project.', 2, 119, '- **OS**: macOS, Linux, hoặc Windows với WSL2 (khuyến nghị mạnh — Docker trên Windows native chậm hơn đáng kể).
- **Python 3.11+** (dùng `pyenv` để quản lý version nếu máy có nhiều dự án Python khác version).
- **Docker + Docker Compose v2** (Docker Desktop hoặc Colima trên macOS).
- **Poetry** (quản lý dependency) — cài qua `pipx install poetry`, không dùng `pip install poetry` trực tiếp để tránh xung đột.
- **AWS CLI** đã config với credential được cấp (để pull secret từ SSM Parameter Store khi cần test tích hợp thật với các dịch vụ AWS).
- **direnv** (khuyến nghị, không bắt buộc) — tự động load biến môi trường khi `cd` vào thư mục project.', 'eecd0268262cf745cce341c8540dc221f5fb22d0666e11c419d1fdfe9104aadd', 'pending', '', '- **OS**: macOS, Linux, hoặc Windows với WSL2 (khuyến nghị mạnh — Docker trên Windows native chậm hơn đáng kể).
- **Python 3.11+** (dùng `pyenv` để quản lý version nếu máy có nhiều dự án Python khác version).
- **Docker + Docker Compose v2** (Docker Desktop hoặc Colima trên macOS).
- **Poetry** (quản lý dependency) — cài qua `pipx install poetry`, không dùng `pip install poetry` trực tiếp để tránh xung đột.
- **AWS CLI** đã config với credential được cấp (để pull secret từ SSM Parameter Store khi cần test tích hợp thật với các dịch vụ AWS).
- **direnv** (khuyến nghị, không bắt buộc) — tự động load biến môi trường khi `cd` vào thư mục project.'),
    ('Các bước setup từ đầu'::text, '```bash
git clone git@github.com:company/phoneshop-api.git
cd phoneshop-api
poetry install                        # cài toàn bộ dependency, bao gồm dev dependency (pytest, ruff, mypy...)
cp .env.example .env                  # điền DATABASE_URL, REDIS_URL, RABBITMQ_URL theo hướng dẫn comment trong file
docker compose up -d db redis rabbitmq  # khởi động 3 service phụ thuộc, KHÔNG khởi động app (chạy app trực tiếp để dễ debug + hot reload)
poetry run alembic upgrade head        # apply toàn bộ migration lên database local
poetry run uvicorn app.main:app --reload --port 8001
```

Lần đầu setup thường mất khoảng 10-15 phút (tuỳ tốc độ pull Docker image và cài dependency Poetry).', 3, 101, '```bash
git clone git@github.com:company/phoneshop-api.git
cd phoneshop-api
poetry install                        # cài toàn bộ dependency, bao gồm dev dependency (pytest, ruff, mypy...)
cp .env.example .env                  # điền DATABASE_URL, REDIS_URL, RABBITMQ_URL theo hướng dẫn comment trong file
docker compose up -d db redis rabbitmq  # khởi động 3 service phụ thuộc, KHÔNG khởi động app (chạy app trực tiếp để dễ debug + hot reload)
poetry run alembic upgrade head        # apply toàn bộ migration lên database local
poetry run uvicorn app.main:app --reload --port 8001
```

Lần đầu setup thường mất khoảng 10-15 phút (tuỳ tốc độ pull Docker image và cài dependency Poetry).', '6bb1d034ef434ef2c5263da181b941a203b5bff10678dfb83d602bfec43392df', 'pending', '', '```bash
git clone git@github.com:company/phoneshop-api.git
cd phoneshop-api
poetry install                        # cài toàn bộ dependency, bao gồm dev dependency (pytest, ruff, mypy...)
cp .env.example .env                  # điền DATABASE_URL, REDIS_URL, RABBITMQ_URL theo hướng dẫn comment trong file
docker compose up -d db redis rabbitmq  # khởi động 3 service phụ thuộc, KHÔNG khởi động app (chạy app trực tiếp để dễ debug + hot reload)
poetry run alembic upgrade head        # apply toàn bộ migration lên database local
poetry run uvicorn app.main:app --reload --port 8001
```

Lần đầu setup thường mất khoảng 10-15 phút (tuỳ tốc độ pull Docker image và cài dependency Poetry).'),
    ('Seed data mẫu'::text, '```bash
poetry run python scripts/seed_catalog.py    # tạo ~50 sản phẩm mẫu thuộc nhiều danh mục, 5 chi nhánh giả lập
poetry run python scripts/seed_promotions.py  # tạo vài mã giảm giá demo (WELCOME10, FLASH50, GIFT_EARPHONE)
poetry run python scripts/seed_customers.py    # tạo 10 tài khoản khách hàng demo với password chuẩn "Test@1234"
```
Sau khi seed xong, có thể đăng nhập storefront local (nếu chạy kèm frontend) bằng tài khoản `demo1@phoneshop.dev` / `Test@1234`.', 4, 71, '```bash
poetry run python scripts/seed_catalog.py    # tạo ~50 sản phẩm mẫu thuộc nhiều danh mục, 5 chi nhánh giả lập
poetry run python scripts/seed_promotions.py  # tạo vài mã giảm giá demo (WELCOME10, FLASH50, GIFT_EARPHONE)
poetry run python scripts/seed_customers.py    # tạo 10 tài khoản khách hàng demo với password chuẩn "Test@1234"
```
Sau khi seed xong, có thể đăng nhập storefront local (nếu chạy kèm frontend) bằng tài khoản `demo1@phoneshop.dev` / `Test@1234`.', '9ae4585dadb58440b03fd45034f581afe47d81fdc6a6f3884ff957aac079f5cd', 'pending', '', '```bash
poetry run python scripts/seed_catalog.py    # tạo ~50 sản phẩm mẫu thuộc nhiều danh mục, 5 chi nhánh giả lập
poetry run python scripts/seed_promotions.py  # tạo vài mã giảm giá demo (WELCOME10, FLASH50, GIFT_EARPHONE)
poetry run python scripts/seed_customers.py    # tạo 10 tài khoản khách hàng demo với password chuẩn "Test@1234"
```
Sau khi seed xong, có thể đăng nhập storefront local (nếu chạy kèm frontend) bằng tài khoản `demo1@phoneshop.dev` / `Test@1234`.'),
    ('Kiểm tra chạy đúng'::text, '1. Mở `http://localhost:8001/docs` — thấy Swagger UI với các nhóm endpoint `catalog`, `orders`, `inventory`, `payments`.
2. Gọi thử `GET /health` phải trả `200 OK` với body `{"status": "ok", "dependencies": {"database": "ok", "redis": "ok"}}`.
3. Gọi `GET /api/v1/products?limit=5` phải trả về danh sách 5 sản phẩm vừa seed.
4. Thử luồng đầy đủ: tạo giỏ hàng → thêm sản phẩm → checkout (dùng payment method `COD` để không cần config cổng thanh toán thật) → xác nhận đơn hàng xuất hiện trong DB.', 5, 82, '1. Mở `http://localhost:8001/docs` — thấy Swagger UI với các nhóm endpoint `catalog`, `orders`, `inventory`, `payments`.
2. Gọi thử `GET /health` phải trả `200 OK` với body `{"status": "ok", "dependencies": {"database": "ok", "redis": "ok"}}`.
3. Gọi `GET /api/v1/products?limit=5` phải trả về danh sách 5 sản phẩm vừa seed.
4. Thử luồng đầy đủ: tạo giỏ hàng → thêm sản phẩm → checkout (dùng payment method `COD` để không cần config cổng thanh toán thật) → xác nhận đơn hàng xuất hiện trong DB.', 'ff79d88ecfa32082e074b37cc8e9a3eef12510333ef7a021752cf1909e6fa738', 'pending', '', '1. Mở `http://localhost:8001/docs` — thấy Swagger UI với các nhóm endpoint `catalog`, `orders`, `inventory`, `payments`.
2. Gọi thử `GET /health` phải trả `200 OK` với body `{"status": "ok", "dependencies": {"database": "ok", "redis": "ok"}}`.
3. Gọi `GET /api/v1/products?limit=5` phải trả về danh sách 5 sản phẩm vừa seed.
4. Thử luồng đầy đủ: tạo giỏ hàng → thêm sản phẩm → checkout (dùng payment method `COD` để không cần config cổng thanh toán thật) → xác nhận đơn hàng xuất hiện trong DB.'),
    ('Chạy test'::text, '```bash
poetry run pytest tests/unit -v                          # nhanh, không cần DB, chạy < 5 giây
poetry run pytest tests/integration -v                    # cần docker compose db/redis/rabbitmq đang chạy
poetry run pytest --cov=app --cov-report=term-missing     # coverage report, target team đặt ra: >80%
poetry run mypy app/ --strict                              # kiểm tra type hint đầy đủ
poetry run ruff check app/ tests/                            # lint
```', 6, 61, '```bash
poetry run pytest tests/unit -v                          # nhanh, không cần DB, chạy < 5 giây
poetry run pytest tests/integration -v                    # cần docker compose db/redis/rabbitmq đang chạy
poetry run pytest --cov=app --cov-report=term-missing     # coverage report, target team đặt ra: >80%
poetry run mypy app/ --strict                              # kiểm tra type hint đầy đủ
poetry run ruff check app/ tests/                            # lint
```', '4bf5886467240372771c54c2e00d5d312309fbf3bc3ec38753fc1dd57081596e', 'pending', '', '```bash
poetry run pytest tests/unit -v                          # nhanh, không cần DB, chạy < 5 giây
poetry run pytest tests/integration -v                    # cần docker compose db/redis/rabbitmq đang chạy
poetry run pytest --cov=app --cov-report=term-missing     # coverage report, target team đặt ra: >80%
poetry run mypy app/ --strict                              # kiểm tra type hint đầy đủ
poetry run ruff check app/ tests/                            # lint
```'),
    ('Lỗi thường gặp'::text, '| Lỗi | Nguyên nhân | Cách fix |
|---|---|---|
| `sqlalchemy.exc.OperationalError: connection refused` | Container `db` chưa healthy | `docker compose ps`, đợi `db` chuyển `healthy` rồi retry, thường mất 5-10 giây sau khi start |
| `pika.exceptions.AMQPConnectionError` | RabbitMQ chưa sẵn sàng hoặc sai `RABBITMQ_URL` trong `.env` | Kiểm tra `docker compose logs rabbitmq`, RabbitMQ khởi động chậm hơn Postgres ~10-15 giây |
| Alembic báo "Target database is not up to date" | Có migration mới trên `main` chưa pull/apply | `git pull`, sau đó `poetry run alembic upgrade head` |
| Import lỗi `ModuleNotFoundError: app` | Chưa activate đúng virtualenv của Poetry | Dùng `poetry run` prefix cho mọi lệnh, hoặc `poetry shell` trước khi chạy trực tiếp |
| Docker Desktop trên Windows chạy rất chậm | Chưa dùng WSL2 backend | Bật WSL2 integration trong Docker Desktop settings, clone repo vào filesystem của WSL2 (không phải `/mnt/c/...`) |
| `RuntimeError: Event loop is closed` khi chạy test | Xung đột giữa pytest-asyncio và cách quản lý connection pool async | Đảm bảo dùng đúng fixture `db_session` có sẵn trong `tests/conftest.py`, không tự tạo session riêng trong test |', 7, 194, '| Lỗi | Nguyên nhân | Cách fix |
|---|---|---|
| `sqlalchemy.exc.OperationalError: connection refused` | Container `db` chưa healthy | `docker compose ps`, đợi `db` chuyển `healthy` rồi retry, thường mất 5-10 giây sau khi start |
| `pika.exceptions.AMQPConnectionError` | RabbitMQ chưa sẵn sàng hoặc sai `RABBITMQ_URL` trong `.env` | Kiểm tra `docker compose logs rabbitmq`, RabbitMQ khởi động chậm hơn Postgres ~10-15 giây |
| Alembic báo "Target database is not up to date" | Có migration mới trên `main` chưa pull/apply | `git pull`, sau đó `poetry run alembic upgrade head` |
| Import lỗi `ModuleNotFoundError: app` | Chưa activate đúng virtualenv của Poetry | Dùng `poetry run` prefix cho mọi lệnh, hoặc `poetry shell` trước khi chạy trực tiếp |
| Docker Desktop trên Windows chạy rất chậm | Chưa dùng WSL2 backend | Bật WSL2 integration trong Docker Desktop settings, clone repo vào filesystem của WSL2 (không phải `/mnt/c/...`) |
| `RuntimeError: Event loop is closed` khi chạy test | Xung đột giữa pytest-asyncio và cách quản lý connection pool async | Đảm bảo dùng đúng fixture `db_session` có sẵn trong `tests/conftest.py`, không tự tạo session riêng trong test |', 'b9f792ac02e7f01038a5b8238532af5f86e44f3c815b64cc5f1e6d9b1551b78b', 'pending', '', '| Lỗi | Nguyên nhân | Cách fix |
|---|---|---|
| `sqlalchemy.exc.OperationalError: connection refused` | Container `db` chưa healthy | `docker compose ps`, đợi `db` chuyển `healthy` rồi retry, thường mất 5-10 giây sau khi start |
| `pika.exceptions.AMQPConnectionError` | RabbitMQ chưa sẵn sàng hoặc sai `RABBITMQ_URL` trong `.env` | Kiểm tra `docker compose logs rabbitmq`, RabbitMQ khởi động chậm hơn Postgres ~10-15 giây |
| Alembic báo "Target database is not up to date" | Có migration mới trên `main` chưa pull/apply | `git pull`, sau đó `poetry run alembic upgrade head` |
| Import lỗi `ModuleNotFoundError: app` | Chưa activate đúng virtualenv của Poetry | Dùng `poetry run` prefix cho mọi lệnh, hoặc `poetry shell` trước khi chạy trực tiếp |
| Docker Desktop trên Windows chạy rất chậm | Chưa dùng WSL2 backend | Bật WSL2 integration trong Docker Desktop settings, clone repo vào filesystem của WSL2 (không phải `/mnt/c/...`) |
| `RuntimeError: Event loop is closed` khi chạy test | Xung đột giữa pytest-asyncio và cách quản lý connection pool async | Đảm bảo dùng đúng fixture `db_session` có sẵn trong `tests/conftest.py`, không tự tạo session riêng trong test |'),
    ('CI/CD'::text, 'Push lên nhánh bất kỳ → GitHub Actions chạy lint (`ruff`) + type check (`mypy`) + test unit + test integration (dùng service container Postgres/Redis/RabbitMQ thật trong CI runner). Toàn bộ pipeline mất khoảng 6-8 phút. Merge vào `main` → tự động build Docker image, push lên ECR, ArgoCD tự động sync lên môi trường staging trong vòng 2-3 phút. Deploy production cần approve thủ công từ Tech Lead trên GitHub Actions (environment protection rule), sau đó ArgoCD sync lên production theo chiến lược rolling update (không downtime).', 8, 88, 'Push lên nhánh bất kỳ → GitHub Actions chạy lint (`ruff`) + type check (`mypy`) + test unit + test integration (dùng service container Postgres/Redis/RabbitMQ thật trong CI runner). Toàn bộ pipeline mất khoảng 6-8 phút. Merge vào `main` → tự động build Docker image, push lên ECR, ArgoCD tự động sync lên môi trường staging trong vòng 2-3 phút. Deploy production cần approve thủ công từ Tech Lead trên GitHub Actions (environment protection rule), sau đó ArgoCD sync lên production theo chiến lược rolling update (không downtime).', '1bbabd90ffb02e77aa2d3adc7beb43fd2f8acdfea60b8dda963a71db0b2f7b56', 'pending', '', 'Push lên nhánh bất kỳ → GitHub Actions chạy lint (`ruff`) + type check (`mypy`) + test unit + test integration (dùng service container Postgres/Redis/RabbitMQ thật trong CI runner). Toàn bộ pipeline mất khoảng 6-8 phút. Merge vào `main` → tự động build Docker image, push lên ECR, ArgoCD tự động sync lên môi trường staging trong vòng 2-3 phút. Deploy production cần approve thủ công từ Tech Lead trên GitHub Actions (environment protection rule), sau đó ArgoCD sync lên production theo chiến lược rolling update (không downtime).')
) AS c(heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical);

-- PHONESHOP: PhoneShop API — Access & Security
WITH doc AS (
  INSERT INTO knowledge_documents
    (project_id, created_by_user_id, knowledge_domain, document_category, policy_category,
     source_key, category_confirmed, category_classification_status,
     title, source_url, status, created_at, updated_at)
  VALUES (
    (SELECT project_id FROM projects WHERE key = 'PHONESHOP'),
    (SELECT user_id FROM users WHERE email = 'pm.phoneshop@onboarding.dev'),
    'PROJECT', 'ACCESS_SECURITY', NULL,
    'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/phoneshop/access-security', true, 'CLASSIFIED',
    'PhoneShop API — Access & Security', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/phoneshop/access-security', 'ACTIVE', now(), now()
  )
  RETURNING document_id
),
ver AS (
  INSERT INTO document_versions
    (document_id, version_no, revision_no, embedding_model_version,
     storage_uri, checksum, status, created_at)
  SELECT document_id, 1, 1, 'pending', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/phoneshop/access-security', '5109a55be03e4e77ec0a36f5a3817435bd59e3c05e8fa0ae138f06aee7a7f96b', 'ACTIVE', now() FROM doc
  RETURNING version_id
)
INSERT INTO document_chunks (version_id, heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical)
SELECT ver.version_id, c.heading, c.content, c.chunk_index, c.token_count, c.embedding_text, c.content_hash, c.embedding_model_version, c.lexical_identifiers, c.lexical_technical
FROM ver, (VALUES
    (NULL::text, '# PhoneShop API — Access & Security', 0, 7, '# PhoneShop API — Access & Security', 'b4cded21479b106a9723ef1da12ffbed1bbe82d06726775431d3b08c09239cd5', 'pending', '', '# PhoneShop API — Access & Security'),
    ('Triết lý bảo mật'::text, 'PhoneShop xử lý dữ liệu thanh toán và thông tin cá nhân của hàng trăm nghìn khách hàng, nên bảo mật được xem là ưu tiên hàng đầu ngang với tính năng sản phẩm, không phải việc "làm sau". Mọi thay đổi liên quan tới auth, payment, hoặc dữ liệu cá nhân đều bắt buộc có review từ Security team trước khi merge, không chỉ review thông thường từ Tech Lead.', 1, 71, 'PhoneShop xử lý dữ liệu thanh toán và thông tin cá nhân của hàng trăm nghìn khách hàng, nên bảo mật được xem là ưu tiên hàng đầu ngang với tính năng sản phẩm, không phải việc "làm sau". Mọi thay đổi liên quan tới auth, payment, hoặc dữ liệu cá nhân đều bắt buộc có review từ Security team trước khi merge, không chỉ review thông thường từ Tech Lead.', 'cc53a709e7d04c0335b91c48c9cabf4be0f85a97eb08de9fdb3254caeabaf94a', 'pending', '', 'PhoneShop xử lý dữ liệu thanh toán và thông tin cá nhân của hàng trăm nghìn khách hàng, nên bảo mật được xem là ưu tiên hàng đầu ngang với tính năng sản phẩm, không phải việc "làm sau". Mọi thay đổi liên quan tới auth, payment, hoặc dữ liệu cá nhân đều bắt buộc có review từ Security team trước khi merge, không chỉ review thông thường từ Tech Lead.'),
    ('Xin quyền truy cập'::text, '| Hệ thống | Cách xin | Ai duyệt | Thời gian xử lý |
|---|---|---|---|
| Repo GitHub (team `phoneshop-backend`) | PM thêm trực tiếp qua GitHub Org settings, dựa trên onboarding checklist | PM | Trong ngày làm việc đầu tiên |
| Database staging (read-only) | Xin qua kênh Slack #phoneshop-infra, kèm lý do cụ thể | Tech Lead | 1 ngày làm việc |
| Database production | KHÔNG cấp trực tiếp cho engineer thường — mọi truy cập qua bastion host có audit log đầy đủ, chỉ Lead/PM/on-call hiện tại mới có quyền | Engineering Manager | Xét duyệt riêng từng trường hợp, có thời hạn |
| VPN nội bộ | Form IT chuẩn (`it.company.com/vpn-request`), cần laptop công ty đã cài MDM | IT | 1-2 ngày làm việc |
| RabbitMQ Management UI / Datadog / Sentry | Tự động cấp khi vào team, SSO qua Google Workspace, không cần xin riêng | — | Ngay khi có tài khoản công ty |
| AWS Console (read-only staging) | Xin qua IT kèm xác nhận từ Tech Lead, MFA bắt buộc | IT + Tech Lead | 1-2 ngày làm việc |
| AWS Console production | Chỉ Engineering Manager, DevOps Lead, và on-call theo lịch mới có quyền tạm thời (time-boxed, tự động thu hồi sau 8 giờ) | Engineering Manager | Xét duyệt riêng, thường dùng khi xử lý sự cố |', 2, 241, '| Hệ thống | Cách xin | Ai duyệt | Thời gian xử lý |
|---|---|---|---|
| Repo GitHub (team `phoneshop-backend`) | PM thêm trực tiếp qua GitHub Org settings, dựa trên onboarding checklist | PM | Trong ngày làm việc đầu tiên |
| Database staging (read-only) | Xin qua kênh Slack #phoneshop-infra, kèm lý do cụ thể | Tech Lead | 1 ngày làm việc |
| Database production | KHÔNG cấp trực tiếp cho engineer thường — mọi truy cập qua bastion host có audit log đầy đủ, chỉ Lead/PM/on-call hiện tại mới có quyền | Engineering Manager | Xét duyệt riêng từng trường hợp, có thời hạn |
| VPN nội bộ | Form IT chuẩn (`it.company.com/vpn-request`), cần laptop công ty đã cài MDM | IT | 1-2 ngày làm việc |
| RabbitMQ Management UI / Datadog / Sentry | Tự động cấp khi vào team, SSO qua Google Workspace, không cần xin riêng | — | Ngay khi có tài khoản công ty |
| AWS Console (read-only staging) | Xin qua IT kèm xác nhận từ Tech Lead, MFA bắt buộc | IT + Tech Lead | 1-2 ngày làm việc |
| AWS Console production | Chỉ Engineering Manager, DevOps Lead, và on-call theo lịch mới có quyền tạm thời (time-boxed, tự động thu hồi sau 8 giờ) | Engineering Manager | Xét duyệt riêng, thường dùng khi xử lý sự cố |', '5ca4be3b9b8279aa9b1389b35382d06e55a832e1cfc91bd3a9b456147b155940', 'pending', '', '| Hệ thống | Cách xin | Ai duyệt | Thời gian xử lý |
|---|---|---|---|
| Repo GitHub (team `phoneshop-backend`) | PM thêm trực tiếp qua GitHub Org settings, dựa trên onboarding checklist | PM | Trong ngày làm việc đầu tiên |
| Database staging (read-only) | Xin qua kênh Slack #phoneshop-infra, kèm lý do cụ thể | Tech Lead | 1 ngày làm việc |
| Database production | KHÔNG cấp trực tiếp cho engineer thường — mọi truy cập qua bastion host có audit log đầy đủ, chỉ Lead/PM/on-call hiện tại mới có quyền | Engineering Manager | Xét duyệt riêng từng trường hợp, có thời hạn |
| VPN nội bộ | Form IT chuẩn (`it.company.com/vpn-request`), cần laptop công ty đã cài MDM | IT | 1-2 ngày làm việc |
| RabbitMQ Management UI / Datadog / Sentry | Tự động cấp khi vào team, SSO qua Google Workspace, không cần xin riêng | — | Ngay khi có tài khoản công ty |
| AWS Console (read-only staging) | Xin qua IT kèm xác nhận từ Tech Lead, MFA bắt buộc | IT + Tech Lead | 1-2 ngày làm việc |
| AWS Console production | Chỉ Engineering Manager, DevOps Lead, và on-call theo lịch mới có quyền tạm thời (time-boxed, tự động thu hồi sau 8 giờ) | Engineering Manager | Xét duyệt riêng, thường dùng khi xử lý sự cố |'),
    ('Quy tắc bảo mật cụ thể'::text, '- Không commit file `.env` hoặc bất kỳ credential nào lên git — dùng `git-secrets` hook đã cài sẵn để tự động chặn commit chứa pattern giống API key/token (`pre-commit` config trong repo, chạy tự động khi `poetry install` xong).
- API key cổng thanh toán (VNPay/Momo) và 3 đối tác trả góp chỉ lưu trong **AWS Secrets Manager**, service đọc qua IAM role gán cho pod Kubernetes lúc runtime — không inject qua biến môi trường plaintext ở production (khác với môi trường dev, nơi vẫn dùng `.env` cho tiện, nhưng dùng key sandbox/test riêng của từng đối tác, không phải key thật).
- Mọi endpoint liên quan tới đơn hàng/thanh toán bắt buộc có JWT hợp lệ (issued bởi Auth Service riêng, TTL 1 giờ, refresh token TTL 30 ngày, có cơ chế revoke khi phát hiện bất thường) cộng với rate limit 100 request/phút/user (Redis-backed sliding window algorithm, chặn ở tầng Kong trước khi vào tới service).
- PII khách hàng (số điện thoại, địa chỉ giao hàng, thông tin CCCD nếu có cho hồ sơ trả góp) được **mã hoá tại tầng ứng dụng** (application-level encryption dùng AWS KMS, không chỉ dựa vào encryption-at-rest của RDS) trước khi lưu Postgres — đảm bảo kể cả backup hoặc snapshot database bị lộ cũng không đọc được dữ liệu gốc.
- Log tuyệt đối không được chứa: số thẻ thanh toán, mã OTP, JWT token đầy đủ (chỉ log 6 ký tự đầu để phục vụ trace/debug), mật khẩu dưới bất kỳ hình thức nào kể cả đã hash.
- Mọi truy vấn database từ code phải dùng parameterized query (SQLAlchemy ORM tự đảm bảo điều này, nhưng nếu viết raw SQL cho tối ưu hiệu năng thì bắt buộc dùng bind parameter, tuyệt đối không string-format trực tiếp giá trị vào câu SQL).', 3, 306, '- Không commit file `.env` hoặc bất kỳ credential nào lên git — dùng `git-secrets` hook đã cài sẵn để tự động chặn commit chứa pattern giống API key/token (`pre-commit` config trong repo, chạy tự động khi `poetry install` xong).
- API key cổng thanh toán (VNPay/Momo) và 3 đối tác trả góp chỉ lưu trong **AWS Secrets Manager**, service đọc qua IAM role gán cho pod Kubernetes lúc runtime — không inject qua biến môi trường plaintext ở production (khác với môi trường dev, nơi vẫn dùng `.env` cho tiện, nhưng dùng key sandbox/test riêng của từng đối tác, không phải key thật).
- Mọi endpoint liên quan tới đơn hàng/thanh toán bắt buộc có JWT hợp lệ (issued bởi Auth Service riêng, TTL 1 giờ, refresh token TTL 30 ngày, có cơ chế revoke khi phát hiện bất thường) cộng với rate limit 100 request/phút/user (Redis-backed sliding window algorithm, chặn ở tầng Kong trước khi vào tới service).
- PII khách hàng (số điện thoại, địa chỉ giao hàng, thông tin CCCD nếu có cho hồ sơ trả góp) được **mã hoá tại tầng ứng dụng** (application-level encryption dùng AWS KMS, không chỉ dựa vào encryption-at-rest của RDS) trước khi lưu Postgres — đảm bảo kể cả backup hoặc snapshot database bị lộ cũng không đọc được dữ liệu gốc.
- Log tuyệt đối không được chứa: số thẻ thanh toán, mã OTP, JWT token đầy đủ (chỉ log 6 ký tự đầu để phục vụ trace/debug), mật khẩu dưới bất kỳ hình thức nào kể cả đã hash.
- Mọi truy vấn database từ code phải dùng parameterized query (SQLAlchemy ORM tự đảm bảo điều này, nhưng nếu viết raw SQL cho tối ưu hiệu năng thì bắt buộc dùng bind parameter, tuyệt đối không string-format trực tiếp giá trị vào câu SQL).', 'e90ab54dfdcaa96e01e482ca20639167a20535183b0b98b78962681e21009740', 'pending', '', '- Không commit file `.env` hoặc bất kỳ credential nào lên git — dùng `git-secrets` hook đã cài sẵn để tự động chặn commit chứa pattern giống API key/token (`pre-commit` config trong repo, chạy tự động khi `poetry install` xong).
- API key cổng thanh toán (VNPay/Momo) và 3 đối tác trả góp chỉ lưu trong **AWS Secrets Manager**, service đọc qua IAM role gán cho pod Kubernetes lúc runtime — không inject qua biến môi trường plaintext ở production (khác với môi trường dev, nơi vẫn dùng `.env` cho tiện, nhưng dùng key sandbox/test riêng của từng đối tác, không phải key thật).
- Mọi endpoint liên quan tới đơn hàng/thanh toán bắt buộc có JWT hợp lệ (issued bởi Auth Service riêng, TTL 1 giờ, refresh token TTL 30 ngày, có cơ chế revoke khi phát hiện bất thường) cộng với rate limit 100 request/phút/user (Redis-backed sliding window algorithm, chặn ở tầng Kong trước khi vào tới service).
- PII khách hàng (số điện thoại, địa chỉ giao hàng, thông tin CCCD nếu có cho hồ sơ trả góp) được **mã hoá tại tầng ứng dụng** (application-level encryption dùng AWS KMS, không chỉ dựa vào encryption-at-rest của RDS) trước khi lưu Postgres — đảm bảo kể cả backup hoặc snapshot database bị lộ cũng không đọc được dữ liệu gốc.
- Log tuyệt đối không được chứa: số thẻ thanh toán, mã OTP, JWT token đầy đủ (chỉ log 6 ký tự đầu để phục vụ trace/debug), mật khẩu dưới bất kỳ hình thức nào kể cả đã hash.
- Mọi truy vấn database từ code phải dùng parameterized query (SQLAlchemy ORM tự đảm bảo điều này, nhưng nếu viết raw SQL cho tối ưu hiệu năng thì bắt buộc dùng bind parameter, tuyệt đối không string-format trực tiếp giá trị vào câu SQL).'),
    ('Compliance'::text, 'Hệ thống thanh toán tuân theo checklist **PCI-DSS cấp độ SAQ-A** (không tự lưu trữ thông tin thẻ thanh toán trong hệ thống của mình, mọi giao dịch xử lý qua cổng thanh toán bên thứ 3 đã có chứng nhận PCI-DSS đầy đủ — VNPay và Momo đều đạt chuẩn này). Audit bảo mật định kỳ 6 tháng/lần do Security team nội bộ thực hiện, kèm penetration test hàng năm thuê bên thứ 3 độc lập thực hiện.

Về bảo vệ dữ liệu cá nhân, hệ thống tuân theo Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân — có cơ chế cho khách hàng yêu cầu xoá tài khoản và toàn bộ dữ liệu liên quan (quy trình xử lý trong vòng 30 ngày theo quy định).', 4, 130, 'Hệ thống thanh toán tuân theo checklist **PCI-DSS cấp độ SAQ-A** (không tự lưu trữ thông tin thẻ thanh toán trong hệ thống của mình, mọi giao dịch xử lý qua cổng thanh toán bên thứ 3 đã có chứng nhận PCI-DSS đầy đủ — VNPay và Momo đều đạt chuẩn này). Audit bảo mật định kỳ 6 tháng/lần do Security team nội bộ thực hiện, kèm penetration test hàng năm thuê bên thứ 3 độc lập thực hiện.

Về bảo vệ dữ liệu cá nhân, hệ thống tuân theo Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân — có cơ chế cho khách hàng yêu cầu xoá tài khoản và toàn bộ dữ liệu liên quan (quy trình xử lý trong vòng 30 ngày theo quy định).', '84a68752611c68516c9bcd51653db4c5e6766b42dc70fe33da4887eb03f90e77', 'pending', '', 'Hệ thống thanh toán tuân theo checklist **PCI-DSS cấp độ SAQ-A** (không tự lưu trữ thông tin thẻ thanh toán trong hệ thống của mình, mọi giao dịch xử lý qua cổng thanh toán bên thứ 3 đã có chứng nhận PCI-DSS đầy đủ — VNPay và Momo đều đạt chuẩn này). Audit bảo mật định kỳ 6 tháng/lần do Security team nội bộ thực hiện, kèm penetration test hàng năm thuê bên thứ 3 độc lập thực hiện.

Về bảo vệ dữ liệu cá nhân, hệ thống tuân theo Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân — có cơ chế cho khách hàng yêu cầu xoá tài khoản và toàn bộ dữ liệu liên quan (quy trình xử lý trong vòng 30 ngày theo quy định).'),
    ('Xử lý sự cố bảo mật'::text, 'Nếu phát hiện hoặc nghi ngờ có lỗ hổng bảo mật, dù nhỏ hay lớn:
1. Báo ngay cho Security team qua kênh #security-incident (response SLA: 15 phút trong giờ hành chính, 1 giờ ngoài giờ thông qua PagerDuty escalation).
2. Không tự ý public thông tin lỗ hổng ra ngoài dưới bất kỳ hình thức nào, kể cả trong Slack channel công khai nội bộ của công ty — kể cả khi đã fix xong, việc công bố (nếu cần) sẽ do Security team và Legal quyết định.
3. Không tự ý "thử nghiệm" khai thác lỗ hổng trên môi trường production để xác minh — báo cáo với đầy đủ thông tin tái hiện (nếu có) và để Security team xử lý.', 5, 124, 'Nếu phát hiện hoặc nghi ngờ có lỗ hổng bảo mật, dù nhỏ hay lớn:
1. Báo ngay cho Security team qua kênh #security-incident (response SLA: 15 phút trong giờ hành chính, 1 giờ ngoài giờ thông qua PagerDuty escalation).
2. Không tự ý public thông tin lỗ hổng ra ngoài dưới bất kỳ hình thức nào, kể cả trong Slack channel công khai nội bộ của công ty — kể cả khi đã fix xong, việc công bố (nếu cần) sẽ do Security team và Legal quyết định.
3. Không tự ý "thử nghiệm" khai thác lỗ hổng trên môi trường production để xác minh — báo cáo với đầy đủ thông tin tái hiện (nếu có) và để Security team xử lý.', '0d8e815216fa95c04ffc6f099a7608d701af9ca0f81bee53bf65132255cf03f9', 'pending', '', 'Nếu phát hiện hoặc nghi ngờ có lỗ hổng bảo mật, dù nhỏ hay lớn:
1. Báo ngay cho Security team qua kênh #security-incident (response SLA: 15 phút trong giờ hành chính, 1 giờ ngoài giờ thông qua PagerDuty escalation).
2. Không tự ý public thông tin lỗ hổng ra ngoài dưới bất kỳ hình thức nào, kể cả trong Slack channel công khai nội bộ của công ty — kể cả khi đã fix xong, việc công bố (nếu cần) sẽ do Security team và Legal quyết định.
3. Không tự ý "thử nghiệm" khai thác lỗ hổng trên môi trường production để xác minh — báo cáo với đầy đủ thông tin tái hiện (nếu có) và để Security team xử lý.')
) AS c(heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical);

-- PHONESHOP: PhoneShop API — Codebase Guide
WITH doc AS (
  INSERT INTO knowledge_documents
    (project_id, created_by_user_id, knowledge_domain, document_category, policy_category,
     source_key, category_confirmed, category_classification_status,
     title, source_url, status, created_at, updated_at)
  VALUES (
    (SELECT project_id FROM projects WHERE key = 'PHONESHOP'),
    (SELECT user_id FROM users WHERE email = 'pm.phoneshop@onboarding.dev'),
    'PROJECT', 'CODEBASE_GUIDE', NULL,
    'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/phoneshop/codebase-guide', true, 'CLASSIFIED',
    'PhoneShop API — Codebase Guide', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/phoneshop/codebase-guide', 'ACTIVE', now(), now()
  )
  RETURNING document_id
),
ver AS (
  INSERT INTO document_versions
    (document_id, version_no, revision_no, embedding_model_version,
     storage_uri, checksum, status, created_at)
  SELECT document_id, 1, 1, 'pending', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/phoneshop/codebase-guide', '7394810e0fadf7a8727354b0399662e2c7bb04a6b528d03a0013ad037b792703', 'ACTIVE', now() FROM doc
  RETURNING version_id
)
INSERT INTO document_chunks (version_id, heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical)
SELECT ver.version_id, c.heading, c.content, c.chunk_index, c.token_count, c.embedding_text, c.content_hash, c.embedding_model_version, c.lexical_identifiers, c.lexical_technical
FROM ver, (VALUES
    (NULL::text, '# PhoneShop API — Codebase Guide', 0, 6, '# PhoneShop API — Codebase Guide', '3392ef849508e8f753ea04463b851588a568db182a3fb7a3db44bdec43486a0c', 'pending', '', '# PhoneShop API — Codebase Guide'),
    ('Cấu trúc thư mục (mỗi service, ví dụ `order-service/`)'::text, '```
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
```', 1, 224, '```
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
```', '0bfccee35d8dfc3274154f0f85349103b6e4a983502aa27fe84395b9f52e2711', 'pending', '', '```
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
```'),
    ('Nguyên tắc kiến trúc (Clean Architecture nhẹ)'::text, 'Chiều phụ thuộc luôn đi từ ngoài vào trong: `api -> services -> domain <- infra`. `domain/` là lớp lõi, không phụ thuộc bất cứ framework hay thư viện I/O nào (không import SQLAlchemy, không import FastAPI) — điều này giúp business logic có thể test cực nhanh (không cần DB, không cần mock phức tạp) và có thể tái sử dụng nếu sau này đổi framework hoặc thêm interface khác (ví dụ CLI, gRPC).

Quy trình thêm tính năng mới, theo đúng thứ tự khuyến nghị:
1. Viết logic ở `domain/` trước (pure Python, không I/O). Ví dụ: thêm rule "đơn hàng trên 5 triệu được miễn phí ship" thì code rule này trong `domain/order.py`.
2. Viết test unit cho logic đó ngay lập tức (mock mọi dependency), đảm bảo rule đúng trước khi nối dây phần còn lại.
3. Nối dây ở `services/` — gọi domain + infra theo đúng thứ tự nghiệp vụ (ví dụ: kiểm tra tồn kho trước, sau đó mới tính giá, sau đó mới tạo giao dịch thanh toán).
4. Expose qua `api/` — router chỉ nhận request, validate bằng Pydantic schema, gọi service, trả response. Không viết logic nghiệp vụ trực tiếp trong router dưới bất kỳ hình thức nào, kể cả logic tưởng chừng đơn giản.', 2, 215, 'Chiều phụ thuộc luôn đi từ ngoài vào trong: `api -> services -> domain <- infra`. `domain/` là lớp lõi, không phụ thuộc bất cứ framework hay thư viện I/O nào (không import SQLAlchemy, không import FastAPI) — điều này giúp business logic có thể test cực nhanh (không cần DB, không cần mock phức tạp) và có thể tái sử dụng nếu sau này đổi framework hoặc thêm interface khác (ví dụ CLI, gRPC).

Quy trình thêm tính năng mới, theo đúng thứ tự khuyến nghị:
1. Viết logic ở `domain/` trước (pure Python, không I/O). Ví dụ: thêm rule "đơn hàng trên 5 triệu được miễn phí ship" thì code rule này trong `domain/order.py`.
2. Viết test unit cho logic đó ngay lập tức (mock mọi dependency), đảm bảo rule đúng trước khi nối dây phần còn lại.
3. Nối dây ở `services/` — gọi domain + infra theo đúng thứ tự nghiệp vụ (ví dụ: kiểm tra tồn kho trước, sau đó mới tính giá, sau đó mới tạo giao dịch thanh toán).
4. Expose qua `api/` — router chỉ nhận request, validate bằng Pydantic schema, gọi service, trả response. Không viết logic nghiệp vụ trực tiếp trong router dưới bất kỳ hình thức nào, kể cả logic tưởng chừng đơn giản.', 'ce3b167bda98bf5257e5b8d11ed0926f34c95cc2d79f97256f9cc346b5c312d0', 'pending', '', 'Chiều phụ thuộc luôn đi từ ngoài vào trong: `api -> services -> domain <- infra`. `domain/` là lớp lõi, không phụ thuộc bất cứ framework hay thư viện I/O nào (không import SQLAlchemy, không import FastAPI) — điều này giúp business logic có thể test cực nhanh (không cần DB, không cần mock phức tạp) và có thể tái sử dụng nếu sau này đổi framework hoặc thêm interface khác (ví dụ CLI, gRPC).

Quy trình thêm tính năng mới, theo đúng thứ tự khuyến nghị:
1. Viết logic ở `domain/` trước (pure Python, không I/O). Ví dụ: thêm rule "đơn hàng trên 5 triệu được miễn phí ship" thì code rule này trong `domain/order.py`.
2. Viết test unit cho logic đó ngay lập tức (mock mọi dependency), đảm bảo rule đúng trước khi nối dây phần còn lại.
3. Nối dây ở `services/` — gọi domain + infra theo đúng thứ tự nghiệp vụ (ví dụ: kiểm tra tồn kho trước, sau đó mới tính giá, sau đó mới tạo giao dịch thanh toán).
4. Expose qua `api/` — router chỉ nhận request, validate bằng Pydantic schema, gọi service, trả response. Không viết logic nghiệp vụ trực tiếp trong router dưới bất kỳ hình thức nào, kể cả logic tưởng chừng đơn giản.'),
    ('File quan trọng cần đọc trước khi bắt đầu code'::text, '- **`app/domain/order.py`** — toàn bộ rule tính giá, áp mã giảm giá, tính phí trả góp nằm ở đây. Đây là file có test coverage cao nhất hệ thống (95%+) vì đây là logic nhạy cảm nhất, ảnh hưởng trực tiếp tới doanh thu nếu tính sai.
- **`app/infra/inventory_repository.py`** — cách xử lý race condition khi nhiều người mua cùng lúc 1 sản phẩm sắp hết hàng (dùng `SELECT ... FOR UPDATE` để khoá pessimistic). Đọc kỹ comment giải thích trong file trước khi sửa bất cứ điều gì liên quan — đã từng có sự cố production nghiêm trọng do một thay đổi tưởng chừng vô hại ở đây (xem `overview.md` mục "Sự cố đáng chú ý").
- **`app/events/consumers/inventory_consumer.py`** — consumer RabbitMQ xử lý event trừ tồn kho, có logic retry với exponential backoff + dead-letter-queue khi xử lý thất bại 3 lần liên tiếp, tránh mất message vĩnh viễn.
- **`app/services/checkout_service.py`** — orchestrate toàn bộ luồng checkout từ đầu đến cuối, đây là nơi tốt nhất để đọc trước tiên nhằm hiểu "bức tranh lớn" trước khi đi sâu vào chi tiết từng module riêng lẻ.
- **`app/config.py`** — toàn bộ config hệ thống đọc từ biến môi trường qua Pydantic Settings, có validation nghiêm ngặt lúc startup (app sẽ fail-fast nếu thiếu biến môi trường bắt buộc, không chạy với config sai âm thầm).', 3, 227, '- **`app/domain/order.py`** — toàn bộ rule tính giá, áp mã giảm giá, tính phí trả góp nằm ở đây. Đây là file có test coverage cao nhất hệ thống (95%+) vì đây là logic nhạy cảm nhất, ảnh hưởng trực tiếp tới doanh thu nếu tính sai.
- **`app/infra/inventory_repository.py`** — cách xử lý race condition khi nhiều người mua cùng lúc 1 sản phẩm sắp hết hàng (dùng `SELECT ... FOR UPDATE` để khoá pessimistic). Đọc kỹ comment giải thích trong file trước khi sửa bất cứ điều gì liên quan — đã từng có sự cố production nghiêm trọng do một thay đổi tưởng chừng vô hại ở đây (xem `overview.md` mục "Sự cố đáng chú ý").
- **`app/events/consumers/inventory_consumer.py`** — consumer RabbitMQ xử lý event trừ tồn kho, có logic retry với exponential backoff + dead-letter-queue khi xử lý thất bại 3 lần liên tiếp, tránh mất message vĩnh viễn.
- **`app/services/checkout_service.py`** — orchestrate toàn bộ luồng checkout từ đầu đến cuối, đây là nơi tốt nhất để đọc trước tiên nhằm hiểu "bức tranh lớn" trước khi đi sâu vào chi tiết từng module riêng lẻ.
- **`app/config.py`** — toàn bộ config hệ thống đọc từ biến môi trường qua Pydantic Settings, có validation nghiêm ngặt lúc startup (app sẽ fail-fast nếu thiếu biến môi trường bắt buộc, không chạy với config sai âm thầm).', '3fe2d36a89b8077179def320fd8e7150f2d5befb7676d7a12208fc72db2660b3', 'pending', '', '- **`app/domain/order.py`** — toàn bộ rule tính giá, áp mã giảm giá, tính phí trả góp nằm ở đây. Đây là file có test coverage cao nhất hệ thống (95%+) vì đây là logic nhạy cảm nhất, ảnh hưởng trực tiếp tới doanh thu nếu tính sai.
- **`app/infra/inventory_repository.py`** — cách xử lý race condition khi nhiều người mua cùng lúc 1 sản phẩm sắp hết hàng (dùng `SELECT ... FOR UPDATE` để khoá pessimistic). Đọc kỹ comment giải thích trong file trước khi sửa bất cứ điều gì liên quan — đã từng có sự cố production nghiêm trọng do một thay đổi tưởng chừng vô hại ở đây (xem `overview.md` mục "Sự cố đáng chú ý").
- **`app/events/consumers/inventory_consumer.py`** — consumer RabbitMQ xử lý event trừ tồn kho, có logic retry với exponential backoff + dead-letter-queue khi xử lý thất bại 3 lần liên tiếp, tránh mất message vĩnh viễn.
- **`app/services/checkout_service.py`** — orchestrate toàn bộ luồng checkout từ đầu đến cuối, đây là nơi tốt nhất để đọc trước tiên nhằm hiểu "bức tranh lớn" trước khi đi sâu vào chi tiết từng module riêng lẻ.
- **`app/config.py`** — toàn bộ config hệ thống đọc từ biến môi trường qua Pydantic Settings, có validation nghiêm ngặt lúc startup (app sẽ fail-fast nếu thiếu biến môi trường bắt buộc, không chạy với config sai âm thầm).'),
    ('Testing strategy'::text, '- **Unit test**: mock toàn bộ I/O (DB, Redis, RabbitMQ, HTTP client gọi service khác), toàn bộ suite chạy dưới 5 giây, chạy được ngay cả khi không có Docker.
- **Integration test**: dùng thư viện `testcontainers-python` để tự động dựng Postgres + Redis thật trong Docker cho mỗi lần chạy CI, đảm bảo test sát với môi trường thật nhất có thể, tránh tình trạng "test pass nhưng production lỗi" do khác biệt giữa mock và DB thật.
- **Contract test** (giữa các service): dùng Pact framework, đảm bảo `order-service` và `inventory-service` không vô tình phá vỡ hợp đồng API khi một bên thay đổi — chạy tự động trong CI của cả 2 repo, nếu contract không khớp thì build fail ngay, không phải chờ tới khi deploy mới phát hiện.
- **Load test**: chạy định kỳ trước mỗi đợt flash sale lớn bằng k6, mô phỏng tải gấp 1.5-2 lần dự kiến để đảm bảo hệ thống chịu được, kết quả lưu lại để so sánh xu hướng theo thời gian.', 4, 174, '- **Unit test**: mock toàn bộ I/O (DB, Redis, RabbitMQ, HTTP client gọi service khác), toàn bộ suite chạy dưới 5 giây, chạy được ngay cả khi không có Docker.
- **Integration test**: dùng thư viện `testcontainers-python` để tự động dựng Postgres + Redis thật trong Docker cho mỗi lần chạy CI, đảm bảo test sát với môi trường thật nhất có thể, tránh tình trạng "test pass nhưng production lỗi" do khác biệt giữa mock và DB thật.
- **Contract test** (giữa các service): dùng Pact framework, đảm bảo `order-service` và `inventory-service` không vô tình phá vỡ hợp đồng API khi một bên thay đổi — chạy tự động trong CI của cả 2 repo, nếu contract không khớp thì build fail ngay, không phải chờ tới khi deploy mới phát hiện.
- **Load test**: chạy định kỳ trước mỗi đợt flash sale lớn bằng k6, mô phỏng tải gấp 1.5-2 lần dự kiến để đảm bảo hệ thống chịu được, kết quả lưu lại để so sánh xu hướng theo thời gian.', '0a8ce57eb313ada4e438f1ddbe97bd827879c04b6fb08b64153b18a0ba8cc8f2', 'pending', '', '- **Unit test**: mock toàn bộ I/O (DB, Redis, RabbitMQ, HTTP client gọi service khác), toàn bộ suite chạy dưới 5 giây, chạy được ngay cả khi không có Docker.
- **Integration test**: dùng thư viện `testcontainers-python` để tự động dựng Postgres + Redis thật trong Docker cho mỗi lần chạy CI, đảm bảo test sát với môi trường thật nhất có thể, tránh tình trạng "test pass nhưng production lỗi" do khác biệt giữa mock và DB thật.
- **Contract test** (giữa các service): dùng Pact framework, đảm bảo `order-service` và `inventory-service` không vô tình phá vỡ hợp đồng API khi một bên thay đổi — chạy tự động trong CI của cả 2 repo, nếu contract không khớp thì build fail ngay, không phải chờ tới khi deploy mới phát hiện.
- **Load test**: chạy định kỳ trước mỗi đợt flash sale lớn bằng k6, mô phỏng tải gấp 1.5-2 lần dự kiến để đảm bảo hệ thống chịu được, kết quả lưu lại để so sánh xu hướng theo thời gian.'),
    ('Feature flag'::text, 'Tính năng mới có rủi ro cao hoặc thay đổi logic nhạy cảm (ví dụ: đổi thuật toán tính phí trả góp, đổi logic reservation) nên bọc qua feature flag (LaunchDarkly), bật dần theo phần trăm traffic (thường bắt đầu 5% → 25% → 50% → 100% qua vài ngày, theo dõi metric liên tục) thay vì release toàn bộ 1 lần cho tất cả người dùng. Cách làm này đã áp dụng thành công cho lần đổi logic reservation tháng 3/2025 sau sự cố race condition, giúp phát hiện sớm vấn đề còn sót ở mức 5% traffic thay vì ảnh hưởng toàn bộ khách hàng.', 5, 107, 'Tính năng mới có rủi ro cao hoặc thay đổi logic nhạy cảm (ví dụ: đổi thuật toán tính phí trả góp, đổi logic reservation) nên bọc qua feature flag (LaunchDarkly), bật dần theo phần trăm traffic (thường bắt đầu 5% → 25% → 50% → 100% qua vài ngày, theo dõi metric liên tục) thay vì release toàn bộ 1 lần cho tất cả người dùng. Cách làm này đã áp dụng thành công cho lần đổi logic reservation tháng 3/2025 sau sự cố race condition, giúp phát hiện sớm vấn đề còn sót ở mức 5% traffic thay vì ảnh hưởng toàn bộ khách hàng.', 'c0439f5ad110f9220523d6418538261141e62a1f04504453a5b308bda2e55355', 'pending', '', 'Tính năng mới có rủi ro cao hoặc thay đổi logic nhạy cảm (ví dụ: đổi thuật toán tính phí trả góp, đổi logic reservation) nên bọc qua feature flag (LaunchDarkly), bật dần theo phần trăm traffic (thường bắt đầu 5% → 25% → 50% → 100% qua vài ngày, theo dõi metric liên tục) thay vì release toàn bộ 1 lần cho tất cả người dùng. Cách làm này đã áp dụng thành công cho lần đổi logic reservation tháng 3/2025 sau sự cố race condition, giúp phát hiện sớm vấn đề còn sót ở mức 5% traffic thay vì ảnh hưởng toàn bộ khách hàng.')
) AS c(heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical);

-- PHONESHOP: PhoneShop API — Coding Convention
WITH doc AS (
  INSERT INTO knowledge_documents
    (project_id, created_by_user_id, knowledge_domain, document_category, policy_category,
     source_key, category_confirmed, category_classification_status,
     title, source_url, status, created_at, updated_at)
  VALUES (
    (SELECT project_id FROM projects WHERE key = 'PHONESHOP'),
    (SELECT user_id FROM users WHERE email = 'pm.phoneshop@onboarding.dev'),
    'PROJECT', 'CONVENTION', NULL,
    'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/phoneshop/convention', true, 'CLASSIFIED',
    'PhoneShop API — Coding Convention', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/phoneshop/convention', 'ACTIVE', now(), now()
  )
  RETURNING document_id
),
ver AS (
  INSERT INTO document_versions
    (document_id, version_no, revision_no, embedding_model_version,
     storage_uri, checksum, status, created_at)
  SELECT document_id, 1, 1, 'pending', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/phoneshop/convention', '002d729dafee29b7159bca9a4ce82b74e246bb2d546faf1af31297adec7d6834', 'ACTIVE', now() FROM doc
  RETURNING version_id
)
INSERT INTO document_chunks (version_id, heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical)
SELECT ver.version_id, c.heading, c.content, c.chunk_index, c.token_count, c.embedding_text, c.content_hash, c.embedding_model_version, c.lexical_identifiers, c.lexical_technical
FROM ver, (VALUES
    (NULL::text, '# PhoneShop API — Coding Convention', 0, 6, '# PhoneShop API — Coding Convention', '9ae3f5a14d66edd485fa75cfb4312c77637022d0073e7ebf5c668bd92c2a4333', 'pending', '', '# PhoneShop API — Coding Convention'),
    ('Triết lý chung'::text, 'Convention tồn tại để giảm chi phí quyết định lặp lại và giảm ma sát khi review code, không phải để gò bó sáng tạo. Mọi rule dưới đây đều nên tự động hoá qua tool (lint, format, CI check) thay vì dựa vào con người nhớ và nhắc nhau bằng tay — nếu 1 rule không thể tự động kiểm tra được, cân nhắc xem có thực sự cần thiết không.', 1, 72, 'Convention tồn tại để giảm chi phí quyết định lặp lại và giảm ma sát khi review code, không phải để gò bó sáng tạo. Mọi rule dưới đây đều nên tự động hoá qua tool (lint, format, CI check) thay vì dựa vào con người nhớ và nhắc nhau bằng tay — nếu 1 rule không thể tự động kiểm tra được, cân nhắc xem có thực sự cần thiết không.', '29b72bc47d5343926157702734533f44cf30b9d0fe2ae00d2d0e5eae5735e25c', 'pending', '', 'Convention tồn tại để giảm chi phí quyết định lặp lại và giảm ma sát khi review code, không phải để gò bó sáng tạo. Mọi rule dưới đây đều nên tự động hoá qua tool (lint, format, CI check) thay vì dựa vào con người nhớ và nhắc nhau bằng tay — nếu 1 rule không thể tự động kiểm tra được, cân nhắc xem có thực sự cần thiết không.'),
    ('Python style'::text, '- Format bằng `black` (line length 100) + `ruff` (lint, thay thế cho flake8/isort/nhiều plugin khác), chạy tự động qua pre-commit hook — không format tay, không tranh cãi về style trong PR review vì tool đã quyết định sẵn.
- Type hint bắt buộc cho mọi function public (kiểm tra bằng `mypy --strict` trong CI, fail build ngay nếu thiếu type hint hoặc type không khớp).
- Đặt tên: `snake_case` cho function/biến, `PascalCase` cho class, hằng số `UPPER_SNAKE_CASE`, private method/biến prefix `_` (single underscore, không dùng double underscore trừ khi thực sự cần name mangling).
- Docstring theo Google style cho mọi public function trong `domain/` và `services/` (không bắt buộc cho `api/` vì FastAPI tự sinh docs từ type hint + `Field(description=...)` trong Pydantic schema).
- Không dùng `# type: ignore` để né lỗi mypy trừ khi có comment giải thích rõ lý do và đã thảo luận với Tech Lead — mypy ignore tràn lan là dấu hiệu type hint đang không phản ánh đúng thực tế code.', 2, 171, '- Format bằng `black` (line length 100) + `ruff` (lint, thay thế cho flake8/isort/nhiều plugin khác), chạy tự động qua pre-commit hook — không format tay, không tranh cãi về style trong PR review vì tool đã quyết định sẵn.
- Type hint bắt buộc cho mọi function public (kiểm tra bằng `mypy --strict` trong CI, fail build ngay nếu thiếu type hint hoặc type không khớp).
- Đặt tên: `snake_case` cho function/biến, `PascalCase` cho class, hằng số `UPPER_SNAKE_CASE`, private method/biến prefix `_` (single underscore, không dùng double underscore trừ khi thực sự cần name mangling).
- Docstring theo Google style cho mọi public function trong `domain/` và `services/` (không bắt buộc cho `api/` vì FastAPI tự sinh docs từ type hint + `Field(description=...)` trong Pydantic schema).
- Không dùng `# type: ignore` để né lỗi mypy trừ khi có comment giải thích rõ lý do và đã thảo luận với Tech Lead — mypy ignore tràn lan là dấu hiệu type hint đang không phản ánh đúng thực tế code.', 'f6952846b49838b1df021c9bf683e25d8d7a4c532ccce1ddbe20ff74ae316cdb', 'pending', '', '- Format bằng `black` (line length 100) + `ruff` (lint, thay thế cho flake8/isort/nhiều plugin khác), chạy tự động qua pre-commit hook — không format tay, không tranh cãi về style trong PR review vì tool đã quyết định sẵn.
- Type hint bắt buộc cho mọi function public (kiểm tra bằng `mypy --strict` trong CI, fail build ngay nếu thiếu type hint hoặc type không khớp).
- Đặt tên: `snake_case` cho function/biến, `PascalCase` cho class, hằng số `UPPER_SNAKE_CASE`, private method/biến prefix `_` (single underscore, không dùng double underscore trừ khi thực sự cần name mangling).
- Docstring theo Google style cho mọi public function trong `domain/` và `services/` (không bắt buộc cho `api/` vì FastAPI tự sinh docs từ type hint + `Field(description=...)` trong Pydantic schema).
- Không dùng `# type: ignore` để né lỗi mypy trừ khi có comment giải thích rõ lý do và đã thảo luận với Tech Lead — mypy ignore tràn lan là dấu hiệu type hint đang không phản ánh đúng thực tế code.'),
    ('Cấu trúc import'::text, 'Sắp xếp theo 3 nhóm, cách nhau 1 dòng trống, tự động qua `ruff` isort rule: (1) standard library, (2) third-party package, (3) import nội bộ project (`app.*`). Không dùng wildcard import (`from x import *`) dưới bất kỳ hoàn cảnh nào.', 3, 42, 'Sắp xếp theo 3 nhóm, cách nhau 1 dòng trống, tự động qua `ruff` isort rule: (1) standard library, (2) third-party package, (3) import nội bộ project (`app.*`). Không dùng wildcard import (`from x import *`) dưới bất kỳ hoàn cảnh nào.', 'b3491344e376a369593d7b32414a9ece3561bf0e1009910fbc30bcc2f64415a3', 'pending', '', 'Sắp xếp theo 3 nhóm, cách nhau 1 dòng trống, tự động qua `ruff` isort rule: (1) standard library, (2) third-party package, (3) import nội bộ project (`app.*`). Không dùng wildcard import (`from x import *`) dưới bất kỳ hoàn cảnh nào.'),
    ('Git'::text, '- Nhánh đặt tên `feature/<mã-task>-mo-ta-ngan`, ví dụ `feature/PHONE-123-them-loc-theo-gia`. Hotfix khẩn cấp: `hotfix/<mã-task>-mo-ta-ngan`, được phép merge thẳng từ `hotfix/*` vào `main` sau khi 1 Senior approve (không cần đợi qua staging đầy đủ nếu là sự cố production nghiêm trọng).
- Commit message theo chuẩn Conventional Commits: `feat:`, `fix:`, `refactor:`, `test:`, `chore:`, `docs:`, `perf:`. Ví dụ tốt: `feat(order): them ho tro ma giam gia theo % cho don hang tren 5 trieu`.
- PR bắt buộc có ít nhất 1 approve từ Tech Lead hoặc Senior engineer + toàn bộ CI check xanh mới được merge, dùng **squash merge** để giữ lịch sử `main` sạch sẽ, mỗi PR tương ứng đúng 1 commit trên `main`.
- Branch protection bật trên `main`: không cho push trực tiếp dưới mọi hình thức (kể cả admin), bắt buộc qua PR, bắt buộc status check pass (lint, type check, unit test, integration test), bắt buộc branch up-to-date với `main` trước khi merge.
- PR nên giữ kích thước nhỏ, khuyến nghị dưới 400 dòng thay đổi (không tính file generated/lock file) — PR lớn hơn nên cân nhắc chia nhỏ, dễ review hơn và giảm rủi ro khi cần revert.', 4, 195, '- Nhánh đặt tên `feature/<mã-task>-mo-ta-ngan`, ví dụ `feature/PHONE-123-them-loc-theo-gia`. Hotfix khẩn cấp: `hotfix/<mã-task>-mo-ta-ngan`, được phép merge thẳng từ `hotfix/*` vào `main` sau khi 1 Senior approve (không cần đợi qua staging đầy đủ nếu là sự cố production nghiêm trọng).
- Commit message theo chuẩn Conventional Commits: `feat:`, `fix:`, `refactor:`, `test:`, `chore:`, `docs:`, `perf:`. Ví dụ tốt: `feat(order): them ho tro ma giam gia theo % cho don hang tren 5 trieu`.
- PR bắt buộc có ít nhất 1 approve từ Tech Lead hoặc Senior engineer + toàn bộ CI check xanh mới được merge, dùng **squash merge** để giữ lịch sử `main` sạch sẽ, mỗi PR tương ứng đúng 1 commit trên `main`.
- Branch protection bật trên `main`: không cho push trực tiếp dưới mọi hình thức (kể cả admin), bắt buộc qua PR, bắt buộc status check pass (lint, type check, unit test, integration test), bắt buộc branch up-to-date với `main` trước khi merge.
- PR nên giữ kích thước nhỏ, khuyến nghị dưới 400 dòng thay đổi (không tính file generated/lock file) — PR lớn hơn nên cân nhắc chia nhỏ, dễ review hơn và giảm rủi ro khi cần revert.', '63892e6b65c36191a58967cd80edd99d87045123a479ade23ebff8d6d124dbc2', 'pending', '', '- Nhánh đặt tên `feature/<mã-task>-mo-ta-ngan`, ví dụ `feature/PHONE-123-them-loc-theo-gia`. Hotfix khẩn cấp: `hotfix/<mã-task>-mo-ta-ngan`, được phép merge thẳng từ `hotfix/*` vào `main` sau khi 1 Senior approve (không cần đợi qua staging đầy đủ nếu là sự cố production nghiêm trọng).
- Commit message theo chuẩn Conventional Commits: `feat:`, `fix:`, `refactor:`, `test:`, `chore:`, `docs:`, `perf:`. Ví dụ tốt: `feat(order): them ho tro ma giam gia theo % cho don hang tren 5 trieu`.
- PR bắt buộc có ít nhất 1 approve từ Tech Lead hoặc Senior engineer + toàn bộ CI check xanh mới được merge, dùng **squash merge** để giữ lịch sử `main` sạch sẽ, mỗi PR tương ứng đúng 1 commit trên `main`.
- Branch protection bật trên `main`: không cho push trực tiếp dưới mọi hình thức (kể cả admin), bắt buộc qua PR, bắt buộc status check pass (lint, type check, unit test, integration test), bắt buộc branch up-to-date với `main` trước khi merge.
- PR nên giữ kích thước nhỏ, khuyến nghị dưới 400 dòng thay đổi (không tính file generated/lock file) — PR lớn hơn nên cân nhắc chia nhỏ, dễ review hơn và giảm rủi ro khi cần revert.'),
    ('Review checklist (template có sẵn trong `.github/PULL_REQUEST_TEMPLATE.md`, tự động điền khi tạo PR)'::text, '- [ ] Có test cho logic mới/thay đổi, coverage tổng thể không giảm so với `main` (CI tự check qua Codecov).
- [ ] Không hardcode credential, URL môi trường, hoặc magic number không có giải thích.
- [ ] Migration (nếu có) đã test cả chiều upgrade lẫn downgrade, đã kiểm tra không lock table quá lâu trên các bảng lớn (`orders` hiện có hơn 2 triệu row, `inventory` cập nhật liên tục — cần cẩn trọng đặc biệt).
- [ ] Nếu đổi API contract (thêm/xoá/đổi field response), đã cập nhật OpenAPI spec và báo trước cho team frontend/mobile ít nhất 1 ngày trước khi merge.
- [ ] Nếu thêm tính năng rủi ro cao hoặc thay đổi logic nhạy cảm (giá, tồn kho, thanh toán), đã bọc qua feature flag và có kế hoạch rollout dần.
- [ ] Log thêm mới (nếu có) không chứa thông tin nhạy cảm (xem `access-security.md`).', 5, 157, '- [ ] Có test cho logic mới/thay đổi, coverage tổng thể không giảm so với `main` (CI tự check qua Codecov).
- [ ] Không hardcode credential, URL môi trường, hoặc magic number không có giải thích.
- [ ] Migration (nếu có) đã test cả chiều upgrade lẫn downgrade, đã kiểm tra không lock table quá lâu trên các bảng lớn (`orders` hiện có hơn 2 triệu row, `inventory` cập nhật liên tục — cần cẩn trọng đặc biệt).
- [ ] Nếu đổi API contract (thêm/xoá/đổi field response), đã cập nhật OpenAPI spec và báo trước cho team frontend/mobile ít nhất 1 ngày trước khi merge.
- [ ] Nếu thêm tính năng rủi ro cao hoặc thay đổi logic nhạy cảm (giá, tồn kho, thanh toán), đã bọc qua feature flag và có kế hoạch rollout dần.
- [ ] Log thêm mới (nếu có) không chứa thông tin nhạy cảm (xem `access-security.md`).', '3b33b240e5b40ec4c5b4a0dc3a48ffc1074ddc047f92f6fed831c98bf7cf2cb1', 'pending', '', '- [ ] Có test cho logic mới/thay đổi, coverage tổng thể không giảm so với `main` (CI tự check qua Codecov).
- [ ] Không hardcode credential, URL môi trường, hoặc magic number không có giải thích.
- [ ] Migration (nếu có) đã test cả chiều upgrade lẫn downgrade, đã kiểm tra không lock table quá lâu trên các bảng lớn (`orders` hiện có hơn 2 triệu row, `inventory` cập nhật liên tục — cần cẩn trọng đặc biệt).
- [ ] Nếu đổi API contract (thêm/xoá/đổi field response), đã cập nhật OpenAPI spec và báo trước cho team frontend/mobile ít nhất 1 ngày trước khi merge.
- [ ] Nếu thêm tính năng rủi ro cao hoặc thay đổi logic nhạy cảm (giá, tồn kho, thanh toán), đã bọc qua feature flag và có kế hoạch rollout dần.
- [ ] Log thêm mới (nếu có) không chứa thông tin nhạy cảm (xem `access-security.md`).'),
    ('SLA review PR'::text, 'Team cam kết review PR trong vòng 4 giờ làm việc kể từ lúc gắn reviewer (không tính ngoài giờ hành chính và cuối tuần). Nếu quá hạn, tác giả PR nên tag lại trực tiếp trên Slack #phoneshop-backend thay vì chờ đợi thụ động. PR liên quan tới sự cố production (hotfix) được ưu tiên review ngay lập tức, không chờ hàng đợi thông thường.', 6, 66, 'Team cam kết review PR trong vòng 4 giờ làm việc kể từ lúc gắn reviewer (không tính ngoài giờ hành chính và cuối tuần). Nếu quá hạn, tác giả PR nên tag lại trực tiếp trên Slack #phoneshop-backend thay vì chờ đợi thụ động. PR liên quan tới sự cố production (hotfix) được ưu tiên review ngay lập tức, không chờ hàng đợi thông thường.', '6fcff1080b67ef7fb374336ebbfe8b8476719a67b61869c840efb521502397a4', 'pending', '', 'Team cam kết review PR trong vòng 4 giờ làm việc kể từ lúc gắn reviewer (không tính ngoài giờ hành chính và cuối tuần). Nếu quá hạn, tác giả PR nên tag lại trực tiếp trên Slack #phoneshop-backend thay vì chờ đợi thụ động. PR liên quan tới sự cố production (hotfix) được ưu tiên review ngay lập tức, không chờ hàng đợi thông thường.'),
    ('Đặt tên API endpoint'::text, 'REST endpoint dùng danh từ số nhiều, kebab-case cho path nhiều từ: `GET /api/v1/products`, `POST /api/v1/orders`, `GET /api/v1/installment-applications/{id}`. Không dùng động từ trong path (tránh `POST /api/v1/create-order`, dùng `POST /api/v1/orders`). Versioning qua path prefix (`/api/v1/`, `/api/v2/`), không dùng header versioning.', 7, 40, 'REST endpoint dùng danh từ số nhiều, kebab-case cho path nhiều từ: `GET /api/v1/products`, `POST /api/v1/orders`, `GET /api/v1/installment-applications/{id}`. Không dùng động từ trong path (tránh `POST /api/v1/create-order`, dùng `POST /api/v1/orders`). Versioning qua path prefix (`/api/v1/`, `/api/v2/`), không dùng header versioning.', '31720ffb8d58c63c1bdd89154414bb7bbf4662b8320488c145b8a9b39ad3164c', 'pending', '', 'REST endpoint dùng danh từ số nhiều, kebab-case cho path nhiều từ: `GET /api/v1/products`, `POST /api/v1/orders`, `GET /api/v1/installment-applications/{id}`. Không dùng động từ trong path (tránh `POST /api/v1/create-order`, dùng `POST /api/v1/orders`). Versioning qua path prefix (`/api/v1/`, `/api/v2/`), không dùng header versioning.')
) AS c(heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical);

-- PHONESHOP: PhoneShop API — First Task gợi ý cho engineer mới
WITH doc AS (
  INSERT INTO knowledge_documents
    (project_id, created_by_user_id, knowledge_domain, document_category, policy_category,
     source_key, category_confirmed, category_classification_status,
     title, source_url, status, created_at, updated_at)
  VALUES (
    (SELECT project_id FROM projects WHERE key = 'PHONESHOP'),
    (SELECT user_id FROM users WHERE email = 'pm.phoneshop@onboarding.dev'),
    'PROJECT', 'FIRST_TASK', NULL,
    'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/phoneshop/first-task', true, 'CLASSIFIED',
    'PhoneShop API — First Task gợi ý cho engineer mới', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/phoneshop/first-task', 'ACTIVE', now(), now()
  )
  RETURNING document_id
),
ver AS (
  INSERT INTO document_versions
    (document_id, version_no, revision_no, embedding_model_version,
     storage_uri, checksum, status, created_at)
  SELECT document_id, 1, 1, 'pending', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/phoneshop/first-task', '26c8347f5b0852f523af78a4b96e89d8bd7360464660f2b4f2d931a3a41bae6a', 'ACTIVE', now() FROM doc
  RETURNING version_id
)
INSERT INTO document_chunks (version_id, heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical)
SELECT ver.version_id, c.heading, c.content, c.chunk_index, c.token_count, c.embedding_text, c.content_hash, c.embedding_model_version, c.lexical_identifiers, c.lexical_technical
FROM ver, (VALUES
    (NULL::text, '# PhoneShop API — First Task gợi ý cho engineer mới', 0, 11, '# PhoneShop API — First Task gợi ý cho engineer mới', 'fc4099ba68736d49be7c898e4bfea515dadea45558c89e41992446304b0063df', 'pending', '', '# PhoneShop API — First Task gợi ý cho engineer mới'),
    ('Mục đích của giai đoạn First Task'::text, 'Trước khi giao bất kỳ task nghiệp vụ phức tạp nào, mọi engineer mới tại PhoneShop đều bắt đầu bằng 1-2 task nhỏ, rủi ro thấp nhưng đi qua đầy đủ luồng `api -> service -> domain -> infra` để làm quen codebase thật, quy trình review PR thật, và pipeline CI/CD thật — thay vì chỉ đọc tài liệu suông. Mục tiêu không phải tốc độ mà là hiểu đúng cách hệ thống vận hành trước khi động vào logic quan trọng như tính giá hay tồn kho.', 1, 89, 'Trước khi giao bất kỳ task nghiệp vụ phức tạp nào, mọi engineer mới tại PhoneShop đều bắt đầu bằng 1-2 task nhỏ, rủi ro thấp nhưng đi qua đầy đủ luồng `api -> service -> domain -> infra` để làm quen codebase thật, quy trình review PR thật, và pipeline CI/CD thật — thay vì chỉ đọc tài liệu suông. Mục tiêu không phải tốc độ mà là hiểu đúng cách hệ thống vận hành trước khi động vào logic quan trọng như tính giá hay tồn kho.', '8e708b6f2a443a1b3f468483f99c9bdc3982db16d53ae2b114177f192d549cb6', 'pending', '', 'Trước khi giao bất kỳ task nghiệp vụ phức tạp nào, mọi engineer mới tại PhoneShop đều bắt đầu bằng 1-2 task nhỏ, rủi ro thấp nhưng đi qua đầy đủ luồng `api -> service -> domain -> infra` để làm quen codebase thật, quy trình review PR thật, và pipeline CI/CD thật — thay vì chỉ đọc tài liệu suông. Mục tiêu không phải tốc độ mà là hiểu đúng cách hệ thống vận hành trước khi động vào logic quan trọng như tính giá hay tồn kho.'),
    ('Task khởi động #1: Thêm filter tồn kho > 0 vào API tìm kiếm sản phẩm'::text, '**Mục tiêu**: giúp bạn làm quen luồng `api -> service -> repository` mà không cần đụng vào logic phức tạp (thanh toán, tồn kho race condition).

**Các bước cụ thể**:
1. Đọc `app/api/catalog_router.py` (trong `catalog-service`), tìm endpoint `GET /products`.
2. Thêm query param mới `in_stock_only: bool = False` vào Pydantic schema request.
3. Khi `True`, filter thêm điều kiện `stock_quantity > 0` ở tầng `app/infra/product_repository.py` — chú ý đây là query join với bảng `inventory` từ `inventory-service` qua replicated view, không phải join trực tiếp cross-database.
4. Viết 1 test integration ở `tests/integration/test_catalog.py` xác nhận filter hoạt động đúng với ít nhất 2 case: có sản phẩm hết hàng bị loại ra, sản phẩm còn hàng vẫn hiển thị.
5. Cập nhật OpenAPI description cho param mới (dùng `Query(..., description="...")` trong FastAPI).
6. Tạo PR, gắn label `good-first-issue`, tag Tech Lead review.

Task này thường mất 0.5–1 ngày cho engineer mới, đủ để làm quen codebase mà không rủi ro phá vỡ tính năng quan trọng đang chạy production.', 2, 169, '**Mục tiêu**: giúp bạn làm quen luồng `api -> service -> repository` mà không cần đụng vào logic phức tạp (thanh toán, tồn kho race condition).

**Các bước cụ thể**:
1. Đọc `app/api/catalog_router.py` (trong `catalog-service`), tìm endpoint `GET /products`.
2. Thêm query param mới `in_stock_only: bool = False` vào Pydantic schema request.
3. Khi `True`, filter thêm điều kiện `stock_quantity > 0` ở tầng `app/infra/product_repository.py` — chú ý đây là query join với bảng `inventory` từ `inventory-service` qua replicated view, không phải join trực tiếp cross-database.
4. Viết 1 test integration ở `tests/integration/test_catalog.py` xác nhận filter hoạt động đúng với ít nhất 2 case: có sản phẩm hết hàng bị loại ra, sản phẩm còn hàng vẫn hiển thị.
5. Cập nhật OpenAPI description cho param mới (dùng `Query(..., description="...")` trong FastAPI).
6. Tạo PR, gắn label `good-first-issue`, tag Tech Lead review.

Task này thường mất 0.5–1 ngày cho engineer mới, đủ để làm quen codebase mà không rủi ro phá vỡ tính năng quan trọng đang chạy production.', 'ed043027c1e23ba7539ec50e6de8f5ca21fb8ba616e54d657aad9cda7769ffd1', 'pending', '', '**Mục tiêu**: giúp bạn làm quen luồng `api -> service -> repository` mà không cần đụng vào logic phức tạp (thanh toán, tồn kho race condition).

**Các bước cụ thể**:
1. Đọc `app/api/catalog_router.py` (trong `catalog-service`), tìm endpoint `GET /products`.
2. Thêm query param mới `in_stock_only: bool = False` vào Pydantic schema request.
3. Khi `True`, filter thêm điều kiện `stock_quantity > 0` ở tầng `app/infra/product_repository.py` — chú ý đây là query join với bảng `inventory` từ `inventory-service` qua replicated view, không phải join trực tiếp cross-database.
4. Viết 1 test integration ở `tests/integration/test_catalog.py` xác nhận filter hoạt động đúng với ít nhất 2 case: có sản phẩm hết hàng bị loại ra, sản phẩm còn hàng vẫn hiển thị.
5. Cập nhật OpenAPI description cho param mới (dùng `Query(..., description="...")` trong FastAPI).
6. Tạo PR, gắn label `good-first-issue`, tag Tech Lead review.

Task này thường mất 0.5–1 ngày cho engineer mới, đủ để làm quen codebase mà không rủi ro phá vỡ tính năng quan trọng đang chạy production.'),
    ('Task khởi động #2 (sau khi hoàn thành task #1): Thêm endpoint lấy lịch sử đơn hàng của khách hàng'::text, '**Mục tiêu**: làm quen với authentication/authorization (JWT), và cách một service gọi sang service khác.

**Các bước gợi ý**:
1. Thêm endpoint `GET /api/v1/customers/me/orders` trong `order-service`, yêu cầu JWT hợp lệ (dùng dependency `get_current_user` có sẵn trong `app/api/deps.py`).
2. Chỉ trả về đơn hàng thuộc về chính user đang đăng nhập (không cho phép xem đơn của người khác qua đổi ID — đây là lỗi bảo mật kinh điển IDOR, cần đặc biệt cẩn thận).
3. Hỗ trợ phân trang (`page`, `page_size`), mặc định sắp xếp theo `created_at DESC`.
4. Viết test đảm bảo user A không thể xem được đơn hàng của user B dù biết order ID (test case bảo mật quan trọng, sẽ được review kỹ).', 3, 120, '**Mục tiêu**: làm quen với authentication/authorization (JWT), và cách một service gọi sang service khác.

**Các bước gợi ý**:
1. Thêm endpoint `GET /api/v1/customers/me/orders` trong `order-service`, yêu cầu JWT hợp lệ (dùng dependency `get_current_user` có sẵn trong `app/api/deps.py`).
2. Chỉ trả về đơn hàng thuộc về chính user đang đăng nhập (không cho phép xem đơn của người khác qua đổi ID — đây là lỗi bảo mật kinh điển IDOR, cần đặc biệt cẩn thận).
3. Hỗ trợ phân trang (`page`, `page_size`), mặc định sắp xếp theo `created_at DESC`.
4. Viết test đảm bảo user A không thể xem được đơn hàng của user B dù biết order ID (test case bảo mật quan trọng, sẽ được review kỹ).', '358cbbded8d8d33d227965e8148c1c7e4f5aee32efebbf7b59049e88ac4c14b9', 'pending', '', '**Mục tiêu**: làm quen với authentication/authorization (JWT), và cách một service gọi sang service khác.

**Các bước gợi ý**:
1. Thêm endpoint `GET /api/v1/customers/me/orders` trong `order-service`, yêu cầu JWT hợp lệ (dùng dependency `get_current_user` có sẵn trong `app/api/deps.py`).
2. Chỉ trả về đơn hàng thuộc về chính user đang đăng nhập (không cho phép xem đơn của người khác qua đổi ID — đây là lỗi bảo mật kinh điển IDOR, cần đặc biệt cẩn thận).
3. Hỗ trợ phân trang (`page`, `page_size`), mặc định sắp xếp theo `created_at DESC`.
4. Viết test đảm bảo user A không thể xem được đơn hàng của user B dù biết order ID (test case bảo mật quan trọng, sẽ được review kỹ).'),
    ('Sau 2 task khởi động'::text, 'Sau khi hoàn thành cả 2 task trên và được Tech Lead xác nhận đã hiểu rõ luồng code, bạn sẽ được giao task nghiệp vụ thật theo sprint hiện tại của team, thường liên quan tới 1 trong các mảng: catalog, checkout flow, hoặc notification — tuỳ theo capacity và định hướng phát triển của bạn đã trao đổi với Tech Lead trong buổi 1-1 đầu tiên.', 4, 68, 'Sau khi hoàn thành cả 2 task trên và được Tech Lead xác nhận đã hiểu rõ luồng code, bạn sẽ được giao task nghiệp vụ thật theo sprint hiện tại của team, thường liên quan tới 1 trong các mảng: catalog, checkout flow, hoặc notification — tuỳ theo capacity và định hướng phát triển của bạn đã trao đổi với Tech Lead trong buổi 1-1 đầu tiên.', 'd5731dd47d83033d342332fb5e4124d7944c37d930ccb410da4aafbff40270b7', 'pending', '', 'Sau khi hoàn thành cả 2 task trên và được Tech Lead xác nhận đã hiểu rõ luồng code, bạn sẽ được giao task nghiệp vụ thật theo sprint hiện tại của team, thường liên quan tới 1 trong các mảng: catalog, checkout flow, hoặc notification — tuỳ theo capacity và định hướng phát triển của bạn đã trao đổi với Tech Lead trong buổi 1-1 đầu tiên.')
) AS c(heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical);

-- TOURBOOK: TourBooking Service — Overview
WITH doc AS (
  INSERT INTO knowledge_documents
    (project_id, created_by_user_id, knowledge_domain, document_category, policy_category,
     source_key, category_confirmed, category_classification_status,
     title, source_url, status, created_at, updated_at)
  VALUES (
    (SELECT project_id FROM projects WHERE key = 'TOURBOOK'),
    (SELECT user_id FROM users WHERE email = 'pm.tourbook@onboarding.dev'),
    'PROJECT', 'OVERVIEW', NULL,
    'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/tourbook/overview', true, 'CLASSIFIED',
    'TourBooking Service — Overview', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/tourbook/overview', 'ACTIVE', now(), now()
  )
  RETURNING document_id
),
ver AS (
  INSERT INTO document_versions
    (document_id, version_no, revision_no, embedding_model_version,
     storage_uri, checksum, status, created_at)
  SELECT document_id, 1, 1, 'pending', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/tourbook/overview', 'e143627dc837230ad0f26b0b49d547583070153883c3b6dc2d02a1c9cfcc8ecf', 'ACTIVE', now() FROM doc
  RETURNING version_id
)
INSERT INTO document_chunks (version_id, heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical)
SELECT ver.version_id, c.heading, c.content, c.chunk_index, c.token_count, c.embedding_text, c.content_hash, c.embedding_model_version, c.lexical_identifiers, c.lexical_technical
FROM ver, (VALUES
    (NULL::text, '# TourBooking Service — Overview', 0, 5, '# TourBooking Service — Overview', '7b51dcb41f112699b1c73650768be3481a9e2af36c4e2c66cd33972e152c7aba', 'pending', '', '# TourBooking Service — Overview'),
    ('Giới thiệu chung'::text, 'TourBooking Service là hệ thống backend trung tâm cho nền tảng đặt tour du lịch trực tuyến, kết nối khách hàng cá nhân với mạng lưới đối tác lữ hành (hiện có 42 đối tác đang hoạt động, từ công ty lữ hành lớn tới các đơn vị tour địa phương nhỏ). Dự án bắt đầu phát triển từ tháng 6/2024, chính thức lên production tháng 1/2025, hiện đang ở giai đoạn mở rộng nhanh với mục tiêu tăng gấp đôi số lượng tour niêm yết trong năm 2025.

Khác với các nền tảng OTA (Online Travel Agency) lớn chỉ làm trung gian đặt phòng khách sạn/vé máy bay, TourBooking tập trung riêng vào **tour trọn gói** (bao gồm di chuyển, lưu trú, ăn uống, hướng dẫn viên) — đây là mảng có biên lợi nhuận tốt hơn nhưng vận hành phức tạp hơn nhiều do phải quản lý lịch khởi hành, số chỗ giới hạn, và phối hợp với đối tác lữ hành theo thời gian thực.', 1, 168, 'TourBooking Service là hệ thống backend trung tâm cho nền tảng đặt tour du lịch trực tuyến, kết nối khách hàng cá nhân với mạng lưới đối tác lữ hành (hiện có 42 đối tác đang hoạt động, từ công ty lữ hành lớn tới các đơn vị tour địa phương nhỏ). Dự án bắt đầu phát triển từ tháng 6/2024, chính thức lên production tháng 1/2025, hiện đang ở giai đoạn mở rộng nhanh với mục tiêu tăng gấp đôi số lượng tour niêm yết trong năm 2025.

Khác với các nền tảng OTA (Online Travel Agency) lớn chỉ làm trung gian đặt phòng khách sạn/vé máy bay, TourBooking tập trung riêng vào **tour trọn gói** (bao gồm di chuyển, lưu trú, ăn uống, hướng dẫn viên) — đây là mảng có biên lợi nhuận tốt hơn nhưng vận hành phức tạp hơn nhiều do phải quản lý lịch khởi hành, số chỗ giới hạn, và phối hợp với đối tác lữ hành theo thời gian thực.', '23e1fcc447286b211b89ea5bd4011cd912951a2f4a24ea2c381547f17cb4d7e7', 'pending', '', 'TourBooking Service là hệ thống backend trung tâm cho nền tảng đặt tour du lịch trực tuyến, kết nối khách hàng cá nhân với mạng lưới đối tác lữ hành (hiện có 42 đối tác đang hoạt động, từ công ty lữ hành lớn tới các đơn vị tour địa phương nhỏ). Dự án bắt đầu phát triển từ tháng 6/2024, chính thức lên production tháng 1/2025, hiện đang ở giai đoạn mở rộng nhanh với mục tiêu tăng gấp đôi số lượng tour niêm yết trong năm 2025.

Khác với các nền tảng OTA (Online Travel Agency) lớn chỉ làm trung gian đặt phòng khách sạn/vé máy bay, TourBooking tập trung riêng vào **tour trọn gói** (bao gồm di chuyển, lưu trú, ăn uống, hướng dẫn viên) — đây là mảng có biên lợi nhuận tốt hơn nhưng vận hành phức tạp hơn nhiều do phải quản lý lịch khởi hành, số chỗ giới hạn, và phối hợp với đối tác lữ hành theo thời gian thực.'),
    ('Bối cảnh kinh doanh'::text, 'Ngành du lịch Việt Nam phục hồi mạnh sau giai đoạn khó khăn, nhu cầu đặt tour online tăng trưởng ổn định ~25%/năm theo báo cáo thị trường nội bộ. Điểm khác biệt cạnh tranh của TourBooking: (1) đảm bảo giá tốt nhất qua đàm phán trực tiếp với đối tác (không qua trung gian), (2) chính sách huỷ/đổi lịch linh hoạt hơn thị trường (hoàn 80% nếu huỷ trước 7 ngày, so với mức thông thường 50%), (3) Partner Portal cho phép đối tác tự quản lý tour, giảm thời gian onboarding đối tác mới từ 2 tuần xuống còn 2-3 ngày.', 2, 103, 'Ngành du lịch Việt Nam phục hồi mạnh sau giai đoạn khó khăn, nhu cầu đặt tour online tăng trưởng ổn định ~25%/năm theo báo cáo thị trường nội bộ. Điểm khác biệt cạnh tranh của TourBooking: (1) đảm bảo giá tốt nhất qua đàm phán trực tiếp với đối tác (không qua trung gian), (2) chính sách huỷ/đổi lịch linh hoạt hơn thị trường (hoàn 80% nếu huỷ trước 7 ngày, so với mức thông thường 50%), (3) Partner Portal cho phép đối tác tự quản lý tour, giảm thời gian onboarding đối tác mới từ 2 tuần xuống còn 2-3 ngày.', '5fcdd446384a36ed50097ff42bc6350c68d3926a6d3e0d8e74045d6e70ef9eba', 'pending', '', 'Ngành du lịch Việt Nam phục hồi mạnh sau giai đoạn khó khăn, nhu cầu đặt tour online tăng trưởng ổn định ~25%/năm theo báo cáo thị trường nội bộ. Điểm khác biệt cạnh tranh của TourBooking: (1) đảm bảo giá tốt nhất qua đàm phán trực tiếp với đối tác (không qua trung gian), (2) chính sách huỷ/đổi lịch linh hoạt hơn thị trường (hoàn 80% nếu huỷ trước 7 ngày, so với mức thông thường 50%), (3) Partner Portal cho phép đối tác tự quản lý tour, giảm thời gian onboarding đối tác mới từ 2 tuần xuống còn 2-3 ngày.'),
    ('Trạng thái vận hành hiện tại'::text, '| Chỉ số | Giá trị |
|---|---|
| Số đối tác lữ hành đang hoạt động | 42 |
| Số tour đang niêm yết | ~680 tour, ~2.100 lịch khởi hành (departure) |
| Booking trung bình/ngày | ~85 booking ngày thường, ~400 booking dịp lễ/Tết |
| Uptime SLA | 99.9% cam kết, thực tế 99.87% quý gần nhất (thấp hơn mục tiêu do 1 sự cố Elasticsearch tháng 4/2025) |
| Latency tìm kiếm tour (p95) | 380ms |
| Tỷ lệ booking bị huỷ do hết chỗ (double booking) | 0.3% (đã giảm đáng kể sau khi fix cơ chế giữ chỗ, xem phần sự cố) |', 3, 112, '| Chỉ số | Giá trị |
|---|---|
| Số đối tác lữ hành đang hoạt động | 42 |
| Số tour đang niêm yết | ~680 tour, ~2.100 lịch khởi hành (departure) |
| Booking trung bình/ngày | ~85 booking ngày thường, ~400 booking dịp lễ/Tết |
| Uptime SLA | 99.9% cam kết, thực tế 99.87% quý gần nhất (thấp hơn mục tiêu do 1 sự cố Elasticsearch tháng 4/2025) |
| Latency tìm kiếm tour (p95) | 380ms |
| Tỷ lệ booking bị huỷ do hết chỗ (double booking) | 0.3% (đã giảm đáng kể sau khi fix cơ chế giữ chỗ, xem phần sự cố) |', '626b39bb36eb69e2970867c6b22b579297d45bc3e92faed61446ad4c46bfe4d2', 'pending', '', '| Chỉ số | Giá trị |
|---|---|
| Số đối tác lữ hành đang hoạt động | 42 |
| Số tour đang niêm yết | ~680 tour, ~2.100 lịch khởi hành (departure) |
| Booking trung bình/ngày | ~85 booking ngày thường, ~400 booking dịp lễ/Tết |
| Uptime SLA | 99.9% cam kết, thực tế 99.87% quý gần nhất (thấp hơn mục tiêu do 1 sự cố Elasticsearch tháng 4/2025) |
| Latency tìm kiếm tour (p95) | 380ms |
| Tỷ lệ booking bị huỷ do hết chỗ (double booking) | 0.3% (đã giảm đáng kể sau khi fix cơ chế giữ chỗ, xem phần sự cố) |'),
    ('Mục tiêu kinh doanh chi tiết'::text, '- Cho phép khách hàng tìm và đặt tour theo điểm đến, ngày khởi hành, khoảng giá, với kết quả tìm kiếm trả về dưới 500ms ở p95.
- Quản lý chính xác số chỗ còn lại theo từng lịch khởi hành, tuyệt đối tránh overbooking (đây là rủi ro uy tín nghiêm trọng nhất — khách đã thanh toán nhưng không có chỗ).
- Cho phép đối tác lữ hành tự đăng tour và quản lý lịch trình qua Partner Portal riêng, giảm tải cho đội vận hành nội bộ.
- Mở rộng từ 42 lên 80 đối tác trong năm 2025, tăng số tour niêm yết lên gấp đôi.', 4, 111, '- Cho phép khách hàng tìm và đặt tour theo điểm đến, ngày khởi hành, khoảng giá, với kết quả tìm kiếm trả về dưới 500ms ở p95.
- Quản lý chính xác số chỗ còn lại theo từng lịch khởi hành, tuyệt đối tránh overbooking (đây là rủi ro uy tín nghiêm trọng nhất — khách đã thanh toán nhưng không có chỗ).
- Cho phép đối tác lữ hành tự đăng tour và quản lý lịch trình qua Partner Portal riêng, giảm tải cho đội vận hành nội bộ.
- Mở rộng từ 42 lên 80 đối tác trong năm 2025, tăng số tour niêm yết lên gấp đôi.', '1b39fc7b7e2b22bd3f8c25c627b6782d7548474a29ff82ec8a0758350a171430', 'pending', '', '- Cho phép khách hàng tìm và đặt tour theo điểm đến, ngày khởi hành, khoảng giá, với kết quả tìm kiếm trả về dưới 500ms ở p95.
- Quản lý chính xác số chỗ còn lại theo từng lịch khởi hành, tuyệt đối tránh overbooking (đây là rủi ro uy tín nghiêm trọng nhất — khách đã thanh toán nhưng không có chỗ).
- Cho phép đối tác lữ hành tự đăng tour và quản lý lịch trình qua Partner Portal riêng, giảm tải cho đội vận hành nội bộ.
- Mở rộng từ 42 lên 80 đối tác trong năm 2025, tăng số tour niêm yết lên gấp đôi.'),
    ('Người dùng chính'::text, '- **Khách hàng đặt tour** (qua web/app): phân khúc chính 28-45 tuổi, có xu hướng đặt tour theo nhóm (trung bình 2.8 người/booking), đặt trước trung bình 3-4 tuần cho tour trong nước, 2-3 tháng cho tour nước ngoài.
- **Đối tác lữ hành**: đăng nhập Partner Portal riêng (`partner.tourbook.vn`), tự quản lý danh sách tour, lịch khởi hành, giá, số chỗ. Nhận thông báo real-time khi có booking mới.
- **Nhân viên chăm sóc khách hàng**: xử lý yêu cầu huỷ/đổi lịch, khiếu nại, hỗ trợ qua hotline và live chat, dùng Admin Portal nội bộ.
- **Đội vận hành/kinh doanh**: theo dõi báo cáo doanh thu theo đối tác, đàm phán hoa hồng, duyệt đối tác mới tham gia nền tảng.', 5, 123, '- **Khách hàng đặt tour** (qua web/app): phân khúc chính 28-45 tuổi, có xu hướng đặt tour theo nhóm (trung bình 2.8 người/booking), đặt trước trung bình 3-4 tuần cho tour trong nước, 2-3 tháng cho tour nước ngoài.
- **Đối tác lữ hành**: đăng nhập Partner Portal riêng (`partner.tourbook.vn`), tự quản lý danh sách tour, lịch khởi hành, giá, số chỗ. Nhận thông báo real-time khi có booking mới.
- **Nhân viên chăm sóc khách hàng**: xử lý yêu cầu huỷ/đổi lịch, khiếu nại, hỗ trợ qua hotline và live chat, dùng Admin Portal nội bộ.
- **Đội vận hành/kinh doanh**: theo dõi báo cáo doanh thu theo đối tác, đàm phán hoa hồng, duyệt đối tác mới tham gia nền tảng.', '73b0df43dafc106429b5ac5ced3249a77cb4ddf7dddb0acd8eda7e21e31e7455', 'pending', '', '- **Khách hàng đặt tour** (qua web/app): phân khúc chính 28-45 tuổi, có xu hướng đặt tour theo nhóm (trung bình 2.8 người/booking), đặt trước trung bình 3-4 tuần cho tour trong nước, 2-3 tháng cho tour nước ngoài.
- **Đối tác lữ hành**: đăng nhập Partner Portal riêng (`partner.tourbook.vn`), tự quản lý danh sách tour, lịch khởi hành, giá, số chỗ. Nhận thông báo real-time khi có booking mới.
- **Nhân viên chăm sóc khách hàng**: xử lý yêu cầu huỷ/đổi lịch, khiếu nại, hỗ trợ qua hotline và live chat, dùng Admin Portal nội bộ.
- **Đội vận hành/kinh doanh**: theo dõi báo cáo doanh thu theo đối tác, đàm phán hoa hồng, duyệt đối tác mới tham gia nền tảng.'),
    ('Phạm vi hiện tại (đã lên production)'::text, 'Tìm kiếm tour theo nhiều tiêu chí, đặt chỗ với cơ chế giữ chỗ tạm thời, thanh toán online qua VNPay/thẻ quốc tế, xác nhận qua email, chính sách huỷ/hoàn tiền tự động theo % dựa trên thời gian huỷ trước ngày khởi hành, Partner Portal đầy đủ cho đối tác tự quản lý.', 6, 54, 'Tìm kiếm tour theo nhiều tiêu chí, đặt chỗ với cơ chế giữ chỗ tạm thời, thanh toán online qua VNPay/thẻ quốc tế, xác nhận qua email, chính sách huỷ/hoàn tiền tự động theo % dựa trên thời gian huỷ trước ngày khởi hành, Partner Portal đầy đủ cho đối tác tự quản lý.', '7f46d4f64b2749696ed85aa8bf2cee9b55aa8b0ee8fc582257cbdea2f7b02659', 'pending', '', 'Tìm kiếm tour theo nhiều tiêu chí, đặt chỗ với cơ chế giữ chỗ tạm thời, thanh toán online qua VNPay/thẻ quốc tế, xác nhận qua email, chính sách huỷ/hoàn tiền tự động theo % dựa trên thời gian huỷ trước ngày khởi hành, Partner Portal đầy đủ cho đối tác tự quản lý.'),
    ('Roadmap sắp tới'::text, '- **Q3/2025**: Tính năng chat trực tiếp giữa khách hàng và đối tác lữ hành trước khi đặt tour (đang thiết kế, cân nhắc dùng dịch vụ chat bên thứ 3 thay vì tự xây).
- **Q3/2025**: Hệ thống đánh giá/review sau tour, ảnh hưởng tới thứ hạng hiển thị tour trong kết quả tìm kiếm.
- **Q4/2025**: Mở rộng thanh toán trả góp cho tour giá trị cao (trên 20 triệu), tương tự mô hình PhoneShop đã áp dụng.
- **2026**: Đánh giá mở rộng sang thị trường tour quốc tế (hiện chỉ có tour trong nước và một số tour nước ngoài do đối tác Việt Nam tổ chức).', 7, 111, '- **Q3/2025**: Tính năng chat trực tiếp giữa khách hàng và đối tác lữ hành trước khi đặt tour (đang thiết kế, cân nhắc dùng dịch vụ chat bên thứ 3 thay vì tự xây).
- **Q3/2025**: Hệ thống đánh giá/review sau tour, ảnh hưởng tới thứ hạng hiển thị tour trong kết quả tìm kiếm.
- **Q4/2025**: Mở rộng thanh toán trả góp cho tour giá trị cao (trên 20 triệu), tương tự mô hình PhoneShop đã áp dụng.
- **2026**: Đánh giá mở rộng sang thị trường tour quốc tế (hiện chỉ có tour trong nước và một số tour nước ngoài do đối tác Việt Nam tổ chức).', '8b545f92b66b5c9f268de3f9c021ac0b9c8253ccaa11f0643ee26cee84e21ddd', 'pending', '', '- **Q3/2025**: Tính năng chat trực tiếp giữa khách hàng và đối tác lữ hành trước khi đặt tour (đang thiết kế, cân nhắc dùng dịch vụ chat bên thứ 3 thay vì tự xây).
- **Q3/2025**: Hệ thống đánh giá/review sau tour, ảnh hưởng tới thứ hạng hiển thị tour trong kết quả tìm kiếm.
- **Q4/2025**: Mở rộng thanh toán trả góp cho tour giá trị cao (trên 20 triệu), tương tự mô hình PhoneShop đã áp dụng.
- **2026**: Đánh giá mở rộng sang thị trường tour quốc tế (hiện chỉ có tour trong nước và một số tour nước ngoài do đối tác Việt Nam tổ chức).'),
    ('Sự cố đáng chú ý gần đây (để tránh lặp lại)'::text, '- **Tháng 02/2025**: Double booking xảy ra khi 2 khách đặt cùng lúc chỗ cuối cùng của 1 lịch khởi hành hot (tour Sapa dịp cuối tuần), do cơ chế giữ chỗ ban đầu chỉ dùng optimistic lock ở tầng ứng dụng, không đủ chặt khi tải cao. Đã fix bằng Redis distributed lock kết hợp TTL 15 phút cho reservation (chi tiết xem `architecture.md`). Đã liên hệ khách hàng bị ảnh hưởng, đền bù voucher theo chính sách công ty.
- **Tháng 04/2025**: Elasticsearch cluster bị chậm nghiêm trọng (latency tăng từ 200ms lên hơn 5 giây) do 1 query aggregation không tối ưu được thêm vào lúc release tính năng lọc theo "tour phù hợp gia đình", gây quá tải cluster trong giờ cao điểm 2 tiếng. Đã rollback ngay và tối ưu lại query trước khi release lại, đồng thời bổ sung alert riêng cho Elasticsearch cluster health.
- **Tháng 06/2025**: 1 đối tác lữ hành cập nhật sai giá tour qua Partner Portal (thiếu 1 số 0, giá 5 triệu thành 500 nghìn), hệ thống cho phép booking với giá sai trong 20 phút trước khi đối tác phát hiện. Đã bổ sung validation cảnh báo khi giá thay đổi bất thường (>50% so với giá trước đó) yêu cầu xác nhận 2 bước từ đối tác.', 8, 221, '- **Tháng 02/2025**: Double booking xảy ra khi 2 khách đặt cùng lúc chỗ cuối cùng của 1 lịch khởi hành hot (tour Sapa dịp cuối tuần), do cơ chế giữ chỗ ban đầu chỉ dùng optimistic lock ở tầng ứng dụng, không đủ chặt khi tải cao. Đã fix bằng Redis distributed lock kết hợp TTL 15 phút cho reservation (chi tiết xem `architecture.md`). Đã liên hệ khách hàng bị ảnh hưởng, đền bù voucher theo chính sách công ty.
- **Tháng 04/2025**: Elasticsearch cluster bị chậm nghiêm trọng (latency tăng từ 200ms lên hơn 5 giây) do 1 query aggregation không tối ưu được thêm vào lúc release tính năng lọc theo "tour phù hợp gia đình", gây quá tải cluster trong giờ cao điểm 2 tiếng. Đã rollback ngay và tối ưu lại query trước khi release lại, đồng thời bổ sung alert riêng cho Elasticsearch cluster health.
- **Tháng 06/2025**: 1 đối tác lữ hành cập nhật sai giá tour qua Partner Portal (thiếu 1 số 0, giá 5 triệu thành 500 nghìn), hệ thống cho phép booking với giá sai trong 20 phút trước khi đối tác phát hiện. Đã bổ sung validation cảnh báo khi giá thay đổi bất thường (>50% so với giá trước đó) yêu cầu xác nhận 2 bước từ đối tác.', '96596d7bd737382df3db8696b9daa44eb5b383aa6cb9ba7cde965faf766af109', 'pending', '', '- **Tháng 02/2025**: Double booking xảy ra khi 2 khách đặt cùng lúc chỗ cuối cùng của 1 lịch khởi hành hot (tour Sapa dịp cuối tuần), do cơ chế giữ chỗ ban đầu chỉ dùng optimistic lock ở tầng ứng dụng, không đủ chặt khi tải cao. Đã fix bằng Redis distributed lock kết hợp TTL 15 phút cho reservation (chi tiết xem `architecture.md`). Đã liên hệ khách hàng bị ảnh hưởng, đền bù voucher theo chính sách công ty.
- **Tháng 04/2025**: Elasticsearch cluster bị chậm nghiêm trọng (latency tăng từ 200ms lên hơn 5 giây) do 1 query aggregation không tối ưu được thêm vào lúc release tính năng lọc theo "tour phù hợp gia đình", gây quá tải cluster trong giờ cao điểm 2 tiếng. Đã rollback ngay và tối ưu lại query trước khi release lại, đồng thời bổ sung alert riêng cho Elasticsearch cluster health.
- **Tháng 06/2025**: 1 đối tác lữ hành cập nhật sai giá tour qua Partner Portal (thiếu 1 số 0, giá 5 triệu thành 500 nghìn), hệ thống cho phép booking với giá sai trong 20 phút trước khi đối tác phát hiện. Đã bổ sung validation cảnh báo khi giá thay đổi bất thường (>50% so với giá trước đó) yêu cầu xác nhận 2 bước từ đối tác.'),
    ('Liên hệ đội ngũ'::text, '- **Kênh Slack chính**: #tourbook-backend (thảo luận kỹ thuật hàng ngày), #tourbook-partners (vấn đề liên quan tích hợp đối tác), #tourbook-incidents (chỉ dùng khi có sự cố production).
- **Tech Lead**: chịu trách nhiệm kiến trúc, review PR quan trọng, quyết định kỹ thuật lớn.', 9, 45, '- **Kênh Slack chính**: #tourbook-backend (thảo luận kỹ thuật hàng ngày), #tourbook-partners (vấn đề liên quan tích hợp đối tác), #tourbook-incidents (chỉ dùng khi có sự cố production).
- **Tech Lead**: chịu trách nhiệm kiến trúc, review PR quan trọng, quyết định kỹ thuật lớn.', '09fb058089c39b2471c3500bec581717ab3f3f10ab6292e68357274b3e2da183', 'pending', '', '- **Kênh Slack chính**: #tourbook-backend (thảo luận kỹ thuật hàng ngày), #tourbook-partners (vấn đề liên quan tích hợp đối tác), #tourbook-incidents (chỉ dùng khi có sự cố production).
- **Tech Lead**: chịu trách nhiệm kiến trúc, review PR quan trọng, quyết định kỹ thuật lớn.')
) AS c(heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical);

-- TOURBOOK: TourBooking Service — Architecture
WITH doc AS (
  INSERT INTO knowledge_documents
    (project_id, created_by_user_id, knowledge_domain, document_category, policy_category,
     source_key, category_confirmed, category_classification_status,
     title, source_url, status, created_at, updated_at)
  VALUES (
    (SELECT project_id FROM projects WHERE key = 'TOURBOOK'),
    (SELECT user_id FROM users WHERE email = 'pm.tourbook@onboarding.dev'),
    'PROJECT', 'ARCHITECTURE', NULL,
    'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/tourbook/architecture', true, 'CLASSIFIED',
    'TourBooking Service — Architecture', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/tourbook/architecture', 'ACTIVE', now(), now()
  )
  RETURNING document_id
),
ver AS (
  INSERT INTO document_versions
    (document_id, version_no, revision_no, embedding_model_version,
     storage_uri, checksum, status, created_at)
  SELECT document_id, 1, 1, 'pending', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/tourbook/architecture', '2cc12168e79a1ce4c41f1a67a29c852b413052506d1386b423bf6e52fa5ca454', 'ACTIVE', now() FROM doc
  RETURNING version_id
)
INSERT INTO document_chunks (version_id, heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical)
SELECT ver.version_id, c.heading, c.content, c.chunk_index, c.token_count, c.embedding_text, c.content_hash, c.embedding_model_version, c.lexical_identifiers, c.lexical_technical
FROM ver, (VALUES
    (NULL::text, '# TourBooking Service — Architecture', 0, 5, '# TourBooking Service — Architecture', 'c6400ae8efc98dc5e895814eeaeebfd3d5f004ae4fa6ec11eafdcba78f9d82b9', 'pending', '', '# TourBooking Service — Architecture'),
    ('Tổng quan kiến trúc'::text, 'TourBooking Service được xây dựng theo kiến trúc **modular monolith** (không phải microservice như PhoneShop) — quyết định có chủ đích dựa trên quy mô team (8 kỹ sư backend) và độ phức tạp nghiệp vụ ở giai đoạn hiện tại. Toàn bộ ứng dụng là 1 Spring Boot application duy nhất nhưng tổ chức code theo package rõ ràng theo domain (`tour`, `booking`, `partner`, `payment`), giữ khả năng tách thành microservice riêng trong tương lai nếu cần scale độc lập từng phần.', 1, 83, 'TourBooking Service được xây dựng theo kiến trúc **modular monolith** (không phải microservice như PhoneShop) — quyết định có chủ đích dựa trên quy mô team (8 kỹ sư backend) và độ phức tạp nghiệp vụ ở giai đoạn hiện tại. Toàn bộ ứng dụng là 1 Spring Boot application duy nhất nhưng tổ chức code theo package rõ ràng theo domain (`tour`, `booking`, `partner`, `payment`), giữ khả năng tách thành microservice riêng trong tương lai nếu cần scale độc lập từng phần.', '6cfb1cc96c46aa24e135ec5824b13cf428220b095154e1462490143020125d3f', 'pending', '', 'TourBooking Service được xây dựng theo kiến trúc **modular monolith** (không phải microservice như PhoneShop) — quyết định có chủ đích dựa trên quy mô team (8 kỹ sư backend) và độ phức tạp nghiệp vụ ở giai đoạn hiện tại. Toàn bộ ứng dụng là 1 Spring Boot application duy nhất nhưng tổ chức code theo package rõ ràng theo domain (`tour`, `booking`, `partner`, `payment`), giữ khả năng tách thành microservice riêng trong tương lai nếu cần scale độc lập từng phần.'),
    ('Tech stack đầy đủ'::text, '| Thành phần | Công nghệ | Ghi chú |
|---|---|---|
| Backend framework | Java 21, Spring Boot 3.2 | Dùng Virtual Threads (Project Loom) cho I/O-bound endpoint, giảm đáng kể thread pool overhead |
| ORM | Spring Data JPA + Hibernate 6 | Flyway quản lý migration, không dùng `ddl-auto` ở bất kỳ môi trường nào kể cả dev |
| Database chính | PostgreSQL 15 (AWS RDS Multi-AZ) | `db.r6g.large`, có read replica riêng cho Partner Portal (đọc nhiều, ghi ít) |
| Search | Elasticsearch 8.x (AWS OpenSearch) | Tìm kiếm tour theo điểm đến/giá/ngày, đồng bộ qua Debezium CDC từ Postgres (không đồng bộ thủ công) |
| Cache | Redis 7 (AWS ElastiCache) | Cache kết quả tìm kiếm tour phổ biến (TTL 2 phút), distributed lock cho luồng giữ chỗ |
| Deploy | Docker, AWS ECS Fargate | Không dùng Kubernetes — team đánh giá ECS đủ dùng và ít vận hành hơn cho quy mô hiện tại |
| Observability | New Relic (APM), CloudWatch (log + alarm), Opsgenie (on-call) | |
| CI/CD | GitHub Actions + AWS CodeDeploy | Blue/green deployment, tự động rollback nếu health check fail sau deploy |', 2, 203, '| Thành phần | Công nghệ | Ghi chú |
|---|---|---|
| Backend framework | Java 21, Spring Boot 3.2 | Dùng Virtual Threads (Project Loom) cho I/O-bound endpoint, giảm đáng kể thread pool overhead |
| ORM | Spring Data JPA + Hibernate 6 | Flyway quản lý migration, không dùng `ddl-auto` ở bất kỳ môi trường nào kể cả dev |
| Database chính | PostgreSQL 15 (AWS RDS Multi-AZ) | `db.r6g.large`, có read replica riêng cho Partner Portal (đọc nhiều, ghi ít) |
| Search | Elasticsearch 8.x (AWS OpenSearch) | Tìm kiếm tour theo điểm đến/giá/ngày, đồng bộ qua Debezium CDC từ Postgres (không đồng bộ thủ công) |
| Cache | Redis 7 (AWS ElastiCache) | Cache kết quả tìm kiếm tour phổ biến (TTL 2 phút), distributed lock cho luồng giữ chỗ |
| Deploy | Docker, AWS ECS Fargate | Không dùng Kubernetes — team đánh giá ECS đủ dùng và ít vận hành hơn cho quy mô hiện tại |
| Observability | New Relic (APM), CloudWatch (log + alarm), Opsgenie (on-call) | |
| CI/CD | GitHub Actions + AWS CodeDeploy | Blue/green deployment, tự động rollback nếu health check fail sau deploy |', '755d03253fe57cb592f6f1991ba0fb95e0464dcf2735e3fe2827554aa97dc127', 'pending', '', '| Thành phần | Công nghệ | Ghi chú |
|---|---|---|
| Backend framework | Java 21, Spring Boot 3.2 | Dùng Virtual Threads (Project Loom) cho I/O-bound endpoint, giảm đáng kể thread pool overhead |
| ORM | Spring Data JPA + Hibernate 6 | Flyway quản lý migration, không dùng `ddl-auto` ở bất kỳ môi trường nào kể cả dev |
| Database chính | PostgreSQL 15 (AWS RDS Multi-AZ) | `db.r6g.large`, có read replica riêng cho Partner Portal (đọc nhiều, ghi ít) |
| Search | Elasticsearch 8.x (AWS OpenSearch) | Tìm kiếm tour theo điểm đến/giá/ngày, đồng bộ qua Debezium CDC từ Postgres (không đồng bộ thủ công) |
| Cache | Redis 7 (AWS ElastiCache) | Cache kết quả tìm kiếm tour phổ biến (TTL 2 phút), distributed lock cho luồng giữ chỗ |
| Deploy | Docker, AWS ECS Fargate | Không dùng Kubernetes — team đánh giá ECS đủ dùng và ít vận hành hơn cho quy mô hiện tại |
| Observability | New Relic (APM), CloudWatch (log + alarm), Opsgenie (on-call) | |
| CI/CD | GitHub Actions + AWS CodeDeploy | Blue/green deployment, tự động rollback nếu health check fail sau deploy |'),
    ('Module chính (theo package, tất cả nằm trong 1 Spring Boot application)'::text, '```
com.tourbook
  ├── tour/          # entity Tour, TourDeparture, quản lý lịch khởi hành, tích hợp Elasticsearch
  ├── booking/        # BookingService, xử lý đặt chỗ, giữ chỗ tạm qua Redis distributed lock
  ├── partner/         # quản lý đối tác lữ hành, Partner Portal API, xác thực riêng cho đối tác
  ├── payment/          # tích hợp cổng thanh toán, xử lý webhook, logic hoàn tiền theo chính sách huỷ
  ├── notification/      # gửi email xác nhận, nhắc lịch khởi hành trước 3 ngày
  └── common/              # config, exception handler, security filter, audit logging
```', 3, 92, '```
com.tourbook
  ├── tour/          # entity Tour, TourDeparture, quản lý lịch khởi hành, tích hợp Elasticsearch
  ├── booking/        # BookingService, xử lý đặt chỗ, giữ chỗ tạm qua Redis distributed lock
  ├── partner/         # quản lý đối tác lữ hành, Partner Portal API, xác thực riêng cho đối tác
  ├── payment/          # tích hợp cổng thanh toán, xử lý webhook, logic hoàn tiền theo chính sách huỷ
  ├── notification/      # gửi email xác nhận, nhắc lịch khởi hành trước 3 ngày
  └── common/              # config, exception handler, security filter, audit logging
```', 'f969a4ea12cf953a96f567a484b062d72dc00725991dba79091e1546a7f1c931', 'pending', '', '```
com.tourbook
  ├── tour/          # entity Tour, TourDeparture, quản lý lịch khởi hành, tích hợp Elasticsearch
  ├── booking/        # BookingService, xử lý đặt chỗ, giữ chỗ tạm qua Redis distributed lock
  ├── partner/         # quản lý đối tác lữ hành, Partner Portal API, xác thực riêng cho đối tác
  ├── payment/          # tích hợp cổng thanh toán, xử lý webhook, logic hoàn tiền theo chính sách huỷ
  ├── notification/      # gửi email xác nhận, nhắc lịch khởi hành trước 3 ngày
  └── common/              # config, exception handler, security filter, audit logging
```'),
    ('Luồng đặt chỗ (booking) — chi tiết kỹ thuật'::text, '1. Khách chọn tour + lịch khởi hành → hệ thống kiểm tra số chỗ còn lại (query Postgres, có cache Redis TTL ngắn 10 giây để giảm tải trong giờ cao điểm).
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
```', 4, 200, '1. Khách chọn tour + lịch khởi hành → hệ thống kiểm tra số chỗ còn lại (query Postgres, có cache Redis TTL ngắn 10 giây để giảm tải trong giờ cao điểm).
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
```', '921fb80740d2ed13d28d1b23baf2c8cf410fbc16ff0b79bb70983cb81491d0a1', 'pending', '', '1. Khách chọn tour + lịch khởi hành → hệ thống kiểm tra số chỗ còn lại (query Postgres, có cache Redis TTL ngắn 10 giây để giảm tải trong giờ cao điểm).
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
```'),
    ('Database schema (rút gọn)'::text, '```sql
tours(id, partner_id, name, destination, description, base_price, created_at)
tour_departures(id, tour_id, departure_date, total_seats, available_seats, price_override)
bookings(id, customer_id, departure_id, num_travelers, status, total_amount, created_at)
partners(id, company_name, contact_email, commission_rate, status)
payment_transactions(id, booking_id, provider, provider_ref, status, amount)
```', 5, 33, '```sql
tours(id, partner_id, name, destination, description, base_price, created_at)
tour_departures(id, tour_id, departure_date, total_seats, available_seats, price_override)
bookings(id, customer_id, departure_id, num_travelers, status, total_amount, created_at)
partners(id, company_name, contact_email, commission_rate, status)
payment_transactions(id, booking_id, provider, provider_ref, status, amount)
```', '63731b846a12f506f4bc5ebb1f9a1dbc6a6a3646fd1ff1d57d7549c96eab2173', 'pending', '', '```sql
tours(id, partner_id, name, destination, description, base_price, created_at)
tour_departures(id, tour_id, departure_date, total_seats, available_seats, price_override)
bookings(id, customer_id, departure_id, num_travelers, status, total_amount, created_at)
partners(id, company_name, contact_email, commission_rate, status)
payment_transactions(id, booking_id, provider, provider_ref, status, amount)
```'),
    ('Đồng bộ Elasticsearch'::text, 'Dùng **Debezium** (Change Data Capture) đọc trực tiếp từ Postgres WAL (write-ahead log), publish thay đổi qua Kafka, consumer riêng cập nhật Elasticsearch index. Cách tiếp cận này (thay vì đồng bộ trực tiếp trong code nghiệp vụ) đảm bảo Elasticsearch luôn nhất quán với Postgres kể cả khi có thay đổi dữ liệu không qua đường API thông thường (ví dụ sửa trực tiếp qua script vận hành khẩn cấp), và tách biệt hoàn toàn concern "đồng bộ search index" khỏi luồng nghiệp vụ chính — bài học rút ra sau sự cố Elasticsearch tháng 4/2025 khi cách đồng bộ đồng bộ trực tiếp trong code cũ gây coupling và khó debug.', 6, 113, 'Dùng **Debezium** (Change Data Capture) đọc trực tiếp từ Postgres WAL (write-ahead log), publish thay đổi qua Kafka, consumer riêng cập nhật Elasticsearch index. Cách tiếp cận này (thay vì đồng bộ trực tiếp trong code nghiệp vụ) đảm bảo Elasticsearch luôn nhất quán với Postgres kể cả khi có thay đổi dữ liệu không qua đường API thông thường (ví dụ sửa trực tiếp qua script vận hành khẩn cấp), và tách biệt hoàn toàn concern "đồng bộ search index" khỏi luồng nghiệp vụ chính — bài học rút ra sau sự cố Elasticsearch tháng 4/2025 khi cách đồng bộ đồng bộ trực tiếp trong code cũ gây coupling và khó debug.', 'ec66869801816b59ebdf46627669a8f47352ce3d14a625991613c887bd9169e9', 'pending', '', 'Dùng **Debezium** (Change Data Capture) đọc trực tiếp từ Postgres WAL (write-ahead log), publish thay đổi qua Kafka, consumer riêng cập nhật Elasticsearch index. Cách tiếp cận này (thay vì đồng bộ trực tiếp trong code nghiệp vụ) đảm bảo Elasticsearch luôn nhất quán với Postgres kể cả khi có thay đổi dữ liệu không qua đường API thông thường (ví dụ sửa trực tiếp qua script vận hành khẩn cấp), và tách biệt hoàn toàn concern "đồng bộ search index" khỏi luồng nghiệp vụ chính — bài học rút ra sau sự cố Elasticsearch tháng 4/2025 khi cách đồng bộ đồng bộ trực tiếp trong code cũ gây coupling và khó debug.'),
    ('Quyết định thiết kế quan trọng'::text, '- **Modular monolith thay vì microservice**: với team 8 người và độ phức tạp nghiệp vụ hiện tại, chi phí vận hành nhiều service (network, observability, deployment riêng biệt) lớn hơn lợi ích. Ranh giới module rõ ràng theo package giữ khả năng tách ra sau này nếu cần — đã có 1 buổi kiến trúc riêng thảo luận và quyết định điều này vào đầu dự án, ghi lại trong ADR (Architecture Decision Record) `ADR-001`.
- **Redis distributed lock cho giữ chỗ, không dùng database lock đơn thuần**: database lock (`SELECT FOR UPDATE`) từng được dùng ban đầu nhưng gây nghẽn connection pool khi tải cao vì giữ transaction mở lâu; chuyển sang Redis lock giúp giải phóng connection Postgres ngay, chỉ mở transaction ngắn khi thực sự confirm booking.
- **ECS Fargate thay vì Kubernetes**: đội DevOps chỉ có 1 người phụ trách hạ tầng cho service này, Kubernetes đòi hỏi kiến thức vận hành sâu hơn đáng kể so với lợi ích mang lại ở quy mô hiện tại.', 7, 172, '- **Modular monolith thay vì microservice**: với team 8 người và độ phức tạp nghiệp vụ hiện tại, chi phí vận hành nhiều service (network, observability, deployment riêng biệt) lớn hơn lợi ích. Ranh giới module rõ ràng theo package giữ khả năng tách ra sau này nếu cần — đã có 1 buổi kiến trúc riêng thảo luận và quyết định điều này vào đầu dự án, ghi lại trong ADR (Architecture Decision Record) `ADR-001`.
- **Redis distributed lock cho giữ chỗ, không dùng database lock đơn thuần**: database lock (`SELECT FOR UPDATE`) từng được dùng ban đầu nhưng gây nghẽn connection pool khi tải cao vì giữ transaction mở lâu; chuyển sang Redis lock giúp giải phóng connection Postgres ngay, chỉ mở transaction ngắn khi thực sự confirm booking.
- **ECS Fargate thay vì Kubernetes**: đội DevOps chỉ có 1 người phụ trách hạ tầng cho service này, Kubernetes đòi hỏi kiến thức vận hành sâu hơn đáng kể so với lợi ích mang lại ở quy mô hiện tại.', '3a66e5eeccace8a85a3cc27209b3bf6141be7ecca57033501a1cf41141df6d46', 'pending', '', '- **Modular monolith thay vì microservice**: với team 8 người và độ phức tạp nghiệp vụ hiện tại, chi phí vận hành nhiều service (network, observability, deployment riêng biệt) lớn hơn lợi ích. Ranh giới module rõ ràng theo package giữ khả năng tách ra sau này nếu cần — đã có 1 buổi kiến trúc riêng thảo luận và quyết định điều này vào đầu dự án, ghi lại trong ADR (Architecture Decision Record) `ADR-001`.
- **Redis distributed lock cho giữ chỗ, không dùng database lock đơn thuần**: database lock (`SELECT FOR UPDATE`) từng được dùng ban đầu nhưng gây nghẽn connection pool khi tải cao vì giữ transaction mở lâu; chuyển sang Redis lock giúp giải phóng connection Postgres ngay, chỉ mở transaction ngắn khi thực sự confirm booking.
- **ECS Fargate thay vì Kubernetes**: đội DevOps chỉ có 1 người phụ trách hạ tầng cho service này, Kubernetes đòi hỏi kiến thức vận hành sâu hơn đáng kể so với lợi ích mang lại ở quy mô hiện tại.'),
    ('Dashboard & alerting'::text, '- New Relic dashboard chính: `TourBook / Production Overview` — theo dõi response time theo endpoint, error rate, database connection pool usage.
- Alert quan trọng nhất: `Elasticsearch cluster status != green` → page on-call ngay (bài học từ sự cố tháng 4/2025, trước đó không có alert riêng cho việc này).
- Alert `booking confirmation rate < 95% trong 10 phút` → cảnh báo có thể đang xảy ra vấn đề ở luồng thanh toán hoặc webhook.', 8, 78, '- New Relic dashboard chính: `TourBook / Production Overview` — theo dõi response time theo endpoint, error rate, database connection pool usage.
- Alert quan trọng nhất: `Elasticsearch cluster status != green` → page on-call ngay (bài học từ sự cố tháng 4/2025, trước đó không có alert riêng cho việc này).
- Alert `booking confirmation rate < 95% trong 10 phút` → cảnh báo có thể đang xảy ra vấn đề ở luồng thanh toán hoặc webhook.', 'b73bd7b20741ddaa7ac9e3d36cfabbbee4f7b7ea01db2fa747a0bfde0712c8b2', 'pending', '', '- New Relic dashboard chính: `TourBook / Production Overview` — theo dõi response time theo endpoint, error rate, database connection pool usage.
- Alert quan trọng nhất: `Elasticsearch cluster status != green` → page on-call ngay (bài học từ sự cố tháng 4/2025, trước đó không có alert riêng cho việc này).
- Alert `booking confirmation rate < 95% trong 10 phút` → cảnh báo có thể đang xảy ra vấn đề ở luồng thanh toán hoặc webhook.')
) AS c(heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical);

-- TOURBOOK: TourBooking Service — Setup môi trường dev
WITH doc AS (
  INSERT INTO knowledge_documents
    (project_id, created_by_user_id, knowledge_domain, document_category, policy_category,
     source_key, category_confirmed, category_classification_status,
     title, source_url, status, created_at, updated_at)
  VALUES (
    (SELECT project_id FROM projects WHERE key = 'TOURBOOK'),
    (SELECT user_id FROM users WHERE email = 'pm.tourbook@onboarding.dev'),
    'PROJECT', 'SETUP', NULL,
    'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/tourbook/setup', true, 'CLASSIFIED',
    'TourBooking Service — Setup môi trường dev', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/tourbook/setup', 'ACTIVE', now(), now()
  )
  RETURNING document_id
),
ver AS (
  INSERT INTO document_versions
    (document_id, version_no, revision_no, embedding_model_version,
     storage_uri, checksum, status, created_at)
  SELECT document_id, 1, 1, 'pending', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/tourbook/setup', '1063a91e3d9a57bc7272caa4cee67b082fcf4d5d4a30537555715fb94ac66c9a', 'ACTIVE', now() FROM doc
  RETURNING version_id
)
INSERT INTO document_chunks (version_id, heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical)
SELECT ver.version_id, c.heading, c.content, c.chunk_index, c.token_count, c.embedding_text, c.content_hash, c.embedding_model_version, c.lexical_identifiers, c.lexical_technical
FROM ver, (VALUES
    (NULL::text, '# TourBooking Service — Setup môi trường dev', 0, 8, '# TourBooking Service — Setup môi trường dev', 'd9b53ee31755360d68cee8d4a613cf4118cba5f6913cfa7c815ae4efd32fcfe9', 'pending', '', '# TourBooking Service — Setup môi trường dev'),
    ('Tổng quan'::text, 'TourBooking Service là 1 Spring Boot application duy nhất (modular monolith), khác với PhoneShop là hệ nhiều microservice — nghĩa là setup đơn giản hơn nhiều, chỉ cần clone 1 repo và chạy.', 1, 33, 'TourBooking Service là 1 Spring Boot application duy nhất (modular monolith), khác với PhoneShop là hệ nhiều microservice — nghĩa là setup đơn giản hơn nhiều, chỉ cần clone 1 repo và chạy.', '93ec89e3fb78fa1d13038a79ea97a1f43ed43776da596394e98fb86c4a2dde51', 'pending', '', 'TourBooking Service là 1 Spring Boot application duy nhất (modular monolith), khác với PhoneShop là hệ nhiều microservice — nghĩa là setup đơn giản hơn nhiều, chỉ cần clone 1 repo và chạy.'),
    ('Yêu cầu hệ thống'::text, '- **JDK 21** (khuyến nghị dùng SDKMAN để quản lý version: `sdk install java 21-tem`).
- **Maven 3.9+** (dự án dùng Maven Wrapper `./mvnw`, không cần cài Maven riêng nếu không muốn).
- **Docker + Docker Compose**.
- **IntelliJ IDEA** (khuyến nghị, team dùng chung 1 bộ code style export sẵn trong `.idea/codeStyles/` — import vào IDE để tự động format đúng chuẩn).', 2, 63, '- **JDK 21** (khuyến nghị dùng SDKMAN để quản lý version: `sdk install java 21-tem`).
- **Maven 3.9+** (dự án dùng Maven Wrapper `./mvnw`, không cần cài Maven riêng nếu không muốn).
- **Docker + Docker Compose**.
- **IntelliJ IDEA** (khuyến nghị, team dùng chung 1 bộ code style export sẵn trong `.idea/codeStyles/` — import vào IDE để tự động format đúng chuẩn).', '1ed256a3db715a384182cb50ba7090c8e2bf078f31b73bc4d9a846c9c255b6db', 'pending', '', '- **JDK 21** (khuyến nghị dùng SDKMAN để quản lý version: `sdk install java 21-tem`).
- **Maven 3.9+** (dự án dùng Maven Wrapper `./mvnw`, không cần cài Maven riêng nếu không muốn).
- **Docker + Docker Compose**.
- **IntelliJ IDEA** (khuyến nghị, team dùng chung 1 bộ code style export sẵn trong `.idea/codeStyles/` — import vào IDE để tự động format đúng chuẩn).'),
    ('Các bước setup từ đầu'::text, '```bash
git clone git@github.com:company/tourbooking-service.git
cd tourbooking-service
cp application-example.yml src/main/resources/application-local.yml
# điền datasource.url, redis.host, elasticsearch.uris trong file vừa copy

docker compose up -d postgres redis elasticsearch kafka  # Kafka cần cho Debezium CDC

./mvnw flyway:migrate
./mvnw spring-boot:run -Dspring-boot.run.profiles=local
```

Lần đầu build Maven có thể mất 5-10 phút để tải toàn bộ dependency. Các lần sau nhanh hơn nhiều nhờ cache local (`~/.m2/repository`).', 3, 62, '```bash
git clone git@github.com:company/tourbooking-service.git
cd tourbooking-service
cp application-example.yml src/main/resources/application-local.yml
# điền datasource.url, redis.host, elasticsearch.uris trong file vừa copy

docker compose up -d postgres redis elasticsearch kafka  # Kafka cần cho Debezium CDC

./mvnw flyway:migrate
./mvnw spring-boot:run -Dspring-boot.run.profiles=local
```

Lần đầu build Maven có thể mất 5-10 phút để tải toàn bộ dependency. Các lần sau nhanh hơn nhiều nhờ cache local (`~/.m2/repository`).', 'c22dd370811b2b11b7ec05cec5487345369eef0ba0454d30ed32d3b93c57093b', 'pending', '', '```bash
git clone git@github.com:company/tourbooking-service.git
cd tourbooking-service
cp application-example.yml src/main/resources/application-local.yml
# điền datasource.url, redis.host, elasticsearch.uris trong file vừa copy

docker compose up -d postgres redis elasticsearch kafka  # Kafka cần cho Debezium CDC

./mvnw flyway:migrate
./mvnw spring-boot:run -Dspring-boot.run.profiles=local
```

Lần đầu build Maven có thể mất 5-10 phút để tải toàn bộ dependency. Các lần sau nhanh hơn nhiều nhờ cache local (`~/.m2/repository`).'),
    ('Bật đồng bộ Elasticsearch (tuỳ chọn, chỉ cần nếu đang làm việc liên quan tìm kiếm)'::text, '```bash
docker compose up -d debezium-connector
curl -X POST http://localhost:8083/connectors -H "Content-Type: application/json" -d @debezium/postgres-connector-config.json
```
Nếu không cần test tính năng search, có thể bỏ qua bước này — các tính năng khác (booking, partner) không phụ thuộc Elasticsearch.', 4, 40, '```bash
docker compose up -d debezium-connector
curl -X POST http://localhost:8083/connectors -H "Content-Type: application/json" -d @debezium/postgres-connector-config.json
```
Nếu không cần test tính năng search, có thể bỏ qua bước này — các tính năng khác (booking, partner) không phụ thuộc Elasticsearch.', '7f8d41f2e32c64aadd8623a426c69241a73c7fb7aa9b20602c7c82502071a721', 'pending', '', '```bash
docker compose up -d debezium-connector
curl -X POST http://localhost:8083/connectors -H "Content-Type: application/json" -d @debezium/postgres-connector-config.json
```
Nếu không cần test tính năng search, có thể bỏ qua bước này — các tính năng khác (booking, partner) không phụ thuộc Elasticsearch.'),
    ('Seed data mẫu'::text, '```bash
./mvnw exec:java -Dexec.mainClass="com.tourbook.tools.SeedDataRunner"
```
Tạo ~20 tour mẫu với nhiều điểm đến (Đà Nẵng, Phú Quốc, Sapa, Hạ Long...), mỗi tour có 3-5 lịch khởi hành trong 2 tháng tới, và 5 đối tác lữ hành demo.', 5, 38, '```bash
./mvnw exec:java -Dexec.mainClass="com.tourbook.tools.SeedDataRunner"
```
Tạo ~20 tour mẫu với nhiều điểm đến (Đà Nẵng, Phú Quốc, Sapa, Hạ Long...), mỗi tour có 3-5 lịch khởi hành trong 2 tháng tới, và 5 đối tác lữ hành demo.', '8ceed8d1f52bfc80c2d484ddc9b19c25164d5bea1a86a04431c57a035da32e51', 'pending', '', '```bash
./mvnw exec:java -Dexec.mainClass="com.tourbook.tools.SeedDataRunner"
```
Tạo ~20 tour mẫu với nhiều điểm đến (Đà Nẵng, Phú Quốc, Sapa, Hạ Long...), mỗi tour có 3-5 lịch khởi hành trong 2 tháng tới, và 5 đối tác lữ hành demo.'),
    ('Kiểm tra chạy đúng'::text, '1. Mở `http://localhost:8080/swagger-ui.html` — thấy đủ nhóm API `tours`, `bookings`, `partners`.
2. Gọi `GET /actuator/health` phải trả `{"status":"UP"}` (Spring Boot Actuator, đã bật sẵn health indicator cho Postgres, Redis, Elasticsearch).
3. Gọi `GET /api/tours?destination=Đà Nẵng` phải trả về danh sách tour đã seed.
4. Thử luồng đặt chỗ đầy đủ: tạo booking → xác nhận giữ chỗ xuất hiện trong Redis (`redis-cli KEYS "booking:hold:*"`) → giả lập thanh toán thành công (endpoint test `/api/test/simulate-payment/{bookingId}`, chỉ có ở môi trường local/staging) → xác nhận `available_seats` giảm đúng.', 6, 86, '1. Mở `http://localhost:8080/swagger-ui.html` — thấy đủ nhóm API `tours`, `bookings`, `partners`.
2. Gọi `GET /actuator/health` phải trả `{"status":"UP"}` (Spring Boot Actuator, đã bật sẵn health indicator cho Postgres, Redis, Elasticsearch).
3. Gọi `GET /api/tours?destination=Đà Nẵng` phải trả về danh sách tour đã seed.
4. Thử luồng đặt chỗ đầy đủ: tạo booking → xác nhận giữ chỗ xuất hiện trong Redis (`redis-cli KEYS "booking:hold:*"`) → giả lập thanh toán thành công (endpoint test `/api/test/simulate-payment/{bookingId}`, chỉ có ở môi trường local/staging) → xác nhận `available_seats` giảm đúng.', 'da45415730ccc133c2f66f3728217bb83cdfa6c18e87cd88a3e6067356b7a2ff', 'pending', '', '1. Mở `http://localhost:8080/swagger-ui.html` — thấy đủ nhóm API `tours`, `bookings`, `partners`.
2. Gọi `GET /actuator/health` phải trả `{"status":"UP"}` (Spring Boot Actuator, đã bật sẵn health indicator cho Postgres, Redis, Elasticsearch).
3. Gọi `GET /api/tours?destination=Đà Nẵng` phải trả về danh sách tour đã seed.
4. Thử luồng đặt chỗ đầy đủ: tạo booking → xác nhận giữ chỗ xuất hiện trong Redis (`redis-cli KEYS "booking:hold:*"`) → giả lập thanh toán thành công (endpoint test `/api/test/simulate-payment/{bookingId}`, chỉ có ở môi trường local/staging) → xác nhận `available_seats` giảm đúng.'),
    ('Chạy test'::text, '```bash
./mvnw test                              # unit test, chạy nhanh
./mvnw verify -Pintegration-test          # integration test, dùng Testcontainers tự dựng Postgres/Redis
./mvnw jacoco:report                       # coverage report, xem tại target/site/jacoco/index.html
```', 7, 28, '```bash
./mvnw test                              # unit test, chạy nhanh
./mvnw verify -Pintegration-test          # integration test, dùng Testcontainers tự dựng Postgres/Redis
./mvnw jacoco:report                       # coverage report, xem tại target/site/jacoco/index.html
```', '8ba57129eaaa68e31ad583ee566219a5f301723dc5873f7fd13cf5374f2e73b8', 'pending', '', '```bash
./mvnw test                              # unit test, chạy nhanh
./mvnw verify -Pintegration-test          # integration test, dùng Testcontainers tự dựng Postgres/Redis
./mvnw jacoco:report                       # coverage report, xem tại target/site/jacoco/index.html
```'),
    ('Lỗi thường gặp'::text, '| Lỗi | Nguyên nhân | Cách fix |
|---|---|---|
| `Connection to localhost:5432 refused` | Container `postgres` chưa healthy | `docker compose ps`, đợi container `healthy` |
| `FlywayException: Validate failed` | Có migration mới trên `main` chưa pull hoặc migration local bị sửa tay sau khi đã chạy | `git pull`, KHÔNG BAO GIỜ sửa file migration đã merge — luôn tạo migration mới |
| Elasticsearch connection timeout | Elasticsearch cần nhiều RAM hơn Docker Desktop mặc định cấp | Tăng RAM cho Docker Desktop lên tối thiểu 4GB trong Settings |
| IntelliJ báo lỗi "cannot resolve symbol" dù build Maven OK | IDE chưa reimport Maven project sau khi đổi `pom.xml` | Chuột phải `pom.xml` → Maven → Reload Project |
| Virtual Threads gây lỗi lạ với thư viện cũ | Một số thư viện dùng `ThreadLocal` không tương thích tốt với Virtual Threads | Đã ghi danh sách thư viện biết có vấn đề trong `docs/virtual-threads-caveats.md` nội bộ repo |', 8, 167, '| Lỗi | Nguyên nhân | Cách fix |
|---|---|---|
| `Connection to localhost:5432 refused` | Container `postgres` chưa healthy | `docker compose ps`, đợi container `healthy` |
| `FlywayException: Validate failed` | Có migration mới trên `main` chưa pull hoặc migration local bị sửa tay sau khi đã chạy | `git pull`, KHÔNG BAO GIỜ sửa file migration đã merge — luôn tạo migration mới |
| Elasticsearch connection timeout | Elasticsearch cần nhiều RAM hơn Docker Desktop mặc định cấp | Tăng RAM cho Docker Desktop lên tối thiểu 4GB trong Settings |
| IntelliJ báo lỗi "cannot resolve symbol" dù build Maven OK | IDE chưa reimport Maven project sau khi đổi `pom.xml` | Chuột phải `pom.xml` → Maven → Reload Project |
| Virtual Threads gây lỗi lạ với thư viện cũ | Một số thư viện dùng `ThreadLocal` không tương thích tốt với Virtual Threads | Đã ghi danh sách thư viện biết có vấn đề trong `docs/virtual-threads-caveats.md` nội bộ repo |', '89a47e983147a8f2d6df9b5fcd925648ed8840f000028247b3846e449a912c52', 'pending', '', '| Lỗi | Nguyên nhân | Cách fix |
|---|---|---|
| `Connection to localhost:5432 refused` | Container `postgres` chưa healthy | `docker compose ps`, đợi container `healthy` |
| `FlywayException: Validate failed` | Có migration mới trên `main` chưa pull hoặc migration local bị sửa tay sau khi đã chạy | `git pull`, KHÔNG BAO GIỜ sửa file migration đã merge — luôn tạo migration mới |
| Elasticsearch connection timeout | Elasticsearch cần nhiều RAM hơn Docker Desktop mặc định cấp | Tăng RAM cho Docker Desktop lên tối thiểu 4GB trong Settings |
| IntelliJ báo lỗi "cannot resolve symbol" dù build Maven OK | IDE chưa reimport Maven project sau khi đổi `pom.xml` | Chuột phải `pom.xml` → Maven → Reload Project |
| Virtual Threads gây lỗi lạ với thư viện cũ | Một số thư viện dùng `ThreadLocal` không tương thích tốt với Virtual Threads | Đã ghi danh sách thư viện biết có vấn đề trong `docs/virtual-threads-caveats.md` nội bộ repo |'),
    ('CI/CD'::text, 'Push lên nhánh bất kỳ → GitHub Actions chạy `./mvnw verify` (bao gồm unit + integration test) + Spotless check. Merge vào `main` → build Docker image, push ECR, AWS CodeDeploy triển khai blue/green lên staging tự động. Production cần approve thủ công, sau đó CodeDeploy chuyển traffic dần sang phiên bản mới (canary 10% → 50% → 100%, tự động rollback nếu error rate tăng bất thường trong quá trình chuyển).', 9, 72, 'Push lên nhánh bất kỳ → GitHub Actions chạy `./mvnw verify` (bao gồm unit + integration test) + Spotless check. Merge vào `main` → build Docker image, push ECR, AWS CodeDeploy triển khai blue/green lên staging tự động. Production cần approve thủ công, sau đó CodeDeploy chuyển traffic dần sang phiên bản mới (canary 10% → 50% → 100%, tự động rollback nếu error rate tăng bất thường trong quá trình chuyển).', '5bf557bd288f37d48f442fe2c5182080868ad2c86ec5ca436d3f72d2f14e0dbb', 'pending', '', 'Push lên nhánh bất kỳ → GitHub Actions chạy `./mvnw verify` (bao gồm unit + integration test) + Spotless check. Merge vào `main` → build Docker image, push ECR, AWS CodeDeploy triển khai blue/green lên staging tự động. Production cần approve thủ công, sau đó CodeDeploy chuyển traffic dần sang phiên bản mới (canary 10% → 50% → 100%, tự động rollback nếu error rate tăng bất thường trong quá trình chuyển).')
) AS c(heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical);

-- TOURBOOK: TourBooking Service — Access & Security
WITH doc AS (
  INSERT INTO knowledge_documents
    (project_id, created_by_user_id, knowledge_domain, document_category, policy_category,
     source_key, category_confirmed, category_classification_status,
     title, source_url, status, created_at, updated_at)
  VALUES (
    (SELECT project_id FROM projects WHERE key = 'TOURBOOK'),
    (SELECT user_id FROM users WHERE email = 'pm.tourbook@onboarding.dev'),
    'PROJECT', 'ACCESS_SECURITY', NULL,
    'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/tourbook/access-security', true, 'CLASSIFIED',
    'TourBooking Service — Access & Security', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/tourbook/access-security', 'ACTIVE', now(), now()
  )
  RETURNING document_id
),
ver AS (
  INSERT INTO document_versions
    (document_id, version_no, revision_no, embedding_model_version,
     storage_uri, checksum, status, created_at)
  SELECT document_id, 1, 1, 'pending', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/tourbook/access-security', 'd43ac33f600efd8c4022c66c50aa35c99e0179cf753eddc8f9153eeff305ef77', 'ACTIVE', now() FROM doc
  RETURNING version_id
)
INSERT INTO document_chunks (version_id, heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical)
SELECT ver.version_id, c.heading, c.content, c.chunk_index, c.token_count, c.embedding_text, c.content_hash, c.embedding_model_version, c.lexical_identifiers, c.lexical_technical
FROM ver, (VALUES
    (NULL::text, '# TourBooking Service — Access & Security', 0, 7, '# TourBooking Service — Access & Security', 'ca3e77194e025b516758cbbf04067adeb1b032be210d5068884429554d735dc9', 'pending', '', '# TourBooking Service — Access & Security'),
    ('Đặc thù bảo mật của TourBooking'::text, 'Khác với PhoneShop (chỉ có nội bộ công ty truy cập hệ thống), TourBooking có thêm 1 nhóm người dùng ngoài công ty truy cập trực tiếp vào hệ thống: **đối tác lữ hành** qua Partner Portal. Đây là bề mặt tấn công (attack surface) lớn hơn cần cân nhắc kỹ — mọi input từ Partner Portal đều được coi là **không tin cậy** ở mức độ tương đương input từ khách hàng thông thường, không có ngoại lệ dù đối tác đã được xác thực.', 1, 86, 'Khác với PhoneShop (chỉ có nội bộ công ty truy cập hệ thống), TourBooking có thêm 1 nhóm người dùng ngoài công ty truy cập trực tiếp vào hệ thống: **đối tác lữ hành** qua Partner Portal. Đây là bề mặt tấn công (attack surface) lớn hơn cần cân nhắc kỹ — mọi input từ Partner Portal đều được coi là **không tin cậy** ở mức độ tương đương input từ khách hàng thông thường, không có ngoại lệ dù đối tác đã được xác thực.', '1f947af2bb2e065ac2df7520b3f307c758786920b2eae21c8463d9e7038fed5c', 'pending', '', 'Khác với PhoneShop (chỉ có nội bộ công ty truy cập hệ thống), TourBooking có thêm 1 nhóm người dùng ngoài công ty truy cập trực tiếp vào hệ thống: **đối tác lữ hành** qua Partner Portal. Đây là bề mặt tấn công (attack surface) lớn hơn cần cân nhắc kỹ — mọi input từ Partner Portal đều được coi là **không tin cậy** ở mức độ tương đương input từ khách hàng thông thường, không có ngoại lệ dù đối tác đã được xác thực.'),
    ('Xin quyền truy cập'::text, '| Hệ thống | Cách xin | Ai duyệt | Thời gian xử lý |
|---|---|---|---|
| Repo GitHub (team `tourbook-backend`) | PM thêm qua GitHub Org settings | PM | Trong ngày làm việc đầu |
| AWS Console (read-only staging) | Xin qua IT theo form chuẩn, MFA bắt buộc | IT + Tech Lead | 1-2 ngày làm việc |
| Elasticsearch Kibana | Truy cập qua VPN nội bộ, credential riêng theo từng người (không dùng chung tài khoản) | Tech Lead | 1 ngày làm việc |
| Partner Portal (test account) | Tạo tài khoản test riêng qua script seed, KHÔNG dùng tài khoản đối tác thật để test | Tự làm, không cần duyệt | Ngay lập tức |
| Database production | Qua bastion host, audit log đầy đủ, chỉ Lead/on-call | Engineering Manager | Xét duyệt riêng |
| Opsgenie on-call access | Tự động khi vào lịch on-call rotation | Tech Lead | Theo lịch on-call |', 2, 167, '| Hệ thống | Cách xin | Ai duyệt | Thời gian xử lý |
|---|---|---|---|
| Repo GitHub (team `tourbook-backend`) | PM thêm qua GitHub Org settings | PM | Trong ngày làm việc đầu |
| AWS Console (read-only staging) | Xin qua IT theo form chuẩn, MFA bắt buộc | IT + Tech Lead | 1-2 ngày làm việc |
| Elasticsearch Kibana | Truy cập qua VPN nội bộ, credential riêng theo từng người (không dùng chung tài khoản) | Tech Lead | 1 ngày làm việc |
| Partner Portal (test account) | Tạo tài khoản test riêng qua script seed, KHÔNG dùng tài khoản đối tác thật để test | Tự làm, không cần duyệt | Ngay lập tức |
| Database production | Qua bastion host, audit log đầy đủ, chỉ Lead/on-call | Engineering Manager | Xét duyệt riêng |
| Opsgenie on-call access | Tự động khi vào lịch on-call rotation | Tech Lead | Theo lịch on-call |', '7d46c8b35a097dd5bf2b4f235f00dcd1241f641730c850fdf766ffd6fee25e1c', 'pending', '', '| Hệ thống | Cách xin | Ai duyệt | Thời gian xử lý |
|---|---|---|---|
| Repo GitHub (team `tourbook-backend`) | PM thêm qua GitHub Org settings | PM | Trong ngày làm việc đầu |
| AWS Console (read-only staging) | Xin qua IT theo form chuẩn, MFA bắt buộc | IT + Tech Lead | 1-2 ngày làm việc |
| Elasticsearch Kibana | Truy cập qua VPN nội bộ, credential riêng theo từng người (không dùng chung tài khoản) | Tech Lead | 1 ngày làm việc |
| Partner Portal (test account) | Tạo tài khoản test riêng qua script seed, KHÔNG dùng tài khoản đối tác thật để test | Tự làm, không cần duyệt | Ngay lập tức |
| Database production | Qua bastion host, audit log đầy đủ, chỉ Lead/on-call | Engineering Manager | Xét duyệt riêng |
| Opsgenie on-call access | Tự động khi vào lịch on-call rotation | Tech Lead | Theo lịch on-call |'),
    ('Quy tắc bảo mật'::text, '- Spring Security filter chain bắt buộc áp dụng trên mọi endpoint trừ `/auth/**` (login/register) và `/actuator/health` (health check cho load balancer) — không có ngoại lệ khác, kể cả endpoint tưởng chừng vô hại như `GET /api/tours` cũng qua filter (dù không yêu cầu login, vẫn qua rate limiting).
- **Xác thực đối tác tách biệt hoàn toàn với xác thực khách hàng**: dùng 2 loại JWT khác nhau với `audience` claim khác nhau, đảm bảo token của đối tác không thể dùng để gọi API dành cho khách hàng và ngược lại — tránh lỗi privilege escalation nếu 1 bên bị lộ token.
- Token API đối tác lữ hành (Partner API key, dùng cho tích hợp server-to-server nếu đối tác có hệ thống riêng) có thời hạn 90 ngày, tự động gửi email nhắc gia hạn trước 7 ngày, tự động vô hiệu hoá nếu không gia hạn (không gia hạn ngầm định vô thời hạn).
- Mọi input từ Partner Portal (giá tour, số chỗ, mô tả) đều validate nghiêm ngặt ở tầng Bean Validation (`@Valid`) VÀ validate lại lần nữa ở tầng service — không tin tưởng chỉ validation ở 1 lớp. Riêng thay đổi giá có chênh lệch bất thường (>50% so với giá hiện tại) yêu cầu xác nhận 2 bước, bài học rút ra từ sự cố tháng 06/2025 (xem `overview.md`).
- Không log thông tin thẻ thanh toán hay số CCCD/hộ chiếu (một số tour yêu cầu thông tin này để làm thủ tục) ra application log, kể cả ở log level DEBUG — các trường này được đánh dấu `@Sensitive` custom annotation, tự động mask khi serialize log qua Logback custom converter.
- Rate limiting riêng cho Partner Portal API (60 request/phút/đối tác) tách biệt với rate limiting cho khách hàng thông thường (120 request/phút/user), tránh 1 đối tác có hệ thống tích hợp lỗi (gọi API liên tục do bug) làm ảnh hưởng tới trải nghiệm khách hàng.', 3, 329, '- Spring Security filter chain bắt buộc áp dụng trên mọi endpoint trừ `/auth/**` (login/register) và `/actuator/health` (health check cho load balancer) — không có ngoại lệ khác, kể cả endpoint tưởng chừng vô hại như `GET /api/tours` cũng qua filter (dù không yêu cầu login, vẫn qua rate limiting).
- **Xác thực đối tác tách biệt hoàn toàn với xác thực khách hàng**: dùng 2 loại JWT khác nhau với `audience` claim khác nhau, đảm bảo token của đối tác không thể dùng để gọi API dành cho khách hàng và ngược lại — tránh lỗi privilege escalation nếu 1 bên bị lộ token.
- Token API đối tác lữ hành (Partner API key, dùng cho tích hợp server-to-server nếu đối tác có hệ thống riêng) có thời hạn 90 ngày, tự động gửi email nhắc gia hạn trước 7 ngày, tự động vô hiệu hoá nếu không gia hạn (không gia hạn ngầm định vô thời hạn).
- Mọi input từ Partner Portal (giá tour, số chỗ, mô tả) đều validate nghiêm ngặt ở tầng Bean Validation (`@Valid`) VÀ validate lại lần nữa ở tầng service — không tin tưởng chỉ validation ở 1 lớp. Riêng thay đổi giá có chênh lệch bất thường (>50% so với giá hiện tại) yêu cầu xác nhận 2 bước, bài học rút ra từ sự cố tháng 06/2025 (xem `overview.md`).
- Không log thông tin thẻ thanh toán hay số CCCD/hộ chiếu (một số tour yêu cầu thông tin này để làm thủ tục) ra application log, kể cả ở log level DEBUG — các trường này được đánh dấu `@Sensitive` custom annotation, tự động mask khi serialize log qua Logback custom converter.
- Rate limiting riêng cho Partner Portal API (60 request/phút/đối tác) tách biệt với rate limiting cho khách hàng thông thường (120 request/phút/user), tránh 1 đối tác có hệ thống tích hợp lỗi (gọi API liên tục do bug) làm ảnh hưởng tới trải nghiệm khách hàng.', 'a9715ebe122f6a86db299bd5d88c0c4291dbada66a4bb1d90b3c0cf7beb5e89c', 'pending', '', '- Spring Security filter chain bắt buộc áp dụng trên mọi endpoint trừ `/auth/**` (login/register) và `/actuator/health` (health check cho load balancer) — không có ngoại lệ khác, kể cả endpoint tưởng chừng vô hại như `GET /api/tours` cũng qua filter (dù không yêu cầu login, vẫn qua rate limiting).
- **Xác thực đối tác tách biệt hoàn toàn với xác thực khách hàng**: dùng 2 loại JWT khác nhau với `audience` claim khác nhau, đảm bảo token của đối tác không thể dùng để gọi API dành cho khách hàng và ngược lại — tránh lỗi privilege escalation nếu 1 bên bị lộ token.
- Token API đối tác lữ hành (Partner API key, dùng cho tích hợp server-to-server nếu đối tác có hệ thống riêng) có thời hạn 90 ngày, tự động gửi email nhắc gia hạn trước 7 ngày, tự động vô hiệu hoá nếu không gia hạn (không gia hạn ngầm định vô thời hạn).
- Mọi input từ Partner Portal (giá tour, số chỗ, mô tả) đều validate nghiêm ngặt ở tầng Bean Validation (`@Valid`) VÀ validate lại lần nữa ở tầng service — không tin tưởng chỉ validation ở 1 lớp. Riêng thay đổi giá có chênh lệch bất thường (>50% so với giá hiện tại) yêu cầu xác nhận 2 bước, bài học rút ra từ sự cố tháng 06/2025 (xem `overview.md`).
- Không log thông tin thẻ thanh toán hay số CCCD/hộ chiếu (một số tour yêu cầu thông tin này để làm thủ tục) ra application log, kể cả ở log level DEBUG — các trường này được đánh dấu `@Sensitive` custom annotation, tự động mask khi serialize log qua Logback custom converter.
- Rate limiting riêng cho Partner Portal API (60 request/phút/đối tác) tách biệt với rate limiting cho khách hàng thông thường (120 request/phút/user), tránh 1 đối tác có hệ thống tích hợp lỗi (gọi API liên tục do bug) làm ảnh hưởng tới trải nghiệm khách hàng.'),
    ('Compliance'::text, 'Thông tin CCCD/hộ chiếu khách hàng cung cấp cho một số tour (yêu cầu làm thủ tục xuất cảnh/vé máy bay) được mã hoá tại tầng ứng dụng và có thời hạn lưu trữ giới hạn (tự động xoá sau 90 ngày kể từ ngày kết thúc tour, trừ trường hợp có yêu cầu pháp lý khác). Tuân theo Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân.', 4, 69, 'Thông tin CCCD/hộ chiếu khách hàng cung cấp cho một số tour (yêu cầu làm thủ tục xuất cảnh/vé máy bay) được mã hoá tại tầng ứng dụng và có thời hạn lưu trữ giới hạn (tự động xoá sau 90 ngày kể từ ngày kết thúc tour, trừ trường hợp có yêu cầu pháp lý khác). Tuân theo Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân.', '9f2da5213138c8a084c9b26a5c5e8c36ce53319f4bfe8aaffb2ad7ab2b3e2646', 'pending', '', 'Thông tin CCCD/hộ chiếu khách hàng cung cấp cho một số tour (yêu cầu làm thủ tục xuất cảnh/vé máy bay) được mã hoá tại tầng ứng dụng và có thời hạn lưu trữ giới hạn (tự động xoá sau 90 ngày kể từ ngày kết thúc tour, trừ trường hợp có yêu cầu pháp lý khác). Tuân theo Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân.'),
    ('Liên hệ khi có sự cố bảo mật'::text, 'Báo Security team qua kênh #security-incident kèm mức độ ảnh hưởng ước tính (bao nhiêu đối tác/khách hàng bị ảnh hưởng nếu biết), không tự xử lý âm thầm dưới bất kỳ hình thức nào — kể cả khi tưởng chừng đã khắc phục xong, vẫn cần báo cáo đầy đủ để Security team đánh giá có cần thông báo cho các bên liên quan hay không.', 5, 67, 'Báo Security team qua kênh #security-incident kèm mức độ ảnh hưởng ước tính (bao nhiêu đối tác/khách hàng bị ảnh hưởng nếu biết), không tự xử lý âm thầm dưới bất kỳ hình thức nào — kể cả khi tưởng chừng đã khắc phục xong, vẫn cần báo cáo đầy đủ để Security team đánh giá có cần thông báo cho các bên liên quan hay không.', 'a2d9a5879b530cc89455a15b7f981e7f5d817106d879fcb9b9583ec2fc5aa27a', 'pending', '', 'Báo Security team qua kênh #security-incident kèm mức độ ảnh hưởng ước tính (bao nhiêu đối tác/khách hàng bị ảnh hưởng nếu biết), không tự xử lý âm thầm dưới bất kỳ hình thức nào — kể cả khi tưởng chừng đã khắc phục xong, vẫn cần báo cáo đầy đủ để Security team đánh giá có cần thông báo cho các bên liên quan hay không.')
) AS c(heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical);

-- TOURBOOK: TourBooking Service — Codebase Guide
WITH doc AS (
  INSERT INTO knowledge_documents
    (project_id, created_by_user_id, knowledge_domain, document_category, policy_category,
     source_key, category_confirmed, category_classification_status,
     title, source_url, status, created_at, updated_at)
  VALUES (
    (SELECT project_id FROM projects WHERE key = 'TOURBOOK'),
    (SELECT user_id FROM users WHERE email = 'pm.tourbook@onboarding.dev'),
    'PROJECT', 'CODEBASE_GUIDE', NULL,
    'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/tourbook/codebase-guide', true, 'CLASSIFIED',
    'TourBooking Service — Codebase Guide', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/tourbook/codebase-guide', 'ACTIVE', now(), now()
  )
  RETURNING document_id
),
ver AS (
  INSERT INTO document_versions
    (document_id, version_no, revision_no, embedding_model_version,
     storage_uri, checksum, status, created_at)
  SELECT document_id, 1, 1, 'pending', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/tourbook/codebase-guide', 'e867b426992a2d3dd2cbf93c04d85a5ff5ecb237706d73eb527c132010fd1ef2', 'ACTIVE', now() FROM doc
  RETURNING version_id
)
INSERT INTO document_chunks (version_id, heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical)
SELECT ver.version_id, c.heading, c.content, c.chunk_index, c.token_count, c.embedding_text, c.content_hash, c.embedding_model_version, c.lexical_identifiers, c.lexical_technical
FROM ver, (VALUES
    (NULL::text, '# TourBooking Service — Codebase Guide', 0, 6, '# TourBooking Service — Codebase Guide', '27f26bc1c8778ecd770a629ded27a23efea8039f2fd24500b667939accc4e0cc', 'pending', '', '# TourBooking Service — Codebase Guide'),
    ('Cấu trúc package đầy đủ'::text, '```
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
```', 1, 132, '```
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
```', '3f77d9accd29f6f6046db4d4c30bb1df85ae12c7a3f3deee3c9b1c8f834030aa', 'pending', '', '```
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
```'),
    ('Nguyên tắc kiến trúc'::text, 'Theo layering chuẩn Spring Boot: `Controller -> Service -> Repository`. Controller chỉ validate input (`@Valid` + Bean Validation annotation) và gọi Service, tuyệt đối không chứa business logic dưới bất kỳ hình thức nào, kể cả logic tưởng chừng đơn giản như "nếu số lượng khách > 10 thì áp dụng giá đoàn" — logic này phải nằm trong `TourPricingService`, không viết trực tiếp trong controller.

Mọi rule nghiệp vụ quan trọng (giữ chỗ 15 phút, kiểm tra overbooking, tính phí huỷ theo thời gian) nằm ở Service layer, được test kỹ bằng unit test với Mockito mock toàn bộ repository/external call.', 2, 102, 'Theo layering chuẩn Spring Boot: `Controller -> Service -> Repository`. Controller chỉ validate input (`@Valid` + Bean Validation annotation) và gọi Service, tuyệt đối không chứa business logic dưới bất kỳ hình thức nào, kể cả logic tưởng chừng đơn giản như "nếu số lượng khách > 10 thì áp dụng giá đoàn" — logic này phải nằm trong `TourPricingService`, không viết trực tiếp trong controller.

Mọi rule nghiệp vụ quan trọng (giữ chỗ 15 phút, kiểm tra overbooking, tính phí huỷ theo thời gian) nằm ở Service layer, được test kỹ bằng unit test với Mockito mock toàn bộ repository/external call.', '3bf87de9b6aaecc1539c38487cd9d81323c08b3b6fce9cfda1cbe0ee3a9a3ace', 'pending', '', 'Theo layering chuẩn Spring Boot: `Controller -> Service -> Repository`. Controller chỉ validate input (`@Valid` + Bean Validation annotation) và gọi Service, tuyệt đối không chứa business logic dưới bất kỳ hình thức nào, kể cả logic tưởng chừng đơn giản như "nếu số lượng khách > 10 thì áp dụng giá đoàn" — logic này phải nằm trong `TourPricingService`, không viết trực tiếp trong controller.

Mọi rule nghiệp vụ quan trọng (giữ chỗ 15 phút, kiểm tra overbooking, tính phí huỷ theo thời gian) nằm ở Service layer, được test kỹ bằng unit test với Mockito mock toàn bộ repository/external call.'),
    ('File quan trọng cần đọc trước khi code'::text, '- **`BookingService.java`** — trung tâm của toàn bộ luồng booking: logic giữ chỗ tạm, xác nhận thanh toán, và job giải phóng chỗ hết hạn. Đây là class có nhiều bài học sau sự cố double booking tháng 02/2025 — đọc kỹ Javadoc comment giải thích tại sao dùng Redisson lock thay vì `@Transactional` đơn thuần.
- **`TourSearchService.java`** — cách sync dữ liệu Tour sang Elasticsearch mỗi khi có thay đổi. Quan trọng: KHÔNG đồng bộ trực tiếp trong cùng transaction lưu Postgres (dùng Spring `@TransactionalEventListener(phase = AFTER_COMMIT)` để đảm bảo chỉ đồng bộ sau khi transaction Postgres đã commit thành công, tránh Elasticsearch có dữ liệu "ảo" nếu transaction Postgres rollback).
- **`ReservationLockService.java`** — wrapper an toàn quanh Redisson, có logic retry với timeout ngắn (500ms) nếu không lấy được lock ngay, tránh block thread quá lâu khi tải cao.
- **`GlobalExceptionHandler.java`** — mọi exception nghiệp vụ (`TourNotFoundException`, `InsufficientSeatsException`, `BookingExpiredException`...) đều map về đúng HTTP status code chuẩn qua đây, controller không tự bắt exception và trả response lỗi thủ công.', 3, 172, '- **`BookingService.java`** — trung tâm của toàn bộ luồng booking: logic giữ chỗ tạm, xác nhận thanh toán, và job giải phóng chỗ hết hạn. Đây là class có nhiều bài học sau sự cố double booking tháng 02/2025 — đọc kỹ Javadoc comment giải thích tại sao dùng Redisson lock thay vì `@Transactional` đơn thuần.
- **`TourSearchService.java`** — cách sync dữ liệu Tour sang Elasticsearch mỗi khi có thay đổi. Quan trọng: KHÔNG đồng bộ trực tiếp trong cùng transaction lưu Postgres (dùng Spring `@TransactionalEventListener(phase = AFTER_COMMIT)` để đảm bảo chỉ đồng bộ sau khi transaction Postgres đã commit thành công, tránh Elasticsearch có dữ liệu "ảo" nếu transaction Postgres rollback).
- **`ReservationLockService.java`** — wrapper an toàn quanh Redisson, có logic retry với timeout ngắn (500ms) nếu không lấy được lock ngay, tránh block thread quá lâu khi tải cao.
- **`GlobalExceptionHandler.java`** — mọi exception nghiệp vụ (`TourNotFoundException`, `InsufficientSeatsException`, `BookingExpiredException`...) đều map về đúng HTTP status code chuẩn qua đây, controller không tự bắt exception và trả response lỗi thủ công.', 'a7f9c152fb9a443f222eed88caa0068227c4cb7a87024f36765480c404bcea68', 'pending', '', '- **`BookingService.java`** — trung tâm của toàn bộ luồng booking: logic giữ chỗ tạm, xác nhận thanh toán, và job giải phóng chỗ hết hạn. Đây là class có nhiều bài học sau sự cố double booking tháng 02/2025 — đọc kỹ Javadoc comment giải thích tại sao dùng Redisson lock thay vì `@Transactional` đơn thuần.
- **`TourSearchService.java`** — cách sync dữ liệu Tour sang Elasticsearch mỗi khi có thay đổi. Quan trọng: KHÔNG đồng bộ trực tiếp trong cùng transaction lưu Postgres (dùng Spring `@TransactionalEventListener(phase = AFTER_COMMIT)` để đảm bảo chỉ đồng bộ sau khi transaction Postgres đã commit thành công, tránh Elasticsearch có dữ liệu "ảo" nếu transaction Postgres rollback).
- **`ReservationLockService.java`** — wrapper an toàn quanh Redisson, có logic retry với timeout ngắn (500ms) nếu không lấy được lock ngay, tránh block thread quá lâu khi tải cao.
- **`GlobalExceptionHandler.java`** — mọi exception nghiệp vụ (`TourNotFoundException`, `InsufficientSeatsException`, `BookingExpiredException`...) đều map về đúng HTTP status code chuẩn qua đây, controller không tự bắt exception và trả response lỗi thủ công.'),
    ('Testing strategy'::text, '- **Unit test**: Mockito mock repository và external service, test riêng logic nghiệp vụ trong Service layer — không cần Spring context, chạy cực nhanh.
- **Integration test** (`@SpringBootTest` + Testcontainers): dựng Postgres + Redis thật, test full luồng từ Controller xuống Repository, đảm bảo wiring Spring đúng và query JPA hoạt động chính xác.
- **Contract test với Partner Portal frontend**: dùng Spring Cloud Contract, đảm bảo response API không đổi bất ngờ làm vỡ Partner Portal.', 4, 78, '- **Unit test**: Mockito mock repository và external service, test riêng logic nghiệp vụ trong Service layer — không cần Spring context, chạy cực nhanh.
- **Integration test** (`@SpringBootTest` + Testcontainers): dựng Postgres + Redis thật, test full luồng từ Controller xuống Repository, đảm bảo wiring Spring đúng và query JPA hoạt động chính xác.
- **Contract test với Partner Portal frontend**: dùng Spring Cloud Contract, đảm bảo response API không đổi bất ngờ làm vỡ Partner Portal.', 'c36637d817ec4f4125cb273cef813422b26fd8c108da58216959c0d444fbd7fe', 'pending', '', '- **Unit test**: Mockito mock repository và external service, test riêng logic nghiệp vụ trong Service layer — không cần Spring context, chạy cực nhanh.
- **Integration test** (`@SpringBootTest` + Testcontainers): dựng Postgres + Redis thật, test full luồng từ Controller xuống Repository, đảm bảo wiring Spring đúng và query JPA hoạt động chính xác.
- **Contract test với Partner Portal frontend**: dùng Spring Cloud Contract, đảm bảo response API không đổi bất ngờ làm vỡ Partner Portal.'),
    ('Lưu ý N+1 query'::text, 'Vì dùng JPA/Hibernate, rủi ro N+1 query luôn hiện hữu khi load `Tour` kèm danh sách `TourDeparture`. Team có quy định bắt buộc: mọi query load entity có quan hệ `@OneToMany` phải dùng `@EntityGraph` hoặc `JOIN FETCH` tường minh, không được để Hibernate tự động lazy-load trong vòng lặp. CI có 1 test riêng dùng thư viện `db-util` để đếm số query SQL thực thi trong mỗi integration test quan trọng, fail nếu vượt ngưỡng dự kiến — cách này đã bắt được nhiều N+1 query tiềm ẩn trước khi lên production.', 5, 92, 'Vì dùng JPA/Hibernate, rủi ro N+1 query luôn hiện hữu khi load `Tour` kèm danh sách `TourDeparture`. Team có quy định bắt buộc: mọi query load entity có quan hệ `@OneToMany` phải dùng `@EntityGraph` hoặc `JOIN FETCH` tường minh, không được để Hibernate tự động lazy-load trong vòng lặp. CI có 1 test riêng dùng thư viện `db-util` để đếm số query SQL thực thi trong mỗi integration test quan trọng, fail nếu vượt ngưỡng dự kiến — cách này đã bắt được nhiều N+1 query tiềm ẩn trước khi lên production.', '174b79ef178c0302c429ab049c72f66ae3e9f006aa0737e00d327cc6359b2b51', 'pending', '', 'Vì dùng JPA/Hibernate, rủi ro N+1 query luôn hiện hữu khi load `Tour` kèm danh sách `TourDeparture`. Team có quy định bắt buộc: mọi query load entity có quan hệ `@OneToMany` phải dùng `@EntityGraph` hoặc `JOIN FETCH` tường minh, không được để Hibernate tự động lazy-load trong vòng lặp. CI có 1 test riêng dùng thư viện `db-util` để đếm số query SQL thực thi trong mỗi integration test quan trọng, fail nếu vượt ngưỡng dự kiến — cách này đã bắt được nhiều N+1 query tiềm ẩn trước khi lên production.'),
    ('AOP cho Audit Log'::text, 'Mọi thao tác nhạy cảm (đối tác đổi giá tour, admin huỷ booking thay khách, thay đổi trạng thái thanh toán thủ công) được tự động ghi audit log qua `AuditLogAspect` (Spring AOP, đánh dấu bằng annotation `@Auditable` trên method), không cần developer tự viết code ghi log thủ công ở từng nơi — giảm rủi ro quên ghi log cho action nhạy cảm mới thêm sau này.', 6, 68, 'Mọi thao tác nhạy cảm (đối tác đổi giá tour, admin huỷ booking thay khách, thay đổi trạng thái thanh toán thủ công) được tự động ghi audit log qua `AuditLogAspect` (Spring AOP, đánh dấu bằng annotation `@Auditable` trên method), không cần developer tự viết code ghi log thủ công ở từng nơi — giảm rủi ro quên ghi log cho action nhạy cảm mới thêm sau này.', '9b4a89d8a507a8915f2642b9ff68c2c050dea1fce534dc95c91eede234722087', 'pending', '', 'Mọi thao tác nhạy cảm (đối tác đổi giá tour, admin huỷ booking thay khách, thay đổi trạng thái thanh toán thủ công) được tự động ghi audit log qua `AuditLogAspect` (Spring AOP, đánh dấu bằng annotation `@Auditable` trên method), không cần developer tự viết code ghi log thủ công ở từng nơi — giảm rủi ro quên ghi log cho action nhạy cảm mới thêm sau này.')
) AS c(heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical);

-- TOURBOOK: TourBooking Service — Coding Convention
WITH doc AS (
  INSERT INTO knowledge_documents
    (project_id, created_by_user_id, knowledge_domain, document_category, policy_category,
     source_key, category_confirmed, category_classification_status,
     title, source_url, status, created_at, updated_at)
  VALUES (
    (SELECT project_id FROM projects WHERE key = 'TOURBOOK'),
    (SELECT user_id FROM users WHERE email = 'pm.tourbook@onboarding.dev'),
    'PROJECT', 'CONVENTION', NULL,
    'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/tourbook/convention', true, 'CLASSIFIED',
    'TourBooking Service — Coding Convention', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/tourbook/convention', 'ACTIVE', now(), now()
  )
  RETURNING document_id
),
ver AS (
  INSERT INTO document_versions
    (document_id, version_no, revision_no, embedding_model_version,
     storage_uri, checksum, status, created_at)
  SELECT document_id, 1, 1, 'pending', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/tourbook/convention', '5c4efeba20ec6fee6e28f02c4bf56f11e1754ad0cdbb0ec28d126bdfe2a3b10f', 'ACTIVE', now() FROM doc
  RETURNING version_id
)
INSERT INTO document_chunks (version_id, heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical)
SELECT ver.version_id, c.heading, c.content, c.chunk_index, c.token_count, c.embedding_text, c.content_hash, c.embedding_model_version, c.lexical_identifiers, c.lexical_technical
FROM ver, (VALUES
    (NULL::text, '# TourBooking Service — Coding Convention', 0, 6, '# TourBooking Service — Coding Convention', '5ec5ad3ee7ce310d14e45c4ab9d5c622cd21664632c6571cb03a8d40dbdd1cd6', 'pending', '', '# TourBooking Service — Coding Convention'),
    ('Triết lý chung'::text, 'Convention được thiết kế để mọi engineer, dù mới hay cũ, đọc code của người khác mà không cần hỏi "tại sao lại viết thế này" — nhất quán quan trọng hơn "cách hay nhất theo ý kiến cá nhân". Mọi bất đồng về style nên giải quyết bằng cách cập nhật rule chung (và tool tự động hoá), không phải tranh luận lặp lại trong từng PR.', 1, 68, 'Convention được thiết kế để mọi engineer, dù mới hay cũ, đọc code của người khác mà không cần hỏi "tại sao lại viết thế này" — nhất quán quan trọng hơn "cách hay nhất theo ý kiến cá nhân". Mọi bất đồng về style nên giải quyết bằng cách cập nhật rule chung (và tool tự động hoá), không phải tranh luận lặp lại trong từng PR.', '45a65ced074d6217b03028ed3c88590770704937926f5cc4a0712e0294b5cae0', 'pending', '', 'Convention được thiết kế để mọi engineer, dù mới hay cũ, đọc code của người khác mà không cần hỏi "tại sao lại viết thế này" — nhất quán quan trọng hơn "cách hay nhất theo ý kiến cá nhân". Mọi bất đồng về style nên giải quyết bằng cách cập nhật rule chung (và tool tự động hoá), không phải tranh luận lặp lại trong từng PR.'),
    ('Java style'::text, '- Format theo Google Java Style Guide, kiểm tra tự động bằng Spotless trong Maven build (`./mvnw spotless:check` chạy trong CI, `./mvnw spotless:apply` để tự format trước khi commit).
- Đặt tên: `camelCase` cho method/biến, `PascalCase` cho class, hằng số `UPPER_SNAKE_CASE`. Package name toàn chữ thường, không gạch dưới.
- Interface không prefix `I` (ví dụ `TourRepository`, không phải `ITourRepository`) — theo convention chuẩn Java hiện đại, khác với 1 số codebase C#/cũ.
- Ưu tiên dùng `record` (Java 17+) cho DTO bất biến thay vì class thông thường với getter/setter — giảm boilerplate đáng kể.
- Không dùng `Optional` làm field trong entity JPA (Hibernate không hỗ trợ tốt), chỉ dùng `Optional` làm kiểu trả về của method ở tầng Service/Repository.
- Exception tự định nghĩa nên extend `RuntimeException` (unchecked), tránh checked exception gây "nhiễm" signature khắp nơi trong codebase — quyết định này khác với 1 số trường phái Java truyền thống, team đã thống nhất từ đầu dự án.', 2, 162, '- Format theo Google Java Style Guide, kiểm tra tự động bằng Spotless trong Maven build (`./mvnw spotless:check` chạy trong CI, `./mvnw spotless:apply` để tự format trước khi commit).
- Đặt tên: `camelCase` cho method/biến, `PascalCase` cho class, hằng số `UPPER_SNAKE_CASE`. Package name toàn chữ thường, không gạch dưới.
- Interface không prefix `I` (ví dụ `TourRepository`, không phải `ITourRepository`) — theo convention chuẩn Java hiện đại, khác với 1 số codebase C#/cũ.
- Ưu tiên dùng `record` (Java 17+) cho DTO bất biến thay vì class thông thường với getter/setter — giảm boilerplate đáng kể.
- Không dùng `Optional` làm field trong entity JPA (Hibernate không hỗ trợ tốt), chỉ dùng `Optional` làm kiểu trả về của method ở tầng Service/Repository.
- Exception tự định nghĩa nên extend `RuntimeException` (unchecked), tránh checked exception gây "nhiễm" signature khắp nơi trong codebase — quyết định này khác với 1 số trường phái Java truyền thống, team đã thống nhất từ đầu dự án.', 'c3e11b79e15e5a4d9243106c3095810dbb16cd269d5212c54b405ca81115dc8e', 'pending', '', '- Format theo Google Java Style Guide, kiểm tra tự động bằng Spotless trong Maven build (`./mvnw spotless:check` chạy trong CI, `./mvnw spotless:apply` để tự format trước khi commit).
- Đặt tên: `camelCase` cho method/biến, `PascalCase` cho class, hằng số `UPPER_SNAKE_CASE`. Package name toàn chữ thường, không gạch dưới.
- Interface không prefix `I` (ví dụ `TourRepository`, không phải `ITourRepository`) — theo convention chuẩn Java hiện đại, khác với 1 số codebase C#/cũ.
- Ưu tiên dùng `record` (Java 17+) cho DTO bất biến thay vì class thông thường với getter/setter — giảm boilerplate đáng kể.
- Không dùng `Optional` làm field trong entity JPA (Hibernate không hỗ trợ tốt), chỉ dùng `Optional` làm kiểu trả về của method ở tầng Service/Repository.
- Exception tự định nghĩa nên extend `RuntimeException` (unchecked), tránh checked exception gây "nhiễm" signature khắp nơi trong codebase — quyết định này khác với 1 số trường phái Java truyền thống, team đã thống nhất từ đầu dự án.'),
    ('Cấu trúc test'::text, 'Đặt tên method test theo pattern `should_<kết quả mong đợi>_when_<điều kiện>`, ví dụ `should_throwInsufficientSeatsException_when_bookingExceedsAvailableSeats()`. Dùng AssertJ cho assertion (`assertThat(...)`), không dùng JUnit assertion cơ bản (`assertEquals`) vì AssertJ đọc tự nhiên hơn và có message lỗi rõ ràng hơn khi fail.', 3, 41, 'Đặt tên method test theo pattern `should_<kết quả mong đợi>_when_<điều kiện>`, ví dụ `should_throwInsufficientSeatsException_when_bookingExceedsAvailableSeats()`. Dùng AssertJ cho assertion (`assertThat(...)`), không dùng JUnit assertion cơ bản (`assertEquals`) vì AssertJ đọc tự nhiên hơn và có message lỗi rõ ràng hơn khi fail.', '0fdedf31512b553277c5c80212d9cb0d7f58f913569bc173df8e5eafc10a9867', 'pending', '', 'Đặt tên method test theo pattern `should_<kết quả mong đợi>_when_<điều kiện>`, ví dụ `should_throwInsufficientSeatsException_when_bookingExceedsAvailableSeats()`. Dùng AssertJ cho assertion (`assertThat(...)`), không dùng JUnit assertion cơ bản (`assertEquals`) vì AssertJ đọc tự nhiên hơn và có message lỗi rõ ràng hơn khi fail.'),
    ('Git'::text, '- Nhánh đặt tên `feature/TOUR-<số ticket Jira>-mo-ta-ngan`, ví dụ `feature/TOUR-456-fix-double-booking`.
- Commit message: bắt đầu bằng mã ticket Jira, ví dụ `TOUR-456: fix double booking khi 2 request cung luc dat cho cuoi`. Không bắt buộc Conventional Commits như PhoneShop (team này chọn convention riêng phù hợp với việc mọi thay đổi đều gắn với ticket Jira).
- PR bắt buộc 1 approve + build Maven xanh (test + Spotless) mới được merge, dùng **merge commit** thường (không squash) vì team muốn giữ lại lịch sử commit chi tiết trong quá trình phát triển 1 ticket lớn.
- Mọi PR liên quan tới `booking` hoặc `payment` package bắt buộc có ít nhất 1 approve từ Tech Lead, không được chỉ Senior thường approve — do đây là 2 package nhạy cảm nhất về tiền và uy tín.', 4, 137, '- Nhánh đặt tên `feature/TOUR-<số ticket Jira>-mo-ta-ngan`, ví dụ `feature/TOUR-456-fix-double-booking`.
- Commit message: bắt đầu bằng mã ticket Jira, ví dụ `TOUR-456: fix double booking khi 2 request cung luc dat cho cuoi`. Không bắt buộc Conventional Commits như PhoneShop (team này chọn convention riêng phù hợp với việc mọi thay đổi đều gắn với ticket Jira).
- PR bắt buộc 1 approve + build Maven xanh (test + Spotless) mới được merge, dùng **merge commit** thường (không squash) vì team muốn giữ lại lịch sử commit chi tiết trong quá trình phát triển 1 ticket lớn.
- Mọi PR liên quan tới `booking` hoặc `payment` package bắt buộc có ít nhất 1 approve từ Tech Lead, không được chỉ Senior thường approve — do đây là 2 package nhạy cảm nhất về tiền và uy tín.', '5a2dca1bbda654b4777a675a17768a6349e28142254c404f699f80a99cd6b88b', 'pending', '', '- Nhánh đặt tên `feature/TOUR-<số ticket Jira>-mo-ta-ngan`, ví dụ `feature/TOUR-456-fix-double-booking`.
- Commit message: bắt đầu bằng mã ticket Jira, ví dụ `TOUR-456: fix double booking khi 2 request cung luc dat cho cuoi`. Không bắt buộc Conventional Commits như PhoneShop (team này chọn convention riêng phù hợp với việc mọi thay đổi đều gắn với ticket Jira).
- PR bắt buộc 1 approve + build Maven xanh (test + Spotless) mới được merge, dùng **merge commit** thường (không squash) vì team muốn giữ lại lịch sử commit chi tiết trong quá trình phát triển 1 ticket lớn.
- Mọi PR liên quan tới `booking` hoặc `payment` package bắt buộc có ít nhất 1 approve từ Tech Lead, không được chỉ Senior thường approve — do đây là 2 package nhạy cảm nhất về tiền và uy tín.'),
    ('Review checklist'::text, '- [ ] Có test unit cho Service layer (Mockito), coverage không giảm.
- [ ] Không có N+1 query mới (kiểm tra bằng log SQL trong integration test, xem `codebase-guide.md`).
- [ ] Entity mới có Flyway migration kèm theo, đã test rollback (`./mvnw flyway:undo` trên môi trường local trước khi merge — lưu ý: Flyway Community Edition không hỗ trợ undo chính thức, team dùng migration riêng viết tay cho phần rollback quan trọng).
- [ ] Nếu thay đổi liên quan Partner Portal API, đã thông báo trước cho đội frontend Partner Portal (team riêng, không cùng team backend).
- [ ] Action nhạy cảm mới thêm đã gắn `@Auditable` annotation nếu cần ghi audit log.', 5, 119, '- [ ] Có test unit cho Service layer (Mockito), coverage không giảm.
- [ ] Không có N+1 query mới (kiểm tra bằng log SQL trong integration test, xem `codebase-guide.md`).
- [ ] Entity mới có Flyway migration kèm theo, đã test rollback (`./mvnw flyway:undo` trên môi trường local trước khi merge — lưu ý: Flyway Community Edition không hỗ trợ undo chính thức, team dùng migration riêng viết tay cho phần rollback quan trọng).
- [ ] Nếu thay đổi liên quan Partner Portal API, đã thông báo trước cho đội frontend Partner Portal (team riêng, không cùng team backend).
- [ ] Action nhạy cảm mới thêm đã gắn `@Auditable` annotation nếu cần ghi audit log.', 'fde41ee0fab35783503123033ad8c8a30a7549867b73b0002adf128b41e08f58', 'pending', '', '- [ ] Có test unit cho Service layer (Mockito), coverage không giảm.
- [ ] Không có N+1 query mới (kiểm tra bằng log SQL trong integration test, xem `codebase-guide.md`).
- [ ] Entity mới có Flyway migration kèm theo, đã test rollback (`./mvnw flyway:undo` trên môi trường local trước khi merge — lưu ý: Flyway Community Edition không hỗ trợ undo chính thức, team dùng migration riêng viết tay cho phần rollback quan trọng).
- [ ] Nếu thay đổi liên quan Partner Portal API, đã thông báo trước cho đội frontend Partner Portal (team riêng, không cùng team backend).
- [ ] Action nhạy cảm mới thêm đã gắn `@Auditable` annotation nếu cần ghi audit log.'),
    ('SLA review PR'::text, 'Cam kết review trong 1 ngày làm việc (khác PhoneShop 4 giờ — team TourBook nhỏ hơn và có nhiều PR cần Tech Lead review kỹ do liên quan booking/payment). PR gắn label `urgent` (dùng cho hotfix production) được ưu tiên review trong 1 giờ.', 6, 45, 'Cam kết review trong 1 ngày làm việc (khác PhoneShop 4 giờ — team TourBook nhỏ hơn và có nhiều PR cần Tech Lead review kỹ do liên quan booking/payment). PR gắn label `urgent` (dùng cho hotfix production) được ưu tiên review trong 1 giờ.', '2884732616902d0ce75cef5b207d1b0b775c9b64aa3b09d4863ac9477dc2c1d6', 'pending', '', 'Cam kết review trong 1 ngày làm việc (khác PhoneShop 4 giờ — team TourBook nhỏ hơn và có nhiều PR cần Tech Lead review kỹ do liên quan booking/payment). PR gắn label `urgent` (dùng cho hotfix production) được ưu tiên review trong 1 giờ.')
) AS c(heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical);

-- TOURBOOK: TourBooking Service — First Task gợi ý cho engineer mới
WITH doc AS (
  INSERT INTO knowledge_documents
    (project_id, created_by_user_id, knowledge_domain, document_category, policy_category,
     source_key, category_confirmed, category_classification_status,
     title, source_url, status, created_at, updated_at)
  VALUES (
    (SELECT project_id FROM projects WHERE key = 'TOURBOOK'),
    (SELECT user_id FROM users WHERE email = 'pm.tourbook@onboarding.dev'),
    'PROJECT', 'FIRST_TASK', NULL,
    'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/tourbook/first-task', true, 'CLASSIFIED',
    'TourBooking Service — First Task gợi ý cho engineer mới', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/tourbook/first-task', 'ACTIVE', now(), now()
  )
  RETURNING document_id
),
ver AS (
  INSERT INTO document_versions
    (document_id, version_no, revision_no, embedding_model_version,
     storage_uri, checksum, status, created_at)
  SELECT document_id, 1, 1, 'pending', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/tourbook/first-task', '19cb6a047d3b6904517b868103b5e5024dc47417ab5a802ab178cb8672c27a89', 'ACTIVE', now() FROM doc
  RETURNING version_id
)
INSERT INTO document_chunks (version_id, heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical)
SELECT ver.version_id, c.heading, c.content, c.chunk_index, c.token_count, c.embedding_text, c.content_hash, c.embedding_model_version, c.lexical_identifiers, c.lexical_technical
FROM ver, (VALUES
    (NULL::text, '# TourBooking Service — First Task gợi ý cho engineer mới', 0, 11, '# TourBooking Service — First Task gợi ý cho engineer mới', '5af6733d4d9f04a1aa322c7a983951c4561129a33ec8be1bb93108120db99154', 'pending', '', '# TourBooking Service — First Task gợi ý cho engineer mới'),
    ('Mục đích'::text, 'Trước khi động vào luồng `BookingService` (phần nhạy cảm nhất hệ thống, liên quan trực tiếp tới tiền và uy tín công ty), mọi engineer mới đều bắt đầu bằng 1-2 task nhỏ ở phần `tour` (chỉ đọc, ít rủi ro) để làm quen layering `Controller -> Service -> Repository` chuẩn Spring Boot, quy trình review PR, và pipeline CI/CD thật của team.', 1, 63, 'Trước khi động vào luồng `BookingService` (phần nhạy cảm nhất hệ thống, liên quan trực tiếp tới tiền và uy tín công ty), mọi engineer mới đều bắt đầu bằng 1-2 task nhỏ ở phần `tour` (chỉ đọc, ít rủi ro) để làm quen layering `Controller -> Service -> Repository` chuẩn Spring Boot, quy trình review PR, và pipeline CI/CD thật của team.', '2c901dc3db4e7035d959670f93b7583113f1f62493c544f52aa244c1b0d379b7', 'pending', '', 'Trước khi động vào luồng `BookingService` (phần nhạy cảm nhất hệ thống, liên quan trực tiếp tới tiền và uy tín công ty), mọi engineer mới đều bắt đầu bằng 1-2 task nhỏ ở phần `tour` (chỉ đọc, ít rủi ro) để làm quen layering `Controller -> Service -> Repository` chuẩn Spring Boot, quy trình review PR, và pipeline CI/CD thật của team.'),
    ('Task khởi động #1: Thêm endpoint lọc tour theo khoảng giá'::text, '**Mục tiêu**: làm quen luồng `Controller -> Service -> Repository` chuẩn Spring Boot, không đụng logic giữ chỗ phức tạp.

**Các bước cụ thể**:
1. Đọc `TourController.java`, tìm endpoint `GET /api/tours`.
2. Thêm 2 query param `minPrice`, `maxPrice` (kiểu `BigDecimal`, optional, dùng `@RequestParam(required = false)`).
3. Cập nhật `TourService.searchTours(...)` truyền thêm điều kiện lọc giá xuống `TourRepository` (dùng JPA Specification, không viết `@Query` string thủ công để giữ khả năng compose điều kiện linh hoạt với các filter khác đã có sẵn như điểm đến, ngày khởi hành).
4. Viết test ở `TourControllerTest.java` (dùng `@WebMvcTest`, mock `TourService`) và `TourServiceTest.java` (dùng Mockito mock `TourRepository`) xác nhận lọc đúng khoảng giá, kể cả case chỉ có `minPrice` hoặc chỉ có `maxPrice`.
5. Cập nhật lại luôn cả filter tương ứng bên Elasticsearch (`TourSearchService`) nếu tính năng tìm kiếm chính đang dùng Elasticsearch thay vì query trực tiếp Postgres — hỏi Tech Lead nếu không chắc endpoint này dùng nguồn dữ liệu nào.
6. Tạo PR, gắn label `good-first-issue`, mã ticket Jira tương ứng (Tech Lead sẽ tạo sẵn ticket mẫu cho bạn).

Task này thường mất 0.5–1 ngày, giúp engineer mới quen cách viết query có điều kiện động trong JPA (Specification pattern) và cách team tổ chức test.', 2, 207, '**Mục tiêu**: làm quen luồng `Controller -> Service -> Repository` chuẩn Spring Boot, không đụng logic giữ chỗ phức tạp.

**Các bước cụ thể**:
1. Đọc `TourController.java`, tìm endpoint `GET /api/tours`.
2. Thêm 2 query param `minPrice`, `maxPrice` (kiểu `BigDecimal`, optional, dùng `@RequestParam(required = false)`).
3. Cập nhật `TourService.searchTours(...)` truyền thêm điều kiện lọc giá xuống `TourRepository` (dùng JPA Specification, không viết `@Query` string thủ công để giữ khả năng compose điều kiện linh hoạt với các filter khác đã có sẵn như điểm đến, ngày khởi hành).
4. Viết test ở `TourControllerTest.java` (dùng `@WebMvcTest`, mock `TourService`) và `TourServiceTest.java` (dùng Mockito mock `TourRepository`) xác nhận lọc đúng khoảng giá, kể cả case chỉ có `minPrice` hoặc chỉ có `maxPrice`.
5. Cập nhật lại luôn cả filter tương ứng bên Elasticsearch (`TourSearchService`) nếu tính năng tìm kiếm chính đang dùng Elasticsearch thay vì query trực tiếp Postgres — hỏi Tech Lead nếu không chắc endpoint này dùng nguồn dữ liệu nào.
6. Tạo PR, gắn label `good-first-issue`, mã ticket Jira tương ứng (Tech Lead sẽ tạo sẵn ticket mẫu cho bạn).

Task này thường mất 0.5–1 ngày, giúp engineer mới quen cách viết query có điều kiện động trong JPA (Specification pattern) và cách team tổ chức test.', 'e6dc6de157bead5fba721be05d57a6628d4562676d8fc237706de2253b1049d8', 'pending', '', '**Mục tiêu**: làm quen luồng `Controller -> Service -> Repository` chuẩn Spring Boot, không đụng logic giữ chỗ phức tạp.

**Các bước cụ thể**:
1. Đọc `TourController.java`, tìm endpoint `GET /api/tours`.
2. Thêm 2 query param `minPrice`, `maxPrice` (kiểu `BigDecimal`, optional, dùng `@RequestParam(required = false)`).
3. Cập nhật `TourService.searchTours(...)` truyền thêm điều kiện lọc giá xuống `TourRepository` (dùng JPA Specification, không viết `@Query` string thủ công để giữ khả năng compose điều kiện linh hoạt với các filter khác đã có sẵn như điểm đến, ngày khởi hành).
4. Viết test ở `TourControllerTest.java` (dùng `@WebMvcTest`, mock `TourService`) và `TourServiceTest.java` (dùng Mockito mock `TourRepository`) xác nhận lọc đúng khoảng giá, kể cả case chỉ có `minPrice` hoặc chỉ có `maxPrice`.
5. Cập nhật lại luôn cả filter tương ứng bên Elasticsearch (`TourSearchService`) nếu tính năng tìm kiếm chính đang dùng Elasticsearch thay vì query trực tiếp Postgres — hỏi Tech Lead nếu không chắc endpoint này dùng nguồn dữ liệu nào.
6. Tạo PR, gắn label `good-first-issue`, mã ticket Jira tương ứng (Tech Lead sẽ tạo sẵn ticket mẫu cho bạn).

Task này thường mất 0.5–1 ngày, giúp engineer mới quen cách viết query có điều kiện động trong JPA (Specification pattern) và cách team tổ chức test.'),
    ('Task khởi động #2 (sau khi hoàn thành task #1): Thêm endpoint xem chi tiết lịch khởi hành còn chỗ'::text, '**Mục tiêu**: làm quen việc đọc dữ liệu liên quan tới 2 entity có quan hệ (`Tour` và `TourDeparture`), và cách tránh N+1 query.

**Các bước gợi ý**:
1. Thêm endpoint `GET /api/tours/{tourId}/departures?onlyAvailable=true` trả về danh sách lịch khởi hành, có tuỳ chọn chỉ lấy lịch còn chỗ trống (`available_seats > 0`).
2. Dùng `@EntityGraph` hoặc `JOIN FETCH` để tránh N+1 query khi load kèm thông tin `Tour` cha (xem lưu ý về N+1 trong `codebase-guide.md`).
3. Viết integration test xác nhận số lượng query SQL thực thi đúng như dự kiến (dùng thư viện `db-util` team đã setup sẵn trong `pom.xml`).', 3, 102, '**Mục tiêu**: làm quen việc đọc dữ liệu liên quan tới 2 entity có quan hệ (`Tour` và `TourDeparture`), và cách tránh N+1 query.

**Các bước gợi ý**:
1. Thêm endpoint `GET /api/tours/{tourId}/departures?onlyAvailable=true` trả về danh sách lịch khởi hành, có tuỳ chọn chỉ lấy lịch còn chỗ trống (`available_seats > 0`).
2. Dùng `@EntityGraph` hoặc `JOIN FETCH` để tránh N+1 query khi load kèm thông tin `Tour` cha (xem lưu ý về N+1 trong `codebase-guide.md`).
3. Viết integration test xác nhận số lượng query SQL thực thi đúng như dự kiến (dùng thư viện `db-util` team đã setup sẵn trong `pom.xml`).', '7bed2bd8f505e1682d646d4312f9660c818b17954b9486cc5fe90e1b92b3c350', 'pending', '', '**Mục tiêu**: làm quen việc đọc dữ liệu liên quan tới 2 entity có quan hệ (`Tour` và `TourDeparture`), và cách tránh N+1 query.

**Các bước gợi ý**:
1. Thêm endpoint `GET /api/tours/{tourId}/departures?onlyAvailable=true` trả về danh sách lịch khởi hành, có tuỳ chọn chỉ lấy lịch còn chỗ trống (`available_seats > 0`).
2. Dùng `@EntityGraph` hoặc `JOIN FETCH` để tránh N+1 query khi load kèm thông tin `Tour` cha (xem lưu ý về N+1 trong `codebase-guide.md`).
3. Viết integration test xác nhận số lượng query SQL thực thi đúng như dự kiến (dùng thư viện `db-util` team đã setup sẵn trong `pom.xml`).'),
    ('Sau 2 task khởi động'::text, 'Sau khi hoàn thành, trao đổi với Tech Lead trong buổi 1-1 để nhận task nghiệp vụ thật — thường sẽ ở mảng `tour` hoặc `partner` trước, `booking`/`payment` chỉ giao sau khi bạn đã làm quen codebase ít nhất 2-3 tuần và được Tech Lead xác nhận đủ tự tin xử lý phần nhạy cảm nhất hệ thống.', 4, 58, 'Sau khi hoàn thành, trao đổi với Tech Lead trong buổi 1-1 để nhận task nghiệp vụ thật — thường sẽ ở mảng `tour` hoặc `partner` trước, `booking`/`payment` chỉ giao sau khi bạn đã làm quen codebase ít nhất 2-3 tuần và được Tech Lead xác nhận đủ tự tin xử lý phần nhạy cảm nhất hệ thống.', '2c7df2bab7962dd6db289c7615beae16274454e7b680e9b02c5eda63fb6e62d6', 'pending', '', 'Sau khi hoàn thành, trao đổi với Tech Lead trong buổi 1-1 để nhận task nghiệp vụ thật — thường sẽ ở mảng `tour` hoặc `partner` trước, `booking`/`payment` chỉ giao sau khi bạn đã làm quen codebase ít nhất 2-3 tuần và được Tech Lead xác nhận đủ tự tin xử lý phần nhạy cảm nhất hệ thống.')
) AS c(heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical);

-- FURNISTORE: FurniStore — Overview
WITH doc AS (
  INSERT INTO knowledge_documents
    (project_id, created_by_user_id, knowledge_domain, document_category, policy_category,
     source_key, category_confirmed, category_classification_status,
     title, source_url, status, created_at, updated_at)
  VALUES (
    (SELECT project_id FROM projects WHERE key = 'FURNISTORE'),
    (SELECT user_id FROM users WHERE email = 'pm.furnistore@onboarding.dev'),
    'PROJECT', 'OVERVIEW', NULL,
    'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/furnistore/overview', true, 'CLASSIFIED',
    'FurniStore — Overview', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/furnistore/overview', 'ACTIVE', now(), now()
  )
  RETURNING document_id
),
ver AS (
  INSERT INTO document_versions
    (document_id, version_no, revision_no, embedding_model_version,
     storage_uri, checksum, status, created_at)
  SELECT document_id, 1, 1, 'pending', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/furnistore/overview', '32346f304dd98d080177bf079182155cd64e96b98fe4279967d4955d7292ed53', 'ACTIVE', now() FROM doc
  RETURNING version_id
)
INSERT INTO document_chunks (version_id, heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical)
SELECT ver.version_id, c.heading, c.content, c.chunk_index, c.token_count, c.embedding_text, c.content_hash, c.embedding_model_version, c.lexical_identifiers, c.lexical_technical
FROM ver, (VALUES
    (NULL::text, '# FurniStore — Overview', 0, 4, '# FurniStore — Overview', '351c94ff27bce0ee938065d67d8a4e8c7d818186f12b75c95297cf160938e695', 'pending', '', '# FurniStore — Overview'),
    ('Giới thiệu chung'::text, 'FurniStore là hệ thống backend cho cửa hàng nội thất trực tuyến, bán bàn ghế, giường tủ, sofa, và đồ trang trí nhà cửa. Dự án khởi động tháng 8/2024 nhằm số hoá kênh bán hàng của chuỗi 12 showroom nội thất đã hoạt động offline nhiều năm, chính thức lên production tháng 2/2025. Điểm đặc thù lớn nhất so với các hệ thống thương mại điện tử thông thường (như PhoneShop): sản phẩm có **kích thước lớn, cồng kềnh, cần tính phí vận chuyển theo khu vực và khối lượng thực tế**, đồng thời phần lớn đơn hàng cần **dịch vụ giao hàng + lắp đặt tận nơi** thay vì chỉ giao bưu kiện thông thường.', 1, 117, 'FurniStore là hệ thống backend cho cửa hàng nội thất trực tuyến, bán bàn ghế, giường tủ, sofa, và đồ trang trí nhà cửa. Dự án khởi động tháng 8/2024 nhằm số hoá kênh bán hàng của chuỗi 12 showroom nội thất đã hoạt động offline nhiều năm, chính thức lên production tháng 2/2025. Điểm đặc thù lớn nhất so với các hệ thống thương mại điện tử thông thường (như PhoneShop): sản phẩm có **kích thước lớn, cồng kềnh, cần tính phí vận chuyển theo khu vực và khối lượng thực tế**, đồng thời phần lớn đơn hàng cần **dịch vụ giao hàng + lắp đặt tận nơi** thay vì chỉ giao bưu kiện thông thường.', '65fa49c607181fafcf776e0a639adc05b0176d9b2c04428c6a94988dac27ecbe', 'pending', '', 'FurniStore là hệ thống backend cho cửa hàng nội thất trực tuyến, bán bàn ghế, giường tủ, sofa, và đồ trang trí nhà cửa. Dự án khởi động tháng 8/2024 nhằm số hoá kênh bán hàng của chuỗi 12 showroom nội thất đã hoạt động offline nhiều năm, chính thức lên production tháng 2/2025. Điểm đặc thù lớn nhất so với các hệ thống thương mại điện tử thông thường (như PhoneShop): sản phẩm có **kích thước lớn, cồng kềnh, cần tính phí vận chuyển theo khu vực và khối lượng thực tế**, đồng thời phần lớn đơn hàng cần **dịch vụ giao hàng + lắp đặt tận nơi** thay vì chỉ giao bưu kiện thông thường.'),
    ('Bối cảnh kinh doanh'::text, 'Ngành nội thất có đặc thù: giá trị đơn hàng trung bình cao (trung bình 4.2 triệu đồng/đơn, so với ~2.5 triệu của ngành điện thoại), nhưng tần suất mua thấp hơn nhiều và quyết định mua thường cần thời gian cân nhắc lâu hơn (khách hay xem sản phẩm nhiều lần trước khi quyết định, tỷ lệ chuyển đổi từ xem sang mua chỉ khoảng 1.2%, thấp hơn đáng kể so với ngành bán lẻ điện tử). Chiến lược khác biệt hoá: cho phép xem trước sản phẩm dạng 3D/AR ngay trên web (đã triển khai cho ~15% sản phẩm chủ lực), và cam kết thời gian giao hàng rõ ràng theo từng khu vực thay vì ước lượng chung chung.', 2, 122, 'Ngành nội thất có đặc thù: giá trị đơn hàng trung bình cao (trung bình 4.2 triệu đồng/đơn, so với ~2.5 triệu của ngành điện thoại), nhưng tần suất mua thấp hơn nhiều và quyết định mua thường cần thời gian cân nhắc lâu hơn (khách hay xem sản phẩm nhiều lần trước khi quyết định, tỷ lệ chuyển đổi từ xem sang mua chỉ khoảng 1.2%, thấp hơn đáng kể so với ngành bán lẻ điện tử). Chiến lược khác biệt hoá: cho phép xem trước sản phẩm dạng 3D/AR ngay trên web (đã triển khai cho ~15% sản phẩm chủ lực), và cam kết thời gian giao hàng rõ ràng theo từng khu vực thay vì ước lượng chung chung.', 'f8f07c42f0559307875b936f3d31a0cae191ce8f18ebbeab6974c3807c506f07', 'pending', '', 'Ngành nội thất có đặc thù: giá trị đơn hàng trung bình cao (trung bình 4.2 triệu đồng/đơn, so với ~2.5 triệu của ngành điện thoại), nhưng tần suất mua thấp hơn nhiều và quyết định mua thường cần thời gian cân nhắc lâu hơn (khách hay xem sản phẩm nhiều lần trước khi quyết định, tỷ lệ chuyển đổi từ xem sang mua chỉ khoảng 1.2%, thấp hơn đáng kể so với ngành bán lẻ điện tử). Chiến lược khác biệt hoá: cho phép xem trước sản phẩm dạng 3D/AR ngay trên web (đã triển khai cho ~15% sản phẩm chủ lực), và cam kết thời gian giao hàng rõ ràng theo từng khu vực thay vì ước lượng chung chung.'),
    ('Trạng thái vận hành hiện tại'::text, '| Chỉ số | Giá trị |
|---|---|
| Đơn hàng trung bình/ngày | ~180 đơn ngày thường, ~600 đơn dịp khuyến mãi lớn (giữa năm, cuối năm) |
| Giá trị đơn hàng trung bình | ~4.2 triệu đồng |
| Uptime SLA | 99.5% cam kết (thấp hơn PhoneShop/TourBook vì hệ thống mới, ít traffic hơn nên rủi ro thấp hơn nếu có downtime ngắn), thực tế đạt 99.7% |
| Số khu vực tính phí ship | 63 tỉnh/thành, chia thành 5 vùng giá (nội thành, ngoại thành, tỉnh lân cận, miền Trung/Tây Nguyên, miền Nam xa) |
| Tỷ lệ đơn cần lắp đặt tận nơi | ~65% tổng số đơn (chủ yếu tủ, giường, sofa lớn) |', 3, 122, '| Chỉ số | Giá trị |
|---|---|
| Đơn hàng trung bình/ngày | ~180 đơn ngày thường, ~600 đơn dịp khuyến mãi lớn (giữa năm, cuối năm) |
| Giá trị đơn hàng trung bình | ~4.2 triệu đồng |
| Uptime SLA | 99.5% cam kết (thấp hơn PhoneShop/TourBook vì hệ thống mới, ít traffic hơn nên rủi ro thấp hơn nếu có downtime ngắn), thực tế đạt 99.7% |
| Số khu vực tính phí ship | 63 tỉnh/thành, chia thành 5 vùng giá (nội thành, ngoại thành, tỉnh lân cận, miền Trung/Tây Nguyên, miền Nam xa) |
| Tỷ lệ đơn cần lắp đặt tận nơi | ~65% tổng số đơn (chủ yếu tủ, giường, sofa lớn) |', '4379569bf8bbc160bdee8adec66481d2c420b91af9c714b2a6efecec8e9435b8', 'pending', '', '| Chỉ số | Giá trị |
|---|---|
| Đơn hàng trung bình/ngày | ~180 đơn ngày thường, ~600 đơn dịp khuyến mãi lớn (giữa năm, cuối năm) |
| Giá trị đơn hàng trung bình | ~4.2 triệu đồng |
| Uptime SLA | 99.5% cam kết (thấp hơn PhoneShop/TourBook vì hệ thống mới, ít traffic hơn nên rủi ro thấp hơn nếu có downtime ngắn), thực tế đạt 99.7% |
| Số khu vực tính phí ship | 63 tỉnh/thành, chia thành 5 vùng giá (nội thành, ngoại thành, tỉnh lân cận, miền Trung/Tây Nguyên, miền Nam xa) |
| Tỷ lệ đơn cần lắp đặt tận nơi | ~65% tổng số đơn (chủ yếu tủ, giường, sofa lớn) |'),
    ('Mục tiêu kinh doanh chi tiết'::text, '- Bán nội thất online kèm xem trước 3D cho một số sản phẩm chủ lực, mở rộng dần độ phủ 3D lên 40% catalog trong năm 2025.
- Tính phí ship chính xác theo khối lượng/kích thước thực tế và khoảng cách, tránh tình trạng báo giá thấp lúc đặt hàng rồi phát sinh thêm phí khi giao (nguyên nhân phổ biến gây khiếu nại ở mô hình cũ khi còn bán chủ yếu qua điện thoại/Zalo).
- Cho phép khách đặt lịch giao hàng + lắp đặt theo khung giờ cụ thể (sáng/chiều/tối), giảm tỷ lệ giao hàng thất bại do khách không có nhà.
- Tích hợp dần với 12 showroom offline để đồng bộ tồn kho, cho phép khách đặt online, nhận tại showroom gần nhất (roadmap Q4/2025, hiện chưa triển khai).', 4, 136, '- Bán nội thất online kèm xem trước 3D cho một số sản phẩm chủ lực, mở rộng dần độ phủ 3D lên 40% catalog trong năm 2025.
- Tính phí ship chính xác theo khối lượng/kích thước thực tế và khoảng cách, tránh tình trạng báo giá thấp lúc đặt hàng rồi phát sinh thêm phí khi giao (nguyên nhân phổ biến gây khiếu nại ở mô hình cũ khi còn bán chủ yếu qua điện thoại/Zalo).
- Cho phép khách đặt lịch giao hàng + lắp đặt theo khung giờ cụ thể (sáng/chiều/tối), giảm tỷ lệ giao hàng thất bại do khách không có nhà.
- Tích hợp dần với 12 showroom offline để đồng bộ tồn kho, cho phép khách đặt online, nhận tại showroom gần nhất (roadmap Q4/2025, hiện chưa triển khai).', 'd3492c3e30be9d02bdb7c226bd62cb093dd93a060f5c8ec4ae9700a015c48265', 'pending', '', '- Bán nội thất online kèm xem trước 3D cho một số sản phẩm chủ lực, mở rộng dần độ phủ 3D lên 40% catalog trong năm 2025.
- Tính phí ship chính xác theo khối lượng/kích thước thực tế và khoảng cách, tránh tình trạng báo giá thấp lúc đặt hàng rồi phát sinh thêm phí khi giao (nguyên nhân phổ biến gây khiếu nại ở mô hình cũ khi còn bán chủ yếu qua điện thoại/Zalo).
- Cho phép khách đặt lịch giao hàng + lắp đặt theo khung giờ cụ thể (sáng/chiều/tối), giảm tỷ lệ giao hàng thất bại do khách không có nhà.
- Tích hợp dần với 12 showroom offline để đồng bộ tồn kho, cho phép khách đặt online, nhận tại showroom gần nhất (roadmap Q4/2025, hiện chưa triển khai).'),
    ('Người dùng chính'::text, '- **Khách hàng mua nội thất**: quyết định mua thường kéo dài (trung bình 5-7 ngày từ lần xem đầu tiên tới lúc đặt hàng), hay so sánh nhiều mẫu, quan tâm nhiều tới chính sách đổi trả và bảo hành (nội thất thường bảo hành 12-24 tháng tuỳ loại).
- **Đội giao hàng/lắp đặt**: dùng app riêng (Delivery App, React Native) để xem lịch giao hàng trong ngày, xác nhận hoàn thành kèm ảnh chụp sau khi lắp đặt (yêu cầu bắt buộc để đóng đơn, tránh tranh chấp sau này).
- **Quản lý cửa hàng/showroom**: quản lý catalog, giá, khuyến mãi theo mùa, theo dõi tồn kho từng showroom qua Admin Portal.
- **Đội chăm sóc khách hàng**: xử lý khiếu nại liên quan giao hàng trễ, sản phẩm lỗi/vỡ khi vận chuyển (tỷ lệ ~2.1% đơn hàng, đang là ưu tiên cải thiện qua việc chuẩn hoá quy trình đóng gói với đối tác vận chuyển).', 5, 159, '- **Khách hàng mua nội thất**: quyết định mua thường kéo dài (trung bình 5-7 ngày từ lần xem đầu tiên tới lúc đặt hàng), hay so sánh nhiều mẫu, quan tâm nhiều tới chính sách đổi trả và bảo hành (nội thất thường bảo hành 12-24 tháng tuỳ loại).
- **Đội giao hàng/lắp đặt**: dùng app riêng (Delivery App, React Native) để xem lịch giao hàng trong ngày, xác nhận hoàn thành kèm ảnh chụp sau khi lắp đặt (yêu cầu bắt buộc để đóng đơn, tránh tranh chấp sau này).
- **Quản lý cửa hàng/showroom**: quản lý catalog, giá, khuyến mãi theo mùa, theo dõi tồn kho từng showroom qua Admin Portal.
- **Đội chăm sóc khách hàng**: xử lý khiếu nại liên quan giao hàng trễ, sản phẩm lỗi/vỡ khi vận chuyển (tỷ lệ ~2.1% đơn hàng, đang là ưu tiên cải thiện qua việc chuẩn hoá quy trình đóng gói với đối tác vận chuyển).', 'eaea63e7e217e480987fedb6876ca7a7b7a6f30ca861622a874946ebf22ed2c2', 'pending', '', '- **Khách hàng mua nội thất**: quyết định mua thường kéo dài (trung bình 5-7 ngày từ lần xem đầu tiên tới lúc đặt hàng), hay so sánh nhiều mẫu, quan tâm nhiều tới chính sách đổi trả và bảo hành (nội thất thường bảo hành 12-24 tháng tuỳ loại).
- **Đội giao hàng/lắp đặt**: dùng app riêng (Delivery App, React Native) để xem lịch giao hàng trong ngày, xác nhận hoàn thành kèm ảnh chụp sau khi lắp đặt (yêu cầu bắt buộc để đóng đơn, tránh tranh chấp sau này).
- **Quản lý cửa hàng/showroom**: quản lý catalog, giá, khuyến mãi theo mùa, theo dõi tồn kho từng showroom qua Admin Portal.
- **Đội chăm sóc khách hàng**: xử lý khiếu nại liên quan giao hàng trễ, sản phẩm lỗi/vỡ khi vận chuyển (tỷ lệ ~2.1% đơn hàng, đang là ưu tiên cải thiện qua việc chuẩn hoá quy trình đóng gói với đối tác vận chuyển).'),
    ('Phạm vi hiện tại (đã lên production)'::text, 'Catalog đầy đủ với ảnh + 3D cho sản phẩm chủ lực, giỏ hàng, tính phí ship theo khu vực (bảng giá cố định theo tỉnh/thành kết hợp khối lượng ước tính), đặt lịch giao hàng theo khung giờ (thủ công, nhân viên điều phối xác nhận qua điện thoại chứ chưa tự động hoàn toàn), thanh toán online + COD (COD giới hạn dưới 5 triệu đồng do rủi ro với đơn giá trị cao).', 6, 76, 'Catalog đầy đủ với ảnh + 3D cho sản phẩm chủ lực, giỏ hàng, tính phí ship theo khu vực (bảng giá cố định theo tỉnh/thành kết hợp khối lượng ước tính), đặt lịch giao hàng theo khung giờ (thủ công, nhân viên điều phối xác nhận qua điện thoại chứ chưa tự động hoàn toàn), thanh toán online + COD (COD giới hạn dưới 5 triệu đồng do rủi ro với đơn giá trị cao).', '4e21911887bca6032dec60885f992ff3bec4466a839e3e0826a7cd3ff6954f2e', 'pending', '', 'Catalog đầy đủ với ảnh + 3D cho sản phẩm chủ lực, giỏ hàng, tính phí ship theo khu vực (bảng giá cố định theo tỉnh/thành kết hợp khối lượng ước tính), đặt lịch giao hàng theo khung giờ (thủ công, nhân viên điều phối xác nhận qua điện thoại chứ chưa tự động hoàn toàn), thanh toán online + COD (COD giới hạn dưới 5 triệu đồng do rủi ro với đơn giá trị cao).'),
    ('Roadmap sắp tới'::text, '- **Q3/2025**: Tự động hoá xác nhận lịch giao hàng (hiện vẫn cần nhân viên gọi điện xác nhận, mục tiêu giảm xuống chỉ cần xác nhận qua SMS/app cho phần lớn trường hợp).
- **Q4/2025**: Tích hợp tồn kho với 12 showroom offline, hỗ trợ mô hình "đặt online, nhận tại showroom".
- **Q4/2025**: Tối ưu thuật toán tính phí ship — hiện dùng bảng giá cố định khá thô, muốn chuyển sang tính theo API thực tế của đối tác vận chuyển để chính xác hơn và cạnh tranh hơn về giá cho khách ở khu vực gần kho.
- **2026**: Mở rộng AR (Augmented Reality) cho phép khách "đặt thử" sản phẩm vào không gian phòng thật qua camera điện thoại — đang trong giai đoạn nghiên cứu khả thi.', 7, 133, '- **Q3/2025**: Tự động hoá xác nhận lịch giao hàng (hiện vẫn cần nhân viên gọi điện xác nhận, mục tiêu giảm xuống chỉ cần xác nhận qua SMS/app cho phần lớn trường hợp).
- **Q4/2025**: Tích hợp tồn kho với 12 showroom offline, hỗ trợ mô hình "đặt online, nhận tại showroom".
- **Q4/2025**: Tối ưu thuật toán tính phí ship — hiện dùng bảng giá cố định khá thô, muốn chuyển sang tính theo API thực tế của đối tác vận chuyển để chính xác hơn và cạnh tranh hơn về giá cho khách ở khu vực gần kho.
- **2026**: Mở rộng AR (Augmented Reality) cho phép khách "đặt thử" sản phẩm vào không gian phòng thật qua camera điện thoại — đang trong giai đoạn nghiên cứu khả thi.', '3f28687d43ea450132f8d189889483c535a5371db852a91e3edb9f52803eafd8', 'pending', '', '- **Q3/2025**: Tự động hoá xác nhận lịch giao hàng (hiện vẫn cần nhân viên gọi điện xác nhận, mục tiêu giảm xuống chỉ cần xác nhận qua SMS/app cho phần lớn trường hợp).
- **Q4/2025**: Tích hợp tồn kho với 12 showroom offline, hỗ trợ mô hình "đặt online, nhận tại showroom".
- **Q4/2025**: Tối ưu thuật toán tính phí ship — hiện dùng bảng giá cố định khá thô, muốn chuyển sang tính theo API thực tế của đối tác vận chuyển để chính xác hơn và cạnh tranh hơn về giá cho khách ở khu vực gần kho.
- **2026**: Mở rộng AR (Augmented Reality) cho phép khách "đặt thử" sản phẩm vào không gian phòng thật qua camera điện thoại — đang trong giai đoạn nghiên cứu khả thi.'),
    ('Sự cố đáng chú ý gần đây (để tránh lặp lại)'::text, '- **Tháng 04/2025**: Job tính phí ship bất đồng bộ (BullMQ) bị treo do 1 job gọi API đối tác vận chuyển timeout nhưng không có cơ chế timeout ở tầng code, khiến job chiếm giữ worker vô thời hạn, dần dần làm nghẽn toàn bộ queue tính phí ship cho các đơn khác trong 4 giờ. Đã bổ sung timeout cứng (10 giây) cho mọi HTTP call ra ngoài, kèm circuit breaker.
- **Tháng 06/2025**: MongoDB (lưu lịch giao hàng) gặp sự cố replica set failover không mượt, gây gián đoạn ghi dữ liệu lịch giao hàng khoảng 8 phút, một số đơn đặt lịch trong thời gian đó bị lỗi phải đặt lại. Đã nâng cấp cấu hình MongoDB Atlas lên tier cao hơn có failover nhanh hơn và bổ sung retry logic ở tầng ứng dụng.', 8, 139, '- **Tháng 04/2025**: Job tính phí ship bất đồng bộ (BullMQ) bị treo do 1 job gọi API đối tác vận chuyển timeout nhưng không có cơ chế timeout ở tầng code, khiến job chiếm giữ worker vô thời hạn, dần dần làm nghẽn toàn bộ queue tính phí ship cho các đơn khác trong 4 giờ. Đã bổ sung timeout cứng (10 giây) cho mọi HTTP call ra ngoài, kèm circuit breaker.
- **Tháng 06/2025**: MongoDB (lưu lịch giao hàng) gặp sự cố replica set failover không mượt, gây gián đoạn ghi dữ liệu lịch giao hàng khoảng 8 phút, một số đơn đặt lịch trong thời gian đó bị lỗi phải đặt lại. Đã nâng cấp cấu hình MongoDB Atlas lên tier cao hơn có failover nhanh hơn và bổ sung retry logic ở tầng ứng dụng.', '4a0518f1365af408fd2fb53adc7c7ddb88adb19eb5c637cad3f9ac706da9d143', 'pending', '', '- **Tháng 04/2025**: Job tính phí ship bất đồng bộ (BullMQ) bị treo do 1 job gọi API đối tác vận chuyển timeout nhưng không có cơ chế timeout ở tầng code, khiến job chiếm giữ worker vô thời hạn, dần dần làm nghẽn toàn bộ queue tính phí ship cho các đơn khác trong 4 giờ. Đã bổ sung timeout cứng (10 giây) cho mọi HTTP call ra ngoài, kèm circuit breaker.
- **Tháng 06/2025**: MongoDB (lưu lịch giao hàng) gặp sự cố replica set failover không mượt, gây gián đoạn ghi dữ liệu lịch giao hàng khoảng 8 phút, một số đơn đặt lịch trong thời gian đó bị lỗi phải đặt lại. Đã nâng cấp cấu hình MongoDB Atlas lên tier cao hơn có failover nhanh hơn và bổ sung retry logic ở tầng ứng dụng.'),
    ('Liên hệ đội ngũ'::text, '- **Kênh Slack chính**: #furnistore-backend, #furnistore-ops (vấn đề vận hành giao hàng/showroom), #furnistore-incidents.
- Team nhỏ hơn 2 dự án còn lại (5 kỹ sư backend), Tech Lead kiêm luôn vai trò DevOps chính cho service này.', 9, 37, '- **Kênh Slack chính**: #furnistore-backend, #furnistore-ops (vấn đề vận hành giao hàng/showroom), #furnistore-incidents.
- Team nhỏ hơn 2 dự án còn lại (5 kỹ sư backend), Tech Lead kiêm luôn vai trò DevOps chính cho service này.', '93feb7876bf261dbe4338a66899267794e0ab173d9ca44c7d65063095fae5e5a', 'pending', '', '- **Kênh Slack chính**: #furnistore-backend, #furnistore-ops (vấn đề vận hành giao hàng/showroom), #furnistore-incidents.
- Team nhỏ hơn 2 dự án còn lại (5 kỹ sư backend), Tech Lead kiêm luôn vai trò DevOps chính cho service này.')
) AS c(heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical);

-- FURNISTORE: FurniStore — Architecture
WITH doc AS (
  INSERT INTO knowledge_documents
    (project_id, created_by_user_id, knowledge_domain, document_category, policy_category,
     source_key, category_confirmed, category_classification_status,
     title, source_url, status, created_at, updated_at)
  VALUES (
    (SELECT project_id FROM projects WHERE key = 'FURNISTORE'),
    (SELECT user_id FROM users WHERE email = 'pm.furnistore@onboarding.dev'),
    'PROJECT', 'ARCHITECTURE', NULL,
    'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/furnistore/architecture', true, 'CLASSIFIED',
    'FurniStore — Architecture', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/furnistore/architecture', 'ACTIVE', now(), now()
  )
  RETURNING document_id
),
ver AS (
  INSERT INTO document_versions
    (document_id, version_no, revision_no, embedding_model_version,
     storage_uri, checksum, status, created_at)
  SELECT document_id, 1, 1, 'pending', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/furnistore/architecture', '94f6219bd4baa8d56b478dd55ca0873c543c7fd06357a9e917b7229849243567', 'ACTIVE', now() FROM doc
  RETURNING version_id
)
INSERT INTO document_chunks (version_id, heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical)
SELECT ver.version_id, c.heading, c.content, c.chunk_index, c.token_count, c.embedding_text, c.content_hash, c.embedding_model_version, c.lexical_identifiers, c.lexical_technical
FROM ver, (VALUES
    (NULL::text, '# FurniStore — Architecture', 0, 4, '# FurniStore — Architecture', '02e9e2221945cf2a8ac6a1381396ab522b7776d320691a88595cbeb0d0b88855', 'pending', '', '# FurniStore — Architecture'),
    ('Tổng quan kiến trúc'::text, 'FurniStore dùng kiến trúc **modular monolith** (giống TourBook, khác PhoneShop) nhưng với 1 điểm đặc biệt: dùng **2 database khác loại** (PostgreSQL + MongoDB) trong cùng 1 application — quyết định xuất phát từ đặc thù dữ liệu lịch giao hàng/lắp đặt có cấu trúc thay đổi liên tục theo nhu cầu vận hành thực tế (khác hẳn dữ liệu đơn hàng/catalog cần tính toàn vẹn quan hệ chặt).', 1, 69, 'FurniStore dùng kiến trúc **modular monolith** (giống TourBook, khác PhoneShop) nhưng với 1 điểm đặc biệt: dùng **2 database khác loại** (PostgreSQL + MongoDB) trong cùng 1 application — quyết định xuất phát từ đặc thù dữ liệu lịch giao hàng/lắp đặt có cấu trúc thay đổi liên tục theo nhu cầu vận hành thực tế (khác hẳn dữ liệu đơn hàng/catalog cần tính toàn vẹn quan hệ chặt).', 'aefb55883cf249182eaa1257565c30c7b403c0da1091955d3eac51d7636103bd', 'pending', '', 'FurniStore dùng kiến trúc **modular monolith** (giống TourBook, khác PhoneShop) nhưng với 1 điểm đặc biệt: dùng **2 database khác loại** (PostgreSQL + MongoDB) trong cùng 1 application — quyết định xuất phát từ đặc thù dữ liệu lịch giao hàng/lắp đặt có cấu trúc thay đổi liên tục theo nhu cầu vận hành thực tế (khác hẳn dữ liệu đơn hàng/catalog cần tính toàn vẹn quan hệ chặt).'),
    ('Tech stack đầy đủ'::text, '| Thành phần | Công nghệ | Ghi chú |
|---|---|---|
| Backend framework | Node.js 20 (LTS), Express 4 | Team đang đánh giá migrate dần sang Fastify cho các endpoint mới do hiệu năng tốt hơn, chưa quyết định migrate toàn bộ |
| ORM/ODM | Prisma (Postgres), Mongoose (MongoDB) | Prisma dùng cho catalog/order/cart, Mongoose cho delivery scheduling |
| Database quan hệ | PostgreSQL 15 (Render managed database) | Đơn hàng, catalog, tồn kho theo showroom |
| Database phi quan hệ | MongoDB Atlas (M10 tier) | Lịch giao hàng/lắp đặt, log thao tác của đội giao hàng qua Delivery App |
| Cache/Queue | Redis (Render managed) + BullMQ | Cache session, giỏ hàng tạm; BullMQ xử lý tính phí ship bất đồng bộ |
| Deploy | Docker, Render | Chọn Render thay vì AWS để giảm chi phí vận hành ở giai đoạn team nhỏ, chưa cần độ phức tạp của AWS |
| Observability | Better Stack (log + uptime monitoring), Sentry (error tracking) | Bộ công cụ nhẹ hơn 2 dự án kia, phù hợp quy mô team 5 người |', 2, 191, '| Thành phần | Công nghệ | Ghi chú |
|---|---|---|
| Backend framework | Node.js 20 (LTS), Express 4 | Team đang đánh giá migrate dần sang Fastify cho các endpoint mới do hiệu năng tốt hơn, chưa quyết định migrate toàn bộ |
| ORM/ODM | Prisma (Postgres), Mongoose (MongoDB) | Prisma dùng cho catalog/order/cart, Mongoose cho delivery scheduling |
| Database quan hệ | PostgreSQL 15 (Render managed database) | Đơn hàng, catalog, tồn kho theo showroom |
| Database phi quan hệ | MongoDB Atlas (M10 tier) | Lịch giao hàng/lắp đặt, log thao tác của đội giao hàng qua Delivery App |
| Cache/Queue | Redis (Render managed) + BullMQ | Cache session, giỏ hàng tạm; BullMQ xử lý tính phí ship bất đồng bộ |
| Deploy | Docker, Render | Chọn Render thay vì AWS để giảm chi phí vận hành ở giai đoạn team nhỏ, chưa cần độ phức tạp của AWS |
| Observability | Better Stack (log + uptime monitoring), Sentry (error tracking) | Bộ công cụ nhẹ hơn 2 dự án kia, phù hợp quy mô team 5 người |', '1521060ff81c03e746134d4c1dfc615c0b5e1b838282d6f9d77b9dfffa2da9a0', 'pending', '', '| Thành phần | Công nghệ | Ghi chú |
|---|---|---|
| Backend framework | Node.js 20 (LTS), Express 4 | Team đang đánh giá migrate dần sang Fastify cho các endpoint mới do hiệu năng tốt hơn, chưa quyết định migrate toàn bộ |
| ORM/ODM | Prisma (Postgres), Mongoose (MongoDB) | Prisma dùng cho catalog/order/cart, Mongoose cho delivery scheduling |
| Database quan hệ | PostgreSQL 15 (Render managed database) | Đơn hàng, catalog, tồn kho theo showroom |
| Database phi quan hệ | MongoDB Atlas (M10 tier) | Lịch giao hàng/lắp đặt, log thao tác của đội giao hàng qua Delivery App |
| Cache/Queue | Redis (Render managed) + BullMQ | Cache session, giỏ hàng tạm; BullMQ xử lý tính phí ship bất đồng bộ |
| Deploy | Docker, Render | Chọn Render thay vì AWS để giảm chi phí vận hành ở giai đoạn team nhỏ, chưa cần độ phức tạp của AWS |
| Observability | Better Stack (log + uptime monitoring), Sentry (error tracking) | Bộ công cụ nhẹ hơn 2 dự án kia, phù hợp quy mô team 5 người |'),
    ('Module chính (theo thư mục)'::text, '```
src/
  modules/
    catalog/           # product, category — Prisma models
    cart/
    order/
    shipping/            # tính phí ship, đặt lịch giao hàng ban đầu (trigger job BullMQ)
    delivery/              # theo dõi trạng thái giao hàng chi tiết, MongoDB models, API cho Delivery App
    showroom/                # quản lý 12 showroom, tồn kho theo showroom (chuẩn bị cho tích hợp Q4/2025)
  shared/
    middlewares/
      error-handler.js
      auth.js
    config/
      prisma-client.js
      mongo-connection.js
    jobs/
      shipping-fee-worker.js   # BullMQ worker
```', 3, 71, '```
src/
  modules/
    catalog/           # product, category — Prisma models
    cart/
    order/
    shipping/            # tính phí ship, đặt lịch giao hàng ban đầu (trigger job BullMQ)
    delivery/              # theo dõi trạng thái giao hàng chi tiết, MongoDB models, API cho Delivery App
    showroom/                # quản lý 12 showroom, tồn kho theo showroom (chuẩn bị cho tích hợp Q4/2025)
  shared/
    middlewares/
      error-handler.js
      auth.js
    config/
      prisma-client.js
      mongo-connection.js
    jobs/
      shipping-fee-worker.js   # BullMQ worker
```', '0fe7ee7de0c6f9bfda9d46c317d024aa6275ad4d95858adfa59cb92225ee2528', 'pending', '', '```
src/
  modules/
    catalog/           # product, category — Prisma models
    cart/
    order/
    shipping/            # tính phí ship, đặt lịch giao hàng ban đầu (trigger job BullMQ)
    delivery/              # theo dõi trạng thái giao hàng chi tiết, MongoDB models, API cho Delivery App
    showroom/                # quản lý 12 showroom, tồn kho theo showroom (chuẩn bị cho tích hợp Q4/2025)
  shared/
    middlewares/
      error-handler.js
      auth.js
    config/
      prisma-client.js
      mongo-connection.js
    jobs/
      shipping-fee-worker.js   # BullMQ worker
```'),
    ('Luồng tính phí giao hàng — chi tiết kỹ thuật'::text, '1. Khách checkout → `shipping` module tính phí **sơ bộ ngay lập tức** (đồng bộ) dựa trên bảng giá tỉnh/thành + tổng khối lượng ước tính từ catalog — đủ nhanh để hiển thị cho khách trước khi đặt hàng.
2. Sau khi đặt hàng, nếu đơn có từ 2 sản phẩm lớn trở lên (tủ, giường, sofa) → hệ thống đẩy job vào BullMQ để **tính lại phí chính xác hơn** (gọi API đối tác vận chuyển thật, tính khối lượng thể tích chính xác thay vì ước tính).
3. Job chạy trong vài phút, nếu giá cuối khác giá sơ bộ quá 10% → gửi email báo khách xác nhận lại trước khi xử lý tiếp (khách có thể huỷ đơn miễn phí nếu không đồng ý giá mới).
4. **Bài học từ sự cố tháng 04/2025**: mọi HTTP call ra đối tác bên ngoài trong job đều có timeout cứng 10 giây + retry tối đa 3 lần với exponential backoff + circuit breaker (dùng thư viện `opossum`) để tự động ngắt gọi tạm thời nếu đối tác đang lỗi liên tục, tránh làm nghẽn toàn bộ queue.

```
Checkout -> tính phí sơ bộ (sync, bảng giá tĩnh) -> hiển thị khách -> Đặt hàng
                                                                          |
                                          (nếu đơn có sản phẩm lớn)      v
                                                                  BullMQ Queue
                                                                          |
                                                          shipping-fee-worker.js
                                                          (gọi API đối tác, timeout 10s,
                                                           circuit breaker, retry 3 lần)
                                                                          |
                                              +---------------------------+---------------------------+
                                              v                                                       v
                                  (giá không đổi nhiều)                                  (giá đổi > 10%)
                                  cập nhật đơn, không cần báo khách                       gửi email xác nhận lại
```', 4, 257, '1. Khách checkout → `shipping` module tính phí **sơ bộ ngay lập tức** (đồng bộ) dựa trên bảng giá tỉnh/thành + tổng khối lượng ước tính từ catalog — đủ nhanh để hiển thị cho khách trước khi đặt hàng.
2. Sau khi đặt hàng, nếu đơn có từ 2 sản phẩm lớn trở lên (tủ, giường, sofa) → hệ thống đẩy job vào BullMQ để **tính lại phí chính xác hơn** (gọi API đối tác vận chuyển thật, tính khối lượng thể tích chính xác thay vì ước tính).
3. Job chạy trong vài phút, nếu giá cuối khác giá sơ bộ quá 10% → gửi email báo khách xác nhận lại trước khi xử lý tiếp (khách có thể huỷ đơn miễn phí nếu không đồng ý giá mới).
4. **Bài học từ sự cố tháng 04/2025**: mọi HTTP call ra đối tác bên ngoài trong job đều có timeout cứng 10 giây + retry tối đa 3 lần với exponential backoff + circuit breaker (dùng thư viện `opossum`) để tự động ngắt gọi tạm thời nếu đối tác đang lỗi liên tục, tránh làm nghẽn toàn bộ queue.

```
Checkout -> tính phí sơ bộ (sync, bảng giá tĩnh) -> hiển thị khách -> Đặt hàng
                                                                          |
                                          (nếu đơn có sản phẩm lớn)      v
                                                                  BullMQ Queue
                                                                          |
                                                          shipping-fee-worker.js
                                                          (gọi API đối tác, timeout 10s,
                                                           circuit breaker, retry 3 lần)
                                                                          |
                                              +---------------------------+---------------------------+
                                              v                                                       v
                                  (giá không đổi nhiều)                                  (giá đổi > 10%)
                                  cập nhật đơn, không cần báo khách                       gửi email xác nhận lại
```', 'b49f40f5994b711dcf54bc59b6a056c34ca12fa9249b12b4221abce3861aa4ca', 'pending', '', '1. Khách checkout → `shipping` module tính phí **sơ bộ ngay lập tức** (đồng bộ) dựa trên bảng giá tỉnh/thành + tổng khối lượng ước tính từ catalog — đủ nhanh để hiển thị cho khách trước khi đặt hàng.
2. Sau khi đặt hàng, nếu đơn có từ 2 sản phẩm lớn trở lên (tủ, giường, sofa) → hệ thống đẩy job vào BullMQ để **tính lại phí chính xác hơn** (gọi API đối tác vận chuyển thật, tính khối lượng thể tích chính xác thay vì ước tính).
3. Job chạy trong vài phút, nếu giá cuối khác giá sơ bộ quá 10% → gửi email báo khách xác nhận lại trước khi xử lý tiếp (khách có thể huỷ đơn miễn phí nếu không đồng ý giá mới).
4. **Bài học từ sự cố tháng 04/2025**: mọi HTTP call ra đối tác bên ngoài trong job đều có timeout cứng 10 giây + retry tối đa 3 lần với exponential backoff + circuit breaker (dùng thư viện `opossum`) để tự động ngắt gọi tạm thời nếu đối tác đang lỗi liên tục, tránh làm nghẽn toàn bộ queue.

```
Checkout -> tính phí sơ bộ (sync, bảng giá tĩnh) -> hiển thị khách -> Đặt hàng
                                                                          |
                                          (nếu đơn có sản phẩm lớn)      v
                                                                  BullMQ Queue
                                                                          |
                                                          shipping-fee-worker.js
                                                          (gọi API đối tác, timeout 10s,
                                                           circuit breaker, retry 3 lần)
                                                                          |
                                              +---------------------------+---------------------------+
                                              v                                                       v
                                  (giá không đổi nhiều)                                  (giá đổi > 10%)
                                  cập nhật đơn, không cần báo khách                       gửi email xác nhận lại
```'),
    ('Vì sao 2 database (Postgres + MongoDB)'::text, 'Lịch giao hàng/lắp đặt có đặc thù: cấu trúc dữ liệu thay đổi thường xuyên theo yêu cầu vận hành thực tế (ví dụ: thêm field "yêu cầu đặc biệt của khách", "ảnh xác nhận lắp đặt", "đánh giá của đội giao hàng về khó khăn khi lắp đặt"...) — mỗi thay đổi này nếu dùng Postgres sẽ cần migration, gây chậm trễ khi đội vận hành cần thêm field mới gấp. MongoDB (schema-less) phù hợp hơn nhiều cho phần này. Ngược lại, đơn hàng/catalog cần tính toàn vẹn quan hệ chặt (không được có `order_item` trỏ tới `product` không tồn tại) — Postgres phù hợp hơn.

Đánh đổi: phải chấp nhận không có transaction xuyên suốt giữa 2 database (nếu tạo `Order` ở Postgres thành công nhưng tạo `DeliverySchedule` tương ứng ở MongoDB thất bại, cần cơ chế bù trừ riêng — hiện xử lý bằng cách: `delivery` module có job quét định kỳ mỗi 5 phút tìm đơn hàng đã `CONFIRMED` ở Postgres nhưng chưa có lịch giao hàng tương ứng ở MongoDB, tự động tạo bù).', 5, 179, 'Lịch giao hàng/lắp đặt có đặc thù: cấu trúc dữ liệu thay đổi thường xuyên theo yêu cầu vận hành thực tế (ví dụ: thêm field "yêu cầu đặc biệt của khách", "ảnh xác nhận lắp đặt", "đánh giá của đội giao hàng về khó khăn khi lắp đặt"...) — mỗi thay đổi này nếu dùng Postgres sẽ cần migration, gây chậm trễ khi đội vận hành cần thêm field mới gấp. MongoDB (schema-less) phù hợp hơn nhiều cho phần này. Ngược lại, đơn hàng/catalog cần tính toàn vẹn quan hệ chặt (không được có `order_item` trỏ tới `product` không tồn tại) — Postgres phù hợp hơn.

Đánh đổi: phải chấp nhận không có transaction xuyên suốt giữa 2 database (nếu tạo `Order` ở Postgres thành công nhưng tạo `DeliverySchedule` tương ứng ở MongoDB thất bại, cần cơ chế bù trừ riêng — hiện xử lý bằng cách: `delivery` module có job quét định kỳ mỗi 5 phút tìm đơn hàng đã `CONFIRMED` ở Postgres nhưng chưa có lịch giao hàng tương ứng ở MongoDB, tự động tạo bù).', '998060158ffafeb0280ad40142f636f9265a3f36b50da06f0d4102128d7c23da', 'pending', '', 'Lịch giao hàng/lắp đặt có đặc thù: cấu trúc dữ liệu thay đổi thường xuyên theo yêu cầu vận hành thực tế (ví dụ: thêm field "yêu cầu đặc biệt của khách", "ảnh xác nhận lắp đặt", "đánh giá của đội giao hàng về khó khăn khi lắp đặt"...) — mỗi thay đổi này nếu dùng Postgres sẽ cần migration, gây chậm trễ khi đội vận hành cần thêm field mới gấp. MongoDB (schema-less) phù hợp hơn nhiều cho phần này. Ngược lại, đơn hàng/catalog cần tính toàn vẹn quan hệ chặt (không được có `order_item` trỏ tới `product` không tồn tại) — Postgres phù hợp hơn.

Đánh đổi: phải chấp nhận không có transaction xuyên suốt giữa 2 database (nếu tạo `Order` ở Postgres thành công nhưng tạo `DeliverySchedule` tương ứng ở MongoDB thất bại, cần cơ chế bù trừ riêng — hiện xử lý bằng cách: `delivery` module có job quét định kỳ mỗi 5 phút tìm đơn hàng đã `CONFIRMED` ở Postgres nhưng chưa có lịch giao hàng tương ứng ở MongoDB, tự động tạo bù).'),
    ('Quyết định thiết kế quan trọng'::text, '- **Render thay vì AWS**: team 5 người, không có DevOps chuyên trách — Render giảm đáng kể gánh nặng vận hành hạ tầng (managed database, auto-deploy từ Git, ít config hơn AWS) dù chi phí/instance cao hơn AWS một chút ở cùng cấu hình.
- **BullMQ (Redis-backed) thay vì RabbitMQ/Kafka**: khối lượng job không lớn (vài trăm job/ngày), BullMQ đơn giản hơn nhiều để vận hành và đã có sẵn Redis dùng cho cache, không cần thêm hạ tầng message queue riêng.
- **Prisma cho Postgres**: type-safe query, migration tự động sinh từ schema, phù hợp team quen TypeScript hơn viết raw SQL hoặc dùng ORM nặng hơn như TypeORM.', 6, 111, '- **Render thay vì AWS**: team 5 người, không có DevOps chuyên trách — Render giảm đáng kể gánh nặng vận hành hạ tầng (managed database, auto-deploy từ Git, ít config hơn AWS) dù chi phí/instance cao hơn AWS một chút ở cùng cấu hình.
- **BullMQ (Redis-backed) thay vì RabbitMQ/Kafka**: khối lượng job không lớn (vài trăm job/ngày), BullMQ đơn giản hơn nhiều để vận hành và đã có sẵn Redis dùng cho cache, không cần thêm hạ tầng message queue riêng.
- **Prisma cho Postgres**: type-safe query, migration tự động sinh từ schema, phù hợp team quen TypeScript hơn viết raw SQL hoặc dùng ORM nặng hơn như TypeORM.', '49a17e7725ddc234b9989bc9213123c2781beea4efd3fb07826bc0ac6940f5a4', 'pending', '', '- **Render thay vì AWS**: team 5 người, không có DevOps chuyên trách — Render giảm đáng kể gánh nặng vận hành hạ tầng (managed database, auto-deploy từ Git, ít config hơn AWS) dù chi phí/instance cao hơn AWS một chút ở cùng cấu hình.
- **BullMQ (Redis-backed) thay vì RabbitMQ/Kafka**: khối lượng job không lớn (vài trăm job/ngày), BullMQ đơn giản hơn nhiều để vận hành và đã có sẵn Redis dùng cho cache, không cần thêm hạ tầng message queue riêng.
- **Prisma cho Postgres**: type-safe query, migration tự động sinh từ schema, phù hợp team quen TypeScript hơn viết raw SQL hoặc dùng ORM nặng hơn như TypeORM.'),
    ('Dashboard & alerting'::text, '- Better Stack dashboard: theo dõi uptime từng endpoint quan trọng (`/health`, `/api/checkout`), response time.
- Sentry: alert ngay khi có exception mới chưa từng thấy (không phải lỗi đã biết và đang track riêng), đặc biệt theo dõi sát `shipping-fee-worker.js` sau sự cố tháng 04/2025.
- Alert MongoDB: theo dõi qua Atlas built-in alerting, cảnh báo khi replica set có vấn đề (bài học từ sự cố tháng 06/2025).', 7, 70, '- Better Stack dashboard: theo dõi uptime từng endpoint quan trọng (`/health`, `/api/checkout`), response time.
- Sentry: alert ngay khi có exception mới chưa từng thấy (không phải lỗi đã biết và đang track riêng), đặc biệt theo dõi sát `shipping-fee-worker.js` sau sự cố tháng 04/2025.
- Alert MongoDB: theo dõi qua Atlas built-in alerting, cảnh báo khi replica set có vấn đề (bài học từ sự cố tháng 06/2025).', '6fcde90a311699483dcd8c964701e7770634899886a8f99115b04ae347d0699e', 'pending', '', '- Better Stack dashboard: theo dõi uptime từng endpoint quan trọng (`/health`, `/api/checkout`), response time.
- Sentry: alert ngay khi có exception mới chưa từng thấy (không phải lỗi đã biết và đang track riêng), đặc biệt theo dõi sát `shipping-fee-worker.js` sau sự cố tháng 04/2025.
- Alert MongoDB: theo dõi qua Atlas built-in alerting, cảnh báo khi replica set có vấn đề (bài học từ sự cố tháng 06/2025).')
) AS c(heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical);

-- FURNISTORE: FurniStore — Setup môi trường dev
WITH doc AS (
  INSERT INTO knowledge_documents
    (project_id, created_by_user_id, knowledge_domain, document_category, policy_category,
     source_key, category_confirmed, category_classification_status,
     title, source_url, status, created_at, updated_at)
  VALUES (
    (SELECT project_id FROM projects WHERE key = 'FURNISTORE'),
    (SELECT user_id FROM users WHERE email = 'pm.furnistore@onboarding.dev'),
    'PROJECT', 'SETUP', NULL,
    'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/furnistore/setup', true, 'CLASSIFIED',
    'FurniStore — Setup môi trường dev', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/furnistore/setup', 'ACTIVE', now(), now()
  )
  RETURNING document_id
),
ver AS (
  INSERT INTO document_versions
    (document_id, version_no, revision_no, embedding_model_version,
     storage_uri, checksum, status, created_at)
  SELECT document_id, 1, 1, 'pending', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/furnistore/setup', '51a849cced1df4fa4b3e37768226aac73a94e71691b6b484658f94ab18882f0c', 'ACTIVE', now() FROM doc
  RETURNING version_id
)
INSERT INTO document_chunks (version_id, heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical)
SELECT ver.version_id, c.heading, c.content, c.chunk_index, c.token_count, c.embedding_text, c.content_hash, c.embedding_model_version, c.lexical_identifiers, c.lexical_technical
FROM ver, (VALUES
    (NULL::text, '# FurniStore — Setup môi trường dev', 0, 7, '# FurniStore — Setup môi trường dev', '1d0f837942390a2a785790ee2f6d9dbce3ef7e48e29611446596fa2b045603f2', 'pending', '', '# FurniStore — Setup môi trường dev'),
    ('Tổng quan'::text, 'FurniStore cần **2 database chạy song song** (Postgres + MongoDB) cho local dev, khác với 2 dự án còn lại chỉ cần 1 database quan hệ — đọc kỹ phần cấu hình `.env` để tránh nhầm lẫn connection string giữa 2 loại database.', 1, 43, 'FurniStore cần **2 database chạy song song** (Postgres + MongoDB) cho local dev, khác với 2 dự án còn lại chỉ cần 1 database quan hệ — đọc kỹ phần cấu hình `.env` để tránh nhầm lẫn connection string giữa 2 loại database.', '39d03db744e109d389e9dec96330499a9788c7f4b168d6b40a216b01ff1bdf84', 'pending', '', 'FurniStore cần **2 database chạy song song** (Postgres + MongoDB) cho local dev, khác với 2 dự án còn lại chỉ cần 1 database quan hệ — đọc kỹ phần cấu hình `.env` để tránh nhầm lẫn connection string giữa 2 loại database.'),
    ('Yêu cầu hệ thống'::text, '- **Node.js 20+** (khuyến nghị dùng `nvm` để quản lý version, repo có sẵn file `.nvmrc`).
- **pnpm** (package manager chính thức của dự án, không dùng `npm`/`yarn` — lockfile chỉ commit `pnpm-lock.yaml`).
- **Docker + Docker Compose**.', 2, 38, '- **Node.js 20+** (khuyến nghị dùng `nvm` để quản lý version, repo có sẵn file `.nvmrc`).
- **pnpm** (package manager chính thức của dự án, không dùng `npm`/`yarn` — lockfile chỉ commit `pnpm-lock.yaml`).
- **Docker + Docker Compose**.', '9fd333f15167ce343754be1792362c494ee775476a00c6d5b56174b503c27974', 'pending', '', '- **Node.js 20+** (khuyến nghị dùng `nvm` để quản lý version, repo có sẵn file `.nvmrc`).
- **pnpm** (package manager chính thức của dự án, không dùng `npm`/`yarn` — lockfile chỉ commit `pnpm-lock.yaml`).
- **Docker + Docker Compose**.'),
    ('Các bước setup từ đầu'::text, '```bash
git clone git@github.com:company/furnistore-api.git
cd furnistore-api
nvm use              # đảm bảo đúng Node version theo .nvmrc
pnpm install
cp .env.example .env   # điền DATABASE_URL (Postgres), MONGO_URL, REDIS_URL

docker compose up -d postgres mongo redis
pnpm prisma migrate dev    # apply migration Postgres + tự sinh Prisma Client
pnpm run seed                # tạo ~30 sản phẩm nội thất mẫu, 12 showroom demo

pnpm run dev                  # chạy dev server có hot reload (nodemon), mặc định port 3000
```', 3, 77, '```bash
git clone git@github.com:company/furnistore-api.git
cd furnistore-api
nvm use              # đảm bảo đúng Node version theo .nvmrc
pnpm install
cp .env.example .env   # điền DATABASE_URL (Postgres), MONGO_URL, REDIS_URL

docker compose up -d postgres mongo redis
pnpm prisma migrate dev    # apply migration Postgres + tự sinh Prisma Client
pnpm run seed                # tạo ~30 sản phẩm nội thất mẫu, 12 showroom demo

pnpm run dev                  # chạy dev server có hot reload (nodemon), mặc định port 3000
```', '1310611326e46d781be4cfb7b692f05ce175331c8c60c4107c5b05738e128a02', 'pending', '', '```bash
git clone git@github.com:company/furnistore-api.git
cd furnistore-api
nvm use              # đảm bảo đúng Node version theo .nvmrc
pnpm install
cp .env.example .env   # điền DATABASE_URL (Postgres), MONGO_URL, REDIS_URL

docker compose up -d postgres mongo redis
pnpm prisma migrate dev    # apply migration Postgres + tự sinh Prisma Client
pnpm run seed                # tạo ~30 sản phẩm nội thất mẫu, 12 showroom demo

pnpm run dev                  # chạy dev server có hot reload (nodemon), mặc định port 3000
```'),
    ('Kiểm tra chạy đúng'::text, '1. Mở `http://localhost:3000/api-docs` (Swagger tự sinh từ JSDoc comment trong route) — thấy nhóm endpoint `catalog`, `cart`, `orders`, `shipping`, `delivery`.
2. Gọi `GET /health` phải trả `{"status":"ok","postgres":"connected","mongo":"connected","redis":"connected"}` — health check kiểm tra cả 3 kết nối, không chỉ trả OK chung chung.
3. Gọi `GET /api/products?limit=5` phải trả về danh sách sản phẩm đã seed.
4. Thử luồng đặt lịch giao hàng: tạo đơn hàng → gọi `POST /api/delivery/schedule` → xác nhận document xuất hiện trong MongoDB (`mongosh`, `db.deliverySchedules.find()`).', 4, 79, '1. Mở `http://localhost:3000/api-docs` (Swagger tự sinh từ JSDoc comment trong route) — thấy nhóm endpoint `catalog`, `cart`, `orders`, `shipping`, `delivery`.
2. Gọi `GET /health` phải trả `{"status":"ok","postgres":"connected","mongo":"connected","redis":"connected"}` — health check kiểm tra cả 3 kết nối, không chỉ trả OK chung chung.
3. Gọi `GET /api/products?limit=5` phải trả về danh sách sản phẩm đã seed.
4. Thử luồng đặt lịch giao hàng: tạo đơn hàng → gọi `POST /api/delivery/schedule` → xác nhận document xuất hiện trong MongoDB (`mongosh`, `db.deliverySchedules.find()`).', '3bdbf95122fee4afeddcc9e26763d35b63f53fef60bd5c0edfd2a08168d97711', 'pending', '', '1. Mở `http://localhost:3000/api-docs` (Swagger tự sinh từ JSDoc comment trong route) — thấy nhóm endpoint `catalog`, `cart`, `orders`, `shipping`, `delivery`.
2. Gọi `GET /health` phải trả `{"status":"ok","postgres":"connected","mongo":"connected","redis":"connected"}` — health check kiểm tra cả 3 kết nối, không chỉ trả OK chung chung.
3. Gọi `GET /api/products?limit=5` phải trả về danh sách sản phẩm đã seed.
4. Thử luồng đặt lịch giao hàng: tạo đơn hàng → gọi `POST /api/delivery/schedule` → xác nhận document xuất hiện trong MongoDB (`mongosh`, `db.deliverySchedules.find()`).'),
    ('Chạy test'::text, '```bash
pnpm test                        # unit test (Jest), mock Prisma Client + Mongoose
pnpm test:integration              # cần docker compose db đang chạy, test qua Supertest
pnpm run test:coverage              # coverage report, mở tại coverage/lcov-report/index.html
```', 5, 34, '```bash
pnpm test                        # unit test (Jest), mock Prisma Client + Mongoose
pnpm test:integration              # cần docker compose db đang chạy, test qua Supertest
pnpm run test:coverage              # coverage report, mở tại coverage/lcov-report/index.html
```', '5b387e95dfc1ba153df4514f2a73aa4753de33ef733e78ae49e6bb2e538da54b', 'pending', '', '```bash
pnpm test                        # unit test (Jest), mock Prisma Client + Mongoose
pnpm test:integration              # cần docker compose db đang chạy, test qua Supertest
pnpm run test:coverage              # coverage report, mở tại coverage/lcov-report/index.html
```'),
    ('Lỗi thường gặp'::text, '| Lỗi | Nguyên nhân | Cách fix |
|---|---|---|
| `pnpm prisma migrate dev` báo lỗi kết nối | Container `postgres` chưa healthy | `docker compose ps`, Prisma cần Postgres sẵn sàng trước khi migrate, đợi vài giây rồi retry |
| `MongoServerError: connection timed out` | Container `mongo` chưa khởi động xong (chậm hơn Postgres) | Đợi thêm 10-15 giây, hoặc kiểm tra `docker compose logs mongo` |
| Job BullMQ không chạy dù đã đẩy vào queue | Chưa chạy worker process riêng (`pnpm run worker`), server chính (`pnpm run dev`) không tự chạy worker | Chạy song song 2 terminal: 1 cho `pnpm run dev`, 1 cho `pnpm run worker` |
| `EADDRINUSE: port 3000 already in use` | Có process cũ chưa tắt hẳn | `lsof -ti:3000 \| xargs kill -9` (macOS/Linux) hoặc tắt qua Task Manager (Windows) |
| Prisma Client báo type không khớp sau khi đổi schema | Chưa regenerate Prisma Client | `pnpm prisma generate` sau mỗi lần đổi `schema.prisma` |', 6, 170, '| Lỗi | Nguyên nhân | Cách fix |
|---|---|---|
| `pnpm prisma migrate dev` báo lỗi kết nối | Container `postgres` chưa healthy | `docker compose ps`, Prisma cần Postgres sẵn sàng trước khi migrate, đợi vài giây rồi retry |
| `MongoServerError: connection timed out` | Container `mongo` chưa khởi động xong (chậm hơn Postgres) | Đợi thêm 10-15 giây, hoặc kiểm tra `docker compose logs mongo` |
| Job BullMQ không chạy dù đã đẩy vào queue | Chưa chạy worker process riêng (`pnpm run worker`), server chính (`pnpm run dev`) không tự chạy worker | Chạy song song 2 terminal: 1 cho `pnpm run dev`, 1 cho `pnpm run worker` |
| `EADDRINUSE: port 3000 already in use` | Có process cũ chưa tắt hẳn | `lsof -ti:3000 \| xargs kill -9` (macOS/Linux) hoặc tắt qua Task Manager (Windows) |
| Prisma Client báo type không khớp sau khi đổi schema | Chưa regenerate Prisma Client | `pnpm prisma generate` sau mỗi lần đổi `schema.prisma` |', '31985c051b09f959ab3c258f7eeb9b3467f2b140a9b6fae88568824a68b6b5bb', 'pending', '', '| Lỗi | Nguyên nhân | Cách fix |
|---|---|---|
| `pnpm prisma migrate dev` báo lỗi kết nối | Container `postgres` chưa healthy | `docker compose ps`, Prisma cần Postgres sẵn sàng trước khi migrate, đợi vài giây rồi retry |
| `MongoServerError: connection timed out` | Container `mongo` chưa khởi động xong (chậm hơn Postgres) | Đợi thêm 10-15 giây, hoặc kiểm tra `docker compose logs mongo` |
| Job BullMQ không chạy dù đã đẩy vào queue | Chưa chạy worker process riêng (`pnpm run worker`), server chính (`pnpm run dev`) không tự chạy worker | Chạy song song 2 terminal: 1 cho `pnpm run dev`, 1 cho `pnpm run worker` |
| `EADDRINUSE: port 3000 already in use` | Có process cũ chưa tắt hẳn | `lsof -ti:3000 \| xargs kill -9` (macOS/Linux) hoặc tắt qua Task Manager (Windows) |
| Prisma Client báo type không khớp sau khi đổi schema | Chưa regenerate Prisma Client | `pnpm prisma generate` sau mỗi lần đổi `schema.prisma` |'),
    ('Cấu trúc `.env` cần lưu ý'::text, '```
DATABASE_URL=postgresql://user:pass@localhost:5432/furnistore    # Prisma dùng
MONGO_URL=mongodb://localhost:27017/furnistore_delivery            # Mongoose dùng, KHÁC connection string với Postgres
REDIS_URL=redis://localhost:6379
SHIPPING_PARTNER_API_KEY=<lấy từ 1Password vault "FurniStore Dev">
```', 7, 22, '```
DATABASE_URL=postgresql://user:pass@localhost:5432/furnistore    # Prisma dùng
MONGO_URL=mongodb://localhost:27017/furnistore_delivery            # Mongoose dùng, KHÁC connection string với Postgres
REDIS_URL=redis://localhost:6379
SHIPPING_PARTNER_API_KEY=<lấy từ 1Password vault "FurniStore Dev">
```', '88f1debd9be3de4bc0089a9e6a72918aaf6d75a590a17d874d0601462559ebfd', 'pending', '', '```
DATABASE_URL=postgresql://user:pass@localhost:5432/furnistore    # Prisma dùng
MONGO_URL=mongodb://localhost:27017/furnistore_delivery            # Mongoose dùng, KHÁC connection string với Postgres
REDIS_URL=redis://localhost:6379
SHIPPING_PARTNER_API_KEY=<lấy từ 1Password vault "FurniStore Dev">
```'),
    ('CI/CD'::text, 'Push lên nhánh bất kỳ → GitHub Actions chạy ESLint + Jest (unit + integration với service container Postgres/MongoDB/Redis). Merge vào `main` → Render tự động deploy (Render tích hợp trực tiếp với GitHub, không cần bước build/push image thủ công như 2 dự án kia). Không có staging riêng biệt hoàn toàn — Render dùng Preview Environment tự động cho mỗi PR để test trước khi merge, xem được ở comment tự động trên PR.', 8, 76, 'Push lên nhánh bất kỳ → GitHub Actions chạy ESLint + Jest (unit + integration với service container Postgres/MongoDB/Redis). Merge vào `main` → Render tự động deploy (Render tích hợp trực tiếp với GitHub, không cần bước build/push image thủ công như 2 dự án kia). Không có staging riêng biệt hoàn toàn — Render dùng Preview Environment tự động cho mỗi PR để test trước khi merge, xem được ở comment tự động trên PR.', '394d7a70022f79ae64794749aeeabd631c39c442da40e5e52ab8dc8298dc289c', 'pending', '', 'Push lên nhánh bất kỳ → GitHub Actions chạy ESLint + Jest (unit + integration với service container Postgres/MongoDB/Redis). Merge vào `main` → Render tự động deploy (Render tích hợp trực tiếp với GitHub, không cần bước build/push image thủ công như 2 dự án kia). Không có staging riêng biệt hoàn toàn — Render dùng Preview Environment tự động cho mỗi PR để test trước khi merge, xem được ở comment tự động trên PR.')
) AS c(heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical);

-- FURNISTORE: FurniStore — Access & Security
WITH doc AS (
  INSERT INTO knowledge_documents
    (project_id, created_by_user_id, knowledge_domain, document_category, policy_category,
     source_key, category_confirmed, category_classification_status,
     title, source_url, status, created_at, updated_at)
  VALUES (
    (SELECT project_id FROM projects WHERE key = 'FURNISTORE'),
    (SELECT user_id FROM users WHERE email = 'pm.furnistore@onboarding.dev'),
    'PROJECT', 'ACCESS_SECURITY', NULL,
    'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/furnistore/access-security', true, 'CLASSIFIED',
    'FurniStore — Access & Security', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/furnistore/access-security', 'ACTIVE', now(), now()
  )
  RETURNING document_id
),
ver AS (
  INSERT INTO document_versions
    (document_id, version_no, revision_no, embedding_model_version,
     storage_uri, checksum, status, created_at)
  SELECT document_id, 1, 1, 'pending', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/furnistore/access-security', '047659353739eb44fbee72894ba1caf70f8d0c6ee27918aa4b716a354d6ba5fb', 'ACTIVE', now() FROM doc
  RETURNING version_id
)
INSERT INTO document_chunks (version_id, heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical)
SELECT ver.version_id, c.heading, c.content, c.chunk_index, c.token_count, c.embedding_text, c.content_hash, c.embedding_model_version, c.lexical_identifiers, c.lexical_technical
FROM ver, (VALUES
    (NULL::text, '# FurniStore — Access & Security', 0, 6, '# FurniStore — Access & Security', 'a934875c8b4d0d37c972ce28d5bdd6e5140537e3408c62d847c904c2c052f791', 'pending', '', '# FurniStore — Access & Security'),
    ('Đặc thù bảo mật của FurniStore'::text, 'Ngoài API cho khách hàng thông thường, FurniStore còn có **Delivery App** (dùng bởi đội giao hàng/lắp đặt, không phải nhân viên văn phòng) truy cập API qua thiết bị di động ngoài hiện trường — đây là nhóm người dùng có rủi ro thiết bị bị mất/thất lạc cao hơn nhân viên văn phòng thông thường, cần cân nhắc riêng về thời hạn token và khả năng thu hồi truy cập nhanh.', 1, 73, 'Ngoài API cho khách hàng thông thường, FurniStore còn có **Delivery App** (dùng bởi đội giao hàng/lắp đặt, không phải nhân viên văn phòng) truy cập API qua thiết bị di động ngoài hiện trường — đây là nhóm người dùng có rủi ro thiết bị bị mất/thất lạc cao hơn nhân viên văn phòng thông thường, cần cân nhắc riêng về thời hạn token và khả năng thu hồi truy cập nhanh.', '038e5c43632b8e2c31855cf2b502cf214d2b32dddf34850da9baa20bef61a74a', 'pending', '', 'Ngoài API cho khách hàng thông thường, FurniStore còn có **Delivery App** (dùng bởi đội giao hàng/lắp đặt, không phải nhân viên văn phòng) truy cập API qua thiết bị di động ngoài hiện trường — đây là nhóm người dùng có rủi ro thiết bị bị mất/thất lạc cao hơn nhân viên văn phòng thông thường, cần cân nhắc riêng về thời hạn token và khả năng thu hồi truy cập nhanh.'),
    ('Xin quyền truy cập'::text, '| Hệ thống | Cách xin | Ai duyệt | Thời gian xử lý |
|---|---|---|---|
| Repo GitHub (team `furnistore-backend`) | PM thêm qua GitHub Org settings | PM | Trong ngày làm việc đầu |
| MongoDB Atlas (staging) | Xin qua IT, chỉ cấp quyền read cho engineer mới, quyền write cấp sau khi quen hệ thống (thường sau 2-3 tuần) | Tech Lead | 1 ngày làm việc |
| Render Dashboard | Chỉ PM và Tech Lead có quyền deploy production, engineer thường chỉ xem log qua Render Dashboard (read-only) | Tech Lead | 1 ngày làm việc |
| Tài khoản test Delivery App | Tạo qua script seed riêng, không dùng tài khoản đội giao hàng thật để test | Tự làm | Ngay lập tức |
| 1Password vault "FurniStore Dev" | Chứa credential dev/staging (API key đối tác vận chuyển sandbox...) | Tech Lead thêm vào vault | Trong ngày |', 2, 160, '| Hệ thống | Cách xin | Ai duyệt | Thời gian xử lý |
|---|---|---|---|
| Repo GitHub (team `furnistore-backend`) | PM thêm qua GitHub Org settings | PM | Trong ngày làm việc đầu |
| MongoDB Atlas (staging) | Xin qua IT, chỉ cấp quyền read cho engineer mới, quyền write cấp sau khi quen hệ thống (thường sau 2-3 tuần) | Tech Lead | 1 ngày làm việc |
| Render Dashboard | Chỉ PM và Tech Lead có quyền deploy production, engineer thường chỉ xem log qua Render Dashboard (read-only) | Tech Lead | 1 ngày làm việc |
| Tài khoản test Delivery App | Tạo qua script seed riêng, không dùng tài khoản đội giao hàng thật để test | Tự làm | Ngay lập tức |
| 1Password vault "FurniStore Dev" | Chứa credential dev/staging (API key đối tác vận chuyển sandbox...) | Tech Lead thêm vào vault | Trong ngày |', '4f01d0a0620a6443a823fe291dd9f84b7fec4cfd2b533db3bdc57491ca77dbf9', 'pending', '', '| Hệ thống | Cách xin | Ai duyệt | Thời gian xử lý |
|---|---|---|---|
| Repo GitHub (team `furnistore-backend`) | PM thêm qua GitHub Org settings | PM | Trong ngày làm việc đầu |
| MongoDB Atlas (staging) | Xin qua IT, chỉ cấp quyền read cho engineer mới, quyền write cấp sau khi quen hệ thống (thường sau 2-3 tuần) | Tech Lead | 1 ngày làm việc |
| Render Dashboard | Chỉ PM và Tech Lead có quyền deploy production, engineer thường chỉ xem log qua Render Dashboard (read-only) | Tech Lead | 1 ngày làm việc |
| Tài khoản test Delivery App | Tạo qua script seed riêng, không dùng tài khoản đội giao hàng thật để test | Tự làm | Ngay lập tức |
| 1Password vault "FurniStore Dev" | Chứa credential dev/staging (API key đối tác vận chuyển sandbox...) | Tech Lead thêm vào vault | Trong ngày |'),
    ('Quy tắc bảo mật'::text, '- Toàn bộ input từ client phải validate bằng `zod` schema trước khi vào business logic — không tin dữ liệu client gửi lên dưới bất kỳ hình thức nào, kể cả từ Delivery App chính chủ (thiết bị có thể bị jailbreak/root, request có thể bị can thiệp).
- Token đăng nhập Delivery App có thời hạn ngắn hơn đáng kể so với web/app khách hàng (TTL 8 giờ, tương ứng ca làm việc, thay vì 30 ngày) — giảm thiểu rủi ro nếu thiết bị bị mất, đội vận hành có thể yêu cầu thu hồi ngay qua Admin Portal (revoke token tức thì, không cần đợi hết hạn).
- API đối tác vận chuyển (tính phí ship) dùng API key lưu trong biến môi trường ở Render (Render Secret, không phải file `.env` commit vào repo), xoay vòng (rotate) mỗi 6 tháng theo lịch, có nhắc nhở tự động qua calendar nội bộ team.
- Rate limit 60 request/phút/IP cho endpoint public, riêng `/api/checkout` giới hạn chặt hơn (10 req/phút) để chống spam đặt hàng ảo — đã từng bị 1 đợt spam đặt hàng ảo (bot test) trước khi có rate limit này, gây nhiễu số liệu báo cáo kinh doanh trong vài giờ.
- Ảnh xác nhận lắp đặt do đội giao hàng upload qua Delivery App lưu trên Cloudinary với access mode "authenticated" (không public URL trực tiếp), chỉ truy cập được qua signed URL có thời hạn ngắn (1 giờ) sinh bởi backend — tránh lộ hình ảnh nhà khách hàng nếu URL bị lộ ra ngoài.', 3, 264, '- Toàn bộ input từ client phải validate bằng `zod` schema trước khi vào business logic — không tin dữ liệu client gửi lên dưới bất kỳ hình thức nào, kể cả từ Delivery App chính chủ (thiết bị có thể bị jailbreak/root, request có thể bị can thiệp).
- Token đăng nhập Delivery App có thời hạn ngắn hơn đáng kể so với web/app khách hàng (TTL 8 giờ, tương ứng ca làm việc, thay vì 30 ngày) — giảm thiểu rủi ro nếu thiết bị bị mất, đội vận hành có thể yêu cầu thu hồi ngay qua Admin Portal (revoke token tức thì, không cần đợi hết hạn).
- API đối tác vận chuyển (tính phí ship) dùng API key lưu trong biến môi trường ở Render (Render Secret, không phải file `.env` commit vào repo), xoay vòng (rotate) mỗi 6 tháng theo lịch, có nhắc nhở tự động qua calendar nội bộ team.
- Rate limit 60 request/phút/IP cho endpoint public, riêng `/api/checkout` giới hạn chặt hơn (10 req/phút) để chống spam đặt hàng ảo — đã từng bị 1 đợt spam đặt hàng ảo (bot test) trước khi có rate limit này, gây nhiễu số liệu báo cáo kinh doanh trong vài giờ.
- Ảnh xác nhận lắp đặt do đội giao hàng upload qua Delivery App lưu trên Cloudinary với access mode "authenticated" (không public URL trực tiếp), chỉ truy cập được qua signed URL có thời hạn ngắn (1 giờ) sinh bởi backend — tránh lộ hình ảnh nhà khách hàng nếu URL bị lộ ra ngoài.', '0f86ddb4546a4885fe7055e19014384a6d580ebce63700125615f879d4c319d5', 'pending', '', '- Toàn bộ input từ client phải validate bằng `zod` schema trước khi vào business logic — không tin dữ liệu client gửi lên dưới bất kỳ hình thức nào, kể cả từ Delivery App chính chủ (thiết bị có thể bị jailbreak/root, request có thể bị can thiệp).
- Token đăng nhập Delivery App có thời hạn ngắn hơn đáng kể so với web/app khách hàng (TTL 8 giờ, tương ứng ca làm việc, thay vì 30 ngày) — giảm thiểu rủi ro nếu thiết bị bị mất, đội vận hành có thể yêu cầu thu hồi ngay qua Admin Portal (revoke token tức thì, không cần đợi hết hạn).
- API đối tác vận chuyển (tính phí ship) dùng API key lưu trong biến môi trường ở Render (Render Secret, không phải file `.env` commit vào repo), xoay vòng (rotate) mỗi 6 tháng theo lịch, có nhắc nhở tự động qua calendar nội bộ team.
- Rate limit 60 request/phút/IP cho endpoint public, riêng `/api/checkout` giới hạn chặt hơn (10 req/phút) để chống spam đặt hàng ảo — đã từng bị 1 đợt spam đặt hàng ảo (bot test) trước khi có rate limit này, gây nhiễu số liệu báo cáo kinh doanh trong vài giờ.
- Ảnh xác nhận lắp đặt do đội giao hàng upload qua Delivery App lưu trên Cloudinary với access mode "authenticated" (không public URL trực tiếp), chỉ truy cập được qua signed URL có thời hạn ngắn (1 giờ) sinh bởi backend — tránh lộ hình ảnh nhà khách hàng nếu URL bị lộ ra ngoài.'),
    ('Compliance'::text, 'Địa chỉ giao hàng và số điện thoại khách hàng là dữ liệu nhạy cảm cần bảo vệ theo Nghị định 13/2023/NĐ-CP — không chia sẻ trực tiếp cho đối tác vận chuyển ngoài phạm vi cần thiết (chỉ gửi thông tin cần cho việc giao hàng cụ thể đó, không gửi toàn bộ lịch sử đơn hàng của khách).', 4, 60, 'Địa chỉ giao hàng và số điện thoại khách hàng là dữ liệu nhạy cảm cần bảo vệ theo Nghị định 13/2023/NĐ-CP — không chia sẻ trực tiếp cho đối tác vận chuyển ngoài phạm vi cần thiết (chỉ gửi thông tin cần cho việc giao hàng cụ thể đó, không gửi toàn bộ lịch sử đơn hàng của khách).', '248befeba817fc35262df4ef828c42d84f1c1c8f6b477f514a3a3c3a65afbc09', 'pending', '', 'Địa chỉ giao hàng và số điện thoại khách hàng là dữ liệu nhạy cảm cần bảo vệ theo Nghị định 13/2023/NĐ-CP — không chia sẻ trực tiếp cho đối tác vận chuyển ngoài phạm vi cần thiết (chỉ gửi thông tin cần cho việc giao hàng cụ thể đó, không gửi toàn bộ lịch sử đơn hàng của khách).'),
    ('Liên hệ khi có sự cố bảo mật'::text, 'Báo Security team qua #security-incident, đính kèm log liên quan nếu có. Với sự cố liên quan thiết bị Delivery App bị mất/thất lạc, báo ngay cho Tech Lead để thu hồi token ngay lập tức qua Admin Portal, không chờ quy trình báo cáo đầy đủ mới xử lý.', 5, 50, 'Báo Security team qua #security-incident, đính kèm log liên quan nếu có. Với sự cố liên quan thiết bị Delivery App bị mất/thất lạc, báo ngay cho Tech Lead để thu hồi token ngay lập tức qua Admin Portal, không chờ quy trình báo cáo đầy đủ mới xử lý.', '55a7b8c710676ffa8d89e887083e785547d2b39f55e4c85da0f6fe2c14ac1a1d', 'pending', '', 'Báo Security team qua #security-incident, đính kèm log liên quan nếu có. Với sự cố liên quan thiết bị Delivery App bị mất/thất lạc, báo ngay cho Tech Lead để thu hồi token ngay lập tức qua Admin Portal, không chờ quy trình báo cáo đầy đủ mới xử lý.')
) AS c(heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical);

-- FURNISTORE: FurniStore — Codebase Guide
WITH doc AS (
  INSERT INTO knowledge_documents
    (project_id, created_by_user_id, knowledge_domain, document_category, policy_category,
     source_key, category_confirmed, category_classification_status,
     title, source_url, status, created_at, updated_at)
  VALUES (
    (SELECT project_id FROM projects WHERE key = 'FURNISTORE'),
    (SELECT user_id FROM users WHERE email = 'pm.furnistore@onboarding.dev'),
    'PROJECT', 'CODEBASE_GUIDE', NULL,
    'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/furnistore/codebase-guide', true, 'CLASSIFIED',
    'FurniStore — Codebase Guide', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/furnistore/codebase-guide', 'ACTIVE', now(), now()
  )
  RETURNING document_id
),
ver AS (
  INSERT INTO document_versions
    (document_id, version_no, revision_no, embedding_model_version,
     storage_uri, checksum, status, created_at)
  SELECT document_id, 1, 1, 'pending', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/furnistore/codebase-guide', '1d760f6b125254371aff3575c1bd509fe5d7d7d37b4dcf71f4cd326adb95cc7d', 'ACTIVE', now() FROM doc
  RETURNING version_id
)
INSERT INTO document_chunks (version_id, heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical)
SELECT ver.version_id, c.heading, c.content, c.chunk_index, c.token_count, c.embedding_text, c.content_hash, c.embedding_model_version, c.lexical_identifiers, c.lexical_technical
FROM ver, (VALUES
    (NULL::text, '# FurniStore — Codebase Guide', 0, 5, '# FurniStore — Codebase Guide', 'd5394b66de8808c2e4fa52e5696da1882c31c83b6c1e83d222300813e5141060', 'pending', '', '# FurniStore — Codebase Guide'),
    ('Cấu trúc thư mục'::text, '```
src/
  modules/<tên-module>/
    <module>.controller.js     # nhận request, gọi service, trả response — không chứa business logic
    <module>.service.js          # business logic chính
    <module>.routes.js             # định nghĩa route + JSDoc comment (tự sinh Swagger)
    <module>.schema.js               # zod schema validate input
    <module>.repository.js             # wrapper quanh Prisma Client hoặc Mongoose model (chỉ có ở module cần thiết)
  shared/
    middlewares/
      error-handler.js          # xử lý lỗi tập trung
      auth.js                     # verify JWT, phân biệt token khách hàng vs Delivery App
    config/
      prisma-client.js
      mongo-connection.js
    jobs/
      shipping-fee-worker.js    # BullMQ worker, chạy process riêng (pnpm run worker)
```', 1, 89, '```
src/
  modules/<tên-module>/
    <module>.controller.js     # nhận request, gọi service, trả response — không chứa business logic
    <module>.service.js          # business logic chính
    <module>.routes.js             # định nghĩa route + JSDoc comment (tự sinh Swagger)
    <module>.schema.js               # zod schema validate input
    <module>.repository.js             # wrapper quanh Prisma Client hoặc Mongoose model (chỉ có ở module cần thiết)
  shared/
    middlewares/
      error-handler.js          # xử lý lỗi tập trung
      auth.js                     # verify JWT, phân biệt token khách hàng vs Delivery App
    config/
      prisma-client.js
      mongo-connection.js
    jobs/
      shipping-fee-worker.js    # BullMQ worker, chạy process riêng (pnpm run worker)
```', '29af2ce57c568e4270b8606accf264ec4bcc52947cb501c21d853dd566ba379d', 'pending', '', '```
src/
  modules/<tên-module>/
    <module>.controller.js     # nhận request, gọi service, trả response — không chứa business logic
    <module>.service.js          # business logic chính
    <module>.routes.js             # định nghĩa route + JSDoc comment (tự sinh Swagger)
    <module>.schema.js               # zod schema validate input
    <module>.repository.js             # wrapper quanh Prisma Client hoặc Mongoose model (chỉ có ở module cần thiết)
  shared/
    middlewares/
      error-handler.js          # xử lý lỗi tập trung
      auth.js                     # verify JWT, phân biệt token khách hàng vs Delivery App
    config/
      prisma-client.js
      mongo-connection.js
    jobs/
      shipping-fee-worker.js    # BullMQ worker, chạy process riêng (pnpm run worker)
```'),
    ('Nguyên tắc kiến trúc: module tự chứa (self-contained)'::text, 'Mỗi module tự chứa toàn bộ: route, controller, service, schema validate đều nằm chung 1 thư mục theo tên module — **không** tách route/controller/service ra các thư mục cấp cao riêng biệt (khác với style MVC truyền thống nhiều dự án Express khác dùng). Lý do: giúp dễ tìm toàn bộ code liên quan tới 1 tính năng chỉ trong 1 thư mục, giảm thời gian "nhảy file" khi debug hoặc thêm tính năng — quan trọng với team nhỏ (5 người) cần tốc độ phát triển nhanh.', 2, 88, 'Mỗi module tự chứa toàn bộ: route, controller, service, schema validate đều nằm chung 1 thư mục theo tên module — **không** tách route/controller/service ra các thư mục cấp cao riêng biệt (khác với style MVC truyền thống nhiều dự án Express khác dùng). Lý do: giúp dễ tìm toàn bộ code liên quan tới 1 tính năng chỉ trong 1 thư mục, giảm thời gian "nhảy file" khi debug hoặc thêm tính năng — quan trọng với team nhỏ (5 người) cần tốc độ phát triển nhanh.', '403b4a6238e200a0ee46654ec5a1772b7a9b1c7accc2571aa503c7179fd3733b', 'pending', '', 'Mỗi module tự chứa toàn bộ: route, controller, service, schema validate đều nằm chung 1 thư mục theo tên module — **không** tách route/controller/service ra các thư mục cấp cao riêng biệt (khác với style MVC truyền thống nhiều dự án Express khác dùng). Lý do: giúp dễ tìm toàn bộ code liên quan tới 1 tính năng chỉ trong 1 thư mục, giảm thời gian "nhảy file" khi debug hoặc thêm tính năng — quan trọng với team nhỏ (5 người) cần tốc độ phát triển nhanh.'),
    ('File quan trọng cần đọc trước khi code'::text, '- **`modules/shipping/shipping.service.js`** — logic tính phí ship theo bảng giá tỉnh/thành (tính sơ bộ, đồng bộ) + trigger job BullMQ tính lại giá chính xác hơn. Đọc kỹ để hiểu 2 giai đoạn tính phí (sơ bộ vs chính xác) trước khi sửa bất cứ gì liên quan.
- **`shared/jobs/shipping-fee-worker.js`** — worker xử lý job BullMQ, có timeout cứng + circuit breaker sau sự cố tháng 04/2025 (xem `overview.md`). Bất kỳ code mới nào gọi API bên ngoài trong file này BẮT BUỘC phải wrap qua helper `callExternalApiWithTimeout()` có sẵn, không tự viết `fetch`/`axios` trực tiếp không có timeout.
- **`shared/middlewares/error-handler.js`** — cách xử lý lỗi tập trung, mọi lỗi nghiệp vụ nên throw `AppError` (class tự định nghĩa, có `statusCode` và `code` riêng) thay vì lỗi thường (`throw new Error(...)`) để middleware xử lý đúng status code và format response lỗi nhất quán cho toàn bộ API.
- **`modules/delivery/delivery.service.js`** — logic đồng bộ giữa Postgres (Order) và MongoDB (DeliverySchedule), bao gồm job quét bù trừ định kỳ (xem giải thích trong `architecture.md` mục "vì sao 2 database").', 3, 178, '- **`modules/shipping/shipping.service.js`** — logic tính phí ship theo bảng giá tỉnh/thành (tính sơ bộ, đồng bộ) + trigger job BullMQ tính lại giá chính xác hơn. Đọc kỹ để hiểu 2 giai đoạn tính phí (sơ bộ vs chính xác) trước khi sửa bất cứ gì liên quan.
- **`shared/jobs/shipping-fee-worker.js`** — worker xử lý job BullMQ, có timeout cứng + circuit breaker sau sự cố tháng 04/2025 (xem `overview.md`). Bất kỳ code mới nào gọi API bên ngoài trong file này BẮT BUỘC phải wrap qua helper `callExternalApiWithTimeout()` có sẵn, không tự viết `fetch`/`axios` trực tiếp không có timeout.
- **`shared/middlewares/error-handler.js`** — cách xử lý lỗi tập trung, mọi lỗi nghiệp vụ nên throw `AppError` (class tự định nghĩa, có `statusCode` và `code` riêng) thay vì lỗi thường (`throw new Error(...)`) để middleware xử lý đúng status code và format response lỗi nhất quán cho toàn bộ API.
- **`modules/delivery/delivery.service.js`** — logic đồng bộ giữa Postgres (Order) và MongoDB (DeliverySchedule), bao gồm job quét bù trừ định kỳ (xem giải thích trong `architecture.md` mục "vì sao 2 database").', '38677ca8e63a57c17473d886879fb6b21c7dff418668cc6b4362aa9a6e7b3956', 'pending', '', '- **`modules/shipping/shipping.service.js`** — logic tính phí ship theo bảng giá tỉnh/thành (tính sơ bộ, đồng bộ) + trigger job BullMQ tính lại giá chính xác hơn. Đọc kỹ để hiểu 2 giai đoạn tính phí (sơ bộ vs chính xác) trước khi sửa bất cứ gì liên quan.
- **`shared/jobs/shipping-fee-worker.js`** — worker xử lý job BullMQ, có timeout cứng + circuit breaker sau sự cố tháng 04/2025 (xem `overview.md`). Bất kỳ code mới nào gọi API bên ngoài trong file này BẮT BUỘC phải wrap qua helper `callExternalApiWithTimeout()` có sẵn, không tự viết `fetch`/`axios` trực tiếp không có timeout.
- **`shared/middlewares/error-handler.js`** — cách xử lý lỗi tập trung, mọi lỗi nghiệp vụ nên throw `AppError` (class tự định nghĩa, có `statusCode` và `code` riêng) thay vì lỗi thường (`throw new Error(...)`) để middleware xử lý đúng status code và format response lỗi nhất quán cho toàn bộ API.
- **`modules/delivery/delivery.service.js`** — logic đồng bộ giữa Postgres (Order) và MongoDB (DeliverySchedule), bao gồm job quét bù trừ định kỳ (xem giải thích trong `architecture.md` mục "vì sao 2 database").'),
    ('Testing strategy'::text, '- Unit test (Jest): mock Prisma Client bằng `jest-mock-extended`, mock Mongoose model bằng `mongodb-memory-server` cho trường hợp cần test logic MongoDB thật mà không cần Atlas thật.
- Integration test: dùng Supertest gọi thẳng vào Express app, với Postgres/MongoDB/Redis thật chạy trong Docker (service container trong CI).
- Không có contract test riêng (khác PhoneShop/TourBook) — team nhỏ, chỉ có API cho Delivery App là "khách hàng nội bộ" duy nhất cần đảm bảo backward-compatible, quản lý qua việc luôn giữ endpoint cũ hoạt động thêm ít nhất 1 tháng sau khi có endpoint mới thay thế (không breaking change đột ngột).', 4, 102, '- Unit test (Jest): mock Prisma Client bằng `jest-mock-extended`, mock Mongoose model bằng `mongodb-memory-server` cho trường hợp cần test logic MongoDB thật mà không cần Atlas thật.
- Integration test: dùng Supertest gọi thẳng vào Express app, với Postgres/MongoDB/Redis thật chạy trong Docker (service container trong CI).
- Không có contract test riêng (khác PhoneShop/TourBook) — team nhỏ, chỉ có API cho Delivery App là "khách hàng nội bộ" duy nhất cần đảm bảo backward-compatible, quản lý qua việc luôn giữ endpoint cũ hoạt động thêm ít nhất 1 tháng sau khi có endpoint mới thay thế (không breaking change đột ngột).', '7b33ec6f49c5ad68826be9d73c665574096a0c2348d8d9633388e0b2ff043038', 'pending', '', '- Unit test (Jest): mock Prisma Client bằng `jest-mock-extended`, mock Mongoose model bằng `mongodb-memory-server` cho trường hợp cần test logic MongoDB thật mà không cần Atlas thật.
- Integration test: dùng Supertest gọi thẳng vào Express app, với Postgres/MongoDB/Redis thật chạy trong Docker (service container trong CI).
- Không có contract test riêng (khác PhoneShop/TourBook) — team nhỏ, chỉ có API cho Delivery App là "khách hàng nội bộ" duy nhất cần đảm bảo backward-compatible, quản lý qua việc luôn giữ endpoint cũ hoạt động thêm ít nhất 1 tháng sau khi có endpoint mới thay thế (không breaking change đột ngột).'),
    ('Quy ước đặt tên biến môi trường'::text, 'Mọi biến môi trường bắt buộc được validate lúc khởi động qua `zod` schema trong `shared/config/env.js` — app sẽ **crash ngay lúc start** với thông báo rõ ràng nếu thiếu biến bắt buộc, thay vì chạy với giá trị `undefined` gây lỗi khó hiểu ở đâu đó sau này lúc runtime.', 5, 51, 'Mọi biến môi trường bắt buộc được validate lúc khởi động qua `zod` schema trong `shared/config/env.js` — app sẽ **crash ngay lúc start** với thông báo rõ ràng nếu thiếu biến bắt buộc, thay vì chạy với giá trị `undefined` gây lỗi khó hiểu ở đâu đó sau này lúc runtime.', 'e65880c3286f39e17a59fc70b6fec433f5460f4e9d8e90b48477f7acd03efa47', 'pending', '', 'Mọi biến môi trường bắt buộc được validate lúc khởi động qua `zod` schema trong `shared/config/env.js` — app sẽ **crash ngay lúc start** với thông báo rõ ràng nếu thiếu biến bắt buộc, thay vì chạy với giá trị `undefined` gây lỗi khó hiểu ở đâu đó sau này lúc runtime.')
) AS c(heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical);

-- FURNISTORE: FurniStore — Coding Convention
WITH doc AS (
  INSERT INTO knowledge_documents
    (project_id, created_by_user_id, knowledge_domain, document_category, policy_category,
     source_key, category_confirmed, category_classification_status,
     title, source_url, status, created_at, updated_at)
  VALUES (
    (SELECT project_id FROM projects WHERE key = 'FURNISTORE'),
    (SELECT user_id FROM users WHERE email = 'pm.furnistore@onboarding.dev'),
    'PROJECT', 'CONVENTION', NULL,
    'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/furnistore/convention', true, 'CLASSIFIED',
    'FurniStore — Coding Convention', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/furnistore/convention', 'ACTIVE', now(), now()
  )
  RETURNING document_id
),
ver AS (
  INSERT INTO document_versions
    (document_id, version_no, revision_no, embedding_model_version,
     storage_uri, checksum, status, created_at)
  SELECT document_id, 1, 1, 'pending', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/furnistore/convention', '1585d84540fbd4d8e7fd80e5f8a095a493273db2899dbbad22dc162faf3a7d2f', 'ACTIVE', now() FROM doc
  RETURNING version_id
)
INSERT INTO document_chunks (version_id, heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical)
SELECT ver.version_id, c.heading, c.content, c.chunk_index, c.token_count, c.embedding_text, c.content_hash, c.embedding_model_version, c.lexical_identifiers, c.lexical_technical
FROM ver, (VALUES
    (NULL::text, '# FurniStore — Coding Convention', 0, 5, '# FurniStore — Coding Convention', 'f353d48cc621615217a005c00339cc2f1d3b0d9bdfb1c3028a72684be8821650', 'pending', '', '# FurniStore — Coding Convention'),
    ('Triết lý chung'::text, 'Team nhỏ (5 kỹ sư), ưu tiên tốc độ phát triển và giảm boilerplate hơn là quy trình phức tạp — nhưng vẫn giữ nghiêm ngặt ở những chỗ ảnh hưởng trực tiếp tới tiền/dữ liệu khách hàng (thanh toán, thông tin giao hàng).', 1, 44, 'Team nhỏ (5 kỹ sư), ưu tiên tốc độ phát triển và giảm boilerplate hơn là quy trình phức tạp — nhưng vẫn giữ nghiêm ngặt ở những chỗ ảnh hưởng trực tiếp tới tiền/dữ liệu khách hàng (thanh toán, thông tin giao hàng).', 'd3028bda2a13b86e606c79e3d3be9bcb1286c0ecb4e34c692b28e8286aceb092', 'pending', '', 'Team nhỏ (5 kỹ sư), ưu tiên tốc độ phát triển và giảm boilerplate hơn là quy trình phức tạp — nhưng vẫn giữ nghiêm ngặt ở những chỗ ảnh hưởng trực tiếp tới tiền/dữ liệu khách hàng (thanh toán, thông tin giao hàng).'),
    ('JavaScript/Node.js style'::text, '- Format + lint bằng ESLint (config `airbnb-base` tuỳ chỉnh thêm vài rule) + Prettier, chạy tự động qua Husky pre-commit hook.
- Đặt tên file: `kebab-case` (`shipping-fee.service.js`), biến/hàm `camelCase`, class `PascalCase`, hằng số `UPPER_SNAKE_CASE`.
- Bắt buộc dùng `async/await`, không dùng `.then()` chain trong code mới (code cũ còn sót lại đang dọn dần, không bắt buộc sửa hết ngay khi không liên quan tới task đang làm).
- Không dùng `var`, chỉ `const`/`let`. Ưu tiên `const` mặc định, chỉ dùng `let` khi thực sự cần reassign.
- Destructuring object/array khi hợp lý để code ngắn gọn hơn, nhưng không lạm dụng tới mức khó đọc (nested destructuring quá 2 cấp nên tách ra biến trung gian).', 2, 118, '- Format + lint bằng ESLint (config `airbnb-base` tuỳ chỉnh thêm vài rule) + Prettier, chạy tự động qua Husky pre-commit hook.
- Đặt tên file: `kebab-case` (`shipping-fee.service.js`), biến/hàm `camelCase`, class `PascalCase`, hằng số `UPPER_SNAKE_CASE`.
- Bắt buộc dùng `async/await`, không dùng `.then()` chain trong code mới (code cũ còn sót lại đang dọn dần, không bắt buộc sửa hết ngay khi không liên quan tới task đang làm).
- Không dùng `var`, chỉ `const`/`let`. Ưu tiên `const` mặc định, chỉ dùng `let` khi thực sự cần reassign.
- Destructuring object/array khi hợp lý để code ngắn gọn hơn, nhưng không lạm dụng tới mức khó đọc (nested destructuring quá 2 cấp nên tách ra biến trung gian).', 'c172d9c9fe8c8d0225699968c6ffa32c2621953ebeac06f69a0ec00db632192e', 'pending', '', '- Format + lint bằng ESLint (config `airbnb-base` tuỳ chỉnh thêm vài rule) + Prettier, chạy tự động qua Husky pre-commit hook.
- Đặt tên file: `kebab-case` (`shipping-fee.service.js`), biến/hàm `camelCase`, class `PascalCase`, hằng số `UPPER_SNAKE_CASE`.
- Bắt buộc dùng `async/await`, không dùng `.then()` chain trong code mới (code cũ còn sót lại đang dọn dần, không bắt buộc sửa hết ngay khi không liên quan tới task đang làm).
- Không dùng `var`, chỉ `const`/`let`. Ưu tiên `const` mặc định, chỉ dùng `let` khi thực sự cần reassign.
- Destructuring object/array khi hợp lý để code ngắn gọn hơn, nhưng không lạm dụng tới mức khó đọc (nested destructuring quá 2 cấp nên tách ra biến trung gian).'),
    ('TypeScript hoá dần (đang chuyển đổi)'::text, 'Dự án khởi đầu bằng JavaScript thuần, từ Q2/2025 team quyết định chuyển dần sang TypeScript cho module mới (đã áp dụng cho `delivery` và `showroom`), module cũ (`catalog`, `cart`, `order`) vẫn JavaScript, sẽ chuyển dần khi có thời gian refactor — không bắt buộc convert toàn bộ ngay lập tức, ưu tiên tính năng mới dùng TypeScript trước.', 3, 59, 'Dự án khởi đầu bằng JavaScript thuần, từ Q2/2025 team quyết định chuyển dần sang TypeScript cho module mới (đã áp dụng cho `delivery` và `showroom`), module cũ (`catalog`, `cart`, `order`) vẫn JavaScript, sẽ chuyển dần khi có thời gian refactor — không bắt buộc convert toàn bộ ngay lập tức, ưu tiên tính năng mới dùng TypeScript trước.', '7e65c220b7158d9fbd785e9ebd353836a7e4901497070df92c25974fd07088a9', 'pending', '', 'Dự án khởi đầu bằng JavaScript thuần, từ Q2/2025 team quyết định chuyển dần sang TypeScript cho module mới (đã áp dụng cho `delivery` và `showroom`), module cũ (`catalog`, `cart`, `order`) vẫn JavaScript, sẽ chuyển dần khi có thời gian refactor — không bắt buộc convert toàn bộ ngay lập tức, ưu tiên tính năng mới dùng TypeScript trước.'),
    ('Git'::text, '- Nhánh đặt tên `feature/FURNI-<số ticket>-mo-ta-ngan`.
- Commit message theo Conventional Commits (`feat:`, `fix:`, `chore:`, `refactor:`).
- PR bắt buộc 1 approve + CI xanh (lint + test) mới merge, dùng squash merge.
- Riêng PR liên quan `shipping` hoặc `delivery` module (2 phần có sự cố từng xảy ra) nên có thêm 1 approve thứ 2 nếu thay đổi lớn (>200 dòng), dù không bắt buộc cứng qua branch protection — team tự giác áp dụng dựa trên bài học từ 2 sự cố đã xảy ra.', 4, 88, '- Nhánh đặt tên `feature/FURNI-<số ticket>-mo-ta-ngan`.
- Commit message theo Conventional Commits (`feat:`, `fix:`, `chore:`, `refactor:`).
- PR bắt buộc 1 approve + CI xanh (lint + test) mới merge, dùng squash merge.
- Riêng PR liên quan `shipping` hoặc `delivery` module (2 phần có sự cố từng xảy ra) nên có thêm 1 approve thứ 2 nếu thay đổi lớn (>200 dòng), dù không bắt buộc cứng qua branch protection — team tự giác áp dụng dựa trên bài học từ 2 sự cố đã xảy ra.', '4c2869067212e06ff142a1ddd5192aa43db2e2b6f138cc014d7a9a2447827615', 'pending', '', '- Nhánh đặt tên `feature/FURNI-<số ticket>-mo-ta-ngan`.
- Commit message theo Conventional Commits (`feat:`, `fix:`, `chore:`, `refactor:`).
- PR bắt buộc 1 approve + CI xanh (lint + test) mới merge, dùng squash merge.
- Riêng PR liên quan `shipping` hoặc `delivery` module (2 phần có sự cố từng xảy ra) nên có thêm 1 approve thứ 2 nếu thay đổi lớn (>200 dòng), dù không bắt buộc cứng qua branch protection — team tự giác áp dụng dựa trên bài học từ 2 sự cố đã xảy ra.'),
    ('Review checklist'::text, '- [ ] Input từ client có schema `zod` validate chưa.
- [ ] Lỗi nghiệp vụ throw `AppError`, không throw string/lỗi thường.
- [ ] Nếu đổi Prisma schema, đã tạo migration và test cả 2 chiều (up/down) chưa.
- [ ] Nếu gọi API bên ngoài mới (đối tác vận chuyển, dịch vụ khác), đã có timeout + xử lý lỗi rõ ràng chưa (xem bài học sự cố tháng 04/2025 trong `overview.md`).
- [ ] Nếu thêm field mới cho MongoDB document, đã cân nhắc dữ liệu cũ không có field này sẽ được xử lý thế nào (MongoDB không tự thêm default value cho document đã tồn tại như migration Postgres).', 5, 115, '- [ ] Input từ client có schema `zod` validate chưa.
- [ ] Lỗi nghiệp vụ throw `AppError`, không throw string/lỗi thường.
- [ ] Nếu đổi Prisma schema, đã tạo migration và test cả 2 chiều (up/down) chưa.
- [ ] Nếu gọi API bên ngoài mới (đối tác vận chuyển, dịch vụ khác), đã có timeout + xử lý lỗi rõ ràng chưa (xem bài học sự cố tháng 04/2025 trong `overview.md`).
- [ ] Nếu thêm field mới cho MongoDB document, đã cân nhắc dữ liệu cũ không có field này sẽ được xử lý thế nào (MongoDB không tự thêm default value cho document đã tồn tại như migration Postgres).', 'fdd7f880117042e8e42f5376be4c74758832e68191170606efee7b68c759fdcf', 'pending', '', '- [ ] Input từ client có schema `zod` validate chưa.
- [ ] Lỗi nghiệp vụ throw `AppError`, không throw string/lỗi thường.
- [ ] Nếu đổi Prisma schema, đã tạo migration và test cả 2 chiều (up/down) chưa.
- [ ] Nếu gọi API bên ngoài mới (đối tác vận chuyển, dịch vụ khác), đã có timeout + xử lý lỗi rõ ràng chưa (xem bài học sự cố tháng 04/2025 trong `overview.md`).
- [ ] Nếu thêm field mới cho MongoDB document, đã cân nhắc dữ liệu cũ không có field này sẽ được xử lý thế nào (MongoDB không tự thêm default value cho document đã tồn tại như migration Postgres).'),
    ('SLA review PR'::text, 'Team nhỏ nên không có SLA cứng bằng giờ như 2 dự án kia — quy ước chung: cố gắng review trong ngày làm việc, PR gắn label `urgent` (hotfix) thì review ngay khi thấy thông báo, bất kể đang làm gì.', 6, 42, 'Team nhỏ nên không có SLA cứng bằng giờ như 2 dự án kia — quy ước chung: cố gắng review trong ngày làm việc, PR gắn label `urgent` (hotfix) thì review ngay khi thấy thông báo, bất kể đang làm gì.', 'ee99287238e6179eab8da83bbc0c1561cd67641db0ec6f5f45e735761689b3bc', 'pending', '', 'Team nhỏ nên không có SLA cứng bằng giờ như 2 dự án kia — quy ước chung: cố gắng review trong ngày làm việc, PR gắn label `urgent` (hotfix) thì review ngay khi thấy thông báo, bất kể đang làm gì.')
) AS c(heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical);

-- FURNISTORE: FurniStore — First Task gợi ý cho engineer mới
WITH doc AS (
  INSERT INTO knowledge_documents
    (project_id, created_by_user_id, knowledge_domain, document_category, policy_category,
     source_key, category_confirmed, category_classification_status,
     title, source_url, status, created_at, updated_at)
  VALUES (
    (SELECT project_id FROM projects WHERE key = 'FURNISTORE'),
    (SELECT user_id FROM users WHERE email = 'pm.furnistore@onboarding.dev'),
    'PROJECT', 'FIRST_TASK', NULL,
    'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/furnistore/first-task', true, 'CLASSIFIED',
    'FurniStore — First Task gợi ý cho engineer mới', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/furnistore/first-task', 'ACTIVE', now(), now()
  )
  RETURNING document_id
),
ver AS (
  INSERT INTO document_versions
    (document_id, version_no, revision_no, embedding_model_version,
     storage_uri, checksum, status, created_at)
  SELECT document_id, 1, 1, 'pending', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/furnistore/first-task', 'db1500e8c1bcc5aa8657e858d266f8b8d3bbe13f980dbdf2155c041280cb94b5', 'ACTIVE', now() FROM doc
  RETURNING version_id
)
INSERT INTO document_chunks (version_id, heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical)
SELECT ver.version_id, c.heading, c.content, c.chunk_index, c.token_count, c.embedding_text, c.content_hash, c.embedding_model_version, c.lexical_identifiers, c.lexical_technical
FROM ver, (VALUES
    (NULL::text, '# FurniStore — First Task gợi ý cho engineer mới', 0, 10, '# FurniStore — First Task gợi ý cho engineer mới', '262c34aea69d3e1fc6c8b45788ba257374b75c7af320379dd970cd55dcae2afe', 'pending', '', '# FurniStore — First Task gợi ý cho engineer mới'),
    ('Mục đích'::text, 'Team nhỏ (5 người) nên engineer mới thường được giao việc thật khá sớm, nhưng vẫn bắt đầu bằng 1 task nhỏ ở module `catalog` (ít rủi ro nhất) để làm quen cấu trúc module tự chứa và quy trình PR trước khi động vào `shipping`/`delivery` (2 phần đã từng có sự cố, xem `overview.md`).', 1, 55, 'Team nhỏ (5 người) nên engineer mới thường được giao việc thật khá sớm, nhưng vẫn bắt đầu bằng 1 task nhỏ ở module `catalog` (ít rủi ro nhất) để làm quen cấu trúc module tự chứa và quy trình PR trước khi động vào `shipping`/`delivery` (2 phần đã từng có sự cố, xem `overview.md`).', 'addf48dbda7d90e2f306849c56b6dd91bb463fba096b03fba6b2a2505f09010c', 'pending', '', 'Team nhỏ (5 người) nên engineer mới thường được giao việc thật khá sớm, nhưng vẫn bắt đầu bằng 1 task nhỏ ở module `catalog` (ít rủi ro nhất) để làm quen cấu trúc module tự chứa và quy trình PR trước khi động vào `shipping`/`delivery` (2 phần đã từng có sự cố, xem `overview.md`).'),
    ('Task khởi động #1: Thêm filter theo khoảng giá cho API danh sách sản phẩm'::text, '**Mục tiêu**: làm quen cấu trúc module tự chứa (`controller -> service -> Prisma`), không đụng vào logic tính phí ship phức tạp.

**Các bước cụ thể**:
1. Đọc `modules/catalog/catalog.routes.js`, tìm route `GET /api/products`.
2. Thêm query param `minPrice`, `maxPrice` vào `catalog.schema.js` (zod schema) — chú ý dùng `z.coerce.number()` vì query param luôn là string, cần coerce sang number.
3. Cập nhật `catalog.service.js` truyền điều kiện lọc giá vào Prisma `where` clause (dùng object spread có điều kiện, tránh viết nhiều nhánh `if` lặp lại — xem ví dụ pattern có sẵn trong hàm `buildProductFilter()` cùng file).
4. Viết test ở `catalog.service.test.js` xác nhận lọc đúng, kể cả case chỉ có 1 trong 2 giá trị min/max.
5. Cập nhật JSDoc comment trên route để Swagger tự sinh docs đúng cho param mới.
6. Tạo PR, gắn label `good-first-issue`.

Task này thường mất 0.5–1 ngày, giúp engineer mới quen cách viết schema validate + query Prisma có điều kiện động.', 2, 160, '**Mục tiêu**: làm quen cấu trúc module tự chứa (`controller -> service -> Prisma`), không đụng vào logic tính phí ship phức tạp.

**Các bước cụ thể**:
1. Đọc `modules/catalog/catalog.routes.js`, tìm route `GET /api/products`.
2. Thêm query param `minPrice`, `maxPrice` vào `catalog.schema.js` (zod schema) — chú ý dùng `z.coerce.number()` vì query param luôn là string, cần coerce sang number.
3. Cập nhật `catalog.service.js` truyền điều kiện lọc giá vào Prisma `where` clause (dùng object spread có điều kiện, tránh viết nhiều nhánh `if` lặp lại — xem ví dụ pattern có sẵn trong hàm `buildProductFilter()` cùng file).
4. Viết test ở `catalog.service.test.js` xác nhận lọc đúng, kể cả case chỉ có 1 trong 2 giá trị min/max.
5. Cập nhật JSDoc comment trên route để Swagger tự sinh docs đúng cho param mới.
6. Tạo PR, gắn label `good-first-issue`.

Task này thường mất 0.5–1 ngày, giúp engineer mới quen cách viết schema validate + query Prisma có điều kiện động.', '4724e987e0edfe6c77ac185c6bee3f0087807d5879d9c952f8b98ff54f80bdb3', 'pending', '', '**Mục tiêu**: làm quen cấu trúc module tự chứa (`controller -> service -> Prisma`), không đụng vào logic tính phí ship phức tạp.

**Các bước cụ thể**:
1. Đọc `modules/catalog/catalog.routes.js`, tìm route `GET /api/products`.
2. Thêm query param `minPrice`, `maxPrice` vào `catalog.schema.js` (zod schema) — chú ý dùng `z.coerce.number()` vì query param luôn là string, cần coerce sang number.
3. Cập nhật `catalog.service.js` truyền điều kiện lọc giá vào Prisma `where` clause (dùng object spread có điều kiện, tránh viết nhiều nhánh `if` lặp lại — xem ví dụ pattern có sẵn trong hàm `buildProductFilter()` cùng file).
4. Viết test ở `catalog.service.test.js` xác nhận lọc đúng, kể cả case chỉ có 1 trong 2 giá trị min/max.
5. Cập nhật JSDoc comment trên route để Swagger tự sinh docs đúng cho param mới.
6. Tạo PR, gắn label `good-first-issue`.

Task này thường mất 0.5–1 ngày, giúp engineer mới quen cách viết schema validate + query Prisma có điều kiện động.'),
    ('Task khởi động #2 (sau khi hoàn thành task #1): Thêm endpoint xem lịch sử đơn hàng của khách'::text, '**Mục tiêu**: làm quen middleware auth (`shared/middlewares/auth.js`) và cách phân biệt token khách hàng vs token Delivery App.

**Các bước gợi ý**:
1. Thêm endpoint `GET /api/customers/me/orders` trong module `order`, yêu cầu JWT khách hàng hợp lệ (không chấp nhận token Delivery App — kiểm tra bằng field `type` trong JWT payload).
2. Chỉ trả về đơn hàng thuộc về đúng khách đang đăng nhập.
3. Viết test xác nhận: (a) không có token → 401, (b) token Delivery App gọi vào → 403 (sai loại token), (c) token khách hàng đúng → trả đúng dữ liệu, (d) không xem được đơn của khách khác dù biết `orderId`.', 3, 108, '**Mục tiêu**: làm quen middleware auth (`shared/middlewares/auth.js`) và cách phân biệt token khách hàng vs token Delivery App.

**Các bước gợi ý**:
1. Thêm endpoint `GET /api/customers/me/orders` trong module `order`, yêu cầu JWT khách hàng hợp lệ (không chấp nhận token Delivery App — kiểm tra bằng field `type` trong JWT payload).
2. Chỉ trả về đơn hàng thuộc về đúng khách đang đăng nhập.
3. Viết test xác nhận: (a) không có token → 401, (b) token Delivery App gọi vào → 403 (sai loại token), (c) token khách hàng đúng → trả đúng dữ liệu, (d) không xem được đơn của khách khác dù biết `orderId`.', '90620d9b4565add1eea7539ba582d8c95292accc617a62c27943b65cc0ee5b0d', 'pending', '', '**Mục tiêu**: làm quen middleware auth (`shared/middlewares/auth.js`) và cách phân biệt token khách hàng vs token Delivery App.

**Các bước gợi ý**:
1. Thêm endpoint `GET /api/customers/me/orders` trong module `order`, yêu cầu JWT khách hàng hợp lệ (không chấp nhận token Delivery App — kiểm tra bằng field `type` trong JWT payload).
2. Chỉ trả về đơn hàng thuộc về đúng khách đang đăng nhập.
3. Viết test xác nhận: (a) không có token → 401, (b) token Delivery App gọi vào → 403 (sai loại token), (c) token khách hàng đúng → trả đúng dữ liệu, (d) không xem được đơn của khách khác dù biết `orderId`.'),
    ('Sau 2 task khởi động'::text, 'Trao đổi với Tech Lead để nhận task nghiệp vụ thật — với team nhỏ, khả năng cao bạn sẽ được giao việc ở nhiều module khác nhau khá sớm thay vì chỉ chuyên 1 mảng như 2 dự án lớn hơn, đây cũng là điểm nhiều engineer thích khi làm ở team FurniStore.', 4, 54, 'Trao đổi với Tech Lead để nhận task nghiệp vụ thật — với team nhỏ, khả năng cao bạn sẽ được giao việc ở nhiều module khác nhau khá sớm thay vì chỉ chuyên 1 mảng như 2 dự án lớn hơn, đây cũng là điểm nhiều engineer thích khi làm ở team FurniStore.', '23ae4b88b51d43c342eb3004ec56c4a6fdb48611f10e899a578685437f3f40de', 'pending', '', 'Trao đổi với Tech Lead để nhận task nghiệp vụ thật — với team nhỏ, khả năng cao bạn sẽ được giao việc ở nhiều module khác nhau khá sớm thay vì chỉ chuyên 1 mảng như 2 dự án lớn hơn, đây cũng là điểm nhiều engineer thích khi làm ở team FurniStore.')
) AS c(heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical);

-- POLICY: Company Policy — Quy định chung công ty
WITH doc AS (
  INSERT INTO knowledge_documents
    (project_id, created_by_user_id, knowledge_domain, document_category, policy_category,
     source_key, category_confirmed, category_classification_status,
     title, source_url, status, created_at, updated_at)
  VALUES (
    NULL,
    (SELECT user_id FROM users WHERE email = 'hr@onboarding.dev'),
    'POLICY', NULL, 'COMPANY_POLICY',
    'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/policy/company-policy', true, 'CLASSIFIED',
    'Company Policy — Quy định chung công ty', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/policy/company-policy', 'ACTIVE', now(), now()
  )
  RETURNING document_id
),
ver AS (
  INSERT INTO document_versions
    (document_id, version_no, revision_no, embedding_model_version,
     storage_uri, checksum, status, created_at)
  SELECT document_id, 1, 1, 'pending', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/policy/company-policy', '40bbce836978de5156043ab8ce9b4e6eb4e1b182046cb749ede1f2a95fb70b6a', 'ACTIVE', now() FROM doc
  RETURNING version_id
)
INSERT INTO document_chunks (version_id, heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical)
SELECT ver.version_id, c.heading, c.content, c.chunk_index, c.token_count, c.embedding_text, c.content_hash, c.embedding_model_version, c.lexical_identifiers, c.lexical_technical
FROM ver, (VALUES
    (NULL::text, '# Company Policy — Quy định chung công ty', 0, 9, '# Company Policy — Quy định chung công ty', 'bbc438b621fd74771eb4316404ae8779554625fc4cf1883e9975d69ca34673b3', 'pending', '', '# Company Policy — Quy định chung công ty'),
    ('Giới thiệu'::text, 'Tài liệu này áp dụng cho toàn bộ nhân viên công ty, không phân biệt phòng ban hay dự án đang tham gia (PhoneShop, TourBooking, FurniStore, hay các dự án nội bộ khác). Đây là tài liệu **POLICY** cấp công ty (khác với tài liệu PROJECT gắn riêng từng dự án) — mọi thành viên onboarding vào bất kỳ dự án nào đều nên đọc tài liệu này ít nhất 1 lần trong tuần đầu tiên.', 1, 76, 'Tài liệu này áp dụng cho toàn bộ nhân viên công ty, không phân biệt phòng ban hay dự án đang tham gia (PhoneShop, TourBooking, FurniStore, hay các dự án nội bộ khác). Đây là tài liệu **POLICY** cấp công ty (khác với tài liệu PROJECT gắn riêng từng dự án) — mọi thành viên onboarding vào bất kỳ dự án nào đều nên đọc tài liệu này ít nhất 1 lần trong tuần đầu tiên.', '991e4f3a3fb15074494a05df8c38603f584928e60d18a3b8f193dc34dd52e9af', 'pending', '', 'Tài liệu này áp dụng cho toàn bộ nhân viên công ty, không phân biệt phòng ban hay dự án đang tham gia (PhoneShop, TourBooking, FurniStore, hay các dự án nội bộ khác). Đây là tài liệu **POLICY** cấp công ty (khác với tài liệu PROJECT gắn riêng từng dự án) — mọi thành viên onboarding vào bất kỳ dự án nào đều nên đọc tài liệu này ít nhất 1 lần trong tuần đầu tiên.'),
    ('Giờ làm việc'::text, 'Giờ hành chính chuẩn: 9:00–18:00, thứ Hai đến thứ Sáu, nghỉ trưa 12:00–13:30. Nhân viên khối kỹ thuật (Engineering) được áp dụng chính sách giờ linh hoạt: có thể vào làm trong khung 8:00–10:00, miễn đảm bảo đủ 8 tiếng làm việc hiệu quả/ngày và có mặt trong khung giờ "core hours" 10:00–16:00 để thuận tiện họp/trao đổi với team. Làm việc từ xa (remote) được chấp nhận tối đa 2 ngày/tuần đối với vị trí kỹ thuật, cần thông báo trước cho quản lý trực tiếp qua lịch chung của team.', 2, 92, 'Giờ hành chính chuẩn: 9:00–18:00, thứ Hai đến thứ Sáu, nghỉ trưa 12:00–13:30. Nhân viên khối kỹ thuật (Engineering) được áp dụng chính sách giờ linh hoạt: có thể vào làm trong khung 8:00–10:00, miễn đảm bảo đủ 8 tiếng làm việc hiệu quả/ngày và có mặt trong khung giờ "core hours" 10:00–16:00 để thuận tiện họp/trao đổi với team. Làm việc từ xa (remote) được chấp nhận tối đa 2 ngày/tuần đối với vị trí kỹ thuật, cần thông báo trước cho quản lý trực tiếp qua lịch chung của team.', '52d7a88f73bc1326b0292da5d1167b02c3ccdcf12a90782bd63730d56427b0a4', 'pending', '', 'Giờ hành chính chuẩn: 9:00–18:00, thứ Hai đến thứ Sáu, nghỉ trưa 12:00–13:30. Nhân viên khối kỹ thuật (Engineering) được áp dụng chính sách giờ linh hoạt: có thể vào làm trong khung 8:00–10:00, miễn đảm bảo đủ 8 tiếng làm việc hiệu quả/ngày và có mặt trong khung giờ "core hours" 10:00–16:00 để thuận tiện họp/trao đổi với team. Làm việc từ xa (remote) được chấp nhận tối đa 2 ngày/tuần đối với vị trí kỹ thuật, cần thông báo trước cho quản lý trực tiếp qua lịch chung của team.'),
    ('Onboarding nhân viên mới'::text, 'Mỗi nhân viên mới có 1 checklist onboarding riêng theo dự án được phân công, quản lý qua hệ thống Onboarding Buddy nội bộ. Checklist gồm các nhóm: Orientation (đọc tài liệu dự án), Access (xin quyền truy cập cần thiết), Setup (cài đặt môi trường phát triển), Codebase (hiểu cấu trúc code), Convention (quy tắc coding), và First Task/First PR (hoàn thành công việc thực tế đầu tiên).

PM (Project Manager) của dự án chịu trách nhiệm duyệt kế hoạch onboarding trước ngày nhân viên bắt đầu chính thức, đảm bảo mọi bước đã sẵn sàng (tài khoản, quyền truy cập cơ bản) trước ngày đầu tiên đi làm. Tech Lead chịu trách nhiệm theo sát tiến độ onboarding kỹ thuật trong 2 tuần đầu, có buổi 1-1 tổng kết sau khi hoàn thành PR đầu tiên.

Thời gian onboarding kỹ thuật tiêu chuẩn: 1-2 tuần cho engineer đã có kinh nghiệm, có thể kéo dài tới 3 tuần cho fresher hoặc người chuyển ngôn ngữ/tech stack mới hoàn toàn.', 3, 171, 'Mỗi nhân viên mới có 1 checklist onboarding riêng theo dự án được phân công, quản lý qua hệ thống Onboarding Buddy nội bộ. Checklist gồm các nhóm: Orientation (đọc tài liệu dự án), Access (xin quyền truy cập cần thiết), Setup (cài đặt môi trường phát triển), Codebase (hiểu cấu trúc code), Convention (quy tắc coding), và First Task/First PR (hoàn thành công việc thực tế đầu tiên).

PM (Project Manager) của dự án chịu trách nhiệm duyệt kế hoạch onboarding trước ngày nhân viên bắt đầu chính thức, đảm bảo mọi bước đã sẵn sàng (tài khoản, quyền truy cập cơ bản) trước ngày đầu tiên đi làm. Tech Lead chịu trách nhiệm theo sát tiến độ onboarding kỹ thuật trong 2 tuần đầu, có buổi 1-1 tổng kết sau khi hoàn thành PR đầu tiên.

Thời gian onboarding kỹ thuật tiêu chuẩn: 1-2 tuần cho engineer đã có kinh nghiệm, có thể kéo dài tới 3 tuần cho fresher hoặc người chuyển ngôn ngữ/tech stack mới hoàn toàn.', '0a45ddf6203ebe87feb90e145756c68b3a3d35b9a7884eac22f9e99c4bc9509c', 'pending', '', 'Mỗi nhân viên mới có 1 checklist onboarding riêng theo dự án được phân công, quản lý qua hệ thống Onboarding Buddy nội bộ. Checklist gồm các nhóm: Orientation (đọc tài liệu dự án), Access (xin quyền truy cập cần thiết), Setup (cài đặt môi trường phát triển), Codebase (hiểu cấu trúc code), Convention (quy tắc coding), và First Task/First PR (hoàn thành công việc thực tế đầu tiên).

PM (Project Manager) của dự án chịu trách nhiệm duyệt kế hoạch onboarding trước ngày nhân viên bắt đầu chính thức, đảm bảo mọi bước đã sẵn sàng (tài khoản, quyền truy cập cơ bản) trước ngày đầu tiên đi làm. Tech Lead chịu trách nhiệm theo sát tiến độ onboarding kỹ thuật trong 2 tuần đầu, có buổi 1-1 tổng kết sau khi hoàn thành PR đầu tiên.

Thời gian onboarding kỹ thuật tiêu chuẩn: 1-2 tuần cho engineer đã có kinh nghiệm, có thể kéo dài tới 3 tuần cho fresher hoặc người chuyển ngôn ngữ/tech stack mới hoàn toàn.'),
    ('Đánh giá hiệu suất'::text, 'Đánh giá hiệu suất diễn ra định kỳ 6 tháng/lần (tháng 6 và tháng 12 hàng năm), dựa trên 3 tiêu chí chính: (1) mức độ hoàn thành công việc được giao đúng deadline và chất lượng, (2) chất lượng code thể hiện qua PR review (ít bug phát sinh sau merge, code dễ đọc/dễ bảo trì), và (3) đóng góp cho team ngoài công việc cá nhân (mentoring người mới, chia sẻ kiến thức qua tech talk nội bộ, cải thiện quy trình chung).

Kết quả đánh giá ảnh hưởng trực tiếp tới xét tăng lương và thăng chức, được thông báo riêng tư qua buổi 1-1 với quản lý trực tiếp, không công khai trong bất kỳ kênh chung nào.', 4, 122, 'Đánh giá hiệu suất diễn ra định kỳ 6 tháng/lần (tháng 6 và tháng 12 hàng năm), dựa trên 3 tiêu chí chính: (1) mức độ hoàn thành công việc được giao đúng deadline và chất lượng, (2) chất lượng code thể hiện qua PR review (ít bug phát sinh sau merge, code dễ đọc/dễ bảo trì), và (3) đóng góp cho team ngoài công việc cá nhân (mentoring người mới, chia sẻ kiến thức qua tech talk nội bộ, cải thiện quy trình chung).

Kết quả đánh giá ảnh hưởng trực tiếp tới xét tăng lương và thăng chức, được thông báo riêng tư qua buổi 1-1 với quản lý trực tiếp, không công khai trong bất kỳ kênh chung nào.', '05f3e5b8764f0700fc08c13b932f05eb09160fee7abc95945d398a348a4eea0a', 'pending', '', 'Đánh giá hiệu suất diễn ra định kỳ 6 tháng/lần (tháng 6 và tháng 12 hàng năm), dựa trên 3 tiêu chí chính: (1) mức độ hoàn thành công việc được giao đúng deadline và chất lượng, (2) chất lượng code thể hiện qua PR review (ít bug phát sinh sau merge, code dễ đọc/dễ bảo trì), và (3) đóng góp cho team ngoài công việc cá nhân (mentoring người mới, chia sẻ kiến thức qua tech talk nội bộ, cải thiện quy trình chung).

Kết quả đánh giá ảnh hưởng trực tiếp tới xét tăng lương và thăng chức, được thông báo riêng tư qua buổi 1-1 với quản lý trực tiếp, không công khai trong bất kỳ kênh chung nào.'),
    ('Xin nghỉ phép'::text, 'Đăng ký nghỉ phép qua hệ thống HR nội bộ (`hr.company.com`), báo trước tối thiểu 2 ngày làm việc đối với nghỉ phép thông thường (trừ trường hợp khẩn cấp có thể báo trong ngày kèm giải thích lý do), quản lý trực tiếp duyệt trong vòng 1 ngày làm việc. Số ngày phép năm: 12 ngày/năm cho nhân viên chính thức, cộng thêm 1 ngày/năm thâm niên sau mỗi năm làm việc đủ 12 tháng (tối đa cộng thêm 5 ngày).', 5, 82, 'Đăng ký nghỉ phép qua hệ thống HR nội bộ (`hr.company.com`), báo trước tối thiểu 2 ngày làm việc đối với nghỉ phép thông thường (trừ trường hợp khẩn cấp có thể báo trong ngày kèm giải thích lý do), quản lý trực tiếp duyệt trong vòng 1 ngày làm việc. Số ngày phép năm: 12 ngày/năm cho nhân viên chính thức, cộng thêm 1 ngày/năm thâm niên sau mỗi năm làm việc đủ 12 tháng (tối đa cộng thêm 5 ngày).', '5d4ca315c35a1089f81224db78559ace900f9ebae0a7fe8e3bc9a1e9831354fe', 'pending', '', 'Đăng ký nghỉ phép qua hệ thống HR nội bộ (`hr.company.com`), báo trước tối thiểu 2 ngày làm việc đối với nghỉ phép thông thường (trừ trường hợp khẩn cấp có thể báo trong ngày kèm giải thích lý do), quản lý trực tiếp duyệt trong vòng 1 ngày làm việc. Số ngày phép năm: 12 ngày/năm cho nhân viên chính thức, cộng thêm 1 ngày/năm thâm niên sau mỗi năm làm việc đủ 12 tháng (tối đa cộng thêm 5 ngày).'),
    ('Chính sách làm thêm giờ (overtime)'::text, 'Khối kỹ thuật hạn chế làm thêm giờ thường xuyên — nếu 1 dự án liên tục cần overtime để đáp ứng deadline, đây được xem là tín hiệu cần xem lại kế hoạch/phân bổ nguồn lực, không phải điều bình thường hoá. Trường hợp cần overtime thực sự (ví dụ xử lý sự cố production khẩn cấp), được ghi nhận và có chính sách bù nghỉ tương ứng, trao đổi trực tiếp với quản lý.', 6, 76, 'Khối kỹ thuật hạn chế làm thêm giờ thường xuyên — nếu 1 dự án liên tục cần overtime để đáp ứng deadline, đây được xem là tín hiệu cần xem lại kế hoạch/phân bổ nguồn lực, không phải điều bình thường hoá. Trường hợp cần overtime thực sự (ví dụ xử lý sự cố production khẩn cấp), được ghi nhận và có chính sách bù nghỉ tương ứng, trao đổi trực tiếp với quản lý.', 'aa076bb943308c485a29df37d2a02473fa5d6a4cfcb7cc2372cdb385c49b8780', 'pending', '', 'Khối kỹ thuật hạn chế làm thêm giờ thường xuyên — nếu 1 dự án liên tục cần overtime để đáp ứng deadline, đây được xem là tín hiệu cần xem lại kế hoạch/phân bổ nguồn lực, không phải điều bình thường hoá. Trường hợp cần overtime thực sự (ví dụ xử lý sự cố production khẩn cấp), được ghi nhận và có chính sách bù nghỉ tương ứng, trao đổi trực tiếp với quản lý.'),
    ('Kênh liên hệ nội bộ quan trọng'::text, '- **HR**: hr@company.com, hoặc kênh Slack #hr-support cho câu hỏi về phép, lương, phúc lợi.
- **IT Helpdesk**: kênh Slack #it-helpdesk, xử lý vấn đề thiết bị, tài khoản, VPN.
- **Toàn công ty**: kênh Slack #general cho thông báo chung, #random cho giao lưu không liên quan công việc.', 7, 50, '- **HR**: hr@company.com, hoặc kênh Slack #hr-support cho câu hỏi về phép, lương, phúc lợi.
- **IT Helpdesk**: kênh Slack #it-helpdesk, xử lý vấn đề thiết bị, tài khoản, VPN.
- **Toàn công ty**: kênh Slack #general cho thông báo chung, #random cho giao lưu không liên quan công việc.', '71a2d69a5e0cdebbd3bdab3883239fddaba600c0dd9ac50d91a1344377270edb', 'pending', '', '- **HR**: hr@company.com, hoặc kênh Slack #hr-support cho câu hỏi về phép, lương, phúc lợi.
- **IT Helpdesk**: kênh Slack #it-helpdesk, xử lý vấn đề thiết bị, tài khoản, VPN.
- **Toàn công ty**: kênh Slack #general cho thông báo chung, #random cho giao lưu không liên quan công việc.')
) AS c(heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical);

-- POLICY: HR Policy — Chính sách nhân sự
WITH doc AS (
  INSERT INTO knowledge_documents
    (project_id, created_by_user_id, knowledge_domain, document_category, policy_category,
     source_key, category_confirmed, category_classification_status,
     title, source_url, status, created_at, updated_at)
  VALUES (
    NULL,
    (SELECT user_id FROM users WHERE email = 'hr@onboarding.dev'),
    'POLICY', NULL, 'HR_POLICY',
    'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/policy/hr-policy', true, 'CLASSIFIED',
    'HR Policy — Chính sách nhân sự', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/policy/hr-policy', 'ACTIVE', now(), now()
  )
  RETURNING document_id
),
ver AS (
  INSERT INTO document_versions
    (document_id, version_no, revision_no, embedding_model_version,
     storage_uri, checksum, status, created_at)
  SELECT document_id, 1, 1, 'pending', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/policy/hr-policy', 'e7d2f329ad1d340b5cfd2a01bab0426c51341b4eb93c1239bb1bd235a177fabb', 'ACTIVE', now() FROM doc
  RETURNING version_id
)
INSERT INTO document_chunks (version_id, heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical)
SELECT ver.version_id, c.heading, c.content, c.chunk_index, c.token_count, c.embedding_text, c.content_hash, c.embedding_model_version, c.lexical_identifiers, c.lexical_technical
FROM ver, (VALUES
    (NULL::text, '# HR Policy — Chính sách nhân sự', 0, 8, '# HR Policy — Chính sách nhân sự', '575c8b649da4e0ab782774534bc904580b8b6839ce3e50c4666c199f38909024', 'pending', '', '# HR Policy — Chính sách nhân sự'),
    ('Phạm vi áp dụng'::text, 'Áp dụng cho toàn bộ nhân viên chính thức của công ty. Nhân viên thử việc áp dụng 1 số điều khoản riêng được nêu rõ ở mục "Thử việc" bên dưới.', 1, 32, 'Áp dụng cho toàn bộ nhân viên chính thức của công ty. Nhân viên thử việc áp dụng 1 số điều khoản riêng được nêu rõ ở mục "Thử việc" bên dưới.', '3ac60d0b2ca2b41d7cc66908d1d428a29fdca874858886bdf7b9ddaa583a0056', 'pending', '', 'Áp dụng cho toàn bộ nhân viên chính thức của công ty. Nhân viên thử việc áp dụng 1 số điều khoản riêng được nêu rõ ở mục "Thử việc" bên dưới.'),
    ('Thử việc'::text, 'Thời gian thử việc tiêu chuẩn: 2 tháng đối với vị trí kỹ thuật (Engineer), 1 tháng đối với vị trí khác. Trong thời gian thử việc, nhân viên nhận 85% mức lương chính thức đã thoả thuận. Đánh giá thử việc diễn ra vào tuần cuối cùng, dựa trên: mức độ hoàn thành onboarding checklist đúng hạn, đánh giá từ Tech Lead/quản lý trực tiếp, và ít nhất 1 PR/task thực tế đã hoàn thành thành công. Kết quả thử việc thông báo chậm nhất 3 ngày trước ngày kết thúc thời gian thử việc.', 2, 96, 'Thời gian thử việc tiêu chuẩn: 2 tháng đối với vị trí kỹ thuật (Engineer), 1 tháng đối với vị trí khác. Trong thời gian thử việc, nhân viên nhận 85% mức lương chính thức đã thoả thuận. Đánh giá thử việc diễn ra vào tuần cuối cùng, dựa trên: mức độ hoàn thành onboarding checklist đúng hạn, đánh giá từ Tech Lead/quản lý trực tiếp, và ít nhất 1 PR/task thực tế đã hoàn thành thành công. Kết quả thử việc thông báo chậm nhất 3 ngày trước ngày kết thúc thời gian thử việc.', 'de848517114095969bd278843cd9f99116f7a49666a897ae79ca0f388e300a02', 'pending', '', 'Thời gian thử việc tiêu chuẩn: 2 tháng đối với vị trí kỹ thuật (Engineer), 1 tháng đối với vị trí khác. Trong thời gian thử việc, nhân viên nhận 85% mức lương chính thức đã thoả thuận. Đánh giá thử việc diễn ra vào tuần cuối cùng, dựa trên: mức độ hoàn thành onboarding checklist đúng hạn, đánh giá từ Tech Lead/quản lý trực tiếp, và ít nhất 1 PR/task thực tế đã hoàn thành thành công. Kết quả thử việc thông báo chậm nhất 3 ngày trước ngày kết thúc thời gian thử việc.'),
    ('Chế độ bảo hiểm và phúc lợi'::text, '- Bảo hiểm xã hội, y tế, thất nghiệp theo đúng quy định pháp luật hiện hành, đóng từ tháng đầu tiên ký hợp đồng chính thức (không áp dụng cho thời gian thử việc trừ khi có thoả thuận riêng).
- Bảo hiểm sức khoẻ bổ sung (bảo hiểm sức khoẻ tư nhân) cho nhân viên chính thức sau khi qua thử việc, mở rộng cho người thân (vợ/chồng, con) với mức phí công ty hỗ trợ 50%.
- Khám sức khoẻ định kỳ hàng năm, công ty chi trả toàn bộ chi phí gói khám cơ bản.
- Phụ cấp ăn trưa, gửi xe theo mức quy định của từng văn phòng (khác nhau theo khu vực địa lý do chi phí sinh hoạt khác nhau).', 3, 128, '- Bảo hiểm xã hội, y tế, thất nghiệp theo đúng quy định pháp luật hiện hành, đóng từ tháng đầu tiên ký hợp đồng chính thức (không áp dụng cho thời gian thử việc trừ khi có thoả thuận riêng).
- Bảo hiểm sức khoẻ bổ sung (bảo hiểm sức khoẻ tư nhân) cho nhân viên chính thức sau khi qua thử việc, mở rộng cho người thân (vợ/chồng, con) với mức phí công ty hỗ trợ 50%.
- Khám sức khoẻ định kỳ hàng năm, công ty chi trả toàn bộ chi phí gói khám cơ bản.
- Phụ cấp ăn trưa, gửi xe theo mức quy định của từng văn phòng (khác nhau theo khu vực địa lý do chi phí sinh hoạt khác nhau).', '030cec4f716d60ea6679a6eae2954686d83166df79390208707b5b09b4bef19d', 'pending', '', '- Bảo hiểm xã hội, y tế, thất nghiệp theo đúng quy định pháp luật hiện hành, đóng từ tháng đầu tiên ký hợp đồng chính thức (không áp dụng cho thời gian thử việc trừ khi có thoả thuận riêng).
- Bảo hiểm sức khoẻ bổ sung (bảo hiểm sức khoẻ tư nhân) cho nhân viên chính thức sau khi qua thử việc, mở rộng cho người thân (vợ/chồng, con) với mức phí công ty hỗ trợ 50%.
- Khám sức khoẻ định kỳ hàng năm, công ty chi trả toàn bộ chi phí gói khám cơ bản.
- Phụ cấp ăn trưa, gửi xe theo mức quy định của từng văn phòng (khác nhau theo khu vực địa lý do chi phí sinh hoạt khác nhau).'),
    ('Lương và tăng lương'::text, 'Lương trả vào ngày 5 hàng tháng qua chuyển khoản. Xét tăng lương định kỳ gắn liền với chu kỳ đánh giá hiệu suất 6 tháng/lần (xem Company Policy). Mức tăng lương không cố định, phụ thuộc kết quả đánh giá cá nhân và tình hình kinh doanh chung của công ty trong kỳ. Ngoài ra có cơ chế xét tăng lương đột xuất (off-cycle) cho trường hợp đặc biệt (thăng chức giữa kỳ, giữ chân nhân sự quan trọng) — do Engineering Manager/quản lý trực tiếp đề xuất lên HR và Ban điều hành phê duyệt.', 4, 97, 'Lương trả vào ngày 5 hàng tháng qua chuyển khoản. Xét tăng lương định kỳ gắn liền với chu kỳ đánh giá hiệu suất 6 tháng/lần (xem Company Policy). Mức tăng lương không cố định, phụ thuộc kết quả đánh giá cá nhân và tình hình kinh doanh chung của công ty trong kỳ. Ngoài ra có cơ chế xét tăng lương đột xuất (off-cycle) cho trường hợp đặc biệt (thăng chức giữa kỳ, giữ chân nhân sự quan trọng) — do Engineering Manager/quản lý trực tiếp đề xuất lên HR và Ban điều hành phê duyệt.', 'c12319e76d6410131a1fd8884bb588a22e12a90fac276e0406900d56f699e64e', 'pending', '', 'Lương trả vào ngày 5 hàng tháng qua chuyển khoản. Xét tăng lương định kỳ gắn liền với chu kỳ đánh giá hiệu suất 6 tháng/lần (xem Company Policy). Mức tăng lương không cố định, phụ thuộc kết quả đánh giá cá nhân và tình hình kinh doanh chung của công ty trong kỳ. Ngoài ra có cơ chế xét tăng lương đột xuất (off-cycle) cho trường hợp đặc biệt (thăng chức giữa kỳ, giữ chân nhân sự quan trọng) — do Engineering Manager/quản lý trực tiếp đề xuất lên HR và Ban điều hành phê duyệt.'),
    ('Quy trình nghỉ việc'::text, 'Nhân viên có nguyện vọng nghỉ việc cần thông báo bằng văn bản (email chính thức tới quản lý trực tiếp và HR) trước tối thiểu 30 ngày theo quy định hợp đồng lao động (45 ngày đối với vị trí quản lý cấp Lead trở lên). Trong thời gian bàn giao, cần hoàn tất: bàn giao công việc/tài liệu cho người kế nhiệm hoặc team, thu hồi toàn bộ thiết bị công ty cấp, thu hồi quyền truy cập hệ thống (GitHub, AWS, database, các công cụ nội bộ khác — IT xử lý ngay trong ngày làm việc cuối cùng).', 5, 102, 'Nhân viên có nguyện vọng nghỉ việc cần thông báo bằng văn bản (email chính thức tới quản lý trực tiếp và HR) trước tối thiểu 30 ngày theo quy định hợp đồng lao động (45 ngày đối với vị trí quản lý cấp Lead trở lên). Trong thời gian bàn giao, cần hoàn tất: bàn giao công việc/tài liệu cho người kế nhiệm hoặc team, thu hồi toàn bộ thiết bị công ty cấp, thu hồi quyền truy cập hệ thống (GitHub, AWS, database, các công cụ nội bộ khác — IT xử lý ngay trong ngày làm việc cuối cùng).', 'a70e0d62b5445d40eda93995f7345f3f4cf6e5afa824e7feb86f3def0e1a5a07', 'pending', '', 'Nhân viên có nguyện vọng nghỉ việc cần thông báo bằng văn bản (email chính thức tới quản lý trực tiếp và HR) trước tối thiểu 30 ngày theo quy định hợp đồng lao động (45 ngày đối với vị trí quản lý cấp Lead trở lên). Trong thời gian bàn giao, cần hoàn tất: bàn giao công việc/tài liệu cho người kế nhiệm hoặc team, thu hồi toàn bộ thiết bị công ty cấp, thu hồi quyền truy cập hệ thống (GitHub, AWS, database, các công cụ nội bộ khác — IT xử lý ngay trong ngày làm việc cuối cùng).'),
    ('Chính sách đào tạo và phát triển'::text, 'Công ty hỗ trợ chi phí học tập/chứng chỉ liên quan trực tiếp tới công việc (tối đa 10 triệu đồng/năm/nhân viên, cần đăng ký và được quản lý trực tiếp phê duyệt trước khi tham gia khoá học). Khuyến khích chia sẻ kiến thức nội bộ qua các buổi Tech Talk hàng tháng — nhân viên trình bày được tính là đóng góp tích cực trong đánh giá hiệu suất.', 6, 71, 'Công ty hỗ trợ chi phí học tập/chứng chỉ liên quan trực tiếp tới công việc (tối đa 10 triệu đồng/năm/nhân viên, cần đăng ký và được quản lý trực tiếp phê duyệt trước khi tham gia khoá học). Khuyến khích chia sẻ kiến thức nội bộ qua các buổi Tech Talk hàng tháng — nhân viên trình bày được tính là đóng góp tích cực trong đánh giá hiệu suất.', '8a7742ea5a05a499679709c955a2627244de90d74502bf4b22f70ef8cb911280', 'pending', '', 'Công ty hỗ trợ chi phí học tập/chứng chỉ liên quan trực tiếp tới công việc (tối đa 10 triệu đồng/năm/nhân viên, cần đăng ký và được quản lý trực tiếp phê duyệt trước khi tham gia khoá học). Khuyến khích chia sẻ kiến thức nội bộ qua các buổi Tech Talk hàng tháng — nhân viên trình bày được tính là đóng góp tích cực trong đánh giá hiệu suất.'),
    ('Bảo mật thông tin nhân sự'::text, 'Thông tin lương, đánh giá hiệu suất cá nhân là thông tin bảo mật, chỉ nhân viên đó, quản lý trực tiếp, và HR có quyền truy cập. Nghiêm cấm chia sẻ thông tin lương của đồng nghiệp (dù vô tình biết được) ra ngoài phạm vi này.', 7, 48, 'Thông tin lương, đánh giá hiệu suất cá nhân là thông tin bảo mật, chỉ nhân viên đó, quản lý trực tiếp, và HR có quyền truy cập. Nghiêm cấm chia sẻ thông tin lương của đồng nghiệp (dù vô tình biết được) ra ngoài phạm vi này.', 'b59292f2cc0da3f17ea5c9bb7831153119af2485e9009f17e42d8e95d4597eed', 'pending', '', 'Thông tin lương, đánh giá hiệu suất cá nhân là thông tin bảo mật, chỉ nhân viên đó, quản lý trực tiếp, và HR có quyền truy cập. Nghiêm cấm chia sẻ thông tin lương của đồng nghiệp (dù vô tình biết được) ra ngoài phạm vi này.'),
    ('Liên hệ HR'::text, 'Mọi câu hỏi liên quan chính sách nhân sự, liên hệ qua email hr@company.com hoặc kênh Slack #hr-support. Vấn đề nhạy cảm (khiếu nại, tranh chấp nội bộ) nên trao đổi trực tiếp/riêng tư với HR, không qua kênh chung.', 8, 40, 'Mọi câu hỏi liên quan chính sách nhân sự, liên hệ qua email hr@company.com hoặc kênh Slack #hr-support. Vấn đề nhạy cảm (khiếu nại, tranh chấp nội bộ) nên trao đổi trực tiếp/riêng tư với HR, không qua kênh chung.', '027227e7a2ee040ab65aff3b110c4cc4374f1654d8e07bf1059f9b410f784b8a', 'pending', '', 'Mọi câu hỏi liên quan chính sách nhân sự, liên hệ qua email hr@company.com hoặc kênh Slack #hr-support. Vấn đề nhạy cảm (khiếu nại, tranh chấp nội bộ) nên trao đổi trực tiếp/riêng tư với HR, không qua kênh chung.')
) AS c(heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical);

-- POLICY: Security Policy — Chính sách bảo mật chung
WITH doc AS (
  INSERT INTO knowledge_documents
    (project_id, created_by_user_id, knowledge_domain, document_category, policy_category,
     source_key, category_confirmed, category_classification_status,
     title, source_url, status, created_at, updated_at)
  VALUES (
    NULL,
    (SELECT user_id FROM users WHERE email = 'hr@onboarding.dev'),
    'POLICY', NULL, 'SECURITY_POLICY',
    'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/policy/security-policy', true, 'CLASSIFIED',
    'Security Policy — Chính sách bảo mật chung', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/policy/security-policy', 'ACTIVE', now(), now()
  )
  RETURNING document_id
),
ver AS (
  INSERT INTO document_versions
    (document_id, version_no, revision_no, embedding_model_version,
     storage_uri, checksum, status, created_at)
  SELECT document_id, 1, 1, 'pending', 'https://res.cloudinary.com/lwqx5mla/raw/upload/knowledge-documents/policy/security-policy', 'e1b1a35a7d06236f967b9b63092df876f7ee7aba65b4ef34498595285025ada9', 'ACTIVE', now() FROM doc
  RETURNING version_id
)
INSERT INTO document_chunks (version_id, heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical)
SELECT ver.version_id, c.heading, c.content, c.chunk_index, c.token_count, c.embedding_text, c.content_hash, c.embedding_model_version, c.lexical_identifiers, c.lexical_technical
FROM ver, (VALUES
    (NULL::text, '# Security Policy — Chính sách bảo mật chung', 0, 9, '# Security Policy — Chính sách bảo mật chung', '7cefd1884e2015ca3498d6c4215a24807199c834a554e27232ebc4f7eb0fbc52', 'pending', '', '# Security Policy — Chính sách bảo mật chung'),
    ('Phạm vi áp dụng'::text, 'Áp dụng cho toàn bộ nhân viên có quyền truy cập vào bất kỳ hệ thống nào của công ty (source code, database, hạ tầng cloud, công cụ nội bộ), bất kể đang tham gia dự án nào. Đây là chính sách nền tảng — mỗi dự án (PhoneShop, TourBooking, FurniStore...) có thể có thêm quy định bảo mật riêng chi tiết hơn (xem tài liệu Access & Security của từng dự án), nhưng không được thấp hơn tiêu chuẩn chung này.', 1, 82, 'Áp dụng cho toàn bộ nhân viên có quyền truy cập vào bất kỳ hệ thống nào của công ty (source code, database, hạ tầng cloud, công cụ nội bộ), bất kể đang tham gia dự án nào. Đây là chính sách nền tảng — mỗi dự án (PhoneShop, TourBooking, FurniStore...) có thể có thêm quy định bảo mật riêng chi tiết hơn (xem tài liệu Access & Security của từng dự án), nhưng không được thấp hơn tiêu chuẩn chung này.', '56eb4faa77ebff45c87e9e27fb3e889d09485c5e0742cc5ac792cbaaa6c8dc3a', 'pending', '', 'Áp dụng cho toàn bộ nhân viên có quyền truy cập vào bất kỳ hệ thống nào của công ty (source code, database, hạ tầng cloud, công cụ nội bộ), bất kể đang tham gia dự án nào. Đây là chính sách nền tảng — mỗi dự án (PhoneShop, TourBooking, FurniStore...) có thể có thêm quy định bảo mật riêng chi tiết hơn (xem tài liệu Access & Security của từng dự án), nhưng không được thấp hơn tiêu chuẩn chung này.'),
    ('Quản lý tài khoản và xác thực'::text, '- Bắt buộc bật xác thực 2 lớp (2FA/MFA) cho toàn bộ tài khoản công việc: email công ty, GitHub, AWS Console, các công cụ nội bộ có hỗ trợ. Không có ngoại lệ, kể cả tài khoản cấp thấp.
- Mật khẩu tối thiểu 12 ký tự, kết hợp chữ hoa/thường/số/ký tự đặc biệt, không dùng lại mật khẩu đã dùng cho dịch vụ cá nhân bên ngoài.
- Dùng password manager công ty cấp (1Password) để lưu trữ mọi credential liên quan công việc — nghiêm cấm lưu mật khẩu trong file text, note, hoặc gửi qua chat không mã hoá.
- Tài khoản không sử dụng quá 90 ngày tự động bị khoá, cần liên hệ IT để mở lại kèm xác minh danh tính.', 2, 128, '- Bắt buộc bật xác thực 2 lớp (2FA/MFA) cho toàn bộ tài khoản công việc: email công ty, GitHub, AWS Console, các công cụ nội bộ có hỗ trợ. Không có ngoại lệ, kể cả tài khoản cấp thấp.
- Mật khẩu tối thiểu 12 ký tự, kết hợp chữ hoa/thường/số/ký tự đặc biệt, không dùng lại mật khẩu đã dùng cho dịch vụ cá nhân bên ngoài.
- Dùng password manager công ty cấp (1Password) để lưu trữ mọi credential liên quan công việc — nghiêm cấm lưu mật khẩu trong file text, note, hoặc gửi qua chat không mã hoá.
- Tài khoản không sử dụng quá 90 ngày tự động bị khoá, cần liên hệ IT để mở lại kèm xác minh danh tính.', 'a77a9e99303962850349dffaf0267ab7b84005a983d6ce8f31efdea614567115', 'pending', '', '- Bắt buộc bật xác thực 2 lớp (2FA/MFA) cho toàn bộ tài khoản công việc: email công ty, GitHub, AWS Console, các công cụ nội bộ có hỗ trợ. Không có ngoại lệ, kể cả tài khoản cấp thấp.
- Mật khẩu tối thiểu 12 ký tự, kết hợp chữ hoa/thường/số/ký tự đặc biệt, không dùng lại mật khẩu đã dùng cho dịch vụ cá nhân bên ngoài.
- Dùng password manager công ty cấp (1Password) để lưu trữ mọi credential liên quan công việc — nghiêm cấm lưu mật khẩu trong file text, note, hoặc gửi qua chat không mã hoá.
- Tài khoản không sử dụng quá 90 ngày tự động bị khoá, cần liên hệ IT để mở lại kèm xác minh danh tính.'),
    ('Nguyên tắc phân quyền (Principle of Least Privilege)'::text, 'Mọi truy cập hệ thống chỉ cấp ở mức tối thiểu cần thiết cho công việc hiện tại, không cấp "phòng khi cần sau này". Quyền truy cập production (database, AWS Console, server) luôn hạn chế nghiêm ngặt hơn nhiều so với staging/dev, và luôn đi kèm audit log đầy đủ (ghi lại ai truy cập, khi nào, làm gì). Khi đổi vai trò/dự án, quyền truy cập cũ không còn cần thiết phải được thu hồi trong vòng 3 ngày làm việc (trách nhiệm của quản lý trực tiếp đề xuất thu hồi kịp thời, không phải tự động).', 3, 100, 'Mọi truy cập hệ thống chỉ cấp ở mức tối thiểu cần thiết cho công việc hiện tại, không cấp "phòng khi cần sau này". Quyền truy cập production (database, AWS Console, server) luôn hạn chế nghiêm ngặt hơn nhiều so với staging/dev, và luôn đi kèm audit log đầy đủ (ghi lại ai truy cập, khi nào, làm gì). Khi đổi vai trò/dự án, quyền truy cập cũ không còn cần thiết phải được thu hồi trong vòng 3 ngày làm việc (trách nhiệm của quản lý trực tiếp đề xuất thu hồi kịp thời, không phải tự động).', 'b8bb429702091366ecfee0cbb9cd078baac8cd0e5567aa87d293478035c4a3ec', 'pending', '', 'Mọi truy cập hệ thống chỉ cấp ở mức tối thiểu cần thiết cho công việc hiện tại, không cấp "phòng khi cần sau này". Quyền truy cập production (database, AWS Console, server) luôn hạn chế nghiêm ngặt hơn nhiều so với staging/dev, và luôn đi kèm audit log đầy đủ (ghi lại ai truy cập, khi nào, làm gì). Khi đổi vai trò/dự án, quyền truy cập cũ không còn cần thiết phải được thu hồi trong vòng 3 ngày làm việc (trách nhiệm của quản lý trực tiếp đề xuất thu hồi kịp thời, không phải tự động).'),
    ('Thiết bị làm việc'::text, 'Laptop công ty cấp bắt buộc cài MDM (Mobile Device Management) để IT có thể quản lý và xoá dữ liệu từ xa nếu thiết bị bị mất/thất lạc. Mã hoá ổ cứng toàn bộ (FileVault trên macOS, BitLocker trên Windows) bắt buộc bật ngay khi nhận máy. Không cài phần mềm không rõ nguồn gốc, không tắt trình diệt virus/bảo mật do IT cài sẵn.', 4, 66, 'Laptop công ty cấp bắt buộc cài MDM (Mobile Device Management) để IT có thể quản lý và xoá dữ liệu từ xa nếu thiết bị bị mất/thất lạc. Mã hoá ổ cứng toàn bộ (FileVault trên macOS, BitLocker trên Windows) bắt buộc bật ngay khi nhận máy. Không cài phần mềm không rõ nguồn gốc, không tắt trình diệt virus/bảo mật do IT cài sẵn.', '3e5907700b0f35a0e86b0773118c4ef11be1dc9197bef53639d2aed8cf5f3049', 'pending', '', 'Laptop công ty cấp bắt buộc cài MDM (Mobile Device Management) để IT có thể quản lý và xoá dữ liệu từ xa nếu thiết bị bị mất/thất lạc. Mã hoá ổ cứng toàn bộ (FileVault trên macOS, BitLocker trên Windows) bắt buộc bật ngay khi nhận máy. Không cài phần mềm không rõ nguồn gốc, không tắt trình diệt virus/bảo mật do IT cài sẵn.'),
    ('Quy tắc xử lý dữ liệu nhạy cảm'::text, '- Không bao giờ lưu dữ liệu khách hàng thật (email, số điện thoại, địa chỉ, thông tin thanh toán) trên máy cá nhân hoặc môi trường dev/staging dưới dạng dữ liệu thật — dùng dữ liệu giả lập/đã ẩn danh hoá (anonymized) cho mục đích test.
- Không chia sẻ dữ liệu nội bộ (kể cả ảnh chụp màn hình dashboard, log, cấu hình hệ thống) ra ngoài kênh nội bộ công ty dưới bất kỳ hình thức nào, kể cả với mục đích "chỉ hỏi ý kiến" trên diễn đàn công khai.
- Credential (API key, mật khẩu, token) tuyệt đối không commit vào git, không gửi qua email/chat thông thường — dùng công cụ quản lý secret chuyên dụng (AWS Secrets Manager, 1Password, biến môi trường CI/CD được mã hoá).', 5, 133, '- Không bao giờ lưu dữ liệu khách hàng thật (email, số điện thoại, địa chỉ, thông tin thanh toán) trên máy cá nhân hoặc môi trường dev/staging dưới dạng dữ liệu thật — dùng dữ liệu giả lập/đã ẩn danh hoá (anonymized) cho mục đích test.
- Không chia sẻ dữ liệu nội bộ (kể cả ảnh chụp màn hình dashboard, log, cấu hình hệ thống) ra ngoài kênh nội bộ công ty dưới bất kỳ hình thức nào, kể cả với mục đích "chỉ hỏi ý kiến" trên diễn đàn công khai.
- Credential (API key, mật khẩu, token) tuyệt đối không commit vào git, không gửi qua email/chat thông thường — dùng công cụ quản lý secret chuyên dụng (AWS Secrets Manager, 1Password, biến môi trường CI/CD được mã hoá).', 'e36910c37dfb23efd666cca3fa7e5395687d3461dfb1cd9787ffe9d64728cc67', 'pending', '', '- Không bao giờ lưu dữ liệu khách hàng thật (email, số điện thoại, địa chỉ, thông tin thanh toán) trên máy cá nhân hoặc môi trường dev/staging dưới dạng dữ liệu thật — dùng dữ liệu giả lập/đã ẩn danh hoá (anonymized) cho mục đích test.
- Không chia sẻ dữ liệu nội bộ (kể cả ảnh chụp màn hình dashboard, log, cấu hình hệ thống) ra ngoài kênh nội bộ công ty dưới bất kỳ hình thức nào, kể cả với mục đích "chỉ hỏi ý kiến" trên diễn đàn công khai.
- Credential (API key, mật khẩu, token) tuyệt đối không commit vào git, không gửi qua email/chat thông thường — dùng công cụ quản lý secret chuyên dụng (AWS Secrets Manager, 1Password, biến môi trường CI/CD được mã hoá).'),
    ('Báo cáo sự cố bảo mật'::text, 'Phát hiện lỗ hổng, rò rỉ dữ liệu, hoặc nghi ngờ truy cập trái phép — báo ngay lập tức qua kênh #security-incident, không tự ý xử lý hoặc công khai thông tin trước khi Security team xác nhận và có hướng dẫn cụ thể. Việc báo cáo sớm và trung thực được khuyến khích, kể cả khi sự cố do chính mình vô tình gây ra — công ty ưu tiên xử lý và khắc phục nhanh hơn là quy trách nhiệm, miễn không phải hành vi cố ý.

SLA phản hồi của Security team: 15 phút trong giờ hành chính, tối đa 1 giờ ngoài giờ hành chính (qua hệ thống on-call PagerDuty/Opsgenie tuỳ dự án).', 6, 118, 'Phát hiện lỗ hổng, rò rỉ dữ liệu, hoặc nghi ngờ truy cập trái phép — báo ngay lập tức qua kênh #security-incident, không tự ý xử lý hoặc công khai thông tin trước khi Security team xác nhận và có hướng dẫn cụ thể. Việc báo cáo sớm và trung thực được khuyến khích, kể cả khi sự cố do chính mình vô tình gây ra — công ty ưu tiên xử lý và khắc phục nhanh hơn là quy trách nhiệm, miễn không phải hành vi cố ý.

SLA phản hồi của Security team: 15 phút trong giờ hành chính, tối đa 1 giờ ngoài giờ hành chính (qua hệ thống on-call PagerDuty/Opsgenie tuỳ dự án).', '45e11e838321d71f9e2172e8df9039fd630311475b98d057a5242a219bfdbefc', 'pending', '', 'Phát hiện lỗ hổng, rò rỉ dữ liệu, hoặc nghi ngờ truy cập trái phép — báo ngay lập tức qua kênh #security-incident, không tự ý xử lý hoặc công khai thông tin trước khi Security team xác nhận và có hướng dẫn cụ thể. Việc báo cáo sớm và trung thực được khuyến khích, kể cả khi sự cố do chính mình vô tình gây ra — công ty ưu tiên xử lý và khắc phục nhanh hơn là quy trách nhiệm, miễn không phải hành vi cố ý.

SLA phản hồi của Security team: 15 phút trong giờ hành chính, tối đa 1 giờ ngoài giờ hành chính (qua hệ thống on-call PagerDuty/Opsgenie tuỳ dự án).'),
    ('Truy cập hệ thống production'::text, 'Chỉ Lead/PM (hoặc engineer đang trong ca on-call theo lịch) được duyệt quyền truy cập production, và mọi truy cập đều có audit log đầy đủ, lưu trữ tối thiểu 1 năm. Engineer thường chỉ được cấp quyền truy cập production tạm thời (time-boxed access, tự động thu hồi sau khoảng thời gian xác định, thường 8 giờ) khi cần debug sự cố khẩn cấp, và phải có xác nhận từ Tech Lead hoặc Engineering Manager trước khi cấp.', 7, 79, 'Chỉ Lead/PM (hoặc engineer đang trong ca on-call theo lịch) được duyệt quyền truy cập production, và mọi truy cập đều có audit log đầy đủ, lưu trữ tối thiểu 1 năm. Engineer thường chỉ được cấp quyền truy cập production tạm thời (time-boxed access, tự động thu hồi sau khoảng thời gian xác định, thường 8 giờ) khi cần debug sự cố khẩn cấp, và phải có xác nhận từ Tech Lead hoặc Engineering Manager trước khi cấp.', '6febc98ad63f8652920abe06235a1d88635de29780e0a7df342945bb04bdd892', 'pending', '', 'Chỉ Lead/PM (hoặc engineer đang trong ca on-call theo lịch) được duyệt quyền truy cập production, và mọi truy cập đều có audit log đầy đủ, lưu trữ tối thiểu 1 năm. Engineer thường chỉ được cấp quyền truy cập production tạm thời (time-boxed access, tự động thu hồi sau khoảng thời gian xác định, thường 8 giờ) khi cần debug sự cố khẩn cấp, và phải có xác nhận từ Tech Lead hoặc Engineering Manager trước khi cấp.'),
    ('Đào tạo bảo mật định kỳ'::text, 'Toàn bộ nhân viên kỹ thuật tham gia buổi đào tạo bảo mật cơ bản (nhận diện phishing, quy tắc xử lý dữ liệu, quy trình báo cáo sự cố) trong tuần đầu onboarding, và khoá refresh hàng năm. Security team tổ chức diễn tập phishing giả lập định kỳ (không báo trước) để đánh giá mức độ nhận thức của nhân viên — đây không phải để "bắt lỗi" cá nhân mà để cải thiện đào tạo nếu tỷ lệ mắc bẫy còn cao.', 8, 85, 'Toàn bộ nhân viên kỹ thuật tham gia buổi đào tạo bảo mật cơ bản (nhận diện phishing, quy tắc xử lý dữ liệu, quy trình báo cáo sự cố) trong tuần đầu onboarding, và khoá refresh hàng năm. Security team tổ chức diễn tập phishing giả lập định kỳ (không báo trước) để đánh giá mức độ nhận thức của nhân viên — đây không phải để "bắt lỗi" cá nhân mà để cải thiện đào tạo nếu tỷ lệ mắc bẫy còn cao.', 'ff0b9fa458dd97ff95fb8a802db09885b19029200ff80eb732317506e581e047', 'pending', '', 'Toàn bộ nhân viên kỹ thuật tham gia buổi đào tạo bảo mật cơ bản (nhận diện phishing, quy tắc xử lý dữ liệu, quy trình báo cáo sự cố) trong tuần đầu onboarding, và khoá refresh hàng năm. Security team tổ chức diễn tập phishing giả lập định kỳ (không báo trước) để đánh giá mức độ nhận thức của nhân viên — đây không phải để "bắt lỗi" cá nhân mà để cải thiện đào tạo nếu tỷ lệ mắc bẫy còn cao.')
) AS c(heading, content, chunk_index, token_count, embedding_text, content_hash, embedding_model_version, lexical_identifiers, lexical_technical);

COMMIT;