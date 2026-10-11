from pathlib import Path


RECOVER = Path("scripts/recover_self_hosted_runner.ps1")
PERSIST = Path("scripts/ensure_self_hosted_runner_persistence.ps1")
STARTER = Path("scripts/start_self_hosted_runner_if_needed.ps1")
LAUNCHER = Path("RUN_HORSERACING_RUNNER_RECOVERY.cmd")


def test_manual_recovery_knows_actual_horseracing_runner_root():
    text = PERSIST.read_text(encoding="utf-8")
    assert (
        'C:\\actions-runner-HorseRacingPredictions\\actions-runner'
        in text
    )


def test_recovery_is_fail_closed_to_expected_registered_runner():
    text = RECOVER.read_text(encoding="utf-8")
    assert (
        'ExpectedRunnerName = "Office-PC-01-HorseRacingPredictions"'
        in text
    )
    assert "agentName" in text
    assert "Runner identity changed after repair" in text
    assert "config.cmd" not in text
    assert "registration_token_requested = $false" in text


def test_recovery_reuses_persistence_and_startup_guards():
    text = RECOVER.read_text(encoding="utf-8")
    assert "ensure_self_hosted_runner_persistence.ps1" in text
    assert "start_self_hosted_runner_if_needed.ps1" in text
    assert "-Repair" in text
    assert "Runner.Listener.exe" in text
    assert "AddSeconds(15)" in text
    assert "github_registration_reused = $true" in text


def test_recovery_does_not_emit_or_request_github_secrets():
    text = RECOVER.read_text(encoding="utf-8").lower()
    forbidden = (
        "registration token",
        "--token",
        "pat",
        "github_token",
        "gh_token",
    )
    assert all(value not in text for value in forbidden)
    assert "secrets_printed = $false" in text


def test_double_click_launcher_calls_only_guarded_recovery_script():
    text = LAUNCHER.read_text(encoding="utf-8")
    assert "recover_self_hosted_runner.ps1" in text
    assert "config.cmd" not in text
    assert "run.cmd" not in text
    assert "pause" in text.lower()


def test_existing_starter_remains_duplicate_listener_safe():
    text = STARTER.read_text(encoding="utf-8")
    assert "$alreadyRunning" in text
    assert "if ($alreadyRunning)" in text
    assert "exit 0" in text


def test_recovery_probes_identity_before_attempting_repair():
    text = RECOVER.read_text(encoding="utf-8")
    probe_index = text.index(
        '& $PersistScript -ExpectedRunnerName $ExpectedRunnerName'
    )
    repair_index = text.index(
        '& $PersistScript -Repair -ExpectedRunnerName $ExpectedRunnerName'
    )
    assert probe_index < repair_index
    assert "Runner identity/root probe failed." in text


def test_persistence_failure_does_not_block_guarded_current_listener_start():
    text = RECOVER.read_text(encoding="utf-8")
    assert "repair_failed_current_start_fallback" in text
    assert "Persistence repair failed; attempting guarded current listener" in text
    assert "& $StartScript -RunnerRoot $runnerRoot" in text
    repair_failure_index = text.index(
        "repair_failed_current_start_fallback"
    )
    starter_index = text.index(
        "& $StartScript -RunnerRoot $runnerRoot"
    )
    assert repair_failure_index < starter_index
