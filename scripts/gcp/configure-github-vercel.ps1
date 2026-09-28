[CmdletBinding()]
param(
    [string]$Repository = "ducTin25/Ralion",
    [string]$PreviewEnvironment = "vercel-preview",
    [string]$ProductionEnvironment = "production",
    [string]$VercelOrgId = "team_dOaspeSFsU5d7Crxr9ixRtKE",
    [string]$VercelProjectId = "prj_RhrXAGiULSQVL6rB7X0b0l2sMeNc"
)

$ErrorActionPreference = "Stop"
$vercelToken = $env:P040_VERCEL_TOKEN

if ([string]::IsNullOrWhiteSpace($vercelToken)) {
    throw "P040_VERCEL_TOKEN must contain the dedicated Vercel CI token."
}

function Set-BranchRestrictedEnvironment {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [string]$Branch
    )

    $payload = @{
        wait_timer               = 0
        prevent_self_review      = $false
        reviewers                = @()
        deployment_branch_policy = @{
            protected_branches     = $false
            custom_branch_policies = $true
        }
    } | ConvertTo-Json -Depth 4 -Compress

    $payload | gh api --method PUT "repos/$Repository/environments/$Name" --input - | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Could not create or update GitHub Environment '$Name'."
    }

    $existingPolicy = $null
    $branchPoliciesReady = $false
    for ($attempt = 1; $attempt -le 10; $attempt++) {
        $policyResponse = gh api "repos/$Repository/environments/$Name/deployment-branch-policies"
        if ($LASTEXITCODE -eq 0) {
            $existingPolicy = ($policyResponse | ConvertFrom-Json).branch_policies |
                Where-Object { $_.name -eq $Branch -and $_.type -eq "branch" } |
                Select-Object -First 1 -ExpandProperty id
            $branchPoliciesReady = $true
            break
        }
        if ($attempt -lt 10) {
            Start-Sleep -Seconds 2
        }
    }
    if (-not $branchPoliciesReady) {
        throw "Could not read branch policies for GitHub Environment '$Name'."
    }
    if ([string]::IsNullOrWhiteSpace(($existingPolicy | Out-String))) {
        gh api --method POST "repos/$Repository/environments/$Name/deployment-branch-policies" `
            -f name=$Branch -f type=branch | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Could not restrict GitHub Environment '$Name' to branch '$Branch'."
        }
    }
}

try {
    Set-BranchRestrictedEnvironment -Name $PreviewEnvironment -Branch "develop"
    Set-BranchRestrictedEnvironment -Name $ProductionEnvironment -Branch "main"

    foreach ($environmentName in @($PreviewEnvironment, $ProductionEnvironment)) {
        $vercelToken | gh secret set VERCEL_TOKEN --env $environmentName --repo $Repository
        if ($LASTEXITCODE -ne 0) {
            throw "Could not set VERCEL_TOKEN in GitHub Environment '$environmentName'."
        }

        gh variable set VERCEL_ORG_ID --env $environmentName --repo $Repository --body $VercelOrgId
        if ($LASTEXITCODE -ne 0) {
            throw "Could not set VERCEL_ORG_ID in GitHub Environment '$environmentName'."
        }

        gh variable set VERCEL_PROJECT_ID --env $environmentName --repo $Repository --body $VercelProjectId
        if ($LASTEXITCODE -ne 0) {
            throw "Could not set VERCEL_PROJECT_ID in GitHub Environment '$environmentName'."
        }
    }
}
finally {
    $vercelToken = $null
    Remove-Item Env:P040_VERCEL_TOKEN -ErrorAction SilentlyContinue
}

Write-Host "Vercel CI environments are configured for develop Preview and main Production deployments."
