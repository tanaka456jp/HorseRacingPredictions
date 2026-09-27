from __future__ import annotations

import math

import pandas as pd

from .calibration import apply_temperature, fit_temperature
from .feature_window import align_history_to_training_start
from .features import build_pre_race_features
from .market_aware_ranker_v11 import (
    MARKET_CONTEXT_FEATURES,
    add_market_context_features,
)
from .market_blend_research import normalized_market_probability
from .model_artifact import LoadedChampion
from .modeling import CatBoostRankingProbabilityModel


OVERLAY_RATIO_THRESHOLDS = (
    0.00,
    0.02,
    0.05,
    0.10,
    0.15,
    0.20,
    0.30,
    0.50,
    0.75,
    1.00,
)

OVERLAY_POLICIES = (
    "all_candidates",
    "top1_overlay_per_race",
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


def market_overlay_ratio(
    model_probability: pd.Series,
    market_probability: pd.Series,
) -> pd.Series:
    if not model_probability.index.equals(
        market_probability.index
    ):
        raise ValueError(
            "model and market probabilities must share the same index"
        )
    denominator = market_probability.astype(float).clip(
        lower=1e-12,
    )
    return (
        model_probability.astype(float) / denominator
    ) - 1.0


def _select_overlay_candidates(
    frame: pd.DataFrame,
    model_probability: pd.Series,
    market_probability: pd.Series,
    *,
    overlay_ratio_threshold: float,
    min_probability: float,
    policy: str,
) -> pd.DataFrame:
    if policy not in OVERLAY_POLICIES:
        raise ValueError(
            f"unknown overlay selection policy: {policy}"
        )
    overlay = market_overlay_ratio(
        model_probability,
        market_probability,
    )
    selected = frame.loc[
        model_probability.ge(min_probability)
        & overlay.ge(overlay_ratio_threshold)
    ].copy()
    if selected.empty:
        return selected

    selected["_model_probability"] = (
        model_probability.loc[selected.index]
    )
    selected["_market_probability"] = (
        market_probability.loc[selected.index]
    )
    selected["_overlay_ratio"] = overlay.loc[
        selected.index
    ]

    if policy == "top1_overlay_per_race":
        selected = (
            selected.sort_values(
                [
                    "race_id",
                    "_overlay_ratio",
                    "_model_probability",
                ],
                ascending=[True, False, False],
                kind="stable",
            )
            .groupby(
                "race_id",
                sort=False,
                as_index=False,
            )
            .head(1)
        )

    return selected


def _overlay_result(
    selected: pd.DataFrame,
    *,
    overlay_ratio_threshold: float,
    policy: str,
) -> dict:
    if selected.empty:
        return {
            "overlay_ratio_threshold": float(
                overlay_ratio_threshold
            ),
            "policy": policy,
            "rows": 0,
            "races": 0,
            "wins": 0,
            "hit_rate": None,
            "average_model_probability": None,
            "average_market_probability": None,
            "average_overlay_ratio": None,
            "flat_bet_roi_final_odds": None,
        }

    odds_column = (
        "win_odds"
        if "win_odds" in selected.columns
        else "decimal_odds"
    )
    odds = pd.to_numeric(
        selected[odds_column],
        errors="coerce",
    )
    finish = pd.to_numeric(
        selected["finish_position"],
        errors="coerce",
    )
    wins_mask = finish.eq(1)
    wins = int(wins_mask.sum())
    flat_return = float(
        odds.where(
            wins_mask,
            0.0,
        ).mean()
    )
    return {
        "overlay_ratio_threshold": float(
            overlay_ratio_threshold
        ),
        "policy": policy,
        "rows": int(len(selected)),
        "races": int(
            selected["race_id"].nunique()
        ),
        "wins": wins,
        "hit_rate": _safe_float(
            wins / len(selected)
        ),
        "average_model_probability": _safe_float(
            selected["_model_probability"].mean()
        ),
        "average_market_probability": _safe_float(
            selected["_market_probability"].mean()
        ),
        "average_overlay_ratio": _safe_float(
            selected["_overlay_ratio"].mean()
        ),
        "flat_bet_roi_final_odds": _safe_float(
            flat_return - 1.0
        ),
    }


def overlay_threshold_sweep(
    frame: pd.DataFrame,
    model_probability: pd.Series,
    market_probability: pd.Series,
    *,
    min_probability: float = 0.03,
    thresholds: tuple[float, ...] = (
        OVERLAY_RATIO_THRESHOLDS
    ),
    policies: tuple[str, ...] = OVERLAY_POLICIES,
) -> list[dict]:
    rows: list[dict] = []
    for policy in policies:
        for threshold in thresholds:
            selected = _select_overlay_candidates(
                frame,
                model_probability,
                market_probability,
                overlay_ratio_threshold=threshold,
                min_probability=min_probability,
                policy=policy,
            )
            rows.append(
                _overlay_result(
                    selected,
                    overlay_ratio_threshold=threshold,
                    policy=policy,
                )
            )
    return rows


def fit_overlay_rule(
    frame: pd.DataFrame,
    model_probability: pd.Series,
    market_probability: pd.Series,
    *,
    min_probability: float = 0.03,
    min_rows: int = 200,
    min_races: int = 100,
) -> tuple[dict | None, list[dict]]:
    sweep = overlay_threshold_sweep(
        frame,
        model_probability,
        market_probability,
        min_probability=min_probability,
    )
    eligible = [
        row
        for row in sweep
        if row["rows"] >= min_rows
        and row["races"] >= min_races
        and row["flat_bet_roi_final_odds"] is not None
    ]
    if not eligible:
        return None, sweep

    best = max(
        eligible,
        key=lambda row: (
            float(
                row["flat_bet_roi_final_odds"]
            ),
            int(row["rows"]),
            -float(
                row["overlay_ratio_threshold"]
            ),
        ),
    )
    return dict(best), sweep


def evaluate_fixed_overlay_rule(
    frame: pd.DataFrame,
    model_probability: pd.Series,
    market_probability: pd.Series,
    rule: dict,
    *,
    min_probability: float = 0.03,
) -> dict:
    selected = _select_overlay_candidates(
        frame,
        model_probability,
        market_probability,
        overlay_ratio_threshold=float(
            rule["overlay_ratio_threshold"]
        ),
        min_probability=min_probability,
        policy=str(rule["policy"]),
    )
    return _overlay_result(
        selected,
        overlay_ratio_threshold=float(
            rule["overlay_ratio_threshold"]
        ),
        policy=str(rule["policy"]),
    )


def evaluate_market_overlay_v11_development(
    history: pd.DataFrame,
    champion: LoadedChampion,
    *,
    challenger_iterations: int = 350,
    calibration_end: str = "2022-12-31",
    tuning_start: str = "2023-01-01",
    tuning_end: str = "2023-12-31",
    validation_start: str = "2024-01-01",
    validation_end: str = "2024-12-31",
    min_probability: float = 0.03,
    min_rows: int = 200,
    min_races: int = 100,
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
            pd.Timestamp(validation_end)
        )
    ].copy()
    if data.empty:
        raise ValueError(
            "market overlay development history is empty"
        )

    enhanced = build_pre_race_features(
        data,
        experimental_ranker_v10=True,
    )
    market_frame = add_market_context_features(
        enhanced.frame
    )
    features = (
        tuple(enhanced.feature_columns)
        + MARKET_CONTEXT_FEATURES
    )

    train_end = pd.Timestamp(
        champion.manifest.train_end
    ).normalize()
    calibration_end_ts = pd.Timestamp(
        calibration_end
    ).normalize()
    tuning_start_ts = pd.Timestamp(
        tuning_start
    ).normalize()
    tuning_end_ts = pd.Timestamp(
        tuning_end
    ).normalize()
    validation_start_ts = pd.Timestamp(
        validation_start
    ).normalize()
    validation_end_ts = pd.Timestamp(
        validation_end
    ).normalize()

    if not (
        train_end
        < calibration_end_ts
        < tuning_start_ts
        <= tuning_end_ts
        < validation_start_ts
        <= validation_end_ts
    ):
        raise ValueError(
            "invalid market overlay development time split"
        )

    dates = pd.to_datetime(
        market_frame["race_date"],
        errors="raise",
    )
    train = market_frame.loc[
        dates.le(train_end)
    ].copy()
    calibration = market_frame.loc[
        dates.gt(train_end)
        & dates.le(calibration_end_ts)
    ].copy()
    tuning = market_frame.loc[
        dates.between(
            tuning_start_ts,
            tuning_end_ts,
            inclusive="both",
        )
    ].copy()
    validation = market_frame.loc[
        dates.between(
            validation_start_ts,
            validation_end_ts,
            inclusive="both",
        )
    ].copy()

    if (
        train.empty
        or calibration.empty
        or tuning.empty
        or validation.empty
    ):
        raise ValueError(
            "market overlay development split contains an empty period"
        )

    model = CatBoostRankingProbabilityModel(
        list(features),
        iterations=challenger_iterations,
    ).fit(
        train,
        target_col="is_winner",
        race_col="race_id",
    )

    calibration_raw = (
        model.predict_win_probability(
            calibration,
            race_col="race_id",
        )
    )
    temperature = fit_temperature(
        calibration_raw,
        calibration["race_id"],
        _outcomes(calibration),
    )

    tuning_probability = apply_temperature(
        model.predict_win_probability(
            tuning,
            race_col="race_id",
        ),
        tuning["race_id"],
        temperature,
    )
    validation_probability = apply_temperature(
        model.predict_win_probability(
            validation,
            race_col="race_id",
        ),
        validation["race_id"],
        temperature,
    )

    tuning_market = normalized_market_probability(
        tuning.rename(
            columns={"win_odds": "decimal_odds"}
        )
    )
    validation_market = normalized_market_probability(
        validation.rename(
            columns={"win_odds": "decimal_odds"}
        )
    )

    fitted_rule, tuning_sweep = fit_overlay_rule(
        tuning,
        tuning_probability,
        tuning_market,
        min_probability=min_probability,
        min_rows=min_rows,
        min_races=min_races,
    )

    if fitted_rule is None:
        validation_result = None
        gate = False
    else:
        validation_result = evaluate_fixed_overlay_rule(
            validation,
            validation_probability,
            validation_market,
            fitted_rule,
            min_probability=min_probability,
        )
        gate = bool(
            float(
                fitted_rule[
                    "flat_bet_roi_final_odds"
                ]
            ) > 0.0
            and validation_result[
                "flat_bet_roi_final_odds"
            ] is not None
            and float(
                validation_result[
                    "flat_bet_roi_final_odds"
                ]
            ) > 0.0
            and int(
                validation_result["rows"]
            ) >= min_rows
            and int(
                validation_result["races"]
            ) >= min_races
        )

    return {
        "status": (
            "research_only_market_overlay_v11_development"
        ),
        "warning": (
            "Historical final odds are used only as a research market proxy. "
            "The overlay rule is selected on 2023 and validated unchanged on "
            "2024. Rows from 2025 onward are excluded before feature building. "
            "A development PASS is not live profitability evidence; pre-race "
            "0B31 snapshots must reproduce the same signal before Paper use."
        ),
        "training": {
            "train_start": champion.manifest.train_start,
            "train_end": champion.manifest.train_end,
            "rows": int(len(train)),
            "races": int(
                train["race_id"].nunique()
            ),
        },
        "calibration": {
            "period_start": str(
                calibration["race_date"].min().date()
            ),
            "period_end": str(
                calibration["race_date"].max().date()
            ),
            "rows": int(len(calibration)),
            "races": int(
                calibration["race_id"].nunique()
            ),
            "temperature": _safe_float(
                temperature
            ),
        },
        "tuning_2023": {
            "period_start": str(
                tuning["race_date"].min().date()
            ),
            "period_end": str(
                tuning["race_date"].max().date()
            ),
            "rows": int(len(tuning)),
            "races": int(
                tuning["race_id"].nunique()
            ),
            "fitted_rule": fitted_rule,
            "threshold_sweep": tuning_sweep,
        },
        "validation_2024": {
            "period_start": str(
                validation["race_date"].min().date()
            ),
            "period_end": str(
                validation["race_date"].max().date()
            ),
            "rows": int(len(validation)),
            "races": int(
                validation["race_id"].nunique()
            ),
            "fixed_rule_result": validation_result,
            "development_gate_passed": gate,
        },
        "constraints": {
            "min_probability": float(
                min_probability
            ),
            "min_rows": int(min_rows),
            "min_races": int(min_races),
        },
    }
