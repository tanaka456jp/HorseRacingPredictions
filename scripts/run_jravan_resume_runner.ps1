param(
    [string]$ParsedHistoryPath = "",
    [string]$BaseHistoryPath = "",
    [string]$ValidationOutput = "artifacts/jravan_runner_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

function Test-UsableFile {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $false
    }
    try {
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
            return $false
        }
        return (Get-Item -LiteralPath $Path).Length -gt 0
    }
    catch {
        return $false
    }
}

function Resolve-ParsedHistorySource {
    param([string]$ExplicitPath)

    if (Test-UsableFile $ExplicitPath) {
        return @{
            Path = (Resolve-Path -LiteralPath $ExplicitPath).Path
            Strategy = "workflow_input"
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($ExplicitPath)) {
        throw "The supplied parsed_history_path does not exist or is empty."
    }

    if (Test-UsableFile $env:HRP_PARSED_HISTORY_PATH) {
        return @{
            Path = (Resolve-Path -LiteralPath $env:HRP_PARSED_HISTORY_PATH).Path
            Strategy = "runner_environment"
        }
    }

    $workspaceCandidate = Join-Path $ProjectRoot "data\jravan\full\parsed_history.csv"
    if (Test-UsableFile $workspaceCandidate) {
        return @{
            Path = (Resolve-Path -LiteralPath $workspaceCandidate).Path
            Strategy = "runner_workspace"
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($env:HRP_PROJECT_ROOT)) {
        $candidate = Join-Path $env:HRP_PROJECT_ROOT "data\jravan\full\parsed_history.csv"
        if (Test-UsableFile $candidate) {
            return @{
                Path = (Resolve-Path -LiteralPath $candidate).Path
                Strategy = "project_root_environment"
            }
        }
    }

    $priorityCandidates = @()
    if (-not [string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
        $priorityCandidates += (Join-Path $env:USERPROFILE "Development\HorseRacingPredictions\data\jravan\full\parsed_history.csv")
        $priorityCandidates += (Join-Path $env:USERPROFILE "Documents\Development\HorseRacingPredictions\data\jravan\full\parsed_history.csv")
    }
    $priorityCandidates += "C:\Development\HorseRacingPredictions\data\jravan\full\parsed_history.csv"

    foreach ($candidate in $priorityCandidates) {
        if (Test-UsableFile $candidate) {
            return @{
                Path = (Resolve-Path -LiteralPath $candidate).Path
                Strategy = "standard_location"
            }
        }
    }

    $discovered = @()
    if (Test-Path "C:\Users") {
        foreach ($profile in Get-ChildItem "C:\Users" -Directory -ErrorAction SilentlyContinue) {
            foreach ($relative in @(
                "Development\HorseRacingPredictions\data\jravan\full\parsed_history.csv",
                "Documents\Development\HorseRacingPredictions\data\jravan\full\parsed_history.csv"
            )) {
                $candidate = Join-Path $profile.FullName $relative
                if (Test-UsableFile $candidate) {
                    $discovered += (Resolve-Path -LiteralPath $candidate).Path
                }
            }
        }
    }

    $discovered = @($discovered | Sort-Object -Unique)
    if ($discovered.Count -eq 1) {
        return @{
            Path = $discovered[0]
            Strategy = "auto_discovery"
        }
    }
    if ($discovered.Count -gt 1) {
        throw "Multiple parsed_history.csv candidates were found. Re-run the workflow with parsed_history_path explicitly set."
    }

    throw "No existing parsed_history.csv was found on this runner. Run the job on the Windows PC that holds the completed JRA-VAN acquisition, or supply parsed_history_path."
}

Write-Host "=== HorseRacingPredictions self-hosted JRA-VAN Resume ==="

$source = Resolve-ParsedHistorySource -ExplicitPath $ParsedHistoryPath
$sourcePath = $source.Path
$sourceStrategy = $source.Strategy

$destination = Join-Path $ProjectRoot "data\jravan\full\parsed_history.csv"
$destinationDir = Split-Path -Parent $destination
New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null

$sourceFull = [System.IO.Path]::GetFullPath($sourcePath)
$destinationFull = [System.IO.Path]::GetFullPath($destination)
if (-not $sourceFull.Equals($destinationFull, [System.StringComparison]::OrdinalIgnoreCase)) {
    Copy-Item -LiteralPath $sourcePath -Destination $destination -Force
}

if (-not (Test-UsableFile $destination)) {
    throw "parsed_history.csv was not available in the runner workspace after staging."
}

$parsedInfo = Get-Item -LiteralPath $destination
$parsedHash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()

$bootstrap = Join-Path $ProjectRoot "scripts\bootstrap_jravan_trial.ps1"
$bootstrapArgs = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $bootstrap,
    "-Resume"
)
if (-not [string]::IsNullOrWhiteSpace($BaseHistoryPath)) {
    if (-not (Test-UsableFile $BaseHistoryPath)) {
        throw "The supplied base_history_path does not exist or is empty."
    }
    $bootstrapArgs += @("-BaseHistory", $BaseHistoryPath)
}

& powershell.exe @bootstrapArgs
if ($LASTEXITCODE -ne 0) {
    throw "JRA-VAN resume bootstrap failed with exit code $LASTEXITCODE."
}

$currentHistory = Join-Path $ProjectRoot "data\jravan\full\current_history.csv"
$pipelineSummary = Join-Path $ProjectRoot "artifacts\jravan_full\pipeline_summary.json"

if (-not (Test-UsableFile $currentHistory)) {
    throw "Resume completed without a non-empty current_history.csv."
}
if (-not (Test-UsableFile $pipelineSummary)) {
    throw "Resume completed without pipeline_summary.json."
}

$summary = Get-Content -LiteralPath $pipelineSummary -Raw | ConvertFrom-Json
if ($summary.acquisition_mode -ne "resume_existing_parsed") {
    throw "Unexpected acquisition_mode in pipeline summary: $($summary.acquisition_mode)"
}

$currentInfo = Get-Item -LiteralPath $currentHistory
$commit = (& git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "git rev-parse HEAD failed."
}

$validationPath = Join-Path $ProjectRoot $ValidationOutput
$validationDir = Split-Path -Parent $validationPath
if (-not [string]::IsNullOrWhiteSpace($validationDir)) {
    New-Item -ItemType Directory -Force -Path $validationDir | Out-Null
}

$validation = [ordered]@{
    validated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    commit_sha = $commit
    runner_os = $env:RUNNER_OS
    runner_arch = $env:RUNNER_ARCH
    parsed_history_source_strategy = $sourceStrategy
    parsed_history_size_bytes = [int64]$parsedInfo.Length
    parsed_history_sha256 = $parsedHash
    current_history_size_bytes = [int64]$currentInfo.Length
    status = $summary.status
    acquisition_mode = $summary.acquisition_mode
    history_gap_days = $summary.history_gap_days
    base_end = $summary.base_end
    parsed_rows = $summary.parsed_rows
    parsed_races = $summary.parsed_races
    supplemental_rows_after_base = $summary.supplemental_rows_after_base
    winner_conflict_excluded_races = $summary.winner_conflict_excluded_races
    winner_conflict_excluded_rows = $summary.winner_conflict_excluded_rows
    zero_winner_races = $summary.zero_winner_races
    multiple_winner_races = $summary.multiple_winner_races
    supplemental_start = $summary.supplemental_start
    supplemental_end = $summary.supplemental_end
    current_history_rows = $summary.current_history_rows
    current_history_end = $summary.current_history_end
}

$validation | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $validationPath -Encoding UTF8

if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_STEP_SUMMARY)) {
    @(
        "### JRA-VAN Resume validation",
        "",
        "- status: $($summary.status)",
        "- acquisition_mode: $($summary.acquisition_mode)",
        "- parsed_rows: $($summary.parsed_rows)",
        "- current_history_rows: $($summary.current_history_rows)",
        "- current_history_end: $($summary.current_history_end)",
        "- winner_conflict_excluded_races: $($summary.winner_conflict_excluded_races)",
        "- source_strategy: $sourceStrategy",
        "- commit: $commit"
    ) | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding UTF8
}

Write-Host "JRA-VAN self-hosted resume validation PASS."
Write-Host "status=$($summary.status)"
Write-Host "parsed_rows=$($summary.parsed_rows)"
Write-Host "current_history_rows=$($summary.current_history_rows)"
Write-Host "current_history_end=$($summary.current_history_end)"
