from pathlib import Path


def test_autonomous_guard_freezes_strategy_and_holdout_boundaries():
    guard = Path(
        "scripts/verify_autonomous_dev_guard.py"
    ).read_text(encoding="utf-8")

    assert '"PAPER_MIN_EV": 1.15' in guard
    assert '"PAPER_MIN_PROBABILITY": 0.03' in guard
    assert '"PAPER_FRACTIONAL_KELLY": 0.25' in guard
    assert '"MIN_PROSPECTIVE_EVALUATED_RACES": 500' in guard
    assert '"MIN_SETTLED_PAPER_BETS": 200' in guard
    assert '"FIXED_GAMMA": 4.0' in guard
    assert '"holdout" in lower' in guard
    assert "live_execution_enabled" in guard


def test_autonomous_cycle_uses_dedicated_clone_and_chatgpt_login_only():
    script = Path(
        "scripts/run_autonomous_dev_cycle.ps1"
    ).read_text(encoding="utf-8")

    assert "HorseRacingPredictionsAutonomousDev" in script
    assert "gh repo clone" in script
    assert "codex.exe" in script
    assert "login status" in script
    assert "Remove-Item Env:OPENAI_API_KEY" in script
    assert "exec --full-auto" in script
    assert "verify_autonomous_dev_guard.py" in script
    assert "python -m pytest -q" in script
    assert "gh pr create" in script
    assert "gh pr merge" in script
    assert "origin/main" in script


def test_autonomous_prompt_preserves_frozen_boundaries():
    script = Path(
        "scripts/run_autonomous_dev_cycle.ps1"
    ).read_text(encoding="utf-8")

    assert "gamma=4.0" in script
    assert "EV=1.15" in script
    assert "min probability=0.03" in script
    assert "fractional Kelly=0.25" in script
    assert "Evidence Gate=500 evaluated races + 200 settled Paper bets" in script
    assert "Never enable live/real-money betting" in script
    assert "Never reuse/rerun the opened 2025-2026 holdout" in script


def test_autonomous_12h_workflow_is_self_hosted_and_not_scheduled():
    workflow = Path(
        ".github/workflows/autonomous-dev-12h-self-hosted.yml"
    ).read_text(encoding="utf-8")

    assert "schedule:" not in workflow
    assert "workflow_dispatch:" in workflow
    assert "research/autonomous_dev_12h_request.txt" in workflow
    assert "runs-on: [self-hosted, Windows]" in workflow
    assert "timeout-minutes: 780" in workflow
    assert "persist-credentials: false" in workflow
    assert "run_autonomous_dev_12h.ps1" in workflow


def test_autonomous_runner_has_lock_stop_and_auth_preflight():
    script = Path(
        "scripts/run_autonomous_dev_12h.ps1"
    ).read_text(encoding="utf-8")

    assert "orchestrator.lock" in script
    assert 'Join-Path $ControlRoot "STOP"' in script
    assert "CODEX_NOT_AUTHENTICATED" in script
    assert "Remove-Item Env:OPENAI_API_KEY" in script
    assert "api_key_used = $false" in script
    assert "live_execution_enabled = $false" in script
