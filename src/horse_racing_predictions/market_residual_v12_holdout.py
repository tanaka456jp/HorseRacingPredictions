from __future__ import annotations

import math

import pandas as pd

from .evaluation import brier_score, binary_log_loss
from .feature_window import align_history_to_training_start
from .features import build_pre_race_features
from .market_aware_ranker_v11 import (
    MARKET_CONTEXT_FEATURES,
    add_market_context_features,
)
from .market_blend_research import normalized_market_probability
from .market_residual_v12 import (
    MarketResidualRegressor,
    residual_adjusted_probability,
)
from .calibration import winner_log_loss
from .model_artifact import LoadedChampion


FIXED_GAMMA = 4.0


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


def _evaluate_period(
    frame: pd.DataFrame,
    model: MarketResidualRegressor,
    *,
    gamma: float,
) -> dict:
    market = normalized_market_probability(
        frame.rename(
            columns={"win_odds": "decimal_odds"}
        )
    )
    residual = model.predict(frame)
    adjusted = residual_adjusted_probability(
        frame,
        market,
        residual,
        gamma=gamma,
    )

    market_quality = _quality(frame, market)
    residual_quality = _quality(frame, adjusted)

    log_loss_delta = (
        float(residual_quality["winner_log_loss"])
        - float(market_quality["winner_log_loss"])
    )
    brier_delta = (
        float(residual_quality["brier"])
        - float(market_quality["brier"])
    )

    return {
        "period_start": str(
            frame["race_date"].min().date()
        ),
        "period_end": str(
            frame["race_date"].max().date()
        ),
        "rows": int(len(frame)),
        "races": int(
            frame["race_id"].nunique()
        ),
        "market_quality": market_quality,
        "residual_quality": residual_quality,
        "winner_log_loss_delta_vs_market": _safe_float(
            log_loss_delta
        ),
        "brier_delta_vs_market": _safe_float(
            brier_delta
        ),
        "beats_market_winner_log_loss": bool(
            log_loss_delta < 0.0
        ),
        "beats_market_brier": bool(
            brier_delta < 0.0
        ),
        "residual_prediction_mean": _safe_float(
            residual.mean()
        ),
        "residual_prediction_std": _safe_float(
            residual.std(ddof=0)
        ),
    }


def evaluate_market_residual_v12_holdout(
    history: pd.DataFrame,
    champion: LoadedChampion,
    *,
    iterations: int = 350,
    fixed_gamma: float = FIXED_GAMMA,
    holdout_start: str = "2025-01-01",
    holdout_end: str | None = None,
) -> dict:
    if iterations < 1:
        raise ValueError(
            "iterations must be positive"
        )
    if fixed_gamma != FIXED_GAMMA:
        raise ValueError(
            "v12 holdout confirmation must use fixed gamma=4.0 "
            "selected before opening the holdout"
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
    ].copy()
    if data.empty:
        raise ValueError(
            "market residual v12 holdout history is empty"
        )

    enhanced = build_pre_race_features(
        data,
        experimental_ranker_v10=True,
    )
    frame = add_market_context_features(
        enhanced.frame
    )
    features = (
        tuple(enhanced.feature_columns)
        + MARKET_CONTEXT_FEATURES
    )

    train_end = pd.Timestamp(
        champion.manifest.train_end
    ).normalize()
    start = pd.Timestamp(
        holdout_start
    ).normalize()
    end = (
        pd.Timestamp(holdout_end).normalize()
        if holdout_end is not None
        else pd.to_datetime(
            frame["race_date"],
            errors="raise",
        ).max().normalize()
    )
    if start <= train_end:
        raise ValueError(
            "holdout must begin after train_end"
        )
    if end < start:
        raise ValueError(
            "holdout_end must be on or after holdout_start"
        )

    dates = pd.to_datetime(
        frame["race_date"],
        errors="raise",
    )
    train = frame.loc[
        dates.le(train_end)
    ].copy()
    holdout = frame.loc[
        dates.between(
            start,
            end,
            inclusive="both",
        )
    ].copy()
    if train.empty or holdout.empty:
        raise ValueError(
            "v12 holdout split contains an empty period"
        )

    train_market = normalized_market_probability(
        train.rename(
            columns={"win_odds": "decimal_odds"}
        )
    )
    train_target = (
        _outcomes(train).astype(float)
        - train_market
    )

    model = MarketResidualRegressor(
        list(features),
        iterations=iterations,
    ).fit(
        train,
        train_target,
    )

    combined = _evaluate_period(
        holdout,
        model,
        gamma=fixed_gamma,
    )

    yearly: list[dict] = []
    for year in sorted(
        int(value)
        for value in holdout["race_date"].dt.year.unique()
    ):
        period = holdout.loc[
            holdout["race_date"].dt.year.eq(year)
        ].copy()
        if period.empty:
            continue
        yearly.append({
            "year": year,
            **_evaluate_period(
                period,
                model,
                gamma=fixed_gamma,
            ),
        })

    required_years = {
        2025,
        2026,
    }
    years_present = {
        row["year"]
        for row in yearly
    }
    yearly_gate = bool(
        required_years.issubset(years_present)
        and all(
            row["beats_market_winner_log_loss"]
            and row["beats_market_brier"]
            for row in yearly
            if row["year"] in required_years
        )
    )
    combined_gate = bool(
        combined["beats_market_winner_log_loss"]
        and combined["beats_market_brier"]
    )

    return {
        "status": (
            "research_only_market_residual_v12_holdout_confirmation"
        ),
        "warning": (
            "This is a one-time confirmation of the frozen residual v12 "
            "selected before opening the 2025-2026 holdout. The model is "
            "retrained only on the original 2017-2021 training period and "
            "uses fixed gamma=4.0. Historical final odds remain a research "
            "market proxy; this is not verified live profitability and must "
            "not be promoted to Forward Paper until equivalent timestamped "
            "0B31 pre-race inputs reproduce the signal."
        ),
        "training": {
            "train_start": champion.manifest.train_start,
            "train_end": champion.manifest.train_end,
            "rows": int(len(train)),
            "races": int(
                train["race_id"].nunique()
            ),
            "feature_count": int(
                len(features)
            ),
        },
        "fixed_parameters": {
            "gamma": float(
                fixed_gamma
            ),
            "iterations": int(
                iterations
            ),
        },
        "holdout_combined": combined,
        "holdout_yearly": yearly,
        "confirmation_gate_passed": bool(
            combined_gate and yearly_gate
        ),
    }
