param(
    [string]$ValidationOutput = "artifacts/market_blend_research_runner_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

$venvPython = Join-Path $ProjectRoot ".venv-jravan\Scripts\python.exe"
$historyPath = Join-Path $ProjectRoot "data\jravan\full\current_history.csv"
$championDir = Join-Path $ProjectRoot "artifacts\champion_v7"
$summaryPath = Join-Path $ProjectRoot "artifacts\market_blend_research\summary.json"

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    throw ".venv-jravan is missing; complete JRA-VAN Resume validation first."
}
if (-not (Test-Path -LiteralPath $historyPath -PathType Leaf)) {
    throw "current_history.csv is missing."
}

Write-Host "=== Champion + market blend holdout research ==="
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

Write-Host "[3/4] Fitting development-only market blend and evaluating holdout"
& $venvPython "scripts\evaluate_market_blend_research.py" --history $historyPath --champion $championDir --output $summaryPath
if ($LASTEXITCODE -ne 0) { throw "Market blend research failed." }
if (-not (Test-Path -LiteralPath $summaryPath -PathType Leaf)) {
    throw "Market blend research summary was not created."
}

Write-Host "[4/4] Writing sanitized validation"
$summary = Get-Content -LiteralPath $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
$dev = $summary.development
$hold = $summary.holdout
$validation = @{
    validated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    commit_sha = (& git rev-parse HEAD).Trim()
    runner_os = $env:RUNNER_OS
    runner_arch = $env:RUNNER_ARCH
    status = [string]$summary.status
    development_period_start = [string]$dev.period_start
    development_period_end = [string]$dev.period_end
    development_rows = [int]$dev.rows
    development_races = [int]$dev.races
    fitted_temperature = [double]$dev.temperature
    fitted_alpha_model_weight = [double]$dev.fitted_alpha_model_weight
    fitted_alpha_market_weight = [double]$dev.fitted_alpha_market_weight
    development_quality = $dev.quality
    development_alpha_sweep = $dev.alpha_sweep
    holdout_period_start = [string]$hold.period_start
    holdout_period_end = [string]$hold.period_end
    holdout_rows = [int]$hold.rows
    holdout_races = [int]$hold.races
    holdout_quality = $hold.quality
    holdout_alpha_sweep_for_diagnostics_only = $hold.alpha_sweep_for_diagnostics_only
    holdout_blend_ev_threshold_sweep = $hold.blend_ev_threshold_sweep
    holdout_blend_confidence_quantiles = $hold.blend_confidence_quantiles
    fitted_blend_beats_market_winner_log_loss = [bool]$hold.fitted_blend_beats_market_winner_log_loss
    winner_log_loss_delta_vs_market = $hold.winner_log_loss_delta_vs_market
}
$validationPath = Join-Path $ProjectRoot $ValidationOutput
$validationDir = Split-Path -Parent $validationPath
if (-not [string]::IsNullOrWhiteSpace($validationDir)) {
    New-Item -ItemType Directory -Force -Path $validationDir | Out-Null
}
$validation | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $validationPath -Encoding UTF8

if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_STEP_SUMMARY)) {
    @(
        "### Champion + market blend research",
        "",
        "- fitted model weight: $($dev.fitted_alpha_model_weight)",
        "- fitted market weight: $($dev.fitted_alpha_market_weight)",
        "- holdout market winner log-loss: $($hold.quality.market.winner_log_loss)",
        "- holdout calibrated model winner log-loss: $($hold.quality.calibrated_model.winner_log_loss)",
        "- holdout fitted blend winner log-loss: $($hold.quality.fitted_blend.winner_log_loss)",
        "- blend beats market: $($hold.fitted_blend_beats_market_winner_log_loss)",
        "- delta vs market: $($hold.winner_log_loss_delta_vs_market)"
    ) | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding UTF8
}

Write-Host "Market blend research PASS."
Write-Host "alpha_model=$($dev.fitted_alpha_model_weight)"
Write-Host "alpha_market=$($dev.fitted_alpha_market_weight)"
Write-Host "holdout_market_log_loss=$($hold.quality.market.winner_log_loss)"
Write-Host "holdout_model_log_loss=$($hold.quality.calibrated_model.winner_log_loss)"
Write-Host "holdout_blend_log_loss=$($hold.quality.fitted_blend.winner_log_loss)"
Write-Host "blend_beats_market=$($hold.fitted_blend_beats_market_winner_log_loss)"
