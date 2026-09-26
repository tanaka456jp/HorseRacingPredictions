from pathlib import Path


def test_smoke_uses_single_current_week_jvopen_without_doctor():
    text = Path(
        "scripts/jravan_trial_smoke.py"
    ).read_text(encoding="utf-8")

    assert 'default="00000000000000"' in text
    assert "default=2" in text
    assert "run_jravan_doctor" not in text
    assert "write_doctor_report" not in text


def test_full_pipeline_does_not_repeat_doctor():
    text = Path(
        "src/horse_racing_predictions/jravan_trial.py"
    ).read_text(encoding="utf-8")

    assert "run_jravan_doctor" not in text
    assert "write_doctor_report" not in text


def test_trial_orchestration_has_runtime_preflight_then_smoke():
    text = Path(
        "scripts/run_jravan_trial.ps1"
    ).read_text(encoding="utf-8")

    assert "check_jravan_runtime.py" in text
    assert "jravan_trial_smoke.py" in text
    assert "jravan_doctor.py" not in text
    assert "[1/2] Bounded current-week RA/SE smoke" in text


def test_bootstrap_clears_stale_jravan_reports():
    text = Path(
        "scripts/bootstrap_jravan_trial.ps1"
    ).read_text(encoding="utf-8")

    assert "Reset-JraVanArtifacts" in text
    assert "jravan_support_bundle.zip" in text
    assert '"artifacts\\jravan_doctor.json"' in text
    assert '"artifacts\\jravan_doctor.json",' not in text.split(
        "function Write-SupportBundle", 1
    )[1].split("foreach", 1)[0]
