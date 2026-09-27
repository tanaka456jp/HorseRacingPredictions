param(
    [string]$ValidationOutput = "artifacts/ranker_v10_holdout_runner_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

$venvPython = Join-Path $ProjectRoot ".venv-jravan\Scripts\python.exe"
$historyPath = Join-Path $ProjectRoot "data\jravan\full\current_history.csv"
$championDir = Join-Path $ProjectRoot "artifacts\champion_v7"
$summaryPath = Join-Path $ProjectRoot "artifacts\ranker_v10_holdout\summary.json"

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    throw ".venv-jravan is missing; complete JRA-VAN Resume validation first."
}
if (-not (Test-Path -LiteralPath $historyPath -PathType Leaf)) {
    throw "current_history.csv is missing."
}

Write-Host "=== Ranker v10 fixed holdout confirmation ==="
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

Write-Host "[3/4] Confirming fixed Ranker v10 on untouched holdout"
& $venvPython "scripts\evaluate_ranker_v10_holdout.py" --history $historyPath --champion $championDir --output $summaryPath
if ($LASTEXITCODE -ne 0) { throw "Ranker v10 holdout confirmation failed." }
if (-not (Test-Path -LiteralPath $summaryPath -PathType Leaf)) {
    throw "Ranker v10 holdout summary was not created."
}

Write-Host "[4/4] Writing sanitized validation"
$summary = Get-Content -LiteralPath $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
$holdout = $summary.holdout_2025_2026
$features = $summary.features
$validation = @{
    validated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    commit_sha = (& git rev-parse HEAD).Trim()
    runner_os = $env:RUNNER_OS
    runner_arch = $env:RUNNER_ARCH
    status = [string]$summary.status
    training = $summary.training
    calibration = $summary.calibration
    holdout_2025_2026 = $holdout
    v9_feature_count = [int]$features.v9_count
    v10_feature_count = [int]$features.v10_count
    added_feature_count = [int]$features.added_count
    holdout_confirmation_passed = [bool]$holdout.holdout_confirmation_passed
}
$validationPath = Join-Path $ProjectRoot $ValidationOutput
$validationDir = Split-Path -Parent $validationPath
if (-not [string]::IsNullOrWhiteSpace($validationDir)) {
    New-Item -ItemType Directory -Force -Path $validationDir | Out-Null
}
$validation | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $validationPath -Encoding UTF8

if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_STEP_SUMMARY)) {
    @(
        "### Ranker v10 fixed holdout confirmation",
        "",
        "- holdout: $($holdout.period_start) .. $($holdout.period_end)",
        "- v9 winner log-loss: $($holdout.v9_quality.winner_log_loss)",
        "- v10 winner log-loss: $($holdout.v10_quality.winner_log_loss)",
        "- market winner log-loss: $($holdout.market_quality.winner_log_loss)",
        "- v9 Brier: $($holdout.v9_quality.brier)",
        "- v10 Brier: $($holdout.v10_quality.brier)",
        "- holdout confirmation passed: $($holdout.holdout_confirmation_passed)",
        "- v9 EV1.15 research ROI: $($holdout.v9_ev15_research.flat_bet_roi_final_odds)",
        "- v10 EV1.15 research ROI: $($holdout.v10_ev15_research.flat_bet_roi_final_odds)"
    ) | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding UTF8
}

Write-Host "Ranker v10 holdout confirmation PASS."
Write-Host "v9_log_loss=$($holdout.v9_quality.winner_log_loss)"
Write-Host "v10_log_loss=$($holdout.v10_quality.winner_log_loss)"
Write-Host "market_log_loss=$($holdout.market_quality.winner_log_loss)"
Write-Host "v9_brier=$($holdout.v9_quality.brier)"
Write-Host "v10_brier=$($holdout.v10_quality.brier)"
Write-Host "holdout_confirmation_passed=$($holdout.holdout_confirmation_passed)"
