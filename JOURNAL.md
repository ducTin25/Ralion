# Nhật ký phát triển — Team P-040

Nhật ký này được tổng hợp từ lịch sử Git, `WORKLOG.md` và các báo cáo giai đoạn.
Các commit được dẫn ở từng tuần đều tồn tại trong repository tại thời điểm chốt
ngày 01/09/2026.

## Tuần 1 — 23/07–02/08: Khởi tạo và chuẩn hóa công cụ

**Mục tiêu.** Khởi tạo repository, thiết lập quy ước cộng tác và bảo đảm AI
ghi nhật ký sử dụng AI hoạt động ổn định trên Windows.

**Kết quả.** Repository được khởi tạo (`7396182`); pre-push hook, encoding và
Codex logging được sửa (`635e0ba`, `9e0a165`, `b4d110b`).

**Quyết định và lý do.** Team đưa AI logging vào workflow Git ngay từ đầu để
có bằng chứng sử dụng công cụ xuyên suốt dự án thay vì tái tạo vào cuối kỳ.

**Khó khăn và giải pháp.** Hook có khác biệt encoding/launcher trên Windows;
team chuẩn hóa script và kiểm tra lại đường dẫn chạy Python.

**Bài học.** Bằng chứng vận hành phải được thiết kế cùng workflow phát triển,
không nên coi là tài liệu bổ sung ở giai đoạn bàn giao.

## Tuần 2 — 03/08–09/08: CI/CD và staging đầu tiên

**Mục tiêu.** Tạo quality gate, staging và luồng tích hợp có thể lặp lại.

**Kết quả.** Render staging, local quality gate, self-hosted runner và CI/CD
ban đầu được thiết lập (`472259d`, `d0bc490`, `8ba5e4f`, `12b5a19`, `f554c96`).

**Quyết định và lý do.** Docker và CI được ưu tiên trước feature để mọi module
sau đó dùng chung cách build/test, giảm sai lệch giữa máy thành viên.

**Khó khăn và giải pháp.** Artifact attestation và runner có giới hạn quyền;
team chọn các gate được hạ tầng hiện tại hỗ trợ, giữ pipeline có thể chạy thật.

**Bài học.** Một pipeline nhỏ nhưng ổn định có giá trị hơn cấu hình nhiều bước
không chạy được trong môi trường tổ chức.

## Tuần 3 — 10/08–16/08: Nền tảng full-stack và các miền nghiệp vụ cốt lõi

**Mục tiêu.** Hoàn thiện scaffold backend/frontend, auth/RBAC, onboarding,
knowledge ingestion, pgvector và các portal theo vai trò.

**Kết quả.** Backend/frontend foundation (`aeec2c8`, `3607c75`), project/member
onboarding (`8a6e1e8`, `23bb368`), pgvector ingestion (`3fc862e`, `faead44`),
grounded chat (`f0a23cc`), auth/RBAC (`73657fe`) và quản lý PM/HR được tích hợp.

**Quyết định và lý do.** PostgreSQL + pgvector được dùng làm nguồn sự thật duy
nhất để tránh đồng bộ metadata và ACL với một vector database độc lập.

**Khó khăn và giải pháp.** Nhiều thành viên cùng tác động Alembic, frontend và
contract dùng chung; team chia ownership theo domain, bổ sung test và merge
theo contract thay vì sửa chéo module.

**Bài học.** Ranh giới module và schema migration cần được review như API công
khai vì chúng quyết định khả năng tích hợp của cả nhóm.

## Tuần 4 — 17/08–23/08: Hoàn thiện RAG cho staging và chuyển hạ tầng

**Mục tiêu.** Đưa hệ thống từ luồng demo sang staging có retrieval, security,
evaluation dashboard, i18n/responsive và release gate thực tế.

**Kết quả.** Staging chuyển sang GCP VPS/Vercel (`24eb0e3`, `1fba8b4`), rule
mining và retrieval được mở rộng (`049daab`, `84b8cb6`), RAG/citation scope được
củng cố (`7179a97`, `e0d6eb6`) và CI/CD full-stack có Playwright/smoke test
(`e7342e0`, `be96229`).

**Quyết định và lý do.** Frontend gọi API qua Vercel same-origin proxy để cookie
session ổn định; backend dùng VPS có quyền kiểm soát Postgres/backup rõ hơn.

**Khó khăn và giải pháp.** CORS, cookie, Linux lockfile, embedding warm-up và
cloud credentials gây lỗi khác local; team thêm smoke gate và runbook thay vì
dựa vào kiểm tra thủ công.

**Bài học.** Deployment chỉ đáng tin khi có health contract, backup/restore và
runtime verification, không chỉ khi trang chủ tải được.

## Tuần 5 — 24/08–30/08: Ổn định UX, điều phối AI và phát hành

**Mục tiêu.** Hoàn thiện role-based workspace, GitHub/document workflows,
conversation continuity và chất lượng grounded answers.

**Kết quả.** GitHub integration/evidence mining (`802301d`, `639a41f`), BGE-M3
warm-up (`9bf8376`), release image/runtime verification (`e0bfc6e`, `c1920c1`),
conversation flow (`a8efe33`, `a1f2046`), async ingestion và degraded mode
(`8528e4a`, `596659c`) cùng nhiều đợt UI polish được hoàn tất.

**Quyết định và lý do.** Hệ thống chuyển các tác vụ ingest/AI dài sang async và
hiển thị degraded state, để lỗi provider không biến thành màn hình treo hoặc
phản hồi không xác định.

**Khó khăn và giải pháp.** Chat follow-up, citation completeness và provider
latency biến thiên; team tách routing/retrieval/generation, thêm evidence gate,
fallback và full evaluation run 147 case.

**Bài học.** Với AI, pass unit test chưa đủ: cần đo faithfulness, abstention,
routing, safety và latency trên cùng một golden set.

## Tuần 6 — 31/08–01/09: Đánh giá và đóng gói bàn giao

**Mục tiêu.** Chốt độ ổn định chatbot, kiểm kê bằng chứng và chuẩn hóa bộ hồ sơ
Demo Day.

**Kết quả.** Answer generation được ổn định (`9de0a79`); hai full evaluation run,
A/B model report, architecture, deployment, worklog và các entry point bàn giao
được đối chiếu. Nhánh bàn giao sau đó đồng bộ với `develop` tại `1580044`, nhận
engineer chatbot shortcut (`1a97fe7`) và bộ README/sơ đồ kiến trúc chính thức
(`ee71113`) mà không tạo merge commit mới trên nhánh bàn giao.

**Quyết định và lý do.** Báo cáo giữ nguyên kết luận “chưa production-ready” khi
độ trung thực, định tuyến và độ trễ chưa đạt SLO; việc các ngưỡng an toàn bắt
buộc đều đạt không được dùng để che những khoảng cách chất lượng còn lại.

**Khó khăn và giải pháp.** Hai checklist BTC dùng vị trí file khác nhau; team giữ
nguồn chính tại root/eval/presentation và bổ sung entry point trong `docs/` để
tương thích cả hai mà không làm gãy link lịch sử.

**Bài học.** Sản phẩm bàn giao tốt phải truy xuất được về tài liệu nguồn thật và
nêu rõ phần chưa đạt; tính trung thực làm báo cáo có giá trị hơn một bảng toàn
dấu xanh.

## Tài liệu đối chiếu

- [`WORKLOG.md`](WORKLOG.md) — lịch sử công việc theo ngày và commit.
- [`docs/PM/BO_06_CLAUDE_PROJECT_SOURCE_OF_TRUTH.md`](docs/PM/BO_06_CLAUDE_PROJECT_SOURCE_OF_TRUTH.md)
  — phạm vi và quyết định sản phẩm.
- [`eval/results/RALION_CHATBOT_EVALUATION_REPORT.md`](eval/results/RALION_CHATBOT_EVALUATION_REPORT.md)
  — phương pháp và kết quả evaluation.
- [`docs/deployment-vps-runbook.md`](docs/deployment-vps-runbook.md) — quyết
  định và vận hành staging.
