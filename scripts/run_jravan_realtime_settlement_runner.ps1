param(
    [string]$ValidationOutput = "artifacts/jravan_realtime_settlement_runner_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

$venvPython = Join-Path $ProjectRoot ".venv-jravan\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    throw ".venv-jravan is missing; complete Resume validation first."
}

Write-Host "=== JRA-VAN 0B12 Realtime Paper Settlement ==="
Write-Host "[1/4] Refreshing local project package"
& $venvPython -m pip install -e ".[research]"
if ($LASTEXITCODE -ne 0) { throw "Project installation failed." }

Write-Host "[2/4] Settling eligible Paper bets from 0B12"
$summaryPath = Join-Path $ProjectRoot "artifacts\jravan_realtime_settlement\summary.json"
& $venvPython "scripts\jravan_realtime_settlement.py" --ledger (Join-Path $ProjectRoot "data\paper\paper_trading.sqlite3") --output $summaryPath
if ($LASTEXITCODE -ne 0) { throw "Realtime settlement pipeline failed." }
if (-not (Test-Path -LiteralPath $summaryPath -PathType Leaf)) {
    throw "Realtime settlement summary was not created."
}

Write-Host "[3/4] Refreshing Residual v12 Paper evidence gate"
$evidencePath = Join-Path $ProjectRoot "artifacts\residual_v12_paper_evidence\summary.json"
& $venvPython "scripts\report_residual_v12_paper_evidence.py" --ledger (Join-Path $ProjectRoot "data\paper\paper_trading.sqlite3") --output $evidencePath
if ($LASTEXITCODE -ne 0) { throw "Residual v12 Paper evidence report failed." }
if (-not (Test-Path -LiteralPath $evidencePath -PathType Leaf)) {
    throw "Residual v12 Paper evidence summary was not created."
}
$evidence = Get-Content -LiteralPath $evidencePath -Raw -Encoding UTF8 | ConvertFrom-Json

Write-Host "[4/4] Writing sanitized validation"
$summary = Get-Content -LiteralPath $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
$validation = @{
    validated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    commit_sha = (& git rev-parse HEAD).Trim()
    runner_os = $env:RUNNER_OS
    runner_arch = $env:RUNNER_ARCH
    status = [string]$summary.status
    unsettled_before = [int]$summary.unsettled_before
    races_requested = [int]$summary.races_requested
    races_completed = [int]$summary.races_completed
    realtime_errors = [int]$summary.realtime_errors
    settled_now = [int]$summary.settled_now
    wins = [int]$summary.wins
    losses = [int]$summary.losses
    unsettled_after = [int]$summary.unsettled_after
    stake_settled_yen = [int]$summary.stake_settled_yen
    payout_yen = [int]$summary.payout_yen
    profit_yen = [int]$summary.profit_yen
    residual_evidence_status = [string]$evidence.status
    residual_prospective_evaluated_races = [int]$evidence.prospective_evaluated_races
    residual_settled_paper_bets = [int]$evidence.settled_paper_bets
    residual_evidence_sufficient = [bool]$evidence.sufficient_evidence
    residual_observed_positive_roi = [bool]$evidence.observed_positive_roi
    residual_roi = $evidence.roi
    residual_profit_yen = [int]$evidence.profit_yen
    residual_max_drawdown_yen = [int]$evidence.max_drawdown_yen
    residual_automatic_live_promotion = [bool]$evidence.automatic_live_promotion
}
$validationPath = Join-Path $ProjectRoot $ValidationOutput
$validationDir = Split-Path -Parent $validationPath
if (-not [string]::IsNullOrWhiteSpace($validationDir)) {
    New-Item -ItemType Directory -Force -Path $validationDir | Out-Null
}
$validation | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $validationPath -Encoding UTF8

if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_STEP_SUMMARY)) {
    @(
        "### JRA-VAN 0B12 Realtime Settlement",
        "",
        "- status: $($summary.status)",
        "- unsettled_before: $($summary.unsettled_before)",
        "- races_requested: $($summary.races_requested)",
        "- settled_now: $($summary.settled_now)",
        "- unsettled_after: $($summary.unsettled_after)",
        "- Residual v12 evidence status: $($evidence.status)",
        "- Residual prospective evaluated races: $($evidence.prospective_evaluated_races) / $($evidence.minimum_prospective_evaluated_races)",
        "- Residual settled Paper bets: $($evidence.settled_paper_bets) / $($evidence.minimum_settled_paper_bets)",
        "- Residual observed ROI: $($evidence.roi)",
        "- Residual max drawdown: $($evidence.max_drawdown_yen) yen",
        "- automatic live promotion: false"
    ) | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding UTF8
}

Write-Host "JRA-VAN 0B12 realtime settlement PASS."
Write-Host "status=$($summary.status)"
Write-Host "settled_now=$($summary.settled_now)"
Write-Host "residual_evidence_status=$($evidence.status)"
Write-Host "residual_prospective_evaluated_races=$($evidence.prospective_evaluated_races)"
Write-Host "residual_settled_paper_bets=$($evidence.settled_paper_bets)"
