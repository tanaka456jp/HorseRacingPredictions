param(
    [string]$ValidationOutput = "artifacts/ranker_v10_development_runner_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

$venvPython = Join-Path $ProjectRoot ".venv-jravan\Scripts\python.exe"
$historyPath = Join-Path $ProjectRoot "data\jravan\full\current_history.csv"
$championDir = Join-Path $ProjectRoot "artifacts\champion_v7"
$summaryPath = Join-Path $ProjectRoot "artifacts\ranker_v10_development\summary.json"

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    throw ".venv-jravan is missing; complete JRA-VAN Resume validation first."
}
if (-not (Test-Path -LiteralPath $historyPath -PathType Leaf)) {
    throw "current_history.csv is missing."
}

Write-Host "=== Ranker v10 development-only feature research ==="
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

Write-Host "[3/4] Comparing Ranker v9 vs v10 on development-only split"
& $venvPython "scripts\evaluate_ranker_v10_development.py" --history $historyPath --champion $championDir --output $summaryPath
if ($LASTEXITCODE -ne 0) { throw "Ranker v10 development research failed." }
if (-not (Test-Path -LiteralPath $summaryPath -PathType Leaf)) {
    throw "Ranker v10 development summary was not created."
}

Write-Host "[4/4] Writing sanitized validation"
$summary = Get-Content -LiteralPath $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
$selection = $summary.selection_2024
$features = $summary.features
$validation = @{
    validated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    commit_sha = (& git rev-parse HEAD).Trim()
    runner_os = $env:RUNNER_OS
    runner_arch = $env:RUNNER_ARCH
    status = [string]$summary.status
    training = $summary.training
    calibration = $summary.calibration
    selection_2024 = $selection
    v9_feature_count = [int]$features.v9_count
    v10_feature_count = [int]$features.v10_count
    added_feature_count = [int]$features.added_count
    added_feature_columns = $features.added_feature_columns
    development_gate_passed = [bool]$selection.development_gate_passed
}
$validationPath = Join-Path $ProjectRoot $ValidationOutput
$validationDir = Split-Path -Parent $validationPath
if (-not [string]::IsNullOrWhiteSpace($validationDir)) {
    New-Item -ItemType Directory -Force -Path $validationDir | Out-Null
}
$validation | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $validationPath -Encoding UTF8

if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_STEP_SUMMARY)) {
    @(
        "### Ranker v10 development-only research",
        "",
        "- selection period: $($selection.period_start) .. $($selection.period_end)",
        "- v9 winner log-loss: $($selection.v9_quality.winner_log_loss)",
        "- v10 winner log-loss: $($selection.v10_quality.winner_log_loss)",
        "- v9 Brier: $($selection.v9_quality.brier)",
        "- v10 Brier: $($selection.v10_quality.brier)",
        "- development gate passed: $($selection.development_gate_passed)",
        "- added features: $($features.added_count)"
    ) | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding UTF8
}

Write-Host "Ranker v10 development research PASS."
Write-Host "v9_log_loss=$($selection.v9_quality.winner_log_loss)"
Write-Host "v10_log_loss=$($selection.v10_quality.winner_log_loss)"
Write-Host "v9_brier=$($selection.v9_quality.brier)"
Write-Host "v10_brier=$($selection.v10_quality.brier)"
Write-Host "development_gate_passed=$($selection.development_gate_passed)"
