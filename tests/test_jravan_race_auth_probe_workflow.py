from pathlib import Path


SCRIPT = Path("scripts/probe_jravan_free_trial_race_auth.py")
WORKFLOW = Path(
    ".github/workflows/jravan-race-auth-probe-self-hosted.yml"
)


def test_race_auth_probe_never_reads_raw_records():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "iter_records" not in text
    assert "JVGets" not in text
    assert '"raw_records_read": False' in text
    assert "paid_action_authorized" in text
    assert "2025-2026 untouched" in text


def test_race_auth_probe_uses_unknown_and_provider_bounded_window():
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'sid: str = "UNKNOWN"' in text
    assert "DEFAULT_ARCHIVE_RANGE" in text
    assert 'probe_dataspec("HOSN")' in text
    assert 'probe_dataspec("RACE")' in text


def test_race_auth_probe_workflow_is_self_hosted_and_sanitized():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows]" in text
    assert "run_jravan_race_auth_probe_bounded.ps1" in text
    assert "-TimeoutSeconds 90" in text
    assert "-ReportPath" in text
    upload = text.split(
        "- name: Publish sanitized probe only",
        maxsplit=1,
    )[1]
    assert "jravan_race_auth_probe.json" in upload
    assert "race_raw.jsonl" not in upload
    assert "bldn_raw.jsonl" not in upload
    assert "pedigree_snapshot.csv" not in upload


def test_race_auth_probe_workflow_is_valid_multiline_yaml_source():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "\\n" not in text
    assert text.startswith("name: JRA-VAN Free Trial RACE Auth Probe\n")
