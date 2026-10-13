from pathlib import Path

WORKFLOW = Path(".github/workflows/jravan-archive-audit-c-self-hosted.yml")
SCRIPT = Path("scripts/audit_jravan_archive_before_copy.py")


def test_c_archive_audit_only_publishes_sanitized_report():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")
    assert "DESKTOP-MVV1FD4" in workflow
    assert "clean: false" in workflow
    assert "jravan_archive_c_inventory_report.json" in workflow
    assert "pedigree_snapshot.csv" not in workflow
    assert "race_raw.jsonl" not in workflow
    assert "JVOpen" not in script
    assert "JVRTOpen" not in script
    assert "unlink(" not in script
    assert "rmtree(" not in script
