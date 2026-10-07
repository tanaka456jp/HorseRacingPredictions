from pathlib import Path

import numpy as np
import pandas as pd

from horse_racing_predictions.exotic_longshot_phase9 import (
    RESIDUAL_OOF_YEARS,
    add_residual_overlay_features,
    annual_oof_masks,
)


def test_annual_oof_masks_use_only_prior_years_for_training():
    dates = pd.Series(pd.to_datetime([
        "2017-12-31",
        "2018-01-01",
        "2018-12-31",
        "2019-01-01",
    ]))
    train, validation = annual_oof_masks(
        dates,
        2018,
    )
    assert train.tolist() == [
        True,
        False,
        False,
        False,
    ]
    assert validation.tolist() == [
        False,
        True,
        True,
        False,
    ]
    assert not bool(
        (train & validation).any()
    )


def test_residual_overlay_features_are_outcome_independent():
    frame = pd.DataFrame({
        "race_id": ["R1", "R1", "R2", "R2"],
        "finish_position": [1, 8, 2, 9],
        "market_implied_probability": [0.10, 0.05, 0.12, 0.06],
    })
    baseline = pd.Series(
        [0.30, 0.12, 0.28, 0.15],
        index=frame.index,
    )
    changed = frame.copy()
    changed["finish_position"] = [9, 1, 8, 2]

    original, generated = add_residual_overlay_features(
        frame,
        baseline,
    )
    changed_out, _ = add_residual_overlay_features(
        changed,
        baseline,
    )

    pd.testing.assert_frame_equal(
        original[list(generated)],
        changed_out[list(generated)],
    )
    assert np.isclose(
        original[
            "residual_baseline_vs_longshot_race_mean"
        ].iloc[0],
        0.09,
    )


def test_phase9_oof_years_are_fixed_before_evaluation():
    assert RESIDUAL_OOF_YEARS == (
        2018,
        2019,
        2020,
        2021,
        2022,
    )


def test_phase9_protocol_preserves_final_holdout_and_forward_paper():
    source = Path(
        "src/horse_racing_predictions/exotic_longshot_phase9.py"
    ).read_text(encoding="utf-8")
    request = Path(
        "research/exotic_longshot_phase9_request.txt"
    ).read_text(encoding="utf-8")

    assert "annual out-of-fold" in source
    assert '"2025-2026 untouched"' in source
    assert '"forward_paper": "unchanged"' in source
    assert "2018-2022" in request
    assert "2025-2026" in request
    assert "Forward Paper" in request
