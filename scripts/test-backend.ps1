param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $repoRoot "docker-compose.test.yml"
$projectName = "p040-member-test"

Set-Location $repoRoot

try {
    Write-Host "[test] Building the production image from the current source"
    docker compose build backend
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    docker compose --project-name $projectName --file $composeFile up `
        --build --abort-on-container-exit --exit-code-from backend-test
    if ($LASTEXITCODE -ne 0) {
        $composeExitCode = $LASTEXITCODE
        docker compose --project-name $projectName --file $composeFile logs --no-color
        exit $composeExitCode
    }
}
finally {
    docker compose --project-name $projectName --file $composeFile down --volumes `
        --remove-orphans | Out-Null
}
