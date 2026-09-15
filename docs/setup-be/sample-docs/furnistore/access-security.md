# FurniStore — Access & Security

## Đặc thù bảo mật của FurniStore
Ngoài API cho khách hàng thông thường, FurniStore còn có **Delivery App** (dùng bởi đội giao hàng/lắp đặt, không phải nhân viên văn phòng) truy cập API qua thiết bị di động ngoài hiện trường — đây là nhóm người dùng có rủi ro thiết bị bị mất/thất lạc cao hơn nhân viên văn phòng thông thường, cần cân nhắc riêng về thời hạn token và khả năng thu hồi truy cập nhanh.

## Xin quyền truy cập
| Hệ thống | Cách xin | Ai duyệt | Thời gian xử lý |
|---|---|---|---|
| Repo GitHub (team `furnistore-backend`) | PM thêm qua GitHub Org settings | PM | Trong ngày làm việc đầu |
| MongoDB Atlas (staging) | Xin qua IT, chỉ cấp quyền read cho engineer mới, quyền write cấp sau khi quen hệ thống (thường sau 2-3 tuần) | Tech Lead | 1 ngày làm việc |
| Render Dashboard | Chỉ PM và Tech Lead có quyền deploy production, engineer thường chỉ xem log qua Render Dashboard (read-only) | Tech Lead | 1 ngày làm việc |
| Tài khoản test Delivery App | Tạo qua script seed riêng, không dùng tài khoản đội giao hàng thật để test | Tự làm | Ngay lập tức |
| 1Password vault "FurniStore Dev" | Chứa credential dev/staging (API key đối tác vận chuyển sandbox...) | Tech Lead thêm vào vault | Trong ngày |

## Quy tắc bảo mật
- Toàn bộ input từ client phải validate bằng `zod` schema trước khi vào business logic — không tin dữ liệu client gửi lên dưới bất kỳ hình thức nào, kể cả từ Delivery App chính chủ (thiết bị có thể bị jailbreak/root, request có thể bị can thiệp).
- Token đăng nhập Delivery App có thời hạn ngắn hơn đáng kể so với web/app khách hàng (TTL 8 giờ, tương ứng ca làm việc, thay vì 30 ngày) — giảm thiểu rủi ro nếu thiết bị bị mất, đội vận hành có thể yêu cầu thu hồi ngay qua Admin Portal (revoke token tức thì, không cần đợi hết hạn).
- API đối tác vận chuyển (tính phí ship) dùng API key lưu trong biến môi trường ở Render (Render Secret, không phải file `.env` commit vào repo), xoay vòng (rotate) mỗi 6 tháng theo lịch, có nhắc nhở tự động qua calendar nội bộ team.
- Rate limit 60 request/phút/IP cho endpoint public, riêng `/api/checkout` giới hạn chặt hơn (10 req/phút) để chống spam đặt hàng ảo — đã từng bị 1 đợt spam đặt hàng ảo (bot test) trước khi có rate limit này, gây nhiễu số liệu báo cáo kinh doanh trong vài giờ.
- Ảnh xác nhận lắp đặt do đội giao hàng upload qua Delivery App lưu trên Cloudinary với access mode "authenticated" (không public URL trực tiếp), chỉ truy cập được qua signed URL có thời hạn ngắn (1 giờ) sinh bởi backend — tránh lộ hình ảnh nhà khách hàng nếu URL bị lộ ra ngoài.

## Compliance
Địa chỉ giao hàng và số điện thoại khách hàng là dữ liệu nhạy cảm cần bảo vệ theo Nghị định 13/2023/NĐ-CP — không chia sẻ trực tiếp cho đối tác vận chuyển ngoài phạm vi cần thiết (chỉ gửi thông tin cần cho việc giao hàng cụ thể đó, không gửi toàn bộ lịch sử đơn hàng của khách).

## Liên hệ khi có sự cố bảo mật
Báo Security team qua #security-incident, đính kèm log liên quan nếu có. Với sự cố liên quan thiết bị Delivery App bị mất/thất lạc, báo ngay cho Tech Lead để thu hồi token ngay lập tức qua Admin Portal, không chờ quy trình báo cáo đầy đủ mới xử lý.
