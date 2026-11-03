# Non-invasive PC2 filename-only discovery of potential historical NAR sources.
# Never open archives, read source bytes, follow junctions, transfer records or write files.
# Counts only; a filename is NOT proof of provenance, rights or pre-event availability.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -cne 'DESKTOP-MVV1FD4') {
    throw 'NAR_PC2_PHYSICAL_MACHINE_REQUIRED'
}
if ($env:GITHUB_ACTIONS -eq 'true' -and (
    $env:GITHUB_REPOSITORY -cne 'tanaka456jp/HorseRacingPredictions' -or
    $env:GITHUB_REF_NAME -cne 'feature/weekly-odds-free-note-20261021'
)) {
    throw 'NAR_PC2_EXPECTED_ACTIONS_BRANCH_REQUIRED'
}

# One whole D volume plus the runner user's three conventional download locations.
# No scanning of C:\, other user profiles, Windows, Program Files or network drives.
$roots = @(
    'D:\',
    'C:\Users\chi1v\Downloads',
    'C:\Users\chi1v\Documents',
    'C:\Users\chi1v\Desktop'
)
$blocked = '(?i)^(?:\$recycle\.bin|system volume information|recovery|\.git|\.venv|venv|node_modules|__pycache__|\.pytest_cache|actions-runner.*|.*holdout.*|.*quarantine.*|.*credential.*|.*secret.*|.*token.*|.*password.*|.*private.key.*|.*wallet.*)$'
$official = '^(?<month>(?:19|20)\d{4})_\d{8,13}_race\.zip$'
$hint = '(?i)(?:nar|keiba|地方競馬|競馬|race|horselist|racelist|payback)'
$studyYear = '(?:2017|2018|2019|2020|2021|2022)'
$maxDirs = 30000
$maxEntries = 250000
$maxDepth = 8
$summaries = @()

for ($rootIndex = 0; $rootIndex -lt $roots.Count; $rootIndex++) {
    $root = $roots[$rootIndex]
    $status = 'ABSENT'
    $visited = 0
    $entries = 0
    $denied = 0
    $skippedReparse = 0
    $skippedProtected = 0
    $officialCount = 0
    $hintCount = 0
    $largeHintCount = 0
    $zipHintCount = 0
    $months = @{}
    try {
        if (Test-Path -LiteralPath $root -PathType Container) {
            $rootItem = Get-Item -LiteralPath $root -Force -ErrorAction Stop
            if (($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                $status = 'REPARSE_ROOT_NOT_FOLLOWED'
            } else {
                $status = 'COMPLETE_WITHIN_DEPTH_LIMIT'
                $queue = New-Object 'System.Collections.Generic.Queue[object]'
                $queue.Enqueue([pscustomobject]@{Path=$root;Depth=0})
                while ($queue.Count -gt 0) {
                    if ($visited -ge $maxDirs -or $entries -ge $maxEntries) {
                        $status = 'BOUNDED_CAP_REACHED_INCOMPLETE'
                        break
                    }
                    $current = $queue.Dequeue()
                    $visited++
                    try {
                        $children = @(Get-ChildItem -LiteralPath $current.Path -Force -ErrorAction Stop)
                    } catch {
                        # Never print exception: it can contain an unapproved local path.
                        $denied++
                        $status = 'PARTIAL_INACCESSIBLE_DIRECTORY'
                        continue
                    }
                    foreach ($child in $children) {
                        $entries++
                        if ($entries -ge $maxEntries) {
                            $status = 'BOUNDED_CAP_REACHED_INCOMPLETE'
                            break
                        }
                        if (($child.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                            $skippedReparse++
                            continue
                        }
                        if ($child.PSIsContainer) {
                            if ($child.Name -match $blocked) {
                                $skippedProtected++
                            } elseif ($current.Depth -lt $maxDepth) {
                                $queue.Enqueue([pscustomobject]@{
                                    Path=$child.FullName;Depth=($current.Depth+1)
                                })
                            }
                            continue
                        }
                        # We inspect only the filename and file-system entry metadata.
                        if ($child.Name -match $official) {
                            $month = $Matches['month']
                            $year = [int]$month.Substring(0,4)
                            $monthNumber = [int]$month.Substring(4,2)
                            if ($year -ge 2017 -and $year -le 2022 -and
                                $monthNumber -ge 1 -and $monthNumber -le 12) {
                                $officialCount++
                                if (-not $months.ContainsKey($month)) { $months[$month] = 0 }
                                $months[$month]++
                            }
                        } elseif ($child.Extension -match '^\.(?:zip|csv|jsonl|parquet|feather)$' -and
                                  $child.Name -match $hint -and
                                  $child.Name -match $studyYear) {
                            # Hints, not official archives; never emit file names.
                            $hintCount++
                            if ($child.Length -ge 500000) { $largeHintCount++ }
                            if ($child.Extension -eq '.zip') { $zipHintCount++ }
                        }
                    }
                    if ($status -eq 'BOUNDED_CAP_REACHED_INCOMPLETE') { break }
                }
            }
        }
    } catch {
        $status = 'ROOT_METADATA_ERROR_INCOMPLETE'
    }
    $duplicates = 0
    foreach ($key in $months.Keys) {
        if ($months[$key] -gt 1) { $duplicates += ($months[$key] - 1) }
    }
    $summaries += [pscustomobject]@{
        RootId = $rootIndex + 1
        Status = $status
        DirectoriesVisited = $visited
        EntriesVisited = $entries
        InaccessibleDirectories = $denied
        SkippedReparseEntries = $skippedReparse
        SkippedSensitiveDirectories = $skippedProtected
        Official2017to2022ZIPsByName = $officialCount
        DistinctTrainingMonthsByName = $months.Count
        DuplicateZIPsByMonth = $duplicates
        OtherCandidateNameHints = $hintCount
        LargeOtherCandidateHintsAtLeast500KB = $largeHintCount
        ZIPOtherCandidateHints = $zipHintCount
    }
}
([ordered]@{
    Schema = 'NAR.PC2.BoundedDrivewideSourceHints.v1'
    VerifiedPhysicalPC2 = $true
    SourceNamesOrPathsLogged = $false
    FileContentRead = $false
    ZIPDecompressed = $false
    ReparsePointsFollowed = $false
    SourceRecordsUploaded = $false
    ArchivesModified = $false
    ProviderRequestAttempted = $false
    TrainingExecuted = $false
    ROIComputed = $false
    PositiveEVDemonstrated = $false
    NotePublicationAuthorized = $false
    PerRoot = $summaries
}) | ConvertTo-Json -Depth 6
