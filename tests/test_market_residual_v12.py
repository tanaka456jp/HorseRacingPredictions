from types import SimpleNamespace

import pandas as pd
import pytest

from horse_racing_predictions.market_residual_v12 import (
    evaluate_market_residual_v12_development,
    evaluate_fixed_residual_ev_rule,
    evaluate_fixed_residual_market_edge_rule,
    fit_residual_ev_rule,
    fit_residual_market_edge_rule,
    fit_residual_market_edge_odds_segment_rule,
    fit_residual_longshot_market_edge_rule,
    fit_residual_stable_longshot_market_edge_rule,
    fit_residual_gamma,
    select_broad_positive_market_edge_odds_segment,
    select_broad_positive_market_edge_rule,
    select_broad_positive_longshot_market_edge_rule,
    select_temporally_stable_longshot_market_edge_rule,
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
        "market_edge_rule_tuning_2022"
        in result
    )
    assert (
        "market_edge_development_gate_passed"
        in result
    )
    assert (
        "broad_market_edge_rule_tuning_2022"
        in result
    )
    assert (
        "broad_market_edge_development_gate_passed"
        in result
    )
    assert (
        "market_edge_odds_segment_tuning_2022"
        in result
    )
    assert (
        "market_edge_odds_segment_development_gate_passed"
        in result
    )
    assert (
        "longshot_market_edge_tuning_2022"
        in result
    )
    assert (
        "longshot_market_edge_development_gate_passed"
        in result
    )
    assert (
        "stable_longshot_market_edge_tuning_2022"
        in result
    )
    assert (
        "stable_longshot_market_edge_development_gate_passed"
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


def test_residual_market_edge_rule_meets_evidence_without_using_holdout():
    frame = pd.DataFrame({
        "race_id": [
            "R1", "R1", "R2", "R2",
            "R3", "R3", "R4", "R4",
        ],
        "finish_position": [1, 2, 2, 1, 1, 2, 2, 1],
        "win_odds": [2.5, 4.0, 3.0, 2.0, 3.5, 2.2, 2.6, 3.2],
    })
    probability = pd.Series(
        [0.45, 0.20, 0.25, 0.50, 0.35, 0.30, 0.30, 0.38],
        index=frame.index,
        dtype=float,
    )
    market_probability = pd.Series(
        [0.40, 0.25, 0.30, 0.45, 0.30, 0.35, 0.35, 0.32],
        index=frame.index,
        dtype=float,
    )

    rule, sweep = fit_residual_market_edge_rule(
        frame,
        probability,
        market_probability,
        min_rows=1,
        min_races=1,
    )

    assert rule is not None
    assert len(sweep) > 0
    assert rule["edge_ratio_threshold"] >= 1.0

    fixed = evaluate_fixed_residual_market_edge_rule(
        frame,
        probability,
        market_probability,
        rule,
    )
    assert (
        fixed["edge_ratio_threshold"]
        == rule["edge_ratio_threshold"]
    )
    assert fixed["policy"] == rule["policy"]


def test_market_edge_rule_requires_minimum_evidence():
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
    market_probability = pd.Series(
        [0.35, 0.25],
        index=frame.index,
        dtype=float,
    )

    rule, _ = fit_residual_market_edge_rule(
        frame,
        probability,
        market_probability,
        min_rows=200,
        min_races=100,
    )

    assert rule is None


def test_broad_market_edge_prefers_evidence_over_peak_tuning_roi():
    sweep = [
        {
            "edge_ratio_threshold": 1.15,
            "policy": "all_candidates",
            "rows": 648,
            "races": 590,
            "flat_bet_roi_final_odds": 0.0125,
        },
        {
            "edge_ratio_threshold": 1.20,
            "policy": "all_candidates",
            "rows": 217,
            "races": 200,
            "flat_bet_roi_final_odds": 0.1534,
        },
        {
            "edge_ratio_threshold": 1.20,
            "policy": "top1_edge_per_race",
            "rows": 200,
            "races": 200,
            "flat_bet_roi_final_odds": 0.015,
        },
    ]

    rule = select_broad_positive_market_edge_rule(
        sweep,
        min_rows=200,
        min_races=100,
    )

    assert rule is not None
    assert rule["edge_ratio_threshold"] == 1.15
    assert rule["policy"] == "all_candidates"
    assert rule["rows"] == 648
    assert rule["races"] == 590


def test_broad_market_edge_requires_positive_tuning_roi():
    sweep = [
        {
            "edge_ratio_threshold": 1.10,
            "policy": "all_candidates",
            "rows": 2223,
            "races": 1797,
            "flat_bet_roi_final_odds": -0.028,
        },
    ]

    rule = select_broad_positive_market_edge_rule(
        sweep,
        min_rows=200,
        min_races=100,
    )

    assert rule is None


def test_odds_segment_selection_prefers_broadest_positive_evidence():
    sweep = [
        {
            "segment_name": "odds_1_to_3",
            "odds_min": 1.0,
            "odds_max": 3.0,
            "edge_ratio_threshold": 1.15,
            "policy": "all_candidates",
            "rows": 205,
            "races": 180,
            "flat_bet_roi_final_odds": 0.08,
        },
        {
            "segment_name": "odds_3_to_6",
            "odds_min": 3.0,
            "odds_max": 6.0,
            "edge_ratio_threshold": 1.15,
            "policy": "all_candidates",
            "rows": 260,
            "races": 230,
            "flat_bet_roi_final_odds": 0.02,
        },
        {
            "segment_name": "odds_6_to_12",
            "odds_min": 6.0,
            "odds_max": 12.0,
            "edge_ratio_threshold": 1.15,
            "policy": "all_candidates",
            "rows": 90,
            "races": 80,
            "flat_bet_roi_final_odds": 0.20,
        },
    ]

    rule = select_broad_positive_market_edge_odds_segment(
        sweep,
        min_rows=200,
        min_races=100,
    )

    assert rule is not None
    assert rule["segment_name"] == "odds_3_to_6"
    assert rule["rows"] == 260
    assert rule["races"] == 230


def test_odds_segment_rule_uses_frozen_broad_market_edge_rule():
    frame = pd.DataFrame({
        "race_id": ["R1", "R1", "R2", "R2", "R3", "R3"],
        "finish_position": [1, 2, 2, 1, 1, 2],
        "win_odds": [2.5, 4.5, 3.2, 5.0, 2.2, 7.0],
    })
    probability = pd.Series(
        [0.45, 0.25, 0.32, 0.35, 0.50, 0.20],
        index=frame.index,
        dtype=float,
    )
    market_probability = pd.Series(
        [0.38, 0.22, 0.27, 0.29, 0.42, 0.18],
        index=frame.index,
        dtype=float,
    )
    base_rule = {
        "edge_ratio_threshold": 1.10,
        "policy": "all_candidates",
    }

    rule, sweep = fit_residual_market_edge_odds_segment_rule(
        frame,
        probability,
        market_probability,
        base_rule,
        min_rows=1,
        min_races=1,
    )

    assert len(sweep) == 4
    if rule is not None:
        assert (
            rule["edge_ratio_threshold"]
            == base_rule["edge_ratio_threshold"]
        )
        assert rule["policy"] == base_rule["policy"]


def test_longshot_rule_prefers_broad_positive_threshold():
    sweep = [
        {
            "segment_name": "odds_6_plus",
            "odds_min": 6.0,
            "odds_max": None,
            "edge_ratio_threshold": 1.10,
            "policy": "all_candidates",
            "rows": 280,
            "races": 220,
            "flat_bet_roi_final_odds": 0.04,
        },
        {
            "segment_name": "odds_6_plus",
            "odds_min": 6.0,
            "odds_max": None,
            "edge_ratio_threshold": 1.15,
            "policy": "all_candidates",
            "rows": 193,
            "races": 150,
            "flat_bet_roi_final_odds": 0.38,
        },
        {
            "segment_name": "odds_6_plus",
            "odds_min": 6.0,
            "odds_max": None,
            "edge_ratio_threshold": 1.20,
            "policy": "all_candidates",
            "rows": 100,
            "races": 90,
            "flat_bet_roi_final_odds": 0.50,
        },
    ]

    rule = select_broad_positive_longshot_market_edge_rule(
        sweep,
        min_rows=200,
        min_races=100,
    )

    assert rule is not None
    assert rule["edge_ratio_threshold"] == 1.10
    assert rule["rows"] == 280
    assert rule["races"] == 220


def test_longshot_rule_keeps_odds_six_plus_fixed():
    frame = pd.DataFrame({
        "race_id": ["R1", "R1", "R2", "R2"],
        "finish_position": [1, 2, 2, 1],
        "win_odds": [7.0, 3.0, 8.0, 10.0],
    })
    probability = pd.Series(
        [0.18, 0.35, 0.16, 0.14],
        index=frame.index,
        dtype=float,
    )
    market_probability = pd.Series(
        [0.14, 0.32, 0.13, 0.11],
        index=frame.index,
        dtype=float,
    )

    rule, sweep = fit_residual_longshot_market_edge_rule(
        frame,
        probability,
        market_probability,
        min_rows=1,
        min_races=1,
    )

    assert len(sweep) > 0
    assert all(row["odds_min"] == 6.0 for row in sweep)
    assert all(row["odds_max"] is None for row in sweep)
    if rule is not None:
        assert rule["policy"] == "all_candidates"


def test_stable_longshot_rule_requires_positive_both_tuning_folds():
    sweep = [
        {
            "edge_ratio_threshold": 1.05,
            "policy": "all_candidates",
            "rows": 500,
            "races": 350,
            "flat_bet_roi_final_odds": 0.03,
            "early_rows": 240,
            "early_races": 170,
            "early_flat_bet_roi_final_odds": -0.01,
            "late_rows": 260,
            "late_races": 180,
            "late_flat_bet_roi_final_odds": 0.07,
        },
        {
            "edge_ratio_threshold": 1.10,
            "policy": "all_candidates",
            "rows": 420,
            "races": 300,
            "flat_bet_roi_final_odds": 0.04,
            "early_rows": 200,
            "early_races": 140,
            "early_flat_bet_roi_final_odds": 0.02,
            "late_rows": 220,
            "late_races": 160,
            "late_flat_bet_roi_final_odds": 0.06,
        },
    ]

    rule = select_temporally_stable_longshot_market_edge_rule(
        sweep,
        min_rows=200,
        min_races=100,
        min_fold_rows=100,
        min_fold_races=50,
    )

    assert rule is not None
    assert rule["edge_ratio_threshold"] == 1.10


def test_stable_longshot_sweep_uses_fixed_time_split():
    frame = pd.DataFrame({
        "race_id": ["R1", "R1", "R2", "R2"],
        "race_date": [
            "2022-01-01", "2022-01-01",
            "2022-08-01", "2022-08-01",
        ],
        "finish_position": [1, 2, 2, 1],
        "win_odds": [7.0, 8.0, 9.0, 10.0],
    })
    probability = pd.Series(
        [0.18, 0.15, 0.14, 0.13],
        index=frame.index,
        dtype=float,
    )
    market_probability = pd.Series(
        [0.14, 0.13, 0.12, 0.11],
        index=frame.index,
        dtype=float,
    )

    rule, sweep = fit_residual_stable_longshot_market_edge_rule(
        frame,
        probability,
        market_probability,
        min_rows=1,
        min_races=1,
        min_fold_rows=1,
        min_fold_races=1,
    )

    assert len(sweep) > 0
    assert all(
        row["stability_split_date"] == "2022-05-01"
        for row in sweep
    )
    if rule is not None:
        assert rule["policy"] == "all_candidates"
