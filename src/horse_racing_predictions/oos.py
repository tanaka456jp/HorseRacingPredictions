from dataclasses import dataclass
import math
import numpy as np
import pandas as pd

from .calibration import (
    apply_isotonic,
    apply_temperature,
    fit_isotonic,
    fit_temperature,
)
from .leakage import assert_leakage_safe
from .modeling import (
    BaselineProbabilityModel,
    CatBoostProbabilityModel,
)
from .walkforward import expanding_walk_forward_splits


@dataclass(frozen=True)
class OOSResult:
    predictions: pd.DataFrame
    fold_count: int


def _race_certainty(probabilities: pd.Series) -> float:
    p = probabilities[probabilities > 0].astype(float)
    n = len(p)
    if n <= 1:
        return 1.0
    entropy = -float((p * p.map(math.log)).sum())
    maximum = math.log(n)
    if maximum <= 0:
        return 1.0
    return max(0.0, min(1.0, 1.0 - entropy / maximum))


def _split_fit_and_calibration(
    train: pd.DataFrame,
    calibration_dates: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = (
        pd.to_datetime(train["race_date"], errors="raise")
        .dt.normalize()
    )
    unique_dates = sorted(dates.unique())
    if calibration_dates <= 0 or len(unique_dates) <= calibration_dates + 2:
        return train, train.iloc[0:0].copy()
    calibration_set = set(unique_dates[-calibration_dates:])
    calibration = train.loc[dates.isin(calibration_set)].copy()
    fit = train.loc[~dates.isin(calibration_set)].copy()
    return fit, calibration


def _make_model(
    model_kind: str,
    feature_columns: list[str],
):
    if model_kind == "logit":
        return BaselineProbabilityModel(feature_columns)
    if model_kind == "catboost":
        return CatBoostProbabilityModel(feature_columns)
    raise ValueError(f"unknown model_kind: {model_kind}")


def generate_walk_forward_predictions(
    frame: pd.DataFrame,
    feature_columns: list[str] | tuple[str, ...],
    min_train_dates: int = 30,
    test_dates: int = 7,
    gap_dates: int = 0,
    model_version: str = "baseline-logit-v0",
    calibration_dates: int = 0,
    calibration_method: str | None = None,
    model_kind: str = "logit",
) -> OOSResult:
    feature_columns = list(feature_columns)
    assert_leakage_safe(feature_columns)

    if calibration_method is None:
        calibration_method = (
            "temperature" if calibration_dates > 0 else "none"
        )

    if calibration_method not in {"none", "temperature", "isotonic"}:
        raise ValueError(
            "calibration_method must be one of: none, temperature, isotonic"
        )

    required = {
        "race_id", "race_date", "horse_name", "finish_position",
        "win_odds", "is_winner",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"missing OOS columns: {sorted(missing)}")

    outputs = []
    fold_count = 0

    for fold_number, fold in enumerate(
        expanding_walk_forward_splits(
            frame,
            "race_date",
            min_train_dates=min_train_dates,
            test_dates=test_dates,
            gap_dates=gap_dates,
        ),
        start=1,
    ):
        train = frame.loc[fold.train_index].copy()
        test = frame.loc[fold.test_index].copy()
        model_train, calibration = _split_fit_and_calibration(
            train,
            calibration_dates=calibration_dates,
        )

        model = _make_model(
            model_kind,
            feature_columns,
        ).fit(
            model_train,
            target_col="is_winner",
        )

        calibration_start = pd.NaT
        temperature = np.nan
        calibrator = None

        if calibration_method != "none" and not calibration.empty:
            raw_cal = model.predict_win_probability(
                calibration,
                race_col="race_id",
            )
            calibration_start = pd.to_datetime(
                calibration["race_date"]
            ).min()

            if calibration_method == "temperature":
                temperature = fit_temperature(
                    raw_cal,
                    calibration["race_id"],
                    calibration["is_winner"],
                )
            elif calibration_method == "isotonic":
                calibrator = fit_isotonic(
                    raw_cal,
                    calibration["is_winner"],
                )

        raw_probability = model.predict_win_probability(
            test,
            race_col="race_id",
        )

        if calibration_method == "temperature" and not np.isnan(temperature):
            probability = apply_temperature(
                raw_probability,
                test["race_id"],
                float(temperature),
            )
        elif calibration_method == "isotonic" and calibrator is not None:
            probability = apply_isotonic(
                raw_probability,
                test["race_id"],
                calibrator,
            )
        else:
            probability = raw_probability

        out = test[
            ["race_id", "race_date", "horse_name", "finish_position", "win_odds"]
        ].copy()
        if "post_position" in test.columns:
            out["horse_id"] = (
                test["race_id"].astype(str)
                + "-"
                + test["post_position"].astype(str)
            )
        else:
            out["horse_id"] = (
                test["race_id"].astype(str)
                + "-"
                + test.groupby("race_id").cumcount().add(1).astype(str)
            )

        out["predicted_win_probability"] = probability
        out["decimal_odds"] = pd.to_numeric(
            out["win_odds"], errors="coerce"
        )
        out["model_version"] = f"{model_version}-fold{fold_number}"
        out["fold_number"] = fold_number
        out["train_end"] = pd.to_datetime(
            model_train["race_date"]
        ).max()
        out["calibration_start"] = calibration_start
        out["test_start"] = fold.test_start
        out["temperature"] = temperature
        out["calibration_method"] = calibration_method
        out["model_kind"] = model_kind

        certainty = probability.groupby(test["race_id"]).transform(
            _race_certainty
        )
        out["confidence"] = certainty
        outputs.append(out)
        fold_count += 1

    if not outputs:
        return OOSResult(pd.DataFrame(), 0)

    predictions = pd.concat(outputs, ignore_index=True)
    return OOSResult(predictions=predictions, fold_count=fold_count)
