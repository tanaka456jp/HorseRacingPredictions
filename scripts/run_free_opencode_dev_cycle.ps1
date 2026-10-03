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
$QwenModel = "ollama/qwen3:8b"
$NemotronFreeModel = "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
$isOllama = $Model -eq $QwenModel
$isNemotronFree = $Model -eq $NemotronFreeModel
if (-not ($isOllama -or $isNemotronFree)) {
    throw "Only ollama/qwen3:8b or the exact Nemotron 3 Ultra :free model is allowed."
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
    "OPENCODE_SERVER_USERNAME",
    "OPENCODE_CONFIG",
    "OPENCODE_CONFIG_CONTENT",
    "OPENCODE_CONFIG_DIR",
    "OPENCODE_PERMISSION"
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

if ($isOllama) {
    $tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 5
    $modelNames = @($tags.models | ForEach-Object { [string]$_.name })
    if ($modelNames -notcontains "qwen3:8b") {
        throw "Required local model qwen3:8b is not available."
    }
} else {
    $envKeyPresent = -not [string]::IsNullOrWhiteSpace($env:OPENROUTER_API_KEY)
    $authText = ""
    try {
        $authRaw = @(& $OpenCodePath auth list --format json 2>$null)
        if ($LASTEXITCODE -eq 0) {
            $authText = [string](($authRaw | Out-String).Trim())
        }
    } catch {
        $authText = ""
    }
    if ([string]::IsNullOrWhiteSpace($authText)) {
        try {
            $authRaw = @(& $OpenCodePath auth list 2>$null)
            if ($LASTEXITCODE -eq 0) {
                $authText = [string](($authRaw | Out-String).Trim())
            }
        } catch {
            $authText = ""
        }
    }
    $storedOpenRouterAuth = $authText -match "(?i)openrouter"
    if (-not ($envKeyPresent -or $storedOpenRouterAuth)) {
        throw "OPENROUTER_NOT_AUTHENTICATED"
    }
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

$ConfigRoot = Join-Path $ControlRoot "free-opencode-cycle-config"
if (Test-Path -LiteralPath $ConfigRoot) {
    Remove-Item -LiteralPath $ConfigRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $ConfigRoot | Out-Null

if ($isOllama) {
    $configJson = @'
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
        "bash": "deny",
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
'@
} else {
    $configJson = @'
{
  "$schema": "https://opencode.ai/config.json",
  "model": "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free",
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
        "bash": "deny",
        "task": "deny",
        "external_directory": "deny",
        "webfetch": "deny",
        "websearch": "deny",
        "question": "deny",
        "doom_loop": "deny"
      }
    }
  }
}
'@
}
$env:OPENCODE_CONFIG_CONTENT = $configJson
$env:OPENCODE_CONFIG_DIR = $ConfigRoot
$env:OPENCODE_DISABLE_PROJECT_CONFIG = "1"
$env:OPENCODE_PURE = "1"
$env:OPENCODE_DISABLE_AUTOUPDATE = "1"
$env:OPENCODE_DISABLE_MODELS_FETCH = "1"
Remove-Item "Env:OPENCODE_CONFIG" -ErrorAction SilentlyContinue

function Assert-LocalConfigUnchanged {
    if ($env:OPENCODE_CONFIG_CONTENT -ne $configJson) {
        throw "OpenCode local-only inline configuration changed during the agent run."
    }
    if ($env:OPENCODE_CONFIG_DIR -ne $ConfigRoot) {
        throw "OpenCode isolated configuration directory changed during the agent run."
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
    $fullPrompt = if ($isOllama) { "/no_think " + $Prompt } else { $Prompt }
    $escapedModel = '"' + $Model.Replace('"', '\"') + '"'
    $escapedPrompt = '"' + $fullPrompt.Replace('"', '\"') + '"'
    $escapedTitle = '"' + $sessionTitle.Replace('"', '\"') + '"'
    $escapedDir = '"' + $DevRoot.Replace('"', '\"') + '"'
    $argumentString = "--pure run --auto --agent build --format json --dir $escapedDir --model $escapedModel --title $escapedTitle $escapedPrompt"

    Write-Host "Invoking free OpenCode model=$Model label=$Label"
    Write-Host "opencode_run_transport=in_process_non_attach"
    Write-Host "opencode_pure=True"
    Write-Host "opencode_auto_approve=True"
    Write-Host "opencode_agent=build"
    Write-Host "opencode_config_mode=inline_isolated"
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

function Get-RepositoryChangedPaths {
    $tracked = @(& git diff --name-only HEAD)
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect tracked repository changes."
    }
    $untracked = @(& git ls-files --others --exclude-standard)
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect untracked repository changes."
    }
    return @(
        @($tracked) + @($untracked) |
        Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } |
        Sort-Object -Unique
    )
}

function Get-CycleMicrotask {
    param([int]$Number)

    switch ($Number) {
        1 {
            return @{
                files = @(
                    "scripts/run_jravan_forward_runner.ps1",
                    "tests/test_jravan_forward_runner_script.py"
                )
                task = (@(
                    "Add a machine-local heartbeat JSON for the JRA-VAN Forward Paper runner.",
                    "Use artifacts/jravan_forward_runner_heartbeat.json.",
                    "Add a small helper that writes stage, updated_at_utc, computer_name, forward_paper_executed, residual_v12_paper_executed, and live_execution_enabled=false.",
                    "Update it at runner start, after input preparation, before and after Champion Paper, before and after Residual v12 Paper, and on normal completion.",
                    "Do not include raw race or horse data.",
                    "Extend the existing source-level tests to assert the heartbeat path, safe fields, and representative stage markers."
                ) -join " ")
            }
        }
        2 {
            return @{
                files = @(
                    "scripts/run_jravan_forward_runner.ps1",
                    "tests/test_jravan_forward_runner_script.py"
                )
                task = (@(
                    "Extend the existing forward-runner heartbeat with started_at_utc and elapsed_seconds so a stalled run can be distinguished from a slow run.",
                    "Keep the values operational-only and machine-local.",
                    "Add source-level tests for both fields.",
                    "Do not change betting behavior."
                ) -join " ")
            }
        }
        3 {
            return @{
                files = @(
                    "src/horse_racing_predictions/dashboard.py",
                    "tests/test_residual_paper_dashboard.py"
                )
                task = (@(
                    "Add a read-only dashboard section that loads artifacts/jravan_forward_runner_heartbeat.json when present.",
                    "Display its stage, updated time, and whether forward and residual Paper stages have executed.",
                    "If the file is absent, show an informational message.",
                    "Do not alter Paper decisions or thresholds.",
                    "Add source-level dashboard tests for the new section."
                ) -join " ")
            }
        }
        4 {
            return @{
                files = @(
                    "src/horse_racing_predictions/dashboard.py",
                    "tests/test_residual_paper_dashboard.py"
                )
                task = (@(
                    "Harden the dashboard heartbeat display.",
                    "If the heartbeat JSON is malformed or updated_at_utc is older than 30 minutes, show a warning instead of crashing.",
                    "Keep this read-only and non-adaptive.",
                    "Add source-level tests that cover malformed and stale handling markers in the dashboard source."
                ) -join " ")
            }
        }
        5 {
            return @{
                files = @(
                    "src/horse_racing_predictions/current_history.py",
                    "tests/test_current_history.py"
                )
                task = (@(
                    "Extend HistoryIntakeReport with base_races, supplemental_races, and merged_races counts.",
                    "Compute them from race_id without changing intake acceptance rules.",
                    "Add tests for the clean adjacent supplement case and keep blocked reports safe."
                ) -join " ")
            }
        }
        6 {
            return @{
                files = @(
                    "src/horse_racing_predictions/current_history.py",
                    "tests/test_current_history.py"
                )
                task = (@(
                    "Extend HistoryIntakeReport with supplemental_date_span_days.",
                    "Define it as the calendar-day difference between supplemental minimum and maximum race_date.",
                    "Use 0 for a single day and None when unavailable.",
                    "This is observability only.",
                    "Add tests."
                ) -join " ")
            }
        }
        7 {
            return @{
                files = @(
                    "src/horse_racing_predictions/jravan_forward.py",
                    "tests/test_jravan_forward.py"
                )
                task = (@(
                    "Extend TrialForwardInputSummary with complete_odds_coverage_rate.",
                    "Calculate it as odds_races divided by future_entry_races when future_entry_races is greater than zero, otherwise None.",
                    "Do not change capture or eligibility behavior.",
                    "Add focused tests."
                ) -join " ")
            }
        }
        8 {
            return @{
                files = @(
                    "src/horse_racing_predictions/jravan_forward.py",
                    "tests/test_jravan_forward.py"
                )
                task = (@(
                    "Extend TrialForwardInputSummary with complete_odds_coverage.",
                    "It is true only when there is at least one future race and every future race has a complete odds race.",
                    "This is diagnostic-only.",
                    "Add focused tests for complete and empty or incomplete cases."
                ) -join " ")
            }
        }
        9 {
            return @{
                files = @(
                    "src/horse_racing_predictions/paper_input.py",
                    "tests/test_future_pipeline.py"
                )
                task = (@(
                    "Fail closed in prepare_paper_input when predictions contain duplicate (race_id, horse_id) rows.",
                    "Raise a clear ValueError before resolving odds.",
                    "Add a test proving duplicate rows are rejected.",
                    "Do not alter valid-row behavior."
                ) -join " ")
            }
        }
        10 {
            return @{
                files = @(
                    "src/horse_racing_predictions/paper_input.py",
                    "tests/test_future_pipeline.py"
                )
                task = (@(
                    "Fail closed in prepare_paper_input when horse_name is blank or whitespace after conversion to string.",
                    "Raise a clear ValueError before odds resolution and add a focused test.",
                    "Do not alter valid-row behavior."
                ) -join " ")
            }
        }
        11 {
            return @{
                files = @(
                    "src/horse_racing_predictions/forward_pipeline.py",
                    "tests/test_future_pipeline.py"
                )
                task = (@(
                    "Add prediction_rows, prediction_races, paper_input_rows, and paper_input_races to the forward_paper_summary.json payload.",
                    "These are sanitized aggregate counts only.",
                    "Add lightweight source-level assertions in tests/test_future_pipeline.py.",
                    "Do not change inference, staking, or Paper behavior."
                ) -join " ")
            }
        }
        default {
            return @{
                files = @(
                    "scripts/run_jravan_forward_runner.ps1",
                    "tests/test_jravan_forward_runner_script.py"
                )
                task = (@(
                    "Add run_duration_seconds to the final JRA-VAN Forward Paper validation payload.",
                    "Measure it from runner start to final validation write.",
                    "It is operational telemetry only.",
                    "Add source-level tests and do not change betting behavior."
                ) -join " ")
            }
        }
    }
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
upload raw JRA-VAN/horse-level data, add paid services, or switch away from the selected free model.

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

$SafetyBoundaries = (@(
    "Frozen safety boundaries:",
    "- gamma=4.0",
    "- EV=1.15",
    "- min probability=0.03",
    "- fractional Kelly=0.25",
    "- max race exposure=2%",
    "- max day exposure=8%",
    "- max single bet=10000 yen",
    "- Evidence Gate=500 evaluated races + 200 settled Paper bets",
    "- Never reuse/rerun the opened 2025-2026 holdout.",
    "- Never enable live/real-money betting or automatic live promotion.",
    "- Do not adapt strategy/model thresholds to prospective outcomes."
) -join [Environment]::NewLine)

$microtask = Get-CycleMicrotask -Number $Cycle
$AllowedCycleFiles = @($microtask.files)
$allowedText = ($AllowedCycleFiles -join ", ")
$prompt = (@(
    "Make exactly one small repository edit for HorseRacingPredictions.",
    "",
    "Task:",
    [string]$microtask.task,
    "",
    "Allowed files only:",
    $allowedText,
    "",
    "Rules:",
    "- Read only the allowed files. Do not explore git history or unrelated files.",
    "- Edit the allowed implementation file(s) and test file(s), then stop.",
    "- Do not run tests or shell commands; the orchestrator runs all tests afterward.",
    "- Do not commit, push, create PRs, merge, or change branches.",
    $SafetyBoundaries,
    "- Never add or switch providers; use only the already-selected exact free model.",
    "- Never add paid services or new network dependencies.",
    "- Never add raw JRA-VAN, horse-level prediction/odds/results, SQLite, secrets, or credentials."
) -join [Environment]::NewLine)

Invoke-FreeOpenCode -Prompt $prompt -Label "new-cycle-$Cycle"
if ((Get-RepositoryChangeCount) -eq 0) {
    $retryPrompt = (@(
        "The first attempt made no repository changes.",
        "Complete only the previously assigned microtask using only: $allowedText",
        "Do not run tests or shell commands. Make the code and test edits now, then stop."
    ) -join [Environment]::NewLine)

    Invoke-FreeOpenCode -Prompt $retryPrompt -Label "new-cycle-$Cycle-retry"
}
if ((Get-RepositoryChangeCount) -eq 0) {
    throw "Free OpenCode cycle produced no repository changes after one retry."
}

$changedPaths = @(Get-RepositoryChangedPaths)
$outsideAllowed = @(
    $changedPaths | Where-Object { $AllowedCycleFiles -notcontains [string]$_ }
)
if ($outsideAllowed.Count -gt 0) {
    throw (
        "Free OpenCode changed files outside the assigned microtask: " +
        ($outsideAllowed -join ", ")
    )
}
Write-Host "microtask_changed_files=$($changedPaths.Count)"
Write-Host "microtask_allowed_files=$allowedText"

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
Automated PC1 free OpenCode development cycle $Cycle using exact model $Model.

Safety boundaries:
- paid provider usage disabled
- paid LLM usage disabled
- exact free model pinned: $Model
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
