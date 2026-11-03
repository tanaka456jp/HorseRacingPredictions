# PC2 private review handoff for THREE filename-only historical-racing CSV hints.
# Reads file/directory entries ONLY; never opens original files or archives.
# Exact names and paths stay on PC2, OUTSIDE any Git worktree; nothing is uploaded.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
try {
    if ($env:COMPUTERNAME -cne 'DESKTOP-MVV1FD4') {
        throw 'PC2_UNEXPECTED_MACHINE'
    }
    if ($env:GITHUB_ACTIONS -eq 'true' -and (
        $env:GITHUB_REPOSITORY -cne 'tanaka456jp/HorseRacingPredictions' -or
        $env:GITHUB_REF_NAME -cne 'feature/weekly-odds-free-note-20261021'
    )) {
        throw 'PC2_UNEXPECTED_REPOSITORY_OR_BRANCH'
    }
    $root = 'D:\'
    $reviewRoot = 'D:\Development\HorseRacingPredictions-PrivateReview'
    if (-not (Test-Path -LiteralPath $root -PathType Container) -or
        -not (Test-Path -LiteralPath 'D:\Development' -PathType Container)) {
        throw 'PC2_EXPECTED_D_VOLUME_MISSING'
    }
    $blocked = '(?i)^(?:\$recycle\.bin|system volume information|recovery|\.git|\.venv|venv|node_modules|__pycache__|\.pytest_cache|actions-runner.*|.*holdout.*|.*quarantine.*|.*credential.*|.*secret.*|.*token.*|.*password.*|.*private.key.*|.*wallet.*|HorseRacingPredictions-PrivateReview)$'
    $hint = '(?i)(?:nar|keiba|地方競馬|競馬|race|horselist|racelist|payback)'
    $studyYear = '(?:2017|2018|2019|2020|2021|2022)'
    $candidates = New-Object 'System.Collections.Generic.List[object]'
    $queue = New-Object 'System.Collections.Generic.Queue[object]'
    $queue.Enqueue([pscustomobject]@{Path=$root;Depth=0})
    $dirs = 0
    $entries = 0
    $inaccessible = 0
    $maxDepth = 8
    while ($queue.Count -gt 0) {
        if ($dirs -ge 30000 -or $entries -ge 250000) {
            throw 'PC2_PRIVATE_REVIEW_SCAN_LIMIT'
        }
        $current = $queue.Dequeue()
        $dirs++
        try {
            $children = @(Get-ChildItem -LiteralPath $current.Path -Force -ErrorAction Stop)
        } catch {
            $inaccessible++
            continue
        }
        foreach ($child in $children) {
            $entries++
            if ($entries -ge 250000) { throw 'PC2_PRIVATE_REVIEW_SCAN_LIMIT' }
            if (($child.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                continue
            }
            if ($child.PSIsContainer) {
                if ($child.Name -match $blocked) { continue }
                if ($current.Depth -lt $maxDepth) {
                    $queue.Enqueue([pscustomobject]@{
                        Path=$child.FullName
                        Depth=($current.Depth+1)
                    })
                }
                continue
            }
            if ($child.Extension -ine '.csv' -or $child.Length -lt 500000 -or
                $child.Name -notmatch $hint -or
                $child.Name -notmatch $studyYear) {
                continue
            }
            # Local filename-only review. The category never grants data-use rights.
            $kind = 'UNVERIFIED_HISTORICAL_RACING_CSV_NAME'
            if ($child.FullName -match '(?i)(?:jra-?van|jravan|jvlink|jra[_-]|bldn)') {
                $kind = 'POSSIBLE_JRA_RESTRICTED_SOURCE_DO_NOT_OPEN'
            } elseif ($child.Name -match '(?i)(?:nar|地方競馬|horselist|racelist|payback)') {
                $kind = 'POSSIBLE_NAR_FILENAME_ONLY_NO_PROVENANCE'
            }
            $candidates.Add([pscustomobject]@{
                path = $child.FullName
                fileName = $child.Name
                sizeBytes = [long]$child.Length
                lastWriteUtc = $child.LastWriteTimeUtc.ToString('o')
                reviewCategory = $kind
                sourceRightsVerified = $false
                preEventAvailabilityVerified = $false
                approvedForTraining = $false
                fileContentRead = $false
            })
            if ($candidates.Count -gt 25) {
                throw 'PC2_PRIVATE_REVIEW_UNEXPECTED_CANDIDATE_VOLUME'
            }
        }
    }

    # Store exact names and paths locally in an isolated, access-controlled D folder,
    # outside the Git repository, outside the ZIP-only NAR training landing.
    $p = Get-Item -LiteralPath 'D:\Development' -Force
    if (($p.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'PC2_PRIVATE_REVIEW_PARENT_REPARSE_FORBIDDEN'
    }
    if (Test-Path -LiteralPath $reviewRoot) {
        $existing = Get-Item -LiteralPath $reviewRoot -Force
        if (-not $existing.PSIsContainer -or
            (($existing.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) {
            throw 'PC2_PRIVATE_REVIEW_UNSAFE_DESTINATION'
        }
    }
    $dir = [System.IO.Directory]::CreateDirectory($reviewRoot)
    $acl = New-Object System.Security.AccessControl.DirectorySecurity
    $acl.SetAccessRuleProtection($true, $false)
    $ids = @(
        [System.Security.Principal.WindowsIdentity]::GetCurrent().User,
        (New-Object System.Security.Principal.SecurityIdentifier('S-1-5-18')),
        (New-Object System.Security.Principal.SecurityIdentifier('S-1-5-32-544'))
    )
    foreach ($sid in $ids) {
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
            $sid, [System.Security.AccessControl.FileSystemRights]::FullControl,
            ([System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
             [System.Security.AccessControl.InheritanceFlags]::ObjectInherit),
            [System.Security.AccessControl.PropagationFlags]::None,
            [System.Security.AccessControl.AccessControlType]::Allow
        )
        $acl.AddAccessRule($rule)
    }
    $dir.SetAccessControl($acl)

    $runId = if ($env:GITHUB_RUN_ID -match '^\d{1,20}$') {
        $env:GITHUB_RUN_ID
    } else {
        [System.DateTime]::UtcNow.ToString('yyyyMMddHHmmss')
    }
    $file = Join-Path $reviewRoot ('candidate-metadata-only-' + $runId + '.json')
    if (Test-Path -LiteralPath $file) {
        throw 'PC2_PRIVATE_REVIEW_EXISTING_REPORT_NOT_OVERWRITTEN'
    }
    $sorted = @($candidates | Sort-Object -Property path)
    $report = [ordered]@{
        schema = 'HorseRacing.PC2.PrivateSourceHints.v1'
        status = 'REQUIRES_PRIVATE_HUMAN_ORIGIN_AND_RIGHTS_REVIEW'
        inputDataRead = $false
        providerCalled = $false
        archiveUnzipped = $false
        sourceDataUploaded = $false
        candidateCount = $sorted.Count
        visitedDirectoryCount = $dirs
        visitedEntryCount = $entries
        inaccessibleDirectoryCount = $inaccessible
        reviewOnly = $true
        sourceRightsVerified = $false
        allowedForModelTraining = $false
        candidates = $sorted
    }
    $text = $report | ConvertTo-Json -Depth 7
    [System.IO.File]::WriteAllText(
        $file, $text, (New-Object System.Text.UTF8Encoding($false))
    )
    # No filenames, source paths, source hashes or source data in Actions logs.
    $jraHints = @($sorted | Where-Object {
        $_.reviewCategory -eq 'POSSIBLE_JRA_RESTRICTED_SOURCE_DO_NOT_OPEN'
    }).Count
    $narHints = @($sorted | Where-Object {
        $_.reviewCategory -eq 'POSSIBLE_NAR_FILENAME_ONLY_NO_PROVENANCE'
    }).Count
    ([ordered]@{
        status = 'PC2_PRIVATE_REVIEW_REPORT_WRITTEN'
        candidateCount = $sorted.Count
        possibleNarFilenameCount = $narHints
        possibleJraRestrictedFilenameCount = $jraHints
        otherUnverifiedFilenameCount = $sorted.Count - $narHints - $jraHints
        directoriesVisited = $dirs
        entriesVisited = $entries
        incompleteBecauseInaccessible = ($inaccessible -gt 0)
        privateReportLocation = 'D:\Development\HorseRacingPredictions-PrivateReview'
        sourceNamesOrPathsLogged = $false
        sourceBytesRead = $false
        sourceBytesUploaded = $false
        trainingApproved = $false
        positiveEvDemonstrated = $false
    } | ConvertTo-Json -Depth 3)
} catch {
    # Never emit the exception: Windows errors may contain private paths.
    Write-Host 'PC2_PRIVATE_SOURCE_REVIEW_FAILED_SAFELY'
    exit 2
}
