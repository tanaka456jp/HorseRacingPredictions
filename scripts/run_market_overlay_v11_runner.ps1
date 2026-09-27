param(
    [string]$ValidationOutput = "artifacts/market_overlay_v11_runner_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

$venvPython = Join-Path $ProjectRoot ".venv-jravan\Scripts\python.exe"
$historyPath = Join-Path $ProjectRoot "data\jravan\full\current_history.csv"
$championDir = Join-Path $ProjectRoot "artifacts\champion_v7"
$summaryPath = Join-Path $ProjectRoot "artifacts\market_overlay_v11\summary.json"

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    throw ".venv-jravan is missing; complete JRA-VAN Resume validation first."
}
if (-not (Test-Path -LiteralPath $historyPath -PathType Leaf)) {
    throw "current_history.csv is missing."
}

Write-Host "=== Market overlay v11 development gate ==="
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

Write-Host "[3/4] Fitting 2023 overlay rule and validating unchanged on 2024"
& $venvPython "scripts\evaluate_market_overlay_v11.py" --history $historyPath --champion $championDir --output $summaryPath
if ($LASTEXITCODE -ne 0) { throw "Market overlay development research failed." }
if (-not (Test-Path -LiteralPath $summaryPath -PathType Leaf)) {
    throw "Market overlay summary was not created."
}

Write-Host "[4/4] Writing sanitized validation"
$summary = Get-Content -LiteralPath $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
$tuning = $summary.tuning_2023
$validation = $summary.validation_2024
$payload = @{
    validated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    commit_sha = (& git rev-parse HEAD).Trim()
    runner_os = $env:RUNNER_OS
    runner_arch = $env:RUNNER_ARCH
    status = [string]$summary.status
    training = $summary.training
    calibration = $summary.calibration
    tuning_period_start = [string]$tuning.period_start
    tuning_period_end = [string]$tuning.period_end
    tuning_rows = [int]$tuning.rows
    tuning_races = [int]$tuning.races
    fitted_rule = $tuning.fitted_rule
    validation_period_start = [string]$validation.period_start
    validation_period_end = [string]$validation.period_end
    validation_rows = [int]$validation.rows
    validation_races = [int]$validation.races
    fixed_rule_result = $validation.fixed_rule_result
    development_gate_passed = [bool]$validation.development_gate_passed
    constraints = $summary.constraints
}
$validationPath = Join-Path $ProjectRoot $ValidationOutput
$validationDir = Split-Path -Parent $validationPath
if (-not [string]::IsNullOrWhiteSpace($validationDir)) {
    New-Item -ItemType Directory -Force -Path $validationDir | Out-Null
}
$payload | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $validationPath -Encoding UTF8

if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_STEP_SUMMARY)) {
    $rule = $tuning.fitted_rule
    $fixed = $validation.fixed_rule_result
    @(
        "### Market overlay v11 development gate",
        "",
        "- tuning period: $($tuning.period_start) .. $($tuning.period_end)",
        "- fitted policy: $($rule.policy)",
        "- fitted overlay threshold: $($rule.overlay_ratio_threshold)",
        "- tuning research ROI: $($rule.flat_bet_roi_final_odds)",
        "- validation period: $($validation.period_start) .. $($validation.period_end)",
        "- validation rows/races: $($fixed.rows) / $($fixed.races)",
        "- validation research ROI: $($fixed.flat_bet_roi_final_odds)",
        "- development gate passed: $($validation.development_gate_passed)"
    ) | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding UTF8
}

Write-Host "Market overlay v11 development research PASS."
Write-Host "development_gate_passed=$($validation.development_gate_passed)"
if ($null -ne $tuning.fitted_rule) {
    Write-Host "overlay_policy=$($tuning.fitted_rule.policy)"
    Write-Host "overlay_threshold=$($tuning.fitted_rule.overlay_ratio_threshold)"
    Write-Host "tuning_roi=$($tuning.fitted_rule.flat_bet_roi_final_odds)"
}
if ($null -ne $validation.fixed_rule_result) {
    Write-Host "validation_roi=$($validation.fixed_rule_result.flat_bet_roi_final_odds)"
    Write-Host "validation_rows=$($validation.fixed_rule_result.rows)"
}
