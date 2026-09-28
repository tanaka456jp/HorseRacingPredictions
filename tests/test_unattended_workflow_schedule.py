from pathlib import Path


SHARED_GROUP = "group: horse-racing-jravan-self-hosted"


def _workflow(name: str) -> str:
    return Path(".github/workflows", name).read_text(encoding="utf-8")


def test_unattended_forward_schedule_covers_daily_jst_race_hours():
    workflow = _workflow("jravan-forward-paper-self-hosted.yml")

    assert '- cron: "0 0-8 * * *"' in workflow
    assert "09:00-17:00 JST" in workflow
    assert SHARED_GROUP in workflow
    assert "cancel-in-progress: false" in workflow


def test_unattended_settlement_and_history_schedule():
    realtime = _workflow("jravan-realtime-settlement-self-hosted.yml")
    incremental = _workflow("jravan-incremental-settlement-self-hosted.yml")
    reconcile = _workflow("residual-v12-shadow-reconcile-self-hosted.yml")

    assert '- cron: "0 9 * * *"' in realtime
    assert "18:00 JST" in realtime
    assert '- cron: "0 11 * * *"' in incremental
    assert "20:00 JST" in incremental
    assert '- cron: "30 12 * * *"' in reconcile
    assert "21:30 JST" in reconcile


def test_jravan_local_state_workflows_are_serialized():
    names = (
        "jravan-forward-paper-self-hosted.yml",
        "jravan-incremental-settlement-self-hosted.yml",
        "jravan-realtime-settlement-self-hosted.yml",
        "jravan-resume-self-hosted.yml",
        "residual-v12-forward-shadow-self-hosted.yml",
        "residual-v12-shadow-reconcile-self-hosted.yml",
    )
    for name in names:
        workflow = _workflow(name)
        assert SHARED_GROUP in workflow
        assert "cancel-in-progress: false" in workflow
