param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("forward", "realtime-settlement", "incremental-settlement", "residual-reconcile")]
    [string]$Task,
    [int]$BankrollYen = 100000,
    [int]$MinLeadMinutes = 10,
    [int]$MaxLeadMinutes = 70,
    [int]$OverlapDays = 7
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

$heartbeatDir = Join-Path $ProjectRoot "artifacts\local_scheduler_heartbeat"
New-Item -ItemType Directory -Force -Path $heartbeatDir | Out-Null
$heartbeatPath = Join-Path $heartbeatDir "$Task.json"

$lockDir = Join-Path $ProjectRoot "data\paper"
New-Item -ItemType Directory -Force -Path $lockDir | Out-Null
$lockPath = Join-Path $lockDir "jravan_scheduler.lock"

function Write-Heartbeat {
    param(
        [string]$Status,
        [datetimeoffset]$StartedAt,
        [Nullable[int]]$ExitCode,
        [string]$Message
    )

    $finished = [DateTimeOffset]::UtcNow
    $commit = ""
    try {
        $commit = (& git rev-parse HEAD).Trim()
    } catch {
        $commit = ""
    }

    @{
        task = $Task
        status = $Status
        started_at_utc = $StartedAt.ToString("o")
        finished_at_utc = $finished.ToString("o")
        duration_seconds = [math]::Round(($finished - $StartedAt).TotalSeconds, 3)
        exit_code = $ExitCode
        message = $Message
        computer_name = $env:COMPUTERNAME
        commit_sha = $commit
        live_execution_enabled = $false
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $heartbeatPath -Encoding UTF8
}

$startedAt = [DateTimeOffset]::UtcNow
$lockStream = $null

try {
    try {
        $lockStream = [System.IO.File]::Open(
            $lockPath,
            [System.IO.FileMode]::OpenOrCreate,
            [System.IO.FileAccess]::ReadWrite,
            [System.IO.FileShare]::None
        )
    } catch [System.IO.IOException] {
        Write-Heartbeat -Status "skipped_lock_busy" -StartedAt $startedAt -ExitCode 0 -Message "Another local JRA-VAN task owns the machine-local lock."
        Write-Host "Local JRA-VAN task skipped: machine-local lock is busy."
        exit 0
    }

    $powershellExe = (Get-Command powershell.exe -ErrorAction Stop).Source

    switch ($Task) {
        "forward" {
            $scriptPath = Join-Path $PSScriptRoot "run_jravan_forward_runner.ps1"
            $childArgs = @(
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File", $scriptPath,
                "-BankrollYen", [string]$BankrollYen,
                "-MinLeadMinutes", [string]$MinLeadMinutes,
                "-MaxLeadMinutes", [string]$MaxLeadMinutes
            )
        }
        "realtime-settlement" {
            $scriptPath = Join-Path $PSScriptRoot "run_jravan_realtime_settlement_runner.ps1"
            $childArgs = @(
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File", $scriptPath
            )
        }
        "incremental-settlement" {
            $scriptPath = Join-Path $PSScriptRoot "run_jravan_incremental_settlement_runner.ps1"
            $childArgs = @(
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File", $scriptPath,
                "-OverlapDays", [string]$OverlapDays
            )
        }
        "residual-reconcile" {
            $scriptPath = Join-Path $PSScriptRoot "run_residual_v12_shadow_reconcile_runner.ps1"
            $childArgs = @(
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File", $scriptPath
            )
        }
    }

    if (-not (Test-Path -LiteralPath $scriptPath -PathType Leaf)) {
        throw "Scheduled child script is missing: $scriptPath"
    }

    Write-Host "=== Local JRA-VAN scheduled task: $Task ==="
    & $powershellExe @childArgs
    $exitCode = [int]$LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "Scheduled child process failed with exit code $exitCode."
    }

    Write-Heartbeat -Status "success" -StartedAt $startedAt -ExitCode 0 -Message "Completed."
    Write-Host "Local scheduled task PASS: $Task"
} catch {
    Write-Heartbeat -Status "failure" -StartedAt $startedAt -ExitCode 1 -Message $_.Exception.Message
    throw
} finally {
    if ($null -ne $lockStream) {
        $lockStream.Dispose()
    }
}
