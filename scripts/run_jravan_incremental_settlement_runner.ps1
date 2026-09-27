param(
    [int]$OverlapDays = 7,
    [string]$ValidationOutput = "artifacts/jravan_incremental_runner_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

function Test-UsableFile {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    return (Get-Item -LiteralPath $Path).Length -gt 0
}

if ($OverlapDays -lt 0) { throw "OverlapDays must be non-negative." }

$parsedPath = Join-Path $ProjectRoot "data\jravan\full\parsed_history.csv"
$venvPython = Join-Path $ProjectRoot ".venv-jravan\Scripts\python.exe"
if (-not (Test-UsableFile $parsedPath)) {
    throw "parsed_history.csv is missing; incremental update cannot proceed."
}
if (-not (Test-UsableFile $venvPython)) {
    throw ".venv-jravan is missing; complete Resume validation first."
}

Write-Host "=== JRA-VAN Incremental History + Paper Settlement ==="
Write-Host "[1/3] Refreshing local project package"
& $venvPython -m pip install -e ".[research]"
if ($LASTEXITCODE -ne 0) { throw "Project installation failed." }

Write-Host "[2/3] Incremental completed-history update and settlement"
$argsList = @(
    "scripts\jravan_incremental_settlement.py",
    "--parsed", $parsedPath,
    "--output-dir", (Join-Path $ProjectRoot "data\jravan\full"),
    "--artifact-dir", (Join-Path $ProjectRoot "artifacts\jravan_incremental"),
    "--ledger", (Join-Path $ProjectRoot "data\paper\paper_trading.sqlite3"),
    "--overlap-days", [string]$OverlapDays
)
& $venvPython @argsList
if ($LASTEXITCODE -ne 0) {
    throw "Incremental history + settlement pipeline failed."
}

Write-Host "[3/3] Writing sanitized validation"
$summaryPath = Join-Path $ProjectRoot "artifacts\jravan_incremental\incremental_settlement_summary.json"
if (-not (Test-UsableFile $summaryPath)) {
    throw "incremental_settlement_summary.json was not created."
}
$summary = Get-Content -LiteralPath $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
$commit = (& git rev-parse HEAD).Trim()
$validation = @{
    validated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    commit_sha = $commit
    runner_os = $env:RUNNER_OS
    runner_arch = $env:RUNNER_ARCH
    incremental_status = [string]$summary.incremental.status
    existing_end = [string]$summary.incremental.existing_end
    requested_from_time = [string]$summary.incremental.requested_from_time
    raw_records = [int]$summary.incremental.raw_records
    parsed_update_rows = [int]$summary.incremental.parsed_update_rows
    parsed_update_races = [int]$summary.incremental.parsed_update_races
    eligible_update_rows = [int]$summary.incremental.eligible_update_rows
    eligible_update_races = [int]$summary.incremental.eligible_update_races
    replaced_races = [int]$summary.incremental.replaced_races
    merged_rows = [int]$summary.incremental.merged_rows
    merged_races = [int]$summary.incremental.merged_races
    merged_end = [string]$summary.incremental.merged_end
    current_history_end = [string]$summary.incremental.current_history_end
    winner_conflict_excluded_races = [int]$summary.incremental.winner_conflict_excluded_races
    winner_conflict_excluded_rows = [int]$summary.incremental.winner_conflict_excluded_rows
    settlement_settled_now = [int]$summary.settlement.settled_now
}
foreach ($name in @("unsettled_before","wins","losses","unsettled_after","stake_settled_yen","payout_yen","profit_yen")) {
    if ($null -ne $summary.settlement.$name) {
        $validation["settlement_$name"] = [int]$summary.settlement.$name
    }
}
$validationPath = Join-Path $ProjectRoot $ValidationOutput
$validationDir = Split-Path -Parent $validationPath
if (-not [string]::IsNullOrWhiteSpace($validationDir)) {
    New-Item -ItemType Directory -Force -Path $validationDir | Out-Null
}
$validation | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $validationPath -Encoding UTF8

if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_STEP_SUMMARY)) {
    @(
        "### JRA-VAN Incremental + Settlement",
        "",
        "- incremental_status: $($summary.incremental.status)",
        "- existing_end: $($summary.incremental.existing_end)",
        "- current_history_end: $($summary.incremental.current_history_end)",
        "- eligible_update_races: $($summary.incremental.eligible_update_races)",
        "- settlement_settled_now: $($summary.settlement.settled_now)"
    ) | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding UTF8
}

Write-Host "JRA-VAN incremental + settlement PASS."
Write-Host "incremental_status=$($summary.incremental.status)"
Write-Host "current_history_end=$($summary.incremental.current_history_end)"
Write-Host "settlement_settled_now=$($summary.settlement.settled_now)"
