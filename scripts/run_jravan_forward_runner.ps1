param(
    [int]$BankrollYen = 100000,
    [int]$MinLeadMinutes = 10,
    [string]$ValidationOutput = "artifacts/jravan_forward_runner_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

function Test-UsableFile {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    return (Get-Item -LiteralPath $Path).Length -gt 0
}

function Write-Validation {
    param([hashtable]$Payload)
    $path = Join-Path $ProjectRoot $ValidationOutput
    $dir = Split-Path -Parent $path
    if (-not [string]::IsNullOrWhiteSpace($dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    $Payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $path -Encoding UTF8
}

if ($BankrollYen -le 0) { throw "BankrollYen must be positive." }
if ($MinLeadMinutes -lt 0) { throw "MinLeadMinutes must be non-negative." }

Write-Host "=== HorseRacingPredictions JRA-VAN FREE-FIRST Forward Paper ==="

$historyPath = Join-Path $ProjectRoot "data\jravan\full\current_history.csv"
$historySummaryPath = Join-Path $ProjectRoot "artifacts\jravan_full\pipeline_summary.json"
if (-not (Test-UsableFile $historyPath)) {
    throw "current_history.csv is missing. Complete the JRA-VAN Resume workflow first."
}

$venvPython = Join-Path $ProjectRoot ".venv-jravan\Scripts\python.exe"
if (-not (Test-UsableFile $venvPython)) {
    throw ".venv-jravan is missing. Complete the JRA-VAN Resume workflow on this runner first."
}

Write-Host "[1/4] Refreshing local project package"
& $venvPython -m pip install -e ".[research]"
if ($LASTEXITCODE -ne 0) { throw "Project installation failed." }

Write-Host "[2/4] Capturing future entries and free-trial realtime odds"
$inputArgs = @(
    "scripts\jravan_trial_forward.py",
    "--history", $historyPath,
    "--history-summary", $historySummaryPath,
    "--min-lead-minutes", [string]$MinLeadMinutes
)
& $venvPython @inputArgs
if ($LASTEXITCODE -ne 0) {
    throw "JRA-VAN trial forward input preparation failed."
}

$inputSummaryPath = Join-Path $ProjectRoot "artifacts\jravan_forward\trial_forward_input_summary.json"
if (-not (Test-UsableFile $inputSummaryPath)) {
    throw "trial_forward_input_summary.json was not created."
}
$inputSummary = Get-Content -LiteralPath $inputSummaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
$commit = (& git rev-parse HEAD).Trim()

$baseValidation = @{
    validated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    commit_sha = $commit
    runner_os = $env:RUNNER_OS
    runner_arch = $env:RUNNER_ARCH
    input_status = [string]$inputSummary.status
    history_cutoff = [string]$inputSummary.history_cutoff
    current_week_rows = [int]$inputSummary.current_week_rows
    current_week_races = [int]$inputSummary.current_week_races
    future_entry_rows = [int]$inputSummary.future_entry_rows
    future_entry_races = [int]$inputSummary.future_entry_races
    odds_rows = [int]$inputSummary.odds_rows
    odds_races = [int]$inputSummary.odds_races
    skipped_races_no_complete_odds = [int]$inputSummary.skipped_races_no_complete_odds
    earliest_post_time = $inputSummary.earliest_post_time
    latest_post_time = $inputSummary.latest_post_time
    decision_time = $inputSummary.decision_time
    forward_paper_executed = $false
}

if ($inputSummary.status -ne "ready") {
    Write-Validation -Payload $baseValidation
    Write-Host "Forward Paper safely deferred: $($inputSummary.status)"
    if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_STEP_SUMMARY)) {
        @(
            "### JRA-VAN Forward Paper",
            "",
            "- input_status: $($inputSummary.status)",
            "- history_cutoff: $($inputSummary.history_cutoff)",
            "- future_entry_races: $($inputSummary.future_entry_races)",
            "- odds_races: $($inputSummary.odds_races)",
            "- forward_paper_executed: false"
        ) | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding UTF8
    }
    exit 0
}

$championDir = Join-Path $ProjectRoot "artifacts\champion_v7"
$modelPath = Join-Path $championDir "model.cbm"
$manifestPath = Join-Path $championDir "manifest.json"

Write-Host "[3/4] Ensuring frozen Champion v7 artifact"
if (-not (Test-UsableFile $modelPath) -or -not (Test-UsableFile $manifestPath)) {
    $championArgs = @(
        "scripts\train_champion_artifact.py",
        "--start", "2017-01-01",
        "--end", "2021-07-31",
        "--output-dir", $championDir
    )
    & $venvPython @championArgs
    if ($LASTEXITCODE -ne 0) { throw "Champion v7 artifact build failed." }
}

$entriesPath = Join-Path $ProjectRoot "data\jravan\forward\future_entries.csv"
$oddsPath = Join-Path $ProjectRoot "data\jravan\forward\odds_snapshots.csv"
if (-not (Test-UsableFile $entriesPath)) {
    throw "future_entries.csv is missing despite ready input status."
}
if (-not (Test-UsableFile $oddsPath)) {
    throw "odds_snapshots.csv is missing despite ready input status."
}

Write-Host "[4/4] Running PaperBroker-only forward pipeline"
$forwardOutputDir = Join-Path $ProjectRoot "artifacts\forward_paper"
$ledgerPath = Join-Path $ProjectRoot "data\paper\paper_trading.sqlite3"
$forwardArgs = @(
    "scripts\run_forward_paper.py",
    "--history", $historyPath,
    "--entries", $entriesPath,
    "--artifact-dir", $championDir,
    "--odds", $oddsPath,
    "--ledger", $ledgerPath,
    "--output-dir", $forwardOutputDir,
    "--bankroll-yen", [string]$BankrollYen,
    "--decision-time", [string]$inputSummary.decision_time
)
& $venvPython @forwardArgs
if ($LASTEXITCODE -ne 0) { throw "Forward Paper pipeline failed." }

$forwardSummaryPath = Join-Path $forwardOutputDir "forward_paper_summary.json"
if (-not (Test-UsableFile $forwardSummaryPath)) {
    throw "forward_paper_summary.json was not created."
}
$forwardSummary = Get-Content -LiteralPath $forwardSummaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
$evaluations = @($forwardSummary.paper_result.evaluations)
$accepted = @($evaluations | Where-Object { $_.accepted -eq $true })

$baseValidation.forward_paper_executed = $true
$baseValidation.model_version = [string]$forwardSummary.model_version
$baseValidation.experiment_id = [string]$forwardSummary.experiment_id
$baseValidation.paper_evaluations = [int]$evaluations.Count
$baseValidation.paper_accepted_bets = [int]$accepted.Count
$baseValidation.committed_stake_yen = [int]$forwardSummary.paper_result.committed_stake_yen
$baseValidation.remaining_uncommitted_bankroll_yen = [int]$forwardSummary.paper_result.remaining_uncommitted_bankroll_yen
Write-Validation -Payload $baseValidation

if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_STEP_SUMMARY)) {
    @(
        "### JRA-VAN Forward Paper",
        "",
        "- input_status: ready",
        "- history_cutoff: $($inputSummary.history_cutoff)",
        "- future_entry_races: $($inputSummary.future_entry_races)",
        "- odds_races: $($inputSummary.odds_races)",
        "- model_version: $($forwardSummary.model_version)",
        "- paper_evaluations: $($evaluations.Count)",
        "- paper_accepted_bets: $($accepted.Count)",
        "- committed_stake_yen: $($forwardSummary.paper_result.committed_stake_yen)",
        "- forward_paper_executed: true"
    ) | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding UTF8
}

Write-Host "JRA-VAN FREE-FIRST Forward Paper PASS."
Write-Host "paper_evaluations=$($evaluations.Count)"
Write-Host "paper_accepted_bets=$($accepted.Count)"
Write-Host "committed_stake_yen=$($forwardSummary.paper_result.committed_stake_yen)"
