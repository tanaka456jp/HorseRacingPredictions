from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/jravan-free-trial-pre2025-archive-self-hosted.yml"
)


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_archive_workflow_uses_latest_single_run_concurrency():
    text = _text()
    assert "group: jravan-free-trial-pre2025-archive" in text
    assert "cancel-in-progress: true" in text


def test_archive_workflow_repairs_runner_persistence_non_blocking():
    text = _text()
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


def test_archive_workflow_builds_pedigree_snapshot_after_raw_archive():
    text = _text()
    archive_index = text.index(
        "- name: Archive provider-bounded setup data"
    )
    snapshot_index = text.index(
        "- name: Build private pedigree snapshot from archived BLOD/BLDN"
    )
    publish_index = text.index(
        "- name: Publish sanitized manifest only"
    )
    assert archive_index < snapshot_index < publish_index
    assert "scripts\\build_jravan_pedigree_snapshot.py" in text
    assert "artifacts\\jravan_pedigree_snapshot_report.json" in text


def test_archive_artifact_never_contains_raw_provider_or_private_snapshot():
    text = _text()
    upload = text.split(
        "- name: Publish sanitized manifest only",
        maxsplit=1,
    )[1].split(
        "- name: Fail if archive was incomplete",
        maxsplit=1,
    )[0]
    assert "jravan_free_trial_archive_manifest.json" in upload
    assert "jravan_pedigree_snapshot_report.json" in upload
    assert "race_raw.jsonl" not in upload
    assert "bldn_raw.jsonl" not in upload
    assert "blod_raw.jsonl" not in upload
    assert "pedigree_snapshot.csv" not in upload
    assert "JraVanFreeTrialArchive" not in upload


def test_archive_workflow_reports_snapshot_failure_without_deleting_raw():
    text = _text()
    assert (
        "JRA-VAN raw archive completed, but pedigree snapshot "
        "post-processing failed."
    ) in text
    assert "raw archive parts remain preserved locally" in text
