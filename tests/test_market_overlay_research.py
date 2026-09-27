from types import SimpleNamespace

import pandas as pd
import pytest

from horse_racing_predictions.market_overlay_research import (
    evaluate_fixed_overlay_rule,
    evaluate_market_overlay_v11_development,
    fit_overlay_rule,
    market_overlay_ratio,
)


def test_market_overlay_ratio_is_relative_to_market_probability():
    model = pd.Series([0.30, 0.10])
    market = pd.Series([0.20, 0.20])

    overlay = market_overlay_ratio(model, market)

    assert abs(overlay.iloc[0] - 0.50) < 1e-12
    assert abs(overlay.iloc[1] + 0.50) < 1e-12


def test_top1_overlay_rule_selects_at_most_one_per_race():
    frame = pd.DataFrame([
        {
            "race_id": "R1",
            "finish_position": 2,
            "win_odds": 4.0,
        },
        {
            "race_id": "R1",
            "finish_position": 1,
            "win_odds": 8.0,
        },
        {
            "race_id": "R2",
            "finish_position": 1,
            "win_odds": 3.0,
        },
        {
            "race_id": "R2",
            "finish_position": 2,
            "win_odds": 10.0,
        },
    ])
    model = pd.Series(
        [0.30, 0.25, 0.50, 0.15],
        index=frame.index,
    )
    market = pd.Series(
        [0.20, 0.10, 0.40, 0.10],
        index=frame.index,
    )

    result = evaluate_fixed_overlay_rule(
        frame,
        model,
        market,
        {
            "overlay_ratio_threshold": 0.10,
            "policy": "top1_overlay_per_race",
        },
    )

    assert result["rows"] == 2
    assert result["races"] == 2


def test_fit_overlay_rule_respects_minimum_sample_constraints():
    frame = pd.DataFrame([
        {
            "race_id": f"R{i}",
            "finish_position": 1,
            "win_odds": 3.0,
        }
        for i in range(4)
    ])
    model = pd.Series(
        [0.50] * len(frame),
        index=frame.index,
    )
    market = pd.Series(
        [0.25] * len(frame),
        index=frame.index,
    )

    rule, sweep = fit_overlay_rule(
        frame,
        model,
        market,
        min_rows=5,
        min_races=5,
    )

    assert rule is None
    assert sweep


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


def test_market_overlay_development_keeps_2025_holdout_untouched():
    pytest.importorskip("catboost")

    result = evaluate_market_overlay_v11_development(
        _history(),
        _champion(),
        challenger_iterations=5,
        min_rows=1,
        min_races=1,
    )

    assert result["calibration"]["period_end"] == "2022-01-05"
    assert result["tuning_2023"]["period_start"] == "2023-01-05"
    assert result["tuning_2023"]["period_end"] == "2023-01-05"
    assert result["validation_2024"]["period_start"] == "2024-01-05"
    assert result["validation_2024"]["period_end"] == "2024-01-05"
    assert (
        "development_gate_passed"
        in result["validation_2024"]
    )
