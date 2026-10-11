param(
    [string]$ExpectedRunnerName = "Office-PC-01-HorseRacingPredictions"
)

$ErrorActionPreference = "Stop"
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

# First perform a read-only identity/root probe. If this fails, do not attempt
# any persistence or listener change.
$probeJson = & $PersistScript -ExpectedRunnerName $ExpectedRunnerName
if ($LASTEXITCODE -ne 0) {
    throw "Runner identity/root probe failed."
}
try {
    $probe = ($probeJson | Out-String) | ConvertFrom-Json
}
catch {
    throw "Runner identity/root probe did not return valid JSON."
}

$runnerRoot = [string]$probe.runner_root
if ([string]::IsNullOrWhiteSpace($runnerRoot)) {
    throw "Runner identity/root probe did not report runner_root."
}

$runnerConfig = Join-Path $runnerRoot ".runner"
$config = Get-Content -LiteralPath $runnerConfig -Raw | ConvertFrom-Json
if ([string]$config.agentName -ne $ExpectedRunnerName) {
    throw "Runner identity changed after probe; refusing startup."
}

$persistenceStatus = "not_repaired"
$persistenceMode = [string]$probe.persistence_mode
$persistenceError = $null

# Persistence is desirable, but an Administrator-only Set-Service failure must
# not prevent recovery of the current queued job.
$repairJson = & $PersistScript -Repair -ExpectedRunnerName $ExpectedRunnerName
$repairExit = $LASTEXITCODE
if ($repairExit -eq 0) {
    try {
        $repair = ($repairJson | Out-String) | ConvertFrom-Json
        $persistenceStatus = [string]$repair.repair_status
        $persistenceMode = [string]$repair.persistence_mode
    }
    catch {
        $persistenceStatus = "repair_json_invalid"
        $persistenceError = $_.Exception.Message
    }
}
else {
    $persistenceStatus = "repair_failed_current_start_fallback"
    $persistenceError = ($repairJson | Out-String).Trim()
    Write-Warning (
        "Persistence repair failed; attempting guarded current listener " +
        "startup for the already-validated runner."
    )
}

# Always use the duplicate-safe starter after identity validation. If a Windows
# service already started the listener, the starter exits 0 without duplication.
& $StartScript -RunnerRoot $runnerRoot
if ($LASTEXITCODE -ne 0) {
    throw "Runner startup wrapper failed."
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
    persistence_mode = $persistenceMode
    persistence_repair_status = $persistenceStatus
    persistence_error = $persistenceError
    listener_pid = [int]$listener.ProcessId
    github_registration_reused = $true
    registration_token_requested = $false
    secrets_printed = $false
}

$result | ConvertTo-Json -Depth 5
