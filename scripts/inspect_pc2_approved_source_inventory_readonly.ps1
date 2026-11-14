param(
    [string]$OutputPath = 'artifacts/approved_source_inventory.json'
)

$ErrorActionPreference = 'Stop'
# Explicit allowlist only. No recursive scan, provider API, licence key,
# CSV read, model load, account change, archive mutation or upload of bytes.
$pc2 = ($env:COMPUTERNAME -eq 'DESKTOP-MVV1FD4')

function Test-ApprovedRegularFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    $item = Get-Item -LiteralPath $Path -ErrorAction Stop
    return -not [bool]($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)
}

$paths = [ordered]@{
    approvedPre2025TrainingCsv =
      'D:\HorseRacingPredictions\approved-history\pre2025.csv'
    approvedLatestHistoryCsv =
      'D:\HorseRacingPredictions\approved-sunday-20261101\race_history.csv'
    approvedNovember1EntriesCsv =
      'D:\HorseRacingPredictions\approved-sunday-20261101\sunday_entries.csv'
    approvedNovember1RaceManifest =
      'D:\HorseRacingPredictions\approved-sunday-20261101\race_manifest.json'
    dualResearchManifest =
      'D:\HorseRacingPredictions\research-candidates\dual-20261025\candidate_manifest.json'
    dualReadyCandidateManifest =
      'D:\HorseRacingPredictions\approved-sunday-20261101\model\candidate_manifest.json'
    dualReadyWinnerBinary =
      'D:\HorseRacingPredictions\approved-sunday-20261101\model\win.cbm'
    dualReadyOutsiderBinary =
      'D:\HorseRacingPredictions\approved-sunday-20261101\model\outsider.cbm'
}
$present = [ordered]@{}
foreach ($role in $paths.Keys) { $present[$role] = $false }
$blockers = @()
if (-not $pc2) {
    $blockers += 'PHYSICAL_PC2_NOT_CONFIRMED'
} else {
    foreach ($role in $paths.Keys) {
        try {
            $present[$role] = [bool](Test-ApprovedRegularFile -Path $paths[$role])
        } catch {
            $blockers += 'FILE_METADATA_VISIBILITY_UNCERTAIN'
        }
    }
    if (-not $present['approvedPre2025TrainingCsv']) {
        $blockers += 'APPROVED_PRE2025_TRAINING_CSV_MISSING'
    }
    if (-not $present['approvedLatestHistoryCsv']) {
        $blockers += 'NEXT_SUNDAY_RECENT_HISTORY_MISSING'
    }
    if (-not $present['approvedNovember1EntriesCsv']) {
        $blockers += 'NEXT_SUNDAY_ENTRIES_MISSING'
    }
    if (-not $present['approvedNovember1RaceManifest']) {
        $blockers += 'NEXT_SUNDAY_RACE_MANIFEST_MISSING'
    }
    if (-not ($present['dualReadyCandidateManifest'] -and
              $present['dualReadyWinnerBinary'] -and
              $present['dualReadyOutsiderBinary'])) {
        $blockers += 'NEXT_SUNDAY_DUAL_MODEL_FILES_MISSING'
    }
}
$out = [ordered]@{
    schemaVersion = 1
    status = 'BLOCKED'
    verifiedPhysicalPC2 = $pc2
    approvedInputPathsOnly = $true
    filePresence = $present
    blockers = @($blockers | Select-Object -Unique)
    modelComputed = $false
    publicationAuthorized = $false
    notePostAttempted = $false
    providerAccessAttempted = $false
    usageKeyRead = $false
    protectedHoldoutOpened = $false
    rawDataUploaded = $false
}
$parent = Split-Path -Parent $OutputPath
if (-not [string]::IsNullOrWhiteSpace($parent)) {
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
}
$out | ConvertTo-Json -Depth 6 |
  Set-Content -LiteralPath $OutputPath -Encoding UTF8
Get-Content -LiteralPath $OutputPath -Encoding UTF8
