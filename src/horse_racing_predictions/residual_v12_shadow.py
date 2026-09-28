from __future__ import annotations

import math
from typing import Callable

import pandas as pd

from .calibration import winner_log_loss
from .evaluation import brier_score, binary_log_loss
from .feature_window import align_history_to_training_start
from .features import build_pre_race_features
from .inference import build_future_feature_frame
from .jravan import JraVanApiError, JvLinkClient
from .jravan_realtime_settlement import capture_completed_race_0b12
from .market_aware_ranker_v11 import (
    MARKET_CONTEXT_FEATURES,
    add_market_context_features,
)
from .market_blend_research import normalized_market_probability
from .market_residual_v12 import (
    MarketResidualRegressor,
    residual_adjusted_probability,
)
from .market_residual_v12_holdout import FIXED_GAMMA
from .model_artifact import LoadedChampion


def _safe_float(value) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None


def _latest_odds(odds: pd.DataFrame) -> pd.DataFrame:
    required = {
        "race_id",
        "horse_id",
        "decimal_odds",
        "observed_at",
        "scheduled_post_time",
    }
    missing = required - set(odds.columns)
    if missing:
        raise ValueError(
            f"shadow odds missing columns: {sorted(missing)}"
        )
    if odds.empty:
        raise ValueError("shadow odds are empty")

    frame = odds.copy()
    frame["race_id"] = frame["race_id"].astype(str)
    frame["horse_id"] = frame["horse_id"].astype(str)
    frame["decimal_odds"] = pd.to_numeric(
        frame["decimal_odds"],
        errors="raise",
    )
    if not frame["decimal_odds"].gt(1.0).all():
        raise ValueError(
            "shadow odds must be decimal odds greater than 1.0"
        )
    frame["observed_at"] = pd.to_datetime(
        frame["observed_at"],
        errors="raise",
        utc=True,
    )
    frame["scheduled_post_time"] = pd.to_datetime(
        frame["scheduled_post_time"],
        errors="raise",
        utc=True,
    )
    if not (
        frame["observed_at"]
        < frame["scheduled_post_time"]
    ).all():
        raise ValueError(
            "shadow odds must be observed before scheduled post time"
        )

    frame = (
        frame.sort_values(
            ["race_id", "horse_id", "observed_at"],
            kind="stable",
        )
        .groupby(
            ["race_id", "horse_id"],
            sort=False,
            as_index=False,
        )
        .tail(1)
        .copy()
    )
    return frame


def build_residual_v12_shadow_predictions(
    history: pd.DataFrame,
    entries: pd.DataFrame,
    odds: pd.DataFrame,
    champion: LoadedChampion,
    *,
    iterations: int = 350,
    fixed_gamma: float = FIXED_GAMMA,
    max_history_gap_days: int = 14,
) -> pd.DataFrame:
    if iterations < 1:
        raise ValueError("iterations must be positive")
    if fixed_gamma != FIXED_GAMMA:
        raise ValueError(
            "Residual v12 shadow must use frozen gamma=4.0"
        )

    aligned_history = align_history_to_training_start(
        history,
        train_start=champion.manifest.train_start,
    )
    history_features = build_pre_race_features(
        aligned_history,
        experimental_ranker_v10=True,
    )
    history_market = add_market_context_features(
        history_features.frame
    )
    feature_columns = (
        tuple(history_features.feature_columns)
        + MARKET_CONTEXT_FEATURES
    )

    history_dates = pd.to_datetime(
        history_market["race_date"],
        errors="raise",
    )
    train_end = pd.Timestamp(
        champion.manifest.train_end
    ).normalize()
    train = history_market.loc[
        history_dates.le(train_end)
    ].copy()
    if train.empty:
        raise ValueError(
            "Residual v12 shadow training frame is empty"
        )

    train_market_probability = normalized_market_probability(
        train.rename(
            columns={"win_odds": "decimal_odds"}
        )
    )
    train_outcome = (
        pd.to_numeric(
            train["finish_position"],
            errors="coerce",
        )
        .eq(1)
        .astype(float)
    )
    train_target = (
        train_outcome - train_market_probability
    )

    model = MarketResidualRegressor(
        list(feature_columns),
        iterations=iterations,
    ).fit(
        train,
        train_target,
    )

    future = build_future_feature_frame(
        aligned_history,
        entries,
        history_features.feature_columns,
        max_history_gap_days=max_history_gap_days,
        experimental_ranker_v10=True,
    )
    if "post_position" not in future.columns:
        raise ValueError(
            "Residual v12 shadow future frame lacks post_position"
        )
    future["horse_id"] = (
        future["race_id"].astype(str)
        + "-"
        + future["post_position"].astype("Int64").astype(str)
    )

    latest = _latest_odds(odds)
    join_columns = [
        "race_id",
        "horse_id",
        "decimal_odds",
        "observed_at",
        "scheduled_post_time",
    ]
    if "source" in latest.columns:
        join_columns.append("source")
    if "source_reference" in latest.columns:
        join_columns.append("source_reference")

    future = future.merge(
        latest[join_columns],
        on=["race_id", "horse_id"],
        how="left",
        validate="one_to_one",
    )
    if future["decimal_odds"].isna().any():
        missing_rows = int(
            future["decimal_odds"].isna().sum()
        )
        raise ValueError(
            "Residual v12 shadow lacks complete pre-race odds: "
            f"missing_rows={missing_rows}"
        )

    future["win_odds"] = pd.to_numeric(
        future["decimal_odds"],
        errors="raise",
    )
    future_market = add_market_context_features(
        future
    )
    residual = model.predict(
        future_market
    )
    market_probability = pd.to_numeric(
        future_market["market_implied_probability"],
        errors="raise",
    ).astype(float)
    adjusted = residual_adjusted_probability(
        future_market,
        market_probability,
        residual,
        gamma=fixed_gamma,
    )
    overlay_ratio = (
        adjusted
        / market_probability.clip(lower=1e-12)
        - 1.0
    )

    output_columns = [
        "race_id",
        "race_date",
        "horse_id",
        "horse_name",
        "post_position",
        "decimal_odds",
        "observed_at",
        "scheduled_post_time",
    ]
    for optional in (
        "source",
        "source_reference",
    ):
        if optional in future_market.columns:
            output_columns.append(optional)

    output = future_market[
        output_columns
    ].copy()
    output["market_probability"] = market_probability
    output["residual_prediction"] = residual
    output["residual_v12_probability"] = adjusted
    output["overlay_ratio"] = overlay_ratio
    output["fixed_gamma"] = float(fixed_gamma)
    output["model_version"] = (
        "shadow-market-residual-v12"
    )
    output["model_train_end"] = (
        champion.manifest.train_end
    )
    output["history_cutoff"] = str(
        pd.to_datetime(
            aligned_history["race_date"],
            errors="raise",
        ).max().date()
    )

    for probability_column in (
        "market_probability",
        "residual_v12_probability",
    ):
        sums = output.groupby("race_id")[
            probability_column
        ].sum()
        if not (
            sums.sub(1.0).abs() < 1e-9
        ).all():
            raise RuntimeError(
                f"{probability_column} failed race normalization"
            )

    return output.sort_values(
        ["race_date", "race_id", "post_position"],
        kind="stable",
    ).reset_index(drop=True)


def summarize_shadow_predictions(
    predictions: pd.DataFrame,
) -> dict:
    if predictions.empty:
        raise ValueError(
            "Residual v12 shadow predictions are empty"
        )
    overlay = pd.to_numeric(
        predictions["overlay_ratio"],
        errors="raise",
    )
    observed = pd.to_datetime(
        predictions["observed_at"],
        errors="raise",
        utc=True,
    )
    scheduled = pd.to_datetime(
        predictions["scheduled_post_time"],
        errors="raise",
        utc=True,
    )
    lead_minutes = (
        scheduled - observed
    ).dt.total_seconds() / 60.0

    return {
        "status": "shadow_predictions_ready",
        "rows": int(len(predictions)),
        "races": int(
            predictions["race_id"].nunique()
        ),
        "positive_overlay_rows": int(
            overlay.gt(0.0).sum()
        ),
        "overlay_ge_5pct_rows": int(
            overlay.ge(0.05).sum()
        ),
        "overlay_ge_10pct_rows": int(
            overlay.ge(0.10).sum()
        ),
        "overlay_ge_20pct_rows": int(
            overlay.ge(0.20).sum()
        ),
        "mean_overlay_ratio": _safe_float(
            overlay.mean()
        ),
        "max_overlay_ratio": _safe_float(
            overlay.max()
        ),
        "min_lead_minutes": _safe_float(
            lead_minutes.min()
        ),
        "max_lead_minutes": _safe_float(
            lead_minutes.max()
        ),
        "fixed_gamma": float(
            predictions["fixed_gamma"].iloc[0]
        ),
    }


def capture_shadow_results_0b12(
    predictions: pd.DataFrame,
    *,
    client_factory: Callable[[], JvLinkClient] = JvLinkClient,
) -> tuple[pd.DataFrame, int]:
    frames: list[pd.DataFrame] = []
    errors = 0
    for race_id in sorted(
        predictions["race_id"].astype(str).unique()
    ):
        try:
            result = capture_completed_race_0b12(
                race_id,
                client_factory=client_factory,
                wait_retries=25,
                wait_seconds=0.2,
            )
        except (JraVanApiError, ValueError):
            errors += 1
            continue
        if not result.empty:
            frames.append(result)

    if not frames:
        return pd.DataFrame(), errors
    return (
        pd.concat(
            frames,
            ignore_index=True,
            sort=False,
        ),
        errors,
    )


def _quality(
    frame: pd.DataFrame,
    probability: pd.Series,
) -> dict:
    outcomes = (
        pd.to_numeric(
            frame["finish_position"],
            errors="raise",
        )
        .eq(1)
        .astype(int)
    )
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


def evaluate_shadow_results(
    predictions: pd.DataFrame,
    results: pd.DataFrame,
) -> dict:
    if results.empty:
        return {
            "status": "pending_results",
            "evaluated_rows": 0,
            "evaluated_races": 0,
        }

    required = {
        "race_id",
        "post_position",
        "finish_position",
    }
    missing = required - set(results.columns)
    if missing:
        raise ValueError(
            f"shadow results missing columns: {sorted(missing)}"
        )

    result_frame = results[
        ["race_id", "post_position", "finish_position"]
    ].copy()
    result_frame["race_id"] = (
        result_frame["race_id"].astype(str)
    )
    result_frame["post_position"] = pd.to_numeric(
        result_frame["post_position"],
        errors="raise",
    ).astype(int)
    result_frame = result_frame.drop_duplicates(
        ["race_id", "post_position"],
        keep=False,
    )

    merged = predictions.merge(
        result_frame,
        on=["race_id", "post_position"],
        how="inner",
        validate="one_to_one",
    )

    complete_races: list[str] = []
    prediction_counts = predictions.groupby(
        "race_id"
    ).size()
    result_counts = merged.groupby(
        "race_id"
    ).size()
    for race_id, count in prediction_counts.items():
        if result_counts.get(race_id, 0) != count:
            continue
        group = merged.loc[
            merged["race_id"].eq(race_id)
        ]
        if int(
            pd.to_numeric(
                group["finish_position"],
                errors="coerce",
            ).eq(1).sum()
        ) != 1:
            continue
        complete_races.append(str(race_id))

    evaluated = merged.loc[
        merged["race_id"].astype(str).isin(
            complete_races
        )
    ].copy()
    if evaluated.empty:
        return {
            "status": "pending_complete_results",
            "evaluated_rows": 0,
            "evaluated_races": 0,
        }

    market_quality = _quality(
        evaluated,
        pd.to_numeric(
            evaluated["market_probability"],
            errors="raise",
        ),
    )
    residual_quality = _quality(
        evaluated,
        pd.to_numeric(
            evaluated["residual_v12_probability"],
            errors="raise",
        ),
    )

    return {
        "status": "evaluated",
        "evaluated_rows": int(
            len(evaluated)
        ),
        "evaluated_races": int(
            evaluated["race_id"].nunique()
        ),
        "market_quality": market_quality,
        "residual_quality": residual_quality,
        "winner_log_loss_delta_vs_market": _safe_float(
            float(
                residual_quality["winner_log_loss"]
            )
            - float(
                market_quality["winner_log_loss"]
            )
        ),
        "brier_delta_vs_market": _safe_float(
            float(
                residual_quality["brier"]
            )
            - float(
                market_quality["brier"]
            )
        ),
        "beats_market_winner_log_loss": bool(
            float(
                residual_quality["winner_log_loss"]
            )
            < float(
                market_quality["winner_log_loss"]
            )
        ),
        "beats_market_brier": bool(
            float(
                residual_quality["brier"]
            )
            < float(
                market_quality["brier"]
            )
        ),
    }
