from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from horse_racing_predictions.challenger_research import (
    evaluate_unweighted_catboost_challenger,
)
from horse_racing_predictions.ranker_challenger_research import (
    evaluate_catboost_ranker_challenger,
)
from horse_racing_predictions.modeling import (
    CatBoostProbabilityModel,
    CatBoostRankingProbabilityModel,
)


class FakeBaselineModel:
    def predict_win_probability(
        self,
        frame,
        race_col="race_id",
    ):
        weights = (
            4.0
            - pd.to_numeric(
                frame["post_position"],
                errors="raise",
            )
        )
        weights = weights.astype(float)
        totals = weights.groupby(
            frame[race_col]
        ).transform("sum")
        return weights / totals


def _history():
    dates = [
        "2017-01-01",
        "2018-01-01",
        "2019-01-01",
        "2020-01-01",
        "2021-01-01",
        "2022-01-01",
        "2023-01-01",
        "2024-01-01",
        "2025-01-01",
        "2026-01-01",
    ]
    rows = []
    for race_number, date in enumerate(dates, start=1):
        winner = (race_number % 3) + 1
        for post in (1, 2, 3):
            rows.append({
                "race_id": f"R{race_number:02d}",
                "race_date": date,
                "horse_name": f"H{post}",
                "finish_position": (
                    1 if post == winner else post + 1
                ),
                "win_odds": float(2 + post),
                "post_position": post,
            })
    return pd.DataFrame(rows)


def _champion():
    return SimpleNamespace(
        model=FakeBaselineModel(),
        manifest=SimpleNamespace(
            feature_columns=("post_position",),
            train_start="2017-01-01",
            train_end="2021-07-31",
            model_version="champion-v7-test",
            experiment_id="baseline-test",
        ),
    )


def test_catboost_supports_unweighted_training():
    pytest.importorskip("catboost")
    train = pd.DataFrame({
        "race_id": ["R1", "R1", "R2", "R2"],
        "post_position": [1, 2, 1, 2],
        "is_winner": [1, 0, 0, 1],
    })
    model = CatBoostProbabilityModel(
        ["post_position"],
        iterations=5,
        depth=2,
        auto_class_weights=None,
    ).fit(train)

    p = model.predict_win_probability(train)
    sums = p.groupby(train["race_id"]).sum()
    assert np.allclose(
        sums.to_numpy(),
        [1.0, 1.0],
    )


def test_unweighted_challenger_uses_same_train_end_and_holdout():
    pytest.importorskip("catboost")
    result = evaluate_unweighted_catboost_challenger(
        _history(),
        _champion(),
        challenger_iterations=5,
    )

    assert result["training"]["train_end"] == "2021-07-31"
    assert result["training"]["races"] == 5
    assert result["evaluation"]["races"] == 5
    assert (
        result["challenger"]["model_version"]
        == "challenger-v8-unweighted-catboost"
    )
    comparison = result["holdout_comparison"]
    assert comparison[
        "baseline_calibrated_winner_log_loss"
    ] is not None
    assert comparison[
        "challenger_calibrated_winner_log_loss"
    ] is not None


def test_catboost_ranker_probabilities_sum_to_one():
    pytest.importorskip("catboost")
    train = pd.DataFrame({
        "race_id": [
            "R1", "R1", "R1",
            "R2", "R2", "R2",
            "R3", "R3", "R3",
        ],
        "post_position": [
            1, 2, 3,
            1, 2, 3,
            1, 2, 3,
        ],
        "is_winner": [
            1, 0, 0,
            0, 1, 0,
            0, 0, 1,
        ],
    })
    model = CatBoostRankingProbabilityModel(
        ["post_position"],
        iterations=5,
        depth=2,
    ).fit(train)

    p = model.predict_win_probability(train)
    sums = p.groupby(train["race_id"]).sum()

    assert np.allclose(
        sums.to_numpy(),
        [1.0, 1.0, 1.0],
    )
    assert ((p >= 0) & (p <= 1)).all()


def test_ranker_challenger_uses_same_train_end_and_holdout():
    pytest.importorskip("catboost")
    result = evaluate_catboost_ranker_challenger(
        _history(),
        _champion(),
        challenger_iterations=5,
    )

    assert result["training"]["train_end"] == "2021-07-31"
    assert result["training"]["races"] == 5
    assert result["evaluation"]["races"] == 5
    assert (
        result["challenger"]["model_version"]
        == "challenger-v9-catboost-ranker"
    )
    comparison = result["holdout_comparison"]
    assert comparison[
        "baseline_calibrated_winner_log_loss"
    ] is not None
    assert comparison[
        "challenger_calibrated_winner_log_loss"
    ] is not None
    assert (
        "challenger_beats_baseline_winner_log_loss"
        in comparison
    )
