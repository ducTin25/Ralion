[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$VpsHost,

    [Parameter(Mandatory = $true)]
    [string]$PublicUrl,

    [Parameter(Mandatory = $true)]
    [string]$SshKeyPath,

    [Parameter(Mandatory = $true)]
    [string]$VerifiedSshHostKey,

    [string]$Repository = "ducTin25/Ralion",
    [string]$VpsUser = "p040-deploy",
    [int]$Port = 22
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $SshKeyPath -PathType Leaf)) {
    throw "SSH private key not found: $SshKeyPath"
}
if ($PublicUrl -notmatch '^https://api-staging\.\d{1,3}(-\d{1,3}){3}\.sslip\.io$') {
    throw "PublicUrl must use the expected api-staging.<hyphenated-IP>.sslip.io hostname."
}
if ([string]::IsNullOrWhiteSpace($VerifiedSshHostKey)) {
    throw "VerifiedSshHostKey is required. Compare its fingerprint before running this script."
}

$environmentPayload = @{
    wait_timer               = 0
    prevent_self_review      = $false
    reviewers                = @()
    deployment_branch_policy = @{
        protected_branches     = $false
        custom_branch_policies = $true
    }
} | ConvertTo-Json -Depth 4 -Compress

$environmentPayload | gh api --method PUT `
    "repos/$Repository/environments/staging" --input - | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Could not create or update the GitHub staging environment."
}

$mainPolicy = $null
$branchPoliciesReady = $false
for ($attempt = 1; $attempt -le 10; $attempt++) {
    $policyResponse = gh api "repos/$Repository/environments/staging/deployment-branch-policies"
    if ($LASTEXITCODE -eq 0) {
        $mainPolicy = ($policyResponse | ConvertFrom-Json).branch_policies |
            Where-Object { $_.name -eq "main" -and $_.type -eq "branch" } |
            Select-Object -First 1 -ExpandProperty id
        $branchPoliciesReady = $true
        break
    }
    if ($attempt -lt 10) {
        Start-Sleep -Seconds 2
    }
}
if (-not $branchPoliciesReady) {
    throw "Could not read the staging deployment branch policies."
}
if ([string]::IsNullOrWhiteSpace(($mainPolicy | Out-String))) {
    gh api --method POST "repos/$Repository/environments/staging/deployment-branch-policies" `
        -f name=main -f type=branch | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Could not restrict staging deployments to main."
    }
}

$VpsHost | gh secret set VPS_HOST --env staging --repo $Repository
if ($LASTEXITCODE -ne 0) { throw "Could not set VPS_HOST." }
$VpsUser | gh secret set VPS_USER --env staging --repo $Repository
if ($LASTEXITCODE -ne 0) { throw "Could not set VPS_USER." }
Get-Content -LiteralPath $SshKeyPath -Raw | gh secret set VPS_SSH_KEY --env staging --repo $Repository
if ($LASTEXITCODE -ne 0) { throw "Could not set VPS_SSH_KEY." }
$VerifiedSshHostKey | gh secret set VPS_SSH_HOST_KEY --env staging --repo $Repository
if ($LASTEXITCODE -ne 0) { throw "Could not set VPS_SSH_HOST_KEY." }

gh variable set VPS_PORT --env staging --repo $Repository --body $Port
if ($LASTEXITCODE -ne 0) { throw "Could not set VPS_PORT." }
gh variable set PUBLIC_URL --env staging --repo $Repository --body $PublicUrl
if ($LASTEXITCODE -ne 0) { throw "Could not set PUBLIC_URL." }

Write-Host "GitHub Environment 'staging' is configured for main-only deployments."
