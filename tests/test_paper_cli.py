from horse_racing_predictions.config import StrategyConfig
from horse_racing_predictions.paper_cli import run_paper_csv


def _write_csv(path):
    path.write_text(
        "race_id,horse_id,horse_name,predicted_win_probability,"
        "decimal_odds,confidence,model_version,observed_at,predicted_at,"
        "scheduled_post_time,source_reference\\n"
        "R1,H1,ALPHA,0.50,4.0,1.0,v1,"
        "2026-10-11T06:20:00+00:00,"
        "2026-10-11T06:21:00+00:00,"
        "2026-10-11T06:30:00+00:00,q1\\n"
        "R1,H2,BRAVO,0.50,4.0,1.0,v1,"
        "2026-10-11T06:20:30+00:00,"
        "2026-10-11T06:21:30+00:00,"
        "2026-10-11T06:30:00+00:00,q2\\n"
        "R2,H3,CHARLIE,0.50,4.0,1.0,v1,"
        "2026-10-11T06:50:00+00:00,"
        "2026-10-11T06:51:00+00:00,"
        "2026-10-11T07:00:00+00:00,q3\\n",
        encoding="utf-8",
    )


def test_run_paper_csv_records_all_evaluations_and_risk_caps(tmp_path):
    input_path = tmp_path / "paper.csv"
    ledger_path = tmp_path / "paper.sqlite3"
    _write_csv(input_path)

    result = run_paper_csv(
        input_path,
        ledger_path,
        bankroll_yen=100_000,
        config=StrategyConfig(
            min_ev=1.05,
            min_probability=0.01,
            min_confidence=0.0,
            fractional_kelly=1.0,
            max_race_fraction=0.02,
            max_day_fraction=0.05,
            max_bet_yen=100_000,
        ),
    )

    assert len(result["evaluations"]) == 3
    stakes = [
        row["stake_yen"]
        for row in result["evaluations"]
    ]
    assert stakes == [2_000, 0, 1_900]
    assert result["committed_stake_yen"] == 3_900
    assert result["remaining_uncommitted_bankroll_yen"] == 96_100
    assert ledger_path.exists()


def test_paper_csv_missing_required_columns_fails(tmp_path):
    input_path = tmp_path / "bad.csv"
    input_path.write_text(
        "race_id,horse_id\\nR1,H1\\n",
        encoding="utf-8",
    )

    try:
        run_paper_csv(
            input_path,
            tmp_path / "paper.sqlite3",
            bankroll_yen=100_000,
        )
    except ValueError as exc:
        assert "missing paper CSV columns" in str(exc)
    else:
        raise AssertionError("expected missing-column failure")
