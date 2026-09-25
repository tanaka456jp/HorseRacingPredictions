from dataclasses import dataclass
import numpy as np
import pandas as pd

from .leakage import assert_leakage_safe

CURRENT_NUMERIC_FEATURES = (
    "distance_m",
    "post_position",
    "age",
    "carried_weight",
    "horse_weight",
    "horse_weight_delta",
)

CURRENT_CATEGORICAL_FEATURES = (
    "racecourse",
    "surface",
    "weather",
    "track_condition",
    "sex",
)

HISTORY_SUFFIXES = (
    "past_starts",
    "past_win_rate",
    "past_avg_finish",
    "days_since_seen",
)

@dataclass(frozen=True)
class FeatureBuildResult:
    frame: pd.DataFrame
    feature_columns: tuple[str, ...]

def _add_group_history(
    frame: pd.DataFrame,
    group_cols: list[str],
    prefix: str,
) -> tuple[pd.DataFrame, list[str]]:
    if any(column not in frame.columns for column in group_cols):
        return frame, []

    df = frame.copy()
    work = df[group_cols + ["_race_day"]].copy()
    work["_starts"] = 1
    work["_wins"] = df["is_winner"].astype(int)
    work["_finish"] = pd.to_numeric(
        df["finish_position"], errors="coerce"
    )
    work["_finish_valid"] = work["_finish"].notna().astype(int)
    work["_finish_sum"] = work["_finish"].fillna(0.0)

    daily = (
        work.groupby(
            group_cols + ["_race_day"],
            dropna=False,
            as_index=False,
        )
        .agg(
            daily_starts=("_starts", "sum"),
            daily_wins=("_wins", "sum"),
            daily_finish_sum=("_finish_sum", "sum"),
            daily_finish_count=("_finish_valid", "sum"),
        )
        .sort_values(group_cols + ["_race_day"])
    )

    grouped = daily.groupby(
        group_cols,
        dropna=False,
        sort=False,
    )
    daily[f"{prefix}_past_starts"] = (
        grouped["daily_starts"].cumsum() - daily["daily_starts"]
    )
    daily[f"{prefix}_past_wins"] = (
        grouped["daily_wins"].cumsum() - daily["daily_wins"]
    )
    daily["_past_finish_sum"] = (
        grouped["daily_finish_sum"].cumsum()
        - daily["daily_finish_sum"]
    )
    daily["_past_finish_count"] = (
        grouped["daily_finish_count"].cumsum()
        - daily["daily_finish_count"]
    )

    starts = daily[f"{prefix}_past_starts"].replace(0, np.nan)
    finish_count = daily["_past_finish_count"].replace(0, np.nan)
    daily[f"{prefix}_past_win_rate"] = (
        daily[f"{prefix}_past_wins"] / starts
    )
    daily[f"{prefix}_past_avg_finish"] = (
        daily["_past_finish_sum"] / finish_count
    )
    previous_day = grouped["_race_day"].shift(1)
    daily[f"{prefix}_days_since_seen"] = (
        daily["_race_day"] - previous_day
    ).dt.days

    generated = [
        f"{prefix}_past_starts",
        f"{prefix}_past_win_rate",
        f"{prefix}_past_avg_finish",
        f"{prefix}_days_since_seen",
    ]
    keep = group_cols + ["_race_day"] + generated
    return (
        df.merge(
            daily[keep],
            on=group_cols + ["_race_day"],
            how="left",
        ),
        generated,
    )

def build_pre_race_features(frame: pd.DataFrame) -> FeatureBuildResult:
    required = {"race_id", "race_date", "horse_name", "finish_position"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"missing feature source columns: {sorted(missing)}")

    df = frame.copy()
    df["_row_order"] = np.arange(len(df))
    df["race_date"] = pd.to_datetime(df["race_date"], errors="raise")
    df["_race_day"] = df["race_date"].dt.normalize()
    df["finish_position"] = pd.to_numeric(
        df["finish_position"], errors="coerce"
    )
    df["is_winner"] = df["finish_position"].eq(1).astype(int)

    for column in CURRENT_NUMERIC_FEATURES:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    for column in CURRENT_CATEGORICAL_FEATURES:
        if column in df.columns:
            df[column] = (
                df[column].astype("string").fillna("UNKNOWN")
            )

    if "distance_m" in df.columns:
        bucket = (df["distance_m"] // 200) * 200
        df["_distance_bucket"] = (
            bucket.astype("Int64").astype("string").fillna("UNKNOWN")
        )

    history_features: list[str] = []
    history_specs = [
        (["horse_name"], "horse"),
        (["jockey"], "jockey"),
        (["trainer"], "trainer"),
        (["horse_name", "surface"], "horse_surface"),
        (["horse_name", "racecourse"], "horse_course"),
        (["horse_name", "_distance_bucket"], "horse_distance"),
        (["jockey", "racecourse"], "jockey_course"),
        (["trainer", "racecourse"], "trainer_course"),
    ]

    for group_cols, prefix in history_specs:
        df, generated = _add_group_history(
            df,
            group_cols,
            prefix,
        )
        history_features.extend(generated)

    feature_columns = tuple(
        [c for c in CURRENT_NUMERIC_FEATURES if c in df.columns]
        + [c for c in CURRENT_CATEGORICAL_FEATURES if c in df.columns]
        + history_features
    )
    assert_leakage_safe(list(feature_columns))

    drop_columns = ["_row_order", "_race_day"]
    if "_distance_bucket" in df.columns:
        drop_columns.append("_distance_bucket")

    df = (
        df.sort_values("_row_order")
        .drop(columns=drop_columns)
        .reset_index(drop=True)
    )
    return FeatureBuildResult(
        frame=df,
        feature_columns=feature_columns,
    )
