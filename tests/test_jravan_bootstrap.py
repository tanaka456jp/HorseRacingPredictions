from pathlib import Path


def test_jravan_bootstrap_is_location_independent_and_isolated():
    text = Path(
        "scripts/bootstrap_jravan_trial.ps1"
    ).read_text(encoding="utf-8")

    assert "$PSScriptRoot" in text
    assert "Set-Location $ProjectRoot" in text
    assert ".venv-jravan" in text
    assert 'pip install -e ".[research]"' in text
    assert "requirements-jravan.txt" in text
    assert "check_jravan_runtime.py" in text


def test_jravan_bootstrap_packages_support_bundle():
    text = Path(
        "scripts/bootstrap_jravan_trial.ps1"
    ).read_text(encoding="utf-8")

    assert "Write-SupportBundle" in text
    assert "Compress-Archive" in text
    assert "jravan_support_bundle.zip" in text
    assert "jravan_doctor.json" in text


def test_double_click_launchers_delegate_to_bootstrap():
    smoke = Path(
        "RUN_JRAVAN_SMOKE.cmd"
    ).read_text(encoding="utf-8")
    full = Path(
        "RUN_JRAVAN_FULL.cmd"
    ).read_text(encoding="utf-8")

    assert "bootstrap_jravan_trial.ps1" in smoke
    assert "bootstrap_jravan_trial.ps1" in full
    assert "-Full" not in smoke
    assert "-Full" in full


def test_jravan_requirements_use_real_lines():
    text = Path("requirements-jravan.txt").read_text(encoding="utf-8")
    assert "\\n" not in text
    assert text.splitlines() == [
        "pywin32>=311",
        "kagglehub",
    ]


def test_bootstrap_uses_script_for_runtime_check():
    text = Path(
        "scripts/bootstrap_jravan_trial.ps1"
    ).read_text(encoding="utf-8")

    assert "check_jravan_runtime.py" in text
    assert "struct.calcsize" not in text
    assert 'Dispatch("JVDTLab.JVLink")' not in text


def test_runtime_check_delegates_to_registration_doctor():
    text = Path(
        "scripts/check_jravan_runtime.py"
    ).read_text(encoding="utf-8")
    runtime = Path(
        "src/horse_racing_predictions/jravan_runtime.py"
    ).read_text(encoding="utf-8")

    assert "inspect_jravan_runtime" in text
    assert "write_runtime_report" in text
    assert "struct.calcsize" in runtime
    assert 'Dispatch(PROGID)' in runtime
