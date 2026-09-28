from types import SimpleNamespace

import pandas as pd
import pytest

from horse_racing_predictions.market_residual_v12_holdout import (
    FIXED_GAMMA,
    evaluate_market_residual_v12_holdout,
)


def _row(
    race_id,
    race_date,
    post,
    *,
    winner,
    odds,
):
    return {
        "race_id": race_id,
        "race_date": race_date,
        "horse_name": f"H{post}",
        "jockey": f"J{post}",
        "trainer": f"T{post}",
        "finish_position": 1 if post == winner else post + 1,
        "win_odds": odds,
        "distance_m": 1600,
        "post_position": post,
        "age": 3,
        "carried_weight": 54 + post,
        "horse_weight": 450 + post * 10,
        "horse_weight_delta": 0,
        "racecourse": "Kyoto",
        "surface": "Turf",
        "weather": "Fine",
        "track_condition": "Good",
        "sex": "M",
        "race_class": "OPEN",
        "graded_race": "NONE",
    }


def _history():
    rows = []
    dates = [
        "2017-01-05",
        "2018-01-05",
        "2019-01-05",
        "2020-01-05",
        "2021-01-05",
        "2022-01-05",
        "2023-01-05",
        "2024-01-05",
        "2025-01-05",
        "2026-01-05",
    ]
    for idx, date in enumerate(dates, start=1):
        winner = 1 if idx % 2 else 2
        odds = (
            [1.8, 4.0, 8.0]
            if winner == 1
            else [4.0, 1.8, 8.0]
        )
        for post in (1, 2, 3):
            rows.append(
                _row(
                    f"R{idx:02d}",
                    date,
                    post,
                    winner=winner,
                    odds=odds[post - 1],
                )
            )
    return pd.DataFrame(rows)


def _champion():
    return SimpleNamespace(
        manifest=SimpleNamespace(
            train_start="2017-01-01",
            train_end="2021-07-31",
        )
    )


def test_holdout_confirmation_rejects_gamma_changes():
    pytest.importorskip("catboost")

    with pytest.raises(
        ValueError,
        match="fixed gamma=4.0",
    ):
        evaluate_market_residual_v12_holdout(
            _history(),
            _champion(),
            iterations=5,
            fixed_gamma=2.0,
        )


def test_holdout_confirmation_keeps_original_training_period():
    pytest.importorskip("catboost")

    result = evaluate_market_residual_v12_holdout(
        _history(),
        _champion(),
        iterations=5,
    )

    assert result["training"]["train_end"] == "2021-07-31"
    assert result["fixed_parameters"]["gamma"] == FIXED_GAMMA
    assert result["holdout_combined"]["period_start"] == "2025-01-05"
    years = {
        row["year"]
        for row in result["holdout_yearly"]
    }
    assert years == {2025, 2026}
    assert (
        "confirmation_gate_passed"
        in result
    )
