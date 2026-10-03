param(
    [int]$Cycle = 1,
    [string]$ExpectedComputerName = "DESKTOP-MVV1FD4",
    [string]$Repository = "tanaka456jp/HorseRacingPredictions",
    [string]$DevRoot = "",
    [int]$CheckWaitMinutes = 20,
    [int]$ModelTimeoutSeconds = 1200,
    [string]$Version = "1.18.29",
    [string]$Model = "ollama/qwen3:8b"
)

$ErrorActionPreference = "Stop"

if ($env:COMPUTERNAME -ne $ExpectedComputerName) {
    throw "Refusing autonomous development on $($env:COMPUTERNAME); expected $ExpectedComputerName."
}
if ($Version -ne "1.18.29") {
    throw "Only the pinned free OpenCode CLI version 1.18.29 is allowed."
}
if ($Model -ne "ollama/qwen3:8b") {
    throw "Only the local model ollama/qwen3:8b is allowed."
}
if ($ModelTimeoutSeconds -lt 60 -or $ModelTimeoutSeconds -gt 1800) {
    throw "ModelTimeoutSeconds must be between 60 and 1800."
}

foreach ($name in @(
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "GROQ_API_KEY",
    "OLLAMA_API_KEY",
    "OPENCODE_SERVER_PASSWORD",
    "OPENCODE_SERVER_USERNAME"
)) {
    Remove-Item "Env:$name" -ErrorAction SilentlyContinue
}

$ControlRoot = Join-Path $env:LOCALAPPDATA "HorseRacingPredictionsAutonomousDev"
if ([string]::IsNullOrWhiteSpace($DevRoot)) {
    $DevRoot = Join-Path $ControlRoot "repo-free-opencode"
}
$LogDir = Join-Path $ControlRoot "logs\free-opencode"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$OpenCodePath = Join-Path $ControlRoot "opencode-cli-$Version\node_modules\opencode-ai\bin\opencode.exe"
if (-not (Test-Path -LiteralPath $OpenCodePath -PathType Leaf)) {
    throw "FREE_OPENCODE_CLI_NOT_BOOTSTRAPPED"
}
if ((Get-Item -LiteralPath $OpenCodePath).Length -lt 1000000) {
    throw "FREE_OPENCODE_CLI_BINARY_IS_PLACEHOLDER"
}

$tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 5
$modelNames = @($tags.models | ForEach-Object { [string]$_.name })
if ($modelNames -notcontains "qwen3:8b") {
    throw "Required local model qwen3:8b is not available."
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
        throw "Unable to create dedicated free OpenCode development clone."
    }
}

Set-Location $DevRoot
& git remote set-url origin "https://github.com/$Repository.git"
& git reset --hard
& git clean -fd
& git fetch origin main --prune
& git checkout -B main origin/main

$excludePath = Join-Path $DevRoot ".git\info\exclude"
$excludeText = ""
if (Test-Path -LiteralPath $excludePath -PathType Leaf) {
    $excludeText = Get-Content -LiteralPath $excludePath -Raw -Encoding UTF8
}
if ($excludeText -notmatch "(?m)^opencode\.json$") {
    Add-Content -LiteralPath $excludePath -Value "opencode.json" -Encoding UTF8
}

$configPath = Join-Path $DevRoot "opencode.json"
@'
{
  "$schema": "https://opencode.ai/config.json",
  "model": "ollama/qwen3:8b",
  "share": "disabled",
  "default_agent": "build",
  "agent": {
    "build": {
      "mode": "primary",
      "permission": {
        "read": "allow",
        "edit": "allow",
        "glob": "allow",
        "grep": "allow",
        "list": "allow",
        "bash": {
          "*": "allow",
          "git commit *": "deny",
          "git push *": "deny",
          "git checkout *": "deny",
          "git switch *": "deny",
          "git reset *": "deny",
          "git clean *": "deny",
          "gh *": "deny",
          "curl *": "deny",
          "wget *": "deny",
          "Invoke-WebRequest *": "deny",
          "Invoke-RestMethod *": "deny",
          "pip install *": "deny",
          "python -m pip install *": "deny",
          "npm install *": "deny",
          "pnpm *": "deny",
          "yarn *": "deny"
        },
        "task": "deny",
        "external_directory": "deny",
        "webfetch": "deny",
        "websearch": "deny",
        "question": "deny",
        "doom_loop": "deny"
      }
    }
  },
  "provider": {
    "ollama": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Ollama (local only)",
      "options": {
        "baseURL": "http://127.0.0.1:11434/v1"
      },
      "models": {
        "qwen3:8b": {
          "name": "qwen3:8b"
        }
      }
    }
  }
}
'@ | Set-Content -LiteralPath $configPath -Encoding UTF8
$configHash = (Get-FileHash -LiteralPath $configPath -Algorithm SHA256).Hash
$env:OPENCODE_CONFIG = $configPath
$env:OPENCODE_DISABLE_AUTOUPDATE = "true"
$env:OPENCODE_AUTO_SHARE = "false"

function Assert-LocalConfigUnchanged {
    if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
        throw "OpenCode local-only configuration was removed."
    }
    $currentHash = (Get-FileHash -LiteralPath $configPath -Algorithm SHA256).Hash
    if ($currentHash -ne $configHash) {
        throw "OpenCode local-only configuration was modified during the agent run."
    }
}

function Invoke-FreeOpenCode {
    param(
        [string]$Prompt,
        [string]$Label
    )

    $stamp = [DateTimeOffset]::UtcNow.ToString("yyyyMMddTHHmmssZ")
    $stdoutPath = Join-Path $LogDir "$stamp-$Label.stdout.txt"
    $stderrPath = Join-Path $LogDir "$stamp-$Label.stderr.txt"
    $sessionTitle = "HRP_FREE_AUTO_$($Label)_$([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())"
    $fullPrompt = "/no_think " + $Prompt
    $escapedModel = '"' + $Model.Replace('"', '\"') + '"'
    $escapedPrompt = '"' + $fullPrompt.Replace('"', '\"') + '"'
    $escapedTitle = '"' + $sessionTitle.Replace('"', '\"') + '"'
    $escapedDir = '"' + $DevRoot.Replace('"', '\"') + '"'
    $argumentString = "run --standalone --auto --agent build --format json --dir $escapedDir --model $escapedModel --title $escapedTitle $escapedPrompt"

    Write-Host "Invoking free OpenCode + local Ollama: $Label"
    Write-Host "opencode_standalone=True"
    Write-Host "opencode_auto_approve=True"
    Write-Host "opencode_agent=build"
    Write-Host "opencode_config=$configPath"
    $process = Start-Process -FilePath $OpenCodePath -ArgumentList $argumentString -WorkingDirectory $DevRoot -NoNewWindow -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru
    $completed = $process.WaitForExit($ModelTimeoutSeconds * 1000)
    if (-not $completed) {
        & taskkill.exe /PID $process.Id /T /F *> $null
        $process.WaitForExit()
        throw "OpenCode timed out for $Label after $ModelTimeoutSeconds seconds."
    }
    $exitCode = [int]$process.ExitCode
    Assert-LocalConfigUnchanged
    $stdoutBytes = if (Test-Path -LiteralPath $stdoutPath) {
        (Get-Item -LiteralPath $stdoutPath).Length
    } else {
        0
    }
    $stderrBytes = if (Test-Path -LiteralPath $stderrPath) {
        (Get-Item -LiteralPath $stderrPath).Length
    } else {
        0
    }
    $repoChangeCount = Get-RepositoryChangeCount
    Write-Host (
        "opencode_result label=$Label exit_code=$exitCode " +
        "stdout_bytes=$stdoutBytes stderr_bytes=$stderrBytes " +
        "repo_changes=$repoChangeCount"
    )
    if ($exitCode -ne 0) {
        throw "OpenCode failed for $Label with exit code $exitCode. Local logs: $stdoutPath ; $stderrPath"
    }
}

function Get-RepositoryChangeCount {
    $lines = @(& git status --porcelain=v1 --untracked-files=all)
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect repository changes."
    }
    return @($lines | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) }).Count
}

function Get-OpenAutoPr {
    $json = & gh pr list --repo $Repository --state open --limit 100 --json number,headRefName,url
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to list autonomous-development PRs."
    }
    $items = @($json | ConvertFrom-Json)
    return $items |
        Where-Object { ([string]$_.headRefName).StartsWith("auto/free-opencode-dev-") } |
        Select-Object -First 1
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
        $status = [string]$check.status
        if ($conclusion -in @(
            "FAILURE", "CANCELLED", "TIMED_OUT",
            "ACTION_REQUIRED", "STARTUP_FAILURE"
        )) {
            $failed = $true
        } elseif (
            [string]::IsNullOrWhiteSpace($conclusion) -and
            $state -notin @("SUCCESS", "COMPLETED") -and
            $status -notin @("COMPLETED")
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
        Start-Sleep -Seconds 30
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
    if ($LASTEXITCODE -ne 0) { throw "Unable to fetch repair branch." }
    & git checkout -B $branchName "origin/$branchName"
    if ($LASTEXITCODE -ne 0) { throw "Unable to checkout repair branch." }
    & git reset --hard "origin/$branchName"
    & git clean -fd

    $ciExcerpt = Get-FailedCiExcerpt -BranchName $branchName
    $repairPrompt = @"
You are repairing an existing autonomous-development PR in HorseRacingPredictions.

Repair only the failing CI with the minimum safe code/test correction.
Work in the current branch and current repository.
Do not commit, push, create PRs, merge, or change git branches.
Do not modify any .github/workflows file, any path containing 'holdout',
src/horse_racing_predictions/residual_shadow_paper.py,
src/horse_racing_predictions/residual_paper_evidence.py,
src/horse_racing_predictions/market_residual_v12_holdout.py,
src/horse_racing_predictions/residual_v12_artifact.py,
scripts/verify_autonomous_dev_guard.py,
scripts/run_autonomous_dev_cycle.ps1,
scripts/run_autonomous_dev_12h.ps1,
scripts/run_free_opencode_dev_cycle.ps1,
scripts/run_free_opencode_dev_12h.ps1,
or research/free_opencode_autonomous_dev_12h_request.txt.
Do not enable live betting, change frozen Paper thresholds, reuse holdout data,
upload raw JRA-VAN/horse-level data, add paid services, or add cloud/API-key providers.

Failed CI excerpt:
$ciExcerpt
"@
    Invoke-FreeOpenCode -Prompt $repairPrompt -Label "repair-pr-$($Pr.number)-cycle-$Cycle"
    if ((Get-RepositoryChangeCount) -eq 0) {
        throw "Free OpenCode repair produced no repository correction."
    }
    Invoke-GuardAndTests

    & git add -A
    & git diff --cached --quiet
    if ($LASTEXITCODE -eq 0) {
        throw "Free OpenCode repair produced no committable correction."
    }
    & git commit -m "auto: repair free OpenCode PR #$($Pr.number) cycle $Cycle"
    if ($LASTEXITCODE -ne 0) { throw "Repair commit failed." }
    & git push origin $branchName
    if ($LASTEXITCODE -ne 0) { throw "Repair push failed." }
}

$openPr = Get-OpenAutoPr
if ($null -ne $openPr) {
    Write-Host "Existing free OpenCode autonomous PR #$($openPr.number) found."
    $checkState = Wait-PrChecks -Number ([int]$openPr.number)
    if ($checkState -eq "failed") {
        Repair-OpenPr -Pr $openPr
        $checkState = Wait-PrChecks -Number ([int]$openPr.number)
    }
    if ($checkState -eq "passed") {
        & gh pr merge ([int]$openPr.number) --repo $Repository --merge --delete-branch
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to merge free OpenCode autonomous PR #$($openPr.number)."
        }
        & git fetch origin main --prune
        & git checkout -B main origin/main
    } elseif ($checkState -eq "pending") {
        Write-Host "cycle_result=existing_pr_pending"
        Write-Host "cycle_pr=$($openPr.number)"
        return
    } else {
        throw "Free OpenCode autonomous PR #$($openPr.number) still has failing checks after one repair."
    }
}

& git reset --hard
& git clean -fd
& git fetch origin main --prune
& git checkout -B main origin/main

$stamp = [DateTimeOffset]::UtcNow.ToString("yyyyMMdd-HHmmss")
$cycleText = "{0:D2}" -f $Cycle
$branchName = "auto/free-opencode-dev-$stamp-c$cycleText"
& git checkout -b $branchName
if ($LASTEXITCODE -ne 0) {
    throw "Unable to create autonomous branch."
}

$prompt = @"
Work on HorseRacingPredictions for one bounded autonomous development cycle.

Goal: make one substantive, non-adaptive engineering improvement that moves the
prospective Residual v12 Paper validation system closer to reliable unattended
evidence collection and analysis.

Priority order:
1. automation reliability, stale heartbeat/failure detection, and data integrity;
2. sanitized Paper/Evidence observability and diagnostics;
3. machine-local state consistency, backup, and failover checks;
4. Streamlit dashboard runtime smoke and robustness;
5. read-only EV/odds/calibration/losing-streak/drawdown diagnostics;
6. meaningful test coverage for the above.

Rules:
- Inspect current code/tests/history first and implement one not-yet-implemented improvement.
- Produce a real code/test change; do not finish with analysis or documentation only.
- Do not commit, push, create/merge PRs, or change git branches; the orchestrator handles git.
- Do not modify .github/workflows, .git, opencode.json, or any path containing 'holdout'.
- Do not modify:
  src/horse_racing_predictions/residual_shadow_paper.py
  src/horse_racing_predictions/residual_paper_evidence.py
  src/horse_racing_predictions/market_residual_v12_holdout.py
  src/horse_racing_predictions/residual_v12_artifact.py
  scripts/verify_autonomous_dev_guard.py
  scripts/run_autonomous_dev_cycle.ps1
  scripts/run_autonomous_dev_12h.ps1
  scripts/run_free_opencode_dev_cycle.ps1
  scripts/run_free_opencode_dev_12h.ps1
  research/free_opencode_autonomous_dev_12h_request.txt
- Frozen values must remain: gamma=4.0, EV=1.15, min probability=0.03,
  fractional Kelly=0.25, max race exposure=2%, max day exposure=8%,
  max single bet=10000 yen, Evidence Gate=500 evaluated races + 200 settled Paper bets.
- Never reuse/rerun the opened 2025-2026 holdout.
- Never enable live/real-money betting or automatic live promotion.
- Never upload raw JRA-VAN data, horse-level predictions/odds/results, SQLite DBs,
  credentials, secrets, or machine-local data to GitHub.
- Do not adapt strategy/model thresholds to current prospective outcomes.
- Do not add paid services, cloud providers, API keys, or network LLM dependencies.
- Run relevant tests before finishing.

Cycle number: $Cycle.
"@

Invoke-FreeOpenCode -Prompt $prompt -Label "new-cycle-$Cycle"
if ((Get-RepositoryChangeCount) -eq 0) {
    $retryPrompt = @"
The first attempt made no repository changes. Make exactly one focused code-and-test
improvement from the allowed priorities in the previous instructions. Keep every
frozen boundary intact. Do not only explain the change; edit the repository and tests.
"@
    Invoke-FreeOpenCode -Prompt $retryPrompt -Label "new-cycle-$Cycle-retry"
}
if ((Get-RepositoryChangeCount) -eq 0) {
    throw "Free OpenCode cycle produced no repository changes after one retry."
}

Invoke-GuardAndTests

& git add -A
& git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    throw "Free OpenCode cycle produced no committable repository changes."
}

& git commit -m "auto: free OpenCode development cycle $Cycle"
if ($LASTEXITCODE -ne 0) {
    throw "Autonomous commit failed."
}
$commitSha = (& git rev-parse HEAD).Trim()

& git push -u origin $branchName
if ($LASTEXITCODE -ne 0) {
    throw "Autonomous branch push failed."
}

$body = @"
Automated PC1 free OpenCode + local Ollama qwen3:8b development cycle $Cycle.

Safety boundaries:
- paid provider usage disabled
- API-key LLM usage disabled
- Codex unused
- frozen strategy/model/Evidence thresholds unchanged
- 2025-2026 holdout untouched
- live execution remains disabled
- no raw JRA-VAN/horse-level/SQLite data uploaded
- local pytest passed
- autonomous safety guard passed

Commit: $commitSha
"@
& gh pr create --repo $Repository --base main --head $branchName --title "Free OpenCode autonomous development cycle $Cycle" --body $body
if ($LASTEXITCODE -ne 0) {
    throw "Autonomous PR creation failed."
}

$created = Get-OpenAutoPr
if ($null -eq $created -or [string]$created.headRefName -ne $branchName) {
    throw "Unable to rediscover the newly created free OpenCode autonomous PR."
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
