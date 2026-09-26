import pandas as pd
import pytest

from horse_racing_predictions.jravan_trial import (
    filter_after_base_history,
)


def test_filter_after_base_history_removes_overlap():
    base = pd.DataFrame([
        {
            "race_id": "B1",
            "race_date": "2021-07-31",
            "horse_name": "A",
        }
    ])
    parsed = pd.DataFrame([
        {
            "race_id": "OLD",
            "race_date": "2021-07-31",
            "post_position": 1,
            "horse_name": "OLD",
        },
        {
            "race_id": "NEW1",
            "race_date": "2021-08-01",
            "post_position": 2,
            "horse_name": "B",
        },
        {
            "race_id": "NEW2",
            "race_date": "2026-09-26",
            "post_position": 1,
            "horse_name": "C",
        },
    ])

    supplement, base_end = filter_after_base_history(
        base,
        parsed,
    )

    assert str(base_end.date()) == "2021-07-31"
    assert list(supplement["race_id"]) == [
        "NEW1",
        "NEW2",
    ]


def test_filter_after_base_history_rejects_empty_frames():
    with pytest.raises(ValueError, match="base history is empty"):
        filter_after_base_history(
            pd.DataFrame(),
            pd.DataFrame([{
                "race_date": "2021-08-01",
            }]),
        )

    with pytest.raises(ValueError, match="parsed JRA-VAN history is empty"):
        filter_after_base_history(
            pd.DataFrame([{
                "race_date": "2021-07-31",
            }]),
            pd.DataFrame(),
        )
