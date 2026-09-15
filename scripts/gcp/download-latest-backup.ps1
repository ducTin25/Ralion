[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$VpsHost,

    [Parameter(Mandatory = $true)]
    [string]$SshKeyPath,

    [string]$VpsUser = "p040-deploy",
    [int]$Port = 22,
    [string]$KnownHostsPath = (Join-Path $env:USERPROFILE ".ssh\known_hosts"),
    [string]$Destination = (Join-Path (Get-Location) "backups\p040-staging")
)

$ErrorActionPreference = "Stop"
$remoteBackupDir = "/opt/p040/backups"
$sshTarget = "${VpsUser}@${VpsHost}"
$sshOptions = @(
    '-o', 'StrictHostKeyChecking=yes',
    '-o', "UserKnownHostsFile=$KnownHostsPath",
    '-p', "$Port",
    '-i', $SshKeyPath
)
$scpOptions = @(
    '-o', 'StrictHostKeyChecking=yes',
    '-o', "UserKnownHostsFile=$KnownHostsPath",
    '-P', "$Port",
    '-i', $SshKeyPath
)

if (-not (Test-Path -LiteralPath $SshKeyPath -PathType Leaf)) {
    throw "SSH private key not found: $SshKeyPath"
}
if (-not (Test-Path -LiteralPath $KnownHostsPath -PathType Leaf)) {
    throw "Pinned known_hosts file not found: $KnownHostsPath"
}

$latestBackup = & ssh @sshOptions $sshTarget `
    "find '$remoteBackupDir' -maxdepth 1 -type f -name 'pgonboarding-*.dump' -printf '%f\n' | sort -r | head -n 1"
if ($LASTEXITCODE -ne 0) {
    throw "Could not list backups on $sshTarget."
}

$latestBackup = $latestBackup.Trim()
if ($latestBackup -notmatch '^pgonboarding-\d{8}T\d{6}Z\.dump$') {
    throw "No valid daily backup was found on the VPS."
}

New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$localBackup = Join-Path $Destination $latestBackup
$localChecksum = "${localBackup}.sha256"

& scp @scpOptions `
    "${sshTarget}:${remoteBackupDir}/${latestBackup}" $localBackup
if ($LASTEXITCODE -ne 0) {
    throw "Backup download failed."
}

& scp @scpOptions `
    "${sshTarget}:${remoteBackupDir}/${latestBackup}.sha256" $localChecksum
if ($LASTEXITCODE -ne 0) {
    throw "Checksum download failed."
}

$expectedHash = ((Get-Content -LiteralPath $localChecksum -Raw).Trim() -split '\s+')[0]
$actualHash = (Get-FileHash -LiteralPath $localBackup -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -ne $expectedHash.ToLowerInvariant()) {
    throw "Checksum mismatch for $localBackup."
}

Write-Host "Verified backup downloaded to $localBackup"
