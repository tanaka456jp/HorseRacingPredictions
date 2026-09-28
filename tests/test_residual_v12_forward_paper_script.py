from pathlib import Path


def test_residual_forward_paper_script_does_not_reconcile_results():
    script = Path("scripts/run_residual_v12_forward_paper.py").read_text(
        encoding="utf-8"
    )

    assert "run_residual_v12_forward_paper" in script
    assert "build_residual_v12_shadow_predictions" in script
    assert "capture_shadow_results_0b12" not in script
    assert '"result_reconciliation_executed": False' in script
    assert '"live_execution_enabled": False' in script
