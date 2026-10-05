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
        market_quality = _quality(
            period,
            market,
        )
        adjusted_quality = _quality(
            period,
            adjusted,
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
        }

    result_2023 = _evaluate_period(
        validation_2023
    )
    result_2024 = _evaluate_period(
        validation_2024
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
        "ev_constraints": {
            "min_probability": float(min_probability),
            "min_rows": int(min_ev_rows),
            "min_races": int(min_ev_races),
        },
    }
