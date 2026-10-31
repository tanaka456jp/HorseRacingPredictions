"""Verify existing historical model features actually match past-only builder.

Column-name allowlisting is necessary but insufficient: a caller might
overwrite a *legitimately named* 'horse_past_starts' with target-race winner
labels. Independently reconstruct all engineered historical fields from the
source results in chronological order before any model is fitted.
Synthetic-only CI; no data acquisition, publication, or trainer authorization.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .features import build_pre_race_features
from .odds_free_chronological_eval import (
    _HISTORICAL_ALLOWED_FEATURES, _validate_research_features,
)

_DERIVED_CURRENT = frozenset({
    "field_size", "relative_post_position",
    "carried_weight_vs_race_mean", "horse_weight_vs_race_mean",
})


def assert_pre_race_engineering_reproducible(
    frame: pd.DataFrame, feature_columns: tuple[str, ...],
) -> None:
    """Reject values inconsistent with outcome-shifted historical engineering.

    Must run before CatBoost or baseline fit. Does not let the model's labels
    or future outcomes become features; rebuilding reads source historical
    result labels solely to derive genuinely *earlier-date* form.
    """
    _validate_research_features(feature_columns)
    if (not isinstance(frame, pd.DataFrame)
            or frame.empty or frame.columns.duplicated().any()
            or not {"race_id", "race_date", "horse_name", "finish_position"}
            .issubset(frame.columns)):
        raise ValueError("RESEARCH_FEATURE_SOURCE_INVALID")
    audited = [
        name for name in feature_columns
        if name in _HISTORICAL_ALLOWED_FEATURES
        or name in _DERIVED_CURRENT
    ]
    if not audited:
        return
    stripped = frame.drop(
        columns=[c for c in frame.columns
                 if c in _HISTORICAL_ALLOWED_FEATURES
                 or c in _DERIVED_CURRENT],
        errors="ignore",
    )
    # The optional experimental ranker uses the same temporal shift,
    # but additional interaction prefixes and finish percentile signals.
    experimental = any(
        name.startswith((
            "horse_jockey_", "jockey_trainer_", "jockey_surface_",
            "trainer_surface_", "jockey_distance_", "trainer_distance_",
        )) or "finish_percentile" in name
        for name in audited
    )
    rebuilt = build_pre_race_features(
        stripped, experimental_ranker_v10=experimental,
    ).frame
    if len(rebuilt) != len(frame):
        raise ValueError("RESEARCH_HISTORICAL_FEATURE_ROWS_CHANGED")
    for name in audited:
        if name not in rebuilt.columns or name not in frame.columns:
            raise ValueError("RESEARCH_HISTORICAL_FEATURE_NOT_REPRODUCIBLE")
        original = pd.to_numeric(frame[name], errors="coerce").to_numpy(
            dtype=float
        )
        actual = pd.to_numeric(rebuilt[name], errors="coerce").to_numpy(
            dtype=float
        )
        if not np.allclose(
            original, actual, atol=1e-10, rtol=1e-10, equal_nan=True,
        ):
            raise ValueError("RESEARCH_HISTORICAL_FEATURE_NOT_REPRODUCIBLE")
