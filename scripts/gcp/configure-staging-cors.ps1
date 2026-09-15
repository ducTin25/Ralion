[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [uri]$FrontendUrl,

    [Parameter(Mandatory = $true)]
    [string]$VpsHost,

    [Parameter(Mandatory = $true)]
    [string]$SshKeyPath,

    [string]$VpsUser = "p040-deploy",
    [int]$Port = 22,
    [string]$KnownHostsPath = (Join-Path $env:USERPROFILE ".ssh\known_hosts")
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $SshKeyPath -PathType Leaf)) {
    throw "SSH private key not found: $SshKeyPath"
}
if (-not (Test-Path -LiteralPath $KnownHostsPath -PathType Leaf)) {
    throw "Pinned known_hosts file not found: $KnownHostsPath"
}

$frontendOrigin = $FrontendUrl.AbsoluteUri.TrimEnd('/')
if ($frontendOrigin -notmatch '^https://[a-z0-9][a-z0-9-]{0,62}\.vercel\.app$') {
    throw "FrontendUrl must be a Vercel HTTPS origin such as https://p040-frontend.vercel.app."
}

$resolvedKey = (Resolve-Path -LiteralPath $SshKeyPath).Path
$resolvedKnownHosts = (Resolve-Path -LiteralPath $KnownHostsPath).Path
$target = "${VpsUser}@${VpsHost}"
$sshArgs = @(
    '-o', 'BatchMode=yes',
    '-o', 'StrictHostKeyChecking=yes',
    '-o', 'KexAlgorithms=curve25519-sha256',
    '-o', "UserKnownHostsFile=$resolvedKnownHosts",
    '-p', "$Port",
    '-i', $resolvedKey
)

# The origin has already passed a strict allow-list, so it is safe to embed it in
# the remote script. No secret is sent or printed by this operation.
$remoteScript = @'
set -Eeuo pipefail
frontend_origin='__FRONTEND_ORIGIN__'
env_file=/opt/p040/env/backend.env
test -f "$env_file"
tmp_env="$(mktemp /opt/p040/env/backend.env.XXXXXX)"
cleanup() { rm -f -- "$tmp_env"; }
trap cleanup EXIT

cors_value=""
while IFS= read -r line; do
  case "$line" in
    CORS_ORIGINS=*) cors_value="${line#CORS_ORIGINS=}" ;;
  esac
done < "$env_file"

if [ -z "$cors_value" ]; then
  cors_value="http://localhost:3000,http://127.0.0.1:3000"
fi
case ",$cors_value," in
  *,"$frontend_origin",*) ;;
  *) cors_value="$cors_value,$frontend_origin" ;;
esac

while IFS= read -r line; do
  case "$line" in
    CORS_ORIGINS=*) printf 'CORS_ORIGINS=%s\n' "$cors_value" ;;
    *) printf '%s\n' "$line" ;;
  esac
done < "$env_file" > "$tmp_env"

chmod 0600 "$tmp_env"
mv -f -- "$tmp_env" "$env_file"
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
echo "CORS updated for Vercel origin."
'@.Replace('__FRONTEND_ORIGIN__', $frontendOrigin)

$remoteScript | & ssh @sshArgs $target 'bash -s'
if ($LASTEXITCODE -ne 0) {
    throw "CORS update or backend restart failed with exit code $LASTEXITCODE."
}

Write-Host "Staging CORS now allows $frontendOrigin (localhost origins retained)."
