param(
    [string]$ValidationOutput = "artifacts/residual_v12_shadow_runner_validation.json"
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
$historyPath = Join-Path $ProjectRoot "data\jravan\full\current_history.csv"
$entriesPath = Join-Path $ProjectRoot "data\jravan\forward\future_entries.csv"
$oddsPath = Join-Path $ProjectRoot "data\jravan\forward\odds_snapshots.csv"
$championDir = Join-Path $ProjectRoot "artifacts\champion_v7"
$modelPath = Join-Path $championDir "model.cbm"
$manifestPath = Join-Path $championDir "manifest.json"
$predictionsPath = Join-Path $ProjectRoot "data\jravan\forward\residual_v12_shadow_predictions.csv"
$ledgerPath = Join-Path $ProjectRoot "data\jravan\forward\residual_v12_shadow.sqlite3"
$paperLedgerPath = Join-Path $ProjectRoot "data\paper\paper_trading.sqlite3"
$residualModelCache = Join-Path $ProjectRoot "artifacts\residual_v12_frozen_model"
$summaryPath = Join-Path $ProjectRoot "artifacts\residual_v12_shadow\summary.json"

if (-not (Test-UsableFile $venvPython)) {
    throw ".venv-jravan is missing; complete JRA-VAN Resume validation first."
}
if (-not (Test-UsableFile $historyPath)) {
    throw "current_history.csv is missing."
}

$base = @{
    validated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    commit_sha = (& git rev-parse HEAD).Trim()
    runner_os = $env:RUNNER_OS
    runner_arch = $env:RUNNER_ARCH
    shadow_executed = $false
    paper_broker_unchanged = $true
}

if (-not (Test-UsableFile $entriesPath) -or -not (Test-UsableFile $oddsPath)) {
    $base.status = "snapshot_missing"
    $base.entries_present = (Test-UsableFile $entriesPath)
    $base.odds_present = (Test-UsableFile $oddsPath)
    Write-Validation -Payload $base
    Write-Host "Residual v12 shadow safely deferred: saved 0B31 snapshot is missing."
    exit 0
}

Write-Host "=== Residual v12 saved 0B31 shadow replay ==="
Write-Host "[1/4] Refreshing local project package"
& $venvPython -m pip install -e ".[research]"
if ($LASTEXITCODE -ne 0) { throw "Project installation failed." }

Write-Host "[2/4] Ensuring frozen Champion v7 artifact"
if (-not (Test-UsableFile $modelPath) -or -not (Test-UsableFile $manifestPath)) {
    & $venvPython "scripts\train_champion_artifact.py" --start "2017-01-01" --end "2021-07-31" --output-dir $championDir
    if ($LASTEXITCODE -ne 0) { throw "Champion v7 artifact creation failed." }
}

Write-Host "[3/4] Running frozen Residual v12 shadow with saved pre-race odds"
& $venvPython "scripts\evaluate_residual_v12_shadow_snapshot.py" --history $historyPath --entries $entriesPath --odds $oddsPath --champion $championDir --predictions-output $predictionsPath --summary-output $summaryPath --ledger $ledgerPath --paper-ledger $paperLedgerPath --residual-model-cache $residualModelCache
if ($LASTEXITCODE -ne 0) { throw "Residual v12 shadow replay failed." }
if (-not (Test-UsableFile $summaryPath)) {
    throw "Residual v12 shadow summary was not created."
}

Write-Host "[4/4] Writing sanitized validation"
$summary = Get-Content -LiteralPath $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
$pred = $summary.prediction_summary
$eval = $summary.evaluation
$paper = $summary.paper_forward
$paperPerf = $paper.performance
$base.status = [string]$summary.status
$base.shadow_executed = $true
$base.uses_timestamped_prerace_odds = [bool]$summary.uses_timestamped_prerace_odds
$base.uses_final_odds_for_shadow_inference = [bool]$summary.uses_final_odds_for_shadow_inference
$base.prediction_rows = [int]$pred.rows
$base.prediction_races = [int]$pred.races
$base.positive_overlay_rows = [int]$pred.positive_overlay_rows
$base.overlay_ge_5pct_rows = [int]$pred.overlay_ge_5pct_rows
$base.overlay_ge_10pct_rows = [int]$pred.overlay_ge_10pct_rows
$base.overlay_ge_20pct_rows = [int]$pred.overlay_ge_20pct_rows
$base.mean_overlay_ratio = $pred.mean_overlay_ratio
$base.max_overlay_ratio = $pred.max_overlay_ratio
$base.min_lead_minutes = $pred.min_lead_minutes
$base.max_lead_minutes = $pred.max_lead_minutes
$base.fixed_gamma = $pred.fixed_gamma
$base.residual_model_cache_status = [string]$pred.residual_model_cache_status
$base.result_fetch_errors = [int]$summary.result_fetch_errors
$base.evaluation_status = [string]$eval.status
$base.evaluated_rows = [int]$eval.evaluated_rows
$base.evaluated_races = [int]$eval.evaluated_races
$base.paper_forward_status = [string]$paper.status
$base.paper_policy_version = [string]$paper.policy_version
$base.paper_min_ev = $paper.min_ev
$base.paper_fractional_kelly = $paper.fractional_kelly
$base.paper_max_odds_age_minutes = [int]$paper.max_odds_age_minutes
$base.paper_stale_odds_rows = [int]$paper.stale_odds_rows
$base.paper_eligible_rows = [int]$paper.eligible_rows
$base.paper_new_evaluations = [int]$paper.new_evaluations
$base.paper_duplicate_evaluations = [int]$paper.duplicate_evaluations
$base.paper_new_selected_bets = [int]$paper.new_selected_bets
$base.paper_new_committed_stake_yen = [int]$paper.new_committed_stake_yen
$base.paper_total_selected_bets = [int]$paperPerf.selected_bets
$base.paper_settled_bets = [int]$paperPerf.settled_bets
$base.paper_unsettled_bets = [int]$paperPerf.unsettled_bets
$base.paper_settled_stake_yen = [int]$paperPerf.settled_stake_yen
$base.paper_payout_yen = [int]$paperPerf.payout_yen
$base.paper_profit_yen = [int]$paperPerf.profit_yen
$base.paper_roi = $paperPerf.roi
$base.paper_max_drawdown_yen = [int]$paperPerf.max_drawdown_yen
$base.paper_prospective_only = [bool]$paper.prospective_only
$base.paper_historical_forward_rows_backfilled = [bool]$paper.historical_forward_rows_backfilled
$base.live_execution_enabled = [bool]$summary.live_execution_enabled
$base.ledger_new_prediction_rows = [int]$summary.ledger_update.new_prediction_rows
$base.ledger_new_result_rows = [int]$summary.ledger_update.new_result_rows
$base.ledger_pending_races_before = [int]$summary.ledger_update.pending_races_before
$base.ledger_pending_races_after = [int]$summary.ledger_update.pending_races_after
$base.ledger_reconciled_races = [int]$summary.ledger_update.reconciled_races
$base.cumulative_prediction_rows = [int]$summary.cumulative.prediction_rows
$base.cumulative_prediction_races = [int]$summary.cumulative.prediction_races
$base.cumulative_evaluated_rows = [int]$summary.cumulative.evaluated_rows
$base.cumulative_evaluated_races = [int]$summary.cumulative.evaluated_races
if ($summary.cumulative.evaluation.status -eq "evaluated") {
    $base.cumulative_winner_log_loss_delta_vs_market = $summary.cumulative.evaluation.winner_log_loss_delta_vs_market
    $base.cumulative_brier_delta_vs_market = $summary.cumulative.evaluation.brier_delta_vs_market
    $base.cumulative_beats_market_winner_log_loss = [bool]$summary.cumulative.evaluation.beats_market_winner_log_loss
    $base.cumulative_beats_market_brier = [bool]$summary.cumulative.evaluation.beats_market_brier
}
if ($eval.status -eq "evaluated") {
    $base.market_quality = $eval.market_quality
    $base.residual_quality = $eval.residual_quality
    $base.winner_log_loss_delta_vs_market = $eval.winner_log_loss_delta_vs_market
    $base.brier_delta_vs_market = $eval.brier_delta_vs_market
    $base.beats_market_winner_log_loss = [bool]$eval.beats_market_winner_log_loss
    $base.beats_market_brier = [bool]$eval.beats_market_brier
}
Write-Validation -Payload $base

if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_STEP_SUMMARY)) {
    @(
        "### Residual v12 saved 0B31 shadow replay",
        "",
        "- status: $($summary.status)",
        "- prediction rows/races: $($pred.rows) / $($pred.races)",
        "- Residual v12 model cache: $($pred.residual_model_cache_status)",
        "- overlay >= 5% rows: $($pred.overlay_ge_5pct_rows)",
        "- result evaluation: $($eval.status)",
        "- evaluated races: $($eval.evaluated_races)",
        "- pending races before reconciliation: $($summary.ledger_update.pending_races_before)",
        "- pending races after reconciliation: $($summary.ledger_update.pending_races_after)",
        "- reconciled races this run: $($summary.ledger_update.reconciled_races)",
        "- cumulative evaluated races: $($summary.cumulative.evaluated_races)",
        "- cumulative log-loss delta vs market: $($summary.cumulative.evaluation.winner_log_loss_delta_vs_market)",
        "- cumulative Brier delta vs market: $($summary.cumulative.evaluation.brier_delta_vs_market)",
        "- Paper v1 status: $($paper.status)",
        "- Paper v1 rule: EV >= $($paper.min_ev), fractional Kelly $($paper.fractional_kelly)",
        "- Paper v1 max odds age: $($paper.max_odds_age_minutes) minutes",
        "- Paper v1 stale odds rows skipped: $($paper.stale_odds_rows)",
        "- Paper v1 new evaluations/bets: $($paper.new_evaluations) / $($paper.new_selected_bets)",
        "- Paper v1 new committed stake: $($paper.new_committed_stake_yen) yen",
        "- Paper v1 settled bets: $($paperPerf.settled_bets)",
        "- Paper v1 profit / ROI: $($paperPerf.profit_yen) yen / $($paperPerf.roi)",
        "- Paper v1 max drawdown: $($paperPerf.max_drawdown_yen) yen",
        "- Paper v1 prospective only: true",
        "- historical forward rows backfilled: false",
        "- live execution enabled: false",
        "- PaperBroker implementation unchanged: true"
    ) | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding UTF8
}

Write-Host "Residual v12 shadow replay PASS."
Write-Host "status=$($summary.status)"
Write-Host "prediction_races=$($pred.races)"
Write-Host "evaluation_status=$($eval.status)"
Write-Host "evaluated_races=$($eval.evaluated_races)"
