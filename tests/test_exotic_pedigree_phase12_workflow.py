from pathlib import Path


SCRIPT = Path("scripts/evaluate_exotic_pedigree_phase12.py")
WORKFLOW = Path(
    ".github/workflows/exotic-pedigree-phase12-self-hosted.yml"
)


def test_phase12_runner_never_references_combined_or_current_history():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "current_history.csv" not in text
    assert "combined" not in text
    assert "race_raw.jsonl" in text
    assert "pedigree_snapshot.csv" in text
    assert "LOCALAPPDATA" in text


def test_phase12_runner_declares_holdout_untouched():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "2025-2026 untouched" in text
    assert "current_history_csv_used" in text
    assert "False" in text


def test_phase12_workflow_uses_self_hosted_windows_and_uploads_metrics_only():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows]" in text

    upload = text.split(
        "- name: Publish metrics only",
        maxsplit=1,
    )[1]
    assert "artifacts/exotic_pedigree_phase12/summary.json" in upload
    assert "race_raw.jsonl" not in upload
    assert "pedigree_snapshot.csv" not in upload
    assert "JraVanFreeTrialArchive" not in upload


def test_phase12_workflow_does_not_collect_or_purchase_provider_data():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "JVRTOpen" not in text
    assert "JVOpen" not in text
    assert "archive_jravan_free_trial_pre2025.py" not in text
    assert "--execute" not in text
