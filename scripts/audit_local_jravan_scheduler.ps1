param(
    [string]$ExpectedComputerName = "DESKTOP-MVV1FD4",
    [string]$ValidationOutput = "artifacts/local_scheduler_audit_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

if ($env:COMPUTERNAME -ne $ExpectedComputerName) {
    throw "Refusing scheduler audit on $($env:COMPUTERNAME); expected $ExpectedComputerName."
}

$names = @(
    "HorseRacingPredictions-ForwardPaper",
    "HorseRacingPredictions-RealtimeSettlement",
    "HorseRacingPredictions-IncrementalSettlement",
    "HorseRacingPredictions-ResidualReconcile"
)

$tasks = @()
foreach ($name in $names) {
    $task = Get-ScheduledTask -TaskName $name -ErrorAction Stop
    $info = Get-ScheduledTaskInfo -TaskName $name -ErrorAction Stop
    $hasRun = ([int]$info.LastTaskResult -ne 267011)
    $lastRunTime = $null
    if ($hasRun -and $null -ne $info.LastRunTime) {
        $lastRunTime = ([datetime]$info.LastRunTime).ToString("o")
    }
    $nextRunTime = $null
    if ($null -ne $info.NextRunTime) {
        $nextRunTime = ([datetime]$info.NextRunTime).ToString("o")
    }
    $tasks += @{
        name = $name
        state = [string]$task.State
        has_run = $hasRun
        last_run_time = $lastRunTime
        next_run_time = $nextRunTime
        last_task_result = [int]$info.LastTaskResult
    }
}

$heartbeatDir = Join-Path $ProjectRoot "artifacts\local_scheduler_heartbeat"
$heartbeats = @()
foreach ($taskName in @(
    "forward",
    "realtime-settlement",
    "incremental-settlement",
    "residual-reconcile"
)) {
    $path = Join-Path $heartbeatDir "$taskName.json"
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        $heartbeats += (
            Get-Content -LiteralPath $path -Raw -Encoding UTF8 |
            ConvertFrom-Json
        )
    } else {
        $heartbeats += @{
            task = $taskName
            status = "no_heartbeat_yet"
        }
    }
}


function Read-SanitizedJson {
    param(
        [string]$RelativePath
    )

    $path = Join-Path $ProjectRoot $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        return @{
            status = "missing"
            path = $RelativePath
        }
    }

    try {
        return @{
            status = "available"
            path = $RelativePath
            payload = (
                Get-Content -LiteralPath $path -Raw -Encoding UTF8 |
                ConvertFrom-Json
            )
        }
    } catch {
        return @{
            status = "invalid_json"
            path = $RelativePath
            error = $_.Exception.Message
        }
    }
}

$sanitizedValidations = @{
    forward = Read-SanitizedJson -RelativePath "artifacts\jravan_forward_runner_validation.json"
    realtime_settlement = Read-SanitizedJson -RelativePath "artifacts\jravan_realtime_settlement_runner_validation.json"
    incremental_settlement = Read-SanitizedJson -RelativePath "artifacts\jravan_incremental_runner_validation.json"
    residual_reconcile = Read-SanitizedJson -RelativePath "artifacts\residual_v12_shadow_reconcile_validation.json"
    residual_paper_evidence = Read-SanitizedJson -RelativePath "artifacts\residual_v12_paper_evidence\summary.json"
}

$validation = @{
    status = "audited"
    validated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    computer_name = $env:COMPUTERNAME
    commit_sha = (& git rev-parse HEAD).Trim()
    local_scheduler_is_primary = $true
    live_execution_enabled = $false
    tasks = $tasks
    heartbeats = $heartbeats
    sanitized_validations = $sanitizedValidations
}

$validationPath = Join-Path $ProjectRoot $ValidationOutput
$validationDir = Split-Path -Parent $validationPath
New-Item -ItemType Directory -Force -Path $validationDir | Out-Null
$validation | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $validationPath -Encoding UTF8

Write-Host "Local JRA-VAN scheduler audit PASS."
foreach ($heartbeat in $heartbeats) {
    Write-Host "$($heartbeat.task): $($heartbeat.status)"
}
foreach ($entry in $sanitizedValidations.GetEnumerator() | Sort-Object Name) {
    Write-Host "sanitized_$($entry.Name): $($entry.Value.status)"
}
