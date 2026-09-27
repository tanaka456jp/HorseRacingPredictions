import pandas as pd

from horse_racing_predictions.champion_diagnostics import (
    race_certainty,
    summarize_prediction_diagnostics,
)
from horse_racing_predictions.config import StrategyConfig


def _predictions():
    return pd.DataFrame([
        {
            "race_id": "R1",
            "race_date": "2026-01-01",
            "horse_id": "R1-1",
            "horse_name": "A",
            "finish_position": 1,
            "decimal_odds": 4.0,
            "predicted_win_probability": 0.40,
            "confidence": 0.60,
            "model_version": "champion-v7",
        },
        {
            "race_id": "R1",
            "race_date": "2026-01-01",
            "horse_id": "R1-2",
            "horse_name": "B",
            "finish_position": 2,
            "decimal_odds": 2.0,
            "predicted_win_probability": 0.60,
            "confidence": 0.60,
            "model_version": "champion-v7",
        },
        {
            "race_id": "R2",
            "race_date": "2026-01-02",
            "horse_id": "R2-1",
            "horse_name": "C",
            "finish_position": 1,
            "decimal_odds": 10.0,
            "predicted_win_probability": 0.02,
            "confidence": 0.70,
            "model_version": "champion-v7",
        },
        {
            "race_id": "R2",
            "race_date": "2026-01-02",
            "horse_id": "R2-2",
            "horse_name": "D",
            "finish_position": 2,
            "decimal_odds": 8.0,
            "predicted_win_probability": 0.10,
            "confidence": 0.20,
            "model_version": "champion-v7",
        },
    ])


def test_race_certainty_is_low_for_uniform_probabilities():
    value = race_certainty(pd.Series([0.5, 0.5]))
    assert value == 0.0


def test_race_certainty_is_high_for_concentrated_probabilities():
    value = race_certainty(pd.Series([0.99, 0.01]))
    assert value > 0.9


def test_diagnostics_reports_current_config_rejection_reasons():
    summary = summarize_prediction_diagnostics(
        _predictions(),
        config=StrategyConfig(
            min_ev=1.15,
            min_probability=0.03,
            min_confidence=0.55,
        ),
    )

    counts = summary["selection_reason_counts"]
    assert counts["eligible"] == 2
    assert counts["probability_below_threshold"] == 1
    assert counts["confidence_below_threshold"] == 1
    assert counts["ev_below_threshold"] == 0
    assert summary["rows"] == 4
    assert summary["races"] == 2


def test_confidence_sweep_includes_current_threshold():
    summary = summarize_prediction_diagnostics(
        _predictions(),
        config=StrategyConfig(),
    )

    thresholds = {
        row["confidence_threshold"]: row
        for row in summary["confidence_threshold_sweep"]
    }
    assert 0.55 in thresholds
    assert thresholds[0.55]["rows"] == 2
    assert thresholds[0.55]["races"] == 1


def test_confidence_sweep_is_split_into_development_and_holdout():
    frame = pd.concat([
        _predictions().assign(race_date=[
            "2024-12-30",
            "2024-12-30",
            "2024-12-31",
            "2024-12-31",
        ]),
        _predictions().assign(
            race_id=["R3", "R3", "R4", "R4"],
            horse_id=["R3-1", "R3-2", "R4-1", "R4-2"],
            race_date=[
                "2025-01-01",
                "2025-01-01",
                "2026-01-02",
                "2026-01-02",
            ],
        ),
    ], ignore_index=True)

    summary = summarize_prediction_diagnostics(
        frame,
        config=StrategyConfig(),
    )

    rows = summary["confidence_threshold_sweep_by_period"]
    periods = {row["period"] for row in rows}
    assert "development_2021_2024" in periods
    assert "holdout_2025_2026" in periods
    assert "year_2024" in periods
    assert "year_2025" in periods
    assert "year_2026" in periods

    holdout = [
        row for row in rows
        if row["period"] == "holdout_2025_2026"
        and row["confidence_threshold"] == 0.55
    ]
    assert len(holdout) == 1
    assert holdout[0]["rows"] == 2


def test_candidate_selection_policy_sweep_limits_to_one_per_race():
    frame = pd.DataFrame([
        {
            "race_id": "R1",
            "race_date": "2025-01-01",
            "horse_id": "R1-1",
            "horse_name": "A",
            "finish_position": 2,
            "decimal_odds": 4.0,
            "predicted_win_probability": 0.40,
            "confidence": 0.30,
            "model_version": "champion-v7",
        },
        {
            "race_id": "R1",
            "race_date": "2025-01-01",
            "horse_id": "R1-2",
            "horse_name": "B",
            "finish_position": 1,
            "decimal_odds": 8.0,
            "predicted_win_probability": 0.20,
            "confidence": 0.30,
            "model_version": "champion-v7",
        },
        {
            "race_id": "R2",
            "race_date": "2025-01-02",
            "horse_id": "R2-1",
            "horse_name": "C",
            "finish_position": 1,
            "decimal_odds": 3.0,
            "predicted_win_probability": 0.50,
            "confidence": 0.30,
            "model_version": "champion-v7",
        },
        {
            "race_id": "R2",
            "race_date": "2025-01-02",
            "horse_id": "R2-2",
            "horse_name": "D",
            "finish_position": 2,
            "decimal_odds": 10.0,
            "predicted_win_probability": 0.15,
            "confidence": 0.30,
            "model_version": "champion-v7",
        },
    ])

    summary = summarize_prediction_diagnostics(
        frame,
        config=StrategyConfig(
            min_ev=1.15,
            min_probability=0.03,
            min_confidence=0.55,
        ),
    )

    rows = summary["candidate_selection_policy_sweep_by_period"]
    holdout = [
        row for row in rows
        if row["period"] == "holdout_2025_2026"
        and row["confidence_threshold"] == 0.0
    ]
    by_policy = {row["policy"]: row for row in holdout}

    assert by_policy["all_candidates"]["rows"] == 4
    assert by_policy["all_candidates"]["races"] == 2
    assert by_policy["top1_ev_per_race"]["rows"] == 2
    assert by_policy["top1_ev_per_race"]["races"] == 2
    assert by_policy["top1_probability_per_race"]["rows"] == 2
    assert by_policy["top1_probability_per_race"]["races"] == 2
