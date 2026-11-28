param([string]$OutputPath = "artifacts/jvlink_64_runtime_agent_metadata.json")
$ErrorActionPreference = "Stop"
# Read-only status: no JVInit/JVOpen/JVGets, no registry key values, no
# service changes, no subprocess debugging, no raw private process paths.
$pc2 = ($env:COMPUTERNAME -eq 'DESKTOP-MVV1FD4')
$report = [ordered]@{
  schemaVersion = 1
  status = "DIAGNOSIS_ONLY"
  physicalPC2Verified = $pc2
  recommendedResearchRuntime = "64bit"
  x86AuthorizationRetryAttempted = $false
  pythonLauncherAvailable = $false
  python64Available = $false
  pywin32Available64 = $false
  nativeAgentProcessesDetected = 0
  matchingWindowsServicesRunning = 0
  matchingWindowsServicesStopped = 0
  matchingServiceInspectionSucceeded = $false
  agentProcessInspectionSucceeded = $false
  blockers = @()
  usageKeyRead = $false
  accountModified = $false
  serviceMutated = $false
  providerAccessAttempted = $false
  nativeJVOpenCalled = $false
  rawRecordsRead = $false
  notePostAttempted = $false
  publicationAuthorized = $false
}
try {
  if (-not $pc2) {
    $report.blockers += "NOT_PHYSICAL_PC2"
  } else {
    # Report counts only: never emit PID, installation paths, commandline,
    # registry values or process environment.
    try {
      $procs = @(Get-Process -ErrorAction Stop | Where-Object {
        $_.ProcessName -match '(?i)^JV.?Link.*(Agent|Service)|^JVLinkAgent$'
      })
      $report.nativeAgentProcessesDetected = $procs.Count
      $report.agentProcessInspectionSucceeded = $true
    } catch {
      $report.blockers += "AGENT_PROCESS_VISIBILITY_UNCERTAIN"
    }
    try {
      $services = @(Get-CimInstance -ClassName Win32_Service -ErrorAction Stop |
        Where-Object { $_.Name -match '(?i)^JV.?Link|^JRA.?VAN' })
      $report.matchingWindowsServicesRunning = @($services | Where-Object {
        $_.State -eq 'Running'
      }).Count
      $report.matchingWindowsServicesStopped = @($services | Where-Object {
        $_.State -eq 'Stopped'
      }).Count
      $report.matchingServiceInspectionSucceeded = $true
    } catch {
      $report.blockers += "AGENT_SERVICE_VISIBILITY_UNCERTAIN"
    }
    # Query the same Python launcher the project scripts use without
    # importing COM or accessing any JV-Link state. Output fixed JSON only.
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($null -eq $py) {
      $report.blockers += "PYTHON_LAUNCHER_UNAVAILABLE"
    } else {
      $report.pythonLauncherAvailable = $true
      try {
        # Dedicated script avoids Windows PowerShell native -c quote stripping.
        # Do not print subprocess stderr, which can contain local paths.
        $script = Join-Path $PSScriptRoot "inspect_pc2_python64_metadata.py"
        if (-not (Test-Path -LiteralPath $script -PathType Leaf)) {
          throw "SAFE_PYTHON_METADATA_SCRIPT_MISSING"
        }
        $lines = @(& py -3 $script 2>$null)
        if ($LASTEXITCODE -ne 0 -or @($lines).Count -eq 0) {
          throw "SAFE_PYTHON_METADATA_PROBE_NO_RESULT"
        }
        $parsed = ($lines -join [Environment]::NewLine) | ConvertFrom-Json
        $report.python64Available = ($parsed.bits -eq 64)
        $report.pywin32Available64 = [bool]$parsed.pywin32
        if (-not $report.python64Available) {
          $report.blockers += "PYTHON_NOT_64BIT"
        }
        if (-not $report.pywin32Available64) {
          $report.blockers += "PYWIN32_NOT_INSTALLED_FOR_SELECTED_PYTHON"
        }
      } catch {
        $report.blockers += "PYTHON_ARCHITECTURE_INSPECTION_FAILED"
      }
    }
  }
} catch {
  $report.blockers += "READONLY_STATUS_INSPECTION_FAILED"
}
$folder = Split-Path -Parent $OutputPath
if ($folder) { New-Item -ItemType Directory -Force -Path $folder | Out-Null }
$report | ConvertTo-Json -Depth 6 |
  Set-Content -LiteralPath $OutputPath -Encoding UTF8
Get-Content -LiteralPath $OutputPath -Encoding UTF8
# GitHub's Windows PowerShell wrapper propagates stale native exit codes
# after a caught py-launch failure. JSON status (not process exit) is the
# authoritative diagnostic outcome; do not pretend Python was available.
$global:LASTEXITCODE = 0
