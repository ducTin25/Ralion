[CmdletBinding()]
param(
    [string]$Repository = "AI20K-Build-Phase-Cohort-3/P-040",
    [string]$PreviewEnvironment = "vercel-preview",
    [string]$StagingEnvironment = "staging",
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

    $existingPolicy = gh api "repos/$Repository/environments/$Name/deployment-branch-policies" `
        --jq ".branch_policies[] | select(.name == `"$Branch`" and .type == `"branch`") | .id"
    if ($LASTEXITCODE -ne 0) {
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
    Set-BranchRestrictedEnvironment -Name $StagingEnvironment -Branch "main"

    foreach ($environmentName in @($PreviewEnvironment, $StagingEnvironment)) {
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
