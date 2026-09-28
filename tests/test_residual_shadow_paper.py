from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from horse_racing_predictions.ledger import Ledger
from horse_racing_predictions.residual_shadow_paper import (
    PAPER_MODEL_VERSION,
    run_residual_v12_forward_paper,
)


UTC = timezone.utc


def _prediction_rows(
    *,
    race_id="R1",
    observed=None,
    post=None,
    probabilities=(0.40, 0.10),
    odds=(4.0, 2.0),
):
    observed = observed or datetime(2026, 9, 29, 0, 0, tzinfo=UTC)
    post = post or observed + timedelta(hours=1)
    rows = []
    for index, (probability, decimal_odds) in enumerate(
        zip(probabilities, odds),
        start=1,
    ):
        rows.append({
            "race_id": race_id,
            "race_date": post.date().isoformat(),
            "horse_id": f"{race_id}-{index}",
            "horse_name": f"H{index}",
            "post_position": index,
            "decimal_odds": decimal_odds,
            "observed_at": observed.isoformat(),
            "scheduled_post_time": post.isoformat(),
            "source": "JRA-VAN 0B31",
            "source_reference": f"quote-{index}",
            "market_probability": 0.5,
            "residual_v12_probability": probability,
            "overlay_ratio": 0.1,
            "fixed_gamma": 4.0,
            "model_version": "shadow-market-residual-v12",
        })
    return pd.DataFrame(rows)


def test_residual_v12_paper_records_only_prospective_decisions(tmp_path):
    observed = datetime(2026, 9, 29, 0, 0, tzinfo=UTC)
    post = observed + timedelta(hours=1)
    decision = observed + timedelta(minutes=10)
    ledger_path = tmp_path / "paper.sqlite3"

    summary = run_residual_v12_forward_paper(
        _prediction_rows(observed=observed, post=post),
        ledger_path=ledger_path,
        bankroll_yen=100_000,
        decision_time=decision,
    )

    assert summary["status"] == "prospective_evaluations_recorded"
    assert summary["eligible_rows"] == 2
    assert summary["new_evaluations"] == 2
    assert summary["new_selected_bets"] == 1
    assert summary["new_committed_stake_yen"] == 2_000
    assert summary["min_ev"] == 1.15
    assert summary["fractional_kelly"] == 0.25
    assert summary["max_odds_age_minutes"] == 10
    assert summary["stale_odds_rows"] == 0
    assert summary["prospective_only"] is True
    assert summary["historical_forward_rows_backfilled"] is False
    assert summary["live_execution_enabled"] is False

    ledger = Ledger(ledger_path)
    try:
        rows = ledger.conn.execute(
            "SELECT model_version,stake_yen FROM bets ORDER BY id"
        ).fetchall()
        assert rows == [(PAPER_MODEL_VERSION, 2_000)]
    finally:
        ledger.close()


def test_residual_v12_paper_is_idempotent_for_same_snapshot(tmp_path):
    observed = datetime(2026, 9, 29, 0, 0, tzinfo=UTC)
    post = observed + timedelta(hours=1)
    decision = observed + timedelta(minutes=10)
    ledger_path = tmp_path / "paper.sqlite3"
    predictions = _prediction_rows(observed=observed, post=post)

    first = run_residual_v12_forward_paper(
        predictions,
        ledger_path=ledger_path,
        decision_time=decision,
    )
    second = run_residual_v12_forward_paper(
        predictions,
        ledger_path=ledger_path,
        decision_time=decision,
    )

    assert first["new_evaluations"] == 2
    assert second["new_evaluations"] == 0
    assert second["duplicate_evaluations"] == 2
    assert second["performance"]["selected_bets"] == 1


def test_residual_v12_paper_does_not_backfill_past_races(tmp_path):
    observed = datetime(2026, 9, 29, 0, 0, tzinfo=UTC)
    post = observed + timedelta(hours=1)

    summary = run_residual_v12_forward_paper(
        _prediction_rows(observed=observed, post=post),
        ledger_path=tmp_path / "paper.sqlite3",
        decision_time=post + timedelta(minutes=1),
    )

    assert summary["status"] == "no_eligible_future_predictions"
    assert summary["new_evaluations"] == 0
    assert summary["new_selected_bets"] == 0
    assert summary["performance"]["selected_bets"] == 0


def test_residual_v12_paper_rejects_gamma_change(tmp_path):
    predictions = _prediction_rows()
    predictions["fixed_gamma"] = 2.0

    with pytest.raises(ValueError, match="frozen gamma=4.0"):
        run_residual_v12_forward_paper(
            predictions,
            ledger_path=tmp_path / "paper.sqlite3",
            decision_time=datetime(2026, 9, 29, 0, 10, tzinfo=UTC),
        )


def test_residual_v12_paper_restores_race_exposure_between_runs(tmp_path):
    observed = datetime(2026, 9, 29, 0, 0, tzinfo=UTC)
    post = observed + timedelta(hours=1)
    ledger_path = tmp_path / "paper.sqlite3"

    first = _prediction_rows(
        observed=observed,
        post=post,
        probabilities=(0.40,),
        odds=(4.0,),
    )
    run_residual_v12_forward_paper(
        first,
        ledger_path=ledger_path,
        bankroll_yen=100_000,
        decision_time=observed + timedelta(minutes=5),
    )

    later = _prediction_rows(
        observed=observed + timedelta(minutes=10),
        post=post,
        probabilities=(0.40,),
        odds=(4.0,),
    )
    later["horse_id"] = "R1-2"
    later["horse_name"] = "H2"
    later["post_position"] = 2

    summary = run_residual_v12_forward_paper(
        later,
        ledger_path=ledger_path,
        bankroll_yen=100_000,
        decision_time=observed + timedelta(minutes=15),
    )

    assert summary["new_evaluations"] == 1
    assert summary["new_selected_bets"] == 0
    assert summary["performance"]["selected_bets"] == 1


def test_residual_v12_paper_performance_uses_settled_final_payout(tmp_path):
    observed = datetime(2026, 9, 29, 0, 0, tzinfo=UTC)
    post = observed + timedelta(hours=1)
    ledger_path = tmp_path / "paper.sqlite3"

    run_residual_v12_forward_paper(
        _prediction_rows(
            observed=observed,
            post=post,
            probabilities=(0.40,),
            odds=(4.0,),
        ),
        ledger_path=ledger_path,
        bankroll_yen=100_000,
        decision_time=observed + timedelta(minutes=10),
    )

    ledger = Ledger(ledger_path)
    try:
        bet_id, stake = ledger.conn.execute(
            "SELECT id,stake_yen FROM bets WHERE model_version=?",
            (PAPER_MODEL_VERSION,),
        ).fetchone()
        ledger.record_paper_settlement(
            bet_id=bet_id,
            race_id="R1",
            horse_id="R1-1",
            finish_position=1,
            final_win_odds=3.0,
            won=True,
            payout_yen=stake * 3,
            source="test-final",
        )
    finally:
        ledger.close()

    summary = run_residual_v12_forward_paper(
        _prediction_rows(
            observed=observed,
            post=post,
            probabilities=(0.40,),
            odds=(4.0,),
        ),
        ledger_path=ledger_path,
        decision_time=post + timedelta(minutes=1),
    )

    performance = summary["performance"]
    assert performance["settled_bets"] == 1
    assert performance["settled_stake_yen"] == 2_000
    assert performance["payout_yen"] == 6_000
    assert performance["profit_yen"] == 4_000
    assert performance["roi"] == 2.0
    assert performance["max_drawdown_yen"] == 0


def test_residual_v12_paper_rejects_stale_prerace_odds(tmp_path):
    observed = datetime(2026, 9, 29, 0, 0, tzinfo=UTC)
    post = observed + timedelta(hours=1)

    summary = run_residual_v12_forward_paper(
        _prediction_rows(observed=observed, post=post),
        ledger_path=tmp_path / "paper.sqlite3",
        bankroll_yen=100_000,
        decision_time=observed + timedelta(minutes=11),
    )

    assert summary["status"] == "no_eligible_future_predictions"
    assert summary["eligible_rows"] == 0
    assert summary["stale_odds_rows"] == 2
    assert summary["new_evaluations"] == 0
    assert summary["new_selected_bets"] == 0
    assert summary["max_odds_age_minutes"] == 10
    assert summary["performance"]["selected_bets"] == 0
