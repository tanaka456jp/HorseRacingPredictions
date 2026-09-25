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
    "field_size",
    "relative_post_position",
    "carried_weight_vs_race_mean",
    "horse_weight_vs_race_mean",
)

CURRENT_CATEGORICAL_FEATURES = (
    "racecourse",
    "surface",
    "weather",
    "track_condition",
    "sex",
    "race_class",
    "graded_race",
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

    grouped = daily.groupby(group_cols, dropna=False, sort=False)
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

def _add_recent_horse_form(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str]]:
    if "horse_name" not in frame.columns:
        return frame, []

    df = frame.copy()
    source = pd.DataFrame({
        "horse_name": df["horse_name"],
        "_race_day": df["_race_day"],
        "_finish": pd.to_numeric(
            df["finish_position"], errors="coerce"
        ),
        "_is_win": df["is_winner"].astype(float),
        "_is_top3": pd.to_numeric(
            df["finish_position"], errors="coerce"
        ).le(3).astype(float),
    })

    optional = {
        "_last_3f": "last_3f",
        "_early_ratio": "_early_position_ratio",
        "_late_ratio": "_late_position_ratio",
    }
    for target, source_col in optional.items():
        if source_col in df.columns:
            source[target] = pd.to_numeric(
                df[source_col], errors="coerce"
            )

    aggregations = {
        "finish": ("_finish", "mean"),
        "win": ("_is_win", "mean"),
        "top3": ("_is_top3", "mean"),
    }
    if "_last_3f" in source.columns:
        aggregations["last_3f"] = ("_last_3f", "mean")
    if "_early_ratio" in source.columns:
        aggregations["early_ratio"] = ("_early_ratio", "mean")
    if "_late_ratio" in source.columns:
        aggregations["late_ratio"] = ("_late_ratio", "mean")

    daily = (
        source.groupby(
            ["horse_name", "_race_day"],
            dropna=False,
            as_index=False,
        )
        .agg(**aggregations)
        .sort_values(["horse_name", "_race_day"])
    )

    generated: list[str] = []
    grouped = daily.groupby("horse_name", dropna=False, sort=False)

    for window in (3, 5):
        metrics = {
            f"horse_recent_finish_mean_{window}": "finish",
            f"horse_recent_win_rate_{window}": "win",
            f"horse_recent_top3_rate_{window}": "top3",
        }
        if "last_3f" in daily.columns:
            metrics[f"horse_recent_last_3f_mean_{window}"] = "last_3f"
        if "early_ratio" in daily.columns:
            metrics[f"horse_recent_early_ratio_mean_{window}"] = "early_ratio"
        if "late_ratio" in daily.columns:
            metrics[f"horse_recent_late_ratio_mean_{window}"] = "late_ratio"

        for output, metric in metrics.items():
            daily[output] = grouped[metric].transform(
                lambda x, w=window: x.shift(1).rolling(
                    w, min_periods=1
                ).mean()
            )
            generated.append(output)

    if "last_3f" in daily.columns:
        daily["horse_recent_last_3f_best_5"] = grouped[
            "last_3f"
        ].transform(
            lambda x: x.shift(1).rolling(5, min_periods=1).min()
        )
        generated.append("horse_recent_last_3f_best_5")

    if {
        "horse_recent_finish_mean_3",
        "horse_recent_finish_mean_5",
    }.issubset(daily.columns):
        daily["horse_recent_finish_trend_3_vs_5"] = (
            daily["horse_recent_finish_mean_3"]
            - daily["horse_recent_finish_mean_5"]
        )
        generated.append("horse_recent_finish_trend_3_vs_5")

    keep = ["horse_name", "_race_day"] + generated
    return (
        df.merge(
            daily[keep],
            on=["horse_name", "_race_day"],
            how="left",
        ),
        generated,
    )

def _prepare_race_relative_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["field_size"] = out.groupby("race_id")["race_id"].transform(
        "size"
    ).astype(float)

    if "post_position" in out.columns:
        denominator = out["field_size"].replace(0, np.nan)
        out["relative_post_position"] = (
            pd.to_numeric(out["post_position"], errors="coerce")
            / denominator
        )

    if "carried_weight" in out.columns:
        weight = pd.to_numeric(out["carried_weight"], errors="coerce")
        race_mean = weight.groupby(out["race_id"]).transform("mean")
        out["carried_weight_vs_race_mean"] = weight - race_mean

    if "horse_weight" in out.columns:
        weight = pd.to_numeric(out["horse_weight"], errors="coerce")
        race_mean = weight.groupby(out["race_id"]).transform("mean")
        out["horse_weight_vs_race_mean"] = weight - race_mean

    return out

def _prepare_postrace_history_sources(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for column in (
        "corner_1", "corner_2", "corner_3", "corner_4", "last_3f"
    ):
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")

    field = out["field_size"].replace(0, np.nan)

    early_cols = [
        c for c in ("corner_1", "corner_2")
        if c in out.columns
    ]
    late_cols = [
        c for c in ("corner_3", "corner_4")
        if c in out.columns
    ]
    if early_cols:
        out["_early_position_ratio"] = (
            out[early_cols].mean(axis=1) / field
        )
    if late_cols:
        out["_late_position_ratio"] = (
            out[late_cols].mean(axis=1) / field
        )
    return out

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

    for column in (
        "distance_m", "post_position", "age", "carried_weight",
        "horse_weight", "horse_weight_delta", "last_3f",
        "corner_1", "corner_2", "corner_3", "corner_4",
    ):
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    for column in CURRENT_CATEGORICAL_FEATURES:
        if column in df.columns:
            df[column] = (
                df[column].astype("string").fillna("UNKNOWN")
            )

    df = _prepare_race_relative_features(df)
    df = _prepare_postrace_history_sources(df)

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
        df, generated = _add_group_history(df, group_cols, prefix)
        history_features.extend(generated)

    df, recent_features = _add_recent_horse_form(df)
    history_features.extend(recent_features)

    feature_columns = tuple(
        [c for c in CURRENT_NUMERIC_FEATURES if c in df.columns]
        + [c for c in CURRENT_CATEGORICAL_FEATURES if c in df.columns]
        + history_features
    )
    assert_leakage_safe(list(feature_columns))

    drop_columns = [
        "_row_order", "_race_day", "_early_position_ratio",
        "_late_position_ratio",
    ]
    if "_distance_bucket" in df.columns:
        drop_columns.append("_distance_bucket")
    drop_columns = [c for c in drop_columns if c in df.columns]

    df = (
        df.sort_values("_row_order")
        .drop(columns=drop_columns)
        .reset_index(drop=True)
    )
    return FeatureBuildResult(
        frame=df,
        feature_columns=feature_columns,
    )
