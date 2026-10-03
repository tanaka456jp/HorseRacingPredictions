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


def test_dashboard_shows_read_only_paper_risk_monitor():
    source = Path(
        "src/horse_racing_predictions/dashboard.py"
    ).read_text(encoding="utf-8")

    assert "Residual Paper Risk Monitor" in source
    assert "settled_hit_rate" in source
    assert "average_settled_odds" in source
    assert "longest_losing_streak" in source
    assert "current_losing_streak" in source
    assert "recent_roi_windows" in source
    assert "固定済みモデル・EV閾値・賭け金ルールを自動変更しません" in source


def test_dashboard_shows_jravan_forward_runner_heartbeat_section():
    source = Path(
        "src/horse_racing_predictions/dashboard.py"
    ).read_text(encoding="utf-8")

    assert "JRA-VAN Forward Runner Heartbeat" in source
    assert "artifacts/jravan_forward_runner_heartbeat.json" in source
    assert "stage" in source
    assert "updated_at_utc" in source
    assert "forward_paper_executed" in source
    assert "residual_v12_paper_executed" in source
    assert "見つかりません" in source


def test_dashboard_heartbeat_handles_malformed_json():
    source = Path(
        "src/horse_racing_predictions/dashboard.py"
    ).read_text(encoding="utf-8")

    assert "JSONDecodeError" in source
    assert "Heartbeat JSON が不正です" in source


def test_dashboard_heartbeat_handles_stale_timestamp():
    source = Path(
        "src/horse_racing_predictions/dashboard.py"
    ).read_text(encoding="utf-8")

    assert "datetime" in source
    assert "timezone" in source
    assert "1800" in source
    assert "30 分以上更新されていません" in source
