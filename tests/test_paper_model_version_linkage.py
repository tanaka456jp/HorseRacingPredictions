"""Synthetic-only regression for immutable Paper model attribution.

No real race, odds, or protected holdout data is accessed.
"""
from datetime import datetime, timedelta, timezone

import pytest

from horse_racing_predictions.domain import BetDecision, HorsePrediction
from horse_racing_predictions.ledger import Ledger
from horse_racing_predictions.snapshots import PreRaceOddsSnapshot


def _linked_prediction(ledger):
    observed = datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc)
    prediction = HorsePrediction(
        race_id="SYNTH-R1",
        horse_id="SYNTH-R1-1",
        horse_name="Synthetic horse",
        predicted_win_probability=0.3,
        decimal_odds=4.0,
        confidence=0.7,
        model_version="model-A",
        predicted_at=observed + timedelta(minutes=1),
    )
    snapshot = PreRaceOddsSnapshot(
        race_id=prediction.race_id,
        horse_id=prediction.horse_id,
        horse_name=prediction.horse_name,
        decimal_odds=prediction.decimal_odds,
        observed_at=observed,
        scheduled_post_time=observed + timedelta(hours=1),
        source="synthetic-fixture",
    )
    return ledger.record_paper_prediction(prediction, snapshot)


def _decision(model_version):
    return BetDecision(
        race_id="SYNTH-R1",
        horse_id="SYNTH-R1-1",
        horse_name="Synthetic horse",
        bet_type="WIN",
        stake_yen=100,
        decimal_odds=4.0,
        expected_return_multiple=1.2,
        edge=0.2,
        reason="synthetic regression only",
        model_version=model_version,
    )


def test_paper_bet_rejects_mismatched_prediction_model_atomically():
    ledger = Ledger(":memory:")
    try:
        prediction_id = _linked_prediction(ledger)
        with pytest.raises(ValueError, match="model_version"):
            ledger.record_paper_bet(_decision("model-B"), prediction_id)
        assert ledger.conn.execute("SELECT COUNT(*) FROM bets").fetchone()[0] == 0
        assert ledger.conn.execute(
            "SELECT COUNT(*) FROM paper_bet_evidence"
        ).fetchone()[0] == 0
    finally:
        ledger.close()


def test_paper_bet_accepts_matching_prediction_model():
    ledger = Ledger(":memory:")
    try:
        prediction_id = _linked_prediction(ledger)
        bet_id = ledger.record_paper_bet(_decision("model-A"), prediction_id)
        assert ledger.conn.execute(
            "SELECT model_version FROM bets WHERE id=?", (bet_id,)
        ).fetchone()[0] == "model-A"
        assert ledger.paper_bet_evidence(bet_id)["prediction_id"] == prediction_id
    finally:
        ledger.close()
