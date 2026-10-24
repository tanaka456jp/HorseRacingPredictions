from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .evaluation import brier_score, binary_log_loss
from .exotic_top3_research import (
    TOP3_BOOTSTRAP_SAMPLES,
    TOP3_BOOTSTRAP_SEED,
    TOP3_LONGSHOT_ODDS_MIN,
    TOP3_MIN_IMPROVEMENT_SUPPORT,
    Top3ProbabilityModel,
    add_top3_race_interaction_features,
    paired_race_bootstrap_binary_quality,
    top3_outcomes,
)
from .feature_window import align_history_to_training_start
from .features import build_pre_race_features
from .market_aware_ranker_v11 import (
    MARKET_CONTEXT_FEATURES,
    add_market_context_features,
)
from .pedigree_features import attach_pedigree_history_features


PHASE12_PEDIGREE_FEATURES = (
    "sire_past_starts",
    "sire_past_win_rate",
    "sire_past_top3_rate",
    "sire_past_avg_finish_percentile",
    "sire_days_since_seen",
    "damsire_past_starts",
    "damsire_past_win_rate",
    "damsire_past_top3_rate",
    "damsire_past_avg_finish_percentile",
    "damsire_days_since_seen",
)


def _safe_float(value) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None


def _quality(
    frame: pd.DataFrame,
    probability: pd.Series,
) -> dict:
    target = top3_outcomes(frame)
    return {
        "rows": int(len(frame)),
        "races": int(frame["race_id"].nunique()),
        "binary_log_loss": _safe_float(
            binary_log_loss(probability, target)
        ),
        "brier": _safe_float(
            brier_score(probability, target)
        ),
        "top3_rate": _safe_float(target.mean()),
        "average_probability": _safe_float(probability.mean()),
    }


def _ranking_evidence(
    frame: pd.DataFrame,
    challenger_probability: pd.Series,
    baseline_probability: pd.Series,
) -> pd.DataFrame:
    mask = pd.to_numeric(
        frame["win_odds"],
        errors="coerce",
    ).ge(TOP3_LONGSHOT_ODDS_MIN)
    work = frame.loc[
        mask,
        ["race_id", "finish_position", "win_odds"],
    ].copy()
    if work.empty:
        raise ValueError("Phase 12 longshot ranking frame is empty")

    work["challenger_probability"] = (
        challenger_probability.loc[work.index].astype(float)
    )
    work["baseline_probability"] = (
        baseline_probability.loc[work.index].astype(float)
    )
    work["target"] = top3_outcomes(
        frame.loc[work.index]
    ).astype(int)

    rows: list[dict] = []
    for race_id, race in work.groupby(
        "race_id",
        sort=False,
    ):
        challenger_order = race.sort_values(
            "challenger_probability",
            ascending=False,
            kind="stable",
        )
        baseline_order = race.sort_values(
            "baseline_probability",
            ascending=False,
            kind="stable",
        )

        def _mrr(values: np.ndarray) -> float:
            positions = np.flatnonzero(values == 1)
            if len(positions) == 0:
                return 0.0
            return 1.0 / float(positions[0] + 1)

        challenger_hits = challenger_order[
            "target"
        ].to_numpy(dtype=int)
        baseline_hits = baseline_order[
            "target"
        ].to_numpy(dtype=int)

        rows.append({
            "race_id": str(race_id),
            "candidate_count": int(len(race)),
            "positive_count": int(race["target"].sum()),
            "challenger_top1_hit": int(challenger_hits[0]),
            "baseline_top1_hit": int(baseline_hits[0]),
            "challenger_mrr": _mrr(challenger_hits),
            "baseline_mrr": _mrr(baseline_hits),
        })

    evidence = pd.DataFrame(rows)
    if evidence.empty:
        raise ValueError("Phase 12 ranking evidence is empty")
    return evidence


def _ranking_summary(evidence: pd.DataFrame) -> dict:
    return {
        "rows": int(evidence["candidate_count"].sum()),
        "races": int(len(evidence)),
        "races_with_positive_longshot": int(
            evidence["positive_count"].gt(0).sum()
        ),
        "top1": {
            "baseline_hit_rate": _safe_float(
                evidence["baseline_top1_hit"].mean()
            ),
            "challenger_hit_rate": _safe_float(
                evidence["challenger_top1_hit"].mean()
            ),
            "hit_rate_delta": _safe_float(
                (
                    evidence["challenger_top1_hit"]
                    - evidence["baseline_top1_hit"]
                ).mean()
            ),
        },
        "mrr": {
            "baseline": _safe_float(
                evidence["baseline_mrr"].mean()
            ),
            "challenger": _safe_float(
                evidence["challenger_mrr"].mean()
            ),
            "delta": _safe_float(
                (
                    evidence["challenger_mrr"]
                    - evidence["baseline_mrr"]
                ).mean()
            ),
        },
    }


def _evaluate_period(
    frame: pd.DataFrame,
    baseline_probability: pd.Series,
    challenger_probability: pd.Series,
) -> dict:
    baseline = _quality(frame, baseline_probability)
    challenger = _quality(frame, challenger_probability)
    bootstrap = paired_race_bootstrap_binary_quality(
        frame,
        challenger_probability,
        baseline_probability,
        samples=TOP3_BOOTSTRAP_SAMPLES,
        seed=TOP3_BOOTSTRAP_SEED,
    )
    ranking = _ranking_summary(
        _ranking_evidence(
            frame,
            challenger_probability,
            baseline_probability,
        )
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
        "longshot_ranking": {
            "definition": (
                "historical final win odds >= 6.0; development-only "
                "candidate proxy, not executable betting odds"
            ),
            **ranking,
        },
    }


def evaluate_pedigree_phase12(
    history: pd.DataFrame,
    pedigree: pd.DataFrame,
    *,
    train_start: str = "2017-01-01",
    train_end: str = "2022-12-31",
    evaluation_2023_start: str = "2023-01-01",
    evaluation_2023_end: str = "2023-12-31",
    evaluation_2024_start: str = "2024-01-01",
    evaluation_2024_end: str = "2024-12-31",
) -> dict:
    """One-shot preregistered Phase 12 pedigree augmentation evaluation."""
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
        raise ValueError("invalid Phase 12 development split")

    if "_jv_blood_registration_number" not in history.columns:
        raise ValueError(
            "Phase 12 requires independently acquired JV history with "
            "_jv_blood_registration_number"
        )

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
    if data["race_date"].gt(v24_end).any():
        raise RuntimeError(
            "Phase 12 history contains post-2024 rows; protected "
            "2025-2026 holdout must remain unread"
        )

    data = data.loc[
        data["finish_position"].notna()
        & data["win_odds"].gt(1.0)
    ].copy()
    if data.empty:
        raise ValueError("Phase 12 development history is empty")

    race_sizes = data.groupby("race_id")["race_id"].transform("size")
    data = data.loc[race_sizes.ge(3)].copy()

    enhanced = build_pre_race_features(
        data,
        experimental_ranker_v10=True,
    )
    baseline_market = add_market_context_features(
        enhanced.frame
    )
    baseline_frame, interaction_features = (
        add_top3_race_interaction_features(
            baseline_market
        )
    )

    pedigree_result = attach_pedigree_history_features(
        enhanced.frame,
        pedigree,
    )
    if tuple(pedigree_result.feature_columns) != PHASE12_PEDIGREE_FEATURES:
        raise RuntimeError(
            "Phase 12 pedigree feature set differs from preregistration"
        )
    challenger_market = add_market_context_features(
        pedigree_result.frame
    )
    challenger_frame, challenger_interactions = (
        add_top3_race_interaction_features(
            challenger_market
        )
    )
    if tuple(challenger_interactions) != tuple(interaction_features):
        raise RuntimeError(
            "Phase 12 changed non-pedigree interaction features"
        )

    baseline_features = (
        tuple(enhanced.feature_columns)
        + MARKET_CONTEXT_FEATURES
        + interaction_features
    )
    challenger_features = (
        baseline_features
        + PHASE12_PEDIGREE_FEATURES
    )
    if any(
        "registration_number" in column
        for column in challenger_features
    ):
        raise RuntimeError(
            "raw pedigree registration identifiers cannot enter Phase 12 model"
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
        raise ValueError("Phase 12 split contains an empty period")

    target = top3_outcomes(baseline_train)
    baseline_model = Top3ProbabilityModel(
        list(baseline_features),
        iterations=300,
        depth=7,
        learning_rate=0.05,
        random_seed=42,
    ).fit(
        baseline_train,
        target,
    )
    challenger_model = Top3ProbabilityModel(
        list(challenger_features),
        iterations=300,
        depth=7,
        learning_rate=0.05,
        random_seed=42,
    ).fit(
        challenger_train,
        target,
    )

    def _score(
        baseline_period: pd.DataFrame,
        challenger_period: pd.DataFrame,
    ) -> dict:
        baseline_probability = baseline_model.predict_probability(
            baseline_period
        )
        challenger_probability = challenger_model.predict_probability(
            challenger_period
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
        bootstrap = result["paired_bootstrap_vs_baseline"]
        return bool(
            float(result["binary_log_loss_delta"]) < 0.0
            and float(result["brier_delta"]) < 0.0
            and float(
                bootstrap["binary_log_loss_improvement_support"]
            ) >= TOP3_MIN_IMPROVEMENT_SUPPORT
            and float(
                bootstrap["brier_improvement_support"]
            ) >= TOP3_MIN_IMPROVEMENT_SUPPORT
        )

    gate = bool(
        _period_passed(result_2023)
        and _period_passed(result_2024)
    )

    return {
        "status": "research_only_exotic_pedigree_phase12",
        "hypothesis": (
            "Strictly past-only sire and damsire performance summaries add "
            "stable lineage signal to the frozen Phase 2-style Top-3 model "
            "without exposing raw pedigree identifiers."
        ),
        "training": {
            "period_start": str(
                baseline_train["race_date"].min().date()
            ),
            "period_end": str(
                baseline_train["race_date"].max().date()
            ),
            "rows": int(len(baseline_train)),
            "races": int(baseline_train["race_id"].nunique()),
            "iterations": 300,
            "depth": 7,
            "learning_rate": 0.05,
            "random_seed": 42,
        },
        "feature_design": {
            "baseline_feature_count": int(len(baseline_features)),
            "challenger_feature_count": int(len(challenger_features)),
            "pedigree_features": list(PHASE12_PEDIGREE_FEATURES),
            "pedigree_matched_rows": int(
                pedigree_result.matched_rows
            ),
            "pedigree_total_rows": int(
                pedigree_result.total_rows
            ),
            "raw_pedigree_ids_as_features": False,
        },
        "research_protocol": {
            "preregistered": True,
            "one_real_evaluation_only": True,
            "baseline": "frozen Phase 2-style Top-3 model",
            "challenger": (
                "same model and hyperparameters plus exactly ten "
                "sire/damsire prior-history features"
            ),
            "bootstrap_samples": TOP3_BOOTSTRAP_SAMPLES,
            "bootstrap_seed": TOP3_BOOTSTRAP_SEED,
            "minimum_improvement_support": (
                TOP3_MIN_IMPROVEMENT_SUPPORT
            ),
            "ranking_metrics_gate": False,
            "final_holdout": "2025-2026 untouched",
            "forward_paper": "unchanged",
            "paid_data": "not_used",
            "real_ticket_generation": "disabled",
        },
        "evaluation_2023": result_2023,
        "evaluation_2024": result_2024,
        "development_pedigree_gate_passed": gate,
    }
