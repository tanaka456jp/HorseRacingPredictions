param(
    [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"

function Get-ComView([Microsoft.Win32.RegistryView]$View) {
    $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
        [Microsoft.Win32.RegistryHive]::LocalMachine,
        $View
    )
    try {
        $prog = $base.OpenSubKey("Software\Classes\JVDTLab.JVLink\CLSID")
        if ($null -eq $prog) {
            return [ordered]@{
                registered = $false
                clsid = $null
                inproc_file = $null
                inproc_version = $null
            }
        }
        $clsid = [string]$prog.GetValue("")
        $prog.Close()
        if ([string]::IsNullOrWhiteSpace($clsid)) {
            return [ordered]@{
                registered = $true
                clsid = $null
                inproc_file = $null
                inproc_version = $null
            }
        }
        $inproc = $base.OpenSubKey(
            "Software\Classes\CLSID\$clsid\InprocServer32"
        )
        $dllPath = $null
        if ($null -ne $inproc) {
            $dllPath = [string]$inproc.GetValue("")
            $inproc.Close()
        }
        $version = $null
        $fileName = $null
        if (
            -not [string]::IsNullOrWhiteSpace($dllPath) -and
            (Test-Path -LiteralPath $dllPath -PathType Leaf)
        ) {
            $fileName = [System.IO.Path]::GetFileName($dllPath)
            $version = (
                Get-Item -LiteralPath $dllPath
            ).VersionInfo.FileVersion
        }
        elseif (-not [string]::IsNullOrWhiteSpace($dllPath)) {
            $fileName = [System.IO.Path]::GetFileName($dllPath)
        }
        return [ordered]@{
            registered = $true
            clsid = $clsid
            inproc_file = $fileName
            inproc_version = $version
        }
    }
    finally {
        $base.Close()
    }
}

function Get-DirectoryMetadata([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        return [ordered]@{
            exists = $false
            file_count = 0
            total_bytes = 0
            total_gib = 0.0
        }
    }
    $files = Get-ChildItem -LiteralPath $Path -File -Recurse -ErrorAction SilentlyContinue
    $bytes = [int64](($files | Measure-Object -Property Length -Sum).Sum)
    return [ordered]@{
        exists = $true
        file_count = [int]$files.Count
        total_bytes = $bytes
        total_gib = [Math]::Round($bytes / 1GB, 2)
    }
}

$pythonInfo = [ordered]@{
    configured = $false
    version = $null
    bits = $null
}
if (
    -not [string]::IsNullOrWhiteSpace($PythonPath) -and
    (Test-Path -LiteralPath $PythonPath -PathType Leaf)
) {
    $pyJson = & $PythonPath -c "import json,struct,sys; print(json.dumps({'version':sys.version.split()[0],'bits':struct.calcsize('P')*8}))"
    if ($LASTEXITCODE -eq 0) {
        $parsed = ($pyJson | Out-String) | ConvertFrom-Json
        $pythonInfo.configured = $true
        $pythonInfo.version = [string]$parsed.version
        $pythonInfo.bits = [int]$parsed.bits
    }
}

$view32 = Get-ComView -View ([Microsoft.Win32.RegistryView]::Registry32)
$view64 = Get-ComView -View ([Microsoft.Win32.RegistryView]::Registry64)
$dual = [bool]($view32.registered -and $view64.registered)

$providerCache = "C:\ProgramData\JRA-VAN\Data Lab\data"
$providerCacheMeta = Get-DirectoryMetadata -Path $providerCache

$dRoot = "D:\HorseRacingPredictions\JraVanFreeTrialArchive\pre2025"
$dMeta = Get-DirectoryMetadata -Path $dRoot

$cDrive = Get-PSDrive -Name C
$dDrive = Get-PSDrive -Name D -ErrorAction SilentlyContinue

$guidance = @()
if ($dual) {
    $guidance += (
        "Both 32-bit and 64-bit JVDTLab.JVLink COM registrations are present. " +
        "Official JRA-VAN guidance notes that mixed installations can matter for authentication."
    )
}
if (
    $pythonInfo.configured -and
    $pythonInfo.bits -eq 32 -and
    -not $view32.registered
) {
    $guidance += "32-bit Python is configured but 32-bit JV-Link COM is not registered."
}
if (
    $pythonInfo.configured -and
    $pythonInfo.bits -eq 64 -and
    -not $view64.registered
) {
    $guidance += "64-bit Python is configured but 64-bit JV-Link COM is not registered."
}
if ($providerCacheMeta.total_bytes -gt 2GB) {
    $guidance += (
        "The official JV-Link provider cache on C: is larger than 2 GiB. " +
        "Do not delete it automatically; review JV-Link Data Save settings before moving/cleaning it."
    )
}

$result = [ordered]@{
    status = "sanitized_environment_probe_complete"
    machine_name = $env:COMPUTERNAME
    os_64bit = [Environment]::Is64BitOperatingSystem
    powershell_process_64bit = [Environment]::Is64BitProcess
    python = $pythonInfo
    jvlink_registry32 = $view32
    jvlink_registry64 = $view64
    dual_jvlink_registration = $dual
    provider_cache = $providerCacheMeta
    d_archive = $dMeta
    c_free_gib = [Math]::Round([double]$cDrive.Free / 1GB, 2)
    d_free_gib = (
        if ($null -ne $dDrive) {
            [Math]::Round([double]$dDrive.Free / 1GB, 2)
        }
        else {
            $null
        }
    )
    provider_access_attempted = $false
    registry_secrets_read = $false
    usage_key_read = $false
    raw_records_read = $false
    protected_holdout = "2025-2026 untouched"
    guidance = $guidance
}

$result | ConvertTo-Json -Depth 7
