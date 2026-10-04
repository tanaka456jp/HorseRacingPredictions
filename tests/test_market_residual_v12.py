from types import SimpleNamespace

import pandas as pd
import pytest

from horse_racing_predictions.market_residual_v12 import (
    evaluate_market_residual_v12_development,
    evaluate_fixed_residual_ev_rule,
    fit_residual_ev_rule,
    fit_residual_gamma,
    residual_adjusted_probability,
)


def test_gamma_zero_reproduces_market_probability():
    frame = pd.DataFrame({
        "race_id": ["R1", "R1", "R1"],
    })
    market = pd.Series(
        [0.60, 0.30, 0.10],
        index=frame.index,
        dtype=float,
    )
    residual = pd.Series(
        [0.5, -0.2, 0.1],
        index=frame.index,
        dtype=float,
    )

    adjusted = residual_adjusted_probability(
        frame,
        market,
        residual,
        gamma=0.0,
    )

    assert all(
        abs(a - b) < 1e-12
        for a, b in zip(adjusted, market)
    )


def test_gamma_fitting_tie_breaks_to_market_baseline():
    frame = pd.DataFrame({
        "race_id": ["R1", "R1", "R2", "R2"],
        "finish_position": [1, 2, 1, 2],
    })
    market = pd.Series(
        [0.7, 0.3, 0.7, 0.3],
        index=frame.index,
        dtype=float,
    )
    residual = pd.Series(
        [0.0, 0.0, 0.0, 0.0],
        index=frame.index,
        dtype=float,
    )

    gamma, rows = fit_residual_gamma(
        frame,
        market,
        residual,
        gamma_grid=(0.0, 1.0, 2.0),
    )

    assert gamma == 0.0
    assert len(rows) == 3


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


def test_residual_v12_development_keeps_2025_holdout_untouched():
    pytest.importorskip("catboost")

    result = evaluate_market_residual_v12_development(
        _history(),
        _champion(),
        iterations=5,
    )

    assert result["training"]["train_end"] == "2021-07-31"
    assert (
        result["gamma_tuning"]["period_end"]
        == "2022-01-05"
    )
    assert (
        result["validation_2023"]["period_start"]
        == "2023-01-05"
    )
    assert (
        result["validation_2024"]["period_start"]
        == "2024-01-05"
    )
    assert (
        "development_gate_passed"
        in result
    )
    assert (
        "ev_rule_tuning_2022"
        in result
    )
    assert (
        "ev_development_gate_passed"
        in result
    )
    assert (
        result["validation_2023"]["fixed_ev_rule_result"]
        is None
        or result["validation_2023"]["fixed_ev_rule_result"][
            "ev_threshold"
        ]
        == result["ev_rule_tuning_2022"]["fitted_rule"][
            "ev_threshold"
        ]
    )


def test_residual_ev_rule_selects_on_tuning_and_evaluates_fixed_rule():
    frame = pd.DataFrame({
        "race_id": ["R1", "R1", "R2", "R2"],
        "finish_position": [1, 2, 2, 1],
        "win_odds": [3.0, 2.0, 2.0, 4.0],
    })
    probability = pd.Series(
        [0.40, 0.20, 0.20, 0.35],
        index=frame.index,
        dtype=float,
    )

    rule, sweep = fit_residual_ev_rule(
        frame,
        probability,
        min_probability=0.03,
        min_rows=1,
        min_races=1,
    )

    assert rule is not None
    assert len(sweep) > 0
    assert rule["policy"] in {
        "all_candidates",
        "top1_ev_per_race",
    }

    fixed = evaluate_fixed_residual_ev_rule(
        frame,
        probability,
        rule,
        min_probability=0.03,
    )
    assert fixed["ev_threshold"] == rule["ev_threshold"]
    assert fixed["policy"] == rule["policy"]


def test_residual_ev_rule_requires_minimum_evidence():
    frame = pd.DataFrame({
        "race_id": ["R1", "R1"],
        "finish_position": [1, 2],
        "win_odds": [3.0, 2.0],
    })
    probability = pd.Series(
        [0.40, 0.20],
        index=frame.index,
        dtype=float,
    )

    rule, _ = fit_residual_ev_rule(
        frame,
        probability,
        min_rows=200,
        min_races=100,
    )

    assert rule is None
