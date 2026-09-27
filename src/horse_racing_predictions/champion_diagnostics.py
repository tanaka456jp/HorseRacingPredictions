from __future__ import annotations

from dataclasses import asdict
import math

import numpy as np
import pandas as pd

from .backtest import simulate_win_strategy
from .config import StrategyConfig
from .diagnostics import build_oos_diagnostics
from .feature_window import align_history_to_training_start
from .features import build_pre_race_features
from .model_artifact import LoadedChampion
from .validation import FINAL_WIN_ODDS


def race_certainty(probabilities: pd.Series) -> float:
    p = probabilities[
        probabilities.notna() & (probabilities > 0)
    ].astype(float)
    n = len(p)
    if n <= 1:
        return 1.0
    entropy = -float((p * p.map(math.log)).sum())
    maximum = math.log(n)
    if maximum <= 0:
        return 1.0
    return max(0.0, min(1.0, 1.0 - entropy / maximum))


def _safe_float(value) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None


def _selection_reason(
    frame: pd.DataFrame,
    config: StrategyConfig,
) -> pd.Series:
    probability = pd.to_numeric(
        frame["predicted_win_probability"],
        errors="coerce",
    )
    confidence = pd.to_numeric(
        frame["confidence"],
        errors="coerce",
    )
    odds = pd.to_numeric(
        frame["decimal_odds"],
        errors="coerce",
    )
    ev = probability * odds

    reason = pd.Series(
        "eligible",
        index=frame.index,
        dtype="string",
    )
    reason.loc[
        probability < config.min_probability
    ] = "probability_below_threshold"

    remaining = reason.eq("eligible")
    reason.loc[
        remaining & (confidence < config.min_confidence)
    ] = "confidence_below_threshold"

    remaining = reason.eq("eligible")
    reason.loc[
        remaining & (ev < config.min_ev)
    ] = "ev_below_threshold"
    return reason


def _confidence_threshold_sweep(
    frame: pd.DataFrame,
    config: StrategyConfig,
    thresholds: tuple[float, ...] = (
        0.0,
        0.02,
        0.05,
        0.10,
        0.20,
        0.35,
        0.50,
        0.55,
        0.60,
        0.70,
    ),
) -> list[dict]:
    probability = pd.to_numeric(
        frame["predicted_win_probability"],
        errors="coerce",
    )
    odds = pd.to_numeric(
        frame["decimal_odds"],
        errors="coerce",
    )
    confidence = pd.to_numeric(
        frame["confidence"],
        errors="coerce",
    )
    finish = pd.to_numeric(
        frame["finish_position"],
        errors="coerce",
    )
    ev = probability * odds

    rows = []
    for threshold in thresholds:
        selected = frame.loc[
            probability.ge(config.min_probability)
            & confidence.ge(threshold)
            & ev.ge(config.min_ev)
        ].copy()
        if selected.empty:
            rows.append({
                "confidence_threshold": threshold,
                "rows": 0,
                "races": 0,
                "wins": 0,
                "hit_rate": None,
                "flat_bet_roi_final_odds": None,
            })
            continue

        selected_finish = finish.loc[selected.index]
        selected_odds = odds.loc[selected.index]
        wins_mask = selected_finish.eq(1)
        wins = int(wins_mask.sum())
        flat_return = float(
            selected_odds.where(wins_mask, 0.0).mean()
        )
        rows.append({
            "confidence_threshold": threshold,
            "rows": int(len(selected)),
            "races": int(selected["race_id"].nunique()),
            "wins": wins,
            "hit_rate": _safe_float(wins / len(selected)),
            "flat_bet_roi_final_odds": _safe_float(
                flat_return - 1.0
            ),
        })
    return rows


def _confidence_threshold_sweep_by_period(
    frame: pd.DataFrame,
    config: StrategyConfig,
) -> list[dict]:
    periods = (
        (
            "development_2021_2024",
            pd.Timestamp("2021-08-01"),
            pd.Timestamp("2024-12-31"),
        ),
        (
            "holdout_2025_2026",
            pd.Timestamp("2025-01-01"),
            pd.Timestamp("2026-12-31"),
        ),
    )
    year_values = sorted(
        int(value)
        for value in frame["race_date"].dt.year.unique()
    )
    rows: list[dict] = []

    for label, start, end in periods:
        subset = frame.loc[
            frame["race_date"].between(
                start,
                end,
                inclusive="both",
            )
        ].copy()
        if subset.empty:
            continue
        for result in _confidence_threshold_sweep(
            subset,
            config,
        ):
            rows.append({
                "period": label,
                "period_start": str(
                    subset["race_date"].min().date()
                ),
                "period_end": str(
                    subset["race_date"].max().date()
                ),
                **result,
            })

    for year in year_values:
        subset = frame.loc[
            frame["race_date"].dt.year.eq(year)
        ].copy()
        if subset.empty:
            continue
        for result in _confidence_threshold_sweep(
            subset,
            config,
        ):
            rows.append({
                "period": f"year_{year}",
                "period_start": str(
                    subset["race_date"].min().date()
                ),
                "period_end": str(
                    subset["race_date"].max().date()
                ),
                **result,
            })

    return rows


def _select_policy_candidates(
    frame: pd.DataFrame,
    *,
    confidence_threshold: float,
    config: StrategyConfig,
    policy: str,
) -> pd.DataFrame:
    probability = pd.to_numeric(
        frame["predicted_win_probability"],
        errors="coerce",
    )
    confidence = pd.to_numeric(
        frame["confidence"],
        errors="coerce",
    )
    odds = pd.to_numeric(
        frame["decimal_odds"],
        errors="coerce",
    )
    eligible = frame.loc[
        probability.ge(config.min_probability)
        & confidence.ge(confidence_threshold)
        & (probability * odds).ge(config.min_ev)
    ].copy()
    if eligible.empty or policy == "all_candidates":
        return eligible

    eligible["_ev"] = (
        pd.to_numeric(
            eligible["predicted_win_probability"],
            errors="coerce",
        )
        * pd.to_numeric(
            eligible["decimal_odds"],
            errors="coerce",
        )
    )
    eligible["_p"] = pd.to_numeric(
        eligible["predicted_win_probability"],
        errors="coerce",
    )

    if policy == "top1_ev_per_race":
        ordered = eligible.sort_values(
            ["race_id", "_ev", "_p", "horse_id"],
            ascending=[True, False, False, True],
            kind="stable",
        )
    elif policy == "top1_probability_per_race":
        ordered = eligible.sort_values(
            ["race_id", "_p", "_ev", "horse_id"],
            ascending=[True, False, False, True],
            kind="stable",
        )
    else:
        raise ValueError(
            f"unknown candidate selection policy: {policy}"
        )

    return (
        ordered.groupby("race_id", sort=False, as_index=False)
        .head(1)
        .drop(columns=["_ev", "_p"])
    )


def _policy_result(
    selected: pd.DataFrame,
    *,
    period: str,
    threshold: float,
    policy: str,
) -> dict:
    if selected.empty:
        return {
            "period": period,
            "confidence_threshold": threshold,
            "policy": policy,
            "rows": 0,
            "races": 0,
            "wins": 0,
            "hit_rate": None,
            "flat_bet_roi_final_odds": None,
        }

    finish = pd.to_numeric(
        selected["finish_position"],
        errors="coerce",
    )
    odds = pd.to_numeric(
        selected["decimal_odds"],
        errors="coerce",
    )
    wins_mask = finish.eq(1)
    wins = int(wins_mask.sum())
    flat_return = float(
        odds.where(wins_mask, 0.0).mean()
    )
    return {
        "period": period,
        "confidence_threshold": threshold,
        "policy": policy,
        "rows": int(len(selected)),
        "races": int(selected["race_id"].nunique()),
        "wins": wins,
        "hit_rate": _safe_float(wins / len(selected)),
        "flat_bet_roi_final_odds": _safe_float(
            flat_return - 1.0
        ),
    }


def _candidate_selection_policy_sweep_by_period(
    frame: pd.DataFrame,
    config: StrategyConfig,
    thresholds: tuple[float, ...] = (
        0.0,
        0.10,
        0.20,
        0.35,
        0.55,
    ),
) -> list[dict]:
    periods = (
        (
            "development_2021_2024",
            pd.Timestamp("2021-08-01"),
            pd.Timestamp("2024-12-31"),
        ),
        (
            "holdout_2025_2026",
            pd.Timestamp("2025-01-01"),
            pd.Timestamp("2026-12-31"),
        ),
    )
    policies = (
        "all_candidates",
        "top1_ev_per_race",
        "top1_probability_per_race",
    )
    results: list[dict] = []

    for label, start, end in periods:
        subset = frame.loc[
            frame["race_date"].between(
                start,
                end,
                inclusive="both",
            )
        ].copy()
        if subset.empty:
            continue

        for threshold in thresholds:
            for policy in policies:
                selected = _select_policy_candidates(
                    subset,
                    confidence_threshold=threshold,
                    config=config,
                    policy=policy,
                )
                results.append(
                    _policy_result(
                        selected,
                        period=label,
                        threshold=threshold,
                        policy=policy,
                    )
                )

    return results


def summarize_prediction_diagnostics(
    predictions: pd.DataFrame,
    *,
    config: StrategyConfig | None = None,
    starting_bankroll_yen: int = 100_000,
) -> dict:
    config = config or StrategyConfig()
    required = {
        "race_id",
        "race_date",
        "horse_id",
        "horse_name",
        "finish_position",
        "decimal_odds",
        "predicted_win_probability",
        "confidence",
        "model_version",
    }
    missing = required - set(predictions.columns)
    if missing:
        raise ValueError(
            f"missing Champion diagnostic columns: {sorted(missing)}"
        )
    if predictions.empty:
        raise ValueError("Champion diagnostic predictions are empty")

    frame = predictions.copy()
    frame["race_date"] = pd.to_datetime(
        frame["race_date"],
        errors="raise",
    )
    frame["decimal_odds"] = pd.to_numeric(
        frame["decimal_odds"],
        errors="coerce",
    )
    frame["finish_position"] = pd.to_numeric(
        frame["finish_position"],
        errors="coerce",
    )
    frame = frame.loc[
        frame["decimal_odds"].gt(1.0)
        & frame["finish_position"].notna()
    ].copy()
    if frame.empty:
        raise ValueError(
            "Champion diagnostic has no completed rows with valid odds"
        )

    frame["selection_reason"] = _selection_reason(
        frame,
        config,
    )
    reason_counts = {
        str(key): int(value)
        for key, value in frame["selection_reason"]
        .value_counts()
        .sort_index()
        .items()
    }
    for key in (
        "probability_below_threshold",
        "confidence_below_threshold",
        "ev_below_threshold",
        "eligible",
    ):
        reason_counts.setdefault(key, 0)

    race_confidence = (
        frame.groupby("race_id", sort=False)["confidence"]
        .first()
        .astype(float)
    )
    confidence_quantiles = {
        str(label): _safe_float(value)
        for label, value in race_confidence.quantile(
            [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99, 1.0]
        ).items()
    }

    _details, backtest = simulate_win_strategy(
        frame,
        starting_bankroll_yen=starting_bankroll_yen,
        config=config,
        odds_evidence=FINAL_WIN_ODDS,
    )

    return {
        "status": "research_only_frozen_champion_diagnostic",
        "warning": (
            "Historical final win odds are used here only to diagnose the "
            "frozen Champion and current selection thresholds. This is not "
            "forward-captured pre-race odds and must not be treated as "
            "verified live profitability."
        ),
        "period": {
            "start": str(frame["race_date"].min().date()),
            "end": str(frame["race_date"].max().date()),
        },
        "rows": int(len(frame)),
        "races": int(frame["race_id"].nunique()),
        "config": {
            "min_ev": float(config.min_ev),
            "min_probability": float(config.min_probability),
            "min_confidence": float(config.min_confidence),
            "fractional_kelly": float(config.fractional_kelly),
            "max_race_fraction": float(config.max_race_fraction),
            "max_day_fraction": float(config.max_day_fraction),
        },
        "selection_reason_counts": reason_counts,
        "race_confidence_quantiles": confidence_quantiles,
        "confidence_threshold_sweep": (
            _confidence_threshold_sweep(frame, config)
        ),
        "confidence_threshold_sweep_by_period": (
            _confidence_threshold_sweep_by_period(
                frame,
                config,
            )
        ),
        "candidate_selection_policy_sweep_by_period": (
            _candidate_selection_policy_sweep_by_period(
                frame,
                config,
            )
        ),
        "current_config_backtest_final_odds": asdict(backtest),
        "oos_style_diagnostics": build_oos_diagnostics(frame),
    }


def build_frozen_champion_predictions(
    history: pd.DataFrame,
    champion: LoadedChampion,
    *,
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    if history.empty:
        raise ValueError("history is empty")

    data = align_history_to_training_start(
        history,
        train_start=champion.manifest.train_start,
    )
    built = build_pre_race_features(data)

    missing_features = (
        set(champion.manifest.feature_columns)
        - set(built.frame.columns)
    )
    if missing_features:
        raise ValueError(
            "current history is missing Champion features: "
            f"{sorted(missing_features)}"
        )

    train_end = pd.Timestamp(
        champion.manifest.train_end
    ).normalize()
    evaluation_start = train_end + pd.Timedelta(days=1)
    if start_date is not None:
        evaluation_start = max(
            evaluation_start,
            pd.Timestamp(start_date).normalize(),
        )

    evaluation_end = built.frame["race_date"].max().normalize()
    if end_date is not None:
        evaluation_end = min(
            evaluation_end,
            pd.Timestamp(end_date).normalize(),
        )
    if evaluation_end < evaluation_start:
        raise ValueError(
            "no post-training history exists in the requested period"
        )

    evaluation = built.frame.loc[
        built.frame["race_date"].between(
            evaluation_start,
            evaluation_end,
            inclusive="both",
        )
    ].copy()
    evaluation = evaluation.loc[
        pd.to_numeric(
            evaluation["finish_position"],
            errors="coerce",
        ).notna()
        & pd.to_numeric(
            evaluation["win_odds"],
            errors="coerce",
        ).gt(1.0)
    ].copy()
    if evaluation.empty:
        raise ValueError(
            "no valid completed post-training rows remain"
        )

    probability = champion.model.predict_win_probability(
        evaluation,
        race_col="race_id",
    )
    confidence = probability.groupby(
        evaluation["race_id"],
    ).transform(race_certainty)

    predictions = evaluation[
        [
            "race_id",
            "race_date",
            "horse_name",
            "finish_position",
            "win_odds",
        ]
    ].copy()
    if "post_position" in evaluation.columns:
        post_position = pd.to_numeric(
            evaluation["post_position"],
            errors="coerce",
        ).astype("Int64")
        predictions["horse_id"] = (
            evaluation["race_id"].astype(str)
            + "-"
            + post_position.astype(str)
        )
    else:
        predictions["horse_id"] = (
            evaluation["race_id"].astype(str)
            + "-"
            + evaluation.groupby("race_id")
            .cumcount()
            .add(1)
            .astype(str)
        )

    predictions["decimal_odds"] = pd.to_numeric(
        predictions["win_odds"],
        errors="coerce",
    )
    predictions["predicted_win_probability"] = probability
    predictions["confidence"] = confidence
    predictions["model_version"] = (
        champion.manifest.model_version
    )
    return predictions.reset_index(drop=True)


def evaluate_frozen_champion_history(
    history: pd.DataFrame,
    champion: LoadedChampion,
    *,
    config: StrategyConfig | None = None,
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp | None = None,
    starting_bankroll_yen: int = 100_000,
) -> dict:
    predictions = build_frozen_champion_predictions(
        history,
        champion,
        start_date=start_date,
        end_date=end_date,
    )
    summary = summarize_prediction_diagnostics(
        predictions,
        config=config,
        starting_bankroll_yen=starting_bankroll_yen,
    )
    summary["champion"] = {
        "model_version": champion.manifest.model_version,
        "experiment_id": champion.manifest.experiment_id,
        "train_start": champion.manifest.train_start,
        "train_end": champion.manifest.train_end,
        "validation_research_roi": (
            champion.manifest.validation_research_roi
        ),
    }
    return summary

