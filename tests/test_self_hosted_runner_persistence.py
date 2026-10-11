from pathlib import Path


PERSIST = Path("scripts/ensure_self_hosted_runner_persistence.ps1")
STARTER = Path("scripts/start_self_hosted_runner_if_needed.ps1")
ARCHIVE_WORKFLOW = Path(
    ".github/workflows/jravan-free-trial-pre2025-archive-self-hosted.yml"
)


def test_runner_persistence_repair_is_fail_closed_to_expected_runner_name():
    text = PERSIST.read_text(encoding="utf-8")
    assert 'ExpectedRunnerName = "Office-PC-01-HorseRacingPredictions"' in text
    assert "Refusing persistence change" in text
    assert ".runner" in text
    assert "agentName" in text


def test_runner_persistence_prefers_existing_windows_service():
    text = PERSIST.read_text(encoding="utf-8")
    service_index = text.index('persistence_mode = "windows_service"')
    hkcu_index = text.index('persistence_mode = "hkcu_logon_wrapper"')
    assert service_index < hkcu_index
    assert "Set-Service" in text
    assert "StartupType Automatic" in text
    assert "Start-Service" in text


def test_runner_persistence_fallback_is_current_user_only():
    text = PERSIST.read_text(encoding="utf-8")
    assert "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" in text
    assert "HKLM:" not in text
    assert "schtasks" not in text.lower()
    assert "Register-ScheduledTask" not in text


def test_runner_starter_does_not_launch_duplicate_listener():
    text = STARTER.read_text(encoding="utf-8")
    assert "Runner.Listener.exe" in text
    assert "$alreadyRunning" in text
    assert "if ($alreadyRunning)" in text
    assert "exit 0" in text
    assert "Start-Process" in text


def test_archive_workflow_repairs_persistence_but_does_not_block_archive():
    text = ARCHIVE_WORKFLOW.read_text(encoding="utf-8")
    assert "Repair runner persistence for future reboots" in text
    section = text.split(
        "- name: Repair runner persistence for future reboots",
        maxsplit=1,
    )[1].split(
        "- name: Archive provider-bounded setup data",
        maxsplit=1,
    )[0]
    assert "continue-on-error: true" in section
    assert "ensure_self_hosted_runner_persistence.ps1" in section
    assert "-Repair" in section


def test_archive_workflow_replaces_stale_queued_runs():
    text = ARCHIVE_WORKFLOW.read_text(encoding="utf-8")
    assert "group: jravan-free-trial-pre2025-archive" in text
    assert "cancel-in-progress: true" in text
