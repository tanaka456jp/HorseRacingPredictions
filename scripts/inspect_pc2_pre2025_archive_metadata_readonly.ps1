param(
    [string]$OutputPath = "artifacts/pre2025_archive_file_inventory.json"
)
$ErrorActionPreference = 'Stop'
# Exact allowlisted roots, metadata only. No contents, CSV parsing,
# provider API, usage-key reads, filenames, archive exports or mutations.
$pc2 = ($env:COMPUTERNAME -eq "DESKTOP-MVV1FD4")
$roots = [ordered]@{
    jvArchivedPre2025 = "D:\JRA-VAN\Data Lab\archive\pre2025"
    approvedHistory = "D:\HorseRacingPredictions\approved-history"
}
$approvedExtensions = @(".csv", ".jsonl", ".zip", ".parquet", ".sqlite", ".db")
$report = [ordered]@{
    schemaVersion = 1
    status = "METADATA_ONLY_NOT_TRAINING_APPROVAL"
    physicalPC2Verified = $pc2
    roots = [ordered]@{}
    fileNamesReadOrUploaded = $false
    sourceBytesOpened = $false
    licenceOrKeyAccess = $false
    existingArchiveMutated = $false
    eligibleTrainingDatasetIndependentlyProven = $false
    rightsIndependentlyVerified = $false
    protectedHoldoutTrainingAllowed = $false
    publicationAuthorized = $false
    notePostAttempted = $false
}
foreach ($role in $roots.Keys) {
    $state = [ordered]@{
        exists = $false
        metadataScanComplete = $false
        eligibleExtensionFiles = 0
        totalCandidateBytes = [long]0
        csvFiles = 0
        jsonlFiles = 0
        zipFiles = 0
        parquetFiles = 0
        sqliteOrDbFiles = 0
        scopeLimitedToTwoLevels = $true
    }
    if ($pc2) {
        $path = $roots[$role]
        try {
            if (Test-Path -LiteralPath $path -PathType Container) {
                $dir = Get-Item -LiteralPath $path
                if (-not ($dir.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
                    $state.exists = $true
                    $folders = @($dir)
                    foreach ($child in (Get-ChildItem -LiteralPath $path -Directory -ErrorAction Stop)) {
                        if (-not ($child.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
                            $folders += $child
                        }
                    }
                    $count = 0
                    foreach ($folder in $folders) {
                        foreach ($file in (Get-ChildItem -LiteralPath $folder.FullName -File -ErrorAction Stop)) {
                            $count++
                            if ($count -gt 5000) {
                                throw "FILE_METADATA_SCOPE_LIMIT"
                            }
                            if ($file.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
                                continue
                            }
                            $ext = $file.Extension.ToLowerInvariant()
                            if ($ext -notin $approvedExtensions) { continue }
                            $state.eligibleExtensionFiles++
                            $state.totalCandidateBytes += [long]$file.Length
                            switch ($ext) {
                                ".csv" {$state.csvFiles++}
                                ".jsonl" {$state.jsonlFiles++}
                                ".zip" {$state.zipFiles++}
                                ".parquet" {$state.parquetFiles++}
                                default {$state.sqliteOrDbFiles++}
                            }
                        }
                    }
                    $state.metadataScanComplete = $true
                }
            }
        } catch {
            # Metadata only. Errors must not expose any local filenames.
            $state.metadataScanComplete = $false
        }
    }
    $report.roots[$role] = $state
}
$dir = Split-Path -Parent $OutputPath
if ($dir) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
$report | ConvertTo-Json -Depth 7 |
    Set-Content -LiteralPath $OutputPath -Encoding UTF8
Get-Content -LiteralPath $OutputPath -Encoding UTF8
$global:LASTEXITCODE = 0
