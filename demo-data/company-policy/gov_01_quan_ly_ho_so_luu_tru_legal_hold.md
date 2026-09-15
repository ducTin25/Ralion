# Chính sách Quản lý Hồ sơ, Lưu trữ và Legal Hold

- **Mã tài liệu:** GOV-POL-001
- **Phiên bản:** 1.0 — Ngày hiệu lực: 01/01/2026
- **Bộ phận ban hành:** Legal & Compliance, phối hợp IT và Data Owners
- **Phạm vi áp dụng:** Hồ sơ kinh doanh, tài chính, nhân sự, hợp đồng, kỹ thuật và dữ liệu có nghĩa vụ lưu trữ
- **Tài liệu liên quan:** SEC-POL-002; IT-POL-008; LEG-POL-002

## 1. Mục đích

Đảm bảo hồ sơ được giữ đủ lâu cho hoạt động, kiểm toán và pháp lý nhưng không lưu vô thời hạn khi không còn mục đích; bảo vệ dữ liệu khi có tranh chấp/điều tra.

## 2. Record và working material

- **Record:** bản chính thức chứng minh quyết định/giao dịch/nghĩa vụ, ví dụ hợp đồng ký, invoice, approval, policy version, audit report.
- **Working material:** draft tạm, bản sao làm việc hoặc dữ liệu trung gian không cần lưu lâu sau khi record đã được chốt.

## 3. Retention Schedule

Thời hạn cụ thể theo loại hồ sơ được Legal/Finance/HR duy trì trong Retention Schedule. Nếu policy chuyên biệt hoặc pháp luật yêu cầu dài hơn, áp dụng thời hạn dài hơn.

Ví dụ control nội bộ:
- Hợp đồng và phụ lục: term + 10 năm trừ khi Legal quy định khác.
- Hồ sơ procurement/approval: 10 năm.
- Incident/security audit evidence: tối thiểu 3 năm hoặc lâu hơn theo yêu cầu hệ thống/hợp đồng.
- Working drafts không còn giá trị: xóa theo lifecycle của hệ thống.

## 4. Nơi lưu chuẩn

Record phải lưu trong system of record được chỉ định: HRM, Contract Repository, Finance/ERP, ticketing, document management. Không dùng mailbox cá nhân hoặc local drive làm nơi duy nhất lưu record.

## 5. Legal Hold

Khi Legal phát hành Legal Hold:
1. Tạm dừng xóa/retention automation với dữ liệu thuộc phạm vi.
2. Người nhận hold phải giữ email, file, chat hoặc artifact liên quan và không chỉnh sửa/xóa.
3. IT hỗ trợ preserve/export; access vẫn theo least privilege.
4. Hold chỉ kết thúc khi Legal phát hành release bằng văn bản.

Legal Hold **ưu tiên hơn** retention schedule và yêu cầu xóa thông thường cho dữ liệu nằm trong phạm vi pháp lý, trong giới hạn pháp luật cho phép.

## 6. Xóa và disposal

- Khi hết retention và không có hold/exception, dữ liệu được xóa an toàn theo SEC-POL-002.
- Không tự giữ “phòng khi cần” bản copy Confidential/Restricted ngoài system of record.
- Backup không được dùng làm kho archive vĩnh viễn; lifecycle backup theo IT-POL-008.

## 7. Chat, email và AI logs

Không phải mọi chat/email đều là record. Nếu một quyết định quan trọng chỉ tồn tại trong chat/email, owner cần đưa quyết định/approval vào system of record phù hợp. AI conversation logs xử lý theo SEC-POL-005 và retention được phê duyệt.

## 8. Tình huống thường gặp

- **Legal Hold yêu cầu giữ email nhưng mailbox policy tự xóa sau X ngày:** hold override xóa tự động cho phạm vi liên quan.
- **Bạn có bản hợp đồng cuối trong Downloads:** upload vào Contract Repository; local copy không phải nguồn chuẩn.
- **Khách hàng yêu cầu xóa dữ liệu:** chuyển privacy workflow; không tự xóa nếu dữ liệu đang thuộc legal hold.

## 9. Kênh và SLA

| Yêu cầu | SLA |
|---|---|
| Hỏi retention cho loại hồ sơ | 3 ngày làm việc |
| Legal Hold support | Ưu tiên trong ngày |
| Restore record bị xóa nhầm | Theo IT-POL-008 |
| Disposal exception | Legal phản hồi 5 ngày làm việc |

**Từ khóa định tuyến:** lưu trữ, retention, record, hồ sơ, legal hold, litigation hold, xóa dữ liệu, archive, email, chứng từ, system of record.
