from pathlib import Path

from horse_racing_predictions.jravan_storage_health import (
    DEFAULT_C_WARN_FREE_BYTES,
    DEFAULT_MIN_D_FREE_BYTES,
)


WORKFLOW = Path(".github/workflows/jravan-storage-health-self-hosted.yml")
ARCHIVE_SCRIPT = Path("scripts/archive_jravan_free_trial_pre2025.py")


def test_storage_thresholds_keep_large_archive_off_system_drive():
    assert DEFAULT_MIN_D_FREE_BYTES == 10 * 1024 ** 3
    assert DEFAULT_C_WARN_FREE_BYTES == 15 * 1024 ** 3


def test_storage_health_workflow_is_self_hosted_and_sanitized():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows]" in text
    assert "report_jravan_storage_health.py" in text
    upload = text.split(
        "- name: Publish sanitized storage report",
        maxsplit=1,
    )[1]
    assert "jravan_storage_health.json" in upload
    assert "race_raw.jsonl" not in upload
    assert "bldn_raw.jsonl" not in upload
    assert "pedigree_snapshot.csv" not in upload


def test_archive_script_requires_storage_guard_before_default_root_use():
    text = ARCHIVE_SCRIPT.read_text(encoding="utf-8")
    assert "assert_jravan_archive_storage_ready()" in text
    assert (
        text.index("assert_jravan_archive_storage_ready()")
        < text.index("archive_root = default_archive_root()")
    )
    assert "refusing large JRA-VAN archive acquisition outside D drive" in text


def test_storage_health_workflow_does_not_open_provider():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "JVOpen" not in text
    assert "JVRTOpen" not in text
    assert "archive_jravan_free_trial_pre2025.py" not in text
