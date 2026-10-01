from pathlib import Path


def _workflow(name: str) -> str:
    return Path(".github/workflows", name).read_text(encoding="utf-8")


def test_time_sensitive_github_workflows_do_not_use_cron_anymore():
    names = (
        "jravan-forward-paper-self-hosted.yml",
        "jravan-realtime-settlement-self-hosted.yml",
        "jravan-incremental-settlement-self-hosted.yml",
        "residual-v12-shadow-reconcile-self-hosted.yml",
    )
    for name in names:
        workflow = _workflow(name)
        assert "schedule:" not in workflow
        assert "run_local_jravan_scheduled_task.ps1" in workflow


def test_local_scheduler_installer_registers_exact_jst_times():
    script = Path(
        "scripts/install_local_jravan_scheduler.ps1"
    ).read_text(encoding="utf-8")

    assert '"09:17"' in script
    assert '"18:17"' in script
    assert '"20:23"' in script
    assert '"21:37"' in script
    assert '"DAILY"' in script
    assert "repeat_minutes = 30" in script
    assert 'duration = "08:31"' in script
    assert '"/RI"' in script
    assert '"/DU"' in script
    assert 'ExpectedComputerName = "DESKTOP-MVV1FD4"' in script
    assert "live_execution_enabled = $false" in script
    assert "HorseRacingPredictionsScheduler" in script
    assert "New-Launcher" in script
    assert "taskCommand.Length -gt 261" in script
    assert "[int]$RepeatMinutes" in script
    assert "if ($RepeatMinutes -gt 0)" in script
    assert '"/MO"' not in script
    assert '"/ET"' not in script
    assert "$null -ne $info.NextRunTime" in script


def test_local_scheduler_wrapper_has_machine_local_lock_and_heartbeat():
    script = Path(
        "scripts/run_local_jravan_scheduled_task.ps1"
    ).read_text(encoding="utf-8")

    assert "jravan_scheduler.lock" in script
    assert "[System.IO.FileShare]::None" in script
    assert "skipped_lock_busy" in script
    assert "local_scheduler_heartbeat" in script
    assert "live_execution_enabled = $false" in script


def test_local_scheduler_install_and_audit_workflows_are_pc1_guarded():
    install = _workflow(
        "install-local-jravan-scheduler-self-hosted.yml"
    )
    audit = _workflow(
        "local-jravan-scheduler-audit-self-hosted.yml"
    )

    assert 'ExpectedComputerName "DESKTOP-MVV1FD4"' in install
    assert 'ExpectedComputerName "DESKTOP-MVV1FD4"' in audit
    assert "schedule:" not in install
    assert "schedule:" not in audit


def test_local_scheduler_audit_handles_never_run_tasks():
    script = Path(
        "scripts/audit_local_jravan_scheduler.ps1"
    ).read_text(encoding="utf-8")

    assert "$null -ne $info.LastRunTime" in script
    assert "$null -ne $info.NextRunTime" in script


def test_local_scheduler_audit_includes_sanitized_pipeline_state():
    script = Path(
        "scripts/audit_local_jravan_scheduler.ps1"
    ).read_text(encoding="utf-8")

    assert "Read-SanitizedJson" in script
    assert "jravan_forward_runner_validation.json" in script
    assert "jravan_realtime_settlement_runner_validation.json" in script
    assert "jravan_incremental_runner_validation.json" in script
    assert "residual_v12_shadow_reconcile_validation.json" in script
    assert "residual_v12_paper_evidence" in script
    assert "sanitized_validations = $sanitizedValidations" in script


def test_local_scheduler_audit_normalizes_never_run_sentinel():
    script = Path(
        "scripts/audit_local_jravan_scheduler.ps1"
    ).read_text(encoding="utf-8")

    assert "$info.LastTaskResult -ne 267011" in script
    assert "has_run = $hasRun" in script
