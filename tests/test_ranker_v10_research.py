from types import SimpleNamespace

import pandas as pd
import pytest

from horse_racing_predictions.ranker_v10_research import (
    evaluate_ranker_v10_development,
)


def _history():
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
    rows = []
    for race_no, date in enumerate(dates, start=1):
        winner = (race_no % 3) + 1
        for post in (1, 2, 3):
            rows.append({
                "race_id": f"R{race_no:02d}",
                "race_date": date,
                "horse_name": f"H{post}",
                "jockey": f"J{(post + race_no) % 3}",
                "trainer": f"T{post}",
                "finish_position": (
                    1 if post == winner else post + 1
                ),
                "win_odds": float(2 + post),
                "distance_m": 1400 + (race_no % 3) * 200,
                "post_position": post,
                "age": 3 + (post % 2),
                "carried_weight": 54 + post,
                "horse_weight": 450 + post * 10,
                "horse_weight_delta": (race_no + post) % 5 - 2,
                "racecourse": "Kyoto",
                "surface": "Turf" if race_no % 2 else "Dirt",
                "weather": "Fine",
                "track_condition": "Good",
                "sex": "M",
                "race_class": "OPEN",
                "graded_race": "NONE",
            })
    return pd.DataFrame(rows)


def _champion():
    return SimpleNamespace(
        manifest=SimpleNamespace(
            feature_columns=("post_position",),
            train_start="2017-01-01",
            train_end="2021-07-31",
        )
    )


def test_ranker_v10_development_excludes_2025_plus_before_selection():
    pytest.importorskip("catboost")
    result = evaluate_ranker_v10_development(
        _history(),
        _champion(),
        challenger_iterations=5,
    )

    assert result["training"]["train_end"] == "2021-07-31"
    assert result["calibration"]["period_end"] == "2023-01-05"
    assert result["selection_2024"]["period_start"] == "2024-01-05"
    assert result["selection_2024"]["period_end"] == "2024-01-05"
    assert result["features"]["added_count"] > 0
    assert (
        "horse_past_avg_finish_percentile"
        in result["features"]["added_feature_columns"]
    )
    assert (
        "horse_jockey_past_starts"
        in result["features"]["added_feature_columns"]
    )
    assert (
        "development_gate_passed"
        in result["selection_2024"]
    )
