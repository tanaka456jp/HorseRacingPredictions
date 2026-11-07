"""Expired-trial popup-loop prevention, using only fake/synthetic objects."""
from pathlib import Path

import pytest

from horse_racing_predictions.jravan import (
    JraVanUnavailableError,
    JvLinkClient,
    _default_com_factory,
)
from horse_racing_predictions import jravan_runtime


def test_real_jvlink_factory_disabled_before_com_dispatch(monkeypatch):
    import horse_racing_predictions.jravan as module
    monkeypatch.setattr(module.platform, "system", lambda: "Windows")
    with pytest.raises(JraVanUnavailableError, match="TRIAL_EXPIRED_LIVE_COM_DISABLED"):
        _default_com_factory()
    with pytest.raises(JraVanUnavailableError, match="TRIAL_EXPIRED_LIVE_COM_DISABLED"):
        JvLinkClient()


def test_trial_expired_runtime_report_does_not_inspect_windows_com(monkeypatch):
    def forbidden_probe():
        raise AssertionError("must never probe registry or Dispatch JV-Link")

    monkeypatch.setattr(jravan_runtime, "_probe_registry_views", forbidden_probe)
    report = jravan_runtime.inspect_jravan_runtime()
    assert report.status == "disabled_trial_expired"
    assert not report.com_created
    assert report.error == "JRA_VAN_TRIAL_EXPIRED_LIVE_COM_DISABLED"


def test_windows_scheduled_wrapper_never_launches_child_after_expiry():
    source = Path("scripts/run_local_jravan_scheduled_task.ps1").read_text(
        encoding="utf-8"
    )
    assert source.index('Write-Heartbeat -Status "disabled_trial_expired"') < source.index(
        "& $powershellExe @childArgs"
    )
    assert source.index('Write-Host "SKIPPED: JRA-VAN trial expired') < source.index(
        "& $powershellExe @childArgs"
    )
    assert "exit 0\n\n$lockStream" in source
    assert "jravan_scheduler.lock" in source


def test_expired_trial_installer_cannot_recreate_tasks():
    source = Path("scripts/install_local_jravan_scheduler.ps1").read_text(
        encoding="utf-8"
    )
    assert source.index('throw "JRA_VAN_TRIAL_EXPIRED_SCHEDULER_INSTALL_DISABLED"') < source.index(
        "New-Launcher"
    )
    assert "HorseRacingPredictions-ForwardPaper" in source


def test_exact_name_disable_script_is_manually_opt_in():
    source = Path("scripts/disable_expired_jravan_scheduled_tasks_local.ps1").read_text(
        encoding="utf-8"
    )
    assert source.count('"HorseRacingPredictions-') == 4
    assert "[switch]$Disable" in source
    assert "[switch]$StopRunning" in source
    assert "if ($Disable)" in source
    assert "Disable-ScheduledTask -TaskName $taskName" in source
    assert "Stop-ScheduledTask -TaskName $taskName" in source
    assert "Unregister-ScheduledTask" not in source
    assert "Stop-Process" not in source
    assert "Remove-Item" not in source
    assert "webbrowser" not in source
