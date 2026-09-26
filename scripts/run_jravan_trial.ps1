param(
    [string]$BaseHistory = "",
    [string]$Python = "python",
    [switch]$Full
)

$ErrorActionPreference = "Stop"

Write-Host "=== HorseRacingPredictions JRA-VAN Trial ==="
& $Python --version
& $Python -c 'import struct; print("Python bits=%d" % (struct.calcsize("P")*8))'

Write-Host "[setup] Installing JRA-VAN trial dependencies"
& $Python -m pip install -r requirements-jravan.txt
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install requirements-jravan.txt"
}

Write-Host "[1/3] JV-Link doctor"
& $Python scripts/jravan_doctor.py
if ($LASTEXITCODE -ne 0) {
    throw "JV-Link doctor failed. See artifacts/jravan_doctor.json"
}

Write-Host "[2/3] Bounded RA/SE smoke"
& $Python scripts/jravan_trial_smoke.py
if ($LASTEXITCODE -ne 0) {
    throw "JRA-VAN smoke failed. See artifacts/jravan_smoke/"
}

if (-not $Full) {
    Write-Host "Smoke PASS. Re-run the same script with -Full to acquire and build current history."
    exit 0
}

Write-Host "[3/3] Full setup acquisition + Current History Intake"
$fullArgs = @("scripts/jravan_trial_full.py")
if (-not [string]::IsNullOrWhiteSpace($BaseHistory)) {
    $fullArgs += @("--base", $BaseHistory)
}
& $Python @fullArgs
if ($LASTEXITCODE -ne 0) {
    throw "Full JRA-VAN trial pipeline failed. See artifacts/jravan_full/"
}

Write-Host "JRA-VAN trial pipeline PASS."
