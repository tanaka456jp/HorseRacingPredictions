param(
    [Parameter(Mandatory = $true)]
    [string]$RunnerRoot
)

$ErrorActionPreference = "Stop"
$runnerRootFull = [System.IO.Path]::GetFullPath($RunnerRoot)
$listener = Join-Path $runnerRootFull "bin\Runner.Listener.exe"
$runCmd = Join-Path $runnerRootFull "run.cmd"

$alreadyRunning = Get-CimInstance Win32_Process -Filter "Name='Runner.Listener.exe'" |
    Where-Object {
        -not [string]::IsNullOrWhiteSpace([string]$_.ExecutablePath) -and
        [System.IO.Path]::GetFullPath([string]$_.ExecutablePath).StartsWith(
            $runnerRootFull,
            [System.StringComparison]::OrdinalIgnoreCase
        )
    }

if ($alreadyRunning) {
    exit 0
}

if (-not (Test-Path -LiteralPath $listener -PathType Leaf)) {
    throw "Runner.Listener.exe is missing."
}
if (-not (Test-Path -LiteralPath $runCmd -PathType Leaf)) {
    throw "run.cmd is missing."
}

Start-Process -FilePath "cmd.exe" -ArgumentList @(
    "/c",
    "`"$runCmd`""
) -WorkingDirectory $runnerRootFull -WindowStyle Hidden