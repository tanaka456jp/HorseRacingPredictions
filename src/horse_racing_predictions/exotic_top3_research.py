from __future__ import annotations

import math
from itertools import permutations

import numpy as np
import pandas as pd

from .evaluation import brier_score, binary_log_loss
from .feature_window import align_history_to_training_start
from .features import build_pre_race_features
from .market_aware_ranker_v11 import (
    MARKET_CONTEXT_FEATURES,
    add_market_context_features,
)


TOP3_LONGSHOT_ODDS_MIN = 6.0
TOP3_BOOTSTRAP_SAMPLES = 1000
TOP3_BOOTSTRAP_SEED = 20261006
TOP3_MIN_IMPROVEMENT_SUPPORT = 0.80

TOP3_INTERACTION_SOURCE_FEATURES = (
    "horse_recent_top3_rate_5",
    "horse_recent_finish_percentile_mean_5",
    "horse_recent_early_ratio_mean_5",
    "horse_recent_late_ratio_mean_5",
    "jockey_past_win_rate",
    "jockey_course_past_win_rate",
    "horse_jockey_past_win_rate",
    "trainer_past_win_rate",
)


def _safe_float(value) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None


def top3_outcomes(frame: pd.DataFrame) -> pd.Series:
    finish = pd.to_numeric(
        frame["finish_position"],
        errors="coerce",
    )
    return finish.le(3).astype(int)


def add_top3_race_interaction_features(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    """Add past-only runner-vs-field context without using same-race outcomes."""
    if "race_id" not in frame.columns:
        raise ValueError("race interaction features require race_id")

    out = frame.copy()
    generated: list[str] = []

    for source in TOP3_INTERACTION_SOURCE_FEATURES:
        if source not in out.columns:
            continue

        values = pd.to_numeric(
            out[source],
            errors="coerce",
        )
        race = values.groupby(out["race_id"], sort=False)
        mean_name = f"{source}_race_mean"
        delta_name = f"{source}_vs_race_mean"
        std_name = f"{source}_race_std"
        rank_name = f"{source}_race_rank_pct"

        race_mean = race.transform("mean")
        out[mean_name] = race_mean
        out[delta_name] = values - race_mean
        out[std_name] = race.transform("std").fillna(0.0)
        out[rank_name] = race.rank(
            method="average",
            ascending=False,
            pct=True,
        )

        generated.extend(
            [mean_name, delta_name, std_name, rank_name]
        )

    if "market_implied_probability" in out.columns:
        market = pd.to_numeric(
            out["market_implied_probability"],
            errors="coerce",
        ).clip(lower=1e-12, upper=1.0)
        grouped = market.groupby(out["race_id"], sort=False)

        out["market_favorite_probability"] = grouped.transform("max")
        out["market_probability_std"] = grouped.transform("std").fillna(0.0)

        entropy_by_race = (
            -(market * np.log(market))
            .groupby(out["race_id"], sort=False)
            .transform("sum")
        )
        out["market_race_entropy"] = entropy_by_race

        rank = market.groupby(
            out["race_id"],
            sort=False,
        ).rank(
            method="first",
            ascending=False,
        )
        top3_component = market.where(rank.le(3), 0.0)
        out["market_top3_probability_share"] = (
            top3_component.groupby(
                out["race_id"],
                sort=False,
            ).transform("sum")
        )

        generated.extend([
            "market_favorite_probability",
            "market_probability_std",
            "market_race_entropy",
            "market_top3_probability_share",
        ])

    return out, tuple(generated)


class Top3ProbabilityModel:
    def __init__(
        self,
        feature_columns: list[str],
        *,
        iterations: int = 300,
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

    def _prepare(self, frame: pd.DataFrame) -> pd.DataFrame:
        out = frame[self.feature_columns].copy()
        for column in self.feature_columns:
            if pd.api.types.is_numeric_dtype(out[column]):
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
    ) -> "Top3ProbabilityModel":
        try:
            from catboost import CatBoostClassifier
        except ImportError as exc:
            raise RuntimeError(
                "Top-3 research requires the research extra: "
                "pip install -e '.[research]'"
            ) from exc

        if len(frame) != len(target):
            raise ValueError(
                "top3 target length must match training frame"
            )

        x = self._prepare(frame)
        self.categorical_columns = [
            column
            for column in self.feature_columns
            if not pd.api.types.is_numeric_dtype(x[column])
        ]
        y = pd.to_numeric(
            target,
            errors="raise",
        ).astype(int)

        self.model = CatBoostClassifier(
            iterations=self.iterations,
            depth=self.depth,
            learning_rate=self.learning_rate,
            loss_function="Logloss",
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

    def predict_probability(
        self,
        frame: pd.DataFrame,
    ) -> pd.Series:
        if self.model is None:
            raise RuntimeError("top3 probability model is not fitted")
        x = self._prepare(frame)
        values = self.model.predict_proba(x)[:, 1]
        return pd.Series(
            values,
            index=frame.index,
            dtype=float,
        ).clip(lower=1e-12, upper=1.0 - 1e-12)


def _top3_quality(
    frame: pd.DataFrame,
    probability: pd.Series,
) -> dict:
    target = top3_outcomes(frame)
    return {
        "rows": int(len(frame)),
        "races": int(frame["race_id"].nunique()),
        "top3_rate": _safe_float(target.mean()),
        "binary_log_loss": _safe_float(
            binary_log_loss(probability, target)
        ),
        "brier": _safe_float(
            brier_score(probability, target)
        ),
        "average_probability": _safe_float(
            probability.mean()
        ),
    }



def paired_race_bootstrap_binary_quality(
    frame: pd.DataFrame,
    challenger_probability: pd.Series,
    baseline_probability: pd.Series,
    *,
    samples: int = TOP3_BOOTSTRAP_SAMPLES,
    seed: int = TOP3_BOOTSTRAP_SEED,
) -> dict:
    """Race-level bootstrap of challenger-minus-baseline binary metrics."""
    if samples < 1:
        raise ValueError("bootstrap samples must be positive")
    if frame.empty:
        raise ValueError("bootstrap frame is empty")
    if not challenger_probability.index.equals(frame.index):
        raise ValueError("challenger probability index differs from frame")
    if not baseline_probability.index.equals(frame.index):
        raise ValueError("baseline probability index differs from frame")

    target = top3_outcomes(frame).astype(float)
    challenger = challenger_probability.astype(float).clip(
        lower=1e-12,
        upper=1.0 - 1e-12,
    )
    baseline = baseline_probability.astype(float).clip(
        lower=1e-12,
        upper=1.0 - 1e-12,
    )

    challenger_logloss = -(
        target * np.log(challenger)
        + (1.0 - target) * np.log(1.0 - challenger)
    )
    baseline_logloss = -(
        target * np.log(baseline)
        + (1.0 - target) * np.log(1.0 - baseline)
    )
    logloss_delta = challenger_logloss - baseline_logloss
    brier_delta = (
        np.square(challenger - target)
        - np.square(baseline - target)
    )

    evidence = pd.DataFrame({
        "race_id": frame["race_id"].astype(str),
        "logloss_delta": logloss_delta,
        "brier_delta": brier_delta,
    })
    grouped = (
        evidence.groupby("race_id", sort=False)
        .agg(
            logloss_sum=("logloss_delta", "sum"),
            brier_sum=("brier_delta", "sum"),
            rows=("race_id", "size"),
        )
        .reset_index(drop=True)
    )
    race_count = int(len(grouped))
    if race_count < 1:
        raise ValueError("bootstrap evidence contains no races")

    rng = np.random.default_rng(seed)
    sampled_logloss = np.empty(int(samples), dtype=float)
    sampled_brier = np.empty(int(samples), dtype=float)

    logloss_sum = grouped["logloss_sum"].to_numpy(dtype=float)
    brier_sum = grouped["brier_sum"].to_numpy(dtype=float)
    row_count = grouped["rows"].to_numpy(dtype=float)

    for idx in range(int(samples)):
        draw = rng.integers(0, race_count, size=race_count)
        denominator = float(row_count[draw].sum())
        sampled_logloss[idx] = float(
            logloss_sum[draw].sum() / denominator
        )
        sampled_brier[idx] = float(
            brier_sum[draw].sum() / denominator
        )

    return {
        "samples": int(samples),
        "seed": int(seed),
        "races": race_count,
        "rows": int(len(frame)),
        "winner_metric": "top3_binary",
        "binary_log_loss_improvement_support": _safe_float(
            np.mean(sampled_logloss < 0.0)
        ),
        "brier_improvement_support": _safe_float(
            np.mean(sampled_brier < 0.0)
        ),
        "binary_log_loss_delta_ci90": [
            _safe_float(np.quantile(sampled_logloss, 0.05)),
            _safe_float(np.quantile(sampled_logloss, 0.95)),
        ],
        "brier_delta_ci90": [
            _safe_float(np.quantile(sampled_brier, 0.05)),
            _safe_float(np.quantile(sampled_brier, 0.95)),
        ],
    }


def _plackett_luce_top3_probability(
    strengths: np.ndarray,
    order: tuple[int, int, int],
) -> float:
    """Probability of one ordered top-three under fixed PL strengths."""
    remaining = float(np.sum(strengths))
    probability = 1.0
    for position in order:
        strength = float(strengths[position])
        if remaining <= 0.0 or strength <= 0.0:
            return 0.0
        probability *= strength / remaining
        remaining -= strength
    return float(probability)


def exotic_combination_race_evidence(
    frame: pd.DataFrame,
    probability: pd.Series,
) -> pd.DataFrame:
    """Convert Top-3 marginals to fixed joint order/set probabilities.

    Phase 3 uses the pre-registered transform strength=q/(1-q), then a
    Plackett-Luce without-replacement ranking distribution. No fitting or
    tuning occurs in this conversion.
    """
    if frame.empty:
        raise ValueError("combination evidence frame is empty")
    if not probability.index.equals(frame.index):
        raise ValueError("combination probability index differs from frame")

    q = probability.astype(float).clip(
        lower=1e-9,
        upper=1.0 - 1e-9,
    )
    rows: list[dict] = []

    for race_id, race in frame.groupby("race_id", sort=False):
        finish = pd.to_numeric(
            race["finish_position"],
            errors="coerce",
        )
        actual_indices: list[object] = []
        valid = True
        for place in (1, 2, 3):
            matches = race.index[finish.eq(place)].tolist()
            if len(matches) != 1:
                valid = False
                break
            actual_indices.append(matches[0])
        if not valid or len(race) < 3:
            continue

        local_indices = list(race.index)
        local_position = {
            index: idx
            for idx, index in enumerate(local_indices)
        }
        ordered = tuple(
            local_position[index]
            for index in actual_indices
        )

        race_q = q.loc[local_indices].to_numpy(dtype=float)
        strengths = race_q / (1.0 - race_q)

        trifecta_probability = _plackett_luce_top3_probability(
            strengths,
            ordered,
        )
        trio_probability = float(sum(
            _plackett_luce_top3_probability(
                strengths,
                tuple(order),
            )
            for order in permutations(ordered, 3)
        ))

        top3_odds = pd.to_numeric(
            race.loc[actual_indices, "win_odds"],
            errors="coerce",
        )
        contains_longshot = bool(
            top3_odds.ge(TOP3_LONGSHOT_ODDS_MIN).any()
        )

        rows.append({
            "race_id": str(race_id),
            "trifecta_probability": max(
                float(trifecta_probability),
                1e-300,
            ),
            "trio_probability": max(
                min(float(trio_probability), 1.0),
                1e-300,
            ),
            "contains_longshot": contains_longshot,
        })

    evidence = pd.DataFrame(rows)
    if evidence.empty:
        raise ValueError(
            "no races with unique first/second/third finishers "
            "for combination evidence"
        )
    evidence["trifecta_nll"] = -np.log(
        evidence["trifecta_probability"]
    )
    evidence["trio_nll"] = -np.log(
        evidence["trio_probability"]
    )
    return evidence


def _joint_quality(evidence: pd.DataFrame) -> dict:
    if evidence.empty:
        raise ValueError("joint quality evidence is empty")
    return {
        "races": int(len(evidence)),
        "mean_trifecta_nll": _safe_float(
            evidence["trifecta_nll"].mean()
        ),
        "mean_trio_nll": _safe_float(
            evidence["trio_nll"].mean()
        ),
        "geometric_mean_realized_trifecta_probability": _safe_float(
            np.exp(-evidence["trifecta_nll"].mean())
        ),
        "geometric_mean_realized_trio_probability": _safe_float(
            np.exp(-evidence["trio_nll"].mean())
        ),
    }


def paired_race_bootstrap_joint_nll(
    challenger_evidence: pd.DataFrame,
    baseline_evidence: pd.DataFrame,
    *,
    samples: int = TOP3_BOOTSTRAP_SAMPLES,
    seed: int = TOP3_BOOTSTRAP_SEED,
) -> dict:
    if samples < 1:
        raise ValueError("bootstrap samples must be positive")

    merged = challenger_evidence[
        ["race_id", "trifecta_nll", "trio_nll"]
    ].merge(
        baseline_evidence[
            ["race_id", "trifecta_nll", "trio_nll"]
        ],
        on="race_id",
        how="inner",
        suffixes=("_challenger", "_baseline"),
        validate="one_to_one",
    )
    if merged.empty:
        raise ValueError("joint bootstrap evidence has no paired races")

    trifecta_delta = (
        merged["trifecta_nll_challenger"]
        - merged["trifecta_nll_baseline"]
    ).to_numpy(dtype=float)
    trio_delta = (
        merged["trio_nll_challenger"]
        - merged["trio_nll_baseline"]
    ).to_numpy(dtype=float)

    race_count = int(len(merged))
    rng = np.random.default_rng(seed)
    sampled_trifecta = np.empty(int(samples), dtype=float)
    sampled_trio = np.empty(int(samples), dtype=float)

    for idx in range(int(samples)):
        draw = rng.integers(0, race_count, size=race_count)
        sampled_trifecta[idx] = float(
            trifecta_delta[draw].mean()
        )
        sampled_trio[idx] = float(
            trio_delta[draw].mean()
        )

    return {
        "samples": int(samples),
        "seed": int(seed),
        "races": race_count,
        "trifecta_nll_improvement_support": _safe_float(
            np.mean(sampled_trifecta < 0.0)
        ),
        "trio_nll_improvement_support": _safe_float(
            np.mean(sampled_trio < 0.0)
        ),
        "trifecta_nll_delta_ci90": [
            _safe_float(np.quantile(sampled_trifecta, 0.05)),
            _safe_float(np.quantile(sampled_trifecta, 0.95)),
        ],
        "trio_nll_delta_ci90": [
            _safe_float(np.quantile(sampled_trio, 0.05)),
            _safe_float(np.quantile(sampled_trio, 0.95)),
        ],
    }


def evaluate_exotic_combination_quality(
    frame: pd.DataFrame,
    baseline_probability: pd.Series,
    challenger_probability: pd.Series,
) -> dict:
    baseline = exotic_combination_race_evidence(
        frame,
        baseline_probability,
    )
    challenger = exotic_combination_race_evidence(
        frame,
        challenger_probability,
    )

    def _segment(
        baseline_segment: pd.DataFrame,
        challenger_segment: pd.DataFrame,
    ) -> dict:
        baseline_quality = _joint_quality(baseline_segment)
        challenger_quality = _joint_quality(challenger_segment)
        bootstrap = paired_race_bootstrap_joint_nll(
            challenger_segment,
            baseline_segment,
        )
        return {
            "baseline": baseline_quality,
            "challenger": challenger_quality,
            "trifecta_nll_delta": _safe_float(
                float(challenger_quality["mean_trifecta_nll"])
                - float(baseline_quality["mean_trifecta_nll"])
            ),
            "trio_nll_delta": _safe_float(
                float(challenger_quality["mean_trio_nll"])
                - float(baseline_quality["mean_trio_nll"])
            ),
            "paired_bootstrap_vs_baseline": bootstrap,
        }

    overall = _segment(baseline, challenger)

    longshot_ids = set(
        challenger.loc[
            challenger["contains_longshot"],
            "race_id",
        ].astype(str)
    )
    baseline_longshot = baseline.loc[
        baseline["race_id"].astype(str).isin(longshot_ids)
    ].copy()
    challenger_longshot = challenger.loc[
        challenger["race_id"].astype(str).isin(longshot_ids)
    ].copy()
    if baseline_longshot.empty or challenger_longshot.empty:
        raise ValueError(
            "no realized top-three combinations contain a longshot proxy"
        )

    return {
        "method": (
            "fixed Plackett-Luce transform from Top-3 marginal "
            "probabilities using strength=q/(1-q)"
        ),
        "overall": overall,
        "longshot_containing": {
            "definition": (
                "realized top three contains at least one runner with "
                "historical final win odds >= 6.0; development proxy only"
            ),
            **_segment(
                baseline_longshot,
                challenger_longshot,
            ),
        },
    }


def _role_aware_top3_probability(
    first_probability: np.ndarray,
    top3_strengths: np.ndarray,
    order: tuple[int, int, int],
) -> float:
    """Use win-market probability for first and Top-3 strength thereafter."""
    first, second, third = order
    first_p = float(first_probability[first])
    remaining_after_first = float(
        np.sum(top3_strengths) - top3_strengths[first]
    )
    if first_p <= 0.0 or remaining_after_first <= 0.0:
        return 0.0

    second_strength = float(top3_strengths[second])
    second_p = second_strength / remaining_after_first

    remaining_after_second = float(
        remaining_after_first - second_strength
    )
    if second_p <= 0.0 or remaining_after_second <= 0.0:
        return 0.0

    third_strength = float(top3_strengths[third])
    third_p = third_strength / remaining_after_second
    if third_p <= 0.0:
        return 0.0
    return float(first_p * second_p * third_p)


def role_aware_combination_race_evidence(
    frame: pd.DataFrame,
    top3_probability: pd.Series,
) -> pd.DataFrame:
    """Phase 4 joint distribution: win market first, Top-3 model second/third."""
    if frame.empty:
        raise ValueError("role-aware combination frame is empty")
    if not top3_probability.index.equals(frame.index):
        raise ValueError("role-aware probability index differs from frame")
    if "market_implied_probability" not in frame.columns:
        raise ValueError(
            "role-aware combinations require market_implied_probability"
        )

    q = top3_probability.astype(float).clip(
        lower=1e-9,
        upper=1.0 - 1e-9,
    )
    rows: list[dict] = []

    for race_id, race in frame.groupby("race_id", sort=False):
        finish = pd.to_numeric(
            race["finish_position"],
            errors="coerce",
        )
        actual_indices: list[object] = []
        valid = True
        for place in (1, 2, 3):
            matches = race.index[finish.eq(place)].tolist()
            if len(matches) != 1:
                valid = False
                break
            actual_indices.append(matches[0])
        if not valid or len(race) < 3:
            continue

        local_indices = list(race.index)
        local_position = {
            index: idx
            for idx, index in enumerate(local_indices)
        }
        ordered = tuple(
            local_position[index]
            for index in actual_indices
        )

        race_q = q.loc[local_indices].to_numpy(dtype=float)
        strengths = race_q / (1.0 - race_q)
        first_probability = pd.to_numeric(
            race.loc[
                local_indices,
                "market_implied_probability",
            ],
            errors="raise",
        ).to_numpy(dtype=float)
        first_probability = np.clip(
            first_probability,
            1e-12,
            None,
        )
        first_probability = (
            first_probability / first_probability.sum()
        )

        trifecta_probability = _role_aware_top3_probability(
            first_probability,
            strengths,
            ordered,
        )
        trio_probability = float(sum(
            _role_aware_top3_probability(
                first_probability,
                strengths,
                tuple(order),
            )
            for order in permutations(ordered, 3)
        ))

        top3_odds = pd.to_numeric(
            race.loc[actual_indices, "win_odds"],
            errors="coerce",
        )
        rows.append({
            "race_id": str(race_id),
            "trifecta_probability": max(
                float(trifecta_probability),
                1e-300,
            ),
            "trio_probability": max(
                min(float(trio_probability), 1.0),
                1e-300,
            ),
            "contains_longshot": bool(
                top3_odds.ge(TOP3_LONGSHOT_ODDS_MIN).any()
            ),
        })

    evidence = pd.DataFrame(rows)
    if evidence.empty:
        raise ValueError(
            "no races with unique first/second/third finishers "
            "for role-aware combination evidence"
        )
    evidence["trifecta_nll"] = -np.log(
        evidence["trifecta_probability"]
    )
    evidence["trio_nll"] = -np.log(
        evidence["trio_probability"]
    )
    return evidence


def evaluate_role_aware_combination_quality(
    frame: pd.DataFrame,
    baseline_probability: pd.Series,
    challenger_probability: pd.Series,
) -> dict:
    baseline = role_aware_combination_race_evidence(
        frame,
        baseline_probability,
    )
    challenger = role_aware_combination_race_evidence(
        frame,
        challenger_probability,
    )

    def _segment(
        baseline_segment: pd.DataFrame,
        challenger_segment: pd.DataFrame,
    ) -> dict:
        baseline_quality = _joint_quality(baseline_segment)
        challenger_quality = _joint_quality(challenger_segment)
        bootstrap = paired_race_bootstrap_joint_nll(
            challenger_segment,
            baseline_segment,
        )
        return {
            "baseline": baseline_quality,
            "challenger": challenger_quality,
            "trifecta_nll_delta": _safe_float(
                float(challenger_quality["mean_trifecta_nll"])
                - float(baseline_quality["mean_trifecta_nll"])
            ),
            "trio_nll_delta": _safe_float(
                float(challenger_quality["mean_trio_nll"])
                - float(baseline_quality["mean_trio_nll"])
            ),
            "paired_bootstrap_vs_baseline": bootstrap,
        }

    overall = _segment(baseline, challenger)
    longshot_ids = set(
        challenger.loc[
            challenger["contains_longshot"],
            "race_id",
        ].astype(str)
    )
    baseline_longshot = baseline.loc[
        baseline["race_id"].astype(str).isin(longshot_ids)
    ].copy()
    challenger_longshot = challenger.loc[
        challenger["race_id"].astype(str).isin(longshot_ids)
    ].copy()
    if baseline_longshot.empty or challenger_longshot.empty:
        raise ValueError(
            "no role-aware realized combinations contain a longshot proxy"
        )

    return {
        "method": (
            "role-aware fixed distribution: normalized historical win-market "
            "probability for first place; Top-3 q/(1-q) strengths for "
            "second and third among remaining runners"
        ),
        "overall": overall,
        "longshot_containing": {
            "definition": (
                "realized top three contains at least one runner with "
                "historical final win odds >= 6.0; development proxy only"
            ),
            **_segment(
                baseline_longshot,
                challenger_longshot,
            ),
        },
    }


def _conditioned_exact_three_set_probability(
    strengths: np.ndarray,
    selected: tuple[int, int, int],
) -> float:
    """Probability of one 3-runner set under Bernoulli odds conditioned on K=3."""
    if len(strengths) < 3:
        return 0.0
    maximum = float(np.max(strengths))
    if maximum <= 0.0:
        return 0.0
    scaled = strengths.astype(float) / maximum
    sum1 = float(np.sum(scaled))
    sum2 = float(np.sum(np.square(scaled)))
    sum3 = float(np.sum(np.power(scaled, 3)))
    normalizer = (
        sum1 ** 3
        - 3.0 * sum1 * sum2
        + 2.0 * sum3
    ) / 6.0
    if normalizer <= 0.0:
        return 0.0
    numerator = float(
        scaled[selected[0]]
        * scaled[selected[1]]
        * scaled[selected[2]]
    )
    return float(numerator / normalizer)


def _market_order_probability_within_selected(
    market_strengths: np.ndarray,
    order: tuple[int, int, int],
) -> float:
    selected_strength = np.asarray(
        [market_strengths[index] for index in order],
        dtype=float,
    )
    total = float(selected_strength.sum())
    if total <= 0.0:
        return 0.0
    first_p = float(selected_strength[0] / total)
    second_denominator = float(
        selected_strength[1] + selected_strength[2]
    )
    if second_denominator <= 0.0:
        return 0.0
    second_p = float(
        selected_strength[1] / second_denominator
    )
    return float(first_p * second_p)


def exact_three_combination_race_evidence(
    frame: pd.DataFrame,
    top3_probability: pd.Series,
) -> pd.DataFrame:
    """Phase 5: condition inclusion propensities on exactly three finishers."""
    if frame.empty:
        raise ValueError("exact-three combination frame is empty")
    if not top3_probability.index.equals(frame.index):
        raise ValueError("exact-three probability index differs from frame")
    if "market_implied_probability" not in frame.columns:
        raise ValueError(
            "exact-three combinations require market_implied_probability"
        )

    q = top3_probability.astype(float).clip(
        lower=1e-9,
        upper=1.0 - 1e-9,
    )
    rows: list[dict] = []

    for race_id, race in frame.groupby("race_id", sort=False):
        finish = pd.to_numeric(
            race["finish_position"],
            errors="coerce",
        )
        actual_indices: list[object] = []
        valid = True
        for place in (1, 2, 3):
            matches = race.index[finish.eq(place)].tolist()
            if len(matches) != 1:
                valid = False
                break
            actual_indices.append(matches[0])
        if not valid or len(race) < 3:
            continue

        local_indices = list(race.index)
        local_position = {
            index: idx
            for idx, index in enumerate(local_indices)
        }
        ordered = tuple(
            local_position[index]
            for index in actual_indices
        )
        selected_set = tuple(sorted(ordered))

        race_q = q.loc[local_indices].to_numpy(dtype=float)
        inclusion_strengths = race_q / (1.0 - race_q)
        trio_probability = _conditioned_exact_three_set_probability(
            inclusion_strengths,
            selected_set,
        )

        market_strengths = pd.to_numeric(
            race.loc[
                local_indices,
                "market_implied_probability",
            ],
            errors="raise",
        ).to_numpy(dtype=float)
        market_strengths = np.clip(
            market_strengths,
            1e-12,
            None,
        )
        order_probability = _market_order_probability_within_selected(
            market_strengths,
            ordered,
        )
        trifecta_probability = float(
            trio_probability * order_probability
        )

        top3_odds = pd.to_numeric(
            race.loc[actual_indices, "win_odds"],
            errors="coerce",
        )
        rows.append({
            "race_id": str(race_id),
            "trifecta_probability": max(
                float(trifecta_probability),
                1e-300,
            ),
            "trio_probability": max(
                min(float(trio_probability), 1.0),
                1e-300,
            ),
            "contains_longshot": bool(
                top3_odds.ge(TOP3_LONGSHOT_ODDS_MIN).any()
            ),
        })

    evidence = pd.DataFrame(rows)
    if evidence.empty:
        raise ValueError(
            "no races with unique first/second/third finishers "
            "for exact-three combination evidence"
        )
    evidence["trifecta_nll"] = -np.log(
        evidence["trifecta_probability"]
    )
    evidence["trio_nll"] = -np.log(
        evidence["trio_probability"]
    )
    return evidence


def evaluate_exact_three_combination_quality(
    frame: pd.DataFrame,
    baseline_probability: pd.Series,
    challenger_probability: pd.Series,
) -> dict:
    baseline = exact_three_combination_race_evidence(
        frame,
        baseline_probability,
    )
    challenger = exact_three_combination_race_evidence(
        frame,
        challenger_probability,
    )

    def _segment(
        baseline_segment: pd.DataFrame,
        challenger_segment: pd.DataFrame,
    ) -> dict:
        baseline_quality = _joint_quality(baseline_segment)
        challenger_quality = _joint_quality(challenger_segment)
        bootstrap = paired_race_bootstrap_joint_nll(
            challenger_segment,
            baseline_segment,
        )
        return {
            "baseline": baseline_quality,
            "challenger": challenger_quality,
            "trifecta_nll_delta": _safe_float(
                float(challenger_quality["mean_trifecta_nll"])
                - float(baseline_quality["mean_trifecta_nll"])
            ),
            "trio_nll_delta": _safe_float(
                float(challenger_quality["mean_trio_nll"])
                - float(baseline_quality["mean_trio_nll"])
            ),
            "paired_bootstrap_vs_baseline": bootstrap,
        }

    overall = _segment(baseline, challenger)
    longshot_ids = set(
        challenger.loc[
            challenger["contains_longshot"],
            "race_id",
        ].astype(str)
    )
    baseline_longshot = baseline.loc[
        baseline["race_id"].astype(str).isin(longshot_ids)
    ].copy()
    challenger_longshot = challenger.loc[
        challenger["race_id"].astype(str).isin(longshot_ids)
    ].copy()
    if baseline_longshot.empty or challenger_longshot.empty:
        raise ValueError(
            "no exact-three realized combinations contain a longshot proxy"
        )

    return {
        "method": (
            "Top-3 q/(1-q) inclusion odds conditioned on exactly three "
            "selected runners; market-implied strengths only allocate "
            "the six within-set finishing orders"
        ),
        "overall": overall,
        "longshot_containing": {
            "definition": (
                "realized top three contains at least one runner with "
                "historical final win odds >= 6.0; development proxy only"
            ),
            **_segment(
                baseline_longshot,
                challenger_longshot,
            ),
        },
    }


def _evaluate_period(
    frame: pd.DataFrame,
    baseline_probability: pd.Series,
    challenger_probability: pd.Series,
) -> dict:
    baseline = _top3_quality(
        frame,
        baseline_probability,
    )
    challenger = _top3_quality(
        frame,
        challenger_probability,
    )

    longshot_mask = pd.to_numeric(
        frame["win_odds"],
        errors="coerce",
    ).ge(TOP3_LONGSHOT_ODDS_MIN)
    longshot = frame.loc[longshot_mask].copy()
    baseline_longshot_probability = (
        baseline_probability.loc[longshot.index]
    )
    challenger_longshot_probability = (
        challenger_probability.loc[longshot.index]
    )

    baseline_longshot = _top3_quality(
        longshot,
        baseline_longshot_probability,
    )
    challenger_longshot = _top3_quality(
        longshot,
        challenger_longshot_probability,
    )

    bootstrap = paired_race_bootstrap_binary_quality(
        frame,
        challenger_probability,
        baseline_probability,
    )
    longshot_bootstrap = paired_race_bootstrap_binary_quality(
        longshot,
        challenger_longshot_probability,
        baseline_longshot_probability,
    )

    return {
        "period_start": str(frame["race_date"].min().date()),
        "period_end": str(frame["race_date"].max().date()),
        "baseline": baseline,
        "challenger": challenger,
        "binary_log_loss_delta": _safe_float(
            float(challenger["binary_log_loss"])
            - float(baseline["binary_log_loss"])
        ),
        "brier_delta": _safe_float(
            float(challenger["brier"])
            - float(baseline["brier"])
        ),
        "paired_bootstrap_vs_baseline": bootstrap,
        "combination_phase3": evaluate_exotic_combination_quality(
            frame,
            baseline_probability,
            challenger_probability,
        ),
        "role_aware_combination_phase4": (
            evaluate_role_aware_combination_quality(
                frame,
                baseline_probability,
                challenger_probability,
            )
        ),
        "exact_three_combination_phase5": (
            evaluate_exact_three_combination_quality(
                frame,
                baseline_probability,
                challenger_probability,
            )
        ),
        "longshot_proxy": {
            "definition": (
                "historical final win odds >= 6.0; "
                "development proxy only"
            ),
            "baseline": baseline_longshot,
            "challenger": challenger_longshot,
            "binary_log_loss_delta": _safe_float(
                float(challenger_longshot["binary_log_loss"])
                - float(baseline_longshot["binary_log_loss"])
            ),
            "brier_delta": _safe_float(
                float(challenger_longshot["brier"])
                - float(baseline_longshot["brier"])
            ),
            "paired_bootstrap_vs_baseline": (
                longshot_bootstrap
            ),
        },
    }


def evaluate_exotic_top3_development(
    history: pd.DataFrame,
    *,
    train_start: str = "2017-01-01",
    train_end: str = "2022-12-31",
    evaluation_2023_start: str = "2023-01-01",
    evaluation_2023_end: str = "2023-12-31",
    evaluation_2024_start: str = "2024-01-01",
    evaluation_2024_end: str = "2024-12-31",
    iterations: int = 300,
) -> dict:
    """Research whether runner-vs-field context improves Top-3 prediction."""
    if iterations < 1:
        raise ValueError("iterations must be positive")

    train_start_ts = pd.Timestamp(train_start).normalize()
    train_end_ts = pd.Timestamp(train_end).normalize()
    v23_start = pd.Timestamp(evaluation_2023_start).normalize()
    v23_end = pd.Timestamp(evaluation_2023_end).normalize()
    v24_start = pd.Timestamp(evaluation_2024_start).normalize()
    v24_end = pd.Timestamp(evaluation_2024_end).normalize()

    if not (
        train_start_ts
        <= train_end_ts
        < v23_start
        <= v23_end
        < v24_start
        <= v24_end
    ):
        raise ValueError("invalid exotic top3 development time split")

    data = align_history_to_training_start(
        history,
        train_start=str(train_start_ts.date()),
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
        & data["race_date"].le(v24_end)
    ].copy()
    if data.empty:
        raise ValueError("exotic top3 development history is empty")

    race_sizes = data.groupby("race_id")["race_id"].transform("size")
    data = data.loc[race_sizes.ge(3)].copy()

    enhanced = build_pre_race_features(
        data,
        experimental_ranker_v10=True,
    )
    baseline_frame = add_market_context_features(
        enhanced.frame
    )
    challenger_frame, interaction_features = (
        add_top3_race_interaction_features(
            baseline_frame
        )
    )

    baseline_features = (
        tuple(enhanced.feature_columns)
        + MARKET_CONTEXT_FEATURES
    )
    challenger_features = (
        baseline_features
        + interaction_features
    )

    dates = pd.to_datetime(
        baseline_frame["race_date"],
        errors="raise",
    )
    train_mask = dates.le(train_end_ts)
    v23_mask = dates.between(
        v23_start,
        v23_end,
        inclusive="both",
    )
    v24_mask = dates.between(
        v24_start,
        v24_end,
        inclusive="both",
    )

    baseline_train = baseline_frame.loc[train_mask].copy()
    challenger_train = challenger_frame.loc[train_mask].copy()
    baseline_v23 = baseline_frame.loc[v23_mask].copy()
    challenger_v23 = challenger_frame.loc[v23_mask].copy()
    baseline_v24 = baseline_frame.loc[v24_mask].copy()
    challenger_v24 = challenger_frame.loc[v24_mask].copy()

    if (
        baseline_train.empty
        or baseline_v23.empty
        or baseline_v24.empty
    ):
        raise ValueError(
            "exotic top3 development split contains an empty period"
        )

    target = top3_outcomes(baseline_train)
    baseline_model = Top3ProbabilityModel(
        list(baseline_features),
        iterations=iterations,
    ).fit(
        baseline_train,
        target,
    )
    challenger_model = Top3ProbabilityModel(
        list(challenger_features),
        iterations=iterations,
    ).fit(
        challenger_train,
        target,
    )

    def _score(
        baseline_period: pd.DataFrame,
        challenger_period: pd.DataFrame,
    ) -> dict:
        baseline_probability = (
            baseline_model.predict_probability(
                baseline_period
            )
        )
        challenger_probability = (
            challenger_model.predict_probability(
                challenger_period
            )
        )
        return _evaluate_period(
            baseline_period,
            baseline_probability,
            challenger_probability,
        )

    result_2023 = _score(
        baseline_v23,
        challenger_v23,
    )
    result_2024 = _score(
        baseline_v24,
        challenger_v24,
    )

    def _period_passed(result: dict) -> bool:
        longshot = result["longshot_proxy"]
        return bool(
            float(result["binary_log_loss_delta"]) < 0.0
            and float(result["brier_delta"]) < 0.0
            and float(
                longshot["binary_log_loss_delta"]
            ) < 0.0
            and float(longshot["brier_delta"]) < 0.0
        )

    gate = bool(
        _period_passed(result_2023)
        and _period_passed(result_2024)
    )

    def _bootstrap_period_passed(result: dict) -> bool:
        overall = result["paired_bootstrap_vs_baseline"]
        longshot = result["longshot_proxy"][
            "paired_bootstrap_vs_baseline"
        ]
        return bool(
            float(
                overall[
                    "binary_log_loss_improvement_support"
                ]
            ) >= TOP3_MIN_IMPROVEMENT_SUPPORT
            and float(
                overall["brier_improvement_support"]
            ) >= TOP3_MIN_IMPROVEMENT_SUPPORT
            and float(
                longshot[
                    "binary_log_loss_improvement_support"
                ]
            ) >= TOP3_MIN_IMPROVEMENT_SUPPORT
            and float(
                longshot["brier_improvement_support"]
            ) >= TOP3_MIN_IMPROVEMENT_SUPPORT
        )

    safety_gate = bool(
        gate
        and _bootstrap_period_passed(result_2023)
        and _bootstrap_period_passed(result_2024)
    )

    def _combination_period_passed(result: dict) -> bool:
        evidence = result["combination_phase3"]
        for segment_name in ("overall", "longshot_containing"):
            segment = evidence[segment_name]
            bootstrap = segment["paired_bootstrap_vs_baseline"]
            if not (
                float(segment["trifecta_nll_delta"]) < 0.0
                and float(segment["trio_nll_delta"]) < 0.0
                and float(
                    bootstrap[
                        "trifecta_nll_improvement_support"
                    ]
                ) >= TOP3_MIN_IMPROVEMENT_SUPPORT
                and float(
                    bootstrap["trio_nll_improvement_support"]
                ) >= TOP3_MIN_IMPROVEMENT_SUPPORT
            ):
                return False
        return True

    combination_gate = bool(
        safety_gate
        and _combination_period_passed(result_2023)
        and _combination_period_passed(result_2024)
    )

    def _role_aware_period_passed(result: dict) -> bool:
        evidence = result["role_aware_combination_phase4"]
        for segment_name in ("overall", "longshot_containing"):
            segment = evidence[segment_name]
            bootstrap = segment["paired_bootstrap_vs_baseline"]
            if not (
                float(segment["trifecta_nll_delta"]) < 0.0
                and float(segment["trio_nll_delta"]) < 0.0
                and float(
                    bootstrap[
                        "trifecta_nll_improvement_support"
                    ]
                ) >= TOP3_MIN_IMPROVEMENT_SUPPORT
                and float(
                    bootstrap["trio_nll_improvement_support"]
                ) >= TOP3_MIN_IMPROVEMENT_SUPPORT
            ):
                return False
        return True

    role_aware_gate = bool(
        safety_gate
        and _role_aware_period_passed(result_2023)
        and _role_aware_period_passed(result_2024)
    )

    def _exact_three_period_passed(result: dict) -> bool:
        evidence = result["exact_three_combination_phase5"]
        for segment_name in ("overall", "longshot_containing"):
            segment = evidence[segment_name]
            bootstrap = segment["paired_bootstrap_vs_baseline"]
            if not (
                float(segment["trifecta_nll_delta"]) < 0.0
                and float(segment["trio_nll_delta"]) < 0.0
                and float(
                    bootstrap[
                        "trifecta_nll_improvement_support"
                    ]
                ) >= TOP3_MIN_IMPROVEMENT_SUPPORT
                and float(
                    bootstrap["trio_nll_improvement_support"]
                ) >= TOP3_MIN_IMPROVEMENT_SUPPORT
            ):
                return False
        return True

    exact_three_gate = bool(
        safety_gate
        and _exact_three_period_passed(result_2023)
        and _exact_three_period_passed(result_2024)
    )

    return {
        "status": "research_only_exotic_top3_development",
        "hypothesis": (
            "Past-only runner-vs-field composition features improve "
            "Top-3 probability estimation, including the pre-registered "
            "historical final-odds >= 6.0 longshot proxy."
        ),
        "warning": (
            "Phase 5 evaluates exact-three conditioned trio/trifecta "
            "probability quality but not betting expected value. Historical "
            "final win odds are development-only market inputs/proxies. No "
            "pre-race exotic combination odds are available in the current "
            "free pipeline, so no three-leg bet is selected."
        ),
        "training": {
            "period_start": str(
                baseline_train["race_date"].min().date()
            ),
            "period_end": str(
                baseline_train["race_date"].max().date()
            ),
            "rows": int(len(baseline_train)),
            "races": int(
                baseline_train["race_id"].nunique()
            ),
            "top3_rate": _safe_float(target.mean()),
        },
        "feature_design": {
            "baseline_feature_count": int(
                len(baseline_features)
            ),
            "challenger_feature_count": int(
                len(challenger_features)
            ),
            "interaction_sources_requested": list(
                TOP3_INTERACTION_SOURCE_FEATURES
            ),
            "interaction_features_generated": list(
                interaction_features
            ),
            "pedigree_status": (
                "not_enabled: current history exposes only a blood "
                "registration identifier, not semantic sire/dam/"
                "broodmare-sire fields; identifier memorization is "
                "intentionally excluded"
            ),
        },
        "research_protocol": {
            "development_periods": [
                "training_through_2022",
                "2023_development_reused",
                "2024_development_reused",
            ],
            "final_holdout": "2025-2026 untouched",
            "forward_paper": "unchanged",
            "paid_data": "not_used",
        },
        "exact_three_combination_phase5": {
            "transform": (
                "condition frozen Top-3 q/(1-q) inclusion odds on exactly "
                "three selected runners; market strengths order the set"
            ),
            "minimum_improvement_support": (
                TOP3_MIN_IMPROVEMENT_SUPPORT
            ),
            "development_exact_three_gate_passed": (
                exact_three_gate
            ),
            "phase3_result_required": False,
            "phase4_result_required": False,
        },
        "role_aware_combination_phase4": {
            "transform": (
                "historical win-market first-place probability + "
                "frozen Top-3 q/(1-q) second/third strengths"
            ),
            "minimum_improvement_support": (
                TOP3_MIN_IMPROVEMENT_SUPPORT
            ),
            "development_role_aware_gate_passed": (
                role_aware_gate
            ),
            "phase3_result_required": False,
        },
        "combination_phase3": {
            "transform": (
                "fixed Plackett-Luce q/(1-q); no Phase 3 fitting"
            ),
            "targets": [
                "realized ordered top-three (trifecta probability proxy)",
                "realized unordered top-three set (trio probability proxy)",
            ],
            "minimum_improvement_support": (
                TOP3_MIN_IMPROVEMENT_SUPPORT
            ),
            "development_combination_gate_passed": (
                combination_gate
            ),
        },
        "bootstrap_safety_phase2": {
            "samples": TOP3_BOOTSTRAP_SAMPLES,
            "seed": TOP3_BOOTSTRAP_SEED,
            "minimum_improvement_support": (
                TOP3_MIN_IMPROVEMENT_SUPPORT
            ),
            "development_safety_gate_passed": safety_gate,
        },
        "evaluation_2023": result_2023,
        "evaluation_2024": result_2024,
        "development_gate_passed": gate,
        "development_safety_gate_passed": safety_gate,
        "development_combination_gate_passed": combination_gate,
        "development_role_aware_gate_passed": role_aware_gate,
        "development_exact_three_gate_passed": exact_three_gate,
    }
