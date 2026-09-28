import pandas as pd
import pytest

from horse_racing_predictions.residual_shadow_ledger import (
    ResidualShadowLedger,
)


def _predictions():
    return pd.DataFrame([
        {
            "race_id": "R1",
            "horse_id": "R1-1",
            "post_position": 1,
            "race_date": "2026-09-28",
            "observed_at": "2026-09-28T00:00:00+00:00",
            "scheduled_post_time": "2026-09-28T01:00:00+00:00",
            "decimal_odds": 2.0,
            "market_probability": 0.6,
            "residual_v12_probability": 0.65,
            "overlay_ratio": 0.0833333333333333,
            "fixed_gamma": 4.0,
        },
        {
            "race_id": "R1",
            "horse_id": "R1-2",
            "post_position": 2,
            "race_date": "2026-09-28",
            "observed_at": "2026-09-28T00:00:00+00:00",
            "scheduled_post_time": "2026-09-28T01:00:00+00:00",
            "decimal_odds": 4.0,
            "market_probability": 0.4,
            "residual_v12_probability": 0.35,
            "overlay_ratio": -0.125,
            "fixed_gamma": 4.0,
        },
    ])


def _results():
    return pd.DataFrame([
        {
            "race_id": "R1",
            "post_position": 1,
            "finish_position": 1,
        },
        {
            "race_id": "R1",
            "post_position": 2,
            "finish_position": 2,
        },
    ])


def test_shadow_ledger_is_idempotent_and_evaluates(tmp_path):
    ledger = ResidualShadowLedger(
        tmp_path / "shadow.sqlite3"
    )
    try:
        assert ledger.record_predictions(_predictions()) == 2
        assert ledger.record_predictions(_predictions()) == 0
        assert ledger.record_results(_results()) == 2
        assert ledger.record_results(_results()) == 0

        summary = ledger.cumulative_summary()
        assert summary["prediction_rows"] == 2
        assert summary["prediction_races"] == 1
        assert summary["evaluated_rows"] == 2
        assert summary["evaluated_races"] == 1
        assert summary["evaluation"]["status"] == "evaluated"
    finally:
        ledger.close()


def test_shadow_ledger_rejects_prediction_conflict(tmp_path):
    ledger = ResidualShadowLedger(
        tmp_path / "shadow.sqlite3"
    )
    try:
        ledger.record_predictions(_predictions())
        changed = _predictions()
        changed.loc[0, "decimal_odds"] = 2.2

        with pytest.raises(
            ValueError,
            match="immutable shadow prediction conflict",
        ):
            ledger.record_predictions(changed)
    finally:
        ledger.close()


def test_shadow_ledger_rejects_result_conflict(tmp_path):
    ledger = ResidualShadowLedger(
        tmp_path / "shadow.sqlite3"
    )
    try:
        ledger.record_predictions(_predictions())
        ledger.record_results(_results())
        changed = _results()
        changed.loc[0, "finish_position"] = 2

        with pytest.raises(
            ValueError,
            match="immutable shadow result conflict",
        ):
            ledger.record_results(changed)
    finally:
        ledger.close()
