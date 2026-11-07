param(
    [ValidateSet(32,64)][int]$ExpectedBits = 64,
    [string]$OutputPath = 'artifacts/jvlink_child_probe.json',
    [switch]$AuthenticationProbe
)

$ErrorActionPreference = 'Stop'
# PC2-only child process. No registry reads for keys, no UI, no elevated
# rights, no JVGets, no history export, no payment, no cache deletion.
# User-provided screenshots show both JV-Link settings report NORMAL.
$actualBits = [IntPtr]::Size * 8
$physicalPC2 = ($env:COMPUTERNAME -eq 'DESKTOP-MVV1FD4')
$report = [ordered]@{
    schemaVersion = 1
    status = 'BLOCKED'
    physicalPC2 = $physicalPC2
    expectedProcessBits = $ExpectedBits
    actualProcessBits = $actualBits
    comCreated = $false
    jvInitReturnCode = $null
    jvStatusBeforeOpen = $null
    authenticationProbeRequested = [bool]$AuthenticationProbe
    jvOpenAttempted = $false
    jvOpenReturnCode = $null
    jvCloseAttempted = $false
    jvCloseSucceeded = $false
    diagnosticCode = 'NOT_STARTED'
    usageKeyRead = $false
    licenceSettingsModified = $false
    rawRecordsRead = $false
    notePostAttempted = $false
    protectedHoldoutOpened = $false
    archivedDDataChanged = $false
}
$jv = $null
try {
    if (-not $physicalPC2) { throw 'PC2_NOT_CONFIRMED' }
    if ($actualBits -ne $ExpectedBits) { throw 'PROCESS_BITNESS_MISMATCH' }
    $report.diagnosticCode = 'COM_DISPATCH_FAILED'
    try {
        $jv = New-Object -ComObject 'JVDTLab.JVLink'
    } catch {
        # HRESULT only; COM exception messages can include user environment.
        $report.diagnosticCode = 'COM_CREATE_FAILED'
        $report['comHResult'] = [int]$_.Exception.HResult
        throw 'COM_CREATE_FAILED'
    }
    if ($null -eq $jv) { throw 'COM_NULL' }
    $report.comCreated = $true
    $report.diagnosticCode = 'JVINIT_ERROR'
    $init = $jv.JVInit('UNKNOWN')
    $report.jvInitReturnCode = [int]$init
    if ([int]$init -ne 0) {
        $report.diagnosticCode = 'JVINIT_RETURNED_NONZERO'
    } else {
        # JVStatus=-203 before opening is ordinary, not proof of a failure.
        try {
            $report.jvStatusBeforeOpen = [int]$jv.JVStatus()
        } catch {
            $report.diagnosticCode = 'JVSTATUS_UNAVAILABLE'
        }
        if (-not $AuthenticationProbe) {
            $report.status = 'INITIALIZATION_ONLY'
            $report.diagnosticCode = 'JVINIT_SUCCEEDED_OPEN_NOT_ATTEMPTED'
        } else {
            $report.diagnosticCode = 'JVOPEN_CALL_FAILED'
            # Current-week RACE (option 2) only; never historical setup (3,4).
            # The provider may populate normal official C cache during this
            # authorized auth test. Never open or transmit race records.
            $report.jvOpenAttempted = $true
            try {
                $response = $jv.JVOpen('RACE', '00000000000000', 2, 0, 0, '')
                if ($response -is [System.Array]) {
                    $rc = [int]$response[0]
                } else {
                    $rc = [int]$response
                }
                $report.jvOpenReturnCode = $rc
                $report.status = if ($rc -ge 0) { 'JVOPEN_SUCCESS' } else { 'JVOPEN_REFUSED' }
                $report.diagnosticCode = if ($rc -eq -301) {
                    'JVOPEN_AUTH_MINUS_301'
                } elseif ($rc -eq -302) {
                    'JVOPEN_TRIAL_OR_SERVICE_EXPIRED'
                } elseif ($rc -eq -303) {
                    'JVOPEN_USAGE_KEY_UNAVAILABLE'
                } elseif ($rc -ge 0) {
                    'JVOPEN_ACCEPTED_CURRENT_WEEK'
                } else { 'JVOPEN_OTHER_RETURN_CODE' }
            } catch {
                $report.diagnosticCode = 'JVOPEN_COM_EXCEPTION'
                $report['jvOpenHResult'] = [int]$_.Exception.HResult
            } finally {
                # Close on any JVOpen attempt, even when COM returns negative.
                $report.jvCloseAttempted = $true
                try {
                    $null = $jv.JVClose()
                    $report.jvCloseSucceeded = $true
                } catch {
                    $report.jvCloseSucceeded = $false
                }
            }
        }
    }
} catch {
    if ($report.diagnosticCode -eq 'NOT_STARTED') {
        $report.diagnosticCode = 'PHYSICAL_PC_OR_BITNESS_MISMATCH'
    }
} finally {
    $jv = $null
    $parent = Split-Path -Parent $OutputPath
    if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    $report | ConvertTo-Json -Depth 5 |
      Set-Content -LiteralPath $OutputPath -Encoding UTF8
    # Strictly the sanitized boolean/return-code report; never exception text.
    Get-Content -LiteralPath $OutputPath
}
