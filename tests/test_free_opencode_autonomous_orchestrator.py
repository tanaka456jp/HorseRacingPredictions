from pathlib import Path


def test_free_opencode_autonomous_workflow_is_pc1_marker_triggered():
    workflow = Path(
        ".github/workflows/free-opencode-autonomous-dev-12h-self-hosted.yml"
    ).read_text(encoding="utf-8")

    assert "schedule:" not in workflow
    assert "workflow_dispatch:" in workflow
    assert "research/free_opencode_autonomous_dev_12h_request.txt" in workflow
    assert "runs-on: [self-hosted, Windows]" in workflow
    assert "timeout-minutes: 780" in workflow
    assert "persist-credentials: false" in workflow
    assert "cancel-in-progress: true" in workflow
    assert "install_free_opencode_cli.ps1" in workflow
    assert "smoke_free_opencode_ollama.ps1" in workflow
    assert "run_free_opencode_dev_12h.ps1" in workflow
    assert 'Model "ollama/qwen3:8b"' in workflow
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
    assert "run --auto --model $escapedModel" in script
    assert '"permission": {' in script
    assert '"external_directory": "deny"' in script
    assert '"webfetch": "deny"' in script
    assert '"websearch": "deny"' in script
    assert '"question": "deny"' in script
    assert '"doom_loop": "deny"' in script
    assert '"git commit *": "deny"' in script
    assert '"git push *": "deny"' in script
    assert '"gh *": "deny"' in script
    assert "codex.exe" not in script.lower()
    assert "verify_autonomous_dev_guard.py" in script
    assert "python -m pytest -q" in script
    assert "gh pr create" in script
    assert "gh pr merge" in script
    assert "auto/free-opencode-dev-" in script
    assert "origin/main" in script


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
    assert "Get-FileHash" in script
    assert "OpenCode local-only configuration was modified" in script
    assert "new-cycle-$Cycle-retry" in script
    assert "produced no repository changes after one retry" in script


def test_free_opencode_12h_summary_proves_free_only_execution():
    script = Path(
        "scripts/run_free_opencode_dev_12h.ps1"
    ).read_text(encoding="utf-8")

    assert "orchestrator.lock" in script
    assert 'Join-Path $ControlRoot "STOP"' in script
    assert 'provider = "ollama_local"' in script
    assert "paid_provider_used = $false" in script
    assert "api_key_used = $false" in script
    assert "codex_used = $false" in script
    assert "live_execution_enabled = $false" in script
    assert "completed_with_failures" in script
    assert "[int]$MaxConsecutiveFailures = 2" in script
    assert "consecutive_failures = $consecutiveFailures" in script
    assert "failed_fast = $failedFast" in script
    assert "GITHUB_STEP_SUMMARY" in script
    assert "Stopping after $consecutiveFailures consecutive failed cycles." in script


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
