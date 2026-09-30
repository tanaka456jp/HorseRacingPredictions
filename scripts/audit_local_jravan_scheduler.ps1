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
    $tasks += @{
        name = $name
        state = [string]$task.State
        last_run_time = $info.LastRunTime.ToString("o")
        next_run_time = $info.NextRunTime.ToString("o")
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

$validation = @{
    status = "audited"
    validated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    computer_name = $env:COMPUTERNAME
    commit_sha = (& git rev-parse HEAD).Trim()
    local_scheduler_is_primary = $true
    live_execution_enabled = $false
    tasks = $tasks
    heartbeats = $heartbeats
}

$validationPath = Join-Path $ProjectRoot $ValidationOutput
$validationDir = Split-Path -Parent $validationPath
New-Item -ItemType Directory -Force -Path $validationDir | Out-Null
$validation | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $validationPath -Encoding UTF8

Write-Host "Local JRA-VAN scheduler audit PASS."
foreach ($heartbeat in $heartbeats) {
    Write-Host "$($heartbeat.task): $($heartbeat.status)"
}
