import numpy as np
import pandas as pd

from horse_racing_predictions.calibration import (
    apply_temperature,
    fit_temperature,
    winner_log_loss,
)

def test_temperature_preserves_race_probability_sum():
    p = pd.Series([0.7, 0.2, 0.1, 0.4, 0.6])
    races = pd.Series(["R1", "R1", "R1", "R2", "R2"])
    out = apply_temperature(p, races, 1.5)
    sums = out.groupby(races).sum()
    assert np.allclose(sums.to_numpy(), [1.0, 1.0])

def test_temperature_fit_can_soften_overconfident_predictions():
    p = pd.Series([
        0.90, 0.05, 0.05,
        0.90, 0.05, 0.05,
        0.90, 0.05, 0.05,
    ])
    races = pd.Series([
        "R1", "R1", "R1",
        "R2", "R2", "R2",
        "R3", "R3", "R3",
    ])
    outcomes = pd.Series([
        0, 1, 0,
        0, 1, 0,
        1, 0, 0,
    ])
    temperature = fit_temperature(p, races, outcomes)
    assert temperature > 1.0
    before = winner_log_loss(p, races, outcomes)
    after = winner_log_loss(
        apply_temperature(p, races, temperature),
        races,
        outcomes,
    )
    assert after < before
