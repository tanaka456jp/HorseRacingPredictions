from __future__ import annotations

import math
import numpy as np
import pandas as pd

from .features import build_pre_race_features
from .model_artifact import LoadedChampion


def build_future_feature_frame(
    history: pd.DataFrame,
    entries: pd.DataFrame,
    required_feature_columns: tuple[str, ...] | list[str],
) -> pd.DataFrame:
    if history.empty:
        raise ValueError("historical frame must not be empty")
    if entries.empty:
        raise ValueError("future entries must not be empty")

    history = history.copy()
    entries = entries.copy()
    history["race_date"] = pd.to_datetime(
        history["race_date"], errors="raise"
    )
    entries["race_date"] = pd.to_datetime(
        entries["race_date"], errors="raise"
    )

    history_end = history["race_date"].max().normalize()
    entry_start = entries["race_date"].min().normalize()
    if entry_start <= history_end:
        raise ValueError(
            "future entries must be strictly later than historical data"
        )

    entries["_prediction_row"] = True
    history["_prediction_row"] = False

    if "finish_position" not in entries:
        entries["finish_position"] = np.nan
    if "win_odds" not in entries:
        entries["win_odds"] = np.nan

    combined = pd.concat(
        [history, entries],
        ignore_index=True,
        sort=False,
    )
    built = build_pre_race_features(combined)
    future = built.frame.loc[
        built.frame["_prediction_row"].fillna(False)
    ].copy()

    missing = set(required_feature_columns) - set(future.columns)
    if missing:
        raise ValueError(
            "future feature frame is missing Champion features: "
            f"{sorted(missing)}"
        )
    return future


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


def predict_future_entries(
    champion: LoadedChampion,
    history: pd.DataFrame,
    entries: pd.DataFrame,
) -> pd.DataFrame:
    future = build_future_feature_frame(
        history,
        entries,
        champion.manifest.feature_columns,
    )
    probability = champion.model.predict_win_probability(
        future,
        race_col="race_id",
    )

    output = future[
        ["race_id", "race_date", "horse_name"]
    ].copy()
    if "post_position" in future.columns:
        output["horse_id"] = (
            future["race_id"].astype(str)
            + "-"
            + future["post_position"].astype("Int64").astype(str)
        )
    else:
        output["horse_id"] = (
            future["race_id"].astype(str)
            + "-"
            + future.groupby("race_id").cumcount().add(1).astype(str)
        )

    output["predicted_win_probability"] = probability
    output["confidence"] = probability.groupby(
        future["race_id"]
    ).transform(_race_certainty)
    output["model_version"] = champion.manifest.model_version
    output["experiment_id"] = champion.manifest.experiment_id
    output["history_cutoff"] = champion.manifest.train_end

    sums = output.groupby("race_id")[
        "predicted_win_probability"
    ].sum()
    if not (sums.sub(1.0).abs() < 1e-9).all():
        raise RuntimeError(
            "future race probabilities failed normalization"
        )
    return output.reset_index(drop=True)
