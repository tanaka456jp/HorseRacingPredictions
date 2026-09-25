from datetime import datetime, timedelta, timezone

import pytest

from horse_racing_predictions.domain import HorsePrediction
from horse_racing_predictions.ledger import Ledger
from horse_racing_predictions.snapshots import (
    PreRaceOddsSnapshot,
    validate_prediction_evidence,
)


UTC = timezone.utc


def _snapshot(**overrides):
    post = datetime(2026, 10, 3, 6, 30, tzinfo=UTC)
    values = {
        "race_id": "202610030811",
        "horse_id": "H07",
        "horse_name": "TEST HORSE",
        "decimal_odds": 6.4,
        "observed_at": post - timedelta(minutes=10),
        "scheduled_post_time": post,
        "source": "paper-test-provider",
        "source_reference": "quote-001",
    }
    values.update(overrides)
    return PreRaceOddsSnapshot(**values)


def _prediction(snapshot, **overrides):
    values = {
        "race_id": snapshot.race_id,
        "horse_id": snapshot.horse_id,
        "horse_name": snapshot.horse_name,
        "predicted_win_probability": 0.20,
        "decimal_odds": snapshot.decimal_odds,
        "confidence": 0.80,
        "model_version": "paper-v1",
        "predicted_at": snapshot.observed_at + timedelta(minutes=1),
    }
    values.update(overrides)
    return HorsePrediction(**values)


def test_snapshot_requires_timezone_aware_times():
    post = datetime(2026, 10, 3, 6, 30)
    with pytest.raises(ValueError, match="timezone-aware"):
        _snapshot(
            observed_at=post - timedelta(minutes=10),
            scheduled_post_time=post,
        )


def test_snapshot_rejects_post_time_observation():
    post = datetime(2026, 10, 3, 6, 30, tzinfo=UTC)
    with pytest.raises(ValueError, match="before scheduled post time"):
        _snapshot(
            observed_at=post,
            scheduled_post_time=post,
        )


def test_prediction_must_match_snapshot_time_and_odds():
    snapshot = _snapshot()

    with pytest.raises(ValueError, match="cannot precede"):
        validate_prediction_evidence(
            _prediction(
                snapshot,
                predicted_at=snapshot.observed_at - timedelta(seconds=1),
            ),
            snapshot,
        )

    with pytest.raises(ValueError, match="before scheduled post time"):
        validate_prediction_evidence(
            _prediction(
                snapshot,
                predicted_at=snapshot.scheduled_post_time,
            ),
            snapshot,
        )

    with pytest.raises(ValueError, match="must match"):
        validate_prediction_evidence(
            _prediction(snapshot, decimal_odds=9.9),
            snapshot,
        )


def test_ledger_records_immutable_prediction_evidence(tmp_path):
    ledger = Ledger(tmp_path / "paper.sqlite3")
    snapshot = _snapshot()
    prediction = _prediction(snapshot)

    prediction_id = ledger.record_paper_prediction(
        prediction,
        snapshot,
    )
    evidence = ledger.paper_evidence(prediction_id)

    assert evidence["race_id"] == snapshot.race_id
    assert evidence["horse_id"] == snapshot.horse_id
    assert evidence["prediction_odds"] == snapshot.decimal_odds
    assert evidence["snapshot_odds"] == snapshot.decimal_odds
    assert evidence["observed_at"] == snapshot.observed_at.isoformat()

    same_id = ledger.record_pre_race_snapshot(snapshot)
    linked_snapshot = ledger.conn.execute(
        "SELECT odds_snapshot_id FROM paper_prediction_evidence "
        "WHERE prediction_id=?",
        (prediction_id,),
    ).fetchone()[0]
    assert same_id == linked_snapshot

    conflicting = _snapshot(decimal_odds=7.1)
    with pytest.raises(ValueError, match="immutable odds snapshot conflict"):
        ledger.record_pre_race_snapshot(conflicting)

    ledger.close()
