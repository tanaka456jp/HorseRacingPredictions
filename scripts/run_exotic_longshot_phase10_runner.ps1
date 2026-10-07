param(
    [string]$ValidationOutput = "artifacts/exotic_longshot_phase10_runner_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

$venvPython = Join-Path $ProjectRoot ".venv-jravan\Scripts\python.exe"
$historyPath = Join-Path $ProjectRoot "data\jravan\full\current_history.csv"
$summaryPath = Join-Path $ProjectRoot "artifacts\exotic_longshot_phase10\summary.json"

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    throw ".venv-jravan is missing; complete JRA-VAN Resume validation first."
}
if (-not (Test-Path -LiteralPath $historyPath -PathType Leaf)) {
    throw "current_history.csv is missing."
}

Write-Host "=== Exotic longshot rolling residual Phase 10 research ==="
Write-Host "[1/3] Refreshing local project package"
& $venvPython -m pip install -e ".[research]"
if ($LASTEXITCODE -ne 0) { throw "Project installation failed." }

Write-Host "[2/3] Running annual walk-forward residual evaluation on reused 2023/2024"
& $venvPython "scripts\evaluate_exotic_longshot_phase10.py" --history $historyPath --output $summaryPath
if ($LASTEXITCODE -ne 0) { throw "Longshot rolling residual Phase 10 research failed." }
if (-not (Test-Path -LiteralPath $summaryPath -PathType Leaf)) {
    throw "Longshot rolling residual Phase 10 summary was not created."
}

Write-Host "[3/3] Writing sanitized validation"
$summary = Get-Content -LiteralPath $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
$v23 = $summary.evaluation_2023
$v24 = $summary.evaluation_2024
$payload = @{
    validated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    commit_sha = (& git rev-parse HEAD).Trim()
    runner_os = $env:RUNNER_OS
    runner_arch = $env:RUNNER_ARCH
    status = [string]$summary.status
    oof_training = $summary.oof_training
    annual_training = $summary.annual_training
    feature_design = $summary.feature_design
    research_protocol = $summary.research_protocol
    evaluation_2023 = $v23
    evaluation_2024 = $v24
    development_longshot_rolling_residual_gate_passed = [bool]$summary.development_longshot_rolling_residual_gate_passed
}
$validationPath = Join-Path $ProjectRoot $ValidationOutput
$validationDir = Split-Path -Parent $validationPath
if (-not [string]::IsNullOrWhiteSpace($validationDir)) {
    New-Item -ItemType Directory -Force -Path $validationDir | Out-Null
}
$payload | ConvertTo-Json -Depth 14 | Set-Content -LiteralPath $validationPath -Encoding UTF8

Write-Host "exotic_phase10_2023_logloss_delta=$($v23.binary_log_loss_delta)"
Write-Host "exotic_phase10_2023_brier_delta=$($v23.brier_delta)"
Write-Host "exotic_phase10_2023_top1_hit_rate_delta=$($v23.top1.hit_rate_delta)"
Write-Host "exotic_phase10_2023_mrr_delta=$($v23.mrr.delta)"
Write-Host "exotic_phase10_2023_logloss_support=$($v23.paired_bootstrap_quality.binary_log_loss_improvement_support)"
Write-Host "exotic_phase10_2023_brier_support=$($v23.paired_bootstrap_quality.brier_improvement_support)"
Write-Host "exotic_phase10_2023_top1_support=$($v23.paired_bootstrap_ranking.top1_hit_rate_improvement_support)"
Write-Host "exotic_phase10_2023_mrr_support=$($v23.paired_bootstrap_ranking.mrr_improvement_support)"
Write-Host "exotic_phase10_2024_logloss_delta=$($v24.binary_log_loss_delta)"
Write-Host "exotic_phase10_2024_brier_delta=$($v24.brier_delta)"
Write-Host "exotic_phase10_2024_top1_hit_rate_delta=$($v24.top1.hit_rate_delta)"
Write-Host "exotic_phase10_2024_mrr_delta=$($v24.mrr.delta)"
Write-Host "exotic_phase10_2024_logloss_support=$($v24.paired_bootstrap_quality.binary_log_loss_improvement_support)"
Write-Host "exotic_phase10_2024_brier_support=$($v24.paired_bootstrap_quality.brier_improvement_support)"
Write-Host "exotic_phase10_2024_top1_support=$($v24.paired_bootstrap_ranking.top1_hit_rate_improvement_support)"
Write-Host "exotic_phase10_2024_mrr_support=$($v24.paired_bootstrap_ranking.mrr_improvement_support)"
Write-Host "exotic_phase10_development_longshot_rolling_residual_gate_passed=$($summary.development_longshot_rolling_residual_gate_passed)"
