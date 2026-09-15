[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-z0-9][a-z0-9_.-]{0,127}$')]
    [string]$ImageTag,

    [Parameter(Mandatory = $true)]
    [string]$VpsHost,

    [Parameter(Mandatory = $true)]
    [string]$SshKeyPath,

    [Parameter(Mandatory = $true)]
    [uri]$PublicUrl,

    [string]$VpsUser = "p040-deploy",
    [int]$Port = 22,
    [string]$KnownHostsPath = (Join-Path $env:USERPROFILE ".ssh\known_hosts"),
    [string]$RepositoryRoot
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepositoryRoot)) {
    $RepositoryRoot = Join-Path $PSScriptRoot "..\.."
}

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Command failed with exit code $LASTEXITCODE."
    }
}

function Quote-CmdArgument {
    param([Parameter(Mandatory = $true)][string]$Value)

    return '"' + $Value.Replace('"', '\"') + '"'
}

if (-not (Test-Path -LiteralPath $SshKeyPath -PathType Leaf)) {
    throw "SSH private key not found: $SshKeyPath"
}
if (-not (Test-Path -LiteralPath $KnownHostsPath -PathType Leaf)) {
    throw "Pinned known_hosts file not found: $KnownHostsPath"
}
if (-not (Test-Path -LiteralPath $RepositoryRoot -PathType Container)) {
    throw "Repository root not found: $RepositoryRoot"
}
if ($PublicUrl.AbsoluteUri -notmatch '^https://api-staging\.\d{1,3}(-\d{1,3}){3}\.sslip\.io/?$') {
    throw "PublicUrl must use https://api-staging.<hyphenated-IP>.sslip.io."
}

$resolvedKey = (Resolve-Path -LiteralPath $SshKeyPath).Path
$resolvedKnownHosts = (Resolve-Path -LiteralPath $KnownHostsPath).Path
$resolvedRoot = (Resolve-Path -LiteralPath $RepositoryRoot).Path
$localImage = "p040-local:$ImageTag"
$target = "${VpsUser}@${VpsHost}"
$sshArgs = @(
    '-o', 'BatchMode=yes',
    '-o', 'StrictHostKeyChecking=yes',
    '-o', "UserKnownHostsFile=$resolvedKnownHosts",
    '-p', "$Port",
    '-i', $resolvedKey
)
$scpArgs = @(
    '-o', 'BatchMode=yes',
    '-o', 'StrictHostKeyChecking=yes',
    '-o', "UserKnownHostsFile=$resolvedKnownHosts",
    '-P', "$Port",
    '-i', $resolvedKey
)
$archivePath = Join-Path $env:TEMP "p040-deploy-$ImageTag.tgz"

try {
    Push-Location $resolvedRoot

    Write-Host "Building linux/amd64 image $localImage"
    Invoke-Native -Command 'docker' -Arguments @('build', '--platform', 'linux/amd64', '--tag', $localImage, '.')

    $localImageId = (& docker image inspect --format '{{.Id}}' $localImage).Trim()
    if ($LASTEXITCODE -ne 0 -or $localImageId -notmatch '^sha256:[a-f0-9]{64}$') {
        throw "Could not resolve a content-addressed local image ID."
    }

    Write-Host "Streaming image to $target over pinned SSH"
    $quotedSshArgs = ($sshArgs | ForEach-Object { Quote-CmdArgument $_ }) -join ' '
    $streamCommand = "docker save $(Quote-CmdArgument $localImage) | ssh $quotedSshArgs $(Quote-CmdArgument $target) docker load"
    Invoke-Native -Command 'cmd.exe' -Arguments @('/d', '/s', '/c', $streamCommand)

    $remoteImageId = (& ssh @sshArgs $target "docker image inspect --format '{{.Id}}' '$localImage'").Trim()
    if ($LASTEXITCODE -ne 0 -or $remoteImageId -notmatch '^sha256:[a-f0-9]{64}$') {
        throw "Could not resolve the loaded image ID on the VPS."
    }
    $localLayers = (& docker image inspect --format '{{json .RootFS.Layers}}' $localImage).Trim()
    $remoteLayers = (& ssh @sshArgs $target "docker image inspect --format '{{json .RootFS.Layers}}' '$localImage'").Trim()
    if ($LASTEXITCODE -ne 0 -or $localLayers -ne $remoteLayers) {
        throw "RootFS layer verification failed after image transfer."
    }

    if (Test-Path -LiteralPath $archivePath) {
        Remove-Item -LiteralPath $archivePath -Force
    }
    Invoke-Native -Command 'tar' -Arguments @('-czf', $archivePath, 'deploy', 'scripts/vps')
    Invoke-Native -Command 'scp' -Arguments ($scpArgs + @($archivePath, "${target}:/tmp/p040-deploy.tgz"))

    $remoteInstall = @'
set -Eeuo pipefail
seed_dir="$(mktemp -d /tmp/p040-release.XXXXXX)"
cleanup() { rm -rf -- "$seed_dir" /tmp/p040-deploy.tgz; }
trap cleanup EXIT
tar -xzf /tmp/p040-deploy.tgz -C "$seed_dir"
sed -i 's/\r$//' "$seed_dir"/scripts/vps/*.sh
install -m 0644 "$seed_dir/deploy/compose.vps.yml" /opt/p040/deploy/compose.vps.yml
install -m 0644 "$seed_dir/deploy/Caddyfile" /opt/p040/deploy/Caddyfile
install -m 0755 "$seed_dir"/scripts/vps/*.sh /opt/p040/scripts/
sudo install -m 0644 "$seed_dir"/deploy/systemd/*.service "$seed_dir"/deploy/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now p040-backup.timer p040-monitor.timer
'@
    $remoteInstall = $remoteInstall.Replace("`r`n", "`n")
    Invoke-Native -Command 'ssh' -Arguments ($sshArgs + @($target, $remoteInstall))
    Invoke-Native -Command 'ssh' -Arguments ($sshArgs + @($target, "/opt/p040/scripts/deploy.sh $remoteImageId"))

    $healthUrl = ([uri]::new($PublicUrl.AbsoluteUri.TrimEnd('/') + '/health')).AbsoluteUri
    $readyUrl = ([uri]::new($PublicUrl.AbsoluteUri.TrimEnd('/') + '/ready')).AbsoluteUri
    Invoke-Native -Command 'curl.exe' -Arguments @('--fail', '--silent', '--show-error', $healthUrl)
    Invoke-Native -Command 'curl.exe' -Arguments @('--fail', '--silent', '--show-error', $readyUrl)
    Write-Host "Local VPS deployment passed: $remoteImageId"
}
finally {
    Pop-Location
    if (Test-Path -LiteralPath $archivePath) {
        Remove-Item -LiteralPath $archivePath -Force
    }
}
