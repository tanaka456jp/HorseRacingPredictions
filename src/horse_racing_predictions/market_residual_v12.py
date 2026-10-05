from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .calibration import winner_log_loss
from .evaluation import brier_score, binary_log_loss
from .feature_window import align_history_to_training_start
from .features import build_pre_race_features
from .market_aware_ranker_v11 import (
    MARKET_CONTEXT_FEATURES,
    add_market_context_features,
)
from .market_blend_research import normalized_market_probability
from .model_artifact import LoadedChampion


GAMMA_GRID = (
    0.0,
    0.25,
    0.50,
    1.0,
    2.0,
    4.0,
    8.0,
    16.0,
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

EV_POLICIES = (
    "all_candidates",
    "top1_ev_per_race",
)


MARKET_EDGE_RATIO_THRESHOLDS = (
    1.00,
    1.005,
    1.01,
    1.02,
    1.03,
    1.05,
    1.075,
    1.10,
    1.15,
    1.20,
)

MARKET_EDGE_POLICIES = (
    "all_candidates",
    "top1_edge_per_race",
)


MARKET_EDGE_ODDS_SEGMENTS = (
    ("odds_1_to_3", 1.0, 3.0),
    ("odds_3_to_6", 3.0, 6.0),
    ("odds_6_to_12", 6.0, 12.0),
    ("odds_12_plus", 12.0, None),
)


LONGSHOT_ODDS_MIN = 6.0
LONGSHOT_SEGMENT_NAME = "odds_6_plus"

LONGSHOT_STABILITY_SPLIT_DATE = "2022-05-01"

STANDARDIZED_RESIDUAL_VARIANCE_FLOOR = 1e-4

ROLLING_REFIT_BOOTSTRAP_SAMPLES = 1000
ROLLING_REFIT_BOOTSTRAP_SEED = 20261006
ROLLING_REFIT_MIN_IMPROVEMENT_SUPPORT = 0.80


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


def _race_softmax(
    scores: pd.Series,
    race_ids: pd.Series,
) -> pd.Series:
    frame = pd.DataFrame({
        "race_id": race_ids.astype(str),
        "score": pd.to_numeric(
            scores,
            errors="raise",
        ).astype(float),
    }, index=scores.index)

    def _softmax(group: pd.Series) -> pd.Series:
        values = group.to_numpy(dtype=float)
        shifted = values - np.max(values)
        exp = np.exp(shifted)
        total = float(exp.sum())
        if total <= 0.0 or not math.isfinite(total):
            raise ValueError(
                "invalid race softmax denominator"
            )
        return pd.Series(
            exp / total,
            index=group.index,
        )

    probability = (
        frame.groupby(
            "race_id",
            group_keys=False,
            sort=False,
        )["score"]
        .apply(_softmax)
    )
    return probability.reindex(scores.index).astype(float)


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


def paired_race_bootstrap_quality_deltas(
    frame: pd.DataFrame,
    challenger_probability: pd.Series,
    baseline_probability: pd.Series,
    *,
    samples: int = ROLLING_REFIT_BOOTSTRAP_SAMPLES,
    seed: int = ROLLING_REFIT_BOOTSTRAP_SEED,
) -> dict:
    """Paired race bootstrap for challenger-minus-baseline quality deltas."""
    if samples < 1:
        raise ValueError("bootstrap samples must be positive")
    if not challenger_probability.index.equals(frame.index):
        raise ValueError("challenger probability index differs from frame")
    if not baseline_probability.index.equals(frame.index):
        raise ValueError("baseline probability index differs from frame")

    outcomes = _outcomes(frame).astype(float)
    evidence = pd.DataFrame(
        {
            "race_id": frame["race_id"].astype(str),
            "outcome": outcomes,
            "challenger": challenger_probability.astype(float),
            "baseline": baseline_probability.astype(float),
        },
        index=frame.index,
    )
    if not np.isfinite(
        evidence[["challenger", "baseline"]].to_numpy(dtype=float)
    ).all():
        raise ValueError("bootstrap probability contains non-finite value")

    eps = 1e-15
    race_logloss_delta: list[float] = []
    race_brier_sum_delta: list[float] = []
    race_row_count: list[int] = []
    for _, group in evidence.groupby("race_id", sort=False):
        winner = group["outcome"].eq(1.0)
        if int(winner.sum()) != 1:
            raise ValueError(
                "bootstrap race must contain exactly one winner"
            )
        challenger = group["challenger"].clip(eps, 1.0)
        baseline = group["baseline"].clip(eps, 1.0)
        challenger_winner = float(challenger.loc[winner].iloc[0])
        baseline_winner = float(baseline.loc[winner].iloc[0])
        race_logloss_delta.append(
            -math.log(challenger_winner)
            + math.log(baseline_winner)
        )
        target = group["outcome"].to_numpy(dtype=float)
        challenger_values = challenger.to_numpy(dtype=float)
        baseline_values = baseline.to_numpy(dtype=float)
        race_brier_sum_delta.append(
            float(
                np.square(challenger_values - target).sum()
                - np.square(baseline_values - target).sum()
            )
        )
        race_row_count.append(int(len(group)))

    logloss_delta = np.asarray(race_logloss_delta, dtype=float)
    brier_sum_delta = np.asarray(race_brier_sum_delta, dtype=float)
    row_count = np.asarray(race_row_count, dtype=float)
    race_count = int(len(logloss_delta))
    if race_count < 1:
        raise ValueError("bootstrap evidence contains no races")

    observed_logloss_delta = float(logloss_delta.mean())
    observed_brier_delta = float(
        brier_sum_delta.sum() / row_count.sum()
    )
    rng = np.random.default_rng(seed)
    draws = rng.integers(
        0,
        race_count,
        size=(int(samples), race_count),
    )
    sampled_logloss_delta = logloss_delta[draws].mean(axis=1)
    sampled_brier_delta = (
        brier_sum_delta[draws].sum(axis=1)
        / row_count[draws].sum(axis=1)
    )

    return {
        "samples": int(samples),
        "seed": int(seed),
        "races": race_count,
        "rows": int(row_count.sum()),
        "winner_log_loss_delta": _safe_float(
            observed_logloss_delta
        ),
        "brier_delta": _safe_float(observed_brier_delta),
        "winner_log_loss_improvement_support": _safe_float(
            np.mean(sampled_logloss_delta < 0.0)
        ),
        "brier_improvement_support": _safe_float(
            np.mean(sampled_brier_delta < 0.0)
        ),
        "winner_log_loss_delta_ci90": [
            _safe_float(np.quantile(sampled_logloss_delta, 0.05)),
            _safe_float(np.quantile(sampled_logloss_delta, 0.95)),
        ],
        "brier_delta_ci90": [
            _safe_float(np.quantile(sampled_brier_delta, 0.05)),
            _safe_float(np.quantile(sampled_brier_delta, 0.95)),
        ],
    }



def _select_ev_candidates(
    frame: pd.DataFrame,
    probability: pd.Series,
    *,
    ev_threshold: float,
    min_probability: float,
    policy: str,
) -> pd.DataFrame:
    if policy not in EV_POLICIES:
        raise ValueError(
            f"unknown EV selection policy: {policy}"
        )
    odds = pd.to_numeric(
        frame["win_odds"],
        errors="coerce",
    )
    expected_return = (
        probability.astype(float) * odds
    )
    selected = frame.loc[
        probability.ge(min_probability)
        & expected_return.ge(ev_threshold)
    ].copy()
    if selected.empty:
        return selected

    selected["_probability"] = probability.loc[
        selected.index
    ]
    selected["_expected_return"] = expected_return.loc[
        selected.index
    ]

    if policy == "top1_ev_per_race":
        selected = (
            selected.sort_values(
                [
                    "race_id",
                    "_expected_return",
                    "_probability",
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


def _ev_rule_result(
    selected: pd.DataFrame,
    *,
    ev_threshold: float,
    policy: str,
) -> dict:
    if selected.empty:
        return {
            "ev_threshold": float(ev_threshold),
            "policy": policy,
            "rows": 0,
            "races": 0,
            "wins": 0,
            "hit_rate": None,
            "average_probability": None,
            "average_expected_return": None,
            "flat_bet_roi_final_odds": None,
        }

    odds = pd.to_numeric(
        selected["win_odds"],
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
        "ev_threshold": float(ev_threshold),
        "policy": policy,
        "rows": int(len(selected)),
        "races": int(
            selected["race_id"].nunique()
        ),
        "wins": wins,
        "hit_rate": _safe_float(
            wins / len(selected)
        ),
        "average_probability": _safe_float(
            selected["_probability"].mean()
        ),
        "average_expected_return": _safe_float(
            selected["_expected_return"].mean()
        ),
        "flat_bet_roi_final_odds": _safe_float(
            flat_return - 1.0
        ),
    }


def residual_ev_threshold_sweep(
    frame: pd.DataFrame,
    probability: pd.Series,
    *,
    min_probability: float = 0.03,
    thresholds: tuple[float, ...] = EV_THRESHOLDS,
    policies: tuple[str, ...] = EV_POLICIES,
) -> list[dict]:
    rows: list[dict] = []
    for policy in policies:
        for threshold in thresholds:
            selected = _select_ev_candidates(
                frame,
                probability,
                ev_threshold=float(threshold),
                min_probability=min_probability,
                policy=policy,
            )
            rows.append(
                _ev_rule_result(
                    selected,
                    ev_threshold=float(threshold),
                    policy=policy,
                )
            )
    return rows


def fit_residual_ev_rule(
    frame: pd.DataFrame,
    probability: pd.Series,
    *,
    min_probability: float = 0.03,
    min_rows: int = 200,
    min_races: int = 100,
) -> tuple[dict | None, list[dict]]:
    sweep = residual_ev_threshold_sweep(
        frame,
        probability,
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
            float(row["flat_bet_roi_final_odds"]),
            int(row["rows"]),
            -float(row["ev_threshold"]),
        ),
    )
    return dict(best), sweep


def evaluate_fixed_residual_ev_rule(
    frame: pd.DataFrame,
    probability: pd.Series,
    rule: dict,
    *,
    min_probability: float = 0.03,
) -> dict:
    selected = _select_ev_candidates(
        frame,
        probability,
        ev_threshold=float(rule["ev_threshold"]),
        min_probability=min_probability,
        policy=str(rule["policy"]),
    )
    return _ev_rule_result(
        selected,
        ev_threshold=float(rule["ev_threshold"]),
        policy=str(rule["policy"]),
    )



def _select_market_edge_candidates(
    frame: pd.DataFrame,
    probability: pd.Series,
    market_probability: pd.Series,
    *,
    edge_ratio_threshold: float,
    min_probability: float,
    policy: str,
) -> pd.DataFrame:
    if policy not in MARKET_EDGE_POLICIES:
        raise ValueError(
            f"unknown market-edge policy: {policy}"
        )
    if not probability.index.equals(
        market_probability.index
    ):
        raise ValueError(
            "probability and market probability indexes differ"
        )

    market = market_probability.astype(float).clip(
        lower=1e-12,
        upper=1.0,
    )
    edge_ratio = probability.astype(float) / market
    odds = pd.to_numeric(
        frame["win_odds"],
        errors="coerce",
    )
    expected_return = probability.astype(float) * odds
    selected = frame.loc[
        probability.ge(min_probability)
        & edge_ratio.ge(edge_ratio_threshold)
    ].copy()
    if selected.empty:
        return selected

    selected["_probability"] = probability.loc[
        selected.index
    ]
    selected["_market_probability"] = market.loc[
        selected.index
    ]
    selected["_edge_ratio"] = edge_ratio.loc[
        selected.index
    ]
    selected["_expected_return"] = expected_return.loc[
        selected.index
    ]

    if policy == "top1_edge_per_race":
        selected = (
            selected.sort_values(
                [
                    "race_id",
                    "_edge_ratio",
                    "_expected_return",
                    "_probability",
                ],
                ascending=[True, False, False, False],
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


def _market_edge_rule_result(
    selected: pd.DataFrame,
    *,
    edge_ratio_threshold: float,
    policy: str,
) -> dict:
    if selected.empty:
        return {
            "edge_ratio_threshold": float(
                edge_ratio_threshold
            ),
            "policy": policy,
            "rows": 0,
            "races": 0,
            "wins": 0,
            "hit_rate": None,
            "average_probability": None,
            "average_market_probability": None,
            "average_edge_ratio": None,
            "average_expected_return": None,
            "flat_bet_roi_final_odds": None,
        }

    odds = pd.to_numeric(
        selected["win_odds"],
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
        "edge_ratio_threshold": float(
            edge_ratio_threshold
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
        "average_probability": _safe_float(
            selected["_probability"].mean()
        ),
        "average_market_probability": _safe_float(
            selected["_market_probability"].mean()
        ),
        "average_edge_ratio": _safe_float(
            selected["_edge_ratio"].mean()
        ),
        "average_expected_return": _safe_float(
            selected["_expected_return"].mean()
        ),
        "flat_bet_roi_final_odds": _safe_float(
            flat_return - 1.0
        ),
    }


def residual_market_edge_sweep(
    frame: pd.DataFrame,
    probability: pd.Series,
    market_probability: pd.Series,
    *,
    min_probability: float = 0.03,
    thresholds: tuple[float, ...] = MARKET_EDGE_RATIO_THRESHOLDS,
    policies: tuple[str, ...] = MARKET_EDGE_POLICIES,
) -> list[dict]:
    rows: list[dict] = []
    for policy in policies:
        for threshold in thresholds:
            selected = _select_market_edge_candidates(
                frame,
                probability,
                market_probability,
                edge_ratio_threshold=float(threshold),
                min_probability=min_probability,
                policy=policy,
            )
            rows.append(
                _market_edge_rule_result(
                    selected,
                    edge_ratio_threshold=float(threshold),
                    policy=policy,
                )
            )
    return rows


def fit_residual_market_edge_rule(
    frame: pd.DataFrame,
    probability: pd.Series,
    market_probability: pd.Series,
    *,
    min_probability: float = 0.03,
    min_rows: int = 200,
    min_races: int = 100,
) -> tuple[dict | None, list[dict]]:
    sweep = residual_market_edge_sweep(
        frame,
        probability,
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
            float(row["flat_bet_roi_final_odds"]),
            int(row["races"]),
            int(row["rows"]),
            -float(row["edge_ratio_threshold"]),
        ),
    )
    return dict(best), sweep


def select_broad_positive_market_edge_rule(
    sweep: list[dict],
    *,
    min_rows: int = 200,
    min_races: int = 100,
) -> dict | None:
    eligible = [
        row
        for row in sweep
        if row["rows"] >= min_rows
        and row["races"] >= min_races
        and row["flat_bet_roi_final_odds"] is not None
        and float(
            row["flat_bet_roi_final_odds"]
        ) > 0.0
    ]
    if not eligible:
        return None

    broadest = max(
        eligible,
        key=lambda row: (
            int(row["races"]),
            int(row["rows"]),
            -float(row["edge_ratio_threshold"]),
            row["policy"] == "all_candidates",
        ),
    )
    return dict(broadest)


def fit_broad_residual_market_edge_rule(
    frame: pd.DataFrame,
    probability: pd.Series,
    market_probability: pd.Series,
    *,
    min_probability: float = 0.03,
    min_rows: int = 200,
    min_races: int = 100,
) -> tuple[dict | None, list[dict]]:
    sweep = residual_market_edge_sweep(
        frame,
        probability,
        market_probability,
        min_probability=min_probability,
    )
    return (
        select_broad_positive_market_edge_rule(
            sweep,
            min_rows=min_rows,
            min_races=min_races,
        ),
        sweep,
    )


def evaluate_fixed_residual_market_edge_rule(
    frame: pd.DataFrame,
    probability: pd.Series,
    market_probability: pd.Series,
    rule: dict,
    *,
    min_probability: float = 0.03,
) -> dict:
    selected = _select_market_edge_candidates(
        frame,
        probability,
        market_probability,
        edge_ratio_threshold=float(
            rule["edge_ratio_threshold"]
        ),
        min_probability=min_probability,
        policy=str(rule["policy"]),
    )
    return _market_edge_rule_result(
        selected,
        edge_ratio_threshold=float(
            rule["edge_ratio_threshold"]
        ),
        policy=str(rule["policy"]),
    )


def _odds_segment_mask(
    frame: pd.DataFrame,
    *,
    odds_min: float,
    odds_max: float | None,
) -> pd.Series:
    odds = pd.to_numeric(
        frame["win_odds"],
        errors="coerce",
    )
    mask = odds.ge(float(odds_min))
    if odds_max is not None:
        mask &= odds.lt(float(odds_max))
    return mask.fillna(False)


def _market_edge_odds_segment_result(
    selected: pd.DataFrame,
    *,
    base_rule: dict,
    segment_name: str,
    odds_min: float,
    odds_max: float | None,
) -> dict:
    segment = selected.loc[
        _odds_segment_mask(
            selected,
            odds_min=odds_min,
            odds_max=odds_max,
        )
    ].copy()
    result = _market_edge_rule_result(
        segment,
        edge_ratio_threshold=float(
            base_rule["edge_ratio_threshold"]
        ),
        policy=str(base_rule["policy"]),
    )
    result.update({
        "segment_name": segment_name,
        "odds_min": float(odds_min),
        "odds_max": (
            None
            if odds_max is None
            else float(odds_max)
        ),
    })
    return result


def residual_market_edge_odds_segment_sweep(
    frame: pd.DataFrame,
    probability: pd.Series,
    market_probability: pd.Series,
    base_rule: dict,
    *,
    min_probability: float = 0.03,
) -> list[dict]:
    selected = _select_market_edge_candidates(
        frame,
        probability,
        market_probability,
        edge_ratio_threshold=float(
            base_rule["edge_ratio_threshold"]
        ),
        min_probability=min_probability,
        policy=str(base_rule["policy"]),
    )
    return [
        _market_edge_odds_segment_result(
            selected,
            base_rule=base_rule,
            segment_name=name,
            odds_min=odds_min,
            odds_max=odds_max,
        )
        for name, odds_min, odds_max
        in MARKET_EDGE_ODDS_SEGMENTS
    ]


def select_broad_positive_market_edge_odds_segment(
    sweep: list[dict],
    *,
    min_rows: int = 200,
    min_races: int = 100,
) -> dict | None:
    eligible = [
        row
        for row in sweep
        if row["rows"] >= min_rows
        and row["races"] >= min_races
        and row["flat_bet_roi_final_odds"] is not None
        and float(
            row["flat_bet_roi_final_odds"]
        ) > 0.0
    ]
    if not eligible:
        return None
    return dict(max(
        eligible,
        key=lambda row: (
            int(row["races"]),
            int(row["rows"]),
            -float(row["odds_min"]),
        ),
    ))


def fit_residual_market_edge_odds_segment_rule(
    frame: pd.DataFrame,
    probability: pd.Series,
    market_probability: pd.Series,
    base_rule: dict | None,
    *,
    min_probability: float = 0.03,
    min_rows: int = 200,
    min_races: int = 100,
) -> tuple[dict | None, list[dict]]:
    if base_rule is None:
        return None, []
    sweep = residual_market_edge_odds_segment_sweep(
        frame,
        probability,
        market_probability,
        base_rule,
        min_probability=min_probability,
    )
    return (
        select_broad_positive_market_edge_odds_segment(
            sweep,
            min_rows=min_rows,
            min_races=min_races,
        ),
        sweep,
    )


def evaluate_fixed_residual_market_edge_odds_segment_rule(
    frame: pd.DataFrame,
    probability: pd.Series,
    market_probability: pd.Series,
    rule: dict,
    *,
    min_probability: float = 0.03,
) -> dict:
    selected = _select_market_edge_candidates(
        frame,
        probability,
        market_probability,
        edge_ratio_threshold=float(
            rule["edge_ratio_threshold"]
        ),
        min_probability=min_probability,
        policy=str(rule["policy"]),
    )
    return _market_edge_odds_segment_result(
        selected,
        base_rule=rule,
        segment_name=str(rule["segment_name"]),
        odds_min=float(rule["odds_min"]),
        odds_max=rule["odds_max"],
    )


def residual_longshot_market_edge_sweep(
    frame: pd.DataFrame,
    probability: pd.Series,
    market_probability: pd.Series,
    *,
    min_probability: float = 0.03,
    thresholds: tuple[float, ...] = MARKET_EDGE_RATIO_THRESHOLDS,
) -> list[dict]:
    rows: list[dict] = []
    for threshold in thresholds:
        base_rule = {
            "edge_ratio_threshold": float(threshold),
            "policy": "all_candidates",
        }
        selected = _select_market_edge_candidates(
            frame,
            probability,
            market_probability,
            edge_ratio_threshold=float(threshold),
            min_probability=min_probability,
            policy="all_candidates",
        )
        rows.append(
            _market_edge_odds_segment_result(
                selected,
                base_rule=base_rule,
                segment_name=LONGSHOT_SEGMENT_NAME,
                odds_min=LONGSHOT_ODDS_MIN,
                odds_max=None,
            )
        )
    return rows


def select_broad_positive_longshot_market_edge_rule(
    sweep: list[dict],
    *,
    min_rows: int = 200,
    min_races: int = 100,
) -> dict | None:
    eligible = [
        row
        for row in sweep
        if row["rows"] >= min_rows
        and row["races"] >= min_races
        and row["flat_bet_roi_final_odds"] is not None
        and float(
            row["flat_bet_roi_final_odds"]
        ) > 0.0
    ]
    if not eligible:
        return None
    return dict(max(
        eligible,
        key=lambda row: (
            int(row["races"]),
            int(row["rows"]),
            -float(row["edge_ratio_threshold"]),
        ),
    ))


def fit_residual_longshot_market_edge_rule(
    frame: pd.DataFrame,
    probability: pd.Series,
    market_probability: pd.Series,
    *,
    min_probability: float = 0.03,
    min_rows: int = 200,
    min_races: int = 100,
) -> tuple[dict | None, list[dict]]:
    sweep = residual_longshot_market_edge_sweep(
        frame,
        probability,
        market_probability,
        min_probability=min_probability,
    )
    return (
        select_broad_positive_longshot_market_edge_rule(
            sweep,
            min_rows=min_rows,
            min_races=min_races,
        ),
        sweep,
    )


def evaluate_fixed_residual_longshot_market_edge_rule(
    frame: pd.DataFrame,
    probability: pd.Series,
    market_probability: pd.Series,
    rule: dict,
    *,
    min_probability: float = 0.03,
) -> dict:
    selected = _select_market_edge_candidates(
        frame,
        probability,
        market_probability,
        edge_ratio_threshold=float(
            rule["edge_ratio_threshold"]
        ),
        min_probability=min_probability,
        policy="all_candidates",
    )
    return _market_edge_odds_segment_result(
        selected,
        base_rule=rule,
        segment_name=LONGSHOT_SEGMENT_NAME,
        odds_min=LONGSHOT_ODDS_MIN,
        odds_max=None,
    )


def residual_stable_longshot_market_edge_sweep(
    frame: pd.DataFrame,
    probability: pd.Series,
    market_probability: pd.Series,
    *,
    min_probability: float = 0.03,
    split_date: str = LONGSHOT_STABILITY_SPLIT_DATE,
    thresholds: tuple[float, ...] = MARKET_EDGE_RATIO_THRESHOLDS,
) -> list[dict]:
    dates = pd.to_datetime(
        frame["race_date"],
        errors="raise",
    )
    split = pd.Timestamp(split_date)
    early_index = frame.index[dates.lt(split)]
    late_index = frame.index[dates.ge(split)]
    if len(early_index) == 0 or len(late_index) == 0:
        raise ValueError(
            "longshot stability split contains an empty period"
        )

    rows: list[dict] = []
    for threshold in thresholds:
        rule = {
            "edge_ratio_threshold": float(threshold),
            "policy": "all_candidates",
        }
        overall = evaluate_fixed_residual_longshot_market_edge_rule(
            frame,
            probability,
            market_probability,
            rule,
            min_probability=min_probability,
        )
        early = evaluate_fixed_residual_longshot_market_edge_rule(
            frame.loc[early_index],
            probability.loc[early_index],
            market_probability.loc[early_index],
            rule,
            min_probability=min_probability,
        )
        late = evaluate_fixed_residual_longshot_market_edge_rule(
            frame.loc[late_index],
            probability.loc[late_index],
            market_probability.loc[late_index],
            rule,
            min_probability=min_probability,
        )
        rows.append({
            **overall,
            "stability_split_date": str(split.date()),
            "early_rows": int(early["rows"]),
            "early_races": int(early["races"]),
            "early_flat_bet_roi_final_odds": early[
                "flat_bet_roi_final_odds"
            ],
            "late_rows": int(late["rows"]),
            "late_races": int(late["races"]),
            "late_flat_bet_roi_final_odds": late[
                "flat_bet_roi_final_odds"
            ],
        })
    return rows


def select_temporally_stable_longshot_market_edge_rule(
    sweep: list[dict],
    *,
    min_rows: int = 200,
    min_races: int = 100,
    min_fold_rows: int = 100,
    min_fold_races: int = 50,
) -> dict | None:
    eligible = [
        row
        for row in sweep
        if row["rows"] >= min_rows
        and row["races"] >= min_races
        and row["early_rows"] >= min_fold_rows
        and row["early_races"] >= min_fold_races
        and row["late_rows"] >= min_fold_rows
        and row["late_races"] >= min_fold_races
        and row["flat_bet_roi_final_odds"] is not None
        and row["early_flat_bet_roi_final_odds"] is not None
        and row["late_flat_bet_roi_final_odds"] is not None
        and float(row["flat_bet_roi_final_odds"]) > 0.0
        and float(row["early_flat_bet_roi_final_odds"]) > 0.0
        and float(row["late_flat_bet_roi_final_odds"]) > 0.0
    ]
    if not eligible:
        return None
    return dict(max(
        eligible,
        key=lambda row: (
            int(row["races"]),
            int(row["rows"]),
            -float(row["edge_ratio_threshold"]),
        ),
    ))


def fit_residual_stable_longshot_market_edge_rule(
    frame: pd.DataFrame,
    probability: pd.Series,
    market_probability: pd.Series,
    *,
    min_probability: float = 0.03,
    min_rows: int = 200,
    min_races: int = 100,
    min_fold_rows: int = 100,
    min_fold_races: int = 50,
) -> tuple[dict | None, list[dict]]:
    sweep = residual_stable_longshot_market_edge_sweep(
        frame,
        probability,
        market_probability,
        min_probability=min_probability,
    )
    return (
        select_temporally_stable_longshot_market_edge_rule(
            sweep,
            min_rows=min_rows,
            min_races=min_races,
            min_fold_rows=min_fold_rows,
            min_fold_races=min_fold_races,
        ),
        sweep,
    )


def market_residual_scale(
    market_probability: pd.Series,
    *,
    variance_floor: float = STANDARDIZED_RESIDUAL_VARIANCE_FLOOR,
) -> pd.Series:
    if variance_floor <= 0.0:
        raise ValueError(
            "variance_floor must be positive"
        )
    market = market_probability.astype(float).clip(
        lower=1e-12,
        upper=1.0 - 1e-12,
    )
    variance = (
        market * (1.0 - market)
    ).clip(lower=float(variance_floor))
    return pd.Series(
        np.sqrt(variance),
        index=market_probability.index,
        dtype=float,
    )


def standardized_market_residual_target(
    frame: pd.DataFrame,
    market_probability: pd.Series,
    *,
    variance_floor: float = STANDARDIZED_RESIDUAL_VARIANCE_FLOOR,
) -> pd.Series:
    if not frame.index.equals(
        market_probability.index
    ):
        raise ValueError(
            "frame and market probability indexes differ"
        )
    raw_residual = (
        _outcomes(frame).astype(float)
        - market_probability.astype(float)
    )
    scale = market_residual_scale(
        market_probability,
        variance_floor=variance_floor,
    )
    return pd.Series(
        raw_residual / scale,
        index=frame.index,
        dtype=float,
    )


def restore_standardized_market_residual(
    market_probability: pd.Series,
    standardized_prediction: pd.Series,
    *,
    variance_floor: float = STANDARDIZED_RESIDUAL_VARIANCE_FLOOR,
) -> pd.Series:
    if not market_probability.index.equals(
        standardized_prediction.index
    ):
        raise ValueError(
            "market probability and standardized prediction indexes differ"
        )
    prediction = pd.to_numeric(
        standardized_prediction,
        errors="raise",
    ).astype(float)
    if not np.isfinite(
        prediction.to_numpy()
    ).all():
        raise ValueError(
            "standardized prediction contains non-finite values"
        )
    scale = market_residual_scale(
        market_probability,
        variance_floor=variance_floor,
    )
    return pd.Series(
        prediction * scale,
        index=market_probability.index,
        dtype=float,
    )


def realized_flat_bet_return(
    frame: pd.DataFrame,
) -> pd.Series:
    odds = pd.to_numeric(
        frame["win_odds"],
        errors="raise",
    ).astype(float)
    return (
        _outcomes(frame).astype(float) * odds
        - 1.0
    )


def direct_value_rule_result(
    frame: pd.DataFrame,
    predicted_return: pd.Series,
    *,
    threshold: float = 0.0,
) -> dict:
    if not frame.index.equals(
        predicted_return.index
    ):
        raise ValueError(
            "frame and predicted return indexes differ"
        )
    score = pd.to_numeric(
        predicted_return,
        errors="raise",
    ).astype(float)
    if not np.isfinite(score.to_numpy()).all():
        raise ValueError(
            "predicted return contains non-finite values"
        )

    selected = frame.loc[
        score.gt(float(threshold))
    ].copy()
    if selected.empty:
        return {
            "predicted_return_threshold": float(threshold),
            "rows": 0,
            "races": 0,
            "wins": 0,
            "hit_rate": None,
            "average_predicted_return": None,
            "flat_bet_roi_final_odds": None,
        }

    selected_score = score.loc[selected.index]
    realized = realized_flat_bet_return(
        selected
    )
    wins = int(
        _outcomes(selected).sum()
    )
    return {
        "predicted_return_threshold": float(threshold),
        "rows": int(len(selected)),
        "races": int(
            selected["race_id"].nunique()
        ),
        "wins": wins,
        "hit_rate": _safe_float(
            wins / len(selected)
        ),
        "average_predicted_return": _safe_float(
            selected_score.mean()
        ),
        "flat_bet_roi_final_odds": _safe_float(
            realized.mean()
        ),
    }


def fit_direct_value_rule(
    frame: pd.DataFrame,
    predicted_return: pd.Series,
    *,
    threshold: float = 0.0,
    min_rows: int = 200,
    min_races: int = 100,
) -> tuple[dict | None, dict]:
    evidence = direct_value_rule_result(
        frame,
        predicted_return,
        threshold=threshold,
    )
    qualifies = bool(
        evidence["rows"] >= min_rows
        and evidence["races"] >= min_races
        and evidence["flat_bet_roi_final_odds"] is not None
        and float(
            evidence["flat_bet_roi_final_odds"]
        ) > 0.0
    )
    rule = (
        {
            "predicted_return_threshold": float(threshold),
            "selection": "predicted_return_gt_threshold",
        }
        if qualifies
        else None
    )
    return rule, evidence


def evaluate_fixed_direct_value_rule(
    frame: pd.DataFrame,
    predicted_return: pd.Series,
    rule: dict,
) -> dict:
    return direct_value_rule_result(
        frame,
        predicted_return,
        threshold=float(
            rule["predicted_return_threshold"]
        ),
    )


class MarketResidualRegressor:
    def __init__(
        self,
        feature_columns: list[str],
        *,
        iterations: int = 350,
        depth: int = 7,
        learning_rate: float = 0.05,
        random_seed: int = 42,
    ) -> None:
        self.feature_columns = list(feature_columns)
        self.iterations = int(iterations)
        self.depth = int(depth)
        self.learning_rate = float(learning_rate)
        self.random_seed = int(random_seed)
        self.model = None
        self.categorical_columns: list[str] = []

    def _prepare(
        self,
        frame: pd.DataFrame,
    ) -> pd.DataFrame:
        out = frame[self.feature_columns].copy()
        for column in self.feature_columns:
            if pd.api.types.is_numeric_dtype(
                out[column]
            ):
                out[column] = pd.to_numeric(
                    out[column],
                    errors="coerce",
                )
            else:
                out[column] = (
                    out[column]
                    .astype("string")
                    .fillna("UNKNOWN")
                    .astype(str)
                )
        return out

    def fit(
        self,
        frame: pd.DataFrame,
        target: pd.Series,
    ) -> "MarketResidualRegressor":
        try:
            from catboost import CatBoostRegressor
        except ImportError as exc:
            raise RuntimeError(
                "Market residual research requires the research extra: "
                "pip install -e '.[research]'"
            ) from exc

        if len(frame) != len(target):
            raise ValueError(
                "residual target length must match training frame"
            )

        x = self._prepare(frame)
        self.categorical_columns = [
            column
            for column in self.feature_columns
            if not pd.api.types.is_numeric_dtype(
                x[column]
            )
        ]
        y = pd.to_numeric(
            target,
            errors="raise",
        ).astype(float)

        self.model = CatBoostRegressor(
            iterations=self.iterations,
            depth=self.depth,
            learning_rate=self.learning_rate,
            loss_function="RMSE",
            random_seed=self.random_seed,
            verbose=False,
            allow_writing_files=False,
            thread_count=-1,
            l2_leaf_reg=5.0,
        )
        self.model.fit(
            x,
            y,
            cat_features=self.categorical_columns,
        )
        return self

    def predict(
        self,
        frame: pd.DataFrame,
    ) -> pd.Series:
        if self.model is None:
            raise RuntimeError(
                "market residual regressor is not fitted"
            )
        x = self._prepare(frame)
        values = self.model.predict(x)
        return pd.Series(
            values,
            index=frame.index,
            dtype=float,
        )


def residual_adjusted_probability(
    frame: pd.DataFrame,
    market_probability: pd.Series,
    residual_prediction: pd.Series,
    *,
    gamma: float,
) -> pd.Series:
    if not market_probability.index.equals(
        residual_prediction.index
    ):
        raise ValueError(
            "market probability and residual prediction indexes differ"
        )
    if gamma < 0.0:
        raise ValueError(
            "gamma must be non-negative"
        )

    market_log = np.log(
        market_probability.astype(float).clip(
            lower=1e-12,
            upper=1.0,
        )
    )
    score = market_log + float(gamma) * (
        residual_prediction.astype(float)
    )
    return _race_softmax(
        pd.Series(
            score,
            index=frame.index,
            dtype=float,
        ),
        frame["race_id"],
    )


def fit_residual_gamma(
    frame: pd.DataFrame,
    market_probability: pd.Series,
    residual_prediction: pd.Series,
    *,
    gamma_grid: tuple[float, ...] = GAMMA_GRID,
) -> tuple[float, list[dict]]:
    if not gamma_grid:
        raise ValueError("gamma grid is empty")

    rows: list[dict] = []
    for gamma in gamma_grid:
        probability = residual_adjusted_probability(
            frame,
            market_probability,
            residual_prediction,
            gamma=float(gamma),
        )
        quality = _quality(
            frame,
            probability,
        )
        rows.append({
            "gamma": float(gamma),
            **quality,
        })

    best = min(
        rows,
        key=lambda row: (
            float(row["winner_log_loss"]),
            float(row["gamma"]),
        ),
    )
    return float(best["gamma"]), rows


def evaluate_rolling_residual_fold(
    frame: pd.DataFrame,
    feature_columns: list[str],
    *,
    train_end: str,
    tuning_start: str,
    tuning_end: str,
    evaluation_start: str,
    evaluation_end: str,
    iterations: int = 350,
    baseline_probability: pd.Series | None = None,
) -> dict:
    train_end_ts = pd.Timestamp(
        train_end
    ).normalize()
    tuning_start_ts = pd.Timestamp(
        tuning_start
    ).normalize()
    tuning_end_ts = pd.Timestamp(
        tuning_end
    ).normalize()
    evaluation_start_ts = pd.Timestamp(
        evaluation_start
    ).normalize()
    evaluation_end_ts = pd.Timestamp(
        evaluation_end
    ).normalize()
    if not (
        train_end_ts
        < tuning_start_ts
        <= tuning_end_ts
        < evaluation_start_ts
        <= evaluation_end_ts
    ):
        raise ValueError(
            "invalid rolling residual fold time split"
        )

    dates = pd.to_datetime(
        frame["race_date"],
        errors="raise",
    )
    train = frame.loc[
        dates.le(train_end_ts)
    ].copy()
    tuning = frame.loc[
        dates.between(
            tuning_start_ts,
            tuning_end_ts,
            inclusive="both",
        )
    ].copy()
    evaluation = frame.loc[
        dates.between(
            evaluation_start_ts,
            evaluation_end_ts,
            inclusive="both",
        )
    ].copy()
    if (
        train.empty
        or tuning.empty
        or evaluation.empty
    ):
        raise ValueError(
            "rolling residual fold contains an empty period"
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
        list(feature_columns),
        iterations=iterations,
    ).fit(
        train,
        train_target,
    )

    tuning_market = normalized_market_probability(
        tuning.rename(
            columns={"win_odds": "decimal_odds"}
        )
    )
    tuning_residual = model.predict(tuning)
    gamma, gamma_sweep = fit_residual_gamma(
        tuning,
        tuning_market,
        tuning_residual,
    )

    evaluation_market = normalized_market_probability(
        evaluation.rename(
            columns={"win_odds": "decimal_odds"}
        )
    )
    evaluation_residual = model.predict(
        evaluation
    )
    evaluation_adjusted = residual_adjusted_probability(
        evaluation,
        evaluation_market,
        evaluation_residual,
        gamma=gamma,
    )
    market_quality = _quality(
        evaluation,
        evaluation_market,
    )
    residual_quality = _quality(
        evaluation,
        evaluation_adjusted,
    )
    paired_bootstrap_vs_static = None
    if baseline_probability is not None:
        baseline = baseline_probability.reindex(
            evaluation.index
        )
        if baseline.isna().any():
            raise ValueError(
                "baseline probability missing rolling evaluation rows"
            )
        paired_bootstrap_vs_static = (
            paired_race_bootstrap_quality_deltas(
                evaluation,
                evaluation_adjusted,
                baseline.astype(float),
            )
        )
    return {
        "train_end": str(train_end_ts.date()),
        "train_rows": int(len(train)),
        "train_races": int(
            train["race_id"].nunique()
        ),
        "tuning_start": str(tuning_start_ts.date()),
        "tuning_end": str(tuning_end_ts.date()),
        "tuning_rows": int(len(tuning)),
        "tuning_races": int(
            tuning["race_id"].nunique()
        ),
        "selected_gamma": _safe_float(
            gamma
        ),
        "gamma_sweep": gamma_sweep,
        "evaluation_start": str(
            evaluation_start_ts.date()
        ),
        "evaluation_end": str(
            evaluation_end_ts.date()
        ),
        "evaluation_rows": int(len(evaluation)),
        "evaluation_races": int(
            evaluation["race_id"].nunique()
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
            float(residual_quality["brier"])
            - float(market_quality["brier"])
        ),
        "paired_bootstrap_vs_static": paired_bootstrap_vs_static,
    }


def evaluate_market_residual_v12_development(
    history: pd.DataFrame,
    champion: LoadedChampion,
    *,
    iterations: int = 350,
    tuning_end: str = "2022-12-31",
    validation_2023_start: str = "2023-01-01",
    validation_2023_end: str = "2023-12-31",
    validation_2024_start: str = "2024-01-01",
    validation_2024_end: str = "2024-12-31",
    min_probability: float = 0.03,
    min_ev_rows: int = 200,
    min_ev_races: int = 100,
) -> dict:
    if iterations < 1:
        raise ValueError(
            "iterations must be positive"
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
            pd.Timestamp(validation_2024_end)
        )
    ].copy()
    if data.empty:
        raise ValueError(
            "market residual v12 development history is empty"
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
    tuning_end_ts = pd.Timestamp(
        tuning_end
    ).normalize()
    v23_start = pd.Timestamp(
        validation_2023_start
    ).normalize()
    v23_end = pd.Timestamp(
        validation_2023_end
    ).normalize()
    v24_start = pd.Timestamp(
        validation_2024_start
    ).normalize()
    v24_end = pd.Timestamp(
        validation_2024_end
    ).normalize()

    if not (
        train_end
        < tuning_end_ts
        < v23_start
        <= v23_end
        < v24_start
        <= v24_end
    ):
        raise ValueError(
            "invalid market residual v12 development time split"
        )

    dates = pd.to_datetime(
        frame["race_date"],
        errors="raise",
    )
    train = frame.loc[
        dates.le(train_end)
    ].copy()
    tuning = frame.loc[
        dates.gt(train_end)
        & dates.le(tuning_end_ts)
    ].copy()
    validation_2023 = frame.loc[
        dates.between(
            v23_start,
            v23_end,
            inclusive="both",
        )
    ].copy()
    validation_2024 = frame.loc[
        dates.between(
            v24_start,
            v24_end,
            inclusive="both",
        )
    ].copy()

    if (
        train.empty
        or tuning.empty
        or validation_2023.empty
        or validation_2024.empty
    ):
        raise ValueError(
            "market residual v12 split contains an empty period"
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
    standardized_model = MarketResidualRegressor(
        list(features),
        iterations=iterations,
    ).fit(
        train,
        standardized_market_residual_target(
            train,
            train_market,
        ),
    )
    direct_value_model = MarketResidualRegressor(
        list(features),
        iterations=iterations,
    ).fit(
        train,
        realized_flat_bet_return(train),
    )

    tuning_market = normalized_market_probability(
        tuning.rename(
            columns={"win_odds": "decimal_odds"}
        )
    )
    tuning_residual = model.predict(
        tuning
    )
    gamma, gamma_sweep = fit_residual_gamma(
        tuning,
        tuning_market,
        tuning_residual,
    )
    tuning_adjusted = residual_adjusted_probability(
        tuning,
        tuning_market,
        tuning_residual,
        gamma=gamma,
    )
    tuning_standardized_prediction = (
        standardized_model.predict(tuning)
    )
    tuning_standardized_residual = (
        restore_standardized_market_residual(
            tuning_market,
            tuning_standardized_prediction,
        )
    )
    (
        standardized_gamma,
        standardized_gamma_sweep,
    ) = fit_residual_gamma(
        tuning,
        tuning_market,
        tuning_standardized_residual,
    )
    tuning_standardized_adjusted = (
        residual_adjusted_probability(
            tuning,
            tuning_market,
            tuning_standardized_residual,
            gamma=standardized_gamma,
        )
    )
    standardized_tuning_quality = _quality(
        tuning,
        tuning_standardized_adjusted,
    )
    fitted_ev_rule, ev_threshold_sweep = (
        fit_residual_ev_rule(
            tuning,
            tuning_adjusted,
            min_probability=min_probability,
            min_rows=min_ev_rows,
            min_races=min_ev_races,
        )
    )
    fitted_market_edge_rule, market_edge_sweep = (
        fit_residual_market_edge_rule(
            tuning,
            tuning_adjusted,
            tuning_market,
            min_probability=min_probability,
            min_rows=min_ev_rows,
            min_races=min_ev_races,
        )
    )
    fitted_broad_market_edge_rule = (
        select_broad_positive_market_edge_rule(
            market_edge_sweep,
            min_rows=min_ev_rows,
            min_races=min_ev_races,
        )
    )
    (
        fitted_market_edge_odds_segment_rule,
        market_edge_odds_segment_sweep,
    ) = fit_residual_market_edge_odds_segment_rule(
        tuning,
        tuning_adjusted,
        tuning_market,
        fitted_broad_market_edge_rule,
        min_probability=min_probability,
        min_rows=min_ev_rows,
        min_races=min_ev_races,
    )
    (
        fitted_longshot_market_edge_rule,
        longshot_market_edge_sweep,
    ) = fit_residual_longshot_market_edge_rule(
        tuning,
        tuning_adjusted,
        tuning_market,
        min_probability=min_probability,
        min_rows=min_ev_rows,
        min_races=min_ev_races,
    )
    (
        fitted_stable_longshot_market_edge_rule,
        stable_longshot_market_edge_sweep,
    ) = fit_residual_stable_longshot_market_edge_rule(
        tuning,
        tuning_adjusted,
        tuning_market,
        min_probability=min_probability,
        min_rows=min_ev_rows,
        min_races=min_ev_races,
        min_fold_rows=max(1, min_ev_rows // 2),
        min_fold_races=max(1, min_ev_races // 2),
    )
    tuning_direct_value_score = (
        direct_value_model.predict(tuning)
    )
    (
        fitted_direct_value_rule,
        direct_value_tuning_evidence,
    ) = fit_direct_value_rule(
        tuning,
        tuning_direct_value_score,
        threshold=0.0,
        min_rows=min_ev_rows,
        min_races=min_ev_races,
    )

    def _evaluate_period(
        period: pd.DataFrame,
    ) -> dict:
        market = normalized_market_probability(
            period.rename(
                columns={
                    "win_odds": "decimal_odds"
                }
            )
        )
        residual = model.predict(period)
        adjusted = residual_adjusted_probability(
            period,
            market,
            residual,
            gamma=gamma,
        )
        standardized_prediction = (
            standardized_model.predict(period)
        )
        standardized_residual = (
            restore_standardized_market_residual(
                market,
                standardized_prediction,
            )
        )
        standardized_adjusted = (
            residual_adjusted_probability(
                period,
                market,
                standardized_residual,
                gamma=standardized_gamma,
            )
        )
        fixed_ev_rule_result = (
            None
            if fitted_ev_rule is None
            else evaluate_fixed_residual_ev_rule(
                period,
                adjusted,
                fitted_ev_rule,
                min_probability=min_probability,
            )
        )
        fixed_market_edge_rule_result = (
            None
            if fitted_market_edge_rule is None
            else evaluate_fixed_residual_market_edge_rule(
                period,
                adjusted,
                market,
                fitted_market_edge_rule,
                min_probability=min_probability,
            )
        )
        fixed_broad_market_edge_rule_result = (
            None
            if fitted_broad_market_edge_rule is None
            else evaluate_fixed_residual_market_edge_rule(
                period,
                adjusted,
                market,
                fitted_broad_market_edge_rule,
                min_probability=min_probability,
            )
        )
        fixed_market_edge_odds_segment_result = (
            None
            if fitted_market_edge_odds_segment_rule is None
            else evaluate_fixed_residual_market_edge_odds_segment_rule(
                period,
                adjusted,
                market,
                fitted_market_edge_odds_segment_rule,
                min_probability=min_probability,
            )
        )
        fixed_longshot_market_edge_result = (
            None
            if fitted_longshot_market_edge_rule is None
            else evaluate_fixed_residual_longshot_market_edge_rule(
                period,
                adjusted,
                market,
                fitted_longshot_market_edge_rule,
                min_probability=min_probability,
            )
        )
        fixed_stable_longshot_market_edge_result = (
            None
            if fitted_stable_longshot_market_edge_rule is None
            else evaluate_fixed_residual_longshot_market_edge_rule(
                period,
                adjusted,
                market,
                fitted_stable_longshot_market_edge_rule,
                min_probability=min_probability,
            )
        )
        direct_value_score = (
            direct_value_model.predict(period)
        )
        fixed_direct_value_rule_result = (
            None
            if fitted_direct_value_rule is None
            else evaluate_fixed_direct_value_rule(
                period,
                direct_value_score,
                fitted_direct_value_rule,
            )
        )
        market_quality = _quality(
            period,
            market,
        )
        adjusted_quality = _quality(
            period,
            adjusted,
        )
        standardized_quality = _quality(
            period,
            standardized_adjusted,
        )
        return {
            "period_start": str(
                period["race_date"].min().date()
            ),
            "period_end": str(
                period["race_date"].max().date()
            ),
            "rows": int(len(period)),
            "races": int(
                period["race_id"].nunique()
            ),
            "market_quality": market_quality,
            "residual_quality": adjusted_quality,
            "standardized_residual_quality": (
                standardized_quality
            ),
            "standardized_winner_log_loss_delta_vs_market": _safe_float(
                float(
                    standardized_quality[
                        "winner_log_loss"
                    ]
                )
                - float(
                    market_quality[
                        "winner_log_loss"
                    ]
                )
            ),
            "standardized_brier_delta_vs_market": _safe_float(
                float(
                    standardized_quality["brier"]
                )
                - float(
                    market_quality["brier"]
                )
            ),
            "standardized_winner_log_loss_delta_vs_baseline_residual": _safe_float(
                float(
                    standardized_quality[
                        "winner_log_loss"
                    ]
                )
                - float(
                    adjusted_quality[
                        "winner_log_loss"
                    ]
                )
            ),
            "standardized_brier_delta_vs_baseline_residual": _safe_float(
                float(
                    standardized_quality["brier"]
                )
                - float(
                    adjusted_quality["brier"]
                )
            ),
            "standardized_beats_baseline_winner_log_loss": bool(
                standardized_quality["winner_log_loss"]
                < adjusted_quality["winner_log_loss"]
            ),
            "standardized_beats_baseline_brier": bool(
                standardized_quality["brier"]
                < adjusted_quality["brier"]
            ),
            "standardized_prediction_mean": _safe_float(
                standardized_prediction.mean()
            ),
            "standardized_prediction_std": _safe_float(
                standardized_prediction.std(ddof=0)
            ),
            "winner_log_loss_delta_vs_market": _safe_float(
                float(
                    adjusted_quality[
                        "winner_log_loss"
                    ]
                )
                - float(
                    market_quality[
                        "winner_log_loss"
                    ]
                )
            ),
            "brier_delta_vs_market": _safe_float(
                float(
                    adjusted_quality["brier"]
                )
                - float(
                    market_quality["brier"]
                )
            ),
            "beats_market_winner_log_loss": bool(
                float(
                    adjusted_quality[
                        "winner_log_loss"
                    ]
                )
                < float(
                    market_quality[
                        "winner_log_loss"
                    ]
                )
            ),
            "beats_market_brier": bool(
                float(
                    adjusted_quality["brier"]
                )
                < float(
                    market_quality["brier"]
                )
            ),
            "residual_prediction_mean": _safe_float(
                residual.mean()
            ),
            "residual_prediction_std": _safe_float(
                residual.std(ddof=0)
            ),
            "fixed_ev_rule_result": fixed_ev_rule_result,
            "fixed_market_edge_rule_result": (
                fixed_market_edge_rule_result
            ),
            "fixed_broad_market_edge_rule_result": (
                fixed_broad_market_edge_rule_result
            ),
            "fixed_market_edge_odds_segment_result": (
                fixed_market_edge_odds_segment_result
            ),
            "fixed_longshot_market_edge_result": (
                fixed_longshot_market_edge_result
            ),
            "fixed_stable_longshot_market_edge_result": (
                fixed_stable_longshot_market_edge_result
            ),
            "fixed_direct_value_rule_result": (
                fixed_direct_value_rule_result
            ),
            "direct_value_score_mean": _safe_float(
                direct_value_score.mean()
            ),
            "direct_value_score_std": _safe_float(
                direct_value_score.std(ddof=0)
            ),
        }

    result_2023 = _evaluate_period(
        validation_2023
    )
    result_2024 = _evaluate_period(
        validation_2024
    )

    def _static_probability_for_rolling_benchmark(
        period: pd.DataFrame,
    ) -> pd.Series:
        market = normalized_market_probability(
            period.rename(
                columns={"win_odds": "decimal_odds"}
            )
        )
        residual = model.predict(period)
        return residual_adjusted_probability(
            period,
            market,
            residual,
            gamma=gamma,
        )

    static_2023_probability = (
        _static_probability_for_rolling_benchmark(
            validation_2023
        )
    )
    static_2024_probability = (
        _static_probability_for_rolling_benchmark(
            validation_2024
        )
    )

    rolling_2023 = evaluate_rolling_residual_fold(
        frame,
        list(features),
        train_end="2021-12-31",
        tuning_start="2022-01-01",
        tuning_end="2022-12-31",
        evaluation_start="2023-01-01",
        evaluation_end="2023-12-31",
        iterations=iterations,
        baseline_probability=static_2023_probability,
    )
    rolling_2024 = evaluate_rolling_residual_fold(
        frame,
        list(features),
        train_end="2022-12-31",
        tuning_start="2023-01-01",
        tuning_end="2023-12-31",
        evaluation_start="2024-01-01",
        evaluation_end="2024-12-31",
        iterations=iterations,
        baseline_probability=static_2024_probability,
    )

    def _annotate_rolling_vs_static(
        rolling: dict,
        static_result: dict,
    ) -> None:
        rolling_quality = rolling[
            "residual_quality"
        ]
        static_quality = static_result[
            "residual_quality"
        ]
        rolling[
            "winner_log_loss_delta_vs_static_residual"
        ] = _safe_float(
            float(
                rolling_quality["winner_log_loss"]
            )
            - float(
                static_quality["winner_log_loss"]
            )
        )
        rolling[
            "brier_delta_vs_static_residual"
        ] = _safe_float(
            float(rolling_quality["brier"])
            - float(static_quality["brier"])
        )
        rolling[
            "beats_static_residual_winner_log_loss"
        ] = bool(
            rolling_quality["winner_log_loss"]
            < static_quality["winner_log_loss"]
        )
        rolling[
            "beats_static_residual_brier"
        ] = bool(
            rolling_quality["brier"]
            < static_quality["brier"]
        )

    _annotate_rolling_vs_static(
        rolling_2023,
        result_2023,
    )
    _annotate_rolling_vs_static(
        rolling_2024,
        result_2024,
    )

    rolling_refit_gate = bool(
        float(rolling_2023["selected_gamma"]) > 0.0
        and float(rolling_2024["selected_gamma"]) > 0.0
        and rolling_2023[
            "beats_static_residual_winner_log_loss"
        ]
        and rolling_2023[
            "beats_static_residual_brier"
        ]
        and rolling_2024[
            "beats_static_residual_winner_log_loss"
        ]
        and rolling_2024[
            "beats_static_residual_brier"
        ]
    )

    def _rolling_safety_fold_passed(
        rolling: dict,
    ) -> bool:
        evidence = rolling[
            "paired_bootstrap_vs_static"
        ]
        return bool(
            evidence is not None
            and float(
                evidence[
                    "winner_log_loss_improvement_support"
                ]
            )
            >= ROLLING_REFIT_MIN_IMPROVEMENT_SUPPORT
            and float(
                evidence["brier_improvement_support"]
            )
            >= ROLLING_REFIT_MIN_IMPROVEMENT_SUPPORT
        )

    rolling_refit_safety_gate = bool(
        rolling_refit_gate
        and _rolling_safety_fold_passed(rolling_2023)
        and _rolling_safety_fold_passed(rolling_2024)
    )

    gate = bool(
        gamma > 0.0
        and result_2023[
            "beats_market_winner_log_loss"
        ]
        and result_2023[
            "beats_market_brier"
        ]
        and result_2024[
            "beats_market_winner_log_loss"
        ]
        and result_2024[
            "beats_market_brier"
        ]
    )

    def _ev_period_passed(result: dict) -> bool:
        ev_result = result["fixed_ev_rule_result"]
        return bool(
            ev_result is not None
            and ev_result["flat_bet_roi_final_odds"] is not None
            and float(
                ev_result["flat_bet_roi_final_odds"]
            ) > 0.0
            and int(ev_result["rows"]) >= min_ev_rows
            and int(ev_result["races"]) >= min_ev_races
        )

    ev_gate = bool(
        fitted_ev_rule is not None
        and fitted_ev_rule["flat_bet_roi_final_odds"] is not None
        and float(
            fitted_ev_rule["flat_bet_roi_final_odds"]
        ) > 0.0
        and _ev_period_passed(result_2023)
        and _ev_period_passed(result_2024)
    )

    def _market_edge_period_passed(
        result: dict,
    ) -> bool:
        edge_result = result[
            "fixed_market_edge_rule_result"
        ]
        return bool(
            edge_result is not None
            and edge_result["flat_bet_roi_final_odds"] is not None
            and float(
                edge_result["flat_bet_roi_final_odds"]
            ) > 0.0
            and int(edge_result["rows"]) >= min_ev_rows
            and int(edge_result["races"]) >= min_ev_races
        )

    market_edge_gate = bool(
        fitted_market_edge_rule is not None
        and fitted_market_edge_rule[
            "flat_bet_roi_final_odds"
        ] is not None
        and float(
            fitted_market_edge_rule[
                "flat_bet_roi_final_odds"
            ]
        ) > 0.0
        and _market_edge_period_passed(
            result_2023
        )
        and _market_edge_period_passed(
            result_2024
        )
    )

    def _broad_market_edge_period_passed(
        result: dict,
    ) -> bool:
        edge_result = result[
            "fixed_broad_market_edge_rule_result"
        ]
        return bool(
            edge_result is not None
            and edge_result["flat_bet_roi_final_odds"] is not None
            and float(
                edge_result["flat_bet_roi_final_odds"]
            ) > 0.0
            and int(edge_result["rows"]) >= min_ev_rows
            and int(edge_result["races"]) >= min_ev_races
        )

    broad_market_edge_gate = bool(
        fitted_broad_market_edge_rule is not None
        and _broad_market_edge_period_passed(
            result_2023
        )
        and _broad_market_edge_period_passed(
            result_2024
        )
    )

    def _odds_segment_period_passed(
        result: dict,
    ) -> bool:
        segment_result = result[
            "fixed_market_edge_odds_segment_result"
        ]
        return bool(
            segment_result is not None
            and segment_result[
                "flat_bet_roi_final_odds"
            ] is not None
            and float(
                segment_result[
                    "flat_bet_roi_final_odds"
                ]
            ) > 0.0
            and int(segment_result["rows"]) >= min_ev_rows
            and int(segment_result["races"]) >= min_ev_races
        )

    market_edge_odds_segment_gate = bool(
        fitted_market_edge_odds_segment_rule is not None
        and _odds_segment_period_passed(
            result_2023
        )
        and _odds_segment_period_passed(
            result_2024
        )
    )

    def _longshot_period_passed(
        result: dict,
    ) -> bool:
        longshot_result = result[
            "fixed_longshot_market_edge_result"
        ]
        return bool(
            longshot_result is not None
            and longshot_result[
                "flat_bet_roi_final_odds"
            ] is not None
            and float(
                longshot_result[
                    "flat_bet_roi_final_odds"
                ]
            ) > 0.0
            and int(longshot_result["rows"]) >= min_ev_rows
            and int(longshot_result["races"]) >= min_ev_races
        )

    longshot_market_edge_gate = bool(
        fitted_longshot_market_edge_rule is not None
        and _longshot_period_passed(
            result_2023
        )
        and _longshot_period_passed(
            result_2024
        )
    )

    def _stable_longshot_period_passed(
        result: dict,
    ) -> bool:
        stable_result = result[
            "fixed_stable_longshot_market_edge_result"
        ]
        return bool(
            stable_result is not None
            and stable_result[
                "flat_bet_roi_final_odds"
            ] is not None
            and float(
                stable_result[
                    "flat_bet_roi_final_odds"
                ]
            ) > 0.0
            and int(stable_result["rows"]) >= min_ev_rows
            and int(stable_result["races"]) >= min_ev_races
        )

    stable_longshot_market_edge_gate = bool(
        fitted_stable_longshot_market_edge_rule is not None
        and _stable_longshot_period_passed(
            result_2023
        )
        and _stable_longshot_period_passed(
            result_2024
        )
    )

    def _direct_value_period_passed(
        result: dict,
    ) -> bool:
        value_result = result[
            "fixed_direct_value_rule_result"
        ]
        return bool(
            value_result is not None
            and value_result[
                "flat_bet_roi_final_odds"
            ] is not None
            and float(
                value_result[
                    "flat_bet_roi_final_odds"
                ]
            ) > 0.0
            and int(value_result["rows"]) >= min_ev_rows
            and int(value_result["races"]) >= min_ev_races
        )

    direct_value_gate = bool(
        fitted_direct_value_rule is not None
        and _direct_value_period_passed(
            result_2023
        )
        and _direct_value_period_passed(
            result_2024
        )
    )

    standardized_residual_gate = bool(
        standardized_gamma > 0.0
        and result_2023[
            "standardized_beats_baseline_winner_log_loss"
        ]
        and result_2023[
            "standardized_beats_baseline_brier"
        ]
        and result_2024[
            "standardized_beats_baseline_winner_log_loss"
        ]
        and result_2024[
            "standardized_beats_baseline_brier"
        ]
    )

    return {
        "status": (
            "research_only_market_residual_v12_development"
        ),
        "warning": (
            "Historical final win odds are used only as a research market "
            "proxy. The residual model learns winner-minus-market probability "
            "on the original training period. Gamma and the research-only EV "
            "selection rule are selected only through 2022 and then frozen for "
            "2023 and 2024 validation. Rows from 2025 onward are excluded "
            "before feature building. The EV rule must not change Forward Paper "
            "thresholds; equivalent timestamped pre-race 0B31 inputs are "
            "required before any Paper decision experiment."
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
        "gamma_tuning": {
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
            "selected_gamma": _safe_float(
                gamma
            ),
            "sweep": gamma_sweep,
        },
        "ev_rule_tuning_2022": {
            "period_start": str(
                tuning["race_date"].min().date()
            ),
            "period_end": str(
                tuning["race_date"].max().date()
            ),
            "fitted_rule": fitted_ev_rule,
            "threshold_sweep": ev_threshold_sweep,
        },
        "market_edge_rule_tuning_2022": {
            "period_start": str(
                tuning["race_date"].min().date()
            ),
            "period_end": str(
                tuning["race_date"].max().date()
            ),
            "fitted_rule": fitted_market_edge_rule,
            "threshold_sweep": market_edge_sweep,
        },
        "broad_market_edge_rule_tuning_2022": {
            "period_start": str(
                tuning["race_date"].min().date()
            ),
            "period_end": str(
                tuning["race_date"].max().date()
            ),
            "selection": (
                "broadest positive-ROI rule meeting "
                "minimum rows/races"
            ),
            "fitted_rule": fitted_broad_market_edge_rule,
        },
        "market_edge_odds_segment_tuning_2022": {
            "period_start": str(
                tuning["race_date"].min().date()
            ),
            "period_end": str(
                tuning["race_date"].max().date()
            ),
            "selection": (
                "broadest positive-ROI final-odds segment "
                "within the frozen broad market-edge rule"
            ),
            "fitted_rule": fitted_market_edge_odds_segment_rule,
            "segment_sweep": market_edge_odds_segment_sweep,
        },
        "longshot_market_edge_tuning_2022": {
            "period_start": str(
                tuning["race_date"].min().date()
            ),
            "period_end": str(
                tuning["race_date"].max().date()
            ),
            "selection": (
                "odds >= 6 fixed; broadest positive-ROI "
                "edge threshold with all-candidates policy"
            ),
            "odds_min": LONGSHOT_ODDS_MIN,
            "fitted_rule": fitted_longshot_market_edge_rule,
            "threshold_sweep": longshot_market_edge_sweep,
        },
        "stable_longshot_market_edge_tuning_2022": {
            "period_start": str(
                tuning["race_date"].min().date()
            ),
            "period_end": str(
                tuning["race_date"].max().date()
            ),
            "stability_split_date": LONGSHOT_STABILITY_SPLIT_DATE,
            "selection": (
                "odds >= 6 fixed; edge rule must be positive "
                "in both pre-registered tuning subperiods"
            ),
            "fold_min_rows": max(1, min_ev_rows // 2),
            "fold_min_races": max(1, min_ev_races // 2),
            "fitted_rule": fitted_stable_longshot_market_edge_rule,
            "threshold_sweep": stable_longshot_market_edge_sweep,
        },
        "direct_value_tuning_2022": {
            "period_start": str(
                tuning["race_date"].min().date()
            ),
            "period_end": str(
                tuning["race_date"].max().date()
            ),
            "target": "winner_times_final_odds_minus_one",
            "selection": "predicted_return_gt_zero",
            "fitted_rule": fitted_direct_value_rule,
            "evidence": direct_value_tuning_evidence,
        },
        "standardized_residual_tuning_2022": {
            "period_start": str(
                tuning["race_date"].min().date()
            ),
            "period_end": str(
                tuning["race_date"].max().date()
            ),
            "target": (
                "(winner - market_probability) / "
                "sqrt(max(p*(1-p), variance_floor))"
            ),
            "variance_floor": float(
                STANDARDIZED_RESIDUAL_VARIANCE_FLOOR
            ),
            "selected_gamma": _safe_float(
                standardized_gamma
            ),
            "gamma_sweep": standardized_gamma_sweep,
            "quality": standardized_tuning_quality,
        },
        "research_protocol": {
            "development_periods": [
                "through_2022_tuning",
                "2023_development_reused",
                "2024_development_reused",
            ],
            "final_holdout": "2025-2026 untouched",
            "note": (
                "2023 and 2024 have been inspected in prior phases "
                "and are development evidence, not independent holdout."
            ),
        },
        "rolling_refit_phase9": {
            "selection": (
                "annual expanding-window raw residual refit; "
                "gamma tuned only on the immediately prior year"
            ),
            "fold_2023": rolling_2023,
            "fold_2024": rolling_2024,
            "development_gate_passed": rolling_refit_gate,
        },
        "rolling_refit_safety_phase10": {
            "method": (
                "paired race bootstrap of frozen phase-9 rolling "
                "probabilities versus static residual v12"
            ),
            "samples": ROLLING_REFIT_BOOTSTRAP_SAMPLES,
            "seed": ROLLING_REFIT_BOOTSTRAP_SEED,
            "minimum_improvement_support": (
                ROLLING_REFIT_MIN_IMPROVEMENT_SUPPORT
            ),
            "fold_2023": rolling_2023[
                "paired_bootstrap_vs_static"
            ],
            "fold_2024": rolling_2024[
                "paired_bootstrap_vs_static"
            ],
            "development_safety_gate_passed": (
                rolling_refit_safety_gate
            ),
        },
        "validation_2023": result_2023,
        "validation_2024": result_2024,
        "development_gate_passed": gate,
        "ev_development_gate_passed": ev_gate,
        "market_edge_development_gate_passed": (
            market_edge_gate
        ),
        "broad_market_edge_development_gate_passed": (
            broad_market_edge_gate
        ),
        "market_edge_odds_segment_development_gate_passed": (
            market_edge_odds_segment_gate
        ),
        "longshot_market_edge_development_gate_passed": (
            longshot_market_edge_gate
        ),
        "stable_longshot_market_edge_development_gate_passed": (
            stable_longshot_market_edge_gate
        ),
        "direct_value_development_gate_passed": (
            direct_value_gate
        ),
        "standardized_residual_development_gate_passed": (
            standardized_residual_gate
        ),
        "rolling_refit_development_gate_passed": (
            rolling_refit_gate
        ),
        "rolling_refit_safety_gate_passed": (
            rolling_refit_safety_gate
        ),
        "ev_constraints": {
            "min_probability": float(min_probability),
            "min_rows": int(min_ev_rows),
            "min_races": int(min_ev_races),
        },
    }
