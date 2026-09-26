param(
    [switch]$Full,
    [switch]$Resume,
    [string]$BaseHistory = "",
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

function Find-Python {
    param([string]$Requested)

    if (-not [string]::IsNullOrWhiteSpace($Requested)) {
        $command = Get-Command $Requested -ErrorAction SilentlyContinue
        if ($null -eq $command) {
            throw "Requested Python command not found: $Requested"
        }
        return @{
            Command = $command.Source
            Prefix = @()
        }
    }

    $py = Get-Command "py.exe" -ErrorAction SilentlyContinue
    if ($null -ne $py) {
        & $py.Source -3.14 -c "import sys; print(sys.executable)" *> $null
        if ($LASTEXITCODE -eq 0) {
            return @{
                Command = $py.Source
                Prefix = @("-3.14")
            }
        }

        & $py.Source -3 -c "import sys; print(sys.executable)" *> $null
        if ($LASTEXITCODE -eq 0) {
            return @{
                Command = $py.Source
                Prefix = @("-3")
            }
        }
    }

    $python = Get-Command "python.exe" -ErrorAction SilentlyContinue
    if ($null -ne $python) {
        return @{
            Command = $python.Source
            Prefix = @()
        }
    }

    throw "Python 3.11+ was not found. Install Python for Windows and retry."
}

function Invoke-BasePython {
    param(
        [hashtable]$Spec,
        [string[]]$Arguments
    )
    & $Spec.Command @($Spec.Prefix) @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed: $($Arguments -join ' ')"
    }
}

function Reset-JraVanArtifacts {
    $targets = @(
        "artifacts\jravan_runtime.json",
        "artifacts\jravan_smoke",
        "artifacts\jravan_full",
        "artifacts\jravan_support",
        "artifacts\jravan_support_bundle.zip"
    )

    foreach ($relative in $targets) {
        $target = Join-Path $ProjectRoot $relative
        if (Test-Path $target) {
            Remove-Item $target -Recurse -Force
        }
    }
}

function Write-SupportBundle {
    $bundleDir = Join-Path $ProjectRoot "artifacts\jravan_support"
    $bundleZip = Join-Path $ProjectRoot "artifacts\jravan_support_bundle.zip"
    if (Test-Path $bundleDir) {
        Remove-Item $bundleDir -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $bundleDir | Out-Null

    $candidates = @(
        "artifacts\jravan_runtime.json",
        "artifacts\jravan_smoke",
        "artifacts\jravan_full",
        "artifacts\jravan_race_raw_summary.json"
    )

    foreach ($relative in $candidates) {
        $source = Join-Path $ProjectRoot $relative
        if (Test-Path $source) {
            Copy-Item $source -Destination $bundleDir -Recurse -Force
        }
    }

    $environmentFile = Join-Path $bundleDir "environment.txt"
    @(
        "timestamp=$(Get-Date -Format o)",
        "project=$ProjectRoot",
        "os=$([System.Environment]::OSVersion.VersionString)",
        "powershell=$($PSVersionTable.PSVersion)"
    ) | Set-Content -Path $environmentFile -Encoding UTF8

    if (Test-Path $bundleZip) {
        Remove-Item $bundleZip -Force
    }
    Compress-Archive -Path (Join-Path $bundleDir "*") -DestinationPath $bundleZip -Force
    Write-Host "Support bundle: $bundleZip"
}

Write-Host "=== HorseRacingPredictions JRA-VAN Bootstrap ==="
Write-Host "Project: $ProjectRoot"

if ($Full -and $Resume) {
    throw "-Full and -Resume cannot be used together."
}

$exitCode = 0
try {
    $pythonSpec = Find-Python -Requested $Python

    Write-Host "[1/5] Creating isolated Python environment"
    $venvDir = Join-Path $ProjectRoot ".venv-jravan"
    $venvPython = Join-Path $venvDir "Scripts\python.exe"

    if (-not (Test-Path $venvPython)) {
        Invoke-BasePython -Spec $pythonSpec -Arguments @(
            "-m", "venv", $venvDir
        )
    }

    Write-Host "[2/5] Installing project + JRA-VAN dependencies"
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "pip upgrade failed"
    }

    & $venvPython -m pip install -e ".[research]"
    if ($LASTEXITCODE -ne 0) {
        throw "Project installation failed"
    }

    & $venvPython -m pip install -r requirements-jravan.txt
    if ($LASTEXITCODE -ne 0) {
        throw "JRA-VAN dependency installation failed"
    }

    Reset-JraVanArtifacts

    if ($Resume) {
        Write-Host "[3/5] Resume preflight: existing parsed history"
        $parsedPath = Join-Path $ProjectRoot "data\jravan\full\parsed_history.csv"
        if (-not (Test-Path $parsedPath)) {
            throw "Resume requires data\jravan\full\parsed_history.csv"
        }

        Write-Host "[4/5] Resuming Current History Intake without JV-Link reacquisition"
        $resumeArgs = @(
            (Join-Path $ProjectRoot "scripts\jravan_trial_resume.py")
        )
        if (-not [string]::IsNullOrWhiteSpace($BaseHistory)) {
            $resumeArgs += @("--base", $BaseHistory)
        }
        & $venvPython @resumeArgs
        if ($LASTEXITCODE -ne 0) {
            throw "JRA-VAN resume workflow failed"
        }
    }
    else {
        Write-Host "[3/5] Verifying Python and JV-Link COM"
        & $venvPython (Join-Path $ProjectRoot "scripts\check_jravan_runtime.py") --output (Join-Path $ProjectRoot "artifacts\jravan_runtime.json")
        if ($LASTEXITCODE -ne 0) {
            throw "Python/JV-Link runtime check failed"
        }

        Write-Host "[4/5] Running RA/SE smoke / optional full acquisition"
        $trialArgs = @(
            "-ExecutionPolicy", "Bypass",
            "-File", (Join-Path $ProjectRoot "scripts\run_jravan_trial.ps1"),
            "-Python", $venvPython
        )
        if ($Full) {
            $trialArgs += "-Full"
        }
        if (-not [string]::IsNullOrWhiteSpace($BaseHistory)) {
            $trialArgs += @("-BaseHistory", $BaseHistory)
        }

        & powershell.exe @trialArgs
        if ($LASTEXITCODE -ne 0) {
            throw "JRA-VAN trial workflow failed"
        }
    }

    Write-Host "[5/5] Packaging audit/support report"
    Write-SupportBundle

    if ($Full -or $Resume) {
        $historyPath = Join-Path $ProjectRoot "data\jravan\full\current_history.csv"
        if (-not (Test-Path $historyPath)) {
            throw "Run ended without current_history.csv"
        }
        Write-Host "Current history: $historyPath"
    }

    Write-Host "JRA-VAN bootstrap PASS."
}
catch {
    $exitCode = 2
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    try {
        Write-SupportBundle
    }
    catch {
        Write-Host "Support bundle creation also failed: $($_.Exception.Message)"
    }
}
finally {
    if ($exitCode -ne 0) {
        exit $exitCode
    }
}
