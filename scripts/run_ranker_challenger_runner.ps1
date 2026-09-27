param(
    [string]$ValidationOutput = "artifacts/ranker_challenger_runner_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

$venvPython = Join-Path $ProjectRoot ".venv-jravan\Scripts\python.exe"
$historyPath = Join-Path $ProjectRoot "data\jravan\full\current_history.csv"
$championDir = Join-Path $ProjectRoot "artifacts\champion_v7"
$summaryPath = Join-Path $ProjectRoot "artifacts\ranker_challenger\summary.json"

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    throw ".venv-jravan is missing; complete JRA-VAN Resume validation first."
}
if (-not (Test-Path -LiteralPath $historyPath -PathType Leaf)) {
    throw "current_history.csv is missing."
}

Write-Host "=== Champion vs CatBoostRanker Challenger ==="
Write-Host "[1/4] Refreshing local project package"
& $venvPython -m pip install -e ".[research]"
if ($LASTEXITCODE -ne 0) { throw "Project installation failed." }

Write-Host "[2/4] Ensuring frozen Champion v7 artifact"
$manifestPath = Join-Path $championDir "manifest.json"
$modelPath = Join-Path $championDir "model.cbm"
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf) -or -not (Test-Path -LiteralPath $modelPath -PathType Leaf)) {
    & $venvPython "scripts\train_champion_artifact.py" --start "2017-01-01" --end "2021-07-31" --output-dir $championDir
    if ($LASTEXITCODE -ne 0) { throw "Champion v7 artifact creation failed." }
}

Write-Host "[3/4] Training and evaluating CatBoostRanker challenger"
& $venvPython "scripts\evaluate_ranker_challenger.py" --history $historyPath --champion $championDir --output $summaryPath
if ($LASTEXITCODE -ne 0) { throw "Ranker challenger research failed." }
if (-not (Test-Path -LiteralPath $summaryPath -PathType Leaf)) {
    throw "Ranker challenger summary was not created."
}

Write-Host "[4/4] Writing sanitized validation"
$summary = Get-Content -LiteralPath $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
$cmp = $summary.holdout_comparison
$validation = @{
    validated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    commit_sha = (& git rev-parse HEAD).Trim()
    runner_os = $env:RUNNER_OS
    runner_arch = $env:RUNNER_ARCH
    status = [string]$summary.status
    training = $summary.training
    evaluation = $summary.evaluation
    baseline_temperature = $cmp.baseline_temperature
    challenger_temperature = $cmp.challenger_temperature
    baseline_calibrated_winner_log_loss = $cmp.baseline_calibrated_winner_log_loss
    challenger_calibrated_winner_log_loss = $cmp.challenger_calibrated_winner_log_loss
    market_winner_log_loss = $cmp.market_winner_log_loss
    challenger_delta_vs_baseline_winner_log_loss = $cmp.challenger_delta_vs_baseline_winner_log_loss
    challenger_delta_vs_market_winner_log_loss = $cmp.challenger_delta_vs_market_winner_log_loss
    challenger_beats_baseline_winner_log_loss = $cmp.challenger_beats_baseline_winner_log_loss
    challenger_beats_market_winner_log_loss = $cmp.challenger_beats_market_winner_log_loss
    baseline_calibrated_brier = $cmp.baseline_calibrated_brier
    challenger_calibrated_brier = $cmp.challenger_calibrated_brier
    market_brier = $cmp.market_brier
    baseline_ev15_rows = $cmp.baseline_ev15_rows
    challenger_ev15_rows = $cmp.challenger_ev15_rows
    baseline_ev15_flat_roi_final_odds = $cmp.baseline_ev15_flat_roi_final_odds
    challenger_ev15_flat_roi_final_odds = $cmp.challenger_ev15_flat_roi_final_odds
}
$validationPath = Join-Path $ProjectRoot $ValidationOutput
$validationDir = Split-Path -Parent $validationPath
if (-not [string]::IsNullOrWhiteSpace($validationDir)) {
    New-Item -ItemType Directory -Force -Path $validationDir | Out-Null
}
$validation | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $validationPath -Encoding UTF8

if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_STEP_SUMMARY)) {
    @(
        "### Champion vs CatBoostRanker challenger",
        "",
        "- baseline holdout winner log-loss: $($cmp.baseline_calibrated_winner_log_loss)",
        "- ranker holdout winner log-loss: $($cmp.challenger_calibrated_winner_log_loss)",
        "- market holdout winner log-loss: $($cmp.market_winner_log_loss)",
        "- ranker beats baseline: $($cmp.challenger_beats_baseline_winner_log_loss)",
        "- ranker beats market: $($cmp.challenger_beats_market_winner_log_loss)",
        "- baseline EV1.15 research ROI: $($cmp.baseline_ev15_flat_roi_final_odds)",
        "- ranker EV1.15 research ROI: $($cmp.challenger_ev15_flat_roi_final_odds)"
    ) | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding UTF8
}

Write-Host "Ranker challenger research PASS."
Write-Host "baseline_holdout_log_loss=$($cmp.baseline_calibrated_winner_log_loss)"
Write-Host "ranker_holdout_log_loss=$($cmp.challenger_calibrated_winner_log_loss)"
Write-Host "market_holdout_log_loss=$($cmp.market_winner_log_loss)"
Write-Host "ranker_beats_baseline=$($cmp.challenger_beats_baseline_winner_log_loss)"
Write-Host "ranker_beats_market=$($cmp.challenger_beats_market_winner_log_loss)"
