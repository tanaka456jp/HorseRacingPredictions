from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .feature_window import align_history_to_training_start
from .features import build_pre_race_features
from .market_aware_ranker_v11 import (
    MARKET_CONTEXT_FEATURES,
    add_market_context_features,
)
from .modeling import CatBoostRankingProbabilityModel
from .exotic_top3_research import (
    TOP3_BOOTSTRAP_SAMPLES,
    TOP3_BOOTSTRAP_SEED,
    TOP3_LONGSHOT_ODDS_MIN,
    TOP3_MIN_IMPROVEMENT_SUPPORT,
    Top3ProbabilityModel,
    add_top3_race_interaction_features,
    top3_outcomes,
)
from .exotic_longshot_phase7 import (
    INTRUSION_COMPARISON_SOURCES,
    add_longshot_intrusion_features,
)


LONGSHOT_RANKER_ITERATIONS = 350
LONGSHOT_RANKER_DEPTH = 7
LONGSHOT_RANKER_LEARNING_RATE = 0.05
LONGSHOT_RANKER_RANDOM_SEED = 42


def _safe_float(value) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None


def _ranking_evidence(
    frame: pd.DataFrame,
    specialist_score: pd.Series,
    baseline_probability: pd.Series,
) -> pd.DataFrame:
    if frame.empty:
        raise ValueError("longshot ranking frame is empty")
    if not specialist_score.index.equals(frame.index):
        raise ValueError(
            "specialist score index differs from frame"
        )
    if not baseline_probability.index.equals(frame.index):
        raise ValueError(
            "baseline probability index differs from frame"
        )

    work = frame[
        ["race_id", "finish_position"]
    ].copy()
    work["target"] = top3_outcomes(frame).astype(int)
    work["specialist_score"] = specialist_score.astype(float)
    work["baseline_probability"] = baseline_probability.astype(float)

    rows: list[dict] = []
    for race_id, race in work.groupby(
        "race_id",
        sort=False,
    ):
        specialist_order = race.sort_values(
            "specialist_score",
            ascending=False,
            kind="stable",
        )
        baseline_order = race.sort_values(
            "baseline_probability",
            ascending=False,
            kind="stable",
        )

        specialist_hits = specialist_order[
            "target"
        ].to_numpy(dtype=int)
        baseline_hits = baseline_order[
            "target"
        ].to_numpy(dtype=int)

        def _mrr(values: np.ndarray) -> float:
            positions = np.flatnonzero(values == 1)
            if len(positions) == 0:
                return 0.0
            return 1.0 / float(positions[0] + 1)

        rows.append({
            "race_id": str(race_id),
            "candidate_count": int(len(race)),
            "positive_count": int(
                race["target"].sum()
            ),
            "specialist_top1_hit": int(
                specialist_hits[0]
            ),
            "baseline_top1_hit": int(
                baseline_hits[0]
            ),
            "specialist_mrr": _mrr(
                specialist_hits
            ),
            "baseline_mrr": _mrr(
                baseline_hits
            ),
        })

    evidence = pd.DataFrame(rows)
    if evidence.empty:
        raise ValueError(
            "longshot ranking evidence is empty"
        )
    return evidence


def paired_race_bootstrap_longshot_ranking(
    evidence: pd.DataFrame,
    *,
    samples: int = TOP3_BOOTSTRAP_SAMPLES,
    seed: int = TOP3_BOOTSTRAP_SEED,
) -> dict:
    if evidence.empty:
        raise ValueError(
            "longshot ranking bootstrap evidence is empty"
        )
    if samples < 1:
        raise ValueError(
            "bootstrap samples must be positive"
        )

    top1_delta = (
        evidence["specialist_top1_hit"]
        - evidence["baseline_top1_hit"]
    ).to_numpy(dtype=float)
    mrr_delta = (
        evidence["specialist_mrr"]
        - evidence["baseline_mrr"]
    ).to_numpy(dtype=float)

    race_count = int(len(evidence))
    rng = np.random.default_rng(seed)
    sampled_top1 = np.empty(
        int(samples),
        dtype=float,
    )
    sampled_mrr = np.empty(
        int(samples),
        dtype=float,
    )

    for idx in range(int(samples)):
        draw = rng.integers(
            0,
            race_count,
            size=race_count,
        )
        sampled_top1[idx] = float(
            top1_delta[draw].mean()
        )
        sampled_mrr[idx] = float(
            mrr_delta[draw].mean()
        )

    return {
        "samples": int(samples),
        "seed": int(seed),
        "races": race_count,
        "top1_hit_rate_improvement_support": _safe_float(
            np.mean(sampled_top1 > 0.0)
        ),
        "mrr_improvement_support": _safe_float(
            np.mean(sampled_mrr > 0.0)
        ),
        "top1_hit_rate_delta_ci90": [
            _safe_float(
                np.quantile(
                    sampled_top1,
                    0.05,
                )
            ),
            _safe_float(
                np.quantile(
                    sampled_top1,
                    0.95,
                )
            ),
        ],
        "mrr_delta_ci90": [
            _safe_float(
                np.quantile(
                    sampled_mrr,
                    0.05,
                )
            ),
            _safe_float(
                np.quantile(
                    sampled_mrr,
                    0.95,
                )
            ),
        ],
    }


def _evaluate_period(
    frame: pd.DataFrame,
    specialist_score: pd.Series,
    baseline_probability: pd.Series,
) -> dict:
    evidence = _ranking_evidence(
        frame,
        specialist_score,
        baseline_probability,
    )
    specialist_top1 = _safe_float(
        evidence[
            "specialist_top1_hit"
        ].mean()
    )
    baseline_top1 = _safe_float(
        evidence[
            "baseline_top1_hit"
        ].mean()
    )
    specialist_mrr = _safe_float(
        evidence[
            "specialist_mrr"
        ].mean()
    )
    baseline_mrr = _safe_float(
        evidence[
            "baseline_mrr"
        ].mean()
    )
    bootstrap = (
        paired_race_bootstrap_longshot_ranking(
            evidence
        )
    )

    return {
        "period_start": str(
            frame["race_date"].min().date()
        ),
        "period_end": str(
            frame["race_date"].max().date()
        ),
        "definition": (
            "historical final win odds >= 6.0; "
            "development proxy only"
        ),
        "rows": int(len(frame)),
        "races": int(
            frame["race_id"].nunique()
        ),
        "races_with_positive_longshot": int(
            evidence[
                "positive_count"
            ].gt(0).sum()
        ),
        "top1": {
            "baseline_hit_rate": (
                baseline_top1
            ),
            "specialist_hit_rate": (
                specialist_top1
            ),
            "hit_rate_delta": _safe_float(
                float(specialist_top1)
                - float(baseline_top1)
            ),
        },
        "mrr": {
            "baseline": baseline_mrr,
            "specialist": specialist_mrr,
            "delta": _safe_float(
                float(specialist_mrr)
                - float(baseline_mrr)
            ),
        },
        "paired_bootstrap_vs_general_top3_ranking": (
            bootstrap
        ),
    }


def evaluate_longshot_ranker_phase8(
    history: pd.DataFrame,
    *,
    train_start: str = "2017-01-01",
    train_end: str = "2022-12-31",
    evaluation_2023_start: str = "2023-01-01",
    evaluation_2023_end: str = "2023-12-31",
    evaluation_2024_start: str = "2024-01-01",
    evaluation_2024_end: str = "2024-12-31",
) -> dict:
    train_start_ts = pd.Timestamp(
        train_start
    ).normalize()
    train_end_ts = pd.Timestamp(
        train_end
    ).normalize()
    v23_start = pd.Timestamp(
        evaluation_2023_start
    ).normalize()
    v23_end = pd.Timestamp(
        evaluation_2023_end
    ).normalize()
    v24_start = pd.Timestamp(
        evaluation_2024_start
    ).normalize()
    v24_end = pd.Timestamp(
        evaluation_2024_end
    ).normalize()

    if not (
        train_start_ts
        <= train_end_ts
        < v23_start
        <= v23_end
        < v24_start
        <= v24_end
    ):
        raise ValueError(
            "invalid longshot ranker development split"
        )

    data = align_history_to_training_start(
        history,
        train_start=str(
            train_start_ts.date()
        ),
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
        raise ValueError(
            "longshot ranker history is empty"
        )

    race_sizes = data.groupby(
        "race_id"
    )["race_id"].transform("size")
    data = data.loc[
        race_sizes.ge(3)
    ].copy()

    enhanced = build_pre_race_features(
        data,
        experimental_ranker_v10=True,
    )
    market_frame = add_market_context_features(
        enhanced.frame
    )
    general_frame, interaction_features = (
        add_top3_race_interaction_features(
            market_frame
        )
    )
    ranker_frame, intrusion_features = (
        add_longshot_intrusion_features(
            general_frame
        )
    )

    general_features = (
        tuple(enhanced.feature_columns)
        + MARKET_CONTEXT_FEATURES
        + interaction_features
    )
    ranker_features = (
        general_features
        + intrusion_features
    )

    dates = pd.to_datetime(
        general_frame["race_date"],
        errors="raise",
    )
    train_mask = dates.le(
        train_end_ts
    )
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
    longshot_mask = pd.to_numeric(
        general_frame["win_odds"],
        errors="coerce",
    ).ge(TOP3_LONGSHOT_ODDS_MIN)

    general_train = general_frame.loc[
        train_mask
    ].copy()
    ranker_train = ranker_frame.loc[
        train_mask & longshot_mask
    ].copy()
    ranker_train["is_top3_longshot"] = (
        top3_outcomes(ranker_train)
    )

    v23_general = general_frame.loc[
        v23_mask & longshot_mask
    ].copy()
    v23_ranker = ranker_frame.loc[
        v23_mask & longshot_mask
    ].copy()
    v24_general = general_frame.loc[
        v24_mask & longshot_mask
    ].copy()
    v24_ranker = ranker_frame.loc[
        v24_mask & longshot_mask
    ].copy()

    if (
        general_train.empty
        or ranker_train.empty
        or v23_general.empty
        or v24_general.empty
    ):
        raise ValueError(
            "longshot ranker split contains an empty period"
        )

    general_model = Top3ProbabilityModel(
        list(general_features),
        iterations=300,
        depth=7,
        learning_rate=0.05,
        random_seed=42,
    ).fit(
        general_train,
        top3_outcomes(general_train),
    )

    ranker_model = CatBoostRankingProbabilityModel(
        feature_columns=list(
            ranker_features
        ),
        iterations=LONGSHOT_RANKER_ITERATIONS,
        depth=LONGSHOT_RANKER_DEPTH,
        learning_rate=(
            LONGSHOT_RANKER_LEARNING_RATE
        ),
        random_seed=(
            LONGSHOT_RANKER_RANDOM_SEED
        ),
        loss_function="YetiRankPairwise",
    ).fit(
        ranker_train,
        target_col="is_top3_longshot",
        race_col="race_id",
    )

    def _score(
        general_period: pd.DataFrame,
        ranker_period: pd.DataFrame,
    ) -> dict:
        baseline_probability = (
            general_model.predict_probability(
                general_period
            )
        )
        specialist_score = (
            ranker_model.predict_win_probability(
                ranker_period,
                race_col="race_id",
            )
        )
        specialist_score.index = (
            general_period.index
        )
        return _evaluate_period(
            general_period,
            specialist_score,
            baseline_probability,
        )

    result_2023 = _score(
        v23_general,
        v23_ranker,
    )
    result_2024 = _score(
        v24_general,
        v24_ranker,
    )

    def _period_passed(
        result: dict,
    ) -> bool:
        bootstrap = result[
            "paired_bootstrap_vs_general_top3_ranking"
        ]
        return bool(
            float(
                result["top1"][
                    "hit_rate_delta"
                ]
            ) > 0.0
            and float(
                result["mrr"]["delta"]
            ) > 0.0
            and float(
                bootstrap[
                    "top1_hit_rate_improvement_support"
                ]
            ) >= TOP3_MIN_IMPROVEMENT_SUPPORT
            and float(
                bootstrap[
                    "mrr_improvement_support"
                ]
            ) >= TOP3_MIN_IMPROVEMENT_SUPPORT
        )

    gate = bool(
        _period_passed(result_2023)
        and _period_passed(result_2024)
    )

    return {
        "status": (
            "research_only_longshot_ranker_phase8"
        ),
        "hypothesis": (
            "The Phase 7 specialist contains useful ordering signal "
            "but poor probability calibration. A race-group ranking "
            "objective trained only on longshot candidates can improve "
            "which longshot is selected while the general Top-3 model "
            "remains the probability source."
        ),
        "warning": (
            "Phase 8 is ranking-only research. It does not replace "
            "general Top-3 probability calibration and does not create "
            "trio/trifecta expected-value estimates or betting tickets."
        ),
        "training": {
            "general_rows": int(
                len(general_train)
            ),
            "ranker_longshot_rows": int(
                len(ranker_train)
            ),
            "general_races": int(
                general_train[
                    "race_id"
                ].nunique()
            ),
            "ranker_longshot_races": int(
                ranker_train[
                    "race_id"
                ].nunique()
            ),
            "iterations": (
                LONGSHOT_RANKER_ITERATIONS
            ),
            "depth": (
                LONGSHOT_RANKER_DEPTH
            ),
            "learning_rate": (
                LONGSHOT_RANKER_LEARNING_RATE
            ),
            "random_seed": (
                LONGSHOT_RANKER_RANDOM_SEED
            ),
            "loss_function": (
                "YetiRankPairwise"
            ),
        },
        "feature_design": {
            "general_feature_count": int(
                len(general_features)
            ),
            "ranker_feature_count": int(
                len(ranker_features)
            ),
            "intrusion_comparison_sources": list(
                INTRUSION_COMPARISON_SOURCES
            ),
            "intrusion_features": list(
                intrusion_features
            ),
        },
        "research_protocol": {
            "baseline": (
                "general Phase 2-style Top-3 probabilities "
                "used only for longshot ordering baseline"
            ),
            "specialist": (
                "longshot-only YetiRankPairwise ranking model; "
                "not used as calibrated probability"
            ),
            "metrics": [
                "top1_longshot_top3_hit_rate",
                "mean_reciprocal_rank_of_first_top3_longshot",
            ],
            "minimum_improvement_support": (
                TOP3_MIN_IMPROVEMENT_SUPPORT
            ),
            "bootstrap_samples": (
                TOP3_BOOTSTRAP_SAMPLES
            ),
            "bootstrap_seed": (
                TOP3_BOOTSTRAP_SEED
            ),
            "final_holdout": (
                "2025-2026 untouched"
            ),
            "forward_paper": "unchanged",
            "paid_data": "not_used",
            "real_ticket_generation": "disabled",
        },
        "evaluation_2023": result_2023,
        "evaluation_2024": result_2024,
        "development_longshot_ranker_gate_passed": gate,
    }
