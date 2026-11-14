param(
    [string]$OutputPath = 'artifacts/sunday_20261025_readiness.json'
)

$ErrorActionPreference = 'Stop'
# This is a *read-only* PC2 diagnostic. No JRA-VAN API or licence key access,
# model retraining, note session access, runner reconfiguration, or betting.
$archive = 'D:\JRA-VAN\Data Lab\archive\pre2025'
$bundle = 'D:\HorseRacingPredictions\approved-sunday-20261025'
$physicalPC2 = ($env:COMPUTERNAME -eq 'DESKTOP-MVV1FD4')
$required = @(
    @{ label='MODEL'; relative='model\manifest.json' },
    @{ label='MODEL'; relative='model\model.cbm' },
    @{ label='HISTORY'; relative='race_history.csv' },
    @{ label='ENTRIES'; relative='sunday_entries.csv' },
    @{ label='RACE_MANIFEST'; relative='race_manifest.json' }
)
$result = [ordered]@{
    schemaVersion = 1
    status = 'BLOCKED'
    raceDate = '2026-10-25'
    machineClass = $(if ($physicalPC2) { 'PC2' } else { 'NOT_PHYSICAL_PC2' })
    archivedPre2025Present = $false
    raceArchiveStatus = 'NOT_INSPECTED'
    raceArchiveRecords = 0
    raceArchiveResearchUseAllowed = $false
    jvlinkCom32Registered = $false
    jvlinkCom64Registered = $false
    jvlinkDualRegistration = $false
    localCandidateBundlePresent = $false
    missingInputRoles = @()
    modelComputed = $false
    publicationAuthorized = $false
    notePostAttempted = $false
    providerAccessAttempted = $false
    usageKeyRead = $false
    rawDataUploaded = $false
    private2025_2026HoldoutOpened = $false
    blockers = @('NO_VERIFIED_REAL_SUNDAY_FORECAST')
}

try {
    if (-not $physicalPC2) {
        $result['blockers'] = @('NOT_PHYSICAL_PC2')
    } else {
        $result['archivedPre2025Present'] = Test-Path -LiteralPath $archive -PathType Container
        # COM registration itself is not evidence of key validity, and the
        # registry's actual usage keys are NEVER read.
        foreach ($viewName in @('Registry32','Registry64')) {
            $view = [Microsoft.Win32.RegistryView]::$viewName
            $key = $null
            $base = $null
            try {
                $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
                    [Microsoft.Win32.RegistryHive]::LocalMachine, $view
                )
                $key = $base.OpenSubKey('Software\Classes\JVDTLab.JVLink\CLSID')
                $registered = ($null -ne $key)
                if ($viewName -eq 'Registry32') {
                    $result['jvlinkCom32Registered'] = $registered
                } else {
                    $result['jvlinkCom64Registered'] = $registered
                }
            } catch {
                # Registry rights may differ under a runner service account.
                # Absence of visibility is never proof of valid credentials.
                $result['blockers'] += 'COM_REGISTRATION_VISIBILITY_UNCERTAIN'
            } finally {
                if ($null -ne $key) { $key.Close() }
                if ($null -ne $base) { $base.Close() }
            }
        }
        $result['jvlinkDualRegistration'] = (
            $result['jvlinkCom32Registered'] -and
            $result['jvlinkCom64Registered']
        )

        $manifest = Join-Path $archive 'relocated_manifest_v2.json'
        if (Test-Path -LiteralPath $manifest -PathType Leaf) {
            try {
                $obj = Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 |
                  ConvertFrom-Json
                $race = @($obj.parts | Where-Object { $_.dataspec -eq 'RACE' })
                if ($race.Count -eq 1) {
                    $result['raceArchiveStatus'] = [string]$race[0].status
                    $result['raceArchiveRecords'] = [int]$race[0].records_written
                    $result['raceArchiveResearchUseAllowed'] = (
                        $race[0].research_use_allowed -eq $true
                    )
                } else {
                    $result['raceArchiveStatus'] = 'RACE_MANIFEST_AMBIGUOUS'
                }
            } catch {
                $result['raceArchiveStatus'] = 'RACE_MANIFEST_INVALID'
            }
        } else {
            $result['raceArchiveStatus'] = 'RACE_MANIFEST_MISSING'
        }

        $result['localCandidateBundlePresent'] = Test-Path -LiteralPath $bundle -PathType Container
        $missing = @(
            foreach ($item in $required) {
                $candidate = Join-Path $bundle $item.relative
                $isValid = Test-Path -LiteralPath $candidate -PathType Leaf
                if ($isValid) {
                    # Do not follow linked inputs into unexpected locations.
                    $isLink = [bool]((Get-Item -LiteralPath $candidate).Attributes -band
                                    [System.IO.FileAttributes]::ReparsePoint)
                    $isValid = -not $isLink
                }
                if (-not $isValid) { $item.label }
            }
        ) | Select-Object -Unique
        $result['missingInputRoles'] = @($missing)

        if ($result['raceArchiveStatus'] -ne 'success' -or
            $result['raceArchiveRecords'] -eq 0 -or
            -not $result['raceArchiveResearchUseAllowed']) {
            $result['blockers'] = @('HISTORICAL_RACE_ARCHIVE_UNAVAILABLE')
        } else {
            $result['blockers'] = @()
        }
        if (@($missing).Count -gt 0) {
            $result['blockers'] += 'LOCAL_SUNDAY_MODEL_INPUTS_INCOMPLETE'
        } else {
            # Actual 36-race runtime inference uses the separate approved
            # candidate bundle, never the pre-2025 raw archive itself.
            $venvPython = Join-Path (Get-Location).Path '.venv-jravan\Scripts\python.exe'
            $launcher = if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
                $venvPython
            } else { $null }
            if ($null -eq $launcher) {
                $py = Get-Command py -ErrorAction SilentlyContinue
                if ($null -ne $py) { $launcher = [string]$py.Source }
            }
            if ($null -eq $launcher) {
                $result['blockers'] += 'PYTHON_UNAVAILABLE'
            } else {
                $priorPythonPath = $env:PYTHONPATH
                $env:PYTHONPATH = Join-Path (Get-Location).Path 'src'
                $savedErrorPreference = $ErrorActionPreference
                $ErrorActionPreference = 'Continue'
                try {
                    $args = @()
                    if ($launcher -eq [string]$py.Source) { $args += '-3' }
                    $args += @(
                        'scripts/inspect_sunday_auto_post_readiness.py',
                        '--bundle-dir', $bundle
                    )
                    $lines = @(& $launcher @args 2>$null)
                    if ($lines.Count -gt 0) {
                        try {
                            $check = ($lines -join [Environment]::NewLine) | ConvertFrom-Json
                            if ($check.modelComputed -eq $true) {
                                $result['modelComputed'] = $true
                                $result['raceCount'] = [int]$check.raceCount
                                $result['modelOutputSha256'] = [string]$check.modelOutputSha256
                            }
                            $result['blockers'] += @($check.blockers)
                        } catch {
                            $result['blockers'] += 'LOCAL_PYTHON_READINESS_INVALID'
                        }
                    } else {
                        $result['blockers'] += 'LOCAL_PYTHON_READINESS_UNAVAILABLE'
                    }
                } catch {
                    $result['blockers'] += 'LOCAL_PYTHON_READINESS_FAILED'
                } finally {
                    $ErrorActionPreference = $savedErrorPreference
                    $env:PYTHONPATH = $priorPythonPath
                }
            }
        }
    }
} catch {
    $result['blockers'] += 'LOCAL_READ_ONLY_INSPECTION_FAILED'
} finally {
    $result['blockers'] = @($result['blockers'] | Where-Object { $_ } |
                          Select-Object -Unique)
    $parent = Split-Path -Parent $OutputPath
    if (-not [string]::IsNullOrWhiteSpace($parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    $result | ConvertTo-Json -Depth 7 |
      Set-Content -LiteralPath $OutputPath -Encoding UTF8
    Get-Content -LiteralPath $OutputPath -Encoding UTF8
}
