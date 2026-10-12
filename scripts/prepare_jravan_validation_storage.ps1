param(
    [string]$Path = "D:\JRA-VAN\Data Lab",
    [double]$MinimumFreeGiB = 20
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath "D:\" -PathType Container)) {
    throw "D drive is not available."
}

$d = Get-PSDrive -Name D
$freeGiB = [Math]::Round([double]$d.Free / 1GB, 2)
if ($freeGiB -lt $MinimumFreeGiB) {
    throw (
        "D drive free space is below the safety minimum. " +
        "free_gib=$freeGiB minimum_gib=$MinimumFreeGiB"
    )
}

if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
}

$resolved = (Resolve-Path -LiteralPath $Path).Path
if (-not $resolved.StartsWith(
    "D:\",
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw "Prepared path is not on D drive."
}

$result = [ordered]@{
    status = "ready"
    prepared_path = $resolved
    d_free_gib = $freeGiB
    minimum_free_gib = $MinimumFreeGiB
    jvlink_settings_changed = $false
    provider_cache_moved = $false
    provider_access_attempted = $false
    usage_key_read = $false
    paid_action_authorized = $false
    protected_holdout = "2025-2026 untouched"
}

$result | ConvertTo-Json -Depth 5
