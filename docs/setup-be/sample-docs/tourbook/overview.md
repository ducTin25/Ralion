# TourBooking Service — Overview

## Giới thiệu chung
TourBooking Service là hệ thống backend trung tâm cho nền tảng đặt tour du lịch trực tuyến, kết nối khách hàng cá nhân với mạng lưới đối tác lữ hành (hiện có 42 đối tác đang hoạt động, từ công ty lữ hành lớn tới các đơn vị tour địa phương nhỏ). Dự án bắt đầu phát triển từ tháng 6/2024, chính thức lên production tháng 1/2025, hiện đang ở giai đoạn mở rộng nhanh với mục tiêu tăng gấp đôi số lượng tour niêm yết trong năm 2025.

Khác với các nền tảng OTA (Online Travel Agency) lớn chỉ làm trung gian đặt phòng khách sạn/vé máy bay, TourBooking tập trung riêng vào **tour trọn gói** (bao gồm di chuyển, lưu trú, ăn uống, hướng dẫn viên) — đây là mảng có biên lợi nhuận tốt hơn nhưng vận hành phức tạp hơn nhiều do phải quản lý lịch khởi hành, số chỗ giới hạn, và phối hợp với đối tác lữ hành theo thời gian thực.

## Bối cảnh kinh doanh
Ngành du lịch Việt Nam phục hồi mạnh sau giai đoạn khó khăn, nhu cầu đặt tour online tăng trưởng ổn định ~25%/năm theo báo cáo thị trường nội bộ. Điểm khác biệt cạnh tranh của TourBooking: (1) đảm bảo giá tốt nhất qua đàm phán trực tiếp với đối tác (không qua trung gian), (2) chính sách huỷ/đổi lịch linh hoạt hơn thị trường (hoàn 80% nếu huỷ trước 7 ngày, so với mức thông thường 50%), (3) Partner Portal cho phép đối tác tự quản lý tour, giảm thời gian onboarding đối tác mới từ 2 tuần xuống còn 2-3 ngày.

## Trạng thái vận hành hiện tại
| Chỉ số | Giá trị |
|---|---|
| Số đối tác lữ hành đang hoạt động | 42 |
| Số tour đang niêm yết | ~680 tour, ~2.100 lịch khởi hành (departure) |
| Booking trung bình/ngày | ~85 booking ngày thường, ~400 booking dịp lễ/Tết |
| Uptime SLA | 99.9% cam kết, thực tế 99.87% quý gần nhất (thấp hơn mục tiêu do 1 sự cố Elasticsearch tháng 4/2025) |
| Latency tìm kiếm tour (p95) | 380ms |
| Tỷ lệ booking bị huỷ do hết chỗ (double booking) | 0.3% (đã giảm đáng kể sau khi fix cơ chế giữ chỗ, xem phần sự cố) |

## Mục tiêu kinh doanh chi tiết
- Cho phép khách hàng tìm và đặt tour theo điểm đến, ngày khởi hành, khoảng giá, với kết quả tìm kiếm trả về dưới 500ms ở p95.
- Quản lý chính xác số chỗ còn lại theo từng lịch khởi hành, tuyệt đối tránh overbooking (đây là rủi ro uy tín nghiêm trọng nhất — khách đã thanh toán nhưng không có chỗ).
- Cho phép đối tác lữ hành tự đăng tour và quản lý lịch trình qua Partner Portal riêng, giảm tải cho đội vận hành nội bộ.
- Mở rộng từ 42 lên 80 đối tác trong năm 2025, tăng số tour niêm yết lên gấp đôi.

## Người dùng chính
- **Khách hàng đặt tour** (qua web/app): phân khúc chính 28-45 tuổi, có xu hướng đặt tour theo nhóm (trung bình 2.8 người/booking), đặt trước trung bình 3-4 tuần cho tour trong nước, 2-3 tháng cho tour nước ngoài.
- **Đối tác lữ hành**: đăng nhập Partner Portal riêng (`partner.tourbook.vn`), tự quản lý danh sách tour, lịch khởi hành, giá, số chỗ. Nhận thông báo real-time khi có booking mới.
- **Nhân viên chăm sóc khách hàng**: xử lý yêu cầu huỷ/đổi lịch, khiếu nại, hỗ trợ qua hotline và live chat, dùng Admin Portal nội bộ.
- **Đội vận hành/kinh doanh**: theo dõi báo cáo doanh thu theo đối tác, đàm phán hoa hồng, duyệt đối tác mới tham gia nền tảng.

## Phạm vi hiện tại (đã lên production)
Tìm kiếm tour theo nhiều tiêu chí, đặt chỗ với cơ chế giữ chỗ tạm thời, thanh toán online qua VNPay/thẻ quốc tế, xác nhận qua email, chính sách huỷ/hoàn tiền tự động theo % dựa trên thời gian huỷ trước ngày khởi hành, Partner Portal đầy đủ cho đối tác tự quản lý.

## Roadmap sắp tới
- **Q3/2025**: Tính năng chat trực tiếp giữa khách hàng và đối tác lữ hành trước khi đặt tour (đang thiết kế, cân nhắc dùng dịch vụ chat bên thứ 3 thay vì tự xây).
- **Q3/2025**: Hệ thống đánh giá/review sau tour, ảnh hưởng tới thứ hạng hiển thị tour trong kết quả tìm kiếm.
- **Q4/2025**: Mở rộng thanh toán trả góp cho tour giá trị cao (trên 20 triệu), tương tự mô hình PhoneShop đã áp dụng.
- **2026**: Đánh giá mở rộng sang thị trường tour quốc tế (hiện chỉ có tour trong nước và một số tour nước ngoài do đối tác Việt Nam tổ chức).

## Sự cố đáng chú ý gần đây (để tránh lặp lại)
- **Tháng 02/2025**: Double booking xảy ra khi 2 khách đặt cùng lúc chỗ cuối cùng của 1 lịch khởi hành hot (tour Sapa dịp cuối tuần), do cơ chế giữ chỗ ban đầu chỉ dùng optimistic lock ở tầng ứng dụng, không đủ chặt khi tải cao. Đã fix bằng Redis distributed lock kết hợp TTL 15 phút cho reservation (chi tiết xem `architecture.md`). Đã liên hệ khách hàng bị ảnh hưởng, đền bù voucher theo chính sách công ty.
- **Tháng 04/2025**: Elasticsearch cluster bị chậm nghiêm trọng (latency tăng từ 200ms lên hơn 5 giây) do 1 query aggregation không tối ưu được thêm vào lúc release tính năng lọc theo "tour phù hợp gia đình", gây quá tải cluster trong giờ cao điểm 2 tiếng. Đã rollback ngay và tối ưu lại query trước khi release lại, đồng thời bổ sung alert riêng cho Elasticsearch cluster health.
- **Tháng 06/2025**: 1 đối tác lữ hành cập nhật sai giá tour qua Partner Portal (thiếu 1 số 0, giá 5 triệu thành 500 nghìn), hệ thống cho phép booking với giá sai trong 20 phút trước khi đối tác phát hiện. Đã bổ sung validation cảnh báo khi giá thay đổi bất thường (>50% so với giá trước đó) yêu cầu xác nhận 2 bước từ đối tác.

## Liên hệ đội ngũ
- **Kênh Slack chính**: #tourbook-backend (thảo luận kỹ thuật hàng ngày), #tourbook-partners (vấn đề liên quan tích hợp đối tác), #tourbook-incidents (chỉ dùng khi có sự cố production).
- **Tech Lead**: chịu trách nhiệm kiến trúc, review PR quan trọng, quyết định kỹ thuật lớn.
