import math
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression


def _renormalize_by_race(
    values: pd.Series,
    race_ids: pd.Series,
) -> pd.Series:
    values = values.astype(float).clip(lower=1e-12)
    totals = values.groupby(race_ids).transform("sum")
    return (values / totals.replace(0, np.nan)).fillna(0.0)


def apply_temperature(
    probabilities: pd.Series,
    race_ids: pd.Series,
    temperature: float,
) -> pd.Series:
    if temperature <= 0:
        raise ValueError("temperature must be positive")

    p = probabilities.astype(float).clip(lower=1e-12)
    logits = np.log(p) / float(temperature)
    logits = pd.Series(logits, index=probabilities.index, dtype=float)
    race_max = logits.groupby(race_ids).transform("max")
    exp_score = np.exp(logits - race_max)
    return _renormalize_by_race(exp_score, race_ids)


def winner_log_loss(
    probabilities: pd.Series,
    race_ids: pd.Series,
    outcomes: pd.Series,
) -> float:
    frame = pd.DataFrame({
        "race_id": race_ids.astype(str),
        "p": probabilities.astype(float).clip(lower=1e-12, upper=1.0),
        "winner": outcomes.astype(int),
    })
    winner_p = (
        frame.loc[frame["winner"] == 1]
        .groupby("race_id")["p"]
        .sum()
    )
    race_count = frame["race_id"].nunique()
    if race_count == 0 or len(winner_p) != race_count:
        raise ValueError("each calibration race must contain exactly one winner")
    return float(-np.log(winner_p.clip(lower=1e-12)).mean())


def fit_temperature(
    probabilities: pd.Series,
    race_ids: pd.Series,
    outcomes: pd.Series,
    candidates: np.ndarray | None = None,
) -> float:
    if candidates is None:
        candidates = np.geomspace(0.40, 3.00, 49)

    best_temperature = 1.0
    best_loss = math.inf

    for candidate in candidates:
        candidate = float(candidate)
        calibrated = apply_temperature(
            probabilities,
            race_ids,
            candidate,
        )
        loss = winner_log_loss(calibrated, race_ids, outcomes)
        if loss < best_loss:
            best_loss = loss
            best_temperature = candidate

    return best_temperature


def fit_isotonic(
    probabilities: pd.Series,
    outcomes: pd.Series,
) -> IsotonicRegression:
    p = probabilities.astype(float).clip(lower=1e-12, upper=1.0)
    y = outcomes.astype(int)
    if len(p) == 0:
        raise ValueError("isotonic calibration requires samples")
    if y.nunique() < 2:
        raise ValueError("isotonic calibration requires both classes")

    calibrator = IsotonicRegression(
        y_min=1e-9,
        y_max=1.0 - 1e-9,
        out_of_bounds="clip",
        increasing=True,
    )
    calibrator.fit(p.to_numpy(), y.to_numpy())
    return calibrator


def apply_isotonic(
    probabilities: pd.Series,
    race_ids: pd.Series,
    calibrator: IsotonicRegression,
) -> pd.Series:
    raw = probabilities.astype(float).clip(lower=1e-12, upper=1.0)
    calibrated = pd.Series(
        calibrator.predict(raw.to_numpy()),
        index=probabilities.index,
        dtype=float,
    )
    return _renormalize_by_race(calibrated, race_ids)
