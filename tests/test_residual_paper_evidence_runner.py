from pathlib import Path


def test_realtime_settlement_refreshes_residual_evidence_gate():
    script = Path(
        "scripts/run_jravan_realtime_settlement_runner.ps1"
    ).read_text(encoding="utf-8")

    assert "report_residual_v12_paper_evidence.py" in script
    assert "residual_evidence_status" in script
    assert "residual_prospective_evaluated_races" in script
    assert "residual_settled_paper_bets" in script
    assert "automatic live promotion: false" in script


def test_incremental_settlement_refreshes_residual_evidence_gate():
    script = Path(
        "scripts/run_jravan_incremental_settlement_runner.ps1"
    ).read_text(encoding="utf-8")

    assert "report_residual_v12_paper_evidence.py" in script
    assert "residual_evidence_status" in script
    assert "residual_prospective_evaluated_races" in script
    assert "residual_settled_paper_bets" in script
    assert "automatic live promotion: false" in script
