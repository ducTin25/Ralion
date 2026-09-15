[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BackupPath,

    [string]$ContainerName = "p040-local-restore-drill"
)

$ErrorActionPreference = "Stop"
$resolvedBackup = (Resolve-Path -LiteralPath $BackupPath -ErrorAction Stop).Path
$checksumPath = "${resolvedBackup}.sha256"

if (-not (Test-Path -LiteralPath $checksumPath -PathType Leaf)) {
    throw "Checksum file not found: $checksumPath"
}
if ($resolvedBackup -notmatch '\.dump$') {
    throw "BackupPath must point to a custom-format .dump file."
}

$expectedHash = ((Get-Content -LiteralPath $checksumPath -Raw).Trim() -split '\s+')[0]
$actualHash = (Get-FileHash -LiteralPath $resolvedBackup -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -ne $expectedHash.ToLowerInvariant()) {
    throw "Checksum mismatch for $resolvedBackup."
}

$existingContainer = docker container ls --all --quiet --filter "name=^/${ContainerName}$"
if ($LASTEXITCODE -ne 0) {
    throw "Could not check whether container '$ContainerName' already exists."
}
if (-not [string]::IsNullOrWhiteSpace(($existingContainer | Out-String))) {
    throw "Container '$ContainerName' already exists; refusing to reuse or remove it."
}

$created = $false
try {
    docker run --detach --rm --name $ContainerName `
        --tmpfs /var/lib/postgresql/data `
        --env POSTGRES_USER=app `
        --env POSTGRES_PASSWORD=app `
        --env POSTGRES_DB=pgonboarding_restore `
        paradedb/paradedb:v0.23.4-pg16 `
        postgres -c shared_preload_libraries=pg_search,pg_cron | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not start the restore-drill database." }
    $created = $true

    $ready = $false
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        docker exec $ContainerName test -f /var/lib/postgresql/data/postmaster.pid *> $null
        if ($LASTEXITCODE -ne 0) {
            Start-Sleep -Seconds 2
            continue
        }

        $postmasterPid = docker exec $ContainerName head -n 1 `
            /var/lib/postgresql/data/postmaster.pid
        if ($LASTEXITCODE -ne 0 -or ($postmasterPid | Out-String).Trim() -ne "1") {
            Start-Sleep -Seconds 2
            continue
        }

        docker exec $ContainerName pg_isready -U app -d pgonboarding_restore *> $null
        if ($LASTEXITCODE -ne 0) {
            Start-Sleep -Seconds 2
            continue
        }

        $pgSearchReady = docker exec $ContainerName psql --tuples-only --no-align `
            --username=app --dbname=pgonboarding_restore `
            --command="SELECT 1 FROM pg_extension WHERE extname = 'pg_search';"
        if ($LASTEXITCODE -eq 0 -and ($pgSearchReady | Out-String).Trim() -eq "1") {
            $ready = $true
            break
        }
        Start-Sleep -Seconds 2
    }
    if (-not $ready) { throw "Restore-drill database did not become ready." }

    docker cp $resolvedBackup "${ContainerName}:/tmp/restore.dump"
    if ($LASTEXITCODE -ne 0) { throw "Could not copy the dump into the test container." }

    docker exec $ContainerName pg_restore --clean --if-exists --no-owner --no-privileges `
        --username=app --dbname=pgonboarding_restore /tmp/restore.dump
    if ($LASTEXITCODE -ne 0) { throw "pg_restore failed." }

    $revision = docker exec $ContainerName psql --tuples-only --no-align `
        --username=app --dbname=pgonboarding_restore `
        --command="SELECT version_num FROM alembic_version ORDER BY version_num;"
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace(($revision | Out-String))) {
        throw "Restore completed but the Alembic revision could not be verified."
    }

    Write-Host "Restore drill passed. Alembic revision(s): $($revision -join ', ')"
}
finally {
    if ($created) {
        docker rm --force $ContainerName *> $null
    }
}
