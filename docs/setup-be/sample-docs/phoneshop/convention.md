# PhoneShop API — Coding Convention

## Triết lý chung
Convention tồn tại để giảm chi phí quyết định lặp lại và giảm ma sát khi review code, không phải để gò bó sáng tạo. Mọi rule dưới đây đều nên tự động hoá qua tool (lint, format, CI check) thay vì dựa vào con người nhớ và nhắc nhau bằng tay — nếu 1 rule không thể tự động kiểm tra được, cân nhắc xem có thực sự cần thiết không.

## Python style
- Format bằng `black` (line length 100) + `ruff` (lint, thay thế cho flake8/isort/nhiều plugin khác), chạy tự động qua pre-commit hook — không format tay, không tranh cãi về style trong PR review vì tool đã quyết định sẵn.
- Type hint bắt buộc cho mọi function public (kiểm tra bằng `mypy --strict` trong CI, fail build ngay nếu thiếu type hint hoặc type không khớp).
- Đặt tên: `snake_case` cho function/biến, `PascalCase` cho class, hằng số `UPPER_SNAKE_CASE`, private method/biến prefix `_` (single underscore, không dùng double underscore trừ khi thực sự cần name mangling).
- Docstring theo Google style cho mọi public function trong `domain/` và `services/` (không bắt buộc cho `api/` vì FastAPI tự sinh docs từ type hint + `Field(description=...)` trong Pydantic schema).
- Không dùng `# type: ignore` để né lỗi mypy trừ khi có comment giải thích rõ lý do và đã thảo luận với Tech Lead — mypy ignore tràn lan là dấu hiệu type hint đang không phản ánh đúng thực tế code.

## Cấu trúc import
Sắp xếp theo 3 nhóm, cách nhau 1 dòng trống, tự động qua `ruff` isort rule: (1) standard library, (2) third-party package, (3) import nội bộ project (`app.*`). Không dùng wildcard import (`from x import *`) dưới bất kỳ hoàn cảnh nào.

## Git
- Nhánh đặt tên `feature/<mã-task>-mo-ta-ngan`, ví dụ `feature/PHONE-123-them-loc-theo-gia`. Hotfix khẩn cấp: `hotfix/<mã-task>-mo-ta-ngan`, được phép merge thẳng từ `hotfix/*` vào `main` sau khi 1 Senior approve (không cần đợi qua staging đầy đủ nếu là sự cố production nghiêm trọng).
- Commit message theo chuẩn Conventional Commits: `feat:`, `fix:`, `refactor:`, `test:`, `chore:`, `docs:`, `perf:`. Ví dụ tốt: `feat(order): them ho tro ma giam gia theo % cho don hang tren 5 trieu`.
- PR bắt buộc có ít nhất 1 approve từ Tech Lead hoặc Senior engineer + toàn bộ CI check xanh mới được merge, dùng **squash merge** để giữ lịch sử `main` sạch sẽ, mỗi PR tương ứng đúng 1 commit trên `main`.
- Branch protection bật trên `main`: không cho push trực tiếp dưới mọi hình thức (kể cả admin), bắt buộc qua PR, bắt buộc status check pass (lint, type check, unit test, integration test), bắt buộc branch up-to-date với `main` trước khi merge.
- PR nên giữ kích thước nhỏ, khuyến nghị dưới 400 dòng thay đổi (không tính file generated/lock file) — PR lớn hơn nên cân nhắc chia nhỏ, dễ review hơn và giảm rủi ro khi cần revert.

## Review checklist (template có sẵn trong `.github/PULL_REQUEST_TEMPLATE.md`, tự động điền khi tạo PR)
- [ ] Có test cho logic mới/thay đổi, coverage tổng thể không giảm so với `main` (CI tự check qua Codecov).
- [ ] Không hardcode credential, URL môi trường, hoặc magic number không có giải thích.
- [ ] Migration (nếu có) đã test cả chiều upgrade lẫn downgrade, đã kiểm tra không lock table quá lâu trên các bảng lớn (`orders` hiện có hơn 2 triệu row, `inventory` cập nhật liên tục — cần cẩn trọng đặc biệt).
- [ ] Nếu đổi API contract (thêm/xoá/đổi field response), đã cập nhật OpenAPI spec và báo trước cho team frontend/mobile ít nhất 1 ngày trước khi merge.
- [ ] Nếu thêm tính năng rủi ro cao hoặc thay đổi logic nhạy cảm (giá, tồn kho, thanh toán), đã bọc qua feature flag và có kế hoạch rollout dần.
- [ ] Log thêm mới (nếu có) không chứa thông tin nhạy cảm (xem `access-security.md`).

## SLA review PR
Team cam kết review PR trong vòng 4 giờ làm việc kể từ lúc gắn reviewer (không tính ngoài giờ hành chính và cuối tuần). Nếu quá hạn, tác giả PR nên tag lại trực tiếp trên Slack #phoneshop-backend thay vì chờ đợi thụ động. PR liên quan tới sự cố production (hotfix) được ưu tiên review ngay lập tức, không chờ hàng đợi thông thường.

## Đặt tên API endpoint
REST endpoint dùng danh từ số nhiều, kebab-case cho path nhiều từ: `GET /api/v1/products`, `POST /api/v1/orders`, `GET /api/v1/installment-applications/{id}`. Không dùng động từ trong path (tránh `POST /api/v1/create-order`, dùng `POST /api/v1/orders`). Versioning qua path prefix (`/api/v1/`, `/api/v2/`), không dùng header versioning.
