param(
    [string]$ValidationOutput = "artifacts/exotic_longshot_phase7_runner_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

$venvPython = Join-Path $ProjectRoot ".venv-jravan\Scripts\python.exe"
$historyPath = Join-Path $ProjectRoot "data\jravan\full\current_history.csv"
$summaryPath = Join-Path $ProjectRoot "artifacts\exotic_longshot_phase7\summary.json"

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    throw ".venv-jravan is missing; complete JRA-VAN Resume validation first."
}
if (-not (Test-Path -LiteralPath $historyPath -PathType Leaf)) {
    throw "current_history.csv is missing."
}

Write-Host "=== Exotic longshot intrusion Phase 7 research ==="
Write-Host "[1/3] Refreshing local project package"
& $venvPython -m pip install -e ".[research]"
if ($LASTEXITCODE -ne 0) { throw "Project installation failed." }

Write-Host "[2/3] Training general/specialist Top-3 models and evaluating reused 2023/2024"
& $venvPython "scripts\evaluate_exotic_longshot_phase7.py" --history $historyPath --output $summaryPath
if ($LASTEXITCODE -ne 0) { throw "Longshot intrusion Phase 7 research failed." }
if (-not (Test-Path -LiteralPath $summaryPath -PathType Leaf)) {
    throw "Longshot intrusion Phase 7 summary was not created."
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
    training = $summary.training
    feature_design = $summary.feature_design
    research_protocol = $summary.research_protocol
    evaluation_2023 = $v23
    evaluation_2024 = $v24
    development_longshot_intrusion_gate_passed = [bool]$summary.development_longshot_intrusion_gate_passed
}
$validationPath = Join-Path $ProjectRoot $ValidationOutput
$validationDir = Split-Path -Parent $validationPath
if (-not [string]::IsNullOrWhiteSpace($validationDir)) {
    New-Item -ItemType Directory -Force -Path $validationDir | Out-Null
}
$payload | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $validationPath -Encoding UTF8

Write-Host "exotic_phase7_2023_logloss_delta=$($v23.binary_log_loss_delta)"
Write-Host "exotic_phase7_2023_brier_delta=$($v23.brier_delta)"
Write-Host "exotic_phase7_2023_top_pick_hit_rate_delta=$($v23.top_pick.hit_rate_delta)"
Write-Host "exotic_phase7_2023_logloss_bootstrap_support=$($v23.paired_bootstrap_vs_general_top3.binary_log_loss_improvement_support)"
Write-Host "exotic_phase7_2023_brier_bootstrap_support=$($v23.paired_bootstrap_vs_general_top3.brier_improvement_support)"
Write-Host "exotic_phase7_2023_top_pick_bootstrap_support=$($v23.paired_bootstrap_vs_general_top3.top_pick_hit_rate_improvement_support)"
Write-Host "exotic_phase7_2024_logloss_delta=$($v24.binary_log_loss_delta)"
Write-Host "exotic_phase7_2024_brier_delta=$($v24.brier_delta)"
Write-Host "exotic_phase7_2024_top_pick_hit_rate_delta=$($v24.top_pick.hit_rate_delta)"
Write-Host "exotic_phase7_2024_logloss_bootstrap_support=$($v24.paired_bootstrap_vs_general_top3.binary_log_loss_improvement_support)"
Write-Host "exotic_phase7_2024_brier_bootstrap_support=$($v24.paired_bootstrap_vs_general_top3.brier_improvement_support)"
Write-Host "exotic_phase7_2024_top_pick_bootstrap_support=$($v24.paired_bootstrap_vs_general_top3.top_pick_hit_rate_improvement_support)"
Write-Host "exotic_phase7_development_longshot_intrusion_gate_passed=$($summary.development_longshot_intrusion_gate_passed)"

if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_STEP_SUMMARY)) {
    @(
        "### Exotic longshot intrusion Phase 7",
        "",
        "- 2023 log-loss delta: $($v23.binary_log_loss_delta)",
        "- 2023 Brier delta: $($v23.brier_delta)",
        "- 2023 top-longshot hit-rate delta: $($v23.top_pick.hit_rate_delta)",
        "- 2023 log-loss bootstrap support: $($v23.paired_bootstrap_vs_general_top3.binary_log_loss_improvement_support)",
        "- 2023 Brier bootstrap support: $($v23.paired_bootstrap_vs_general_top3.brier_improvement_support)",
        "- 2023 top-pick bootstrap support: $($v23.paired_bootstrap_vs_general_top3.top_pick_hit_rate_improvement_support)",
        "- 2024 log-loss delta: $($v24.binary_log_loss_delta)",
        "- 2024 Brier delta: $($v24.brier_delta)",
        "- 2024 top-longshot hit-rate delta: $($v24.top_pick.hit_rate_delta)",
        "- 2024 log-loss bootstrap support: $($v24.paired_bootstrap_vs_general_top3.binary_log_loss_improvement_support)",
        "- 2024 Brier bootstrap support: $($v24.paired_bootstrap_vs_general_top3.brier_improvement_support)",
        "- 2024 top-pick bootstrap support: $($v24.paired_bootstrap_vs_general_top3.top_pick_hit_rate_improvement_support)",
        "- gate passed: $($summary.development_longshot_intrusion_gate_passed)",
        "- final holdout: $($summary.research_protocol.final_holdout)",
        "- Forward Paper: $($summary.research_protocol.forward_paper)"
    ) | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding UTF8
}
