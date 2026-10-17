"""Synthetic-only Phase 11 calendar-boundary regression tests.

No historical files, model fitting, final holdout, or Forward Paper are used.
"""
import numpy as np
import pandas as pd
import pytest

import horse_racing_predictions.exotic_longshot_phase11 as phase11


def test_canonical_race_id_uses_calendar_day_not_timestamp():
    source = pd.DataFrame(
        {
            "race_date": [
                "2024-12-31 09:00:00",
                "2024-12-31 15:00:00",
                "2023-12-31 23:59:59",
            ],
            "race_id": ["R7", "R7", "R7"],
        },
        index=[11, 7, 19],
    )
    actual = phase11.canonicalize_phase11_race_ids(source)
    assert actual["race_id"].tolist() == [
        "2024-12-31:R7", "2024-12-31:R7", "2023-12-31:R7"
    ]
    assert actual.index.equals(source.index)
    assert source["race_id"].tolist() == ["R7"] * 3


@pytest.mark.parametrize("bad_id", [None, "", "  "])
def test_canonical_race_id_rejects_missing_or_blank_ids(bad_id):
    frame = pd.DataFrame({
        "race_date": ["2024-12-31"], "race_id": [bad_id]
    })
    with pytest.raises(ValueError, match="race_id"):
        phase11.canonicalize_phase11_race_ids(frame)


def test_centering_groups_intraday_times_as_one_calendar_race():
    frame = pd.DataFrame({
        "race_id": ["R7", "R7", "R7", "R7"],
        "race_date": [
            "2024-12-31 09:00:00",
            "2024-12-31 15:00:00",
            "2023-12-31 09:00:00",
            "2023-12-31 15:00:00",
        ],
    }, index=[2, 4, 6, 8])
    raw = pd.Series([0.4, 0.2, 0.8, 0.4], index=frame.index)
    result = phase11.center_residual_within_race(frame, raw)
    np.testing.assert_allclose(result.to_numpy(), [0.1, -0.1, 0.2, -0.2])


def test_last_development_day_with_time_passes_preflight(monkeypatch):
    calls = []

    def stop_before_any_training(*args, **kwargs):
        calls.append(True)
        raise RuntimeError("synthetic preflight accepted")

    monkeypatch.setattr(
        phase11, "align_history_to_training_start", stop_before_any_training
    )
    synthetic = pd.DataFrame({
        "race_date": ["2024-12-31 23:59:59"],
        "race_id": ["R7"],
    })
    with pytest.raises(RuntimeError, match="synthetic preflight accepted"):
        phase11.evaluate_longshot_race_centered_phase11(synthetic)
    assert calls == [True]


def test_first_post_2024_day_rejected_before_any_training(monkeypatch):
    calls = []

    def stop_before_any_training(*args, **kwargs):
        calls.append(True)
        raise AssertionError("must not access training")

    monkeypatch.setattr(
        phase11, "align_history_to_training_start", stop_before_any_training
    )
    synthetic = pd.DataFrame({
        "race_date": ["2024-12-31 23:59:59", "2025-01-01 00:00:00"],
        "race_id": ["R7", "R8"],
    })
    with pytest.raises(ValueError, match="post-2024"):
        phase11.evaluate_longshot_race_centered_phase11(synthetic)
    assert not calls
