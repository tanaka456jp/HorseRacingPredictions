param(
    [string]$BaseHistory = "",
    [string]$Python = "python",
    [switch]$Full
)

$ErrorActionPreference = "Stop"

Write-Host "=== HorseRacingPredictions JRA-VAN Trial ==="
& $Python --version

Write-Host "[setup] Installing JRA-VAN trial dependencies"
& $Python -m pip install -r requirements-jravan.txt
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install requirements-jravan.txt"
}

Write-Host "[preflight] Verifying JV-Link COM runtime"
& $Python scripts/check_jravan_runtime.py --output artifacts/jravan_runtime.json
if ($LASTEXITCODE -ne 0) {
    throw "JV-Link runtime check failed. See artifacts/jravan_runtime.json"
}

Write-Host "[1/2] Bounded current-week RA/SE smoke"
& $Python scripts/jravan_trial_smoke.py
if ($LASTEXITCODE -ne 0) {
    throw "JRA-VAN smoke failed. See artifacts/jravan_smoke/"
}

if (-not $Full) {
    Write-Host "Smoke PASS. Re-run the same script with -Full to acquire and build current history."
    exit 0
}

Write-Host "[2/2] Full setup acquisition + Current History Intake"
$fullArgs = @("scripts/jravan_trial_full.py")
if (-not [string]::IsNullOrWhiteSpace($BaseHistory)) {
    $fullArgs += @("--base", $BaseHistory)
}
& $Python @fullArgs
if ($LASTEXITCODE -ne 0) {
    throw "Full JRA-VAN trial pipeline failed. See artifacts/jravan_full/"
}

Write-Host "JRA-VAN trial pipeline PASS."
