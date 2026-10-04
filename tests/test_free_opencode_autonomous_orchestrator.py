from pathlib import Path


def test_free_opencode_autonomous_workflow_is_pc2_marker_triggered():
    workflow = Path(
        ".github/workflows/free-opencode-autonomous-dev-12h-self-hosted.yml"
    ).read_text(encoding="utf-8")

    assert "schedule:" not in workflow
    assert "workflow_dispatch:" in workflow
    assert "research/free_opencode_autonomous_dev_12h_request.txt" in workflow
    assert "runs-on: [self-hosted, Windows]" in workflow
    assert "Autonomous Development 12h (PC2 Free OpenCode)" in workflow
    assert "Run guarded free autonomous development on PC2" in workflow
    assert "DESKTOP-MVV1FD4 is PC2" in workflow
    assert "timeout-minutes: 780" in workflow
    assert "persist-credentials: false" in workflow
    assert "cancel-in-progress: true" in workflow
    assert "install_free_opencode_cli.ps1" in workflow
    assert "audit_free_nemotron_opencode.ps1" in workflow
    assert "run_free_opencode_dev_12h.ps1" in workflow
    assert "Parse free OpenCode PowerShell scripts" in workflow
    assert "System.Management.Automation.Language.Parser" in workflow
    assert "id: nemotron_smoke" in workflow
    assert "continue-on-error: true" in workflow
    assert "Select free autonomous model" in workflow
    assert "SELECTED_FREE_MODEL" in workflow
    assert "nemotron_smoke_failed_local_fallback" in workflow
    assert 'openrouter/nvidia/nemotron-3-ultra-550b-a55b:free' in workflow
    assert 'ollama/qwen3:8b' in workflow
    assert '-Model "$env:SELECTED_FREE_MODEL"' in workflow
    assert '-FallbackModel "ollama/qwen3:8b"' in workflow
    assert "OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}" in workflow
    assert "I_APPROVE_PAID_CODEX" not in workflow


def test_free_opencode_cycle_uses_only_pinned_local_model_and_git_pr_flow():
    script = Path(
        "scripts/run_free_opencode_dev_cycle.ps1"
    ).read_text(encoding="utf-8")

    assert '[string]$Version = "1.18.29"' in script
    assert '[string]$Model = "ollama/qwen3:8b"' in script
    assert "opencode-ai\\bin\\opencode.exe" in script
    assert "http://127.0.0.1:11434/api/tags" in script
    assert 'baseURL": "http://127.0.0.1:11434/v1"' in script
    assert '"OPENAI_API_KEY"' in script
    assert '"ANTHROPIC_API_KEY"' in script
    assert '"GOOGLE_API_KEY"' in script
    assert '"GROQ_API_KEY"' in script
    assert '"OLLAMA_API_KEY"' in script
    assert "--standalone" not in script
    assert "--pure run --auto --agent build --format json --dir $escapedDir --model $escapedModel" in script
    assert '$env:OPENCODE_CONFIG_CONTENT = $configJson' in script
    assert '$env:OPENCODE_CONFIG_DIR = $ConfigRoot' in script
    assert '$env:OPENCODE_DISABLE_PROJECT_CONFIG = "1"' in script
    assert '$env:OPENCODE_PURE = "1"' in script
    assert '$env:OPENCODE_DISABLE_AUTOUPDATE = "1"' in script
    assert '$env:OPENCODE_DISABLE_MODELS_FETCH = "1"' in script
    assert '"share": "disabled"' in script
    assert "opencode_run_transport=in_process_non_attach" in script
    assert "opencode_result label=$Label" in script
    assert "repo_changes=$repoChangeCount" in script
    assert '"default_agent": "build"' in script
    assert '"agent": {' in script
    assert '"build": {' in script
    assert '"permission": {' in script
    assert '"external_directory": "deny"' in script
    assert '"webfetch": "deny"' in script
    assert '"websearch": "deny"' in script
    assert '"question": "deny"' in script
    assert '"doom_loop": "deny"' in script
    assert '"bash": "deny"' in script
    assert 'opencode_agent=build' in script
    assert "codex.exe" not in script.lower()
    assert "verify_autonomous_dev_guard.py" in script
    assert "python -m pytest -q" in script
    assert "gh pr create" in script
    assert "gh pr merge" in script
    assert "auto/free-opencode-dev-" in script
    assert "origin/main" in script
    assert "Get-CycleMicrotask" in script
    assert "Get-RepositoryChangedPaths" in script
    assert "Allowed files only:" in script
    assert "Do not run tests or shell commands" in script
    assert "microtask_changed_files=" in script
    assert "outside the assigned microtask" in script
    assert "scripts/run_jravan_forward_runner.ps1" in script
    assert "src/horse_racing_predictions/dashboard.py" in script
    assert "src/horse_racing_predictions/jravan_forward.py" in script
    assert "src/horse_racing_predictions/paper_input.py" in script
    assert "src/horse_racing_predictions/forward_pipeline.py" in script


def test_free_opencode_cycle_preserves_frozen_betting_boundaries():
    script = Path(
        "scripts/run_free_opencode_dev_cycle.ps1"
    ).read_text(encoding="utf-8")

    assert "gamma=4.0" in script
    assert "EV=1.15" in script
    assert "min probability=0.03" in script
    assert "fractional Kelly=0.25" in script
    assert "max race exposure=2%" in script
    assert "max day exposure=8%" in script
    assert "max single bet=10000 yen" in script
    assert "Evidence Gate=500 evaluated races + 200 settled Paper bets" in script
    assert "Never reuse/rerun the opened 2025-2026 holdout" in script
    assert "Never enable live/real-money betting" in script
    assert "Do not adapt strategy/model thresholds" in script


def test_free_opencode_cycle_has_bounded_retry_and_local_config_integrity():
    script = Path(
        "scripts/run_free_opencode_dev_cycle.ps1"
    ).read_text(encoding="utf-8")

    assert "[int]$ModelTimeoutSeconds = 1200" in script
    assert "WaitForExit($ModelTimeoutSeconds * 1000)" in script
    assert "taskkill.exe /PID $process.Id /T /F" in script
    assert '$env:OPENCODE_CONFIG_CONTENT -ne $configJson' in script
    assert "OpenCode local-only inline configuration changed" in script
    assert "new-cycle-$Cycle-retry" in script
    assert "Start-Sleep -Seconds 30" in script
    assert '[string]$microtask.task' in script
    assert "produced no repository changes after one retry" in script
    assert "Invoke-GuardTestsWithLocalRepair" in script
    assert "local_pytest_repair_attempt=1" in script
    assert "repair-local-pytest-cycle-$Cycle" in script
    assert "Pytest failure excerpt:" in script
    assert "Read and edit only the allowed files." in script
    assert "Assert-CycleChangedPathsAllowed" in script
    assert "Local pytest still failed after one repair attempt." in script
    assert "local_pytest_repair_result=success" in script


def test_free_opencode_12h_summary_proves_free_only_execution():
    script = Path(
        "scripts/run_free_opencode_dev_12h.ps1"
    ).read_text(encoding="utf-8")

    assert "orchestrator.lock" in script
    assert 'Join-Path $ControlRoot "STOP"' in script
    assert '"openrouter_free"' in script
    assert '[string]$FallbackModel = "ollama/qwen3:8b"' in script
    assert '$freeFallbackAllowed' in script
    assert 'local_free_fallback=$FallbackModel' in script
    assert 'free_fallback_used = [bool]$fallbackUsed' in script
    assert 'free_fallback_cycles = $fallbackCycles' in script
    assert 'provider = $providerName' in script
    assert "paid_provider_used = $false" in script
    assert "paid_fallback_allowed = $false" in script
    assert "api_key_used = $apiKeyUsed" in script
    assert 'OPENROUTER_API_KEY is required for the exact Nemotron :free model.' in script
    assert "codex_used = $false" in script
    assert "live_execution_enabled = $false" in script
    assert "completed_with_failures" in script
    assert "[int]$MaxConsecutiveFailures = 2" in script
    assert "consecutive_failures = $consecutiveFailures" in script
    assert "failed_fast = $failedFast" in script
    assert "GITHUB_STEP_SUMMARY" in script
    assert "Stopping after $consecutiveFailures consecutive failed cycles." in script
    assert "Skipping cycle pacing after failure for immediate diagnostic retry." in script
    assert '$cycle -lt $Cycles -and $status -eq "success"' in script


def test_autonomous_guard_includes_untracked_files_and_free_control_files():
    guard = Path(
        "scripts/verify_autonomous_dev_guard.py"
    ).read_text(encoding="utf-8")

    assert '"ls-files", "--others", "--exclude-standard"' in guard
    assert '"scripts/run_free_opencode_dev_cycle.ps1"' in guard
    assert '"scripts/run_free_opencode_dev_12h.ps1"' in guard
    assert '"research/free_opencode_autonomous_dev_12h_request.txt"' in guard
    assert '".opencode/"' in guard
    assert "Autonomous agent produced no repository changes." in guard
    assert "MAX_AUTONOMOUS_DIFF_LINES = 240" in guard
    assert "MAX_AUTONOMOUS_DELETIONS = 80" in guard
    assert "MAX_TEST_FILE_DELETIONS = 20" in guard
    assert '"diff", "--numstat", "origin/main"' in guard
    assert "Autonomous diff is too large for one microtask" in guard
    assert "Autonomous diff removes too much test coverage" in guard


def test_free_opencode_microtasks_are_narrow_and_deterministic():
    script = Path(
        "scripts/run_free_opencode_dev_cycle.ps1"
    ).read_text(encoding="utf-8")

    cycle_one = script.split("        2 {", 1)[0]
    assert '"src/horse_racing_predictions/paper_input.py"' in cycle_one
    assert '"tests/test_future_pipeline.py"' in cycle_one
    assert "duplicate" in cycle_one
    assert "(race_id, horse_id)" in cycle_one
    assert "horse_name is blank or whitespace" in script
    assert "missing_complete_odds_races" in script
    assert "race_id is blank or whitespace" in script
    assert "horse_id is blank or whitespace" in script
    assert "prediction_rows, prediction_races" in script
    assert "paper_input_race_coverage_rate" in script
    assert "safely defers because input status is not ready" in script
    assert "started_at_utc and elapsed_seconds" in script
    assert "predicted_win_probability is non-finite" in script
    assert "confidence is non-finite" in script
    assert '$AllowedCycleFiles = @($microtask.files)' in script
    assert '$outsideAllowed.Count -gt 0' in script
    assert 'Read only the allowed files.' in script
    assert 'Do not run tests or shell commands' in script
    assert "Preserve existing functions and tests" in script
    assert "Prefer surgical additive edits at precise existing locations." in script
    assert "Do not delete more than 20 existing test lines or 80 existing lines total." in script
    assert "Test-AutonomousGuard" in script
    assert "autonomous_guard_rejection_retry=1" in script
    assert "git reset --hard HEAD" in script
    assert "guard-retry-cycle-$Cycle" in script
    assert "Keep the total patch under 80 changed lines and under 10 deleted lines." in script
    assert "Autonomous development safety guard failed after one clean guard retry." in script
    assert "autonomous_guard_rejection_retry_result=success" in script
