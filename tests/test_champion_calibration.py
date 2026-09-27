from types import SimpleNamespace

import pandas as pd

from horse_racing_predictions.champion_calibration import (
    evaluate_temperature_calibration_predictions,
)
from horse_racing_predictions.config import StrategyConfig


def _race(race_id, date, winner_index):
    probabilities = [0.90, 0.05, 0.05]
    rows = []
    for index, probability in enumerate(probabilities):
        rows.append({
            "race_id": race_id,
            "race_date": date,
            "horse_id": f"{race_id}-{index + 1}",
            "horse_name": f"H{index + 1}",
            "finish_position": (
                1 if index == winner_index else index + 2
            ),
            "decimal_odds": 3.0 + index,
            "predicted_win_probability": probability,
            "confidence": 0.8,
            "model_version": "champion-v7",
        })
    return rows


def _predictions():
    rows = []
    rows += _race("D1", "2023-01-01", 1)
    rows += _race("D2", "2023-01-02", 1)
    rows += _race("D3", "2024-01-01", 0)
    rows += _race("D4", "2024-01-02", 1)
    rows += _race("H1", "2025-01-01", 1)
    rows += _race("H2", "2026-01-01", 0)
    return pd.DataFrame(rows)


def _champion():
    return SimpleNamespace(
        manifest=SimpleNamespace(
            model_version="champion-v7",
            experiment_id="v7-test",
            train_end="2021-07-31",
        )
    )


def test_temperature_is_fit_only_from_development_period():
    result = evaluate_temperature_calibration_predictions(
        _predictions(),
        _champion(),
        config=StrategyConfig(),
    )

    assert result["development"]["races"] == 4
    assert result["holdout"]["races"] == 2
    assert result["development"]["period_end"] == "2024-01-02"
    assert result["holdout"]["period_start"] == "2025-01-01"
    assert result["temperature"] > 1.0


def test_calibration_softens_overconfident_development_predictions():
    result = evaluate_temperature_calibration_predictions(
        _predictions(),
        _champion(),
        config=StrategyConfig(),
    )

    raw = result["development"]["raw_quality"][
        "winner_log_loss"
    ]
    calibrated = result["development"][
        "calibrated_quality"
    ]["winner_log_loss"]
    assert calibrated < raw


def test_calibration_reports_holdout_ev_sweeps_without_changing_config():
    result = evaluate_temperature_calibration_predictions(
        _predictions(),
        _champion(),
        config=StrategyConfig(
            min_ev=1.15,
            min_probability=0.03,
            min_confidence=0.55,
        ),
    )

    raw = result["holdout"]["raw_ev_threshold_sweep"]
    calibrated = result["holdout"][
        "calibrated_ev_threshold_sweep"
    ]
    assert [row["ev_threshold"] for row in raw] == [
        row["ev_threshold"] for row in calibrated
    ]
    assert 1.15 in {
        row["ev_threshold"] for row in calibrated
    }


def test_calibrated_candidate_policy_sweep_is_reported():
    result = evaluate_temperature_calibration_predictions(
        _predictions(),
        _champion(),
        config=StrategyConfig(
            min_ev=1.15,
            min_probability=0.03,
            min_confidence=0.55,
        ),
    )

    rows = result[
        "calibrated_candidate_selection_policy_sweep_by_period"
    ]
    assert rows
    holdout = [
        row for row in rows
        if row["period"] == "holdout_2025_2026"
        and row["confidence_threshold"] == 0.0
    ]
    policies = {row["policy"] for row in holdout}
    assert policies == {
        "all_candidates",
        "top1_ev_per_race",
        "top1_probability_per_race",
    }


def test_market_consensus_sweep_reports_rank_caps():
    result = evaluate_temperature_calibration_predictions(
        _predictions(),
        _champion(),
        config=StrategyConfig(
            min_ev=1.15,
            min_probability=0.03,
            min_confidence=0.55,
        ),
    )

    rows = result["calibrated_market_consensus_sweep"]
    holdout = [
        row for row in rows
        if row["period"] == "holdout_2025_2026"
        and row["confidence_threshold"] == 0.0
    ]
    assert {row["market_rank_cap"] for row in holdout} == {
        1,
        3,
        5,
    }
    assert all(
        row["rows"] <= row["races"]
        for row in holdout
    )
