# NAR-approved training-source presence, filenames and file sizes ONLY.
# Never opens a ZIP, reads a race record, accesses JRA-VAN, trains, or publishes.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -cne 'DESKTOP-MVV1FD4') {
    throw 'NAR_METADATA_REQUIRES_PHYSICAL_PC2'
}
$roots = @(
    'D:\HorseRacingPredictions\nar-personal',
    'D:\Development\HorseRacingPredictions\nar-personal'
)
$required = @{}
foreach ($y in 2017..2022) {
    foreach ($m in 1..12) {
        $required[('{0}{1:D2}' -f $y,$m)] = $true
    }
}
$summaries = @()
foreach ($root in $roots) {
    $status = 'ABSENT'
    $matching = @{}
    $duplicates = 0
    $unexpectedZip = 0
    $otherYears = 0
    $reparse = 0
    $bytes = [long]0
    $count = 0
    if (Test-Path -LiteralPath $root -PathType Container) {
        $dir = Get-Item -LiteralPath $root -Force
        if (($dir.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            $status = 'REPARSE_POINT_BLOCKED'
        } else {
            $status = 'FILENAMES_ONLY'
            $files = @(Get-ChildItem -LiteralPath $root -File -Force -ErrorAction Stop)
            if ($files.Count -gt 1000) {
                $status = 'TOO_MANY_ENTRIES_BLOCKED'
            } else {
                foreach ($file in $files) {
                    if (($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                        $reparse++; continue
                    }
                    if ($file.Extension -ne '.zip') { continue }
                    if ($file.Name -cnotmatch '^(19|20)[0-9]{4}_[0-9]{8,13}_race\.zip$') {
                        $unexpectedZip++; continue
                    }
                    $month = $file.Name.Substring(0,6)
                    if (-not $required.ContainsKey($month)) { $otherYears++; continue }
                    if ($matching.ContainsKey($month)) { $duplicates++; continue }
                    $matching[$month] = $true
                    $count++
                    $bytes += [long]$file.Length
                }
            }
        }
    }
    $summaries += [pscustomobject]@{
        rootId = ($summaries.Count + 1)
        status = $status
        trainingMonthsObservedByName = $count
        trainingMonthsMissingByName = (72 - $count)
        duplicateTrainingMonthZips = $duplicates
        outOfPeriodMonthlyZips = $otherYears
        otherZipFilenames = $unexpectedZip
        reparseFiles = $reparse
        matchingZipBytesMetadata = $bytes
        zipContentsOpened = $false
    }
}
([ordered]@{
    schema = 'NAR.PC2.TrainingZIPNamesOnly.v1'
    pc2Verified = $true
    candidates = $summaries
    realNARRowsProcessed = 0
    finishedRacePayoutsRead = $false
    historicalHoldoutOpened = $false
    JraVanConnectionAttempted = $false
    sourceRecordsUploaded = $false
    trainingExecuted = $false
    roiComputed = $false
    publicationAuthorized = $false
    filesChanged = $false
}) | ConvertTo-Json -Depth 5
