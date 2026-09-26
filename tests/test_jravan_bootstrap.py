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
    assert 'JVDTLab.JVLink' in text


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
