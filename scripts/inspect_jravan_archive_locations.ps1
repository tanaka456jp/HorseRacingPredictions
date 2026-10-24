$ErrorActionPreference = "Stop"
if ($env:COMPUTERNAME -ne "DESKTOP-MVV1FD4") {
    throw "Storage discovery is restricted to physical PC2"
}

function Inspect-Root([string]$Label, [string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        return [ordered]@{ label=$Label; exists=$false }
    }
    $files = @(Get-ChildItem -LiteralPath $Path -File -Recurse -ErrorAction Stop)
    $size = [int64](($files | Measure-Object -Property Length -Sum).Sum)
    $names = @("latest_manifest.json", "latest_manifest_v2.json",
        "relocated_manifest_v2.json", "migration_receipt.json", "MOVED_TO_D.json",
        "race_raw.jsonl", "bldn_raw.jsonl", "pedigree_snapshot.csv",
        "migration_file_hashes.json")
    $evidence = [ordered]@{}
    foreach ($name in $names) {
        $evidence[$name] = Test-Path -LiteralPath (Join-Path $Path $name) -PathType Leaf
    }
    $primary = Join-Path $Path "latest_manifest.json"
    $v2 = Join-Path $Path "latest_manifest_v2.json"
    $primaryHash = $null
    $v2Hash = $null
    if (Test-Path -LiteralPath $primary -PathType Leaf) {
        $primaryHash = (Get-FileHash -LiteralPath $primary -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    if (Test-Path -LiteralPath $v2 -PathType Leaf) {
        $v2Hash = (Get-FileHash -LiteralPath $v2 -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    return [ordered]@{
        label=$Label; exists=$true; file_count=$files.Count
        total_bytes=$size; evidence=$evidence
        latest_manifest_sha256=$primaryHash
        latest_manifest_v2_sha256=$v2Hash
    }
}

$roots = @(
    (Inspect-Root "legacy_C_LOCALAPPDATA" (Join-Path $env:LOCALAPPDATA "HorseRacingPredictions\JraVanFreeTrialArchive\pre2025")),
    (Inspect-Root "previous_D_archive" "D:\HorseRacingPredictions\JraVanFreeTrialArchive\pre2025"),
    (Inspect-Root "approved_D_archive" "D:\JRA-VAN\Data Lab\archive\pre2025")
)
$result = [ordered]@{
    status="metadata_only_storage_location_discovery"
    machine="PC2"
    roots=$roots
    runner_manifest_artifact_present=(Test-Path -LiteralPath "artifacts\jravan_free_trial_archive_manifest.json" -PathType Leaf)
    provider_cache_root_exists=(Test-Path -LiteralPath "C:\ProgramData\JRA-VAN\Data Lab\data" -PathType Container)
    provider_access_attempted=$false
    file_contents_read=$false
    raw_archive_deleted=$false
    holdout_evaluated=$false
}
New-Item -ItemType Directory -Path "artifacts" -Force | Out-Null
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath "artifacts\jravan_storage_locations.json" -Encoding UTF8
$result | ConvertTo-Json -Depth 8
