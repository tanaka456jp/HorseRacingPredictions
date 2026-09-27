param(
    [string]$ValidationOutput = "artifacts/champion_challenger_runner_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

$venvPython = Join-Path $ProjectRoot ".venv-jravan\Scripts\python.exe"
$historyPath = Join-Path $ProjectRoot "data\jravan\full\current_history.csv"
$championDir = Join-Path $ProjectRoot "artifacts\champion_v7"
$summaryPath = Join-Path $ProjectRoot "artifacts\champion_challenger\summary.json"

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    throw ".venv-jravan is missing; complete JRA-VAN Resume validation first."
}
if (-not (Test-Path -LiteralPath $historyPath -PathType Leaf)) {
    throw "current_history.csv is missing."
}

Write-Host "=== Champion vs Unweighted CatBoost Challenger ==="
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

Write-Host "[3/4] Training and evaluating unweighted challenger"
& $venvPython "scripts\evaluate_unweighted_challenger.py" --history $historyPath --champion $championDir --output $summaryPath
if ($LASTEXITCODE -ne 0) { throw "Unweighted challenger research failed." }
if (-not (Test-Path -LiteralPath $summaryPath -PathType Leaf)) {
    throw "Challenger summary was not created."
}

Write-Host "[4/4] Writing sanitized validation"
$summary = Get-Content -LiteralPath $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
$baselineHoldout = $summary.baseline.temperature_calibration.holdout
$challengerHoldout = $summary.challenger.temperature_calibration.holdout
$validation = @{
    validated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    commit_sha = (& git rev-parse HEAD).Trim()
    runner_os = $env:RUNNER_OS
    runner_arch = $env:RUNNER_ARCH
    status = [string]$summary.status
    training = $summary.training
    evaluation = $summary.evaluation
    holdout_comparison = $summary.holdout_comparison
    baseline_temperature = $summary.baseline.temperature_calibration.temperature
    challenger_temperature = $summary.challenger.temperature_calibration.temperature
    baseline_holdout_quality = $baselineHoldout.calibrated_quality
    challenger_holdout_quality = $challengerHoldout.calibrated_quality
    baseline_holdout_ev_sweep = $baselineHoldout.calibrated_ev_threshold_sweep
    challenger_holdout_ev_sweep = $challengerHoldout.calibrated_ev_threshold_sweep
}
$validationPath = Join-Path $ProjectRoot $ValidationOutput
$validationDir = Split-Path -Parent $validationPath
if (-not [string]::IsNullOrWhiteSpace($validationDir)) {
    New-Item -ItemType Directory -Force -Path $validationDir | Out-Null
}
$validation | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $validationPath -Encoding UTF8

if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_STEP_SUMMARY)) {
    $cmp = $summary.holdout_comparison
    @(
        "### Champion vs unweighted CatBoost challenger",
        "",
        "- holdout: $($summary.evaluation.period_start) .. $($summary.evaluation.period_end)",
        "- baseline calibrated winner log-loss: $($cmp.baseline_calibrated_winner_log_loss)",
        "- challenger calibrated winner log-loss: $($cmp.challenger_calibrated_winner_log_loss)",
        "- baseline calibrated Brier: $($cmp.baseline_calibrated_brier)",
        "- challenger calibrated Brier: $($cmp.challenger_calibrated_brier)",
        "- baseline EV1.15 research ROI: $($cmp.baseline_ev15_flat_roi_final_odds)",
        "- challenger EV1.15 research ROI: $($cmp.challenger_ev15_flat_roi_final_odds)"
    ) | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding UTF8
}

Write-Host "Champion challenger research PASS."
Write-Host "baseline_holdout_log_loss=$($summary.holdout_comparison.baseline_calibrated_winner_log_loss)"
Write-Host "challenger_holdout_log_loss=$($summary.holdout_comparison.challenger_calibrated_winner_log_loss)"
Write-Host "baseline_ev15_roi=$($summary.holdout_comparison.baseline_ev15_flat_roi_final_odds)"
Write-Host "challenger_ev15_roi=$($summary.holdout_comparison.challenger_ev15_flat_roi_final_odds)"
