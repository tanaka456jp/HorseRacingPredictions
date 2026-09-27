param(
    [string]$ValidationOutput = "artifacts/champion_diagnostics_runner_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

$venvPython = Join-Path $ProjectRoot ".venv-jravan\Scripts\python.exe"
$historyPath = Join-Path $ProjectRoot "data\jravan\full\current_history.csv"
$championDir = Join-Path $ProjectRoot "artifacts\champion_v7"
$summaryPath = Join-Path $ProjectRoot "artifacts\champion_diagnostics\summary.json"

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    throw ".venv-jravan is missing; complete JRA-VAN Resume validation first."
}
if (-not (Test-Path -LiteralPath $historyPath -PathType Leaf)) {
    throw "current_history.csv is missing."
}

Write-Host "=== Frozen Champion post-training diagnostics ==="
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

Write-Host "[3/4] Evaluating frozen Champion on post-training history"
& $venvPython "scripts\diagnose_champion_current_history.py" --history $historyPath --champion $championDir --output $summaryPath
if ($LASTEXITCODE -ne 0) { throw "Champion diagnostic failed." }
if (-not (Test-Path -LiteralPath $summaryPath -PathType Leaf)) {
    throw "Champion diagnostic summary was not created."
}

Write-Host "[4/4] Writing sanitized validation"
$summary = Get-Content -LiteralPath $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
$reasons = $summary.selection_reason_counts
$quantiles = $summary.race_confidence_quantiles
$backtest = $summary.current_config_backtest_final_odds
$validation = @{
    validated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    commit_sha = (& git rev-parse HEAD).Trim()
    runner_os = $env:RUNNER_OS
    runner_arch = $env:RUNNER_ARCH
    status = [string]$summary.status
    period_start = [string]$summary.period.start
    period_end = [string]$summary.period.end
    rows = [int]$summary.rows
    races = [int]$summary.races
    min_ev = [double]$summary.config.min_ev
    min_probability = [double]$summary.config.min_probability
    min_confidence = [double]$summary.config.min_confidence
    probability_below_threshold = [int]$reasons.probability_below_threshold
    confidence_below_threshold = [int]$reasons.confidence_below_threshold
    ev_below_threshold = [int]$reasons.ev_below_threshold
    eligible = [int]$reasons.eligible
    confidence_q50 = [double]$quantiles."0.5"
    confidence_q90 = [double]$quantiles."0.9"
    confidence_q95 = [double]$quantiles."0.95"
    confidence_q99 = [double]$quantiles."0.99"
    confidence_max = [double]$quantiles."1.0"
    research_bets = [int]$backtest.bets
    research_stake_yen = [int]$backtest.stake_yen
    research_profit_yen = [int]$backtest.profit_yen
    research_roi = [double]$backtest.roi
    research_max_drawdown = [double]$backtest.max_drawdown
    odds_evidence = [string]$backtest.odds_evidence
    roi_verified = [bool]$backtest.roi_verified
    confidence_threshold_sweep = $summary.confidence_threshold_sweep
    confidence_threshold_sweep_by_period = $summary.confidence_threshold_sweep_by_period
}
$validationPath = Join-Path $ProjectRoot $ValidationOutput
$validationDir = Split-Path -Parent $validationPath
if (-not [string]::IsNullOrWhiteSpace($validationDir)) {
    New-Item -ItemType Directory -Force -Path $validationDir | Out-Null
}
$validation | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $validationPath -Encoding UTF8

if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_STEP_SUMMARY)) {
    @(
        "### Frozen Champion diagnostics",
        "",
        "- period: $($summary.period.start) .. $($summary.period.end)",
        "- rows/races: $($summary.rows) / $($summary.races)",
        "- current min_confidence: $($summary.config.min_confidence)",
        "- confidence rejects: $($reasons.confidence_below_threshold)",
        "- eligible: $($reasons.eligible)",
        "- confidence q95/max: $($quantiles."0.95") / $($quantiles."1.0")",
        "- research ROI (final odds; not verified live): $($backtest.roi)",
        "- threshold rows exported: $($summary.confidence_threshold_sweep.Count)",
        "- period-threshold rows exported: $($summary.confidence_threshold_sweep_by_period.Count)"
    ) | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding UTF8
}

Write-Host "Frozen Champion diagnostic PASS."
Write-Host "period=$($summary.period.start)..$($summary.period.end)"
Write-Host "rows=$($summary.rows)"
Write-Host "races=$($summary.races)"
Write-Host "confidence_below_threshold=$($reasons.confidence_below_threshold)"
Write-Host "eligible=$($reasons.eligible)"
Write-Host "confidence_q95=$($quantiles."0.95")"
Write-Host "confidence_max=$($quantiles."1.0")"
