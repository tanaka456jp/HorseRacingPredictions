from pathlib import Path


SCRIPT = Path("scripts/reassess_jravan_free_trial_archive.py")
WORKFLOW = Path(
    ".github/workflows/jravan-free-trial-postprocess-self-hosted.yml"
)


def test_reassessment_runner_is_metadata_only():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "reassess_local_archive_manifest" in text
    assert "JVOpen" not in text
    assert "JVRTOpen" not in text
    assert "parse_raw_jsonl" not in text
    assert '"raw_records_read": False' in text


def test_postprocess_workflow_never_opens_provider():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "reassess_jravan_free_trial_archive.py" in text
    assert "build_jravan_pedigree_snapshot.py" in text
    assert "archive_jravan_free_trial_pre2025.py" not in text
    assert "JVOpen" not in text
    assert "JVRTOpen" not in text
    assert "--execute" not in text


def test_postprocess_workflow_uploads_sanitized_reports_only():
    text = WORKFLOW.read_text(encoding="utf-8")
    upload = text.split(
        "- name: Publish sanitized reports only",
        maxsplit=1,
    )[1]
    assert "jravan_archive_reassessment_report.json" in upload
    assert "jravan_pedigree_snapshot_report.json" in upload
    assert "race_raw.jsonl" not in upload
    assert "bldn_raw.jsonl" not in upload
    assert "blod_raw.jsonl" not in upload
    assert "pedigree_snapshot.csv" not in upload
    assert "latest_manifest_v2.json" not in upload


def test_postprocess_workflow_uses_existing_self_hosted_windows_runner():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows]" in text
    assert "clean: false" in text
    assert "persist-credentials: false" in text
