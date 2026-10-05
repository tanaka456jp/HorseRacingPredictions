param(
    [string]$ValidationOutput = "artifacts/market_residual_v12_runner_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

$venvPython = Join-Path $ProjectRoot ".venv-jravan\Scripts\python.exe"
$historyPath = Join-Path $ProjectRoot "data\jravan\full\current_history.csv"
$championDir = Join-Path $ProjectRoot "artifacts\champion_v7"
$summaryPath = Join-Path $ProjectRoot "artifacts\market_residual_v12\summary.json"

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    throw ".venv-jravan is missing; complete JRA-VAN Resume validation first."
}
if (-not (Test-Path -LiteralPath $historyPath -PathType Leaf)) {
    throw "current_history.csv is missing."
}

Write-Host "=== Market residual v12 development research ==="
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

Write-Host "[3/4] Training residual model and validating 2023/2024"
& $venvPython "scripts\evaluate_market_residual_v12.py" --history $historyPath --champion $championDir --output $summaryPath
if ($LASTEXITCODE -ne 0) { throw "Market residual v12 research failed." }
if (-not (Test-Path -LiteralPath $summaryPath -PathType Leaf)) {
    throw "Market residual v12 summary was not created."
}

Write-Host "[4/4] Writing sanitized validation"
$summary = Get-Content -LiteralPath $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
$v23 = $summary.validation_2023
$v24 = $summary.validation_2024
$payload = @{
    validated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    commit_sha = (& git rev-parse HEAD).Trim()
    runner_os = $env:RUNNER_OS
    runner_arch = $env:RUNNER_ARCH
    status = [string]$summary.status
    training = $summary.training
    gamma_tuning_period_start = [string]$summary.gamma_tuning.period_start
    gamma_tuning_period_end = [string]$summary.gamma_tuning.period_end
    gamma_tuning_rows = [int]$summary.gamma_tuning.rows
    gamma_tuning_races = [int]$summary.gamma_tuning.races
    selected_gamma = [double]$summary.gamma_tuning.selected_gamma
    gamma_sweep = $summary.gamma_tuning.sweep
    ev_rule_tuning_2022 = $summary.ev_rule_tuning_2022
    market_edge_rule_tuning_2022 = $summary.market_edge_rule_tuning_2022
    broad_market_edge_rule_tuning_2022 = $summary.broad_market_edge_rule_tuning_2022
    market_edge_odds_segment_tuning_2022 = $summary.market_edge_odds_segment_tuning_2022
    longshot_market_edge_tuning_2022 = $summary.longshot_market_edge_tuning_2022
    stable_longshot_market_edge_tuning_2022 = $summary.stable_longshot_market_edge_tuning_2022
    direct_value_tuning_2022 = $summary.direct_value_tuning_2022
    validation_2023 = $v23
    validation_2024 = $v24
    development_gate_passed = [bool]$summary.development_gate_passed
    ev_development_gate_passed = [bool]$summary.ev_development_gate_passed
    market_edge_development_gate_passed = [bool]$summary.market_edge_development_gate_passed
    broad_market_edge_development_gate_passed = [bool]$summary.broad_market_edge_development_gate_passed
    market_edge_odds_segment_development_gate_passed = [bool]$summary.market_edge_odds_segment_development_gate_passed
    longshot_market_edge_development_gate_passed = [bool]$summary.longshot_market_edge_development_gate_passed
    stable_longshot_market_edge_development_gate_passed = [bool]$summary.stable_longshot_market_edge_development_gate_passed
    direct_value_development_gate_passed = [bool]$summary.direct_value_development_gate_passed
    ev_constraints = $summary.ev_constraints
}
$validationPath = Join-Path $ProjectRoot $ValidationOutput
$validationDir = Split-Path -Parent $validationPath
if (-not [string]::IsNullOrWhiteSpace($validationDir)) {
    New-Item -ItemType Directory -Force -Path $validationDir | Out-Null
}
$payload | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $validationPath -Encoding UTF8

if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_STEP_SUMMARY)) {
    @(
        "### Market residual v12 development research",
        "",
        "- selected gamma: $($summary.gamma_tuning.selected_gamma)",
        "- 2023 market winner log-loss: $($v23.market_quality.winner_log_loss)",
        "- 2023 residual winner log-loss: $($v23.residual_quality.winner_log_loss)",
        "- 2023 market Brier: $($v23.market_quality.brier)",
        "- 2023 residual Brier: $($v23.residual_quality.brier)",
        "- 2024 market winner log-loss: $($v24.market_quality.winner_log_loss)",
        "- 2024 residual winner log-loss: $($v24.residual_quality.winner_log_loss)",
        "- 2024 market Brier: $($v24.market_quality.brier)",
        "- 2024 residual Brier: $($v24.residual_quality.brier)",
        "- development gate passed: $($summary.development_gate_passed)",
        "- fitted EV rule: $($summary.ev_rule_tuning_2022.fitted_rule | ConvertTo-Json -Compress)",
        "- 2023 fixed EV result: $($v23.fixed_ev_rule_result | ConvertTo-Json -Compress)",
        "- 2024 fixed EV result: $($v24.fixed_ev_rule_result | ConvertTo-Json -Compress)",
        "- EV development gate passed: $($summary.ev_development_gate_passed)",
        "- fitted market-edge rule: $($summary.market_edge_rule_tuning_2022.fitted_rule | ConvertTo-Json -Compress)",
        "- 2023 fixed market-edge result: $($v23.fixed_market_edge_rule_result | ConvertTo-Json -Compress)",
        "- 2024 fixed market-edge result: $($v24.fixed_market_edge_rule_result | ConvertTo-Json -Compress)",
        "- market-edge development gate passed: $($summary.market_edge_development_gate_passed)",
        "- fitted broad market-edge rule: $($summary.broad_market_edge_rule_tuning_2022.fitted_rule | ConvertTo-Json -Compress)",
        "- 2023 broad market-edge result: $($v23.fixed_broad_market_edge_rule_result | ConvertTo-Json -Compress)",
        "- 2024 broad market-edge result: $($v24.fixed_broad_market_edge_rule_result | ConvertTo-Json -Compress)",
        "- broad market-edge gate passed: $($summary.broad_market_edge_development_gate_passed)",
        "- fitted odds segment rule: $($summary.market_edge_odds_segment_tuning_2022.fitted_rule | ConvertTo-Json -Compress)",
        "- 2023 fixed odds segment result: $($v23.fixed_market_edge_odds_segment_result | ConvertTo-Json -Compress)",
        "- 2024 fixed odds segment result: $($v24.fixed_market_edge_odds_segment_result | ConvertTo-Json -Compress)",
        "- odds segment development gate passed: $($summary.market_edge_odds_segment_development_gate_passed)",
        "- fitted longshot market-edge rule: $($summary.longshot_market_edge_tuning_2022.fitted_rule | ConvertTo-Json -Compress)",
        "- 2023 fixed longshot result: $($v23.fixed_longshot_market_edge_result | ConvertTo-Json -Compress)",
        "- 2024 fixed longshot result: $($v24.fixed_longshot_market_edge_result | ConvertTo-Json -Compress)",
        "- longshot development gate passed: $($summary.longshot_market_edge_development_gate_passed)",
        "- fitted stable longshot rule: $($summary.stable_longshot_market_edge_tuning_2022.fitted_rule | ConvertTo-Json -Compress)",
        "- 2023 stable longshot result: $($v23.fixed_stable_longshot_market_edge_result | ConvertTo-Json -Compress)",
        "- 2024 stable longshot result: $($v24.fixed_stable_longshot_market_edge_result | ConvertTo-Json -Compress)",
        "- stable longshot gate passed: $($summary.stable_longshot_market_edge_development_gate_passed)",
        "- direct-value tuning evidence: $($summary.direct_value_tuning_2022.evidence | ConvertTo-Json -Compress)",
        "- fitted direct-value rule: $($summary.direct_value_tuning_2022.fitted_rule | ConvertTo-Json -Compress)",
        "- 2023 fixed direct-value result: $($v23.fixed_direct_value_rule_result | ConvertTo-Json -Compress)",
        "- 2024 fixed direct-value result: $($v24.fixed_direct_value_rule_result | ConvertTo-Json -Compress)",
        "- direct-value gate passed: $($summary.direct_value_development_gate_passed)"
    ) | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding UTF8
}

Write-Host "Market residual v12 development research PASS."
Write-Host "selected_gamma=$($summary.gamma_tuning.selected_gamma)"
Write-Host "v2023_log_loss_delta=$($v23.winner_log_loss_delta_vs_market)"
Write-Host "v2023_brier_delta=$($v23.brier_delta_vs_market)"
Write-Host "v2024_log_loss_delta=$($v24.winner_log_loss_delta_vs_market)"
Write-Host "v2024_brier_delta=$($v24.brier_delta_vs_market)"
Write-Host "development_gate_passed=$($summary.development_gate_passed)"
Write-Host "fitted_ev_rule=$($summary.ev_rule_tuning_2022.fitted_rule | ConvertTo-Json -Compress)"
Write-Host "v2023_fixed_ev=$($v23.fixed_ev_rule_result | ConvertTo-Json -Compress)"
Write-Host "v2024_fixed_ev=$($v24.fixed_ev_rule_result | ConvertTo-Json -Compress)"
Write-Host "ev_development_gate_passed=$($summary.ev_development_gate_passed)"
Write-Host "fitted_market_edge_rule=$($summary.market_edge_rule_tuning_2022.fitted_rule | ConvertTo-Json -Compress)"
Write-Host "v2023_fixed_market_edge=$($v23.fixed_market_edge_rule_result | ConvertTo-Json -Compress)"
Write-Host "v2024_fixed_market_edge=$($v24.fixed_market_edge_rule_result | ConvertTo-Json -Compress)"
Write-Host "market_edge_development_gate_passed=$($summary.market_edge_development_gate_passed)"
Write-Host "fitted_broad_market_edge_rule=$($summary.broad_market_edge_rule_tuning_2022.fitted_rule | ConvertTo-Json -Compress)"
Write-Host "v2023_broad_market_edge=$($v23.fixed_broad_market_edge_rule_result | ConvertTo-Json -Compress)"
Write-Host "v2024_broad_market_edge=$($v24.fixed_broad_market_edge_rule_result | ConvertTo-Json -Compress)"
Write-Host "broad_market_edge_development_gate_passed=$($summary.broad_market_edge_development_gate_passed)"
Write-Host "fitted_odds_segment_rule=$($summary.market_edge_odds_segment_tuning_2022.fitted_rule | ConvertTo-Json -Compress)"
Write-Host "v2023_fixed_odds_segment=$($v23.fixed_market_edge_odds_segment_result | ConvertTo-Json -Compress)"
Write-Host "v2024_fixed_odds_segment=$($v24.fixed_market_edge_odds_segment_result | ConvertTo-Json -Compress)"
Write-Host "odds_segment_development_gate_passed=$($summary.market_edge_odds_segment_development_gate_passed)"
Write-Host "fitted_longshot_market_edge_rule=$($summary.longshot_market_edge_tuning_2022.fitted_rule | ConvertTo-Json -Compress)"
Write-Host "v2023_fixed_longshot=$($v23.fixed_longshot_market_edge_result | ConvertTo-Json -Compress)"
Write-Host "v2024_fixed_longshot=$($v24.fixed_longshot_market_edge_result | ConvertTo-Json -Compress)"
Write-Host "longshot_market_edge_development_gate_passed=$($summary.longshot_market_edge_development_gate_passed)"
Write-Host "fitted_stable_longshot_rule=$($summary.stable_longshot_market_edge_tuning_2022.fitted_rule | ConvertTo-Json -Compress)"
Write-Host "v2023_stable_longshot=$($v23.fixed_stable_longshot_market_edge_result | ConvertTo-Json -Compress)"
Write-Host "v2024_stable_longshot=$($v24.fixed_stable_longshot_market_edge_result | ConvertTo-Json -Compress)"
Write-Host "stable_longshot_market_edge_development_gate_passed=$($summary.stable_longshot_market_edge_development_gate_passed)"
Write-Host "direct_value_tuning_evidence=$($summary.direct_value_tuning_2022.evidence | ConvertTo-Json -Compress)"
Write-Host "fitted_direct_value_rule=$($summary.direct_value_tuning_2022.fitted_rule | ConvertTo-Json -Compress)"
Write-Host "v2023_fixed_direct_value=$($v23.fixed_direct_value_rule_result | ConvertTo-Json -Compress)"
Write-Host "v2024_fixed_direct_value=$($v24.fixed_direct_value_rule_result | ConvertTo-Json -Compress)"
Write-Host "direct_value_development_gate_passed=$($summary.direct_value_development_gate_passed)"
