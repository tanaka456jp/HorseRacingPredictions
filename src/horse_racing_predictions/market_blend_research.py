from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .calibration import (
    apply_temperature,
    fit_temperature,
    winner_log_loss,
)
from .champion_diagnostics import (
    build_frozen_champion_predictions,
    race_certainty,
)
from .config import StrategyConfig
from .evaluation import brier_score, binary_log_loss
from .model_artifact import LoadedChampion


BLEND_ALPHAS = tuple(
    float(value)
    for value in np.linspace(0.0, 1.0, 41)
)

EV_THRESHOLDS = (
    1.05,
    1.10,
    1.15,
    1.20,
    1.25,
    1.30,
    1.40,
    1.50,
    1.75,
    2.00,
)


def _safe_float(value) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None


def normalized_market_probability(
    frame: pd.DataFrame,
) -> pd.Series:
    odds = pd.to_numeric(
        frame["decimal_odds"],
        errors="coerce",
    )
    inverse = 1.0 / odds.where(odds > 1.0)
    denominator = inverse.groupby(
        frame["race_id"]
    ).transform("sum")
    market = (
        inverse / denominator.replace(0, pd.NA)
    ).fillna(0.0)
    return pd.Series(
        market,
        index=frame.index,
        dtype=float,
    )


def blend_probability(
    model_probability: pd.Series,
    market_probability: pd.Series,
    alpha: float,
) -> pd.Series:
    if not 0.0 <= float(alpha) <= 1.0:
        raise ValueError("alpha must be between 0 and 1")
    if not model_probability.index.equals(
        market_probability.index
    ):
        raise ValueError(
            "model and market probabilities must share the same index"
        )
    return (
        float(alpha) * model_probability.astype(float)
        + (1.0 - float(alpha))
        * market_probability.astype(float)
    )


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


def _alpha_sweep(
    frame: pd.DataFrame,
    model_probability: pd.Series,
    market_probability: pd.Series,
    *,
    alphas: tuple[float, ...] = BLEND_ALPHAS,
) -> list[dict]:
    outcomes = _outcomes(frame)
    rows: list[dict] = []
    for alpha in alphas:
        blended = blend_probability(
            model_probability,
            market_probability,
            alpha,
        )
        rows.append({
            "alpha_model_weight": float(alpha),
            "alpha_market_weight": float(1.0 - alpha),
            "winner_log_loss": _safe_float(
                winner_log_loss(
                    blended,
                    frame["race_id"],
                    outcomes,
                )
            ),
            "binary_log_loss": _safe_float(
                binary_log_loss(
                    blended,
                    outcomes,
                )
            ),
            "brier": _safe_float(
                brier_score(
                    blended,
                    outcomes,
                )
            ),
        })
    return rows


def fit_market_blend_alpha(
    frame: pd.DataFrame,
    model_probability: pd.Series,
    market_probability: pd.Series,
    *,
    alphas: tuple[float, ...] = BLEND_ALPHAS,
) -> tuple[float, list[dict]]:
    rows = _alpha_sweep(
        frame,
        model_probability,
        market_probability,
        alphas=alphas,
    )
    if not rows:
        raise ValueError("market blend alpha grid is empty")

    # Tie-break toward the market baseline so model weight is added only
    # when development data gives a measurable log-loss improvement.
    best = min(
        rows,
        key=lambda row: (
            float(row["winner_log_loss"]),
            float(row["alpha_model_weight"]),
        ),
    )
    return float(best["alpha_model_weight"]), rows


def _ev_threshold_sweep(
    frame: pd.DataFrame,
    probability: pd.Series,
    *,
    min_probability: float,
) -> list[dict]:
    odds = pd.to_numeric(
        frame["decimal_odds"],
        errors="coerce",
    )
    finish = pd.to_numeric(
        frame["finish_position"],
        errors="coerce",
    )
    ev = probability * odds
    rows: list[dict] = []

    for threshold in EV_THRESHOLDS:
        mask = (
            probability.ge(min_probability)
            & ev.ge(threshold)
        )
        selected = frame.loc[mask]
        if selected.empty:
            rows.append({
                "ev_threshold": threshold,
                "rows": 0,
                "races": 0,
                "wins": 0,
                "hit_rate": None,
                "average_probability": None,
                "average_ev": None,
                "flat_bet_roi_final_odds": None,
            })
            continue

        selected_finish = finish.loc[selected.index]
        selected_odds = odds.loc[selected.index]
        selected_probability = probability.loc[
            selected.index
        ]
        selected_ev = ev.loc[selected.index]
        wins_mask = selected_finish.eq(1)
        wins = int(wins_mask.sum())
        flat_return = float(
            selected_odds.where(
                wins_mask,
                0.0,
            ).mean()
        )
        rows.append({
            "ev_threshold": threshold,
            "rows": int(len(selected)),
            "races": int(
                selected["race_id"].nunique()
            ),
            "wins": wins,
            "hit_rate": _safe_float(
                wins / len(selected)
            ),
            "average_probability": _safe_float(
                selected_probability.mean()
            ),
            "average_ev": _safe_float(
                selected_ev.mean()
            ),
            "flat_bet_roi_final_odds": _safe_float(
                flat_return - 1.0
            ),
        })
    return rows


def _confidence_quantiles(
    frame: pd.DataFrame,
    probability: pd.Series,
) -> dict:
    confidence = probability.groupby(
        frame["race_id"]
    ).transform(race_certainty)
    race_confidence = (
        confidence.groupby(frame["race_id"])
        .first()
    )
    return {
        str(q): _safe_float(value)
        for q, value in race_confidence.quantile(
            [0.5, 0.9, 0.95, 0.99, 1.0]
        ).items()
    }


def evaluate_market_blend_predictions(
    predictions: pd.DataFrame,
    champion: LoadedChampion,
    *,
    config: StrategyConfig | None = None,
    development_end: str = "2024-12-31",
    holdout_start: str = "2025-01-01",
) -> dict:
    config = config or StrategyConfig()
    if predictions.empty:
        raise ValueError("market blend predictions are empty")

    frame = predictions.copy()
    frame["race_date"] = pd.to_datetime(
        frame["race_date"],
        errors="raise",
    )
    frame["decimal_odds"] = pd.to_numeric(
        frame["decimal_odds"],
        errors="coerce",
    )
    frame = frame.loc[
        frame["decimal_odds"].gt(1.0)
    ].copy()
    if frame.empty:
        raise ValueError(
            "market blend has no rows with valid odds"
        )

    dates = frame["race_date"]
    development = frame.loc[
        dates.le(pd.Timestamp(development_end))
    ].copy()
    holdout = frame.loc[
        dates.ge(pd.Timestamp(holdout_start))
    ].copy()
    if development.empty or holdout.empty:
        raise ValueError(
            "market blend requires non-empty development and holdout"
        )

    raw_development = pd.to_numeric(
        development["predicted_win_probability"],
        errors="raise",
    )
    development_outcomes = _outcomes(development)
    temperature = fit_temperature(
        raw_development,
        development["race_id"],
        development_outcomes,
    )
    calibrated_development = apply_temperature(
        raw_development,
        development["race_id"],
        temperature,
    )

    raw_holdout = pd.to_numeric(
        holdout["predicted_win_probability"],
        errors="raise",
    )
    calibrated_holdout = apply_temperature(
        raw_holdout,
        holdout["race_id"],
        temperature,
    )

    development_market = normalized_market_probability(
        development
    )
    holdout_market = normalized_market_probability(
        holdout
    )

    alpha, development_alpha_sweep = (
        fit_market_blend_alpha(
            development,
            calibrated_development,
            development_market,
        )
    )
    holdout_alpha_sweep = _alpha_sweep(
        holdout,
        calibrated_holdout,
        holdout_market,
    )

    blended_development = blend_probability(
        calibrated_development,
        development_market,
        alpha,
    )
    blended_holdout = blend_probability(
        calibrated_holdout,
        holdout_market,
        alpha,
    )

    development_quality = {
        "market": _quality(
            development,
            development_market,
        ),
        "calibrated_model": _quality(
            development,
            calibrated_development,
        ),
        "fitted_blend": _quality(
            development,
            blended_development,
        ),
    }
    holdout_quality = {
        "market": _quality(
            holdout,
            holdout_market,
        ),
        "calibrated_model": _quality(
            holdout,
            calibrated_holdout,
        ),
        "fitted_blend": _quality(
            holdout,
            blended_holdout,
        ),
    }

    market_loss = holdout_quality[
        "market"
    ]["winner_log_loss"]
    blend_loss = holdout_quality[
        "fitted_blend"
    ]["winner_log_loss"]

    return {
        "status": (
            "research_only_market_blend_holdout_diagnostic"
        ),
        "warning": (
            "Historical final win odds are used to construct the market "
            "baseline and research EV. The blend weight is fit only on "
            "2021-2024 development data and evaluated untouched on the "
            "2025-2026 holdout. This cannot be promoted to live or Paper "
            "decisioning until equivalent pre-race odds snapshots are "
            "validated."
        ),
        "champion": {
            "model_version": champion.manifest.model_version,
            "experiment_id": champion.manifest.experiment_id,
            "train_end": champion.manifest.train_end,
        },
        "development": {
            "period_start": str(
                development["race_date"].min().date()
            ),
            "period_end": str(
                development["race_date"].max().date()
            ),
            "rows": int(len(development)),
            "races": int(
                development["race_id"].nunique()
            ),
            "temperature": _safe_float(temperature),
            "fitted_alpha_model_weight": _safe_float(alpha),
            "fitted_alpha_market_weight": _safe_float(
                1.0 - alpha
            ),
            "quality": development_quality,
            "alpha_sweep": development_alpha_sweep,
            "blend_ev_threshold_sweep": (
                _ev_threshold_sweep(
                    development,
                    blended_development,
                    min_probability=config.min_probability,
                )
            ),
            "blend_confidence_quantiles": (
                _confidence_quantiles(
                    development,
                    blended_development,
                )
            ),
        },
        "holdout": {
            "period_start": str(
                holdout["race_date"].min().date()
            ),
            "period_end": str(
                holdout["race_date"].max().date()
            ),
            "rows": int(len(holdout)),
            "races": int(
                holdout["race_id"].nunique()
            ),
            "quality": holdout_quality,
            "alpha_sweep_for_diagnostics_only": (
                holdout_alpha_sweep
            ),
            "blend_ev_threshold_sweep": (
                _ev_threshold_sweep(
                    holdout,
                    blended_holdout,
                    min_probability=config.min_probability,
                )
            ),
            "blend_confidence_quantiles": (
                _confidence_quantiles(
                    holdout,
                    blended_holdout,
                )
            ),
            "fitted_blend_beats_market_winner_log_loss": (
                bool(
                    blend_loss is not None
                    and market_loss is not None
                    and float(blend_loss)
                    < float(market_loss)
                )
            ),
            "winner_log_loss_delta_vs_market": (
                None
                if (
                    blend_loss is None
                    or market_loss is None
                )
                else _safe_float(
                    float(blend_loss)
                    - float(market_loss)
                )
            ),
        },
    }


def evaluate_market_blend_history(
    history: pd.DataFrame,
    champion: LoadedChampion,
    *,
    config: StrategyConfig | None = None,
    development_end: str = "2024-12-31",
    holdout_start: str = "2025-01-01",
) -> dict:
    predictions = build_frozen_champion_predictions(
        history,
        champion,
    )
    return evaluate_market_blend_predictions(
        predictions,
        champion,
        config=config,
        development_end=development_end,
        holdout_start=holdout_start,
    )
