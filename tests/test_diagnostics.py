import pandas as pd

from horse_racing_predictions.diagnostics import (
    add_research_diagnostic_columns,
    build_oos_diagnostics,
)


def _sample():
    return pd.DataFrame([
        {
            "race_id": "R1",
            "predicted_win_probability": 0.50,
            "decimal_odds": 3.0,
            "finish_position": 1,
            "confidence": 0.20,
        },
        {
            "race_id": "R1",
            "predicted_win_probability": 0.30,
            "decimal_odds": 4.0,
            "finish_position": 2,
            "confidence": 0.20,
        },
        {
            "race_id": "R1",
            "predicted_win_probability": 0.20,
            "decimal_odds": 8.0,
            "finish_position": 3,
            "confidence": 0.20,
        },
        {
            "race_id": "R2",
            "predicted_win_probability": 0.60,
            "decimal_odds": 2.0,
            "finish_position": 2,
            "confidence": 0.30,
        },
        {
            "race_id": "R2",
            "predicted_win_probability": 0.40,
            "decimal_odds": 3.0,
            "finish_position": 1,
            "confidence": 0.30,
        },
    ])


def test_market_probabilities_normalize_per_race():
    out = add_research_diagnostic_columns(_sample())
    sums = out.groupby("race_id")["market_implied_probability"].sum()
    assert (sums.sub(1.0).abs() < 1e-12).all()


def test_diagnostics_include_threshold_and_segment_reports():
    report = build_oos_diagnostics(_sample())
    assert report["status"] == "post_hoc_research_diagnostic_only"
    assert report["ev_bands"]
    assert report["odds_bands"]
    assert report["model_minus_market_bands"]
    assert any(
        row["ev_threshold"] == 1.15
        for row in report["ev_threshold_sweep"]
    )
