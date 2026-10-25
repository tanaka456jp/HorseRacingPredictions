param([string]$OutputPath = "artifacts/pc2_pywin32_venv_status.json")
$ErrorActionPreference = 'Stop'
# Free-only, pinned PyPI SHA256, no global/site-wide pip, no registry,
# no JV-Link settings/key operations, no deletion or replacement of files.
$expectedComputer = 'DESKTOP-MVV1FD4'
$venvRoot = 'D:\HorseRacingPredictions\runtime\pc2-jvlink64-py314-312'
$venvPython = Join-Path $venvRoot 'Scripts\python.exe'
$marker = Join-Path $venvRoot '.horse-jvlink64-diagnostic-owned.txt'
$requirements = Join-Path $PSScriptRoot '..\requirements-pc2-jvlink64-py314.txt'
$report = [ordered]@{
    schemaVersion = 1
    status = 'BLOCKED'
    physicalPC2Verified = ($env:COMPUTERNAME -eq $expectedComputer)
    venvExpectedOnD = $true
    venvExistingReplaced = $false
    dependencyInstallAttempted = $false
    dependencyVerified = $false
    selectedPythonBits = 0
    blocker = 'NOT_STARTED'
    usageKeyRead = $false
    jvlinkInvoked = $false
    serviceChanged = $false
    rawRecordsRead = $false
    notePostAttempted = $false
    publicationAuthorized = $false
}
try {
    if ($env:COMPUTERNAME -ne $expectedComputer) {
        throw 'NOT_PHYSICAL_PC2'
    }
    $drive = Get-PSDrive -Name D -ErrorAction Stop
    if ($drive.Free -lt 800MB) { throw 'INSUFFICIENT_D_SPACE' }
    if (-not (Test-Path -LiteralPath $requirements -PathType Leaf)) {
        throw 'PINNED_REQUIREMENTS_MISSING'
    }
    if (Test-Path -LiteralPath $venvRoot -PathType Container) {
        if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
            throw 'EXISTING_UNOWNED_VENV_WILL_NOT_BE_MODIFIED'
        }
        $markerText = Get-Content -LiteralPath $marker -Raw
        if ($markerText.Trim() -ne 'HorseRacingPredictions PC2 isolated pywin32 only') {
            throw 'UNTRUSTED_VENV_PROVENANCE'
        }
    } else {
        New-Item -ItemType Directory -Path (Split-Path -Parent $venvRoot) -Force |
            Out-Null
        # New dedicated D directory only; never modify installed system Python.
        & py -3 -m venv $venvRoot 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0 -or
            -not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
            throw 'D_VENV_CREATION_FAILED'
        }
        Set-Content -LiteralPath $marker -Encoding UTF8 -Value (
            'HorseRacingPredictions PC2 isolated pywin32 only'
        )
    }
    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        throw 'D_VENV_PYTHON_MISSING'
    }
    $probe = Join-Path $PSScriptRoot 'inspect_pc2_python64_metadata.py'
    $metadata = @(& $venvPython $probe 2>$null)
    if ($LASTEXITCODE -ne 0 -or @($metadata).Count -eq 0) {
        throw 'VENV_ARCHITECTURE_PROBE_FAILED'
    }
    $arch = ($metadata -join [Environment]::NewLine) | ConvertFrom-Json
    $report.selectedPythonBits = [int]$arch.bits
    if ($arch.bits -ne 64) { throw 'ONLY_64BIT_PYTHON_ALLOWED' }
    if (-not $arch.pywin32) {
        $report.dependencyInstallAttempted = $true
        # Official PyPI wheel only, exact SHA256 pinned, and no dependencies.
        # All package bytes and pip working files reside in this D venv
        # where possible. This cannot change a JRA-VAN subscription/key.
        & $venvPython -m pip install --disable-pip-version-check `
            --no-cache-dir --no-deps --only-binary=:all: `
            --require-hashes --index-url https://pypi.org/simple `
            -r $requirements 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'HASHED_FREE_PYWIN32_INSTALL_FAILED' }
    }
    $verified = @(& $venvPython $probe 2>$null)
    if ($LASTEXITCODE -ne 0 -or @($verified).Count -eq 0) {
        throw 'PYWIN32_POSTINSTALL_PROBE_FAILED'
    }
    $ready = ($verified -join [Environment]::NewLine) | ConvertFrom-Json
    $report.dependencyVerified = ($ready.bits -eq 64 -and $ready.pywin32 -eq $true)
    if (-not $report.dependencyVerified) {
        throw 'VENV_PYWIN32_IMPORT_UNAVAILABLE'
    }
    $report.status = 'ISOLATED_PYTHON64_COM_DEPENDENCY_READY'
    $report.blocker = ''
} catch {
    # No exception details, paths, user names or downloaded content in CI.
    $allowed = @(
        'NOT_PHYSICAL_PC2','INSUFFICIENT_D_SPACE',
        'PINNED_REQUIREMENTS_MISSING',
        'EXISTING_UNOWNED_VENV_WILL_NOT_BE_MODIFIED',
        'UNTRUSTED_VENV_PROVENANCE',
        'D_VENV_CREATION_FAILED','D_VENV_PYTHON_MISSING',
        'VENV_ARCHITECTURE_PROBE_FAILED','ONLY_64BIT_PYTHON_ALLOWED',
        'HASHED_FREE_PYWIN32_INSTALL_FAILED',
        'PYWIN32_POSTINSTALL_PROBE_FAILED',
        'VENV_PYWIN32_IMPORT_UNAVAILABLE'
    )
    $last = [string]$_.Exception.Message
    $report.blocker = if ($last -in $allowed) { $last } else {
        'ISOLATED_ENVIRONMENT_PREPARATION_FAILED'
    }
} finally {
    $dir = Split-Path -Parent $OutputPath
    if ($dir) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $report | ConvertTo-Json -Depth 5 |
        Set-Content -LiteralPath $OutputPath -Encoding UTF8
    Get-Content -LiteralPath $OutputPath -Encoding UTF8
    # Previous caught pip failures must not escape as stale runner failures.
    $global:LASTEXITCODE = 0
}
