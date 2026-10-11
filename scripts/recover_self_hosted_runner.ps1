param(
    [string]$ExpectedRunnerName = "Office-PC-01-HorseRacingPredictions"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PersistScript = Join-Path $PSScriptRoot "ensure_self_hosted_runner_persistence.ps1"
$StartScript = Join-Path $PSScriptRoot "start_self_hosted_runner_if_needed.ps1"

if (-not (Test-Path -LiteralPath $PersistScript -PathType Leaf)) {
    throw "Runner persistence script is missing: $PersistScript"
}
if (-not (Test-Path -LiteralPath $StartScript -PathType Leaf)) {
    throw "Runner startup script is missing: $StartScript"
}

Write-Host "=== HorseRacingPredictions self-hosted runner recovery ==="
Write-Host "Expected runner: $ExpectedRunnerName"

$json = & $PersistScript -Repair -ExpectedRunnerName $ExpectedRunnerName
if ($LASTEXITCODE -ne 0) {
    throw "Runner persistence repair failed."
}

try {
    $state = ($json | Out-String) | ConvertFrom-Json
}
catch {
    throw "Runner persistence repair did not return valid JSON."
}

$runnerRoot = [string]$state.runner_root
if ([string]::IsNullOrWhiteSpace($runnerRoot)) {
    throw "Runner persistence repair did not report runner_root."
}

$runnerConfig = Join-Path $runnerRoot ".runner"
$config = Get-Content -LiteralPath $runnerConfig -Raw | ConvertFrom-Json
if ([string]$config.agentName -ne $ExpectedRunnerName) {
    throw "Runner identity changed after repair; refusing startup."
}

if ([string]$state.persistence_mode -eq "hkcu_logon_wrapper") {
    & $StartScript -RunnerRoot $runnerRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Runner startup wrapper failed."
    }
}

$deadline = (Get-Date).AddSeconds(15)
$listener = $null
do {
    $listener = Get-CimInstance Win32_Process -Filter "Name='Runner.Listener.exe'" |
        Where-Object {
            -not [string]::IsNullOrWhiteSpace([string]$_.ExecutablePath) -and
            [System.IO.Path]::GetFullPath([string]$_.ExecutablePath).StartsWith(
                [System.IO.Path]::GetFullPath($runnerRoot),
                [System.StringComparison]::OrdinalIgnoreCase
            )
        } |
        Select-Object -First 1
    if ($null -ne $listener) {
        break
    }
    Start-Sleep -Seconds 1
} while ((Get-Date) -lt $deadline)

if ($null -eq $listener) {
    throw "Runner.Listener.exe did not start within 15 seconds."
}

$result = [ordered]@{
    status = "runner_listener_running"
    runner_name = $ExpectedRunnerName
    runner_root = $runnerRoot
    persistence_mode = [string]$state.persistence_mode
    persistence_repair_status = [string]$state.repair_status
    listener_pid = [int]$listener.ProcessId
    github_registration_reused = $true
    registration_token_requested = $false
    secrets_printed = $false
}

$result | ConvertTo-Json -Depth 5
