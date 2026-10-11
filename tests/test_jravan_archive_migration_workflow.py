from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/jravan-archive-migrate-to-d-self-hosted.yml"
)
SCRIPT = Path("scripts/migrate_jravan_archive_to_d.py")


def test_migration_workflow_requires_d_drive_before_moving():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'Test-Path -LiteralPath "D:\\" -PathType Container' in text
    assert (
        "D drive is unavailable; C-drive archive will remain untouched."
        in text
    )


def test_migration_workflow_deletes_source_only_after_verified_runner():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "migrate_jravan_archive_to_d.py" in text
    assert "--delete-source-after-verify" in text
    assert "SHA-256 verification" in text


def test_migration_workflow_uploads_only_sanitized_report():
    text = WORKFLOW.read_text(encoding="utf-8")
    upload = text.split(
        "- name: Publish sanitized migration report only",
        maxsplit=1,
    )[1]
    assert "jravan_archive_d_drive_migration_report.json" in upload
    assert "bldn_raw.jsonl" not in upload
    assert "race_raw.jsonl" not in upload
    assert "pedigree_snapshot.csv" not in upload
    assert "latest_manifest" not in upload


def test_migration_script_does_not_open_provider_or_generate_tickets():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "JVOpen" not in text
    assert "JVRTOpen" not in text
    assert "ticket" not in text.lower()
    assert "raw_provider_data_uploaded" in text


def test_migration_uses_existing_self_hosted_windows_runner():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows]" in text
    assert "clean: false" in text
    assert "persist-credentials: false" in text
