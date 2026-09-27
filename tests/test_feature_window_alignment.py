from types import SimpleNamespace

import pandas as pd

from horse_racing_predictions.feature_window import (
    align_history_to_training_start,
)
from horse_racing_predictions.inference import (
    predict_future_entries,
)


def _row(race_id, race_date, horse_name, post_position, finish_position):
    return {
        "race_id": race_id,
        "race_date": race_date,
        "horse_name": horse_name,
        "finish_position": finish_position,
        "win_odds": 2.0,
        "distance_m": 1600,
        "post_position": post_position,
        "age": 3,
        "carried_weight": 55,
        "horse_weight": 470,
        "horse_weight_delta": 0,
        "racecourse": "Kyoto",
        "surface": "Turf",
        "weather": "Fine",
        "track_condition": "Good",
        "sex": "M",
        "jockey": "J1",
        "trainer": "T1",
    }


def _entry(race_id, race_date, horse_name, post_position):
    row = _row(
        race_id,
        race_date,
        horse_name,
        post_position,
        None,
    )
    row.pop("finish_position")
    row.pop("win_odds")
    return row


class CaptureModel:
    def __init__(self):
        self.seen = None

    def predict_win_probability(self, frame, race_col="race_id"):
        self.seen = frame.copy()
        return pd.Series(
            [1.0 / len(frame)] * len(frame),
            index=frame.index,
            dtype=float,
        )


def test_align_history_drops_rows_before_champion_train_start():
    history = pd.DataFrame([
        _row("OLD", "2016-12-31", "H1", 1, 1),
        _row("TRAIN", "2017-01-01", "H1", 1, 1),
        _row("LATER", "2018-01-01", "H1", 1, 1),
    ])

    aligned = align_history_to_training_start(
        history,
        train_start="2017-01-01",
    )

    assert list(aligned["race_id"]) == ["TRAIN", "LATER"]


def test_forward_features_match_champion_training_history_origin():
    history = pd.DataFrame([
        _row("OLD1", "2010-01-01", "H1", 1, 1),
        _row("OLD2", "2016-12-31", "H1", 1, 1),
        _row("T1", "2017-01-01", "H1", 1, 1),
        _row("T2", "2018-01-01", "H1", 1, 2),
        _row("T3", "2019-01-01", "H1", 1, 1),
    ])
    entries = pd.DataFrame([
        _entry("F1", "2020-01-01", "H1", 1),
        _entry("F1", "2020-01-01", "H2", 2),
    ])

    model = CaptureModel()
    champion = SimpleNamespace(
        model=model,
        manifest=SimpleNamespace(
            feature_columns=("horse_past_starts",),
            train_start="2017-01-01",
            train_end="2019-12-31",
            model_version="champion-v7",
            experiment_id="v7-test",
        ),
    )

    output = predict_future_entries(
        champion,
        history,
        entries,
        max_history_gap_days=400,
    )

    assert len(output) == 2
    assert model.seen is not None
    h1 = model.seen.loc[
        model.seen["horse_name"] == "H1"
    ].iloc[0]
    assert h1["horse_past_starts"] == 3
