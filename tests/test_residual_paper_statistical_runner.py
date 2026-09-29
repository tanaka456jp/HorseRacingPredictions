from pathlib import Path


def _source(name: str) -> str:
    return Path("scripts", name).read_text(encoding="utf-8")


def test_realtime_settlement_publishes_statistical_roi_evidence():
    source = _source("run_jravan_realtime_settlement_runner.ps1")
    assert "residual_statistical_positive_roi_evidence" in source
    assert "residual_roi_ci_lower" in source
    assert "residual_roi_ci_upper" in source
    assert "residual_bootstrap_positive_roi_fraction" in source


def test_incremental_settlement_publishes_statistical_roi_evidence():
    source = _source("run_jravan_incremental_settlement_runner.ps1")
    assert "residual_statistical_positive_roi_evidence" in source
    assert "residual_roi_ci_lower" in source
    assert "residual_roi_ci_upper" in source
    assert "residual_bootstrap_positive_roi_fraction" in source
