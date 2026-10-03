param(
    [int]$Cycles = 12,
    [int]$CycleMinutes = 60,
    [string]$ExpectedComputerName = "DESKTOP-MVV1FD4",
    [string]$Version = "1.18.29",
    [string]$Model = "ollama/qwen3:8b",
    [int]$MaxConsecutiveFailures = 2,
    [string]$SummaryOutput = "artifacts/free_opencode_autonomous_dev_12h_summary.json"
)

$ErrorActionPreference = "Stop"

if ($env:COMPUTERNAME -ne $ExpectedComputerName) {
    throw "Refusing autonomous development on $($env:COMPUTERNAME); expected $ExpectedComputerName."
}
if ($Cycles -lt 1 -or $Cycles -gt 12) {
    throw "Cycles must be between 1 and 12."
}
if ($CycleMinutes -lt 30 -or $CycleMinutes -gt 120) {
    throw "CycleMinutes must be between 30 and 120."
}
if ($Version -ne "1.18.29") {
    throw "Only the pinned free OpenCode CLI version 1.18.29 is allowed."
}
if ($Model -ne "ollama/qwen3:8b") {
    throw "Only the local model ollama/qwen3:8b is allowed."
}
if ($MaxConsecutiveFailures -lt 1 -or $MaxConsecutiveFailures -gt 4) {
    throw "MaxConsecutiveFailures must be between 1 and 4."
}

foreach ($name in @(
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "GROQ_API_KEY",
    "OLLAMA_API_KEY",
    "OPENCODE_SERVER_PASSWORD",
    "OPENCODE_SERVER_USERNAME"
)) {
    Remove-Item "Env:$name" -ErrorAction SilentlyContinue
}

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot
$ControlRoot = Join-Path $env:LOCALAPPDATA "HorseRacingPredictionsAutonomousDev"
New-Item -ItemType Directory -Force -Path $ControlRoot | Out-Null
$lockPath = Join-Path $ControlRoot "orchestrator.lock"
$stopPath = Join-Path $ControlRoot "STOP"
$OpenCodePath = Join-Path $ControlRoot "opencode-cli-$Version\node_modules\opencode-ai\bin\opencode.exe"

if (-not (Test-Path -LiteralPath $OpenCodePath -PathType Leaf)) {
    throw "FREE_OPENCODE_CLI_NOT_BOOTSTRAPPED"
}
if ((Get-Item -LiteralPath $OpenCodePath).Length -lt 1000000) {
    throw "FREE_OPENCODE_CLI_BINARY_IS_PLACEHOLDER"
}

$tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 5
$modelNames = @($tags.models | ForEach-Object { [string]$_.name })
if ($modelNames -notcontains "qwen3:8b") {
    throw "Required local model qwen3:8b is not available."
}

& gh auth status --hostname github.com *> $null
if ($LASTEXITCODE -ne 0) {
    throw "GH_NOT_AUTHENTICATED"
}

$lockStream = $null
$results = @()
$consecutiveFailures = 0
$failedFast = $false
$started = [DateTimeOffset]::UtcNow
$summaryPath = Join-Path $ProjectRoot $SummaryOutput
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $summaryPath) | Out-Null

try {
    try {
        $lockStream = [System.IO.File]::Open(
            $lockPath,
            [System.IO.FileMode]::OpenOrCreate,
            [System.IO.FileAccess]::ReadWrite,
            [System.IO.FileShare]::None
        )
    } catch [System.IO.IOException] {
        throw "Another autonomous-development orchestrator is already running."
    }

    Remove-Item -LiteralPath $stopPath -Force -ErrorAction SilentlyContinue

    if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_STEP_SUMMARY)) {
        Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding UTF8 -Value "### Free OpenCode autonomous cycles"
        Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding UTF8 -Value "| Cycle | Status | Consecutive failures |"
        Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding UTF8 -Value "|---:|---|---:|"
    }

    for ($cycle = 1; $cycle -le $Cycles; $cycle++) {
        if (Test-Path -LiteralPath $stopPath) {
            $results += @{
                cycle = $cycle
                status = "stopped_by_control_file"
                message = ""
            }
            break
        }

        $cycleStart = [DateTimeOffset]::UtcNow
        $status = "success"
        $message = ""
        try {
            & (Join-Path $PSScriptRoot "run_free_opencode_dev_cycle.ps1") -Cycle $cycle -ExpectedComputerName $ExpectedComputerName -Version $Version -Model $Model
            if ($LASTEXITCODE -ne 0) {
                throw "Cycle script exited with code $LASTEXITCODE."
            }
        } catch {
            $status = "failure"
            $message = $_.Exception.Message
            Write-Error -ErrorAction Continue "Cycle $cycle failed: $message"
        }

        if ($status -eq "failure") {
            $consecutiveFailures += 1
        } else {
            $consecutiveFailures = 0
        }

        $cycleEnd = [DateTimeOffset]::UtcNow
        $results += @{
            cycle = $cycle
            status = $status
            message = $message
            started_at_utc = $cycleStart.ToString("o")
            finished_at_utc = $cycleEnd.ToString("o")
            duration_seconds = [math]::Round(($cycleEnd - $cycleStart).TotalSeconds, 3)
        }

        @{
            status = "running"
            computer_name = $env:COMPUTERNAME
            started_at_utc = $started.ToString("o")
            updated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
            cycles_requested = $Cycles
            cycles_completed = $results.Count
            provider = "ollama_local"
            model = $Model
            opencode_version = $Version
            paid_provider_used = $false
            api_key_used = $false
            codex_used = $false
            live_execution_enabled = $false
            consecutive_failures = $consecutiveFailures
            max_consecutive_failures = $MaxConsecutiveFailures
            results = $results
        } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

        Write-Host "cycle=$cycle status=$status consecutive_failures=$consecutiveFailures"
        if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_STEP_SUMMARY)) {
            Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding UTF8 -Value (
                "| $cycle | $status | $consecutiveFailures |"
            )
        }

        if ($consecutiveFailures -ge $MaxConsecutiveFailures) {
            $failedFast = $true
            Write-Error -ErrorAction Continue (
                "Stopping after $consecutiveFailures consecutive failed cycles."
            )
            break
        }

        if ($cycle -lt $Cycles -and $status -eq "success") {
            $elapsed = ([DateTimeOffset]::UtcNow - $cycleStart).TotalSeconds
            $targetSeconds = $CycleMinutes * 60
            $sleepSeconds = [math]::Max(0, [int]($targetSeconds - $elapsed))
            if ($sleepSeconds -gt 0) {
                Start-Sleep -Seconds $sleepSeconds
            }
        } elseif ($cycle -lt $Cycles -and $status -eq "failure") {
            Write-Host "Skipping cycle pacing after failure for immediate diagnostic retry."
        }
    }

    $finished = [DateTimeOffset]::UtcNow
    $successfulCycles = @($results | Where-Object { $_.status -eq "success" }).Count
    $failedCycles = @($results | Where-Object { $_.status -eq "failure" }).Count
    @{
        status = if ($failedFast) { "failed_fast" } elseif ($failedCycles -gt 0) { "completed_with_failures" } else { "completed" }
        computer_name = $env:COMPUTERNAME
        started_at_utc = $started.ToString("o")
        finished_at_utc = $finished.ToString("o")
        cycles_requested = $Cycles
        cycles_completed = $results.Count
        successful_cycles = $successfulCycles
        failed_cycles = $failedCycles
        provider = "ollama_local"
        model = $Model
        opencode_version = $Version
        paid_provider_used = $false
        api_key_used = $false
        codex_used = $false
        live_execution_enabled = $false
        consecutive_failures = $consecutiveFailures
        max_consecutive_failures = $MaxConsecutiveFailures
        failed_fast = $failedFast
        results = $results
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

    if ($failedFast) {
        throw "Free OpenCode autonomous development stopped after $consecutiveFailures consecutive failed cycles."
    }
    if ($failedCycles -gt 0) {
        throw "Free OpenCode autonomous development completed with $failedCycles failed cycle(s)."
    }
} finally {
    if ($null -ne $lockStream) {
        $lockStream.Dispose()
    }
}
