param(
    [string]$PythonPathPath,
    [string]$ReportPath,
    [int]$TimeoutSeconds = 90
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    throw "PythonPath is required."
}
if ([string]::IsNullOrWhiteSpace($ReportPath)) {
    throw "ReportPath is required."
}
$script = Join-Path $PSScriptRoot "probe_jravan_free_trial_race_auth.py"
if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    throw "Python executable is missing."
}
if (-not (Test-Path -LiteralPath $script -PathType Leaf)) {
    throw "Probe script is missing."
}
if ($TimeoutSeconds -lt 10 -or $TimeoutSeconds -gt 300) {
    throw "TimeoutSeconds must be between 10 and 300."
}

$outputPath = [System.IO.Path]::GetFullPath($ReportPath)
$outputDir = Split-Path -LiteralPath $outputPath -Parent
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

$stdout = Join-Path $env:RUNNER_TEMP "jravan-race-auth-probe.stdout.txt"
$stderr = Join-Path $env:RUNNER_TEMP "jravan-race-auth-probe.stderr.txt"
Remove-Item -LiteralPath $stdout,$stderr -ErrorAction SilentlyContinue

$process = Start-Process -FilePath $PythonPath -ArgumentList @(
    $script,
    "--output",
    $outputPath
) -WorkingDirectory (Split-Path -LiteralPath $PSScriptRoot -Parent) -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru -WindowStyle Hidden

if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    $timeoutReport = [ordered]@{
        status = "probe_timeout"
        timeout_seconds = $TimeoutSeconds
        raw_records_read = $false
        paid_action_authorized = $false
        protected_holdout = "2025-2026 untouched"
        guidance = "JV-Link COM probe did not return before timeout. Do not loop retries; use the official JRA-VAN sample/validation tool on this PC."
    }
    $timeoutReport | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $outputPath -Encoding UTF8
    Write-Warning "JRA-VAN auth probe timed out after $TimeoutSeconds seconds."
    exit 3
}

if (Test-Path -LiteralPath $stdout -PathType Leaf) {
    Get-Content -LiteralPath $stdout
}
if (Test-Path -LiteralPath $stderr -PathType Leaf) {
    $safeError = Get-Content -LiteralPath $stderr | Where-Object {
        $_ -notmatch '(?i)(usage.?key|利用キー)\s*[:=]\s*\S+'
    }
    if ($safeError) {
        $safeError | Write-Warning
    }
}

exit $process.ExitCode