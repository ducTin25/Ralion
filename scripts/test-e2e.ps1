param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $repoRoot "docker-compose.e2e.yml"
$frontendRoot = Join-Path $repoRoot "frontend"
$projectName = "p040-member-e2e"

Set-Location $repoRoot

try {
    docker compose --project-name $projectName --file $composeFile up --build --detach --wait
    if ($LASTEXITCODE -ne 0) {
        $composeExitCode = $LASTEXITCODE
        docker compose --project-name $projectName --file $composeFile logs --no-color
        exit $composeExitCode
    }

    $env:API_UPSTREAM_URL = "http://127.0.0.1:8001"
    Set-Location $frontendRoot
    npm run test:e2e
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Set-Location $repoRoot
    docker compose --project-name $projectName --file $composeFile down --volumes --remove-orphans | Out-Null
}
