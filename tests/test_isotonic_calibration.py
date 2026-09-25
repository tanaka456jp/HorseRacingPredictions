import numpy as np
import pandas as pd

from horse_racing_predictions.calibration import (
    apply_isotonic,
    fit_isotonic,
)
from horse_racing_predictions.oos import generate_walk_forward_predictions


def test_isotonic_output_is_race_normalized_and_monotonic():
    calibration_p = pd.Series([
        0.01, 0.02, 0.05, 0.10, 0.20, 0.40,
        0.01, 0.02, 0.05, 0.10, 0.20, 0.40,
    ])
    outcomes = pd.Series([
        0, 0, 0, 0, 0, 1,
        0, 0, 0, 0, 1, 1,
    ])
    calibrator = fit_isotonic(calibration_p, outcomes)

    test_p = pd.Series(
        [0.05, 0.15, 0.30, 0.05, 0.15, 0.30],
        index=[10, 11, 12, 20, 21, 22],
    )
    race_ids = pd.Series(
        ["R1", "R1", "R1", "R2", "R2", "R2"],
        index=test_p.index,
    )

    calibrated = apply_isotonic(test_p, race_ids, calibrator)

    sums = calibrated.groupby(race_ids).sum()
    assert np.allclose(sums.to_numpy(), [1.0, 1.0])
    assert calibrated.loc[10] <= calibrated.loc[11] <= calibrated.loc[12]
    assert calibrated.loc[20] <= calibrated.loc[21] <= calibrated.loc[22]


def test_walk_forward_isotonic_uses_only_prior_calibration_dates():
    rows = []
    for day in range(1, 21):
        winner = day % 3
        for horse in range(3):
            rows.append({
                "race_id": f"R{day:02d}",
                "race_date": pd.Timestamp("2026-01-01") + pd.Timedelta(days=day-1),
                "horse_name": f"H{horse}",
                "finish_position": 1 if horse == winner else horse + 2,
                "win_odds": 2.0 + horse,
                "is_winner": 1 if horse == winner else 0,
                "x": float(horse + day % 4),
            })

    frame = pd.DataFrame(rows)
    result = generate_walk_forward_predictions(
        frame,
        ["x"],
        min_train_dates=10,
        test_dates=2,
        calibration_dates=3,
        calibration_method="isotonic",
        model_kind="logit",
        model_version="test-isotonic",
    )

    assert result.fold_count > 0
    assert not result.predictions.empty
    assert (
        pd.to_datetime(result.predictions["train_end"])
        < pd.to_datetime(result.predictions["calibration_start"])
    ).all()
    assert (
        pd.to_datetime(result.predictions["calibration_start"])
        < pd.to_datetime(result.predictions["test_start"])
    ).all()
    assert (
        result.predictions["calibration_method"] == "isotonic"
    ).all()
    sums = (
        result.predictions
        .groupby("race_id")["predicted_win_probability"]
        .sum()
    )
    assert (sums.sub(1.0).abs() < 1e-9).all()
