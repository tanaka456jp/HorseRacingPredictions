param(
    [string]$ValidationOutput = "artifacts/exotic_trio_phase6_runner_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

$venvPython = Join-Path $ProjectRoot ".venv-jravan\Scripts\python.exe"
$historyPath = Join-Path $ProjectRoot "data\jravan\full\current_history.csv"
$summaryPath = Join-Path $ProjectRoot "artifacts\exotic_trio_phase6\summary.json"

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    throw ".venv-jravan is missing; complete JRA-VAN Resume validation first."
}
if (-not (Test-Path -LiteralPath $historyPath -PathType Leaf)) {
    throw "current_history.csv is missing."
}

Write-Host "=== Exotic direct trio Phase 6 research ==="
Write-Host "[1/3] Refreshing local project package"
& $venvPython -m pip install -e ".[research]"
if ($LASTEXITCODE -ne 0) { throw "Project installation failed." }

Write-Host "[2/3] Training direct trio ranker and evaluating reused 2023/2024"
& $venvPython "scripts\evaluate_exotic_trio_phase6.py" --history $historyPath --output $summaryPath
if ($LASTEXITCODE -ne 0) { throw "Direct trio Phase 6 research failed." }
if (-not (Test-Path -LiteralPath $summaryPath -PathType Leaf)) {
    throw "Direct trio Phase 6 summary was not created."
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
    research_protocol = $summary.research_protocol
    evaluation_2023 = $v23
    evaluation_2024 = $v24
    development_direct_trio_gate_passed = [bool]$summary.development_direct_trio_gate_passed
}
$validationPath = Join-Path $ProjectRoot $ValidationOutput
$validationDir = Split-Path -Parent $validationPath
if (-not [string]::IsNullOrWhiteSpace($validationDir)) {
    New-Item -ItemType Directory -Force -Path $validationDir | Out-Null
}
$payload | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $validationPath -Encoding UTF8

Write-Host "exotic_phase6_2023_trio_nll_delta=$($v23.overall.trio_nll_delta_vs_phase5)"
Write-Host "exotic_phase6_2023_trio_bootstrap_support=$($v23.overall.paired_bootstrap_vs_phase5.trio_nll_improvement_support)"
Write-Host "exotic_phase6_2023_longshot_trio_nll_delta=$($v23.longshot_containing.trio_nll_delta_vs_phase5)"
Write-Host "exotic_phase6_2023_longshot_trio_bootstrap_support=$($v23.longshot_containing.paired_bootstrap_vs_phase5.trio_nll_improvement_support)"
Write-Host "exotic_phase6_2024_trio_nll_delta=$($v24.overall.trio_nll_delta_vs_phase5)"
Write-Host "exotic_phase6_2024_trio_bootstrap_support=$($v24.overall.paired_bootstrap_vs_phase5.trio_nll_improvement_support)"
Write-Host "exotic_phase6_2024_longshot_trio_nll_delta=$($v24.longshot_containing.trio_nll_delta_vs_phase5)"
Write-Host "exotic_phase6_2024_longshot_trio_bootstrap_support=$($v24.longshot_containing.paired_bootstrap_vs_phase5.trio_nll_improvement_support)"
Write-Host "exotic_phase6_development_direct_trio_gate_passed=$($summary.development_direct_trio_gate_passed)"

if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_STEP_SUMMARY)) {
    @(
        "### Exotic direct trio Phase 6 research",
        "",
        "- 2023 overall trio NLL delta vs Phase 5: $($v23.overall.trio_nll_delta_vs_phase5)",
        "- 2023 overall bootstrap support: $($v23.overall.paired_bootstrap_vs_phase5.trio_nll_improvement_support)",
        "- 2023 longshot trio NLL delta vs Phase 5: $($v23.longshot_containing.trio_nll_delta_vs_phase5)",
        "- 2023 longshot bootstrap support: $($v23.longshot_containing.paired_bootstrap_vs_phase5.trio_nll_improvement_support)",
        "- 2024 overall trio NLL delta vs Phase 5: $($v24.overall.trio_nll_delta_vs_phase5)",
        "- 2024 overall bootstrap support: $($v24.overall.paired_bootstrap_vs_phase5.trio_nll_improvement_support)",
        "- 2024 longshot trio NLL delta vs Phase 5: $($v24.longshot_containing.trio_nll_delta_vs_phase5)",
        "- 2024 longshot bootstrap support: $($v24.longshot_containing.paired_bootstrap_vs_phase5.trio_nll_improvement_support)",
        "- gate passed: $($summary.development_direct_trio_gate_passed)",
        "- final holdout: $($summary.research_protocol.final_holdout)",
        "- Forward Paper: $($summary.research_protocol.forward_paper)"
    ) | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding UTF8
}
