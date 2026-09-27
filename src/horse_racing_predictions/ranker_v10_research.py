from __future__ import annotations

import math

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


def evaluate_ranker_v10_development(
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
            "Ranker v10 development history is empty"
        )

    base = build_pre_race_features(
        data,
        experimental_ranker_v10=False,
    )
    enhanced = build_pre_race_features(
        data,
        experimental_ranker_v10=True,
    )

    required_v9 = tuple(
        champion.manifest.feature_columns
    )
    missing_v9 = (
        set(required_v9)
        - set(base.frame.columns)
    )
    if missing_v9:
        raise ValueError(
            "development history missing Ranker v9 features: "
            f"{sorted(missing_v9)}"
        )

    v10_features = tuple(enhanced.feature_columns)
    added_features = tuple(
        feature
        for feature in v10_features
        if feature not in set(required_v9)
    )
    if not added_features:
        raise ValueError(
            "Ranker v10 experimental feature set added no features"
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
            "invalid Ranker v10 development time split"
        )

    dates = pd.to_datetime(
        base.frame["race_date"],
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

    base_train = base.frame.loc[train_mask].copy()
    base_calibration = base.frame.loc[
        calibration_mask
    ].copy()
    base_selection = base.frame.loc[
        selection_mask
    ].copy()

    enhanced_train = enhanced.frame.loc[
        train_mask
    ].copy()
    enhanced_calibration = enhanced.frame.loc[
        calibration_mask
    ].copy()
    enhanced_selection = enhanced.frame.loc[
        selection_mask
    ].copy()

    if (
        base_train.empty
        or base_calibration.empty
        or base_selection.empty
    ):
        raise ValueError(
            "Ranker v10 development split contains an empty period"
        )

    v9 = CatBoostRankingProbabilityModel(
        list(required_v9),
        iterations=challenger_iterations,
    ).fit(
        base_train,
        target_col="is_winner",
        race_col="race_id",
    )
    v10 = CatBoostRankingProbabilityModel(
        list(v10_features),
        iterations=challenger_iterations,
    ).fit(
        enhanced_train,
        target_col="is_winner",
        race_col="race_id",
    )

    v9_calibration_probability = (
        v9.predict_win_probability(
            base_calibration,
            race_col="race_id",
        )
    )
    v10_calibration_probability = (
        v10.predict_win_probability(
            enhanced_calibration,
            race_col="race_id",
        )
    )
    v9_temperature = fit_temperature(
        v9_calibration_probability,
        base_calibration["race_id"],
        _outcomes(base_calibration),
    )
    v10_temperature = fit_temperature(
        v10_calibration_probability,
        enhanced_calibration["race_id"],
        _outcomes(enhanced_calibration),
    )

    v9_selection_raw = v9.predict_win_probability(
        base_selection,
        race_col="race_id",
    )
    v10_selection_raw = v10.predict_win_probability(
        enhanced_selection,
        race_col="race_id",
    )
    v9_selection = apply_temperature(
        v9_selection_raw,
        base_selection["race_id"],
        v9_temperature,
    )
    v10_selection = apply_temperature(
        v10_selection_raw,
        enhanced_selection["race_id"],
        v10_temperature,
    )
    market_selection = normalized_market_probability(
        base_selection.rename(
            columns={"win_odds": "decimal_odds"}
        )
    )

    v9_quality = _quality(
        base_selection,
        v9_selection,
    )
    v10_quality = _quality(
        enhanced_selection,
        v10_selection,
    )
    market_quality = _quality(
        base_selection,
        market_selection,
    )

    log_loss_delta = (
        float(v10_quality["winner_log_loss"])
        - float(v9_quality["winner_log_loss"])
    )
    brier_delta = (
        float(v10_quality["brier"])
        - float(v9_quality["brier"])
    )

    return {
        "status": (
            "research_only_ranker_v10_development_selection"
        ),
        "warning": (
            "This experiment excludes 2025+ rows before feature building. "
            "Temperature calibration uses only post-training history through "
            "2023, and feature selection is based only on 2024. The 2025-2026 "
            "holdout must remain untouched until the development gate passes."
        ),
        "training": {
            "train_start": champion.manifest.train_start,
            "train_end": champion.manifest.train_end,
            "rows": int(len(base_train)),
            "races": int(
                base_train["race_id"].nunique()
            ),
        },
        "calibration": {
            "period_start": str(
                base_calibration["race_date"].min().date()
            ),
            "period_end": str(
                base_calibration["race_date"].max().date()
            ),
            "rows": int(len(base_calibration)),
            "races": int(
                base_calibration["race_id"].nunique()
            ),
            "v9_temperature": _safe_float(
                v9_temperature
            ),
            "v10_temperature": _safe_float(
                v10_temperature
            ),
        },
        "selection_2024": {
            "period_start": str(
                base_selection["race_date"].min().date()
            ),
            "period_end": str(
                base_selection["race_date"].max().date()
            ),
            "rows": int(len(base_selection)),
            "races": int(
                base_selection["race_id"].nunique()
            ),
            "v9_quality": v9_quality,
            "v10_quality": v10_quality,
            "market_quality": market_quality,
            "v10_delta_vs_v9_winner_log_loss": (
                _safe_float(log_loss_delta)
            ),
            "v10_delta_vs_v9_brier": (
                _safe_float(brier_delta)
            ),
            "v10_beats_v9_winner_log_loss": bool(
                log_loss_delta < 0.0
            ),
            "v10_beats_v9_brier": bool(
                brier_delta < 0.0
            ),
            "development_gate_passed": bool(
                log_loss_delta < 0.0
                and brier_delta < 0.0
            ),
        },
        "features": {
            "v9_count": int(len(required_v9)),
            "v10_count": int(len(v10_features)),
            "added_count": int(len(added_features)),
            "added_feature_columns": list(
                added_features
            ),
        },
    }



def _ev15_research_diagnostic(
    frame: pd.DataFrame,
    probability: pd.Series,
    *,
    min_probability: float = 0.03,
    ev_threshold: float = 1.15,
) -> dict:
    odds = pd.to_numeric(
        frame["win_odds"],
        errors="coerce",
    )
    finish = pd.to_numeric(
        frame["finish_position"],
        errors="coerce",
    )
    ev = probability * odds
    mask = (
        probability.ge(min_probability)
        & ev.ge(ev_threshold)
    )
    selected = frame.loc[mask]
    if selected.empty:
        return {
            "ev_threshold": ev_threshold,
            "rows": 0,
            "races": 0,
            "wins": 0,
            "hit_rate": None,
            "flat_bet_roi_final_odds": None,
        }

    selected_finish = finish.loc[selected.index]
    selected_odds = odds.loc[selected.index]
    wins_mask = selected_finish.eq(1)
    wins = int(wins_mask.sum())
    flat_return = float(
        selected_odds.where(
            wins_mask,
            0.0,
        ).mean()
    )
    return {
        "ev_threshold": ev_threshold,
        "rows": int(len(selected)),
        "races": int(
            selected["race_id"].nunique()
        ),
        "wins": wins,
        "hit_rate": _safe_float(
            wins / len(selected)
        ),
        "flat_bet_roi_final_odds": _safe_float(
            flat_return - 1.0
        ),
    }


def evaluate_ranker_v10_holdout_confirmation(
    history: pd.DataFrame,
    champion: LoadedChampion,
    *,
    challenger_iterations: int = 350,
    calibration_end: str = "2023-12-31",
    holdout_start: str = "2025-01-01",
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
    ].copy()
    if data.empty:
        raise ValueError(
            "Ranker v10 holdout history is empty"
        )

    base = build_pre_race_features(
        data,
        experimental_ranker_v10=False,
    )
    enhanced = build_pre_race_features(
        data,
        experimental_ranker_v10=True,
    )

    required_v9 = tuple(
        champion.manifest.feature_columns
    )
    missing_v9 = (
        set(required_v9)
        - set(base.frame.columns)
    )
    if missing_v9:
        raise ValueError(
            "holdout history missing Ranker v9 features: "
            f"{sorted(missing_v9)}"
        )

    v10_features = tuple(enhanced.feature_columns)
    added_features = tuple(
        feature
        for feature in v10_features
        if feature not in set(required_v9)
    )
    if not added_features:
        raise ValueError(
            "Ranker v10 holdout feature set added no features"
        )

    train_end = pd.Timestamp(
        champion.manifest.train_end
    ).normalize()
    calibration_end_ts = pd.Timestamp(
        calibration_end
    ).normalize()
    holdout_start_ts = pd.Timestamp(
        holdout_start
    ).normalize()
    if not (
        train_end
        < calibration_end_ts
        < holdout_start_ts
    ):
        raise ValueError(
            "invalid Ranker v10 holdout time split"
        )

    dates = pd.to_datetime(
        base.frame["race_date"],
        errors="raise",
    )
    train_mask = dates.le(train_end)
    calibration_mask = (
        dates.gt(train_end)
        & dates.le(calibration_end_ts)
    )
    holdout_mask = dates.ge(holdout_start_ts)

    base_train = base.frame.loc[
        train_mask
    ].copy()
    enhanced_train = enhanced.frame.loc[
        train_mask
    ].copy()
    base_calibration = base.frame.loc[
        calibration_mask
    ].copy()
    enhanced_calibration = enhanced.frame.loc[
        calibration_mask
    ].copy()
    base_holdout = base.frame.loc[
        holdout_mask
    ].copy()
    enhanced_holdout = enhanced.frame.loc[
        holdout_mask
    ].copy()

    if (
        base_train.empty
        or base_calibration.empty
        or base_holdout.empty
    ):
        raise ValueError(
            "Ranker v10 holdout split contains an empty period"
        )

    v9 = CatBoostRankingProbabilityModel(
        list(required_v9),
        iterations=challenger_iterations,
    ).fit(
        base_train,
        target_col="is_winner",
        race_col="race_id",
    )
    v10 = CatBoostRankingProbabilityModel(
        list(v10_features),
        iterations=challenger_iterations,
    ).fit(
        enhanced_train,
        target_col="is_winner",
        race_col="race_id",
    )

    v9_calibration_raw = (
        v9.predict_win_probability(
            base_calibration,
            race_col="race_id",
        )
    )
    v10_calibration_raw = (
        v10.predict_win_probability(
            enhanced_calibration,
            race_col="race_id",
        )
    )
    v9_temperature = fit_temperature(
        v9_calibration_raw,
        base_calibration["race_id"],
        _outcomes(base_calibration),
    )
    v10_temperature = fit_temperature(
        v10_calibration_raw,
        enhanced_calibration["race_id"],
        _outcomes(enhanced_calibration),
    )

    v9_holdout_raw = v9.predict_win_probability(
        base_holdout,
        race_col="race_id",
    )
    v10_holdout_raw = v10.predict_win_probability(
        enhanced_holdout,
        race_col="race_id",
    )
    v9_holdout = apply_temperature(
        v9_holdout_raw,
        base_holdout["race_id"],
        v9_temperature,
    )
    v10_holdout = apply_temperature(
        v10_holdout_raw,
        enhanced_holdout["race_id"],
        v10_temperature,
    )
    market_holdout = normalized_market_probability(
        base_holdout.rename(
            columns={"win_odds": "decimal_odds"}
        )
    )

    v9_quality = _quality(
        base_holdout,
        v9_holdout,
    )
    v10_quality = _quality(
        enhanced_holdout,
        v10_holdout,
    )
    market_quality = _quality(
        base_holdout,
        market_holdout,
    )

    log_loss_delta = (
        float(v10_quality["winner_log_loss"])
        - float(v9_quality["winner_log_loss"])
    )
    brier_delta = (
        float(v10_quality["brier"])
        - float(v9_quality["brier"])
    )

    return {
        "status": (
            "research_only_ranker_v10_holdout_confirmation"
        ),
        "warning": (
            "The v10 feature set, Ranker configuration, and calibration "
            "period were fixed before this 2025-2026 holdout evaluation. "
            "Historical final odds are used only for market comparison and "
            "research EV diagnostics; they do not verify live profitability."
        ),
        "training": {
            "train_start": champion.manifest.train_start,
            "train_end": champion.manifest.train_end,
            "rows": int(len(base_train)),
            "races": int(
                base_train["race_id"].nunique()
            ),
        },
        "calibration": {
            "period_start": str(
                base_calibration["race_date"].min().date()
            ),
            "period_end": str(
                base_calibration["race_date"].max().date()
            ),
            "rows": int(len(base_calibration)),
            "races": int(
                base_calibration["race_id"].nunique()
            ),
            "v9_temperature": _safe_float(
                v9_temperature
            ),
            "v10_temperature": _safe_float(
                v10_temperature
            ),
        },
        "holdout_2025_2026": {
            "period_start": str(
                base_holdout["race_date"].min().date()
            ),
            "period_end": str(
                base_holdout["race_date"].max().date()
            ),
            "rows": int(len(base_holdout)),
            "races": int(
                base_holdout["race_id"].nunique()
            ),
            "v9_quality": v9_quality,
            "v10_quality": v10_quality,
            "market_quality": market_quality,
            "v10_delta_vs_v9_winner_log_loss": (
                _safe_float(log_loss_delta)
            ),
            "v10_delta_vs_v9_brier": (
                _safe_float(brier_delta)
            ),
            "v10_beats_v9_winner_log_loss": bool(
                log_loss_delta < 0.0
            ),
            "v10_beats_v9_brier": bool(
                brier_delta < 0.0
            ),
            "holdout_confirmation_passed": bool(
                log_loss_delta < 0.0
                and brier_delta < 0.0
            ),
            "v9_ev15_research": (
                _ev15_research_diagnostic(
                    base_holdout,
                    v9_holdout,
                )
            ),
            "v10_ev15_research": (
                _ev15_research_diagnostic(
                    enhanced_holdout,
                    v10_holdout,
                )
            ),
        },
        "features": {
            "v9_count": int(len(required_v9)),
            "v10_count": int(len(v10_features)),
            "added_count": int(len(added_features)),
            "added_feature_columns": list(
                added_features
            ),
        },
    }
