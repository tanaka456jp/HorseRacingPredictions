from types import SimpleNamespace

import pandas as pd

from horse_racing_predictions.config import StrategyConfig
from horse_racing_predictions.market_blend_research import (
    blend_probability,
    evaluate_market_blend_predictions,
    normalized_market_probability,
)


def _race(
    race_id,
    date,
    *,
    winner_index,
    probabilities,
    odds,
):
    rows = []
    for index, (p, price) in enumerate(
        zip(probabilities, odds)
    ):
        rows.append({
            "race_id": race_id,
            "race_date": date,
            "horse_id": f"{race_id}-{index + 1}",
            "horse_name": f"H{index + 1}",
            "finish_position": (
                1 if index == winner_index else index + 2
            ),
            "decimal_odds": price,
            "predicted_win_probability": p,
            "confidence": 0.2,
            "model_version": "champion-v7",
        })
    return rows


def _champion():
    return SimpleNamespace(
        manifest=SimpleNamespace(
            model_version="champion-v7",
            experiment_id="v7-test",
            train_end="2021-07-31",
        )
    )


def _predictions(holdout_winner_index=0):
    rows = []
    # Development: market strongly favors horse 1 and horse 1 wins,
    # while the model favors horse 2. The fitted blend should stay
    # close to the market baseline.
    for race_id, date in (
        ("D1", "2023-01-01"),
        ("D2", "2023-06-01"),
        ("D3", "2024-01-01"),
        ("D4", "2024-06-01"),
    ):
        rows += _race(
            race_id,
            date,
            winner_index=0,
            probabilities=[0.10, 0.80, 0.10],
            odds=[1.6, 5.0, 10.0],
        )

    rows += _race(
        "H1",
        "2025-01-01",
        winner_index=holdout_winner_index,
        probabilities=[0.10, 0.80, 0.10],
        odds=[1.6, 5.0, 10.0],
    )
    rows += _race(
        "H2",
        "2026-01-01",
        winner_index=holdout_winner_index,
        probabilities=[0.10, 0.80, 0.10],
        odds=[1.6, 5.0, 10.0],
    )
    return pd.DataFrame(rows)


def test_market_probability_is_normalized_per_race():
    frame = _predictions()
    market = normalized_market_probability(frame)

    totals = market.groupby(frame["race_id"]).sum()
    assert all(abs(value - 1.0) < 1e-12 for value in totals)


def test_blend_endpoints_match_market_and_model():
    frame = _predictions()
    model = pd.to_numeric(
        frame["predicted_win_probability"],
    )
    market = normalized_market_probability(frame)

    market_only = blend_probability(
        model,
        market,
        0.0,
    )
    model_only = blend_probability(
        model,
        market,
        1.0,
    )

    pd.testing.assert_series_equal(
        market_only,
        market,
        check_names=False,
    )
    pd.testing.assert_series_equal(
        model_only,
        model.astype(float),
        check_names=False,
    )


def test_alpha_is_fitted_from_development_only():
    first = evaluate_market_blend_predictions(
        _predictions(holdout_winner_index=0),
        _champion(),
        config=StrategyConfig(),
    )
    second = evaluate_market_blend_predictions(
        _predictions(holdout_winner_index=1),
        _champion(),
        config=StrategyConfig(),
    )

    assert (
        first["development"][
            "fitted_alpha_model_weight"
        ]
        == second["development"][
            "fitted_alpha_model_weight"
        ]
    )
    assert (
        first["development"][
            "fitted_alpha_model_weight"
        ]
        < 0.5
    )


def test_holdout_reports_market_model_and_fitted_blend_quality():
    result = evaluate_market_blend_predictions(
        _predictions(),
        _champion(),
        config=StrategyConfig(),
    )

    quality = result["holdout"]["quality"]
    assert set(quality) == {
        "market",
        "calibrated_model",
        "fitted_blend",
    }
    assert result["holdout"]["races"] == 2
    assert (
        "winner_log_loss_delta_vs_market"
        in result["holdout"]
    )
    assert result["holdout"]["blend_ev_threshold_sweep"]
