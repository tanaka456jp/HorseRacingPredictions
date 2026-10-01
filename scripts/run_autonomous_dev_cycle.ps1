param(
    [int]$Cycle = 1,
    [string]$ExpectedComputerName = "DESKTOP-MVV1FD4",
    [string]$Repository = "tanaka456jp/HorseRacingPredictions",
    [string]$DevRoot = "",
    [int]$CheckWaitMinutes = 20
)

$ErrorActionPreference = "Stop"

if ($env:COMPUTERNAME -ne $ExpectedComputerName) {
    throw "Refusing autonomous development on $($env:COMPUTERNAME); expected $ExpectedComputerName."
}

$ControlRoot = Join-Path $env:LOCALAPPDATA "HorseRacingPredictionsAutonomousDev"
if ([string]::IsNullOrWhiteSpace($DevRoot)) {
    $DevRoot = Join-Path $ControlRoot "repo"
}
$LogDir = Join-Path $ControlRoot "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$CodexPath = Join-Path $env:LOCALAPPDATA "Programs\OpenAI\Codex\codex.exe"
if (-not (Test-Path -LiteralPath $CodexPath -PathType Leaf)) {
    throw "CODEX_NOT_INSTALLED: $CodexPath"
}

Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue

& $CodexPath login status *> $null
if ($LASTEXITCODE -ne 0) {
    throw "CODEX_NOT_AUTHENTICATED: run codex once on PC1 and sign in with ChatGPT."
}
& gh auth status --hostname github.com *> $null
if ($LASTEXITCODE -ne 0) {
    throw "GH_NOT_AUTHENTICATED"
}
& gh auth setup-git *> $null
if ($LASTEXITCODE -ne 0) {
    throw "GH_GIT_SETUP_FAILED"
}

if (-not (Test-Path -LiteralPath (Join-Path $DevRoot ".git"))) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $DevRoot) | Out-Null
    & gh repo clone $Repository $DevRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to create dedicated autonomous-development clone."
    }
}

Set-Location $DevRoot
& git remote set-url origin "https://github.com/$Repository.git"
& git reset --hard
& git clean -fd
& git fetch origin main --prune
& git checkout -B main origin/main

function Invoke-Codex {
    param(
        [string]$Prompt,
        [string]$Label
    )

    $stamp = [DateTimeOffset]::UtcNow.ToString("yyyyMMddTHHmmssZ")
    $logPath = Join-Path $LogDir "$stamp-$Label.txt"
    Write-Host "Invoking Codex: $Label"
    $output = & $CodexPath exec --full-auto $Prompt 2>&1
    $exitCode = [int]$LASTEXITCODE
    $output | Set-Content -LiteralPath $logPath -Encoding UTF8
    if ($exitCode -ne 0) {
        throw "Codex failed for $Label with exit code $exitCode. Local log: $logPath"
    }
}

function Get-OpenAutoPr {
    $json = & gh pr list --repo $Repository --state open --search "head:auto/dev-" --limit 10 --json number,headRefName,url
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to list autonomous-development PRs."
    }
    $items = @($json | ConvertFrom-Json)
    if ($items.Count -eq 0) {
        return $null
    }
    return $items[0]
}

function Get-PrCheckState {
    param([int]$Number)

    $json = & gh pr view $Number --repo $Repository --json statusCheckRollup
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect PR #$Number checks."
    }
    $data = $json | ConvertFrom-Json
    $checks = @($data.statusCheckRollup)
    if ($checks.Count -eq 0) {
        return "pending"
    }

    $failed = $false
    $pending = $false
    foreach ($check in $checks) {
        $conclusion = [string]$check.conclusion
        $state = [string]$check.state
        if ($conclusion -in @(
            "FAILURE", "CANCELLED", "TIMED_OUT",
            "ACTION_REQUIRED", "STARTUP_FAILURE"
        )) {
            $failed = $true
        } elseif (
            [string]::IsNullOrWhiteSpace($conclusion) -and
            $state -notin @("SUCCESS", "COMPLETED")
        ) {
            $pending = $true
        }
    }
    if ($failed) { return "failed" }
    if ($pending) { return "pending" }
    return "passed"
}

function Wait-PrChecks {
    param([int]$Number)

    $deadline = [DateTimeOffset]::UtcNow.AddMinutes($CheckWaitMinutes)
    while ([DateTimeOffset]::UtcNow -lt $deadline) {
        $state = Get-PrCheckState -Number $Number
        if ($state -ne "pending") {
            return $state
        }
        Start-Sleep -Seconds 20
    }
    return "pending"
}

function Get-FailedCiExcerpt {
    param([string]$BranchName)

    $json = & gh run list --repo $Repository --branch $BranchName --limit 8 --json databaseId,status,conclusion,name
    if ($LASTEXITCODE -ne 0) {
        return "Unable to read failed CI logs."
    }
    $runs = @($json | ConvertFrom-Json)
    $failedRun = $runs | Where-Object {
        $_.conclusion -eq "failure"
    } | Select-Object -First 1
    if ($null -eq $failedRun) {
        return "CI failed, but no failed workflow run was located."
    }
    $log = (& gh run view ([int]$failedRun.databaseId) --repo $Repository --log-failed 2>&1 | Out-String)
    if ($log.Length -gt 12000) {
        return $log.Substring($log.Length - 12000)
    }
    return $log
}

function Invoke-GuardAndTests {
    $guardPath = Join-Path $PSScriptRoot "verify_autonomous_dev_guard.py"
    & python $guardPath --repo $DevRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Autonomous development safety guard failed."
    }
    & python -m pytest -q
    if ($LASTEXITCODE -ne 0) {
        throw "Local pytest failed."
    }
}

function Repair-OpenPr {
    param($Pr)

    $branchName = [string]$Pr.headRefName
    & git fetch origin $branchName
    & git checkout -B $branchName "origin/$branchName"

    $ciExcerpt = Get-FailedCiExcerpt -BranchName $branchName
    $repairPrompt = @"
You are repairing an existing autonomous-development PR in HorseRacingPredictions.

Repair the failing CI only. Work in the current branch and current repository.
Do not commit, push, create PRs, merge, or change git branches.
Do not modify any .github/workflows file, any path containing 'holdout',
src/horse_racing_predictions/residual_shadow_paper.py,
src/horse_racing_predictions/residual_paper_evidence.py,
src/horse_racing_predictions/market_residual_v12_holdout.py,
src/horse_racing_predictions/residual_v12_artifact.py,
scripts/verify_autonomous_dev_guard.py,
scripts/run_autonomous_dev_cycle.ps1,
or scripts/run_autonomous_dev_12h.ps1.
Do not enable live betting, change frozen Paper thresholds, reuse holdout data,
upload raw JRA-VAN/horse-level data, or add paid services.
Make the minimum safe code/test correction needed for CI.

Failed CI excerpt:
$ciExcerpt
"@
    Invoke-Codex -Prompt $repairPrompt -Label "repair-pr-$($Pr.number)-cycle-$Cycle"
    Invoke-GuardAndTests

    & git add -A
    & git diff --cached --quiet
    if ($LASTEXITCODE -eq 0) {
        throw "Repair Codex run produced no tracked correction."
    }
    & git commit -m "auto: repair PR #$($Pr.number) cycle $Cycle"
    if ($LASTEXITCODE -ne 0) { throw "Repair commit failed." }
    & git push origin $branchName
    if ($LASTEXITCODE -ne 0) { throw "Repair push failed." }
}

$openPr = Get-OpenAutoPr
if ($null -ne $openPr) {
    Write-Host "Existing autonomous PR #$($openPr.number) found."
    $checkState = Wait-PrChecks -Number ([int]$openPr.number)
    if ($checkState -eq "failed") {
        Repair-OpenPr -Pr $openPr
        $checkState = Wait-PrChecks -Number ([int]$openPr.number)
    }
    if ($checkState -eq "passed") {
        & gh pr merge ([int]$openPr.number) --repo $Repository --merge --delete-branch
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to merge autonomous PR #$($openPr.number)."
        }
        & git fetch origin main --prune
        & git checkout -B main origin/main
    } elseif ($checkState -eq "pending") {
        throw "Autonomous PR #$($openPr.number) checks did not finish within the cycle window."
    } else {
        throw "Autonomous PR #$($openPr.number) still has failing checks after one repair."
    }
}

$stamp = [DateTimeOffset]::UtcNow.ToString("yyyyMMdd-HHmmss")
$cycleText = "{0:D2}" -f $Cycle
$branchName = "auto/dev-$stamp-c$cycleText"
& git checkout -b $branchName

$prompt = @"
Work on HorseRacingPredictions for one bounded autonomous development cycle.

Goal: make one substantive, non-adaptive engineering improvement that moves the
prospective Residual v12 Paper validation system closer to reliable unattended
evidence collection and analysis.

Priority order:
1. automation reliability, stale heartbeat/failure detection, data integrity;
2. sanitized Paper/Evidence observability and diagnostics;
3. machine-local state consistency/backup/failover checks;
4. Streamlit dashboard runtime smoke and robustness;
5. read-only EV/odds/calibration/losing-streak/drawdown diagnostics;
6. meaningful test coverage for the above.

Rules:
- Inspect current code/tests/history first and choose one not-yet-implemented improvement.
- Do not commit, push, create/merge PRs, or change git branches; the orchestrator handles git.
- Do not modify .github/workflows or any path containing 'holdout'.
- Do not modify:
  src/horse_racing_predictions/residual_shadow_paper.py
  src/horse_racing_predictions/residual_paper_evidence.py
  src/horse_racing_predictions/market_residual_v12_holdout.py
  src/horse_racing_predictions/residual_v12_artifact.py
  scripts/verify_autonomous_dev_guard.py
  scripts/run_autonomous_dev_cycle.ps1
  scripts/run_autonomous_dev_12h.ps1
- Frozen values must remain: gamma=4.0, EV=1.15, min probability=0.03,
  fractional Kelly=0.25, max race exposure=2%, max day exposure=8%,
  Evidence Gate=500 evaluated races + 200 settled Paper bets.
- Never reuse/rerun the opened 2025-2026 holdout.
- Never enable live/real-money betting or automatic live promotion.
- Never upload raw JRA-VAN data, horse-level predictions/odds/results, SQLite DBs,
  credentials, secrets, or machine-local data to GitHub.
- Do not adapt strategy/model thresholds to current prospective outcomes.
- Do not add paid services or API dependencies.
- Prefer a focused code change with tests over documentation-only work.
- Run relevant tests before finishing.

Cycle number: $Cycle.
"@

Invoke-Codex -Prompt $prompt -Label "new-cycle-$Cycle"
Invoke-GuardAndTests

& git add -A
& git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    throw "Codex cycle produced no tracked repository changes."
}

& git commit -m "auto: autonomous development cycle $Cycle"
if ($LASTEXITCODE -ne 0) {
    throw "Autonomous commit failed."
}
$commitSha = (& git rev-parse HEAD).Trim()

& git push -u origin $branchName
if ($LASTEXITCODE -ne 0) {
    throw "Autonomous branch push failed."
}

$body = @"
Automated PC1 Codex development cycle $Cycle.

Safety boundaries:
- frozen strategy/model/Evidence thresholds unchanged
- holdout untouched
- live execution remains disabled
- no raw JRA-VAN/horse-level/SQLite data uploaded
- local pytest passed
- autonomous safety guard passed

Commit: $commitSha
"@
& gh pr create --repo $Repository --base main --head $branchName --title "Autonomous development cycle $Cycle" --body $body
if ($LASTEXITCODE -ne 0) {
    throw "Autonomous PR creation failed."
}

$created = Get-OpenAutoPr
if ($null -eq $created -or [string]$created.headRefName -ne $branchName) {
    throw "Unable to rediscover the newly created autonomous PR."
}

$checkState = Wait-PrChecks -Number ([int]$created.number)
if ($checkState -eq "failed") {
    Repair-OpenPr -Pr $created
    $checkState = Wait-PrChecks -Number ([int]$created.number)
}
if ($checkState -eq "passed") {
    & gh pr merge ([int]$created.number) --repo $Repository --merge --delete-branch
    if ($LASTEXITCODE -ne 0) {
        throw "Autonomous PR merge failed."
    }
    Write-Host "cycle_result=merged"
    Write-Host "cycle_commit=$commitSha"
    Write-Host "cycle_pr=$($created.number)"
} elseif ($checkState -eq "pending") {
    Write-Host "cycle_result=pr_pending"
    Write-Host "cycle_commit=$commitSha"
    Write-Host "cycle_pr=$($created.number)"
} else {
    throw "Autonomous PR still fails after one repair attempt."
}
