[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SecretsPath,

    [Parameter(Mandatory = $true)]
    [string]$VpsHost,

    [Parameter(Mandatory = $true)]
    [string]$SshKeyPath,

    [Parameter(Mandatory = $true)]
    [uri]$PublicUrl,

    [string]$VpsUser = "p040-deploy",
    [int]$Port = 22,
    [string]$KnownHostsPath = (Join-Path $env:USERPROFILE ".ssh\known_hosts")
)

$ErrorActionPreference = "Stop"
$allowedKeys = @(
    'BGE_M3_ENDPOINT',
    'BGE_M3_API_KEY',
    'DEEPSEEK_API_KEY',
    'LANGFUSE_PUBLIC_KEY',
    'LANGFUSE_SECRET_KEY',
    'LANGFUSE_HOST',
    'CLOUDINARY_CLOUD_NAME',
    'CLOUDINARY_API_KEY',
    'CLOUDINARY_API_SECRET',
    'GITHUB_CREDENTIAL_ENCRYPTION_KEY'
)
$requiredKeys = @(
    'BGE_M3_ENDPOINT',
    'BGE_M3_API_KEY',
    'DEEPSEEK_API_KEY',
    'LANGFUSE_PUBLIC_KEY',
    'LANGFUSE_SECRET_KEY',
    'LANGFUSE_HOST',
    'CLOUDINARY_CLOUD_NAME',
    'CLOUDINARY_API_KEY',
    'CLOUDINARY_API_SECRET',
    'GITHUB_CREDENTIAL_ENCRYPTION_KEY'
)

if (-not (Test-Path -LiteralPath $SecretsPath -PathType Leaf)) {
    throw "Secrets file not found: $SecretsPath"
}
if (-not (Test-Path -LiteralPath $SshKeyPath -PathType Leaf)) {
    throw "SSH private key not found: $SshKeyPath"
}
if (-not (Test-Path -LiteralPath $KnownHostsPath -PathType Leaf)) {
    throw "Pinned known_hosts file not found: $KnownHostsPath"
}
if ($PublicUrl.AbsoluteUri -notmatch '^https://api-staging\.\d{1,3}(-\d{1,3}){3}\.sslip\.io/?$') {
    throw "PublicUrl must use https://api-staging.<hyphenated-IP>.sslip.io."
}

$entries = @{}
foreach ($line in Get-Content -LiteralPath $SecretsPath) {
    if ([string]::IsNullOrWhiteSpace($line) -or $line.TrimStart().StartsWith('#')) {
        continue
    }
    if ($line -notmatch '^([A-Z][A-Z0-9_]*)=(.*)$') {
        throw "Invalid secrets line; expected KEY=value."
    }
    $key = $Matches[1]
    if ($key -notin $allowedKeys) {
        throw "Key '$key' is not permitted by this transfer script."
    }
    if ($entries.ContainsKey($key)) {
        throw "Duplicate key '$key'."
    }
    if ([string]::IsNullOrWhiteSpace($Matches[2])) {
        throw "Required key '$key' is empty."
    }
    $entries[$key] = $Matches[2]
}
foreach ($key in $requiredKeys) {
    if (-not $entries.ContainsKey($key)) {
        throw "Required key '$key' is missing."
    }
}
if ($entries['LANGFUSE_HOST'] -notmatch '^https://[^\s/]+(?:/.*)?$') {
    throw "LANGFUSE_HOST must be an HTTPS URL."
}

$resolvedKey = (Resolve-Path -LiteralPath $SshKeyPath).Path
$resolvedKnownHosts = (Resolve-Path -LiteralPath $KnownHostsPath).Path
$target = "${VpsUser}@${VpsHost}"
$sshArgs = @(
    '-o', 'BatchMode=yes',
    '-o', 'StrictHostKeyChecking=yes',
    '-o', "UserKnownHostsFile=$resolvedKnownHosts",
    '-p', "$Port",
    '-i', $resolvedKey
)
$remoteScript = @'
set -Eeuo pipefail
secret_file="$(mktemp /tmp/p040-staging-secrets.XXXXXX)"
trap 'rm -f -- "$secret_file"' EXIT
cat > "$secret_file"
chmod 0600 "$secret_file"
for key in BGE_M3_ENDPOINT BGE_M3_API_KEY DEEPSEEK_API_KEY LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY LANGFUSE_HOST CLOUDINARY_CLOUD_NAME CLOUDINARY_API_KEY CLOUDINARY_API_SECRET; do
  value="$(awk -F= -v name="$key" '$1 == name { sub(/^[^=]*=/, ""); print; exit }' "$secret_file")"
  if [ -z "$value" ]; then
    echo "Missing or empty required key: $key" >&2
    exit 1
  fi
done
langfuse_host="$(awk -F= '$1 == "LANGFUSE_HOST" { sub(/^[^=]*=/, ""); print; exit }' "$secret_file")"
case "$langfuse_host" in
  https://*) ;;
  *) echo "LANGFUSE_HOST must use HTTPS" >&2; exit 1 ;;
esac

env_file=/opt/p040/env/backend.env
tmp_env="$(mktemp /opt/p040/env/backend.env.XXXXXX)"
trap 'rm -f -- "$secret_file" "$tmp_env"' EXIT
# Remove only keys supplied by this transfer, preserve every other runtime setting, then append
# the new values. This also handles variables that did not previously exist in backend.env.
awk -F= 'NR==FNR { supplied[$1]=1; next } !($1 in supplied) { print }' \
  "$secret_file" "$env_file" > "$tmp_env"
cat "$secret_file" >> "$tmp_env"
chmod 0600 "$tmp_env"
mv -f -- "$tmp_env" "$env_file"
unset value langfuse_host
cd /opt/p040
export BACKEND_IMAGE="$(cat state/current-image)"
docker compose --env-file env/compose.env -f deploy/compose.vps.yml up -d --force-recreate --no-deps backend
for attempt in $(seq 1 30); do
  status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' p040-staging-backend-1)"
  [ "$status" = healthy ] && break
  [ "$attempt" = 30 ] && exit 1
  sleep 2
done
test "$(stat -c %a "$env_file")" = 600
'@
$remoteScript = $remoteScript -replace "`r`n", "`n"

Get-Content -LiteralPath $SecretsPath -Raw -Encoding utf8 | & ssh @sshArgs $target $remoteScript
if ($LASTEXITCODE -ne 0) {
    throw "Secret transfer or backend restart failed with exit code $LASTEXITCODE."
}

$healthUrl = ([uri]::new($PublicUrl.AbsoluteUri.TrimEnd('/') + '/health')).AbsoluteUri
$readyUrl = ([uri]::new($PublicUrl.AbsoluteUri.TrimEnd('/') + '/ready')).AbsoluteUri
& curl.exe --fail --silent --show-error --retry 10 --retry-all-errors --retry-delay 2 $healthUrl
if ($LASTEXITCODE -ne 0) { throw "Health check failed: $healthUrl" }
& curl.exe --fail --silent --show-error --retry 10 --retry-all-errors --retry-delay 2 $readyUrl
if ($LASTEXITCODE -ne 0) { throw "Readiness check failed: $readyUrl" }
Write-Host "Staging integration secrets transferred and backend is ready."
