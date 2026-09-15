param(
    [switch]$SkipDocker
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $python = "python"
}

Write-Host "[ci] Ruff"
& $python -m ruff check src tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[ci] Pytest"
& $python -m pytest tests -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($SkipDocker) {
    Write-Host "[ci] Docker check skipped"
    exit 0
}

$image = "p040:local-ci"
$container = "p040-local-ci"
$existingContainer = docker ps -aq --filter "name=^/$container$"
if ($existingContainer) {
    docker rm --force $container | Out-Null
}

try {
    Write-Host "[ci] Docker build"
    docker build -t $image .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "[ci] Container smoke test"
    docker run --detach --name $container --publish 18000:8000 --env APP_ENV=test $image | Out-Null
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    $healthy = $false
    for ($attempt = 1; $attempt -le 20; $attempt++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:18000/health" -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                Write-Host "[ci] Health check passed"
                $healthy = $true
                break
            }
        } catch {
            # The application may still be starting.
        }
        Start-Sleep -Seconds 2
    }

    if (-not $healthy) {
        docker logs $container
        throw "Container health check failed"
    }
}
finally {
    $runningContainer = docker ps -aq --filter "name=^/$container$"
    if ($runningContainer) {
        docker rm --force $container | Out-Null
    }
}

Write-Host "[ci] All checks passed"
