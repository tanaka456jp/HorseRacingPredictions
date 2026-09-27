from __future__ import annotations

import math

import pandas as pd

from .challenger_research import (
    ResearchLoadedModel,
    ResearchManifest,
    _holdout_ev_row,
    _prediction_frame,
)
from .champion_calibration import (
    evaluate_temperature_calibration_predictions,
)
from .champion_diagnostics import (
    summarize_prediction_diagnostics,
)
from .config import StrategyConfig
from .feature_window import align_history_to_training_start
from .features import build_pre_race_features
from .model_artifact import LoadedChampion
from .modeling import CatBoostRankingProbabilityModel


def _safe_float(value) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None


def evaluate_catboost_ranker_challenger(
    history: pd.DataFrame,
    champion: LoadedChampion,
    *,
    config: StrategyConfig | None = None,
    challenger_iterations: int = 350,
) -> dict:
    config = config or StrategyConfig()
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
            "ranker challenger research history is empty"
        )

    built = build_pre_race_features(data)
    required_features = tuple(
        champion.manifest.feature_columns
    )
    missing = (
        set(required_features)
        - set(built.frame.columns)
    )
    if missing:
        raise ValueError(
            "ranker challenger history missing Champion features: "
            f"{sorted(missing)}"
        )

    train_end = pd.Timestamp(
        champion.manifest.train_end
    ).normalize()
    dates = pd.to_datetime(
        built.frame["race_date"],
        errors="raise",
    )
    train = built.frame.loc[
        dates.le(train_end)
    ].copy()
    evaluation = built.frame.loc[
        dates.gt(train_end)
    ].copy()
    if train.empty or evaluation.empty:
        raise ValueError(
            "ranker challenger requires train and evaluation rows"
        )

    if challenger_iterations < 1:
        raise ValueError(
            "challenger_iterations must be positive"
        )

    challenger_model = CatBoostRankingProbabilityModel(
        list(required_features),
        iterations=challenger_iterations,
    ).fit(
        train,
        target_col="is_winner",
        race_col="race_id",
    )
    challenger = ResearchLoadedModel(
        model=challenger_model,
        manifest=ResearchManifest(
            model_version="challenger-v9-catboost-ranker",
            experiment_id=(
                "v9-catboost-ranker-recent-form"
            ),
            train_end=champion.manifest.train_end,
        ),
    )

    baseline_probability = (
        champion.model.predict_win_probability(
            evaluation,
            race_col="race_id",
        )
    )
    challenger_probability = (
        challenger.model.predict_win_probability(
            evaluation,
            race_col="race_id",
        )
    )

    baseline_predictions = _prediction_frame(
        evaluation,
        baseline_probability,
        model_version=champion.manifest.model_version,
    )
    challenger_predictions = _prediction_frame(
        evaluation,
        challenger_probability,
        model_version=challenger.manifest.model_version,
    )

    baseline_summary = summarize_prediction_diagnostics(
        baseline_predictions,
        config=config,
    )
    challenger_summary = summarize_prediction_diagnostics(
        challenger_predictions,
        config=config,
    )
    baseline_calibration = (
        evaluate_temperature_calibration_predictions(
            baseline_predictions,
            champion,
            config=config,
        )
    )
    challenger_calibration = (
        evaluate_temperature_calibration_predictions(
            challenger_predictions,
            challenger,
            config=config,
        )
    )

    base_holdout = baseline_calibration["holdout"]
    chal_holdout = challenger_calibration["holdout"]
    base_ev = _holdout_ev_row(
        baseline_calibration,
        config.min_ev,
    )
    chal_ev = _holdout_ev_row(
        challenger_calibration,
        config.min_ev,
    )

    base_loss = _safe_float(
        base_holdout["calibrated_quality"][
            "winner_log_loss"
        ]
    )
    chal_loss = _safe_float(
        chal_holdout["calibrated_quality"][
            "winner_log_loss"
        ]
    )
    market_loss = _safe_float(
        base_holdout["calibrated_quality"][
            "market_winner_log_loss"
        ]
    )

    return {
        "status": (
            "research_only_catboost_ranker_challenger"
        ),
        "warning": (
            "The ranker uses the same leakage-safe features and train_end "
            "as Champion v7, but optimizes within-race ranking rather than "
            "independent horse classification. Promotion decisions must be "
            "based on untouched 2025-2026 holdout metrics. Historical final "
            "odds remain research-only and do not verify live profitability."
        ),
        "training": {
            "train_start": champion.manifest.train_start,
            "train_end": champion.manifest.train_end,
            "rows": int(len(train)),
            "races": int(train["race_id"].nunique()),
            "feature_columns_match_champion": (
                tuple(built.feature_columns)
                == required_features
            ),
            "loss_function": (
                challenger_model.loss_function
            ),
        },
        "evaluation": {
            "rows": int(len(evaluation)),
            "races": int(
                evaluation["race_id"].nunique()
            ),
            "period_start": str(
                dates.loc[evaluation.index].min().date()
            ),
            "period_end": str(
                dates.loc[evaluation.index].max().date()
            ),
        },
        "baseline": {
            "model_version": champion.manifest.model_version,
            "overall": baseline_summary,
            "temperature_calibration": (
                baseline_calibration
            ),
        },
        "challenger": {
            "model_version": challenger.manifest.model_version,
            "overall": challenger_summary,
            "temperature_calibration": (
                challenger_calibration
            ),
        },
        "holdout_comparison": {
            "baseline_temperature": _safe_float(
                baseline_calibration["temperature"]
            ),
            "challenger_temperature": _safe_float(
                challenger_calibration["temperature"]
            ),
            "baseline_calibrated_winner_log_loss": (
                base_loss
            ),
            "challenger_calibrated_winner_log_loss": (
                chal_loss
            ),
            "market_winner_log_loss": market_loss,
            "challenger_delta_vs_baseline_winner_log_loss": (
                _safe_float(chal_loss - base_loss)
            ),
            "challenger_delta_vs_market_winner_log_loss": (
                _safe_float(chal_loss - market_loss)
            ),
            "challenger_beats_baseline_winner_log_loss": (
                bool(chal_loss < base_loss)
            ),
            "challenger_beats_market_winner_log_loss": (
                bool(chal_loss < market_loss)
            ),
            "baseline_calibrated_brier": _safe_float(
                base_holdout[
                    "calibrated_quality"
                ]["brier"]
            ),
            "challenger_calibrated_brier": _safe_float(
                chal_holdout[
                    "calibrated_quality"
                ]["brier"]
            ),
            "market_brier": _safe_float(
                base_holdout[
                    "calibrated_quality"
                ]["market_brier"]
            ),
            "baseline_ev15_rows": int(
                base_ev["rows"]
            ),
            "challenger_ev15_rows": int(
                chal_ev["rows"]
            ),
            "baseline_ev15_flat_roi_final_odds": (
                base_ev[
                    "flat_bet_roi_final_odds"
                ]
            ),
            "challenger_ev15_flat_roi_final_odds": (
                chal_ev[
                    "flat_bet_roi_final_odds"
                ]
            ),
        },
    }
