"""Leakage-safe pedigree history features.

Breeding-registration IDs are used strictly as grouping/linkage keys and are
removed before model input. Outcomes from the current race day are never used
for another race on the same day; each lineage's daily aggregate enters history
only on subsequent calendar days.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PedigreeFeatureResult:
    frame: pd.DataFrame
    feature_columns: tuple[str, ...]
    matched_rows: int
    total_rows: int


def _daily_lineage_history(
    frame: pd.DataFrame,
    *,
    lineage_col: str,
    prefix: str,
) -> tuple[pd.DataFrame, list[str]]:
    df = frame.copy()
    valid = df[lineage_col].astype("string").fillna("").str.strip().ne("")
    if not valid.any():
        return df, []

    work = df.loc[
        valid,
        [lineage_col, "_race_day", "finish_position", "field_size"],
    ].copy()
    finish = pd.to_numeric(
        work["finish_position"],
        errors="coerce",
    )
    field = pd.to_numeric(
        work["field_size"],
        errors="coerce",
    )
    denominator = (field - 1.0).replace(0, np.nan)

    work["_starts"] = 1
    work["_wins"] = finish.eq(1).astype(int)
    work["_top3"] = finish.le(3).astype(int)
    work["_finish_pct"] = (
        (finish - 1.0) / denominator
    ).clip(lower=0.0, upper=1.0)
    work["_finish_pct_valid"] = work["_finish_pct"].notna().astype(int)
    work["_finish_pct_sum"] = work["_finish_pct"].fillna(0.0)

    daily = (
        work.groupby(
            [lineage_col, "_race_day"],
            dropna=False,
            as_index=False,
        )
        .agg(
            daily_starts=("_starts", "sum"),
            daily_wins=("_wins", "sum"),
            daily_top3=("_top3", "sum"),
            daily_finish_pct_sum=("_finish_pct_sum", "sum"),
            daily_finish_pct_count=("_finish_pct_valid", "sum"),
        )
        .sort_values(
            [lineage_col, "_race_day"],
            kind="stable",
        )
    )
    grouped = daily.groupby(
        lineage_col,
        dropna=False,
        sort=False,
    )

    daily[f"{prefix}_past_starts"] = (
        grouped["daily_starts"].cumsum()
        - daily["daily_starts"]
    )
    daily["_past_wins"] = (
        grouped["daily_wins"].cumsum()
        - daily["daily_wins"]
    )
    daily["_past_top3"] = (
        grouped["daily_top3"].cumsum()
        - daily["daily_top3"]
    )
    daily["_past_finish_pct_sum"] = (
        grouped["daily_finish_pct_sum"].cumsum()
        - daily["daily_finish_pct_sum"]
    )
    daily["_past_finish_pct_count"] = (
        grouped["daily_finish_pct_count"].cumsum()
        - daily["daily_finish_pct_count"]
    )

    starts = daily[f"{prefix}_past_starts"].replace(0, np.nan)
    finish_count = daily["_past_finish_pct_count"].replace(0, np.nan)
    daily[f"{prefix}_past_win_rate"] = daily["_past_wins"] / starts
    daily[f"{prefix}_past_top3_rate"] = daily["_past_top3"] / starts
    daily[f"{prefix}_past_avg_finish_percentile"] = (
        daily["_past_finish_pct_sum"] / finish_count
    )
    daily[f"{prefix}_days_since_seen"] = (
        daily["_race_day"]
        - grouped["_race_day"].shift(1)
    ).dt.days

    generated = [
        f"{prefix}_past_starts",
        f"{prefix}_past_win_rate",
        f"{prefix}_past_top3_rate",
        f"{prefix}_past_avg_finish_percentile",
        f"{prefix}_days_since_seen",
    ]
    keep = [lineage_col, "_race_day", *generated]
    merged = df.merge(
        daily[keep],
        on=[lineage_col, "_race_day"],
        how="left",
        sort=False,
    )
    return merged, generated


def attach_pedigree_history_features(
    frame: pd.DataFrame,
    pedigree: pd.DataFrame,
) -> PedigreeFeatureResult:
    """Attach sire/damsire prior-outcome features without exposing lineage IDs."""
    required = {
        "race_id",
        "race_date",
        "finish_position",
        "_jv_blood_registration_number",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(
            f"missing pedigree feature source columns: {sorted(missing)}"
        )

    pedigree_required = {
        "blood_registration_number",
        "sire_breeding_registration_number",
        "damsire_breeding_registration_number",
    }
    pedigree_missing = pedigree_required - set(pedigree.columns)
    if pedigree_missing:
        raise ValueError(
            "missing pedigree mapping columns: "
            f"{sorted(pedigree_missing)}"
        )

    df = frame.copy()
    df["_pedigree_row_order"] = np.arange(len(df))
    df["race_date"] = pd.to_datetime(
        df["race_date"],
        errors="raise",
    )
    df["_race_day"] = df["race_date"].dt.normalize()

    if "field_size" not in df.columns:
        df["field_size"] = (
            df.groupby("race_id")["race_id"]
            .transform("size")
            .astype(float)
        )

    mapping = pedigree[
        [
            "blood_registration_number",
            "sire_breeding_registration_number",
            "damsire_breeding_registration_number",
        ]
    ].drop_duplicates(
        subset=["blood_registration_number"],
        keep="last",
    )

    df = df.merge(
        mapping,
        left_on="_jv_blood_registration_number",
        right_on="blood_registration_number",
        how="left",
        sort=False,
    )
    matched = int(
        df["sire_breeding_registration_number"]
        .astype("string")
        .fillna("")
        .str.strip()
        .ne("")
        .sum()
    )

    generated: list[str] = []
    for lineage_col, prefix in (
        ("sire_breeding_registration_number", "sire"),
        ("damsire_breeding_registration_number", "damsire"),
    ):
        df, cols = _daily_lineage_history(
            df,
            lineage_col=lineage_col,
            prefix=prefix,
        )
        generated.extend(cols)

    forbidden_model_keys = {
        "blood_registration_number",
        "sire_breeding_registration_number",
        "damsire_breeding_registration_number",
    }
    if forbidden_model_keys.intersection(generated):
        raise AssertionError(
            "raw pedigree linkage IDs must never become model features"
        )

    df = (
        df.sort_values("_pedigree_row_order", kind="stable")
        .drop(
            columns=[
                "_pedigree_row_order",
                "_race_day",
                "blood_registration_number",
                "sire_breeding_registration_number",
                "damsire_breeding_registration_number",
            ],
            errors="ignore",
        )
        .reset_index(drop=True)
    )

    return PedigreeFeatureResult(
        frame=df,
        feature_columns=tuple(generated),
        matched_rows=matched,
        total_rows=int(len(df)),
    )
