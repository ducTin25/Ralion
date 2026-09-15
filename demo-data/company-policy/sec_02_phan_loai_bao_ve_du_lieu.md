# Chính sách Phân loại và Bảo vệ Dữ liệu

- **Mã tài liệu:** SEC-POL-002
- **Phiên bản:** 2.6 — Ngày hiệu lực: 01/01/2026
- **Bộ phận ban hành:** Phòng An toàn Thông tin
- **Phạm vi áp dụng:** Mọi dữ liệu do công ty tạo ra, thu thập, lưu trữ, xử lý — mọi định dạng, mọi nơi lưu
- **Tài liệu tham chiếu:** ISO/IEC 27001:2022; **Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15** (hiệu lực 01/01/2026); **Nghị định 356/2025/NĐ-CP** và văn bản hướng dẫn còn hiệu lực

## 1. Mục đích

Xác lập cách phân loại dữ liệu theo mức nhạy cảm và quy tắc xử lý tương ứng ở từng khâu: tạo, lưu trữ, chia sẻ, truyền, và hủy.

## 2. Bốn mức phân loại

| Mức | Định nghĩa | Ví dụ |
|---|---|---|
| **Public** | Công bố công khai không gây hại | Tài liệu marketing, thông cáo báo chí, tin tuyển dụng |
| **Internal** | Dùng trong nội bộ; lộ ra ngoài gây bất tiện nhưng thiệt hại thấp | Quy trình nội bộ, tài liệu dự án chung, sơ đồ tổ chức |
| **Confidential** | Lộ gây thiệt hại đáng kể về kinh doanh/pháp lý | Hợp đồng, dữ liệu khách hàng, mã nguồn sản phẩm, kế hoạch kinh doanh, tài liệu đấu thầu |
| **Restricted** | Lộ gây thiệt hại nghiêm trọng; kiểm soát chặt nhất | Lương thưởng, dữ liệu cá nhân nhạy cảm, secret/API key, thông tin M&A, dữ liệu điều tra |

Nguyên tắc: **không chắc mức nào → coi là Confidential** và hỏi Security hoặc chủ dữ liệu.

## 3. Quy tắc xử lý theo mức

### 3.1. Lưu trữ

| Mức | Nơi lưu cho phép | Mã hóa |
|---|---|---|
| Public | Bất kỳ | Không bắt buộc |
| Internal | Hệ thống công ty (drive nội bộ, wiki, repo nội bộ) | Khuyến nghị |
| Confidential | Hệ thống công ty có kiểm soát quyền theo SEC-POL-001 | Bắt buộc khi lưu (at-rest) |
| Restricted | Kho chuyên biệt được chỉ định, quyền theo cá nhân | Bắt buộc at-rest + kiểm soát khóa riêng |

- Cấm lưu dữ liệu Confidential trở lên trên: thiết bị cá nhân không MDM, USB không mã hóa, dịch vụ lưu trữ cá nhân (Google Drive cá nhân, Dropbox cá nhân...).

### 3.2. Chia sẻ và truyền

- Chia sẻ nội bộ: qua hệ thống công ty với quyền cụ thể (theo người/nhóm), hạn chế "anyone with the link" cho Confidential trở lên.
- Gửi ra ngoài: Confidential cần phê duyệt của chủ dữ liệu + NDA với bên nhận; Restricted cần thêm phê duyệt Security, gửi qua kênh mã hóa đầu-cuối hoặc file mã hóa với mật khẩu truyền riêng kênh khác.
- Mọi truyền dữ liệu qua mạng dùng TLS 1.2 trở lên; cấm gửi Confidential qua kênh chat cá nhân (Zalo/Messenger cá nhân...).

### 3.3. Hiển thị và in ấn

- Tài liệu Confidential trở lên ghi nhãn mức bảo mật ở đầu trang.
- In tài liệu Restricted: hạn chế tối đa, lấy ngay tại máy in, hủy bằng máy hủy tài liệu sau khi dùng.

### 3.4. Lưu trữ hồ sơ và hủy

- Thời hạn lưu theo quy định pháp luật và lịch lưu trữ nội bộ (hồ sơ kế toán 10 năm, hồ sơ nhân sự theo luật lao động...).
- Hủy dữ liệu số: xóa an toàn (secure wipe); hủy thiết bị lưu trữ hỏng bằng phá hủy vật lý có biên bản.

## 4. Dữ liệu cá nhân

- Xử lý dữ liệu cá nhân theo **Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15**, Nghị định 356/2025/NĐ-CP và văn bản hướng dẫn còn hiệu lực: xác định rõ mục đích, phạm vi, cơ sở xử lý và chỉ thu thập dữ liệu cần thiết cho mục đích đã xác định.
- Dữ liệu cá nhân nhạy cảm (sức khỏe, tài chính, sinh trắc học) xếp mức **Restricted**.
- Chuyển dữ liệu cá nhân ra nước ngoài hoặc cho bên thứ ba xử lý: phải qua đánh giá của Security và Pháp chế trước khi thực hiện.
- Yêu cầu của chủ thể dữ liệu (xem, sửa, xóa): chuyển đầu mối bảo vệ dữ liệu cá nhân xử lý trong thời hạn luật định.

## 5. Dữ liệu trong phát triển phần mềm

- **Cấm dùng dữ liệu production thật** trong môi trường dev/test; dùng dữ liệu tổng hợp (synthetic) hoặc đã ẩn danh hóa/mask.
- Log ứng dụng không được ghi dữ liệu Restricted (mật khẩu, token, số thẻ, dữ liệu cá nhân nhạy cảm); rà soát log filter khi review code.
- Bản sao lưu (backup) mã hóa như dữ liệu gốc, kiểm tra khôi phục định kỳ 6 tháng/lần.

## 6. Ngăn ngừa thất thoát dữ liệu (DLP)

- Hệ thống DLP giám sát các kênh ra: email ra ngoài, upload web, thiết bị ngoại vi; cảnh báo hoặc chặn theo mức phân loại.
- Cảnh báo DLP sai (false positive): nhân viên phản hồi qua ticket Security để tinh chỉnh, SLA 2 ngày làm việc.
- Cố tình vượt DLP (nén đổi tên file, mã hóa để né quét) được xem là vi phạm nghiêm trọng.

## 7. Trách nhiệm

- **Chủ dữ liệu (Data Owner):** gán mức phân loại, quyết định ai được truy cập, rà soát định kỳ.
- **Người sử dụng:** xử lý đúng quy tắc theo nhãn; báo ngay khi phát hiện dữ liệu để sai chỗ hoặc chia sẻ sai.
- **Security:** giám sát, DLP, đánh giá rủi ro và điều tra sự cố dữ liệu.

## 8. Kênh hỗ trợ và SLA

| Loại yêu cầu | SLA |
|---|---|
| Tư vấn phân loại dữ liệu | 2 ngày làm việc |
| Phê duyệt chia sẻ dữ liệu ra ngoài | 3 ngày làm việc (Restricted: 5 ngày) |
| Phản hồi cảnh báo DLP | 2 ngày làm việc |
| Báo dữ liệu chia sẻ sai / lộ dữ liệu | Khẩn cấp — theo SEC-POL-004, trong 1 giờ |

**Từ khóa định tuyến về Security:** dữ liệu, phân loại, confidential, restricted, lộ dữ liệu, chia sẻ file, dữ liệu cá nhân, DLP, mã hóa, backup, dữ liệu khách hàng, gửi ra ngoài, USB, drive cá nhân, ẩn danh hóa.


## 9. Data lifecycle

Mọi tập dữ liệu quan trọng cần owner và mục đích sử dụng rõ ràng. Vòng đời gồm: **collect/create → classify → use → share → retain/archive → delete/destroy**. Control áp dụng theo mức nhạy cảm và bối cảnh xử lý, không chỉ theo nơi file đang nằm.

## 10. Personal data governance

Khi xử lý dữ liệu cá nhân, đơn vị nghiệp vụ cần xác định tối thiểu: nhóm chủ thể dữ liệu, trường dữ liệu, mục đích, cơ sở xử lý, hệ thống lưu, bên nhận/chia sẻ, thời hạn lưu và biện pháp bảo vệ. Thu thập “để sau này có thể cần” không phải mục đích đủ rõ.

Dữ liệu cá nhân nhạy cảm được xử lý ở mức kiểm soát **Restricted** trừ khi Legal/DPO xác định yêu cầu cao hơn. Dữ liệu của trẻ em hoặc nhóm cần bảo vệ đặc biệt phải có kiểm soát phù hợp pháp luật hiện hành.

## 11. Data subject requests

Yêu cầu liên quan dữ liệu cá nhân (truy cập/xem, chỉnh sửa, hạn chế, phản đối, xóa hoặc quyền khác theo luật) phải chuyển đầu mối Privacy/DPO. Nhân viên không tự xóa hoặc xuất dữ liệu từ hệ thống để trả lời yêu cầu nếu chưa xác minh danh tính và phạm vi pháp lý.

## 12. Third party và cross-border

Trước khi chia sẻ dữ liệu cá nhân/Confidential cho vendor hoặc chuyển xử lý ra ngoài phạm vi đã phê duyệt, owner phối hợp Security/Legal đánh giá hợp đồng, mục đích, subprocessor, location, retention, deletion, incident notification và biện pháp truyền an toàn. DPA/điều khoản bảo vệ dữ liệu được áp dụng khi cần.

## 13. Data minimization trong kỹ thuật

- API chỉ trả field cần cho consumer.
- Analytics/dev dùng dữ liệu synthetic, masked hoặc de-identified khi có thể.
- Log/trace không ghi secret, auth token, full payment data hoặc dữ liệu nhạy cảm không cần thiết.
- Export CSV/report chứa dữ liệu nhiều người phải có owner và thời hạn sử dụng; xóa sau khi hoàn tất mục đích.

## 14. Labeling và metadata

Hệ thống quản lý tài liệu nên lưu classification dưới dạng metadata để hỗ trợ DLP/ACL. Nếu file không có nhãn nhưng nội dung rõ ràng nhạy cảm, người dùng phải xử lý theo **mức thực tế cao hơn**, không dựa vào việc thiếu label để hạ mức bảo vệ.

## 15. Retention schedule

Retention do Data Owner phối hợp Legal/Privacy xác định theo loại hồ sơ và mục đích. “Lưu vô thời hạn để tiện tra cứu” không được dùng làm mặc định. Legal hold có thể tạm dừng việc xóa theo lịch nhưng phải có phạm vi và owner.

## 16. Privacy/security incident

Gửi nhầm, public link, mất thiết bị, upload nhầm vào AI/SaaS, hoặc data export bất thường đều có thể là data incident. Người phát hiện báo trong 1 giờ theo SEC-POL-004; không chờ xác nhận chắc chắn đã có người ngoài đọc dữ liệu.

## 17. RAG/AI

Hệ thống RAG phải lọc ACL **trước retrieval**, không chỉ ẩn citation sau generation. Chunk/index/embedding của tài liệu Restricted phải được bảo vệ tương xứng dữ liệu gốc. Log prompt/response cũng phải được phân loại theo nội dung thực tế.
