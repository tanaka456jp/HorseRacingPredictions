from pathlib import Path


SHARED_GROUP = "group: horse-racing-jravan-self-hosted"


def _workflow(name: str) -> str:
    return Path(".github/workflows", name).read_text(encoding="utf-8")


def test_time_sensitive_jravan_workflows_are_manual_or_marker_only():
    names = (
        "jravan-forward-paper-self-hosted.yml",
        "jravan-incremental-settlement-self-hosted.yml",
        "jravan-realtime-settlement-self-hosted.yml",
        "residual-v12-shadow-reconcile-self-hosted.yml",
    )
    for name in names:
        workflow = _workflow(name)
        assert "schedule:" not in workflow
        assert "workflow_dispatch:" in workflow
        assert "push:" in workflow
        assert "run_local_jravan_scheduled_task.ps1" in workflow


def test_github_jravan_workflows_keep_shared_concurrency_for_manual_runs():
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


def test_exact_times_are_owned_by_pc1_local_scheduler():
    script = Path(
        "scripts/install_local_jravan_scheduler.ps1"
    ).read_text(encoding="utf-8")

    assert '"09:17"' in script
    assert '"17:47"' in script
    assert '"18:17"' in script
    assert '"20:23"' in script
    assert '"21:37"' in script
    assert "modifier = 30" in script
    assert "github_cron_is_primary = $false" in script
    assert "local_scheduler_is_primary = $true" in script
