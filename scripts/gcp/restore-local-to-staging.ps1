[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$DumpPath,
    [Parameter(Mandatory = $true)]
    [string]$VpsHost,
    [Parameter(Mandatory = $true)]
    [string]$SshKeyPath,
    [string]$VpsUser = "p040-deploy",
    [int]$Port = 22,
    [string]$KnownHostsPath = (Join-Path $env:USERPROFILE ".ssh\known_hosts"),
    [switch]$ConfirmStagingReplace
)

$ErrorActionPreference = "Stop"
if (-not $ConfirmStagingReplace) {
    throw "This operation replaces the staging database. Re-run with -ConfirmStagingReplace after verifying the target host."
}
if (-not (Test-Path -LiteralPath $DumpPath -PathType Leaf)) { throw "Dump file not found: $DumpPath" }
if ((Get-Item -LiteralPath $DumpPath).Length -le 0) { throw "Dump file is empty: $DumpPath" }
if (-not (Test-Path -LiteralPath $SshKeyPath -PathType Leaf)) { throw "SSH private key not found: $SshKeyPath" }
if (-not (Test-Path -LiteralPath $KnownHostsPath -PathType Leaf)) { throw "Pinned known_hosts file not found: $KnownHostsPath" }

$resolvedDump = (Resolve-Path -LiteralPath $DumpPath).Path
$resolvedKey = (Resolve-Path -LiteralPath $SshKeyPath).Path
$resolvedKnownHosts = (Resolve-Path -LiteralPath $KnownHostsPath).Path
$target = "${VpsUser}@${VpsHost}"
$remoteDump = "/opt/p040/backups/local-sync-pgonboarding.dump"
$remotePartialDump = "$remoteDump.partial"
$sshArgs = @('-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','KexAlgorithms=curve25519-sha256','-o',"UserKnownHostsFile=$resolvedKnownHosts",'-p',"$Port",'-i',$resolvedKey)
$scpArgs = @('-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','KexAlgorithms=curve25519-sha256','-o',"UserKnownHostsFile=$resolvedKnownHosts",'-P',"$Port",'-i',$resolvedKey)

$localHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $resolvedDump).Hash.ToLowerInvariant()
Write-Host "Local dump SHA256: $localHash"
& ssh @sshArgs $target "rm -f '$remotePartialDump'"
if ($LASTEXITCODE -ne 0) { throw "Could not prepare the remote upload path." }
& scp @scpArgs $resolvedDump "${target}:$remotePartialDump"
if ($LASTEXITCODE -ne 0) { throw "Dump upload failed with exit code $LASTEXITCODE." }
$remoteHash = (& ssh @sshArgs $target "sha256sum '$remotePartialDump'").Trim().Split(' ')[0]
if ($LASTEXITCODE -ne 0 -or $remoteHash -ne $localHash) { throw "Remote dump checksum mismatch. Local=$localHash Remote=$remoteHash" }
& ssh @sshArgs $target "mv '$remotePartialDump' '$remoteDump'"
if ($LASTEXITCODE -ne 0) { throw "Could not finalize the verified remote dump." }

# Stream the remote script through stdin so PowerShell does not reinterpret shell quotes.
$remoteScript = @'
set -Eeuo pipefail
cd /opt/p040
set -a
source env/compose.env
set +a
compose=(docker compose --env-file env/compose.env -f deploy/compose.vps.yml)
export BACKEND_IMAGE="$(cat state/current-image)"
backup_dir=/opt/p040/backups
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
safety_backup="$backup_dir/pre-local-restore-$timestamp.dump"
safety_partial="$safety_backup.partial"
restore_complete=false
cleanup() {
  status=$?
  rm -f "$safety_partial"
  if [ "$status" -ne 0 ] && [ "$restore_complete" != true ]; then
    echo "Restore failed. Recovery backup: $safety_backup" >&2
    "${compose[@]}" up -d backend caddy >/dev/null 2>&1 || true
  fi
  exit "$status"
}
trap cleanup EXIT

test -s /opt/p040/backups/local-sync-pgonboarding.dump
"${compose[@]}" config --quiet
"${compose[@]}" exec -T db pg_isready --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" >/dev/null
"${compose[@]}" exec -T db pg_dump --format=custom --no-owner --no-privileges --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" >"$safety_partial"
test -s "$safety_partial"
mv "$safety_partial" "$safety_backup"
sha256sum "$safety_backup" >"$safety_backup.sha256"
echo "Created recovery backup: $safety_backup"

"${compose[@]}" stop backend || true
"${compose[@]}" exec -T db psql --username="$POSTGRES_USER" --dbname=postgres --set=ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS \"$POSTGRES_DB\" WITH (FORCE);" </dev/null
"${compose[@]}" exec -T db psql --username="$POSTGRES_USER" --dbname=postgres --set=ON_ERROR_STOP=1 -c "CREATE DATABASE \"$POSTGRES_DB\" OWNER \"$POSTGRES_USER\";" </dev/null
"${compose[@]}" exec -T db psql --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --set=ON_ERROR_STOP=1 -c "DROP EXTENSION IF EXISTS pg_search CASCADE; DROP EXTENSION IF EXISTS vector CASCADE; DROP SCHEMA IF EXISTS paradedb CASCADE;" </dev/null
cat /opt/p040/backups/local-sync-pgonboarding.dump | "${compose[@]}" exec -T db pg_restore --exit-on-error --no-owner --no-privileges --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"
"${compose[@]}" run --rm migrate </dev/null
"${compose[@]}" up -d backend caddy </dev/null
for attempt in $(seq 1 45); do
  status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' p040-staging-backend-1)"
  [ "$status" = healthy ] && break
  [ "$attempt" = 45 ] && { docker logs --tail 80 p040-staging-backend-1 >&2 || true; exit 1; }
  sleep 2
done
"${compose[@]}" exec -T db psql --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --tuples-only --no-align --set=ON_ERROR_STOP=1 -c "SELECT 'users=' || count(*) FROM users;" </dev/null
restore_complete=true
echo "Database replacement restore completed."
'@.Replace("`r`n", "`n")

$remoteScript | & ssh @sshArgs $target 'bash -s'
if ($LASTEXITCODE -ne 0) { throw "Database restore failed with exit code $LASTEXITCODE. Staging backend may remain stopped; inspect the output above." }
Write-Host "Local database restored to staging successfully."
