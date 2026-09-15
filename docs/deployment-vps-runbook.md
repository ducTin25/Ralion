# Google Cloud credit-backed staging runbook

Runbook này thay Render bằng một VPS staging dùng Welcome credit còn lại trên Google Cloud
Paid account. Kiến trúc cố ý
giữ nhỏ: một VM `e2-medium`, một boot disk `pd-standard` 30 GB, Docker Compose, Caddy,
FastAPI và ParadeDB. Không tạo load balancer, Cloud SQL, static IP, snapshot schedule hoặc
object storage.

> Billing account đã là **Paid account**. Welcome credit hết hạn ngày **13/11/2026** và
> phương thức thanh toán có thể bị charge nếu vượt credit. Budget alert không tự dừng tài
> nguyên. Deadline bắt buộc để backup và destroy hạ tầng là **08/11/2026**.

## 1. Những gì repository đã tự động hóa

- `infra/gcp`: tạo project riêng, VPC/subnet Singapore, firewall, budget và VM Ubuntu 24.04
  x86-64 bằng Terraform.
- `.github/workflows/ci.yml`: Ruff, Alembic và pytest trên shared ephemeral self-hosted
  runner của organization với ParadeDB tmpfs cô lập. Workflow bỏ qua PR từ fork.
- `.github/workflows/release.yml`: merge vào `main` build image `linux/amd64`, push GHCR theo
  digest và deploy staging qua SSH. Build tái sử dụng inline cache từ image `main`, không
  dùng GitHub Actions cache storage.
- `.github/workflows/staging-monitor.yml`: kiểm tra thủ công từ bên ngoài khi cần chẩn đoán.
- `scripts/vps`: deploy có lock, backup trước migration, smoke test và rollback application.
- systemd timers: monitor mỗi 5 phút; `pg_dump` hằng ngày và giữ đúng ba dump mới nhất.
- `scripts/gcp/download-latest-backup.ps1`: tải dump và checksum mới nhất về máy cá nhân.
- `scripts/gcp/restore-backup-local.ps1`: restore drill tháng bằng ParadeDB tmpfs local.

Chỉ `main` được phép deploy vào GitHub Environment `staging`. Workflow không còn job deploy
production bằng tag vì trial này chỉ phục vụ staging.

## 2. Kiểm tra repository trước khi tạo VM

Từ nhánh `feat/replace-render-with-vps`, bật Docker Desktop rồi chạy:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test-backend.ps1
terraform -chdir=infra/gcp fmt -check
terraform -chdir=infra/gcp validate
```

Push nhánh và mở PR vào `develop`. Chỉ sau khi CI pass mới merge vào `develop`, rồi mở PR
`develop -> main`. Chưa merge PR thứ hai trước khi VM, environment files và GitHub
Environment đã sẵn sàng, vì merge `main` sẽ kích hoạt deploy ngay.

## 3. Xác minh Paid account credit và chuẩn bị Terraform

1. Mở [Google Cloud Billing](https://console.cloud.google.com/billing) và xác nhận rõ:
   - tài khoản hiển thị **Paid account**;
   - còn Welcome credit;
   - credit hết hạn ngày **13/11/2026**;
   - operator chấp nhận rủi ro overage và deadline destroy **08/11/2026**.
2. Cài `gcloud` và Terraform, sau đó đăng nhập Application Default Credentials:

   ```powershell
   gcloud auth application-default login
   gcloud billing accounts list
   ```

3. Tạo SSH key riêng cho staging. Không commit private key:

   ```powershell
   ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\p040_staging" -C "p040-staging"
   ```

4. Tạo cấu hình Terraform local:

   ```powershell
   Copy-Item infra\gcp\terraform.tfvars.example infra\gcp\terraform.tfvars
   Get-Content "$env:USERPROFILE\.ssh\p040_staging.pub"
   ```

   Sửa `infra/gcp/terraform.tfvars`:

   ```hcl
   billing_account_id = "YOUR-BILLING-ACCOUNT-ID"
   deploy_public_key  = "ssh-ed25519 AAAA... p040-staging"
   credit_backed_paid_account_confirmed = true
   credit_expiry_date                   = "2026-11-13"
   teardown_deadline                    = "2026-11-08"

   # Shared ephemeral runners có outbound IP thay đổi; SSH được khóa bằng key-only.
   ssh_source_ranges = ["0.0.0.0/0"]
   ```

   Giữ `credit_backed_paid_account_confirmed=false` cho tới khi đã nhìn thấy credit còn lại
   và chấp nhận Paid account risk. Terraform từ chối plan/apply nếu cờ chưa là `true`, hoặc
   nếu chạy sau deadline 08/11/2026.

5. Khởi tạo, kiểm tra và đọc kỹ plan:

   ```powershell
   terraform -chdir=infra/gcp init
   terraform -chdir=infra/gcp validate
   terraform -chdir=infra/gcp plan -out=p040-staging.tfplan
   ```

Plan hợp lệ chỉ gồm project `p040-staging-<suffix>`, API cần thiết, custom VPC/subnet,
firewall 22/80/443, budget 7.897.351 VND (giá trị Welcome credit được Console hiển thị)
và đúng một VM `e2-medium` với boot disk 30 GB
`pd-standard` tại `asia-southeast1-b`. VM dùng ephemeral IPv4; không được xuất hiện static
address, load balancer, Cloud SQL, snapshot schedule hoặc storage bucket.

6. Chỉ sau khi xác minh credit và chấp nhận Paid account risk, apply đúng plan đã duyệt:

   ```powershell
   terraform -chdir=infra/gcp apply p040-staging.tfplan
   terraform -chdir=infra/gcp output
   ```

Terraform phải khai báo budget bằng VND vì đó là currency của billing account. Tổng budget
7.897.351 VND và các threshold theo tỷ lệ vẫn xấp xỉ 1, 50, 200 và 280 USD, đồng thời loại credit khỏi
phép tính để cảnh báo theo gross usage trước khi Welcome credit được trừ. Threshold đầu là
1/300 của budget, không phải mức phần trăm tùy ý. Budget alert không khóa tài nguyên.

## 4. Xác nhận bootstrap và hostname miễn phí

Lấy output:

```powershell
$VpsIp = terraform -chdir=infra/gcp output -raw instance_external_ip
$PublicHost = terraform -chdir=infra/gcp output -raw public_host
$PublicUrl = terraform -chdir=infra/gcp output -raw public_url
ssh -i "$env:USERPROFILE\.ssh\p040_staging" "p040-deploy@$VpsIp"
```

Hostname có dạng `api-staging.34-142-10-20.sslip.io`. `sslip.io` phân giải IP nằm trong
hostname, nên không cần mua domain. Caddy dùng cổng 80 để xin TLS HTTP-01.

Trong VM, kiểm tra bootstrap:

```bash
cat /var/log/p040-bootstrap.log
docker version
docker compose version
sudo ufw status
systemctl status p040-backup.timer --no-pager
systemctl cat p040-monitor.timer
```

Firewall Google Cloud và UFW chỉ mở TCP 22, TCP 80/443 và UDP 443. Compose không publish
port của backend hoặc PostgreSQL. Cổng 22 phải nhận được kết nối từ shared self-hosted runner có
IP thay đổi, nên SSH bắt buộc key-only, root login bị tắt và workflow pin host key.

## 5. Tạo environment files và cài deployment bundle

Từ repository trên máy cá nhân:

```powershell
tar -czf "$env:TEMP\p040-deploy.tgz" deploy scripts/vps
scp -i "$env:USERPROFILE\.ssh\p040_staging" `
  "$env:TEMP\p040-deploy.tgz" "p040-deploy@${VpsIp}:/tmp/p040-deploy.tgz"
ssh -i "$env:USERPROFILE\.ssh\p040_staging" "p040-deploy@$VpsIp" `
  "rm -rf /tmp/p040-seed && mkdir /tmp/p040-seed && tar -xzf /tmp/p040-deploy.tgz -C /tmp/p040-seed && install -m 0644 /tmp/p040-seed/deploy/compose.vps.yml /opt/p040/deploy/compose.vps.yml && install -m 0644 /tmp/p040-seed/deploy/Caddyfile /opt/p040/deploy/Caddyfile && install -m 0755 /tmp/p040-seed/scripts/vps/*.sh /opt/p040/scripts/ && install -m 0600 /tmp/p040-seed/deploy/compose.env.example /opt/p040/env/compose.env && install -m 0600 /tmp/p040-seed/deploy/backend.env.example /opt/p040/env/backend.env && sudo install -m 0644 /tmp/p040-seed/deploy/systemd/*.service /tmp/p040-seed/deploy/systemd/*.timer /etc/systemd/system/ && sudo systemctl daemon-reload"
```

Sinh secret riêng, mỗi lệnh một giá trị khác nhau:

```bash
openssl rand -hex 32  # POSTGRES_PASSWORD
openssl rand -hex 32  # SESSION_SECRET
```

Sửa `/opt/p040/env/compose.env`:

```dotenv
COMPOSE_PROJECT_NAME=p040-staging
PUBLIC_HOST=api-staging.<IP-DANG-GACH-NGANG>.sslip.io
PUBLIC_URL=https://api-staging.<IP-DANG-GACH-NGANG>.sslip.io
ACME_EMAIL=<EMAIL-NHAN-CANH-BAO-TLS>
BACKEND_ENV_FILE=/opt/p040/env/backend.env
POSTGRES_USER=p040_app
POSTGRES_PASSWORD=<RANDOM-SECRET>
POSTGRES_DB=pgonboarding
BACKUP_RETENTION_COUNT=3
```

Sửa `/opt/p040/env/backend.env`:

```dotenv
APP_ENV=production
DATABASE_URL=postgresql+asyncpg://p040_app:<CUNG-DB-PASSWORD>@db:5432/pgonboarding
SESSION_SECRET=<RANDOM-SECRET-KHAC>
ALLOW_HEADER_USER_CONTEXT=false
USE_FAKE_EMBEDDER=false
CORS_ORIGINS=https://<FRONTEND-ORIGIN-THAT>
```

Điền thêm Cloudinary, GitHub sync, embedding và LLM credentials cần thiết. Không đưa các
giá trị thật vào Git, history shell hoặc workflow log.

User `p040-deploy` có Docker và passwordless sudo để vận hành VM; cả hai đều tương đương
quyền root. Private key phải chỉ nằm trên máy quản trị và GitHub Environment.

Đăng nhập private GHCR một lần trên VM bằng personal access token chỉ có `read:packages`:

```bash
docker login ghcr.io
```

Nếu GitHub Environment/runner chưa dùng được và chưa có PAT `read:packages` riêng, không
chép token GitHub CLI nhiều quyền lên VM. Có thể chuyển image đã build qua SSH, chạy
`docker load`, lấy trường `.Id` bằng `docker image inspect`, rồi gọi `deploy.sh` với ID dạng
`sha256:<64-hex>`. Script chỉ chấp nhận image ID content-addressed đã tồn tại local; đường
deploy tự động vẫn bắt buộc GHCR digest.

Wrapper lặp lại quy trình này mà không truyền GitHub token:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\gcp\deploy-local.ps1 `
  -ImageTag "manual-$(Get-Date -Format yyyyMMddHHmmss)" `
  -VpsHost $VpsIp `
  -SshKeyPath "$env:USERPROFILE\.ssh\p040_staging" `
  -KnownHostsPath "$env:USERPROFILE\.ssh\known_hosts" `
  -PublicUrl $PublicUrl
```

`known_hosts` phải chứa host key đã đối chiếu fingerprint trước đó. Wrapper build `linux/amd64`,
stream image qua SSH, so sánh toàn bộ RootFS layer digest ở hai phía, cài bundle, deploy bằng
image ID local và gọi smoke test public.

Tạo credential local từ template rồi điền giá trị thật trước khi truyền một lần qua SSH:

```powershell
Copy-Item staging.secrets.env.example staging.secrets.env
powershell -ExecutionPolicy Bypass -File scripts\gcp\configure-staging-secrets.ps1 `
  -SecretsPath .\staging.secrets.env `
  -VpsHost $VpsIp `
  -SshKeyPath "$env:USERPROFILE\.ssh\p040_staging" `
  -KnownHostsPath "$env:USERPROFILE\.ssh\known_hosts" `
  -PublicUrl $PublicUrl
```

Không commit `staging.secrets.env`, không đưa secret vào command line hoặc log. Cập nhật
`/opt/p040/env/backend.env` bằng file tạm có quyền `0600`, sau đó recreate backend.

Nếu staging cũ có dữ liệu cần giữ, tạm dừng thao tác ghi, tạo `pg_dump -Fc` từ PostgreSQL
hiện tại, tải dump/checksum vào `/opt/p040/backups` rồi restore trước khi chuyển frontend:

```bash
/opt/p040/scripts/restore-db.sh /opt/p040/backups/pgonboarding-TIMESTAMP.dump --confirm-restore
```

Ghi lại Alembic revision và row counts trước/sau. Nếu staging cũ không có dữ liệu cần giữ,
khởi tạo database rỗng bằng release migration là đủ.

## 5.1. Deploy frontend trên Vercel

Frontend không chạy trên VPS. GitHub organization không cho phép cài Vercel GitHub App, nên
deploy tự động dùng Vercel CLI với token chuyên dụng thay vì Git integration. Project Vercel
được link với root `frontend`; file `frontend/vercel.json` cố định build bằng `npm ci` và chọn
region Singapore (`sin1`).

Tạo token Vercel riêng cho CI, scope team `T040`, không tái sử dụng token CLI cá nhân. Đặt
token vào biến môi trường `P040_VERCEL_TOKEN`, rồi cấu hình GitHub Environments mà không đưa
token lên command line hoặc log:

```powershell
$env:P040_VERCEL_TOKEN = Get-Clipboard
powershell -ExecutionPolicy Bypass -File scripts\gcp\configure-github-vercel.ps1
Remove-Item Env:P040_VERCEL_TOKEN
Set-Clipboard $null
```

Script tạo `vercel-preview` chỉ cho `develop`, bổ sung Vercel credentials vào `staging` chỉ
cho `main`, và lưu `VERCEL_ORG_ID`/`VERCEL_PROJECT_ID` dưới dạng variables. Workflow pull
request không nhận Vercel token. Preview chỉ deploy sau khi code đã merge vào `develop`;
Production chỉ deploy sau khi backend `main` đã sẵn sàng trên VPS.

Lệnh cấu hình GitHub Environments phải chạy bằng tài khoản có quyền repository admin. GitHub
trả `404` cho API environment khi token chỉ có quyền contributor/write; không được coi đó là
environment chưa tồn tại rồi tìm cách bỏ qua branch policy.

Tạo biến môi trường cho **Production** và **Preview** khi cần:

```dotenv
API_UPSTREAM_URL=https://api-staging.<IP-DANG-GACH-NGANG>.sslip.io
NEXT_PUBLIC_DEMO_USER_ID=9
NEXT_PUBLIC_CONSOLE_DEMO_USER_ID=1
```

Không đặt `NEXT_PUBLIC_API_URL`. Trình duyệt gọi API bằng đường dẫn tương đối và rewrite
trong `frontend/next.config.ts` chuyển tiếp `/api/:path*` sang `API_UPSTREAM_URL`. Đây là
yêu cầu bắt buộc, không phải tối ưu: cookie phiên là `SameSite=Lax` và host-only, nên nếu
trình duyệt gọi thẳng domain API thì request là cross-site, `Set-Cookie` bị bỏ và đăng nhập
trả 200 nhưng không có phiên. Proxy làm cookie thành first-party trên domain Vercel, nhờ đó
`frontend/src/middleware.ts` cũng đọc được cookie để gác route.

Vì mọi request tới backend giờ phát sinh từ server của Vercel chứ không từ trình duyệt,
`CORS_ORIGINS` không còn tham gia luồng đăng nhập. Vẫn nên giữ origin Vercel trong danh sách
để chẩn đoán bằng lệnh gọi trực tiếp:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\gcp\configure-staging-cors.ps1 `
  -FrontendUrl "https://<PROJECT>.vercel.app" `
  -VpsHost $VpsIp `
  -SshKeyPath "$env:USERPROFILE\.ssh\p040_staging" `
  -KnownHostsPath "$env:USERPROFILE\.ssh\known_hosts"
```

Script giữ hai origin localhost cho phát triển local, thêm origin Vercel, cập nhật file env
bằng thao tác atomic với quyền `0600`, recreate riêng backend và chờ healthcheck. Không truyền
secret hay GitHub token.

Kiểm thử theo thứ tự: mở URL Vercel, đăng nhập/session, gọi một API có credentials, upload
Cloudinary và truy xuất RAG. Sau khi đăng nhập, kiểm tra DevTools → Application → Cookies:
`ralion_session` phải nằm dưới domain `.vercel.app`, không phải domain API. Chỉ sau khi các
kiểm thử này pass mới tắt hoặc xóa Render.

## 6. Tạo GitHub Environment staging

Lấy host key rồi so fingerprint trước khi lưu:

```powershell
$ScannedHostKey = ssh-keyscan -p 22 $VpsIp 2>$null
$ScannedHostKey | ssh-keygen -lf -
ssh -i "$env:USERPROFILE\.ssh\p040_staging" "p040-deploy@$VpsIp" `
  "ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub"
```

Hai fingerprint Ed25519 phải giống nhau. Sau đó chạy script cấu hình environment:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\gcp\configure-github-staging.ps1 `
  -VpsHost $VpsIp `
  -PublicUrl $PublicUrl `
  -SshKeyPath "$env:USERPROFILE\.ssh\p040_staging" `
  -VerifiedSshHostKey ($ScannedHostKey -join "`n")
```

Script tạo GitHub Environment `staging`, chỉ cho branch `main` deploy và đặt:

- Secrets: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, `VPS_SSH_HOST_KEY`.
- Variables: `VPS_PORT=22`, `PUBLIC_URL`.

Script `configure-github-vercel.ps1` bổ sung `VERCEL_TOKEN`, `VERCEL_ORG_ID` và
`VERCEL_PROJECT_ID` mà không thay đổi các VPS secrets ở trên.

Không dùng `StrictHostKeyChecking=no`. Nếu ephemeral IP đổi, phải cập nhật `PUBLIC_HOST`,
`PUBLIC_URL`, Caddy hostname, `VPS_HOST`, pinned host key và GitHub variable `PUBLIC_URL`.

## 7. Deploy lần đầu

1. Merge feature PR vào `develop` sau khi CI pass.
2. Mở PR `develop -> main` và kiểm tra lại VM/environment.
3. Merge vào `main` để release workflow build image `linux/amd64` và deploy digest bất biến.
4. Theo dõi `Verify release`, `Publish immutable container image`, `Deploy staging VPS`.

Release cài và bật cả `p040-backup.timer` lẫn `p040-monitor.timer`. Không cài GitHub Actions
runner lên VPS; VM chỉ chạy application, database, proxy và các timer vận hành.

Sau deploy:

```powershell
curl.exe --fail "$PublicUrl/health"
curl.exe --fail "$PublicUrl/ready"
ssh -i "$env:USERPROFILE\.ssh\p040_staging" "p040-deploy@$VpsIp" `
  "cd /opt/p040 && docker compose --env-file env/compose.env -f deploy/compose.vps.yml ps"
```

Kiểm tra từ Internet chỉ thấy 22, 80 và 443; database/backend không có public port. Kiểm
thử login, session, Cloudinary, GitHub sync, embedding và RAG. Reboot VM một lần và xác nhận
containers cùng `/ready` tự phục hồi. Thực hiện ba merge/deploy staging liên tiếp thành công.

Rollback thủ công về image trước:

```bash
PREVIOUS_IMAGE="$(cat /opt/p040/state/previous-image)"
/opt/p040/scripts/deploy.sh "$PREVIOUS_IMAGE"
```

Rollback không downgrade database; migration phải theo expand-contract.

Chỉ suspend/xóa Render sau khi toàn bộ checklist pass và VPS đã ổn định. Khi đó xóa Render
deploy hook/registry credential cũ; không giữ secret `RENDER_DEPLOY_HOOK_URL` trong GitHub.

## 8. Backup miễn phí và restore drill

Timer chạy hằng ngày lúc khoảng 02:00 UTC và giữ ba dump mới nhất cùng checksum:

```bash
systemctl list-timers p040-backup.timer
sudo systemctl start p040-backup.service
sudo journalctl -u p040-backup.service --since today
ls -lh /opt/p040/backups
```

Mỗi tuần tải bản mới nhất về máy cá nhân:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\gcp\download-latest-backup.ps1 `
  -VpsHost $VpsIp `
  -SshKeyPath "$env:USERPROFILE\.ssh\p040_staging" `
  -KnownHostsPath "$env:USERPROFILE\.ssh\known_hosts"
```

Script tải cả `.dump` và `.sha256`, rồi từ chối bản sao sai checksum. Thư mục `backups/`
được Git ignore. Có thể tạo Windows Task Scheduler để chạy lệnh này mỗi tuần khi máy bật.

Mỗi tháng restore thử bản đã tải vào một ParadeDB tmpfs local, không đụng database
development:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\gcp\restore-backup-local.ps1 `
  -BackupPath backups\p040-staging\pgonboarding-TIMESTAMP.dump
```

Script verify checksum, restore custom-format dump, đọc `alembic_version` rồi xóa container
tạm. Với restore thật trên VPS, dùng `scripts/vps/restore-db.sh --confirm-restore`; thao tác
đó destructive đối với database đích.

Dữ liệu trên boot disk không phải bản backup độc lập; bản tải về máy cá nhân mới là bản
off-VM trong phương án không dùng object storage này.

## 9. Theo dõi chi phí và tài nguyên

- `p040-monitor.timer` chạy mỗi 5 phút, kiểm tra HTTPS qua Caddy, `/health`, `/ready` và fail
  nếu root disk vượt 70%. Xem lần gần nhất bằng:

  ```bash
  systemctl list-timers p040-monitor.timer
  systemctl status p040-monitor.service --no-pager
  cat /opt/p040/state/last-monitor
  sudo journalctl -u p040-monitor.service --since today
  ```

- GitHub workflow `Manually check staging VPS` chỉ dùng khi cần kiểm tra từ Internet; nó
  không chạy theo lịch và không phải thành phần bắt buộc của monitoring.
- Sau mỗi deploy, script dọn Docker images không dùng cũ hơn 7 ngày.
- Kiểm tra định kỳ bằng `docker stats --no-stream`, `df -h` và Google Cloud Billing Reports.
- Không tạo thêm service ngoài Terraform plan đã duyệt.
- Không stop/start VM tùy tiện vì ephemeral IP có thể thay đổi.
- Budget 7.897.351 VND với các mốc tỷ lệ xấp xỉ 1/50/200/280 USD chỉ cảnh báo. Muốn chặn
  chắc chắn phải chủ động destroy project.

## 10. Lịch thoát credit bắt buộc

- **18/10/2026**: ghi CPU, RAM, disk và credit đã dùng.
- **29/10/2026**: tạo full dump, tải về máy và chọn server kế tiếp.
- **02/11/2026**: restore thử sang server kế tiếp.
- **05/11/2026**: chuyển traffic khỏi Google Cloud.
- **08/11/2026**: tải dump/checksum cuối, xác minh restore, rồi xóa hạ tầng:

  ```powershell
  terraform -chdir=infra/gcp plan -destroy
  terraform -chdir=infra/gcp destroy
  ```

Sau `destroy`, kiểm tra Google Cloud Console không còn VM, disk, reserved IP hoặc project
liên quan. Terraform state có thể chứa metadata nhạy cảm và không được commit.

## 11. Definition of done

- Ruff, Alembic và toàn bộ pytest pass trên local Docker và shared self-hosted CI.
- `main` tự deploy staging qua shared ephemeral runner, không cần máy cá nhân.
- `/health` và `/ready` trả 200 qua HTTPS sslip.io.
- PostgreSQL và FastAPI không public port.
- Login/session/Cloudinary/GitHub sync/embedding/RAG pass.
- Reboot không mất database; ba auto-deploy liên tiếp pass; rollback image pass.
- Backup hằng ngày giữ ba bản, backup tuần đã tải/verify và restore drill tháng pass.
- Disk alert >70%, Docker image cleanup và budget alerts hoạt động.
- Có full backup và hạ tầng được chuyển/xóa chậm nhất ngày 08/11/2026.

Tham khảo: [Google Cloud Free Program](https://docs.cloud.google.com/free/docs/free-cloud-features),
[Google Cloud budgets](https://docs.cloud.google.com/billing/docs/how-to/budgets) và
[sslip.io](https://sslip.io/).
