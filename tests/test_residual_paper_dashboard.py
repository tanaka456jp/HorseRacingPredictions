from pathlib import Path


def test_dashboard_defaults_to_local_paper_ledger_and_shows_evidence_gate():
    source = Path(
        "src/horse_racing_predictions/dashboard.py"
    ).read_text(encoding="utf-8")

    assert "data/paper/paper_trading.sqlite3" in source
    assert "Residual v12 Paper v1 Evidence Gate" in source
    assert "build_residual_v12_paper_evidence_report" in source
    assert "prospective_evaluated_races" in source
    assert "settled_paper_bets" in source
    assert "max_drawdown_yen" in source
    assert "実賭けへの自動昇格は行いません" in source


def test_dashboard_uses_only_settled_bets_for_realized_roi():
    source = Path(
        "src/horse_racing_predictions/dashboard.py"
    ).read_text(encoding="utf-8")

    assert 'selected["result"].notna()' in source
    assert "settled_stake" in source
    assert "settled_payout" in source
    assert "settled_roi" in source
