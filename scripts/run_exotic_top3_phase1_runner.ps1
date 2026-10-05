param(
    [string]$ValidationOutput = "artifacts/exotic_top3_phase1_runner_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

$venvPython = Join-Path $ProjectRoot ".venv-jravan\Scripts\python.exe"
$historyPath = Join-Path $ProjectRoot "data\jravan\full\current_history.csv"
$summaryPath = Join-Path $ProjectRoot "artifacts\exotic_top3_phase1\summary.json"

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    throw ".venv-jravan is missing; complete JRA-VAN Resume validation first."
}
if (-not (Test-Path -LiteralPath $historyPath -PathType Leaf)) {
    throw "current_history.csv is missing."
}

Write-Host "=== Exotic Top-3 Phase 1 development research ==="
Write-Host "[1/3] Refreshing local project package"
& $venvPython -m pip install -e ".[research]"
if ($LASTEXITCODE -ne 0) { throw "Project installation failed." }

Write-Host "[2/3] Training baseline/challenger and evaluating reused 2023/2024 development periods"
& $venvPython "scripts\evaluate_exotic_top3_phase1.py" --history $historyPath --output $summaryPath
if ($LASTEXITCODE -ne 0) { throw "Exotic Top-3 Phase 1 research failed." }
if (-not (Test-Path -LiteralPath $summaryPath -PathType Leaf)) {
    throw "Exotic Top-3 Phase 1 summary was not created."
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
    evaluation_2023 = @{
        period_start = $v23.period_start
        period_end = $v23.period_end
        binary_log_loss_delta = [double]$v23.binary_log_loss_delta
        brier_delta = [double]$v23.brier_delta
        longshot_rows = [int]$v23.longshot_proxy.challenger.rows
        longshot_races = [int]$v23.longshot_proxy.challenger.races
        longshot_top3_rate = [double]$v23.longshot_proxy.challenger.top3_rate
        longshot_binary_log_loss_delta = [double]$v23.longshot_proxy.binary_log_loss_delta
        longshot_brier_delta = [double]$v23.longshot_proxy.brier_delta
    }
    evaluation_2024 = @{
        period_start = $v24.period_start
        period_end = $v24.period_end
        binary_log_loss_delta = [double]$v24.binary_log_loss_delta
        brier_delta = [double]$v24.brier_delta
        longshot_rows = [int]$v24.longshot_proxy.challenger.rows
        longshot_races = [int]$v24.longshot_proxy.challenger.races
        longshot_top3_rate = [double]$v24.longshot_proxy.challenger.top3_rate
        longshot_binary_log_loss_delta = [double]$v24.longshot_proxy.binary_log_loss_delta
        longshot_brier_delta = [double]$v24.longshot_proxy.brier_delta
    }
    bootstrap_safety_phase2 = $summary.bootstrap_safety_phase2
    combination_phase3 = $summary.combination_phase3
    development_gate_passed = [bool]$summary.development_gate_passed
    development_safety_gate_passed = [bool]$summary.development_safety_gate_passed
    development_combination_gate_passed = [bool]$summary.development_combination_gate_passed
}
$validationPath = Join-Path $ProjectRoot $ValidationOutput
$validationDir = Split-Path -Parent $validationPath
if (-not [string]::IsNullOrWhiteSpace($validationDir)) {
    New-Item -ItemType Directory -Force -Path $validationDir | Out-Null
}
$payload | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $validationPath -Encoding UTF8

if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_STEP_SUMMARY)) {
    @(
        "### Exotic Top-3 Phase 1 development research",
        "",
        "- 2023 log-loss delta challenger vs baseline: $($v23.binary_log_loss_delta)",
        "- 2023 Brier delta challenger vs baseline: $($v23.brier_delta)",
        "- 2023 longshot log-loss delta: $($v23.longshot_proxy.binary_log_loss_delta)",
        "- 2023 longshot Brier delta: $($v23.longshot_proxy.brier_delta)",
        "- 2024 log-loss delta challenger vs baseline: $($v24.binary_log_loss_delta)",
        "- 2024 Brier delta challenger vs baseline: $($v24.brier_delta)",
        "- 2024 longshot log-loss delta: $($v24.longshot_proxy.binary_log_loss_delta)",
        "- 2024 longshot Brier delta: $($v24.longshot_proxy.brier_delta)",
        "- development gate passed: $($summary.development_gate_passed)",
        "- 2023 overall log-loss bootstrap support: $($v23.paired_bootstrap_vs_baseline.binary_log_loss_improvement_support)",
        "- 2023 overall Brier bootstrap support: $($v23.paired_bootstrap_vs_baseline.brier_improvement_support)",
        "- 2023 longshot log-loss bootstrap support: $($v23.longshot_proxy.paired_bootstrap_vs_baseline.binary_log_loss_improvement_support)",
        "- 2023 longshot Brier bootstrap support: $($v23.longshot_proxy.paired_bootstrap_vs_baseline.brier_improvement_support)",
        "- 2024 overall log-loss bootstrap support: $($v24.paired_bootstrap_vs_baseline.binary_log_loss_improvement_support)",
        "- 2024 overall Brier bootstrap support: $($v24.paired_bootstrap_vs_baseline.brier_improvement_support)",
        "- 2024 longshot log-loss bootstrap support: $($v24.longshot_proxy.paired_bootstrap_vs_baseline.binary_log_loss_improvement_support)",
        "- 2024 longshot Brier bootstrap support: $($v24.longshot_proxy.paired_bootstrap_vs_baseline.brier_improvement_support)",
        "- development safety gate passed: $($summary.development_safety_gate_passed)",
        "- 2023 trifecta NLL delta: $($v23.combination_phase3.overall.trifecta_nll_delta)",
        "- 2023 trio NLL delta: $($v23.combination_phase3.overall.trio_nll_delta)",
        "- 2023 longshot-containing trifecta NLL delta: $($v23.combination_phase3.longshot_containing.trifecta_nll_delta)",
        "- 2023 longshot-containing trio NLL delta: $($v23.combination_phase3.longshot_containing.trio_nll_delta)",
        "- 2024 trifecta NLL delta: $($v24.combination_phase3.overall.trifecta_nll_delta)",
        "- 2024 trio NLL delta: $($v24.combination_phase3.overall.trio_nll_delta)",
        "- 2024 longshot-containing trifecta NLL delta: $($v24.combination_phase3.longshot_containing.trifecta_nll_delta)",
        "- 2024 longshot-containing trio NLL delta: $($v24.combination_phase3.longshot_containing.trio_nll_delta)",
        "- Phase 3 combination gate passed: $($summary.development_combination_gate_passed)",
        "- final holdout: $($summary.research_protocol.final_holdout)",
        "- Forward Paper: $($summary.research_protocol.forward_paper)"
    ) | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding UTF8
}

Write-Host "exotic_top3_2023_logloss_delta=$($v23.binary_log_loss_delta)"
Write-Host "exotic_top3_2023_brier_delta=$($v23.brier_delta)"
Write-Host "exotic_top3_2023_longshot_logloss_delta=$($v23.longshot_proxy.binary_log_loss_delta)"
Write-Host "exotic_top3_2023_longshot_brier_delta=$($v23.longshot_proxy.brier_delta)"
Write-Host "exotic_top3_2024_logloss_delta=$($v24.binary_log_loss_delta)"
Write-Host "exotic_top3_2024_brier_delta=$($v24.brier_delta)"
Write-Host "exotic_top3_2024_longshot_logloss_delta=$($v24.longshot_proxy.binary_log_loss_delta)"
Write-Host "exotic_top3_2024_longshot_brier_delta=$($v24.longshot_proxy.brier_delta)"
Write-Host "exotic_top3_development_gate_passed=$($summary.development_gate_passed)"
Write-Host "exotic_top3_2023_logloss_bootstrap_support=$($v23.paired_bootstrap_vs_baseline.binary_log_loss_improvement_support)"
Write-Host "exotic_top3_2023_brier_bootstrap_support=$($v23.paired_bootstrap_vs_baseline.brier_improvement_support)"
Write-Host "exotic_top3_2023_longshot_logloss_bootstrap_support=$($v23.longshot_proxy.paired_bootstrap_vs_baseline.binary_log_loss_improvement_support)"
Write-Host "exotic_top3_2023_longshot_brier_bootstrap_support=$($v23.longshot_proxy.paired_bootstrap_vs_baseline.brier_improvement_support)"
Write-Host "exotic_top3_2024_logloss_bootstrap_support=$($v24.paired_bootstrap_vs_baseline.binary_log_loss_improvement_support)"
Write-Host "exotic_top3_2024_brier_bootstrap_support=$($v24.paired_bootstrap_vs_baseline.brier_improvement_support)"
Write-Host "exotic_top3_2024_longshot_logloss_bootstrap_support=$($v24.longshot_proxy.paired_bootstrap_vs_baseline.binary_log_loss_improvement_support)"
Write-Host "exotic_top3_2024_longshot_brier_bootstrap_support=$($v24.longshot_proxy.paired_bootstrap_vs_baseline.brier_improvement_support)"
Write-Host "exotic_top3_development_safety_gate_passed=$($summary.development_safety_gate_passed)"

Write-Host "exotic_phase3_2023_trifecta_nll_delta=$($v23.combination_phase3.overall.trifecta_nll_delta)"
Write-Host "exotic_phase3_2023_trio_nll_delta=$($v23.combination_phase3.overall.trio_nll_delta)"
Write-Host "exotic_phase3_2023_trifecta_bootstrap_support=$($v23.combination_phase3.overall.paired_bootstrap_vs_baseline.trifecta_nll_improvement_support)"
Write-Host "exotic_phase3_2023_trio_bootstrap_support=$($v23.combination_phase3.overall.paired_bootstrap_vs_baseline.trio_nll_improvement_support)"
Write-Host "exotic_phase3_2023_longshot_trifecta_nll_delta=$($v23.combination_phase3.longshot_containing.trifecta_nll_delta)"
Write-Host "exotic_phase3_2023_longshot_trio_nll_delta=$($v23.combination_phase3.longshot_containing.trio_nll_delta)"
Write-Host "exotic_phase3_2023_longshot_trifecta_bootstrap_support=$($v23.combination_phase3.longshot_containing.paired_bootstrap_vs_baseline.trifecta_nll_improvement_support)"
Write-Host "exotic_phase3_2023_longshot_trio_bootstrap_support=$($v23.combination_phase3.longshot_containing.paired_bootstrap_vs_baseline.trio_nll_improvement_support)"
Write-Host "exotic_phase3_2024_trifecta_nll_delta=$($v24.combination_phase3.overall.trifecta_nll_delta)"
Write-Host "exotic_phase3_2024_trio_nll_delta=$($v24.combination_phase3.overall.trio_nll_delta)"
Write-Host "exotic_phase3_2024_trifecta_bootstrap_support=$($v24.combination_phase3.overall.paired_bootstrap_vs_baseline.trifecta_nll_improvement_support)"
Write-Host "exotic_phase3_2024_trio_bootstrap_support=$($v24.combination_phase3.overall.paired_bootstrap_vs_baseline.trio_nll_improvement_support)"
Write-Host "exotic_phase3_2024_longshot_trifecta_nll_delta=$($v24.combination_phase3.longshot_containing.trifecta_nll_delta)"
Write-Host "exotic_phase3_2024_longshot_trio_nll_delta=$($v24.combination_phase3.longshot_containing.trio_nll_delta)"
Write-Host "exotic_phase3_2024_longshot_trifecta_bootstrap_support=$($v24.combination_phase3.longshot_containing.paired_bootstrap_vs_baseline.trifecta_nll_improvement_support)"
Write-Host "exotic_phase3_2024_longshot_trio_bootstrap_support=$($v24.combination_phase3.longshot_containing.paired_bootstrap_vs_baseline.trio_nll_improvement_support)"
Write-Host "exotic_phase3_development_combination_gate_passed=$($summary.development_combination_gate_passed)"
