from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/jravan-pedigree-snapshot-self-hosted.yml"
)


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_pedigree_snapshot_workflow_uses_self_hosted_windows_runner():
    text = _text()
    assert "runs-on: [self-hosted, Windows]" in text


def test_pedigree_snapshot_workflow_uploads_only_sanitized_report():
    text = _text()
    upload = text.split(
        "- name: Publish aggregate coverage only",
        maxsplit=1,
    )[1]
    assert "artifacts/jravan_pedigree_snapshot_report.json" in upload
    assert "pedigree_snapshot.csv" not in upload
    assert "JraVanFreeTrialArchive" not in upload
    assert "raw.jsonl" not in upload


def test_pedigree_snapshot_workflow_does_not_collect_provider_data():
    text = _text()
    assert "archive_jravan_free_trial_pre2025.py" not in text
    assert "JVRTOpen" not in text
    assert "--execute" not in text
