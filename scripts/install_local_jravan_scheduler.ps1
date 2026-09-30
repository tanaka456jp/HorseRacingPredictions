param(
    [string]$ExpectedComputerName = "DESKTOP-MVV1FD4",
    [string]$ValidationOutput = "artifacts/local_scheduler_install_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

if ($env:COMPUTERNAME -ne $ExpectedComputerName) {
    throw "Refusing scheduler installation on $($env:COMPUTERNAME); expected $ExpectedComputerName."
}

$wrapperPath = Join-Path $PSScriptRoot "run_local_jravan_scheduled_task.ps1"
if (-not (Test-Path -LiteralPath $wrapperPath -PathType Leaf)) {
    throw "Local scheduler wrapper is missing."
}

$powershellExe = (Get-Command powershell.exe -ErrorAction Stop).Source

function Install-Task {
    param(
        [string]$Name,
        [string]$TaskName,
        [ValidateSet("DAILY", "MINUTE")]
        [string]$Schedule,
        [string]$StartTime,
        [Nullable[int]]$Modifier,
        [string]$EndTime
    )

    $taskCommand = ('"{0}" -NoProfile -ExecutionPolicy Bypass -File "{1}" -Task {2}' -f $powershellExe, $wrapperPath, $TaskName)
    $argsList = @(
        "/Create",
        "/TN", $Name,
        "/TR", $taskCommand,
        "/SC", $Schedule,
        "/ST", $StartTime,
        "/F"
    )
    if ($null -ne $Modifier) {
        $argsList += @("/MO", [string]$Modifier.Value)
    }
    if (-not [string]::IsNullOrWhiteSpace($EndTime)) {
        $argsList += @("/ET", $EndTime)
    }

    & schtasks.exe @argsList
    if ($LASTEXITCODE -ne 0) {
        throw "schtasks /Create failed for $Name with exit code $LASTEXITCODE."
    }
}

$taskSpecs = @(
    @{
        name = "HorseRacingPredictions-ForwardPaper"
        task = "forward"
        schedule = "MINUTE"
        start = "09:17"
        modifier = 30
        end = "17:47"
        description = "Every 30 minutes 09:17-17:47 local time"
    },
    @{
        name = "HorseRacingPredictions-RealtimeSettlement"
        task = "realtime-settlement"
        schedule = "DAILY"
        start = "18:17"
        modifier = $null
        end = ""
        description = "Daily 18:17 local time"
    },
    @{
        name = "HorseRacingPredictions-IncrementalSettlement"
        task = "incremental-settlement"
        schedule = "DAILY"
        start = "20:23"
        modifier = $null
        end = ""
        description = "Daily 20:23 local time"
    },
    @{
        name = "HorseRacingPredictions-ResidualReconcile"
        task = "residual-reconcile"
        schedule = "DAILY"
        start = "21:37"
        modifier = $null
        end = ""
        description = "Daily 21:37 local time"
    }
)

foreach ($spec in $taskSpecs) {
    Install-Task -Name $spec.name -TaskName $spec.task -Schedule $spec.schedule -StartTime $spec.start -Modifier $spec.modifier -EndTime $spec.end
}

$installed = @()
foreach ($spec in $taskSpecs) {
    $task = Get-ScheduledTask -TaskName $spec.name -ErrorAction Stop
    $info = Get-ScheduledTaskInfo -TaskName $spec.name -ErrorAction Stop
    $installed += @{
        name = $spec.name
        task = $spec.task
        schedule = $spec.description
        state = [string]$task.State
        next_run_time = $info.NextRunTime.ToString("o")
        last_task_result = [int]$info.LastTaskResult
    }
}

$validation = @{
    status = "installed"
    validated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    computer_name = $env:COMPUTERNAME
    expected_computer_name = $ExpectedComputerName
    commit_sha = (& git rev-parse HEAD).Trim()
    scheduler = "Windows Task Scheduler"
    github_cron_is_primary = $false
    local_scheduler_is_primary = $true
    live_execution_enabled = $false
    tasks = $installed
}

$validationPath = Join-Path $ProjectRoot $ValidationOutput
$validationDir = Split-Path -Parent $validationPath
New-Item -ItemType Directory -Force -Path $validationDir | Out-Null
$validation | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $validationPath -Encoding UTF8

Write-Host "Local JRA-VAN scheduler installation PASS."
foreach ($task in $installed) {
    Write-Host "$($task.name): $($task.schedule); next=$($task.next_run_time)"
}
