param(
    [int]$Cycles = 12,
    [int]$CycleMinutes = 60,
    [string]$ExpectedComputerName = "DESKTOP-MVV1FD4",
    [string]$SummaryOutput = "artifacts/autonomous_dev_12h_summary.json"
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

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot
$ControlRoot = Join-Path $env:LOCALAPPDATA "HorseRacingPredictionsAutonomousDev"
New-Item -ItemType Directory -Force -Path $ControlRoot | Out-Null
$lockPath = Join-Path $ControlRoot "orchestrator.lock"
$stopPath = Join-Path $ControlRoot "STOP"
$CodexPath = Join-Path $env:LOCALAPPDATA "Programs\OpenAI\Codex\codex.exe"

Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue

if (-not (Test-Path -LiteralPath $CodexPath -PathType Leaf)) {
    throw "CODEX_NOT_INSTALLED"
}
& $CodexPath login status *> $null
if ($LASTEXITCODE -ne 0) {
    $blocked = @{
        status = "blocked_codex_login"
        computer_name = $env:COMPUTERNAME
        api_key_used = $false
        live_execution_enabled = $false
        cycles_requested = $Cycles
        cycles_completed = 0
    }
    $summaryPath = Join-Path $ProjectRoot $SummaryOutput
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $summaryPath) | Out-Null
    $blocked | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $summaryPath -Encoding UTF8
    throw "CODEX_NOT_AUTHENTICATED: sign into Codex CLI with ChatGPT on PC1."
}

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
        throw "Another autonomous-development orchestrator is already running."
    }

    Remove-Item -LiteralPath $stopPath -Force -ErrorAction SilentlyContinue
    $started = [DateTimeOffset]::UtcNow
    $results = @()

    for ($cycle = 1; $cycle -le $Cycles; $cycle++) {
        if (Test-Path -LiteralPath $stopPath) {
            $results += @{
                cycle = $cycle
                status = "stopped_by_control_file"
            }
            break
        }

        $cycleStart = [DateTimeOffset]::UtcNow
        $status = "success"
        $message = ""
        try {
            & (Join-Path $PSScriptRoot "run_autonomous_dev_cycle.ps1") -Cycle $cycle -ExpectedComputerName $ExpectedComputerName
            if ($LASTEXITCODE -ne 0) {
                throw "Cycle script exited with code $LASTEXITCODE."
            }
        } catch {
            $status = "failure"
            $message = $_.Exception.Message
            Write-Error -ErrorAction Continue "Cycle $cycle failed: $message"
        }
        $cycleEnd = [DateTimeOffset]::UtcNow
        $results += @{
            cycle = $cycle
            status = $status
            message = $message
            started_at_utc = $cycleStart.ToString("o")
            finished_at_utc = $cycleEnd.ToString("o")
            duration_seconds = [math]::Round(
                ($cycleEnd - $cycleStart).TotalSeconds,
                3
            )
        }

        $summaryPath = Join-Path $ProjectRoot $SummaryOutput
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $summaryPath) | Out-Null
        @{
            status = "running"
            computer_name = $env:COMPUTERNAME
            started_at_utc = $started.ToString("o")
            updated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
            cycles_requested = $Cycles
            cycles_completed = $results.Count
            api_key_used = $false
            live_execution_enabled = $false
            results = $results
        } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

        if ($cycle -lt $Cycles) {
            $elapsed = ([DateTimeOffset]::UtcNow - $cycleStart).TotalSeconds
            $targetSeconds = $CycleMinutes * 60
            $sleepSeconds = [math]::Max(0, [int]($targetSeconds - $elapsed))
            if ($sleepSeconds -gt 0) {
                Start-Sleep -Seconds $sleepSeconds
            }
        }
    }

    $finished = [DateTimeOffset]::UtcNow
    $summaryPath = Join-Path $ProjectRoot $SummaryOutput
    @{
        status = "completed"
        computer_name = $env:COMPUTERNAME
        started_at_utc = $started.ToString("o")
        finished_at_utc = $finished.ToString("o")
        cycles_requested = $Cycles
        cycles_completed = $results.Count
        successful_cycles = @($results | Where-Object { $_.status -eq "success" }).Count
        failed_cycles = @($results | Where-Object { $_.status -eq "failure" }).Count
        api_key_used = $false
        live_execution_enabled = $false
        results = $results
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding UTF8
} finally {
    if ($null -ne $lockStream) {
        $lockStream.Dispose()
    }
}
