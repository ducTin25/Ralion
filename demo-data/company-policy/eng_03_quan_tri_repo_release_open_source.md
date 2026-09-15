# Chính sách Quản trị Repository, Release và Đóng góp Open Source

- **Mã tài liệu:** ENG-POL-003
- **Phiên bản:** 1.0 — Ngày hiệu lực: 01/01/2026
- **Bộ phận ban hành:** Engineering Platform, phối hợp Security và Legal
- **Phạm vi áp dụng:** Source code repository, CI/CD workflow, release artifact và đóng góp open source liên quan công việc
- **Tài liệu liên quan:** ENG-POL-001; SEC-POL-003; LEG-POL-001; IT-POL-006

## 1. Mục đích

Chuẩn hóa ownership và bảo vệ source code, branch/release pipeline; cho phép đóng góp cộng đồng mà không làm lộ proprietary code, secret hoặc dữ liệu khách hàng.

## 2. Repository ownership

Mỗi repo phải có owner/team chịu trách nhiệm, classification, default branch, CODEOWNERS hoặc cơ chế review tương đương và trạng thái active/archived.

## 3. Branch protection

Protected branch production/release phải bật review và CI bắt buộc theo risk. Force push/delete bị giới hạn. Admin bypass chỉ dùng cho tình huống được phép và phải có audit trail.

## 4. Access

Repo access theo SEC-POL-001 và project membership. Public visibility là quyết định Legal/Security/Product, không phải quyền mặc định của repo admin.

## 5. Secrets và sensitive files

- Secret scanning/pre-commit theo SEC-POL-003.
- Commit secret rồi xóa ở commit sau vẫn được coi là **đã lộ**; rotate/revoke trước khi clean history.
- Production dump, customer export, private key và credential không được lưu trong repo.

## 6. Release artifact

Production artifact phải xây từ pipeline tin cậy; version/tag liên kết tới commit và change record khi áp dụng. Không upload binary thủ công từ laptop cá nhân vào production registry trừ emergency control được ghi nhận.

## 7. Tag và version

Release tag bất biến theo quy ước của team; nếu cần sửa, tạo version mới thay vì thay artifact phía sau cùng tag khi hệ thống hỗ trợ.

## 8. Archive/deletion

Repo không dùng phải archive trước; deletion cần owner xác nhận và retention check. Repo thuộc legal hold không được xóa.

## 9. Đóng góp open source

- Được khuyến khích khi không xung đột nhiệm vụ và không lộ Internal/Confidential content.
- Contribution được tạo trong giờ làm hoặc dựa trực tiếp vào code công ty có thể cần manager/Legal xác nhận quyền đóng góp.
- Open-source một project nội bộ cần scrub history, secret scan, license, README/notice và Security/Legal approval.

## 10. Fork và tài khoản cá nhân

Không fork private company repo sang namespace cá nhân/public. Nếu nền tảng tạo fork cá nhân trong cùng enterprise theo control chuẩn thì vẫn chịu ACL/retention của công ty.

## 11. Tình huống thường gặp

- **Lỡ commit API key rồi git revert:** phải rotate secret; revert không làm key “chưa từng lộ”.
- **Muốn open-source utility 200 dòng:** theo release checklist; nhỏ không đồng nghĩa không có IP/secret risk.
- **Hotfix cần admin bypass:** dùng change/emergency process và ghi lý do/reviewer sau đó.

## 12. Kênh và SLA

| Yêu cầu | SLA |
|---|---|
| Tạo repo/project chuẩn | 1 ngày làm việc |
| Public/open-source review | 5–10 ngày làm việc |
| Restore repo/archive | 2 ngày làm việc |
| Secret committed | Báo Security trong 1 giờ |

**Từ khóa định tuyến:** repository, GitHub, GitLab, branch protection, CODEOWNERS, tag, release, artifact, open source, public repo, fork, force push.
