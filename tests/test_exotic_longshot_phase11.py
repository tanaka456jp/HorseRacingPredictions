from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from horse_racing_predictions.exotic_longshot_phase11 import (
    center_residual_within_race,
)


def test_centering_is_race_relative_zero_sum_and_order_preserving():
    frame = pd.DataFrame(
        {"race_id": ["B", "A", "B", "A", "C"],
         "finish_position": [1, 2, 3, 4, 5]},
        index=[7, 2, 9, 4, 12],
    )
    raw = pd.Series([0.4, 0.3, 0.2, -0.1, 0.9], index=frame.index)
    centered = center_residual_within_race(frame, raw)
    np.testing.assert_allclose(
        centered.to_numpy(), [0.1, 0.2, -0.1, -0.2, 0.0],
    )
    assert centered.index.equals(frame.index)
    assert centered.groupby(frame["race_id"]).sum().abs().max() < 1e-12
    shifted = raw + frame["race_id"].map(
        {"A": 10.0, "B": -20.0, "C": 30.0}
    )
    np.testing.assert_allclose(
        center_residual_within_race(frame, shifted).to_numpy(),
        centered.to_numpy(),
    )
    changed = frame.copy()
    changed["finish_position"] = [9, 8, 7, 6, 5]
    pd.testing.assert_series_equal(
        center_residual_within_race(changed, raw), centered
    )


def test_centering_fails_closed_on_bad_inputs():
    frame = pd.DataFrame({"race_id": ["A", "A"]}, index=[3, 4])
    with pytest.raises(ValueError, match="index"):
        center_residual_within_race(frame, pd.Series([0.1, 0.2]))
    with pytest.raises(ValueError, match="non-finite"):
        center_residual_within_race(
            frame, pd.Series([0.1, np.inf], index=frame.index)
        )
    with pytest.raises(ValueError, match="race_id"):
        center_residual_within_race(
            frame.drop(columns="race_id"),
            pd.Series([0.1, 0.2], index=frame.index),
        )


def test_phase11_does_not_change_paper_or_final_holdout():
    source = Path(
        "src/horse_racing_predictions/exotic_longshot_phase11.py"
    ).read_text(encoding="utf-8")
    request = Path(
        "research/exotic_longshot_phase11_request.txt"
    ).read_text(encoding="utf-8")
    assert "oof_years=ROLLING_RESIDUAL_OOF_YEARS" in source
    assert '"final_holdout": "2025-2026 untouched"' in source
    assert '"forward_paper": "unchanged"' in source
    assert "2025-2026" in request
    assert "subtract within-race longshot residual mean" in source
