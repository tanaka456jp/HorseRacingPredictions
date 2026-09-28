from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .calibration import (
    apply_temperature,
    fit_temperature,
    winner_log_loss,
)
from .evaluation import brier_score, binary_log_loss
from .feature_window import align_history_to_training_start
from .features import build_pre_race_features
from .market_blend_research import normalized_market_probability
from .model_artifact import LoadedChampion
from .modeling import CatBoostRankingProbabilityModel


MARKET_CONTEXT_FEATURES = (
    "market_implied_probability",
    "market_log_probability",
    "market_probability_rank",
    "market_gap_to_favorite",
)


def _safe_float(value) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None


def _outcomes(frame: pd.DataFrame) -> pd.Series:
    return (
        pd.to_numeric(
            frame["finish_position"],
            errors="coerce",
        )
        .eq(1)
        .astype(int)
    )


def _quality(
    frame: pd.DataFrame,
    probability: pd.Series,
) -> dict:
    outcomes = _outcomes(frame)
    return {
        "winner_log_loss": _safe_float(
            winner_log_loss(
                probability,
                frame["race_id"],
                outcomes,
            )
        ),
        "binary_log_loss": _safe_float(
            binary_log_loss(
                probability,
                outcomes,
            )
        ),
        "brier": _safe_float(
            brier_score(
                probability,
                outcomes,
            )
        ),
    }


def add_market_context_features(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    if "win_odds" not in frame.columns:
        raise ValueError(
            "market-aware research requires win_odds"
        )

    out = frame.copy()
    market_frame = out.copy()
    if "decimal_odds" in market_frame.columns:
        market_frame["decimal_odds"] = pd.to_numeric(
            out["win_odds"],
            errors="raise",
        )
    else:
        market_frame = market_frame.rename(
            columns={"win_odds": "decimal_odds"}
        )
    market = normalized_market_probability(
        market_frame
    )
    clipped = market.clip(
        lower=1e-12,
        upper=1.0,
    )
    favorite = market.groupby(
        out["race_id"]
    ).transform("max")

    out["market_implied_probability"] = market
    out["market_log_probability"] = np.log(clipped)
    out["market_probability_rank"] = (
        market.groupby(out["race_id"])
        .rank(
            method="first",
            ascending=False,
        )
        .astype(float)
    )
    out["market_gap_to_favorite"] = (
        favorite - market
    )
    return out


def evaluate_market_aware_ranker_v11_development(
    history: pd.DataFrame,
    champion: LoadedChampion,
    *,
    challenger_iterations: int = 350,
    calibration_end: str = "2023-12-31",
    selection_start: str = "2024-01-01",
    selection_end: str = "2024-12-31",
) -> dict:
    if challenger_iterations < 1:
        raise ValueError(
            "challenger_iterations must be positive"
        )

    data = align_history_to_training_start(
        history,
        train_start=champion.manifest.train_start,
    )
    data["race_date"] = pd.to_datetime(
        data["race_date"],
        errors="raise",
    )
    data["finish_position"] = pd.to_numeric(
        data["finish_position"],
        errors="coerce",
    )
    data["win_odds"] = pd.to_numeric(
        data["win_odds"],
        errors="coerce",
    )
    data = data.loc[
        data["finish_position"].notna()
        & data["win_odds"].gt(1.0)
        & data["race_date"].le(
            pd.Timestamp(selection_end)
        )
    ].copy()
    if data.empty:
        raise ValueError(
            "market-aware Ranker v11 development history is empty"
        )

    enhanced = build_pre_race_features(
        data,
        experimental_ranker_v10=True,
    )
    base_frame = enhanced.frame.copy()
    market_frame = add_market_context_features(
        enhanced.frame
    )

    v10_features = tuple(
        enhanced.feature_columns
    )
    v11_features = (
        v10_features + MARKET_CONTEXT_FEATURES
    )

    train_end = pd.Timestamp(
        champion.manifest.train_end
    ).normalize()
    calibration_end_ts = pd.Timestamp(
        calibration_end
    ).normalize()
    selection_start_ts = pd.Timestamp(
        selection_start
    ).normalize()
    selection_end_ts = pd.Timestamp(
        selection_end
    ).normalize()

    if not (
        train_end
        < calibration_end_ts
        < selection_start_ts
        <= selection_end_ts
    ):
        raise ValueError(
            "invalid market-aware Ranker v11 development split"
        )

    dates = pd.to_datetime(
        base_frame["race_date"],
        errors="raise",
    )
    train_mask = dates.le(train_end)
    calibration_mask = (
        dates.gt(train_end)
        & dates.le(calibration_end_ts)
    )
    selection_mask = dates.between(
        selection_start_ts,
        selection_end_ts,
        inclusive="both",
    )

    v10_train = base_frame.loc[
        train_mask
    ].copy()
    v10_calibration = base_frame.loc[
        calibration_mask
    ].copy()
    v10_selection = base_frame.loc[
        selection_mask
    ].copy()

    v11_train = market_frame.loc[
        train_mask
    ].copy()
    v11_calibration = market_frame.loc[
        calibration_mask
    ].copy()
    v11_selection = market_frame.loc[
        selection_mask
    ].copy()

    if (
        v10_train.empty
        or v10_calibration.empty
        or v10_selection.empty
    ):
        raise ValueError(
            "market-aware Ranker v11 split contains an empty period"
        )

    v10 = CatBoostRankingProbabilityModel(
        list(v10_features),
        iterations=challenger_iterations,
    ).fit(
        v10_train,
        target_col="is_winner",
        race_col="race_id",
    )
    v11 = CatBoostRankingProbabilityModel(
        list(v11_features),
        iterations=challenger_iterations,
    ).fit(
        v11_train,
        target_col="is_winner",
        race_col="race_id",
    )

    v10_calibration_raw = (
        v10.predict_win_probability(
            v10_calibration,
            race_col="race_id",
        )
    )
    v11_calibration_raw = (
        v11.predict_win_probability(
            v11_calibration,
            race_col="race_id",
        )
    )
    v10_temperature = fit_temperature(
        v10_calibration_raw,
        v10_calibration["race_id"],
        _outcomes(v10_calibration),
    )
    v11_temperature = fit_temperature(
        v11_calibration_raw,
        v11_calibration["race_id"],
        _outcomes(v11_calibration),
    )

    v10_selection_raw = (
        v10.predict_win_probability(
            v10_selection,
            race_col="race_id",
        )
    )
    v11_selection_raw = (
        v11.predict_win_probability(
            v11_selection,
            race_col="race_id",
        )
    )
    v10_selection_probability = apply_temperature(
        v10_selection_raw,
        v10_selection["race_id"],
        v10_temperature,
    )
    v11_selection_probability = apply_temperature(
        v11_selection_raw,
        v11_selection["race_id"],
        v11_temperature,
    )
    market_selection_probability = (
        normalized_market_probability(
            v10_selection.rename(
                columns={
                    "win_odds": "decimal_odds"
                }
            )
        )
    )

    v10_quality = _quality(
        v10_selection,
        v10_selection_probability,
    )
    v11_quality = _quality(
        v11_selection,
        v11_selection_probability,
    )
    market_quality = _quality(
        v10_selection,
        market_selection_probability,
    )

    v11_vs_v10_loss = (
        float(v11_quality["winner_log_loss"])
        - float(v10_quality["winner_log_loss"])
    )
    v11_vs_market_loss = (
        float(v11_quality["winner_log_loss"])
        - float(market_quality["winner_log_loss"])
    )
    v11_vs_v10_brier = (
        float(v11_quality["brier"])
        - float(v10_quality["brier"])
    )
    v11_vs_market_brier = (
        float(v11_quality["brier"])
        - float(market_quality["brier"])
    )

    return {
        "status": (
            "research_only_market_aware_ranker_v11_development"
        ),
        "warning": (
            "Historical final win odds are used here only as a research "
            "market proxy. The 2025-2026 holdout is excluded before feature "
            "construction. This model must not be promoted to Forward Paper "
            "until equivalent pre-race odds features are reproduced from "
            "timestamped 0B31 snapshots."
        ),
        "training": {
            "train_start": champion.manifest.train_start,
            "train_end": champion.manifest.train_end,
            "rows": int(len(v10_train)),
            "races": int(
                v10_train["race_id"].nunique()
            ),
        },
        "calibration": {
            "period_start": str(
                v10_calibration[
                    "race_date"
                ].min().date()
            ),
            "period_end": str(
                v10_calibration[
                    "race_date"
                ].max().date()
            ),
            "rows": int(len(v10_calibration)),
            "races": int(
                v10_calibration[
                    "race_id"
                ].nunique()
            ),
            "v10_temperature": _safe_float(
                v10_temperature
            ),
            "v11_temperature": _safe_float(
                v11_temperature
            ),
        },
        "selection_2024": {
            "period_start": str(
                v10_selection[
                    "race_date"
                ].min().date()
            ),
            "period_end": str(
                v10_selection[
                    "race_date"
                ].max().date()
            ),
            "rows": int(len(v10_selection)),
            "races": int(
                v10_selection[
                    "race_id"
                ].nunique()
            ),
            "v10_quality": v10_quality,
            "v11_quality": v11_quality,
            "market_quality": market_quality,
            "v11_delta_vs_v10_winner_log_loss": (
                _safe_float(
                    v11_vs_v10_loss
                )
            ),
            "v11_delta_vs_market_winner_log_loss": (
                _safe_float(
                    v11_vs_market_loss
                )
            ),
            "v11_delta_vs_v10_brier": (
                _safe_float(
                    v11_vs_v10_brier
                )
            ),
            "v11_delta_vs_market_brier": (
                _safe_float(
                    v11_vs_market_brier
                )
            ),
            "v11_beats_v10_winner_log_loss": bool(
                v11_vs_v10_loss < 0.0
            ),
            "v11_beats_market_winner_log_loss": bool(
                v11_vs_market_loss < 0.0
            ),
            "v11_beats_v10_brier": bool(
                v11_vs_v10_brier < 0.0
            ),
            "v11_beats_market_brier": bool(
                v11_vs_market_brier < 0.0
            ),
            "development_gate_passed": bool(
                v11_vs_market_loss < 0.0
                and v11_vs_market_brier < 0.0
            ),
        },
        "features": {
            "v10_count": int(
                len(v10_features)
            ),
            "v11_count": int(
                len(v11_features)
            ),
            "market_feature_count": int(
                len(MARKET_CONTEXT_FEATURES)
            ),
            "market_feature_columns": list(
                MARKET_CONTEXT_FEATURES
            ),
        },
    }
