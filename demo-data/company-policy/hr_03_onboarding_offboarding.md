# Chính sách Onboarding và Offboarding

- **Mã tài liệu:** HR-POL-003
- **Phiên bản:** 2.0 — Ngày hiệu lực: 01/01/2026
- **Bộ phận ban hành:** Phòng Nhân sự, phối hợp Phòng CNTT và Phòng An toàn Thông tin
- **Phạm vi áp dụng:** Toàn bộ nhân viên mới, nhân viên nghỉ việc, chuyển bộ phận
- **Tài liệu liên quan:** IT-POL-001 (Cấp phát thiết bị), SEC-POL-001 (Phân quyền truy cập)

## 1. Mục đích

Chuẩn hóa quy trình tiếp nhận nhân viên mới và kết thúc hợp tác, đảm bảo nhân viên mới hòa nhập nhanh, được cấp đủ công cụ làm việc đúng quyền hạn, và mọi tài sản/quyền truy cập được thu hồi đầy đủ khi nhân viên rời công ty.

## 2. Onboarding — Quy trình tiếp nhận nhân viên mới

### 2.1. Trước ngày làm việc đầu tiên (Pre-boarding)

| Việc | Bộ phận | Thời hạn |
|---|---|---|
| Gửi thư mời nhận việc và hướng dẫn hồ sơ | HR | Ngay khi ứng viên nhận offer |
| Tạo yêu cầu cấp thiết bị và tài khoản | HR → IT | Trước ngày vào ít nhất 3 ngày làm việc |
| Khai báo Project, Role, Module và Access Scope | Project Owner → Security | Trước ngày vào ít nhất 2 ngày làm việc |
| Phân công Buddy/Mentor | Trưởng bộ phận | Trước ngày vào |
| Gửi email chào mừng kèm lịch ngày đầu tiên | HR | Trước ngày vào 1 ngày |

### 2.2. Ngày đầu tiên

- HR đón tiếp, hướng dẫn nội quy, ký hợp đồng lao động và **cam kết bảo mật thông tin (NDA)**.
- IT bàn giao laptop, tài khoản email, tài khoản hệ thống; nhân viên ký biên bản bàn giao thiết bị.
- Nhân viên đổi mật khẩu lần đầu, bật MFA và hoàn thành khóa học nhận thức an toàn thông tin cơ bản.
- Quản lý trực tiếp giới thiệu team, tổng quan dự án và lộ trình onboarding (Onboarding Plan).

### 2.3. Tuần 1 — Tháng đầu

- Nhân viên thực hiện **checklist onboarding** trên hệ thống: đọc tài liệu dự án, thiết lập môi trường phát triển, hoàn thành các task hướng dẫn theo Role/Module được giao.
- Cập nhật trạng thái từng task: NOT_STARTED → IN_PROGRESS → DONE; nếu vướng mắc không tự giải quyết được, báo **BLOCKED** kèm lý do để hệ thống định tuyến hỗ trợ (IT/Security/HR/Owner).
- Buddy check-in tối thiểu 2 lần/tuần trong tháng đầu.
- Mốc khuyến nghị: hoàn thành **First Task** trong 2 tuần đầu và **First Pull Request** trong tháng đầu (với vị trí kỹ thuật).

### 2.4. Đánh giá thử việc và đóng onboarding

- Thời gian thử việc và mốc đánh giá phải nằm trong giới hạn pháp luật áp dụng cho từng nhóm chức danh; HR xác nhận thời hạn ngay khi phát hành offer/hợp đồng thử việc để tránh dùng một mốc chung cho mọi vị trí.
- Đánh giá giữa kỳ (ngày 30) và cuối kỳ (trước ngày 55): quản lý trực tiếp đánh giá trên biểu mẫu chuẩn, trao đổi 1-1 với nhân viên.
- Onboarding được **đóng chính thức** khi: toàn bộ checklist hoàn thành, không còn blocker mở, và Project Owner xác nhận trên hệ thống (trạng thái ONBOARDING_CLOSED).

## 3. Chuyển bộ phận nội bộ

- Quy trình rút gọn: Trưởng bộ phận cũ xác nhận bàn giao → HR cập nhật hồ sơ → Security điều chỉnh Access Scope (thu hồi quyền cũ, cấp quyền mới) trong **2 ngày làm việc**.
- Nhân viên chuyển bộ phận thực hiện onboarding rút gọn cho project mới.

## 4. Offboarding — Quy trình nghỉ việc

### 4.1. Thông báo và bàn giao

- Nhân viên nộp thông báo/đơn nghỉ việc trên HRM và tuân thủ **thời hạn báo trước theo loại hợp đồng, công việc đặc thù và quy định pháp luật hiện hành**. Trong thời gian thử việc, việc chấm dứt thực hiện theo quy định pháp luật và thỏa thuận thử việc áp dụng; HR xác nhận mốc cuối cùng cho từng trường hợp.
- Quản lý trực tiếp lập kế hoạch bàn giao: danh sách công việc, tài liệu, đầu mối liên hệ; bàn giao có xác nhận của người nhận.

### 4.2. Thu hồi tài sản và quyền truy cập

| Việc | Bộ phận | Thời hạn |
|---|---|---|
| Thu hồi laptop, thẻ, thiết bị | IT | Ngày làm việc cuối |
| Vô hiệu hóa toàn bộ tài khoản, email, VPN | IT + Security | Trong 24 giờ sau ngày cuối |
| Thu hồi quyền repository, database, hệ thống nội bộ | Security | Trong 24 giờ sau ngày cuối |
| Chuyển quyền sở hữu tài liệu, email cần giữ | Quản lý + IT | Trước ngày cuối |

### 4.3. Hoàn tất

- HR thực hiện phỏng vấn nghỉ việc (exit interview) — không bắt buộc nhưng khuyến khích.
- Thanh toán các khoản còn lại (lương, phép chưa dùng quy đổi) trong vòng **14 ngày** kể từ ngày chấm dứt hợp đồng theo luật.
- Chốt và trả sổ/xác nhận BHXH theo quy định.
- Nghĩa vụ bảo mật theo NDA **tiếp tục có hiệu lực sau khi nghỉ việc**.

## 5. Trách nhiệm các bên

- **HR:** điều phối toàn bộ quy trình, hồ sơ, hợp đồng, chế độ.
- **IT:** thiết bị và tài khoản, đúng SLA cấp phát/thu hồi.
- **Security:** Access Scope đúng nguyên tắc least privilege, thu hồi quyền đúng hạn.
- **Quản lý trực tiếp/Project Owner:** kế hoạch onboarding, đánh giá thử việc, xác nhận đóng onboarding, kế hoạch bàn giao khi nghỉ việc.

## 6. Kênh hỗ trợ và SLA

| Loại yêu cầu | Kênh tiếp nhận | SLA xử lý |
|---|---|---|
| Hồ sơ, hợp đồng, NDA | HR Service Desk | 3 ngày làm việc |
| Blocker trong onboarding | Hệ thống onboarding (báo BLOCKED) | Định tuyến trong 4 giờ |
| Xác nhận nghỉ việc, chế độ | HR Service Desk | 5 ngày làm việc |

**Từ khóa định tuyến về HR:** onboarding, nhân viên mới, thử việc, buddy, mentor, hợp đồng, NDA, nghỉ việc, offboarding, bàn giao, exit interview, chuyển bộ phận, đánh giá thử việc, checklist onboarding.


## 7. Mô hình 30–60–90 ngày

Tùy vai trò, quản lý xây Onboarding Plan theo ba lớp:

- **0–30 ngày:** hiểu tổ chức, sản phẩm/dự án, quy tắc bắt buộc, môi trường làm việc và hoàn thành first task có giám sát.
- **31–60 ngày:** tự xử lý phần việc chuẩn, hoàn thiện knowledge gaps, nhận feedback chính thức.
- **61–90 ngày:** đạt mức độc lập kỳ vọng của vai trò hoặc có kế hoạch phát triển cụ thể nếu chưa đạt.

Mốc này là khung vận hành, không thay thế thời hạn thử việc pháp lý/hợp đồng.

## 8. Joiner–Mover–Leaver controls

### Joiner

Mọi quyền phải xuất phát từ role/project đã được xác nhận. Không sao chép toàn bộ quyền của một nhân viên cũ cho người mới. Quyền production/admin không cấp mặc định trong onboarding.

### Mover

Khi đổi team/project/role, quản lý cũ xác nhận tài nguyên cần bàn giao; Security thực hiện **revoke-before-grant** cho quyền không còn phù hợp để tránh privilege creep. Dữ liệu sở hữu cá nhân trên drive/repo công ty phải chuyển owner nếu là tài sản công việc.

### Leaver

- Nghỉ việc thông thường: lịch thu hồi được lập trước ngày cuối.
- Chấm dứt đột xuất hoặc có rủi ro: HR, Security và IT thống nhất thời điểm khóa quyền tương ứng với thời điểm quyết định có hiệu lực; không chờ 24 giờ nếu việc tiếp tục truy cập tạo rủi ro.
- Legal hold/điều tra: không xóa mailbox, log hoặc thiết bị liên quan cho đến khi Pháp chế/Security cho phép.

## 9. Offboarding checklist tối thiểu

1. Công việc, tài liệu, repository, dashboard, lịch vận hành và đầu mối đối tác đã bàn giao.
2. Tài sản vật lý đối soát theo asset ID/serial.
3. Account, group, VPN, SaaS, cloud, repo và privileged access đã thu hồi.
4. Secret mà người nghỉ từng có khả năng đọc trực tiếp được đánh giá rotation theo SEC-POL-003.
5. License cá nhân hóa được thu hồi theo IT-POL-004.
6. Quyền sở hữu file/calendar/service account được chuyển cho owner mới.
7. HR xác nhận nghĩa vụ sau nghỉ việc: bảo mật, sở hữu trí tuệ, hoàn trả tài sản và các nghĩa vụ hợp đồng còn hiệu lực.

## 10. Onboarding quality gates

Không đóng onboarding chỉ vì checklist đạt 100%. Project Owner cần xác nhận tối thiểu: nhân viên truy cập được đúng tài nguyên, hoàn thành đào tạo bắt buộc, biết kênh hỗ trợ/escalation, và đã hoàn thành một nhiệm vụ thực tế phù hợp vai trò.

## 11. Trách nhiệm và bằng chứng

Mỗi bước quan trọng cần để lại dấu vết trên hệ thống tương ứng: HRM, IT Service Desk, Access Management hoặc onboarding system. Checklist ngoài spreadsheet cá nhân chỉ là bản hỗ trợ, không phải nguồn audit chính thức.

## 12. Tình huống thường gặp

- **Ngày đầu chưa có laptop:** HR/IT ưu tiên thiết bị mượn và ghi blocker; không yêu cầu nhân viên dùng máy cá nhân cho dữ liệu nhạy cảm.
- **Chuyển project nhưng vẫn thấy repo cũ:** báo Project Owner/Security; không tiếp tục sử dụng quyền thừa.
- **Nhân viên nghỉ đột xuất:** quản lý ưu tiên chuyển owner tài liệu/tài khoản dịch vụ và phối hợp Security khóa quyền theo mức rủi ro.
