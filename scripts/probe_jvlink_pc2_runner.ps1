param(
    [string]$OutputPath = 'artifacts/jvlink_runner_bitness.json',
    [switch]$AuthenticationProbe
)

$ErrorActionPreference = 'Stop'
# Always use the existing runner, NEVER reinstall JV-Link or touch licence
# settings. The official GUI "JV-Link is normal" status does not prove
# JVOpen(-301) authorization. All child errors are reduced to fixed codes.
$pc2 = ($env:COMPUTERNAME -eq 'DESKTOP-MVV1FD4')
$results = [ordered]@{}
foreach ($bits in @(32,64)) {
    $results["bit$bits"] = [ordered]@{
        attempted = $false
        childProcessStarted = $false
        result = 'NOT_RUN'
        comCreated = $false
        jvInitReturnCode = $null
        jvOpenReturnCode = $null
        jvOpenAttempted = $false
    }
}
$root = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$root32 = Join-Path $env:SystemRoot 'SysWOW64\WindowsPowerShell\v1.0\powershell.exe'
$exeByBits = @{ 32 = $root32; 64 = $root }
$source = Join-Path $PSScriptRoot 'probe_jvlink_bitness_child.ps1'
if ($pc2) {
    foreach ($bits in @(32,64)) {
        $slot = $results["bit$bits"]
        $slot.attempted = $true
        $exe = $exeByBits[$bits]
        if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
            $slot.result = 'WINDOWS_POWERSHELL_ARCH_NOT_AVAILABLE'
            continue
        }
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
            $slot.result = 'CHILD_SCRIPT_NOT_FOUND'
            continue
        }
        $childOutput = Join-Path 'artifacts' ("jvlink_child_$bits.json")
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $exe
        $psi.Arguments = ('-NoProfile -NonInteractive -File "{0}" -ExpectedBits {1} -OutputPath "{2}"' -f
            $source, $bits, $childOutput)
        if ($AuthenticationProbe) { $psi.Arguments += ' -AuthenticationProbe' }
        $psi.WorkingDirectory = (Get-Location).Path
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $child = $null
        try {
            $child = [System.Diagnostics.Process]::Start($psi)
            $slot.childProcessStarted = $true
            if (-not $child.WaitForExit(45000)) {
                $slot.result = 'CHILD_PROBE_TIMEOUT'
                try { $child.Kill() } catch {}
                continue
            }
            # Do NOT log stdout/stderr: COM can return private messages.
            if (-not (Test-Path -LiteralPath $childOutput -PathType Leaf)) {
                $slot.result = 'CHILD_SANITIZED_JSON_MISSING'
                continue
            }
            $payload = Get-Content -LiteralPath $childOutput -Raw -Encoding UTF8 |
              ConvertFrom-Json
            if ($payload.physicalPC2 -ne $true -or
                $payload.actualProcessBits -ne $bits -or
                $payload.usageKeyRead -ne $false -or
                $payload.rawRecordsRead -ne $false -or
                $payload.licenceSettingsModified -ne $false) {
                $slot.result = 'CHILD_SECURITY_INVARIANT_FAILED'
                continue
            }
            $slot.result = [string]$payload.diagnosticCode
            $slot.comCreated = [bool]$payload.comCreated
            $slot.jvInitReturnCode = $payload.jvInitReturnCode
            $slot.jvOpenReturnCode = $payload.jvOpenReturnCode
            $slot.jvOpenAttempted = [bool]$payload.jvOpenAttempted
            $slot.jvCloseSucceeded = [bool]$payload.jvCloseSucceeded
        } catch {
            $slot.result = 'CHILD_PROCESS_EXECUTION_FAILED'
        } finally {
            if ($null -ne $child) { $child.Dispose() }
        }
    }
}
$report = [ordered]@{
    schemaVersion = 1
    status = 'DIAGNOSIS_ONLY'
    physicalPC2Verified = $pc2
    guiStatusUserReportedNormalBothBits = $true
    authenticationProbeRequested = [bool]$AuthenticationProbe
    bitness = $results
    usageKeyRead = $false
    licenceSettingsModified = $false
    providerRawRecordsRead = $false
    notePostAttempted = $false
    trainerInvoked = $false
    publicationAuthorized = $false
    diagnosisAloneProvesKeyValidity = $false
}
$dir = Split-Path -Parent $OutputPath
if ($dir) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
$report | ConvertTo-Json -Depth 8 |
  Set-Content -LiteralPath $OutputPath -Encoding UTF8
Get-Content -LiteralPath $OutputPath -Encoding UTF8
