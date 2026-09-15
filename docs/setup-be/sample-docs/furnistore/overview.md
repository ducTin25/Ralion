# FurniStore — Overview

## Giới thiệu chung
FurniStore là hệ thống backend cho cửa hàng nội thất trực tuyến, bán bàn ghế, giường tủ, sofa, và đồ trang trí nhà cửa. Dự án khởi động tháng 8/2024 nhằm số hoá kênh bán hàng của chuỗi 12 showroom nội thất đã hoạt động offline nhiều năm, chính thức lên production tháng 2/2025. Điểm đặc thù lớn nhất so với các hệ thống thương mại điện tử thông thường (như PhoneShop): sản phẩm có **kích thước lớn, cồng kềnh, cần tính phí vận chuyển theo khu vực và khối lượng thực tế**, đồng thời phần lớn đơn hàng cần **dịch vụ giao hàng + lắp đặt tận nơi** thay vì chỉ giao bưu kiện thông thường.

## Bối cảnh kinh doanh
Ngành nội thất có đặc thù: giá trị đơn hàng trung bình cao (trung bình 4.2 triệu đồng/đơn, so với ~2.5 triệu của ngành điện thoại), nhưng tần suất mua thấp hơn nhiều và quyết định mua thường cần thời gian cân nhắc lâu hơn (khách hay xem sản phẩm nhiều lần trước khi quyết định, tỷ lệ chuyển đổi từ xem sang mua chỉ khoảng 1.2%, thấp hơn đáng kể so với ngành bán lẻ điện tử). Chiến lược khác biệt hoá: cho phép xem trước sản phẩm dạng 3D/AR ngay trên web (đã triển khai cho ~15% sản phẩm chủ lực), và cam kết thời gian giao hàng rõ ràng theo từng khu vực thay vì ước lượng chung chung.

## Trạng thái vận hành hiện tại
| Chỉ số | Giá trị |
|---|---|
| Đơn hàng trung bình/ngày | ~180 đơn ngày thường, ~600 đơn dịp khuyến mãi lớn (giữa năm, cuối năm) |
| Giá trị đơn hàng trung bình | ~4.2 triệu đồng |
| Uptime SLA | 99.5% cam kết (thấp hơn PhoneShop/TourBook vì hệ thống mới, ít traffic hơn nên rủi ro thấp hơn nếu có downtime ngắn), thực tế đạt 99.7% |
| Số khu vực tính phí ship | 63 tỉnh/thành, chia thành 5 vùng giá (nội thành, ngoại thành, tỉnh lân cận, miền Trung/Tây Nguyên, miền Nam xa) |
| Tỷ lệ đơn cần lắp đặt tận nơi | ~65% tổng số đơn (chủ yếu tủ, giường, sofa lớn) |

## Mục tiêu kinh doanh chi tiết
- Bán nội thất online kèm xem trước 3D cho một số sản phẩm chủ lực, mở rộng dần độ phủ 3D lên 40% catalog trong năm 2025.
- Tính phí ship chính xác theo khối lượng/kích thước thực tế và khoảng cách, tránh tình trạng báo giá thấp lúc đặt hàng rồi phát sinh thêm phí khi giao (nguyên nhân phổ biến gây khiếu nại ở mô hình cũ khi còn bán chủ yếu qua điện thoại/Zalo).
- Cho phép khách đặt lịch giao hàng + lắp đặt theo khung giờ cụ thể (sáng/chiều/tối), giảm tỷ lệ giao hàng thất bại do khách không có nhà.
- Tích hợp dần với 12 showroom offline để đồng bộ tồn kho, cho phép khách đặt online, nhận tại showroom gần nhất (roadmap Q4/2025, hiện chưa triển khai).

## Người dùng chính
- **Khách hàng mua nội thất**: quyết định mua thường kéo dài (trung bình 5-7 ngày từ lần xem đầu tiên tới lúc đặt hàng), hay so sánh nhiều mẫu, quan tâm nhiều tới chính sách đổi trả và bảo hành (nội thất thường bảo hành 12-24 tháng tuỳ loại).
- **Đội giao hàng/lắp đặt**: dùng app riêng (Delivery App, React Native) để xem lịch giao hàng trong ngày, xác nhận hoàn thành kèm ảnh chụp sau khi lắp đặt (yêu cầu bắt buộc để đóng đơn, tránh tranh chấp sau này).
- **Quản lý cửa hàng/showroom**: quản lý catalog, giá, khuyến mãi theo mùa, theo dõi tồn kho từng showroom qua Admin Portal.
- **Đội chăm sóc khách hàng**: xử lý khiếu nại liên quan giao hàng trễ, sản phẩm lỗi/vỡ khi vận chuyển (tỷ lệ ~2.1% đơn hàng, đang là ưu tiên cải thiện qua việc chuẩn hoá quy trình đóng gói với đối tác vận chuyển).

## Phạm vi hiện tại (đã lên production)
Catalog đầy đủ với ảnh + 3D cho sản phẩm chủ lực, giỏ hàng, tính phí ship theo khu vực (bảng giá cố định theo tỉnh/thành kết hợp khối lượng ước tính), đặt lịch giao hàng theo khung giờ (thủ công, nhân viên điều phối xác nhận qua điện thoại chứ chưa tự động hoàn toàn), thanh toán online + COD (COD giới hạn dưới 5 triệu đồng do rủi ro với đơn giá trị cao).

## Roadmap sắp tới
- **Q3/2025**: Tự động hoá xác nhận lịch giao hàng (hiện vẫn cần nhân viên gọi điện xác nhận, mục tiêu giảm xuống chỉ cần xác nhận qua SMS/app cho phần lớn trường hợp).
- **Q4/2025**: Tích hợp tồn kho với 12 showroom offline, hỗ trợ mô hình "đặt online, nhận tại showroom".
- **Q4/2025**: Tối ưu thuật toán tính phí ship — hiện dùng bảng giá cố định khá thô, muốn chuyển sang tính theo API thực tế của đối tác vận chuyển để chính xác hơn và cạnh tranh hơn về giá cho khách ở khu vực gần kho.
- **2026**: Mở rộng AR (Augmented Reality) cho phép khách "đặt thử" sản phẩm vào không gian phòng thật qua camera điện thoại — đang trong giai đoạn nghiên cứu khả thi.

## Sự cố đáng chú ý gần đây (để tránh lặp lại)
- **Tháng 04/2025**: Job tính phí ship bất đồng bộ (BullMQ) bị treo do 1 job gọi API đối tác vận chuyển timeout nhưng không có cơ chế timeout ở tầng code, khiến job chiếm giữ worker vô thời hạn, dần dần làm nghẽn toàn bộ queue tính phí ship cho các đơn khác trong 4 giờ. Đã bổ sung timeout cứng (10 giây) cho mọi HTTP call ra ngoài, kèm circuit breaker.
- **Tháng 06/2025**: MongoDB (lưu lịch giao hàng) gặp sự cố replica set failover không mượt, gây gián đoạn ghi dữ liệu lịch giao hàng khoảng 8 phút, một số đơn đặt lịch trong thời gian đó bị lỗi phải đặt lại. Đã nâng cấp cấu hình MongoDB Atlas lên tier cao hơn có failover nhanh hơn và bổ sung retry logic ở tầng ứng dụng.

## Liên hệ đội ngũ
- **Kênh Slack chính**: #furnistore-backend, #furnistore-ops (vấn đề vận hành giao hàng/showroom), #furnistore-incidents.
- Team nhỏ hơn 2 dự án còn lại (5 kỹ sư backend), Tech Lead kiêm luôn vai trò DevOps chính cho service này.
