# NAR monthly training ZIP filename inventory on fixed PC2 D locations.
# Does NOT open or copy any file, enter protected holdouts, or fetch data.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
if($env:COMPUTERNAME -cne 'DESKTOP-MVV1FD4') {throw 'NAR_PC2_MACHINE_MISMATCH'}
$roots=@(
    'D:\Development\HorseRacingPredictions',
    'D:\HorseRacingPredictions',
    'D:\NAR',
    'D:\Development\NAR'
)
$blocked='^(?:\.git|\.venv|venv|__pycache__|node_modules|\.pytest_cache|jra-van|jravan|.*holdout.*|.*quarantine.*|.*credential.*|.*secret.*|.*token.*|.*runner.*)$'
$details=@()
$index=0
foreach($root in $roots) {
    $index++
    $exists=Test-Path -LiteralPath $root -PathType Container
    $status='ABSENT'
    $dirs=0
    $files=0
    $matching=0
    $training=@{}
    $outOfWindow=0
    $blockedDirs=0
    if($exists) {
        $entry=Get-Item -LiteralPath $root -Force
        if(($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            $status='REPARSE_ROOT_NOT_FOLLOWED'
        } else {
            $status='SCANNED_METADATA_ONLY'
            $queue=New-Object 'System.Collections.Generic.Queue[object]'
            $queue.Enqueue([pscustomobject]@{Path=$root;Level=0})
            while($queue.Count -gt 0) {
                $current=$queue.Dequeue()
                $dirs++
                if($dirs -gt 400) { $status='DIRECTORY_LIMIT_REACHED'; break }
                $entries=@(Get-ChildItem -LiteralPath $current.Path -Force -ErrorAction Stop)
                foreach($item in $entries) {
                    $files++
                    if($files -gt 20000) { $status='ENTRY_LIMIT_REACHED'; break }
                    if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                        continue
                    }
                    if($item.PSIsContainer) {
                        if($item.Name -match $blocked) {
                            $blockedDirs++
                            continue
                        }
                        if($current.Level -lt 2) {
                            $queue.Enqueue([pscustomobject]@{Path=$item.FullName;Level=($current.Level+1)})
                        }
                        continue
                    }
                    if($item.Name -match '^((?:19|20)[0-9]{4})_[0-9]{8,13}_race\.zip$') {
                        $matching++
                        $month=$Matches[1]
                        $year=[int]$month.Substring(0,4)
                        $mo=[int]$month.Substring(4,2)
                        if($year -ge 2017 -and $year -le 2022 -and $mo -ge 1 -and $mo -le 12) {
                            if(-not $training.ContainsKey($month)) {$training[$month]=0}
                            $training[$month]++
                        } else { $outOfWindow++ }
                    }
                }
                if($status -ne 'SCANNED_METADATA_ONLY') { break }
            }
        }
    }
    $duplicates=0
    foreach($month in $training.Keys) {
        if($training[$month] -gt 1) {$duplicates+=($training[$month]-1)}
    }
    $details += [pscustomobject]@{
        AllowlistRootId=$index
        Status=$status
        DirectoryEntriesVisited=$dirs
        DirectoryOrFileEntriesSeen=$files
        OfficialNamePatternZIPCount=$matching
        Training2017to2022MonthsByFilename=$training.Count
        TrainingMonthDuplicateZIPs=$duplicates
        OutOfStudyWindowPatternCount=$outOfWindow
        SkippedSensitiveOrLargeDirectories=$blockedDirs
        FileContentsRead=$false
    }
}
([pscustomobject]@{
    Schema='NAR.PC2.AllowlistedMetadataDiscovery.v1'
    MachineVerified=$true
    Roots=$details
    JraVanContentRead=$false
    HoldoutContentRead=$false
    ProviderCalls=$false
    FilesCopiedOrModified=$false
    SourceNamesLogged=$false
    DataUploaded=$false
    RealTrainingPerformed=$false
    PositiveExpectedValueDemonstrated=$false
    NotePublicationAuthorized=$false
}) | ConvertTo-Json -Depth 5
Write-Host 'PASS: bounded D-root metadata inventory; no data content read.'
