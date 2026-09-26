import pandas as pd
import pytest

from horse_racing_predictions.features import build_pre_race_features
from horse_racing_predictions.inference import build_future_feature_frame


def _history():
    return pd.DataFrame([
        {
            "race_id": "R1",
            "race_date": "2021-07-30",
            "horse_name": "A",
            "finish_position": 1,
            "win_odds": 2.0,
        },
        {
            "race_id": "R1",
            "race_date": "2021-07-30",
            "horse_name": "B",
            "finish_position": 2,
            "win_odds": 4.0,
        },
        {
            "race_id": "R2",
            "race_date": "2021-07-31",
            "horse_name": "A",
            "finish_position": 2,
            "win_odds": 3.0,
        },
        {
            "race_id": "R2",
            "race_date": "2021-07-31",
            "horse_name": "B",
            "finish_position": 1,
            "win_odds": 2.5,
        },
    ])


def _entries(date):
    return pd.DataFrame([
        {
            "race_id": "F1",
            "race_date": date,
            "horse_name": "A",
            "post_position": 1,
        },
        {
            "race_id": "F1",
            "race_date": date,
            "horse_name": "B",
            "post_position": 2,
        },
    ])


def test_forward_inference_blocks_stale_history():
    history = _history()
    features = build_pre_race_features(history)

    with pytest.raises(ValueError, match="historical data is stale"):
        build_future_feature_frame(
            history,
            _entries("2026-09-26"),
            features.feature_columns,
        )


def test_forward_inference_accepts_recent_history():
    history = _history()
    features = build_pre_race_features(history)

    future = build_future_feature_frame(
        history,
        _entries("2021-08-01"),
        features.feature_columns,
    )
    assert len(future) == 2


def test_stale_history_requires_explicit_override():
    history = _history()
    features = build_pre_race_features(history)

    future = build_future_feature_frame(
        history,
        _entries("2026-09-26"),
        features.feature_columns,
        allow_stale_history=True,
    )
    assert len(future) == 2
