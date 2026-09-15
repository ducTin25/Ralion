# Chính sách Quản lý Secret và Khóa Mã hóa

- **Mã tài liệu:** SEC-POL-003
- **Phiên bản:** 2.1 — Ngày hiệu lực: 01/01/2026
- **Bộ phận ban hành:** Phòng An toàn Thông tin
- **Phạm vi áp dụng:** Mọi secret dùng trong hệ thống, ứng dụng và quy trình phát triển
- **Tài liệu liên quan:** SEC-POL-001 (Phân quyền), IT-POL-004 (Phần mềm), SEC-POL-004 (Ứng phó sự cố)

## 1. Mục đích

Ngăn ngừa lộ secret — một trong những nguyên nhân phổ biến nhất dẫn đến xâm nhập hệ thống — bằng quy tắc thống nhất về lưu trữ, sử dụng, luân chuyển và thu hồi.

## 2. Định nghĩa Secret

Bao gồm nhưng không giới hạn: mật khẩu hệ thống, **API key**, access token, refresh token, khóa SSH, chứng chỉ TLS và private key, connection string chứa credential, khóa mã hóa dữ liệu, webhook secret, credential của tài khoản dịch vụ, khóa của nhà cung cấp LLM/AI.

Mọi secret mặc định xếp mức **Restricted** theo SEC-POL-002.

## 3. Nguyên tắc bắt buộc

1. **Chỉ lưu secret trong Secret Manager** được công ty phê duyệt (Vault/AWS Secrets Manager/Azure Key Vault theo môi trường). Cấm lưu ở: source code, file cấu hình commit vào repo, biến môi trường ghi trong Dockerfile, tài liệu wiki, chat, email, ticket, ghi chú cá nhân.
2. **Secret chỉ tồn tại ở backend/môi trường triển khai.** Không nhúng secret vào frontend, mobile app, hay bất kỳ mã nào chuyển tới client. Khóa LLM API cũng vậy — mọi gọi LLM đi qua backend.
3. **Mỗi môi trường một secret riêng** (dev/staging/production không dùng chung); mỗi service một credential riêng để cô lập phạm vi khi lộ.
4. **Không chia sẻ secret giữa người với người.** Cần truy cập → xin quyền trên Secret Manager theo SEC-POL-001; tuyệt đối không gửi secret qua chat/email kể cả "chỉ một lần".
5. **Least privilege cho secret:** token/key tạo với phạm vi (scope) hẹp nhất và thời hạn ngắn nhất đủ dùng.

## 4. Vòng đời secret

### 4.1. Tạo

- Tạo trực tiếp trong Secret Manager hoặc qua pipeline tự động; đặt tên theo chuẩn `<env>/<service>/<purpose>`.
- Gán **owner** (người/nhóm chịu trách nhiệm) và ngày rà soát cho mỗi secret.

### 4.2. Sử dụng

- Ứng dụng đọc secret lúc chạy (runtime) từ Secret Manager qua identity của service (IAM role/service account), không hardcode.
- CI/CD dùng secret store của hệ thống CI với masking log; cấm echo/print secret trong log build.
- Truy cập secret production của con người: chỉ qua phiên just-in-time có phê duyệt, ghi log ai-đọc-gì-khi-nào.

### 4.3. Luân chuyển (Rotation)

| Loại secret                                      | Chu kỳ luân chuyển                                 |
| ------------------------------------------------ | -------------------------------------------------- |
| Credential tài khoản dịch vụ, API key bên thứ ba | 90 ngày (tự động nếu hỗ trợ)                       |
| Khóa SSH cá nhân                                 | 12 tháng                                           |
| Chứng chỉ TLS                                    | Trước hạn 30 ngày (tự động qua ACME nếu được)      |
| Khóa mã hóa dữ liệu (KEK/DEK)                    | Theo thiết kế hệ thống, tối thiểu rà soát hằng năm |
| Bất kỳ secret nào nghi lộ                        | **Ngay lập tức**                                   |

### 4.4. Thu hồi

- Nhân viên rời dự án/nghỉ việc: luân chuyển các secret người đó từng truy cập trực tiếp (danh sách lấy từ log Secret Manager) trong **48 giờ**.
- Service ngừng sử dụng: vô hiệu hóa credential liên quan trong 7 ngày.

## 5. Phòng chống lộ secret trong mã nguồn

- **Pre-commit hook + secret scanning** bật bắt buộc trên mọi repo: chặn commit chứa pattern secret (key AWS, token, private key...).
- Quét định kỳ toàn bộ lịch sử repo; phát hiện secret trong lịch sử → xử lý như secret đã lộ (mục 6), không chỉ xóa commit.
- File cấu hình mẫu dùng placeholder (`API_KEY=<your-key-here>`), file `.env` thật đưa vào `.gitignore`.
- Review code có trách nhiệm từ chối merge khi thấy secret/credential trong diff.

## 6. Xử lý khi lộ secret

1. **Báo ngay Security** (kênh khẩn cấp) — trong vòng **1 giờ** kể từ khi phát hiện; tự xử lý âm thầm được xem là vi phạm.
2. Security phối hợp owner **thu hồi/luân chuyển secret ngay**, ưu tiên trước cả việc điều tra.
3. Rà soát log sử dụng secret bị lộ để xác định có truy cập trái phép chưa; xử lý tiếp theo SEC-POL-004.
4. Ghi nhận bài học và bổ sung rule quét nếu pattern chưa được nhận diện.

Người **chủ động báo cáo sớm** sự cố lộ secret do sơ suất được xem xét giảm nhẹ; che giấu là tình tiết tăng nặng.

## 7. Khóa mã hóa

- Thuật toán chuẩn: AES-256 (đối xứng), RSA-2048/ECDSA P-256 trở lên (bất đối xứng); cấm thuật toán yếu (DES, RC4, MD5/SHA-1 cho chữ ký).
- Khóa quản lý qua KMS; khóa gốc (root/master key) chỉ nhóm được chỉ định kiểm soát theo cơ chế nhiều người (quorum).
- Không tự thiết kế thuật toán mã hóa; dùng thư viện chuẩn đã kiểm định.

## 8. Kênh hỗ trợ và SLA

| Loại yêu cầu                                  | SLA                                           |
| --------------------------------------------- | --------------------------------------------- |
| Xin quyền truy cập secret trên Secret Manager | 2 ngày làm việc                               |
| Tạo secret/namespace mới cho service          | 2 ngày làm việc                               |
| Hỗ trợ tích hợp Secret Manager vào ứng dụng   | 5 ngày làm việc                               |
| Báo lộ secret                                 | **Khẩn cấp — phản hồi 30 phút, thu hồi ngay** |

**Từ khóa định tuyến về Security:** secret, API key, token, private key, SSH key, chứng chỉ, TLS, hardcode, lộ key, commit nhầm key, secret manager, vault, rotation, luân chuyển khóa, mã hóa, KMS, credential.

## 9. Ưu tiên identity thay static secret

Khi nền tảng hỗ trợ, dùng workload identity, short-lived token, OIDC federation hoặc managed identity thay cho API key dài hạn. Static secret chỉ dùng khi không có lựa chọn phù hợp và phải có owner/rotation/monitoring.

## 10. Secret inventory

Mỗi secret cần metadata tối thiểu: owner/team, service, environment, purpose, privilege/scope, created date, expiry/rotation date và nơi sử dụng. Secret không xác định được owner phải được điều tra và thu hồi nếu không chứng minh được nhu cầu.

## 11. Rotation strategy

Rotation phải có khả năng **không gây downtime** khi có thể: hỗ trợ hai credential song song, deploy consumer trước khi revoke credential cũ và có validation. Mốc 90 ngày là baseline cho một số static credential; secret short-lived hoặc managed identity dùng vòng đời khác phù hợp thiết kế.

## 12. Secret exposure taxonomy

Coi secret đã compromise nếu xuất hiện trong public/private repo không đúng chỗ, CI log, ticket/chat, prompt AI ngoài phạm vi cho phép, client bundle hoặc máy cá nhân không kiểm soát. “Repo private” không làm cho hardcoded secret trở thành hợp lệ.

## 13. Detection

Bật secret scanning tại pre-commit/CI/repository hosting khi khả thi và cảnh báo bất thường tại cloud/provider. Detection rule phải tránh chỉ dựa vào regex; có thể kết hợp entropy, known token format và verified secret checks an toàn.

## 14. Cryptographic key lifecycle

Key encryption/signing cần mục đích cụ thể, algorithm/key size theo standard hiện hành, KMS/HSM khi phù hợp, access control, rotation/versioning, backup/recovery và destruction. Không xóa key đang cần giải mã dữ liệu còn retention.

## 15. Emergency access

Trường hợp production incident cần đọc secret thủ công phải dùng JIT/break-glass, log người truy cập và lý do. Sau incident, đánh giá rotate secret nếu giá trị đã được con người xem/copy ra ngoài luồng tự động.

## 16. Developer guidance

- `.env.example` chỉ có placeholder.
- Không paste secret thật vào issue/PR/chatbot.
- Khi cần chia sẻ cách cấu hình, chia sẻ **tên secret/đường dẫn vault**, không chia sẻ value.
- Nếu commit nhầm: revoke/rotate trước, sau đó mới dọn history; xóa commit không làm secret “chưa từng lộ”.
