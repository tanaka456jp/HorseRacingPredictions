from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .evaluation import brier_score, binary_log_loss
from .feature_window import align_history_to_training_start
from .features import build_pre_race_features
from .market_aware_ranker_v11 import (
    MARKET_CONTEXT_FEATURES,
    add_market_context_features,
)
from .exotic_top3_research import (
    TOP3_BOOTSTRAP_SAMPLES,
    TOP3_BOOTSTRAP_SEED,
    TOP3_INTERACTION_SOURCE_FEATURES,
    TOP3_LONGSHOT_ODDS_MIN,
    TOP3_MIN_IMPROVEMENT_SUPPORT,
    Top3ProbabilityModel,
    add_top3_race_interaction_features,
    top3_outcomes,
)


LONGSHOT_INTRUSION_ITERATIONS = 300
LONGSHOT_INTRUSION_DEPTH = 7
LONGSHOT_INTRUSION_LEARNING_RATE = 0.05
LONGSHOT_INTRUSION_RANDOM_SEED = 42

INTRUSION_COMPARISON_SOURCES = (
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


def add_longshot_intrusion_features(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    """Add favorite/top-market comparisons from pre-race-only source features."""
    required = {
        "race_id",
        "market_implied_probability",
        "market_probability_rank",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(
            f"longshot intrusion frame missing columns: {sorted(missing)}"
        )

    out = frame.copy()
    rank = pd.to_numeric(
        out["market_probability_rank"],
        errors="coerce",
    )
    market = pd.to_numeric(
        out["market_implied_probability"],
        errors="coerce",
    )
    race_id = out["race_id"]
    generated: list[str] = []

    field_size = race_id.groupby(race_id, sort=False).transform("size")
    out["intrusion_market_rank_pct"] = (
        rank / field_size.astype(float)
    )
    favorite_probability = market.groupby(
        race_id,
        sort=False,
    ).transform("max").clip(lower=1e-12)
    out["intrusion_market_probability_vs_favorite"] = (
        market / favorite_probability
    )
    top3_market = market.where(rank.le(3))
    top3_market_mean = top3_market.groupby(
        race_id,
        sort=False,
    ).transform("mean")
    out["intrusion_market_probability_vs_top3_mean"] = (
        market - top3_market_mean
    )
    generated.extend([
        "intrusion_market_rank_pct",
        "intrusion_market_probability_vs_favorite",
        "intrusion_market_probability_vs_top3_mean",
    ])

    for source in INTRUSION_COMPARISON_SOURCES:
        if source not in out.columns:
            continue
        values = pd.to_numeric(
            out[source],
            errors="coerce",
        )
        favorite_values = values.where(rank.eq(1))
        favorite = favorite_values.groupby(
            race_id,
            sort=False,
        ).transform("max")
        top3_values = values.where(rank.le(3))
        top3_mean = top3_values.groupby(
            race_id,
            sort=False,
        ).transform("mean")

        favorite_name = f"intrusion_{source}_vs_favorite"
        top3_name = f"intrusion_{source}_vs_market_top3_mean"
        out[favorite_name] = values - favorite
        out[top3_name] = values - top3_mean
        generated.extend([favorite_name, top3_name])

    return out, tuple(generated)


def _longshot_quality(
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


def _top_longshot_pick_evidence(
    frame: pd.DataFrame,
    specialist_probability: pd.Series,
    baseline_probability: pd.Series,
) -> pd.DataFrame:
    evidence = frame[
        ["race_id", "finish_position", "win_odds"]
    ].copy()
    evidence["specialist_probability"] = (
        specialist_probability.astype(float)
    )
    evidence["baseline_probability"] = (
        baseline_probability.astype(float)
    )
    rows: list[dict] = []

    for race_id, race in evidence.groupby(
        "race_id",
        sort=False,
    ):
        if race.empty:
            continue
        specialist_index = race[
            "specialist_probability"
        ].idxmax()
        baseline_index = race[
            "baseline_probability"
        ].idxmax()
        rows.append({
            "race_id": str(race_id),
            "specialist_hit": int(
                float(
                    pd.to_numeric(
                        race.loc[
                            specialist_index,
                            "finish_position",
                        ],
                        errors="coerce",
                    )
                ) <= 3.0
            ),
            "baseline_hit": int(
                float(
                    pd.to_numeric(
                        race.loc[
                            baseline_index,
                            "finish_position",
                        ],
                        errors="coerce",
                    )
                ) <= 3.0
            ),
        })

    result = pd.DataFrame(rows)
    if result.empty:
        raise ValueError(
            "top-longshot pick evidence is empty"
        )
    return result


def paired_race_bootstrap_longshot_intrusion(
    frame: pd.DataFrame,
    specialist_probability: pd.Series,
    baseline_probability: pd.Series,
    *,
    samples: int = TOP3_BOOTSTRAP_SAMPLES,
    seed: int = TOP3_BOOTSTRAP_SEED,
) -> dict:
    """Paired race bootstrap for conditional longshot model quality."""
    if frame.empty:
        raise ValueError("longshot bootstrap frame is empty")
    if not specialist_probability.index.equals(frame.index):
        raise ValueError(
            "specialist probability index differs from frame"
        )
    if not baseline_probability.index.equals(frame.index):
        raise ValueError(
            "baseline probability index differs from frame"
        )

    target = top3_outcomes(frame).astype(float)
    specialist = specialist_probability.astype(float).clip(
        lower=1e-12,
        upper=1.0 - 1e-12,
    )
    baseline = baseline_probability.astype(float).clip(
        lower=1e-12,
        upper=1.0 - 1e-12,
    )

    specialist_logloss = -(
        target * np.log(specialist)
        + (1.0 - target) * np.log(1.0 - specialist)
    )
    baseline_logloss = -(
        target * np.log(baseline)
        + (1.0 - target) * np.log(1.0 - baseline)
    )

    row_evidence = pd.DataFrame({
        "race_id": frame["race_id"].astype(str),
        "logloss_delta": (
            specialist_logloss - baseline_logloss
        ),
        "brier_delta": (
            np.square(specialist - target)
            - np.square(baseline - target)
        ),
    })
    grouped = (
        row_evidence.groupby("race_id", sort=False)
        .agg(
            logloss_sum=("logloss_delta", "sum"),
            brier_sum=("brier_delta", "sum"),
            rows=("race_id", "size"),
        )
    )

    pick = _top_longshot_pick_evidence(
        frame,
        specialist_probability,
        baseline_probability,
    ).set_index("race_id")
    grouped = grouped.join(
        pick,
        how="inner",
    )
    if grouped.empty:
        raise ValueError(
            "longshot bootstrap has no paired races"
        )

    logloss_sum = grouped[
        "logloss_sum"
    ].to_numpy(dtype=float)
    brier_sum = grouped[
        "brier_sum"
    ].to_numpy(dtype=float)
    row_count = grouped[
        "rows"
    ].to_numpy(dtype=float)
    hit_delta = (
        grouped["specialist_hit"]
        - grouped["baseline_hit"]
    ).to_numpy(dtype=float)

    race_count = int(len(grouped))
    rng = np.random.default_rng(seed)
    sampled_logloss = np.empty(
        int(samples),
        dtype=float,
    )
    sampled_brier = np.empty(
        int(samples),
        dtype=float,
    )
    sampled_hit_delta = np.empty(
        int(samples),
        dtype=float,
    )

    for idx in range(int(samples)):
        draw = rng.integers(
            0,
            race_count,
            size=race_count,
        )
        denominator = float(
            row_count[draw].sum()
        )
        sampled_logloss[idx] = float(
            logloss_sum[draw].sum()
            / denominator
        )
        sampled_brier[idx] = float(
            brier_sum[draw].sum()
            / denominator
        )
        sampled_hit_delta[idx] = float(
            hit_delta[draw].mean()
        )

    return {
        "samples": int(samples),
        "seed": int(seed),
        "races": race_count,
        "binary_log_loss_improvement_support": _safe_float(
            np.mean(sampled_logloss < 0.0)
        ),
        "brier_improvement_support": _safe_float(
            np.mean(sampled_brier < 0.0)
        ),
        "top_pick_hit_rate_improvement_support": _safe_float(
            np.mean(sampled_hit_delta > 0.0)
        ),
        "binary_log_loss_delta_ci90": [
            _safe_float(
                np.quantile(
                    sampled_logloss,
                    0.05,
                )
            ),
            _safe_float(
                np.quantile(
                    sampled_logloss,
                    0.95,
                )
            ),
        ],
        "brier_delta_ci90": [
            _safe_float(
                np.quantile(
                    sampled_brier,
                    0.05,
                )
            ),
            _safe_float(
                np.quantile(
                    sampled_brier,
                    0.95,
                )
            ),
        ],
        "top_pick_hit_rate_delta_ci90": [
            _safe_float(
                np.quantile(
                    sampled_hit_delta,
                    0.05,
                )
            ),
            _safe_float(
                np.quantile(
                    sampled_hit_delta,
                    0.95,
                )
            ),
        ],
    }


def _evaluate_period(
    frame: pd.DataFrame,
    specialist_probability: pd.Series,
    baseline_probability: pd.Series,
) -> dict:
    specialist = _longshot_quality(
        frame,
        specialist_probability,
    )
    baseline = _longshot_quality(
        frame,
        baseline_probability,
    )
    picks = _top_longshot_pick_evidence(
        frame,
        specialist_probability,
        baseline_probability,
    )
    specialist_hit_rate = _safe_float(
        picks["specialist_hit"].mean()
    )
    baseline_hit_rate = _safe_float(
        picks["baseline_hit"].mean()
    )
    bootstrap = (
        paired_race_bootstrap_longshot_intrusion(
            frame,
            specialist_probability,
            baseline_probability,
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
        "baseline": baseline,
        "specialist": specialist,
        "binary_log_loss_delta": _safe_float(
            float(specialist["binary_log_loss"])
            - float(baseline["binary_log_loss"])
        ),
        "brier_delta": _safe_float(
            float(specialist["brier"])
            - float(baseline["brier"])
        ),
        "top_pick": {
            "races": int(len(picks)),
            "baseline_hit_rate": (
                baseline_hit_rate
            ),
            "specialist_hit_rate": (
                specialist_hit_rate
            ),
            "hit_rate_delta": _safe_float(
                float(specialist_hit_rate)
                - float(baseline_hit_rate)
            ),
        },
        "paired_bootstrap_vs_general_top3": (
            bootstrap
        ),
    }


def evaluate_longshot_intrusion_phase7(
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
            "invalid longshot intrusion development split"
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
            "longshot intrusion history is empty"
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
    specialist_frame, intrusion_features = (
        add_longshot_intrusion_features(
            general_frame
        )
    )

    general_features = (
        tuple(enhanced.feature_columns)
        + MARKET_CONTEXT_FEATURES
        + interaction_features
    )
    specialist_features = (
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
    specialist_train = specialist_frame.loc[
        train_mask & longshot_mask
    ].copy()

    v23_general = general_frame.loc[
        v23_mask & longshot_mask
    ].copy()
    v23_specialist = specialist_frame.loc[
        v23_mask & longshot_mask
    ].copy()
    v24_general = general_frame.loc[
        v24_mask & longshot_mask
    ].copy()
    v24_specialist = specialist_frame.loc[
        v24_mask & longshot_mask
    ].copy()

    if (
        general_train.empty
        or specialist_train.empty
        or v23_general.empty
        or v24_general.empty
    ):
        raise ValueError(
            "longshot intrusion split contains an empty period"
        )

    general_model = Top3ProbabilityModel(
        list(general_features),
        iterations=LONGSHOT_INTRUSION_ITERATIONS,
        depth=LONGSHOT_INTRUSION_DEPTH,
        learning_rate=LONGSHOT_INTRUSION_LEARNING_RATE,
        random_seed=LONGSHOT_INTRUSION_RANDOM_SEED,
    ).fit(
        general_train,
        top3_outcomes(general_train),
    )

    specialist_model = Top3ProbabilityModel(
        list(specialist_features),
        iterations=LONGSHOT_INTRUSION_ITERATIONS,
        depth=LONGSHOT_INTRUSION_DEPTH,
        learning_rate=LONGSHOT_INTRUSION_LEARNING_RATE,
        random_seed=LONGSHOT_INTRUSION_RANDOM_SEED,
    ).fit(
        specialist_train,
        top3_outcomes(specialist_train),
    )

    def _score(
        general_period: pd.DataFrame,
        specialist_period: pd.DataFrame,
    ) -> dict:
        baseline_probability = (
            general_model.predict_probability(
                general_period
            )
        )
        specialist_probability = (
            specialist_model.predict_probability(
                specialist_period
            )
        )
        specialist_probability.index = (
            general_period.index
        )
        return _evaluate_period(
            general_period,
            specialist_probability,
            baseline_probability,
        )

    result_2023 = _score(
        v23_general,
        v23_specialist,
    )
    result_2024 = _score(
        v24_general,
        v24_specialist,
    )

    def _period_passed(
        result: dict,
    ) -> bool:
        bootstrap = result[
            "paired_bootstrap_vs_general_top3"
        ]
        return bool(
            float(
                result[
                    "binary_log_loss_delta"
                ]
            ) < 0.0
            and float(
                result["brier_delta"]
            ) < 0.0
            and float(
                result["top_pick"][
                    "hit_rate_delta"
                ]
            ) > 0.0
            and float(
                bootstrap[
                    "binary_log_loss_improvement_support"
                ]
            ) >= TOP3_MIN_IMPROVEMENT_SUPPORT
            and float(
                bootstrap[
                    "brier_improvement_support"
                ]
            ) >= TOP3_MIN_IMPROVEMENT_SUPPORT
            and float(
                bootstrap[
                    "top_pick_hit_rate_improvement_support"
                ]
            ) >= TOP3_MIN_IMPROVEMENT_SUPPORT
        )

    gate = bool(
        _period_passed(result_2023)
        and _period_passed(result_2024)
    )

    return {
        "status": (
            "research_only_longshot_intrusion_phase7"
        ),
        "hypothesis": (
            "A conditional model trained only on the pre-registered "
            "longshot development regime, with favorite/top-market "
            "comparison features, can identify which unpopular runner "
            "is most likely to intrude into the top three better than "
            "the general Phase 2 Top-3 challenger."
        ),
        "warning": (
            "Historical final win odds define the development-only "
            "longshot proxy and are not proof of deployable pre-race "
            "availability. This phase tests probability/ranking quality "
            "only; it does not generate exotic tickets or expected value."
        ),
        "training": {
            "general_rows": int(
                len(general_train)
            ),
            "specialist_longshot_rows": int(
                len(specialist_train)
            ),
            "general_races": int(
                general_train[
                    "race_id"
                ].nunique()
            ),
            "specialist_longshot_races": int(
                specialist_train[
                    "race_id"
                ].nunique()
            ),
            "iterations": (
                LONGSHOT_INTRUSION_ITERATIONS
            ),
            "depth": (
                LONGSHOT_INTRUSION_DEPTH
            ),
            "learning_rate": (
                LONGSHOT_INTRUSION_LEARNING_RATE
            ),
            "random_seed": (
                LONGSHOT_INTRUSION_RANDOM_SEED
            ),
        },
        "feature_design": {
            "general_feature_count": int(
                len(general_features)
            ),
            "specialist_feature_count": int(
                len(specialist_features)
            ),
            "interaction_sources": list(
                TOP3_INTERACTION_SOURCE_FEATURES
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
                "general Phase 2-style Top-3 challenger "
                "trained on all runners through 2022"
            ),
            "specialist": (
                "same fixed model family trained only on "
                "historical-final-win-odds >= 6.0 runners "
                "through 2022 plus fixed intrusion features"
            ),
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
            "real_ticket_generation": (
                "disabled"
            ),
        },
        "evaluation_2023": result_2023,
        "evaluation_2024": result_2024,
        "development_longshot_intrusion_gate_passed": gate,
    }
