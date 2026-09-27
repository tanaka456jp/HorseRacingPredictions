from __future__ import annotations

import math

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
    2.50,
    3.00,
)


def _safe_float(value) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None


def _market_probability(frame: pd.DataFrame) -> pd.Series:
    odds = pd.to_numeric(
        frame["decimal_odds"],
        errors="coerce",
    )
    inverse = 1.0 / odds.where(odds > 1.0)
    denominator = inverse.groupby(
        frame["race_id"]
    ).transform("sum")
    return (
        inverse / denominator.replace(0, pd.NA)
    ).fillna(0.0)


def _quality(
    frame: pd.DataFrame,
    probability: pd.Series,
) -> dict:
    outcomes = (
        pd.to_numeric(
            frame["finish_position"],
            errors="coerce",
        )
        .eq(1)
        .astype(int)
    )
    market = _market_probability(frame)
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
        "market_winner_log_loss": _safe_float(
            winner_log_loss(
                market,
                frame["race_id"],
                outcomes,
            )
        ),
        "market_binary_log_loss": _safe_float(
            binary_log_loss(
                market,
                outcomes,
            )
        ),
        "market_brier": _safe_float(
            brier_score(
                market,
                outcomes,
            )
        ),
    }


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

    rows = []
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


def evaluate_temperature_calibration_predictions(
    predictions: pd.DataFrame,
    champion: LoadedChampion,
    *,
    config: StrategyConfig | None = None,
    development_end: str = "2024-12-31",
    holdout_start: str = "2025-01-01",
) -> dict:
    config = config or StrategyConfig()
    if predictions.empty:
        raise ValueError(
            "temperature calibration predictions are empty"
        )

    dates = pd.to_datetime(
        predictions["race_date"],
        errors="raise",
    )
    development = predictions.loc[
        dates.le(
            pd.Timestamp(development_end)
        )
    ].copy()
    holdout = predictions.loc[
        dates.ge(
            pd.Timestamp(holdout_start)
        )
    ].copy()

    if development.empty:
        raise ValueError(
            "temperature calibration development period is empty"
        )
    if holdout.empty:
        raise ValueError(
            "temperature calibration holdout period is empty"
        )

    development_outcomes = (
        pd.to_numeric(
            development["finish_position"],
            errors="coerce",
        )
        .eq(1)
        .astype(int)
    )
    raw_development = pd.to_numeric(
        development["predicted_win_probability"],
        errors="raise",
    )
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

    development_confidence = (
        calibrated_development.groupby(
            development["race_id"]
        ).transform(race_certainty)
    )
    holdout_confidence = (
        calibrated_holdout.groupby(
            holdout["race_id"]
        ).transform(race_certainty)
    )

    return {
        "status": (
            "research_only_post_training_temperature_calibration"
        ),
        "warning": (
            "Temperature is fit only on the development period. "
            "The holdout is untouched until evaluation. Final historical "
            "win odds are used only for research EV diagnostics and do "
            "not prove live profitability."
        ),
        "champion": {
            "model_version": champion.manifest.model_version,
            "experiment_id": champion.manifest.experiment_id,
            "train_end": champion.manifest.train_end,
        },
        "temperature": _safe_float(temperature),
        "development": {
            "period_start": str(
                pd.to_datetime(
                    development["race_date"]
                ).min().date()
            ),
            "period_end": str(
                pd.to_datetime(
                    development["race_date"]
                ).max().date()
            ),
            "rows": int(len(development)),
            "races": int(
                development["race_id"].nunique()
            ),
            "raw_quality": _quality(
                development,
                raw_development,
            ),
            "calibrated_quality": _quality(
                development,
                calibrated_development,
            ),
            "raw_ev_threshold_sweep": (
                _ev_threshold_sweep(
                    development,
                    raw_development,
                    min_probability=(
                        config.min_probability
                    ),
                )
            ),
            "calibrated_ev_threshold_sweep": (
                _ev_threshold_sweep(
                    development,
                    calibrated_development,
                    min_probability=(
                        config.min_probability
                    ),
                )
            ),
            "calibrated_confidence_quantiles": {
                str(q): _safe_float(v)
                for q, v in (
                    development_confidence.groupby(
                        development["race_id"]
                    )
                    .first()
                    .quantile(
                        [
                            0.5,
                            0.9,
                            0.95,
                            0.99,
                            1.0,
                        ]
                    )
                    .items()
                )
            },
        },
        "holdout": {
            "period_start": str(
                pd.to_datetime(
                    holdout["race_date"]
                ).min().date()
            ),
            "period_end": str(
                pd.to_datetime(
                    holdout["race_date"]
                ).max().date()
            ),
            "rows": int(len(holdout)),
            "races": int(
                holdout["race_id"].nunique()
            ),
            "raw_quality": _quality(
                holdout,
                raw_holdout,
            ),
            "calibrated_quality": _quality(
                holdout,
                calibrated_holdout,
            ),
            "raw_ev_threshold_sweep": (
                _ev_threshold_sweep(
                    holdout,
                    raw_holdout,
                    min_probability=(
                        config.min_probability
                    ),
                )
            ),
            "calibrated_ev_threshold_sweep": (
                _ev_threshold_sweep(
                    holdout,
                    calibrated_holdout,
                    min_probability=(
                        config.min_probability
                    ),
                )
            ),
            "calibrated_confidence_quantiles": {
                str(q): _safe_float(v)
                for q, v in (
                    holdout_confidence.groupby(
                        holdout["race_id"]
                    )
                    .first()
                    .quantile(
                        [
                            0.5,
                            0.9,
                            0.95,
                            0.99,
                            1.0,
                        ]
                    )
                    .items()
                )
            },
        },
    }


def evaluate_temperature_calibration_split(
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
    return evaluate_temperature_calibration_predictions(
        predictions,
        champion,
        config=config,
        development_end=development_end,
        holdout_start=holdout_start,
    )
