# Chính sách Phần mềm và Bản quyền (License)

- **Mã tài liệu:** IT-POL-004
- **Phiên bản:** 2.3 — Ngày hiệu lực: 01/01/2026
- **Bộ phận ban hành:** Phòng CNTT
- **Phạm vi áp dụng:** Mọi phần mềm cài đặt/sử dụng trên thiết bị công ty và cho công việc công ty
- **Tài liệu liên quan:** SEC-POL-005 (Sử dụng AI và dịch vụ bên ngoài), IT-POL-001 (Thiết bị)

## 1. Mục đích

Đảm bảo phần mềm sử dụng trong công ty hợp pháp về bản quyền, an toàn về bảo mật và được quản lý tập trung về chi phí.

## 2. Danh mục phần mềm

### 2.1. Phân loại

| Nhóm | Mô tả | Cách cài |
|---|---|---|
| Chuẩn (Standard) | Cài sẵn trong image: bộ office, trình duyệt, chat, endpoint security | Tự động khi cấp máy |
| Được phê duyệt (Approved) | Danh mục công khai trên cổng nội bộ: IDE, công cụ thiết kế, tiện ích | Tự cài từ kho nội bộ hoặc ticket IT |
| Cần xin phép (Restricted) | Phần mềm mới chưa có trong danh mục, công cụ có quyền hệ thống sâu | Quy trình đánh giá mục 3 |
| Cấm (Prohibited) | Crack/keygen, torrent, công cụ đào coin, phần mềm ẩn danh vượt kiểm soát, remote access ngoài danh mục (TeamViewer cá nhân...) | Không được cài dưới mọi hình thức |

### 2.2. Nguyên tắc

- **Nghiêm cấm phần mềm bẻ khóa (crack)** dưới mọi hình thức — rủi ro pháp lý và là nguồn mã độc phổ biến nhất.
- Nhân viên không có quyền admin cài đặt tùy ý trên máy chuẩn hóa; cài qua kho phần mềm nội bộ (self-service) hoặc ticket.
- License công ty mua chỉ dùng cho công việc công ty; không dùng license cá nhân (mua tư nhân) cho sản phẩm thương mại của công ty nếu điều khoản không cho phép.

## 3. Quy trình xin phê duyệt phần mềm mới

1. Nhân viên tạo ticket: tên phần mềm, nhà cung cấp, mục đích, số người dùng dự kiến, chi phí (nếu có), link trang chủ.
2. IT đánh giá kỹ thuật (3 ngày làm việc): tính tương thích, trùng lặp với công cụ hiện có.
3. Security đánh giá rủi ro (3 ngày làm việc): quyền truy cập dữ liệu, nơi lưu dữ liệu, tuân thủ; phần mềm xử lý dữ liệu Confidential trở lên cần đánh giá sâu (5–10 ngày).
4. Phê duyệt chi phí: dưới 5 triệu/năm → Trưởng phòng IT; trên 5 triệu/năm → thêm Trưởng bộ phận đề xuất; trên 50 triệu/năm → Ban Giám đốc.
5. Kết quả: đưa vào danh mục Approved (kèm điều kiện sử dụng nếu có) hoặc từ chối kèm gợi ý thay thế.

## 4. Quản lý license

- IT quản lý tập trung toàn bộ license: số lượng, người dùng, ngày gia hạn, trên hệ thống quản lý tài sản phần mềm.
- Rà soát **mỗi quý**: license không sử dụng 60 ngày sẽ thu hồi và cấp cho người cần; nhân viên được thông báo trước 7 ngày.
- Nghỉ việc/chuyển bộ phận: license cá nhân hóa (IDE, design tool) thu hồi cùng quy trình offboarding.
- Trước ngày gia hạn 30 ngày, IT xác nhận lại nhu cầu với các bộ phận để tối ưu số lượng.

## 5. Phần mềm mã nguồn mở (Open Source)

- Được khuyến khích sử dụng trong phát triển, nhưng phải kiểm tra **giấy phép (license)** trước khi đưa vào sản phẩm:
  - An toàn cho sản phẩm thương mại: MIT, Apache 2.0, BSD.
  - Cần thẩm định trước khi dùng: GPL/AGPL và các license copyleft (nguy cơ buộc mở mã nguồn sản phẩm).
- Thư viện/dependency mới trong project phải qua quét lỗ hổng tự động (CI) trước khi merge.
- Không kéo dependency từ nguồn không chính thống; ưu tiên registry chuẩn (npm, PyPI, Maven Central) và khóa phiên bản (lockfile).

## 6. Môi trường phát triển

- Quyền truy cập repository, CI/CD, database dev/staging: tạo ticket kèm tên project và xác nhận của Project Owner; Security duyệt Access Scope.
- Không dùng dữ liệu production thật trong môi trường dev/test; dùng dữ liệu giả lập hoặc đã ẩn danh hóa (masking) theo SEC-POL-002.
- Công cụ CLI/SDK cài trên máy dev thuộc nhóm Approved mặc định nếu từ nguồn chính thức của nhà cung cấp cloud/công cụ đã phê duyệt.

## 7. Kiểm tra tuân thủ

- IT quét định kỳ phần mềm cài đặt trên thiết bị công ty qua công cụ quản lý endpoint; phần mềm ngoài danh mục sẽ nhận cảnh báo yêu cầu gỡ trong 7 ngày hoặc nộp đơn xin phê duyệt.
- Phát hiện phần mềm nhóm Cấm: gỡ ngay từ xa, lập biên bản, xử lý theo HR-POL-005; nếu là crack gây rủi ro pháp lý hoặc mã độc, chuyển Security điều tra.

## 8. Kênh hỗ trợ và SLA

| Loại yêu cầu | SLA |
|---|---|
| Cài phần mềm trong danh mục Approved | 1 ngày làm việc |
| Phê duyệt phần mềm mới (không chi phí) | 6 ngày làm việc |
| Phê duyệt phần mềm mới (có chi phí / dữ liệu nhạy cảm) | 10–15 ngày làm việc |
| Cấp license (còn slot) | 1 ngày làm việc |
| Quyền repo/CI-CD/database dev | 2 ngày làm việc |

**Từ khóa định tuyến về IT:** phần mềm, cài đặt, license, bản quyền, IDE, tool, crack, mã nguồn mở, open source, thư viện, dependency, repository, repo, CI/CD, GitHub, GitLab, database dev, npm, PyPI.


## 9. Software Asset Management (SAM)

IT duy trì inventory license gồm sản phẩm, edition, số seat, owner, cost center, renewal date, điều khoản quan trọng và người dùng. Mục tiêu là tuân thủ license và tối ưu chi phí, không chỉ kiểm soát cài đặt.

## 10. SaaS và shadow IT

Một SaaS có thể không cần cài phần mềm nhưng vẫn là “công cụ” thuộc policy này nếu xử lý dữ liệu công ty. Đánh giá tối thiểu gồm: loại dữ liệu, data residency/retention, SSO/MFA, khả năng export/delete, subprocessor, incident notification, DPA và quyền OAuth/API.

Dùng bản free để thử nghiệm với dữ liệu Public có thể được cho phép theo danh mục sandbox; đưa dữ liệu Internal trở lên vào SaaS chưa duyệt là không được phép.

## 11. Open-source governance

Đối với dependency đưa vào sản phẩm:

- dùng nguồn registry/repository chính thống;
- lock version và bật dependency/vulnerability scanning;
- xem xét license obligations, đặc biệt copyleft/network copyleft;
- tránh package không duy trì hoặc có dấu hiệu typosquatting;
- lưu thông tin dependency/SBOM khi pipeline hỗ trợ.

License “permissive” không đồng nghĩa tự động an toàn; vẫn phải tuân notice/attribution và yêu cầu bảo mật.

## 12. Tooling cho developer

IDE, CLI và SDK chính thống có thể thuộc danh mục Approved nhưng plugin/extension cài thêm được đánh giá riêng vì có thể đọc source code, terminal và credential. Extension yêu cầu quyền rộng hoặc gửi code ra cloud phải tuân SEC-POL-005.

## 13. Renewal và offboarding

30–60 ngày trước renewal lớn, owner xác nhận nhu cầu, active users và alternative. License không hoạt động có thể thu hồi để tái cấp. Khi offboarding, IT thu hồi seat/token/OAuth integration và chuyển owner cho tài sản SaaS cần giữ.

## 14. Exception

Phần mềm Restricted chỉ được dùng khi có approval record nêu phạm vi, compensating controls, người chịu rủi ro và ngày hết hạn. “Đã dùng từ trước” không phải lý do để trở thành Approved.
