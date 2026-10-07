param(
    [string]$ValidationOutput = "artifacts/exotic_longshot_phase8_runner_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

$venvPython = Join-Path $ProjectRoot ".venv-jravan\Scripts\python.exe"
$historyPath = Join-Path $ProjectRoot "data\jravan\full\current_history.csv"
$summaryPath = Join-Path $ProjectRoot "artifacts\exotic_longshot_phase8\summary.json"

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    throw ".venv-jravan is missing; complete JRA-VAN Resume validation first."
}
if (-not (Test-Path -LiteralPath $historyPath -PathType Leaf)) {
    throw "current_history.csv is missing."
}

Write-Host "=== Exotic longshot ranking Phase 8 research ==="
Write-Host "[1/3] Refreshing local project package"
& $venvPython -m pip install -e ".[research]"
if ($LASTEXITCODE -ne 0) { throw "Project installation failed." }

Write-Host "[2/3] Training longshot ranker and evaluating reused 2023/2024"
& $venvPython "scripts\evaluate_exotic_longshot_phase8.py" --history $historyPath --output $summaryPath
if ($LASTEXITCODE -ne 0) { throw "Longshot ranking Phase 8 research failed." }
if (-not (Test-Path -LiteralPath $summaryPath -PathType Leaf)) {
    throw "Longshot ranking Phase 8 summary was not created."
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
    development_longshot_ranker_gate_passed = [bool]$summary.development_longshot_ranker_gate_passed
}
$validationPath = Join-Path $ProjectRoot $ValidationOutput
$validationDir = Split-Path -Parent $validationPath
if (-not [string]::IsNullOrWhiteSpace($validationDir)) {
    New-Item -ItemType Directory -Force -Path $validationDir | Out-Null
}
$payload | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $validationPath -Encoding UTF8

Write-Host "exotic_phase8_2023_top1_hit_rate_delta=$($v23.top1.hit_rate_delta)"
Write-Host "exotic_phase8_2023_mrr_delta=$($v23.mrr.delta)"
Write-Host "exotic_phase8_2023_top1_bootstrap_support=$($v23.paired_bootstrap_vs_general_top3_ranking.top1_hit_rate_improvement_support)"
Write-Host "exotic_phase8_2023_mrr_bootstrap_support=$($v23.paired_bootstrap_vs_general_top3_ranking.mrr_improvement_support)"
Write-Host "exotic_phase8_2024_top1_hit_rate_delta=$($v24.top1.hit_rate_delta)"
Write-Host "exotic_phase8_2024_mrr_delta=$($v24.mrr.delta)"
Write-Host "exotic_phase8_2024_top1_bootstrap_support=$($v24.paired_bootstrap_vs_general_top3_ranking.top1_hit_rate_improvement_support)"
Write-Host "exotic_phase8_2024_mrr_bootstrap_support=$($v24.paired_bootstrap_vs_general_top3_ranking.mrr_improvement_support)"
Write-Host "exotic_phase8_development_longshot_ranker_gate_passed=$($summary.development_longshot_ranker_gate_passed)"

if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_STEP_SUMMARY)) {
    @(
        "### Exotic longshot ranking Phase 8",
        "",
        "- 2023 top1 hit-rate delta: $($v23.top1.hit_rate_delta)",
        "- 2023 MRR delta: $($v23.mrr.delta)",
        "- 2023 top1 bootstrap support: $($v23.paired_bootstrap_vs_general_top3_ranking.top1_hit_rate_improvement_support)",
        "- 2023 MRR bootstrap support: $($v23.paired_bootstrap_vs_general_top3_ranking.mrr_improvement_support)",
        "- 2024 top1 hit-rate delta: $($v24.top1.hit_rate_delta)",
        "- 2024 MRR delta: $($v24.mrr.delta)",
        "- 2024 top1 bootstrap support: $($v24.paired_bootstrap_vs_general_top3_ranking.top1_hit_rate_improvement_support)",
        "- 2024 MRR bootstrap support: $($v24.paired_bootstrap_vs_general_top3_ranking.mrr_improvement_support)",
        "- gate passed: $($summary.development_longshot_ranker_gate_passed)",
        "- final holdout: $($summary.research_protocol.final_holdout)",
        "- Forward Paper: $($summary.research_protocol.forward_paper)"
    ) | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding UTF8
}
