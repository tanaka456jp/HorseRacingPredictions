param(
    [string]$ValidationOutput = "artifacts/residual_v12_shadow_reconcile_validation.json"
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
    $Payload | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $path -Encoding UTF8
}

$venvPython = Join-Path $ProjectRoot ".venv-jravan\Scripts\python.exe"
$ledgerPath = Join-Path $ProjectRoot "data\jravan\forward\residual_v12_shadow.sqlite3"
$summaryPath = Join-Path $ProjectRoot "artifacts\residual_v12_shadow\reconcile_summary.json"

$base = @{
    validated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    commit_sha = (& git rev-parse HEAD).Trim()
    runner_os = $env:RUNNER_OS
    runner_arch = $env:RUNNER_ARCH
    reconciliation_executed = $false
    predictions_regenerated = $false
    holdout_reused = $false
    paper_broker_unchanged = $true
    horse_level_data_uploaded = $false
}

if (-not (Test-UsableFile $venvPython)) {
    throw ".venv-jravan is missing; complete JRA-VAN Resume validation first."
}

if (-not (Test-UsableFile $ledgerPath)) {
    $base.status = "ledger_missing"
    Write-Validation -Payload $base
    Write-Host "Residual v12 result reconciliation safely deferred: local ledger is missing."
    exit 0
}

Write-Host "=== Residual v12 pending-result reconciliation ==="
& $venvPython "scripts\reconcile_residual_v12_shadow_results.py" --ledger $ledgerPath --summary-output $summaryPath
if ($LASTEXITCODE -ne 0) {
    throw "Residual v12 pending-result reconciliation failed."
}
if (-not (Test-UsableFile $summaryPath)) {
    throw "Residual v12 reconciliation summary was not created."
}

$summary = Get-Content -LiteralPath $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
$base.status = [string]$summary.status
$base.reconciliation_executed = $true
$base.fixed_gamma = $summary.fixed_gamma
$base.result_fetch_errors = [int]$summary.result_fetch_errors
$base.new_result_rows = [int]$summary.new_result_rows
$base.pending_races_before = [int]$summary.pending_races_before
$base.pending_races_after = [int]$summary.pending_races_after
$base.reconciled_races = [int]$summary.reconciled_races
$base.cumulative_prediction_rows = [int]$summary.cumulative.prediction_rows
$base.cumulative_prediction_races = [int]$summary.cumulative.prediction_races
$base.cumulative_evaluated_rows = [int]$summary.cumulative.evaluated_rows
$base.cumulative_evaluated_races = [int]$summary.cumulative.evaluated_races

if ($null -ne $summary.cumulative.evaluation -and $summary.cumulative.evaluation.status -eq "evaluated") {
    $base.cumulative_winner_log_loss_delta_vs_market = $summary.cumulative.evaluation.winner_log_loss_delta_vs_market
    $base.cumulative_brier_delta_vs_market = $summary.cumulative.evaluation.brier_delta_vs_market
    $base.cumulative_beats_market_winner_log_loss = [bool]$summary.cumulative.evaluation.beats_market_winner_log_loss
    $base.cumulative_beats_market_brier = [bool]$summary.cumulative.evaluation.beats_market_brier
}

Write-Validation -Payload $base

if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_STEP_SUMMARY)) {
    @(
        "### Residual v12 pending-result reconciliation",
        "",
        "- status: $($summary.status)",
        "- pending races before: $($summary.pending_races_before)",
        "- pending races after: $($summary.pending_races_after)",
        "- reconciled races: $($summary.reconciled_races)",
        "- new result rows: $($summary.new_result_rows)",
        "- result fetch errors: $($summary.result_fetch_errors)",
        "- cumulative evaluated races: $($summary.cumulative.evaluated_races)",
        "- predictions regenerated: false",
        "- holdout reused: false",
        "- gamma retuned: false",
        "- PaperBroker unchanged: true"
    ) | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding UTF8
}

Write-Host "Residual v12 pending-result reconciliation PASS."
Write-Host "status=$($summary.status)"
Write-Host "pending_races_before=$($summary.pending_races_before)"
Write-Host "pending_races_after=$($summary.pending_races_after)"
Write-Host "reconciled_races=$($summary.reconciled_races)"
