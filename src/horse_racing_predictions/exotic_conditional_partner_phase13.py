from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .exotic_top3_research import (
    TOP3_BOOTSTRAP_SAMPLES,
    TOP3_BOOTSTRAP_SEED,
    TOP3_LONGSHOT_ODDS_MIN,
    TOP3_MIN_IMPROVEMENT_SUPPORT,
    Top3ProbabilityModel,
    add_top3_race_interaction_features,
    top3_outcomes,
)
from .feature_window import align_history_to_training_start
from .features import build_pre_race_features
from .market_aware_ranker_v11 import (
    MARKET_CONTEXT_FEATURES,
    add_market_context_features,
)
from .modeling import CatBoostRankingProbabilityModel


PHASE13_OOF_YEARS = (2018, 2019, 2020, 2021, 2022)
PHASE13_ITERATIONS = 300
PHASE13_DEPTH = 7
PHASE13_LEARNING_RATE = 0.05
PHASE13_RANDOM_SEED = 42

PHASE13_RELATIVE_SOURCES = (
    "horse_recent_top3_rate_5",
    "horse_recent_finish_percentile_mean_5",
    "horse_recent_early_ratio_mean_5",
    "horse_recent_late_ratio_mean_5",
    "jockey_past_win_rate",
    "jockey_course_past_win_rate",
    "horse_jockey_past_win_rate",
    "trainer_past_win_rate",
)

PHASE13_PAIR_CONTEXT_FEATURES = (
    "partner_general_probability",
    "anchor_general_probability",
    "partner_vs_anchor_general_probability",
    "partner_market_implied_probability",
    "anchor_market_implied_probability",
    "partner_vs_anchor_market_probability",
    "partner_market_rank_minus_anchor",
) + tuple(
    f"partner_{source}_minus_anchor"
    for source in PHASE13_RELATIVE_SOURCES
)


def _safe_float(value) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None


def _validate_probability_index(
    frame: pd.DataFrame,
    probability: pd.Series,
) -> None:
    if not probability.index.equals(frame.index):
        raise ValueError(
            "Phase 13 general probability index differs from frame"
        )


def _select_longshot_anchor(
    race: pd.DataFrame,
    probability: pd.Series,
) -> object | None:
    odds = pd.to_numeric(
        race["win_odds"],
        errors="coerce",
    )
    candidates = race.loc[
        odds.ge(TOP3_LONGSHOT_ODDS_MIN)
    ]
    if candidates.empty:
        return None

    score = probability.loc[candidates.index].astype(float)
    maximum = float(score.max())
    # Stable first maximum keeps nomination deterministic.
    return score.index[
        np.flatnonzero(
            np.isclose(
                score.to_numpy(dtype=float),
                maximum,
                rtol=0.0,
                atol=0.0,
            )
        )[0]
    ]


def build_conditional_partner_frame(
    frame: pd.DataFrame,
    general_probability: pd.Series,
    *,
    base_feature_columns: tuple[str, ...],
) -> tuple[pd.DataFrame, tuple[str, ...], dict]:
    """Create pair-ranking rows only for races where the nominated anchor hit Top 3.

    Outcome data controls the conditional research sample and target only. It is
    never added to the model feature set.
    """
    required = {
        "race_id",
        "finish_position",
        "win_odds",
        "market_implied_probability",
        "market_probability_rank",
        *PHASE13_RELATIVE_SOURCES,
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(
            f"Phase 13 frame missing required columns: {sorted(missing)}"
        )
    _validate_probability_index(
        frame,
        general_probability,
    )

    forbidden = {
        "finish_position",
        "win_odds",
        "_jv_blood_registration_number",
        "blood_registration_number",
        "sire_breeding_registration_number",
        "dam_breeding_registration_number",
        "damsire_breeding_registration_number",
    }
    leaked = forbidden.intersection(base_feature_columns)
    if leaked:
        raise ValueError(
            "Phase 13 base features contain forbidden outcome/ID columns: "
            f"{sorted(leaked)}"
        )

    rows: list[dict] = []
    races_with_candidate = 0
    anchor_top3_count = 0
    conditional_races = 0

    for race_id, race in frame.groupby(
        "race_id",
        sort=False,
    ):
        anchor_index = _select_longshot_anchor(
            race,
            general_probability,
        )
        if anchor_index is None:
            continue
        races_with_candidate += 1

        finish = pd.to_numeric(
            race["finish_position"],
            errors="coerce",
        )
        top3_mask = finish.le(3)
        anchor_top3 = bool(top3_mask.loc[anchor_index])
        if anchor_top3:
            anchor_top3_count += 1

        # Exact partner-pair evaluation requires exactly two other positives.
        if not anchor_top3 or int(top3_mask.sum()) != 3:
            continue

        conditional_races += 1
        anchor = race.loc[anchor_index]
        anchor_probability = float(
            general_probability.loc[anchor_index]
        )
        anchor_market = float(
            pd.to_numeric(
                pd.Series(
                    [anchor["market_implied_probability"]]
                ),
                errors="raise",
            ).iloc[0]
        )
        anchor_rank = float(
            pd.to_numeric(
                pd.Series(
                    [anchor["market_probability_rank"]]
                ),
                errors="raise",
            ).iloc[0]
        )

        for candidate_index, candidate in race.iterrows():
            if candidate_index == anchor_index:
                continue

            row = candidate.to_dict()
            candidate_probability = float(
                general_probability.loc[candidate_index]
            )
            candidate_market = float(
                pd.to_numeric(
                    pd.Series(
                        [candidate["market_implied_probability"]]
                    ),
                    errors="raise",
                ).iloc[0]
            )
            candidate_rank = float(
                pd.to_numeric(
                    pd.Series(
                        [candidate["market_probability_rank"]]
                    ),
                    errors="raise",
                ).iloc[0]
            )

            row["_pair_group_id"] = str(race_id)
            row["_partner_source_index"] = str(candidate_index)
            row["is_partner_top3"] = int(
                bool(top3_mask.loc[candidate_index])
            )
            row["partner_general_probability"] = candidate_probability
            row["anchor_general_probability"] = anchor_probability
            row["partner_vs_anchor_general_probability"] = (
                candidate_probability - anchor_probability
            )
            row["partner_market_implied_probability"] = candidate_market
            row["anchor_market_implied_probability"] = anchor_market
            row["partner_vs_anchor_market_probability"] = (
                candidate_market - anchor_market
            )
            row["partner_market_rank_minus_anchor"] = (
                candidate_rank - anchor_rank
            )

            for source in PHASE13_RELATIVE_SOURCES:
                candidate_value = pd.to_numeric(
                    pd.Series([candidate[source]]),
                    errors="coerce",
                ).iloc[0]
                anchor_value = pd.to_numeric(
                    pd.Series([anchor[source]]),
                    errors="coerce",
                ).iloc[0]
                row[
                    f"partner_{source}_minus_anchor"
                ] = (
                    float(candidate_value)
                    - float(anchor_value)
                    if pd.notna(candidate_value)
                    and pd.notna(anchor_value)
                    else np.nan
                )

            rows.append(row)

    pair_features = (
        tuple(base_feature_columns)
        + PHASE13_PAIR_CONTEXT_FEATURES
    )
    if len(pair_features) != len(set(pair_features)):
        raise ValueError(
            "Phase 13 pair feature list contains duplicates"
        )
    if any(
        column in forbidden
        or "registration_number" in column
        for column in pair_features
    ):
        raise ValueError(
            "Phase 13 pair features expose forbidden outcomes or IDs"
        )

    pairs = pd.DataFrame(rows)
    metadata = {
        "races_with_longshot_anchor_candidate": int(
            races_with_candidate
        ),
        "nominated_anchor_top3_count": int(
            anchor_top3_count
        ),
        "nominated_anchor_top3_hit_rate": (
            _safe_float(
                anchor_top3_count / races_with_candidate
            )
            if races_with_candidate
            else None
        ),
        "conditional_partner_races": int(
            conditional_races
        ),
    }
    return pairs, pair_features, metadata


def partner_selection_evidence(
    pairs: pd.DataFrame,
    challenger_score: pd.Series,
) -> pd.DataFrame:
    if pairs.empty:
        raise ValueError(
            "Phase 13 conditional partner frame is empty"
        )
    if not challenger_score.index.equals(pairs.index):
        raise ValueError(
            "Phase 13 challenger score index differs from pair frame"
        )

    work = pairs[
        [
            "_pair_group_id",
            "is_partner_top3",
            "partner_general_probability",
        ]
    ].copy()
    work["challenger_score"] = challenger_score.astype(float)

    rows: list[dict] = []
    for group_id, group in work.groupby(
        "_pair_group_id",
        sort=False,
    ):
        if len(group) < 2:
            continue
        if int(group["is_partner_top3"].sum()) != 2:
            raise ValueError(
                "Phase 13 conditional race must contain exactly two partners"
            )

        baseline_top2 = group.sort_values(
            "partner_general_probability",
            ascending=False,
            kind="stable",
        ).head(2)
        challenger_top2 = group.sort_values(
            "challenger_score",
            ascending=False,
            kind="stable",
        ).head(2)

        baseline_hits = int(
            baseline_top2["is_partner_top3"].sum()
        )
        challenger_hits = int(
            challenger_top2["is_partner_top3"].sum()
        )

        rows.append({
            "race_id": str(group_id),
            "baseline_exact_pair_hit": int(
                baseline_hits == 2
            ),
            "challenger_exact_pair_hit": int(
                challenger_hits == 2
            ),
            "baseline_recall_at_2": (
                baseline_hits / 2.0
            ),
            "challenger_recall_at_2": (
                challenger_hits / 2.0
            ),
        })

    evidence = pd.DataFrame(rows)
    if evidence.empty:
        raise ValueError(
            "Phase 13 partner selection evidence is empty"
        )
    return evidence


def paired_race_bootstrap_partner_selection(
    evidence: pd.DataFrame,
    *,
    samples: int = TOP3_BOOTSTRAP_SAMPLES,
    seed: int = TOP3_BOOTSTRAP_SEED,
) -> dict:
    if evidence.empty:
        raise ValueError(
            "Phase 13 partner bootstrap evidence is empty"
        )
    if samples < 1:
        raise ValueError("bootstrap samples must be positive")

    exact_delta = (
        evidence["challenger_exact_pair_hit"]
        - evidence["baseline_exact_pair_hit"]
    ).to_numpy(dtype=float)
    recall_delta = (
        evidence["challenger_recall_at_2"]
        - evidence["baseline_recall_at_2"]
    ).to_numpy(dtype=float)

    race_count = int(len(evidence))
    rng = np.random.default_rng(seed)
    sampled_exact = np.empty(samples, dtype=float)
    sampled_recall = np.empty(samples, dtype=float)

    for idx in range(samples):
        draw = rng.integers(
            0,
            race_count,
            size=race_count,
        )
        sampled_exact[idx] = float(
            exact_delta[draw].mean()
        )
        sampled_recall[idx] = float(
            recall_delta[draw].mean()
        )

    return {
        "samples": int(samples),
        "seed": int(seed),
        "races": race_count,
        "exact_pair_hit_improvement_support": _safe_float(
            np.mean(sampled_exact > 0.0)
        ),
        "recall_at_2_improvement_support": _safe_float(
            np.mean(sampled_recall > 0.0)
        ),
        "exact_pair_hit_delta_ci90": [
            _safe_float(
                np.quantile(sampled_exact, 0.05)
            ),
            _safe_float(
                np.quantile(sampled_exact, 0.95)
            ),
        ],
        "recall_at_2_delta_ci90": [
            _safe_float(
                np.quantile(sampled_recall, 0.05)
            ),
            _safe_float(
                np.quantile(sampled_recall, 0.95)
            ),
        ],
    }


def _partner_quality(
    evidence: pd.DataFrame,
) -> dict:
    baseline_exact = _safe_float(
        evidence["baseline_exact_pair_hit"].mean()
    )
    challenger_exact = _safe_float(
        evidence["challenger_exact_pair_hit"].mean()
    )
    baseline_recall = _safe_float(
        evidence["baseline_recall_at_2"].mean()
    )
    challenger_recall = _safe_float(
        evidence["challenger_recall_at_2"].mean()
    )
    return {
        "races": int(len(evidence)),
        "baseline_exact_partner_pair_hit_rate": baseline_exact,
        "challenger_exact_partner_pair_hit_rate": challenger_exact,
        "exact_partner_pair_hit_rate_delta": _safe_float(
            float(challenger_exact) - float(baseline_exact)
        ),
        "baseline_partner_recall_at_2": baseline_recall,
        "challenger_partner_recall_at_2": challenger_recall,
        "partner_recall_at_2_delta": _safe_float(
            float(challenger_recall) - float(baseline_recall)
        ),
    }


def _build_oof_partner_training(
    general_frame: pd.DataFrame,
    general_features: tuple[str, ...],
) -> tuple[
    pd.DataFrame,
    tuple[str, ...],
    list[dict],
]:
    dates = pd.to_datetime(
        general_frame["race_date"],
        errors="raise",
    )
    pieces: list[pd.DataFrame] = []
    folds: list[dict] = []
    pair_features: tuple[str, ...] | None = None

    for year in PHASE13_OOF_YEARS:
        start = pd.Timestamp(
            f"{year}-01-01"
        )
        end = pd.Timestamp(
            f"{year}-12-31"
        )
        train = general_frame.loc[
            dates.lt(start)
        ].copy()
        validation = general_frame.loc[
            dates.between(
                start,
                end,
                inclusive="both",
            )
        ].copy()
        if train.empty or validation.empty:
            raise ValueError(
                f"Phase 13 OOF fold {year} is empty"
            )

        model = Top3ProbabilityModel(
            list(general_features),
            iterations=300,
            depth=7,
            learning_rate=0.05,
            random_seed=42,
        ).fit(
            train,
            top3_outcomes(train),
        )
        probability = model.predict_probability(
            validation
        )
        pairs, fold_features, metadata = (
            build_conditional_partner_frame(
                validation,
                probability,
                base_feature_columns=general_features,
            )
        )
        if pairs.empty:
            raise ValueError(
                f"Phase 13 OOF fold {year} has no conditional partner races"
            )

        if pair_features is None:
            pair_features = fold_features
        elif pair_features != fold_features:
            raise ValueError(
                "Phase 13 OOF pair feature columns changed between folds"
            )

        pieces.append(pairs)
        folds.append({
            "year": int(year),
            "train_rows": int(len(train)),
            "train_races": int(
                train["race_id"].nunique()
            ),
            "validation_rows": int(
                len(validation)
            ),
            "validation_races": int(
                validation["race_id"].nunique()
            ),
            **metadata,
            "partner_rows": int(len(pairs)),
        })

    if pair_features is None:
        raise ValueError(
            "Phase 13 produced no OOF pair feature columns"
        )
    training = pd.concat(
        pieces,
        axis=0,
        ignore_index=True,
    )
    return training, pair_features, folds


def _evaluate_period(
    frame: pd.DataFrame,
    general_probability: pd.Series,
    partner_model: CatBoostRankingProbabilityModel,
    general_features: tuple[str, ...],
) -> dict:
    pairs, pair_features, metadata = (
        build_conditional_partner_frame(
            frame,
            general_probability,
            base_feature_columns=general_features,
        )
    )
    if pairs.empty:
        raise ValueError(
            "Phase 13 evaluation has no conditional partner races"
        )
    if tuple(partner_model.feature_columns) != tuple(pair_features):
        raise ValueError(
            "Phase 13 evaluation pair features differ from training"
        )

    challenger_score = (
        partner_model.predict_win_probability(
            pairs,
            race_col="_pair_group_id",
        )
    )
    evidence = partner_selection_evidence(
        pairs,
        challenger_score,
    )
    quality = _partner_quality(evidence)
    bootstrap = paired_race_bootstrap_partner_selection(
        evidence,
    )
    return {
        "period_start": str(
            frame["race_date"].min().date()
        ),
        "period_end": str(
            frame["race_date"].max().date()
        ),
        **metadata,
        **quality,
        "paired_bootstrap_vs_baseline": bootstrap,
    }


def evaluate_conditional_partner_phase13(
    history: pd.DataFrame,
    *,
    train_start: str = "2017-01-01",
    train_end: str = "2022-12-31",
    evaluation_2023_start: str = "2023-01-01",
    evaluation_2023_end: str = "2023-12-31",
    evaluation_2024_start: str = "2024-01-01",
    evaluation_2024_end: str = "2024-12-31",
) -> dict:
    """Evaluate preregistered conditional two-partner selection."""
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
            "invalid Phase 13 development split"
        )

    raw_dates = pd.to_datetime(
        history["race_date"],
        errors="raise",
    )
    if raw_dates.gt(v24_end).any():
        raise RuntimeError(
            "Phase 13 history contains post-2024 rows; protected "
            "2025-2026 holdout must remain unread"
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
    ].copy()
    if data.empty:
        raise ValueError(
            "Phase 13 development history is empty"
        )

    race_sizes = data.groupby(
        "race_id"
    )["race_id"].transform("size")
    data = data.loc[
        race_sizes.ge(4)
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
    general_features = (
        tuple(enhanced.feature_columns)
        + MARKET_CONTEXT_FEATURES
        + interaction_features
    )

    (
        partner_training,
        pair_features,
        oof_folds,
    ) = _build_oof_partner_training(
        general_frame,
        general_features,
    )
    partner_model = CatBoostRankingProbabilityModel(
        feature_columns=list(pair_features),
        iterations=PHASE13_ITERATIONS,
        depth=PHASE13_DEPTH,
        learning_rate=PHASE13_LEARNING_RATE,
        random_seed=PHASE13_RANDOM_SEED,
        loss_function="YetiRankPairwise",
    ).fit(
        partner_training,
        target_col="is_partner_top3",
        race_col="_pair_group_id",
    )

    dates = pd.to_datetime(
        general_frame["race_date"],
        errors="raise",
    )
    final_train = general_frame.loc[
        dates.le(train_end_ts)
    ].copy()
    v23 = general_frame.loc[
        dates.between(
            v23_start,
            v23_end,
            inclusive="both",
        )
    ].copy()
    v24 = general_frame.loc[
        dates.between(
            v24_start,
            v24_end,
            inclusive="both",
        )
    ].copy()
    if (
        final_train.empty
        or v23.empty
        or v24.empty
    ):
        raise ValueError(
            "Phase 13 final split contains an empty period"
        )

    general_model = Top3ProbabilityModel(
        list(general_features),
        iterations=300,
        depth=7,
        learning_rate=0.05,
        random_seed=42,
    ).fit(
        final_train,
        top3_outcomes(final_train),
    )

    result_2023 = _evaluate_period(
        v23,
        general_model.predict_probability(v23),
        partner_model,
        general_features,
    )
    result_2024 = _evaluate_period(
        v24,
        general_model.predict_probability(v24),
        partner_model,
        general_features,
    )

    def _period_passed(result: dict) -> bool:
        bootstrap = result[
            "paired_bootstrap_vs_baseline"
        ]
        return bool(
            float(
                result[
                    "exact_partner_pair_hit_rate_delta"
                ]
            ) > 0.0
            and float(
                result[
                    "partner_recall_at_2_delta"
                ]
            ) > 0.0
            and float(
                bootstrap[
                    "exact_pair_hit_improvement_support"
                ]
            ) >= TOP3_MIN_IMPROVEMENT_SUPPORT
            and float(
                bootstrap[
                    "recall_at_2_improvement_support"
                ]
            ) >= TOP3_MIN_IMPROVEMENT_SUPPORT
        )

    gate = bool(
        _period_passed(result_2023)
        and _period_passed(result_2024)
    )

    return {
        "status": (
            "research_only_conditional_partner_phase13"
        ),
        "hypothesis": (
            "Conditional two-partner ranking around a pre-race nominated "
            "longshot anchor can improve who accompanies that anchor in "
            "the Top 3 without constructing a joint ticket probability "
            "from independent horse marginals."
        ),
        "warning": (
            "Phase 13 is conditional partner-selection research only. "
            "Anchor nomination still uses historical final win odds >= 6.0 "
            "as a development proxy, and no executable trio/trifecta EV "
            "or real betting ticket is produced."
        ),
        "training": {
            "oof_years": list(PHASE13_OOF_YEARS),
            "partner_rows": int(
                len(partner_training)
            ),
            "partner_races": int(
                partner_training[
                    "_pair_group_id"
                ].nunique()
            ),
            "iterations": PHASE13_ITERATIONS,
            "depth": PHASE13_DEPTH,
            "learning_rate": PHASE13_LEARNING_RATE,
            "random_seed": PHASE13_RANDOM_SEED,
            "oof_folds": oof_folds,
        },
        "feature_design": {
            "general_feature_count": int(
                len(general_features)
            ),
            "partner_feature_count": int(
                len(pair_features)
            ),
            "pair_context_features": list(
                PHASE13_PAIR_CONTEXT_FEATURES
            ),
            "raw_identifiers_as_features": False,
            "post_race_values_as_features": False,
        },
        "research_protocol": {
            "preregistered": True,
            "one_real_evaluation_only": True,
            "anchor_rule": (
                "highest frozen general Top-3 probability among "
                "historical-final-win-odds >= 6.0 candidates"
            ),
            "training_anchor_predictions": (
                "annual out-of-fold 2018-2022"
            ),
            "baseline_partner_selection": (
                "two highest general Top-3 probabilities among non-anchor runners"
            ),
            "challenger_partner_selection": (
                "two highest Phase 13 YetiRankPairwise scores"
            ),
            "bootstrap_samples": TOP3_BOOTSTRAP_SAMPLES,
            "bootstrap_seed": TOP3_BOOTSTRAP_SEED,
            "minimum_improvement_support": (
                TOP3_MIN_IMPROVEMENT_SUPPORT
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
        "development_conditional_partner_gate_passed": gate,
    }
