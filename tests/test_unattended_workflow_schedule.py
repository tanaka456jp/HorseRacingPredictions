from pathlib import Path


SHARED_GROUP = "group: horse-racing-jravan-self-hosted"


def _workflow(name: str) -> str:
    return Path(".github/workflows", name).read_text(encoding="utf-8")


def test_unattended_forward_schedule_covers_daily_jst_race_hours():
    workflow = _workflow("jravan-forward-paper-self-hosted.yml")

    assert '- cron: "17 0-8 * * *"' in workflow
    assert '- cron: "47 0-8 * * *"' in workflow
    assert "09:17/09:47-17:17/17:47" in workflow
    assert SHARED_GROUP in workflow
    assert "cancel-in-progress: false" in workflow


def test_unattended_settlement_and_history_schedule():
    realtime = _workflow("jravan-realtime-settlement-self-hosted.yml")
    incremental = _workflow("jravan-incremental-settlement-self-hosted.yml")
    reconcile = _workflow("residual-v12-shadow-reconcile-self-hosted.yml")

    assert '- cron: "17 9 * * *"' in realtime
    assert "18:17 JST" in realtime
    assert '- cron: "23 11 * * *"' in incremental
    assert "20:23 JST" in incremental
    assert '- cron: "37 12 * * *"' in reconcile
    assert "21:37 JST" in reconcile


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


def test_forward_schedule_avoids_top_of_hour_and_has_redundant_attempts():
    workflow = _workflow("jravan-forward-paper-self-hosted.yml")

    assert 'cron: "0 ' not in workflow
    assert workflow.count("- cron:") == 2
    assert "model/race lock" in workflow


def test_settlement_schedules_avoid_top_of_hour():
    names = (
        "jravan-realtime-settlement-self-hosted.yml",
        "jravan-incremental-settlement-self-hosted.yml",
        "residual-v12-shadow-reconcile-self-hosted.yml",
    )
    for name in names:
        workflow = _workflow(name)
        assert 'cron: "0 ' not in workflow
