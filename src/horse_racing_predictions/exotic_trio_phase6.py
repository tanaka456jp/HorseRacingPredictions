from __future__ import annotations

from itertools import combinations
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
    exact_three_combination_race_evidence,
    top3_outcomes,
)


DIRECT_TRIO_RANDOM_SEED = 20261006
DIRECT_TRIO_MAX_NEGATIVES_PER_RACE = 31
DIRECT_TRIO_HARD_MARKET_NEGATIVES = 8
DIRECT_TRIO_LONGSHOT_NEGATIVES = 12
DIRECT_TRIO_ITERATIONS = 250

DIRECT_TRIO_MEMBER_FEATURES = (
    "market_implied_probability",
    "market_probability_rank",
    "market_gap_to_favorite",
    "relative_post_position",
    "carried_weight_vs_race_mean",
    "horse_weight_vs_race_mean",
    "horse_recent_top3_rate_5",
    "horse_recent_finish_percentile_mean_5",
    "horse_recent_early_ratio_mean_5",
    "horse_recent_late_ratio_mean_5",
    "jockey_past_win_rate",
    "trainer_past_win_rate",
    "horse_jockey_past_win_rate",
)


def _safe_float(value) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None


def _actual_top3_indices(race: pd.DataFrame) -> tuple[object, object, object] | None:
    finish = pd.to_numeric(
        race["finish_position"],
        errors="coerce",
    )
    members: list[object] = []
    for place in (1, 2, 3):
        matches = race.index[finish.eq(place)].tolist()
        if len(matches) != 1:
            return None
        members.append(matches[0])
    return tuple(members)


def _triple_sort_key(
    race: pd.DataFrame,
    triple: tuple[object, object, object],
) -> tuple[object, object, object]:
    market = pd.to_numeric(
        race.loc[list(triple), "market_implied_probability"],
        errors="coerce",
    ).fillna(-1.0)
    ordered = market.sort_values(
        ascending=False,
        kind="stable",
    ).index.tolist()
    return tuple(ordered)


def _triple_market_product(
    race: pd.DataFrame,
    triple: tuple[object, object, object],
) -> float:
    values = pd.to_numeric(
        race.loc[list(triple), "market_implied_probability"],
        errors="coerce",
    ).fillna(0.0)
    return float(np.prod(values.to_numpy(dtype=float)))


def _triple_contains_longshot(
    race: pd.DataFrame,
    triple: tuple[object, object, object],
) -> bool:
    odds = pd.to_numeric(
        race.loc[list(triple), "win_odds"],
        errors="coerce",
    )
    return bool(odds.ge(TOP3_LONGSHOT_ODDS_MIN).any())


def _select_training_triples(
    race: pd.DataFrame,
    triples: list[tuple[object, object, object]],
    actual: tuple[object, object, object],
    rng: np.random.Generator,
) -> list[tuple[object, object, object]]:
    actual_set = frozenset(actual)
    negatives = [
        triple
        for triple in triples
        if frozenset(triple) != actual_set
    ]
    if len(negatives) <= DIRECT_TRIO_MAX_NEGATIVES_PER_RACE:
        return [actual] + negatives

    hard = sorted(
        negatives,
        key=lambda triple: (
            -_triple_market_product(race, triple),
            tuple(str(index) for index in triple),
        ),
    )[:DIRECT_TRIO_HARD_MARKET_NEGATIVES]
    chosen = list(hard)
    chosen_sets = {frozenset(triple) for triple in chosen}

    longshots = [
        triple
        for triple in negatives
        if frozenset(triple) not in chosen_sets
        and _triple_contains_longshot(race, triple)
    ]
    if longshots:
        take = min(
            DIRECT_TRIO_LONGSHOT_NEGATIVES,
            len(longshots),
        )
        draw = rng.choice(
            len(longshots),
            size=take,
            replace=False,
        )
        for position in np.atleast_1d(draw):
            triple = longshots[int(position)]
            chosen.append(triple)
            chosen_sets.add(frozenset(triple))

    remaining = [
        triple
        for triple in negatives
        if frozenset(triple) not in chosen_sets
    ]
    slots = (
        DIRECT_TRIO_MAX_NEGATIVES_PER_RACE
        - len(chosen)
    )
    if slots > 0 and remaining:
        take = min(slots, len(remaining))
        draw = rng.choice(
            len(remaining),
            size=take,
            replace=False,
        )
        for position in np.atleast_1d(draw):
            chosen.append(remaining[int(position)])

    return [actual] + chosen


def _triple_feature_row(
    race: pd.DataFrame,
    triple: tuple[object, object, object],
    *,
    actual: tuple[object, object, object],
    member_features: tuple[str, ...],
) -> dict:
    ordered = _triple_sort_key(
        race,
        triple,
    )
    members = race.loc[list(ordered)]

    row: dict[str, object] = {
        "race_id": str(race["race_id"].iloc[0]),
        "is_actual_top3_set": int(
            frozenset(triple) == frozenset(actual)
        ),
        "contains_longshot": _triple_contains_longshot(
            race,
            triple,
        ),
    }

    for slot, index in enumerate(ordered, start=1):
        source = race.loc[index]
        for feature in member_features:
            row[f"member{slot}_{feature}"] = source[feature]

    market = pd.to_numeric(
        members["market_implied_probability"],
        errors="coerce",
    ).clip(lower=1e-12)
    market_rank = pd.to_numeric(
        members["market_probability_rank"],
        errors="coerce",
    )
    win_odds = pd.to_numeric(
        members["win_odds"],
        errors="coerce",
    )

    row.update({
        "set_market_probability_sum": float(market.sum()),
        "set_market_log_probability_sum": float(
            np.log(market).sum()
        ),
        "set_market_probability_min": float(market.min()),
        "set_market_probability_max": float(market.max()),
        "set_market_rank_sum": float(market_rank.sum()),
        "set_market_rank_max": float(market_rank.max()),
        "set_win_odds_min": float(win_odds.min()),
        "set_win_odds_max": float(win_odds.max()),
        "set_longshot_count": int(
            win_odds.ge(TOP3_LONGSHOT_ODDS_MIN).sum()
        ),
        "set_contains_market_favorite": int(
            market_rank.eq(1.0).any()
        ),
    })

    aggregate_sources = (
        "horse_recent_top3_rate_5",
        "horse_recent_finish_percentile_mean_5",
        "horse_recent_early_ratio_mean_5",
        "horse_recent_late_ratio_mean_5",
        "jockey_past_win_rate",
        "trainer_past_win_rate",
        "horse_jockey_past_win_rate",
    )
    for source in aggregate_sources:
        if source not in members.columns:
            continue
        values = pd.to_numeric(
            members[source],
            errors="coerce",
        )
        row[f"set_{source}_mean"] = float(
            values.mean()
        ) if values.notna().any() else np.nan
        row[f"set_{source}_std"] = float(
            values.std(ddof=0)
        ) if values.notna().any() else np.nan
        row[f"set_{source}_range"] = float(
            values.max() - values.min()
        ) if values.notna().any() else np.nan

    return row


def build_direct_trio_candidates(
    frame: pd.DataFrame,
    *,
    training: bool,
    random_seed: int = DIRECT_TRIO_RANDOM_SEED,
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    required = {
        "race_id",
        "finish_position",
        "win_odds",
        "market_implied_probability",
        "market_probability_rank",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(
            f"direct trio candidate frame missing columns: {sorted(missing)}"
        )

    member_features = tuple(
        feature
        for feature in DIRECT_TRIO_MEMBER_FEATURES
        if feature in frame.columns
    )
    rng = np.random.default_rng(random_seed)
    rows: list[dict] = []

    for _race_id, race in frame.groupby(
        "race_id",
        sort=False,
    ):
        if len(race) < 3:
            continue
        actual = _actual_top3_indices(race)
        if actual is None:
            continue

        triples = list(combinations(race.index.tolist(), 3))
        selected = (
            _select_training_triples(
                race,
                triples,
                actual,
                rng,
            )
            if training
            else triples
        )
        for triple in selected:
            rows.append(
                _triple_feature_row(
                    race,
                    triple,
                    actual=actual,
                    member_features=member_features,
                )
            )

    candidates = pd.DataFrame(rows)
    if candidates.empty:
        raise ValueError(
            "direct trio candidate generation produced no rows"
        )
    if training:
        positive_per_race = candidates.groupby(
            "race_id"
        )["is_actual_top3_set"].sum()
        if not positive_per_race.eq(1).all():
            raise ValueError(
                "direct trio training requires exactly one positive set per race"
            )

    excluded = {
        "race_id",
        "is_actual_top3_set",
        "contains_longshot",
    }
    feature_columns = tuple(
        column
        for column in candidates.columns
        if column not in excluded
    )
    return candidates, feature_columns


def _direct_realized_evidence(
    candidates: pd.DataFrame,
    probability: pd.Series,
) -> pd.DataFrame:
    if not probability.index.equals(candidates.index):
        raise ValueError(
            "direct trio probability index differs from candidates"
        )
    realized = candidates.loc[
        candidates["is_actual_top3_set"].eq(1)
    ].copy()
    if realized.empty:
        raise ValueError("direct trio realized evidence is empty")
    realized["trio_probability"] = probability.loc[
        realized.index
    ].astype(float).clip(
        lower=1e-300,
        upper=1.0,
    )
    realized["trio_nll"] = -np.log(
        realized["trio_probability"]
    )
    return realized[
        [
            "race_id",
            "contains_longshot",
            "trio_probability",
            "trio_nll",
        ]
    ].reset_index(drop=True)


def _paired_trio_nll_bootstrap(
    direct: pd.DataFrame,
    baseline: pd.DataFrame,
    *,
    samples: int = TOP3_BOOTSTRAP_SAMPLES,
    seed: int = TOP3_BOOTSTRAP_SEED,
) -> dict:
    merged = direct[
        ["race_id", "trio_nll"]
    ].merge(
        baseline[
            ["race_id", "trio_nll"]
        ],
        on="race_id",
        how="inner",
        suffixes=("_direct", "_baseline"),
        validate="one_to_one",
    )
    if merged.empty:
        raise ValueError(
            "direct trio bootstrap has no paired races"
        )

    delta = (
        merged["trio_nll_direct"]
        - merged["trio_nll_baseline"]
    ).to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    count = int(len(delta))
    sampled = np.empty(int(samples), dtype=float)
    for idx in range(int(samples)):
        draw = rng.integers(0, count, size=count)
        sampled[idx] = float(delta[draw].mean())

    return {
        "samples": int(samples),
        "seed": int(seed),
        "races": count,
        "trio_nll_improvement_support": _safe_float(
            np.mean(sampled < 0.0)
        ),
        "trio_nll_delta_ci90": [
            _safe_float(np.quantile(sampled, 0.05)),
            _safe_float(np.quantile(sampled, 0.95)),
        ],
    }


def _compare_direct_to_phase5(
    direct: pd.DataFrame,
    phase5: pd.DataFrame,
) -> dict:
    direct_quality = _safe_float(
        direct["trio_nll"].mean()
    )
    phase5_quality = _safe_float(
        phase5["trio_nll"].mean()
    )
    bootstrap = _paired_trio_nll_bootstrap(
        direct,
        phase5,
    )
    return {
        "races": int(len(direct)),
        "direct_mean_trio_nll": direct_quality,
        "phase5_mean_trio_nll": phase5_quality,
        "trio_nll_delta_vs_phase5": _safe_float(
            float(direct_quality)
            - float(phase5_quality)
        ),
        "paired_bootstrap_vs_phase5": bootstrap,
    }


def evaluate_direct_trio_phase6(
    history: pd.DataFrame,
    *,
    train_start: str = "2017-01-01",
    train_end: str = "2022-12-31",
    evaluation_2023_start: str = "2023-01-01",
    evaluation_2023_end: str = "2023-12-31",
    evaluation_2024_start: str = "2024-01-01",
    evaluation_2024_end: str = "2024-12-31",
) -> dict:
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
        raise ValueError(
            "invalid direct trio development time split"
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
    data = data.loc[
        data["finish_position"].notna()
        & data["win_odds"].gt(1.0)
        & data["race_date"].le(v24_end)
    ].copy()
    if data.empty:
        raise ValueError(
            "direct trio development history is empty"
        )

    race_sizes = data.groupby(
        "race_id"
    )["race_id"].transform("size")
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
    top3_features = (
        tuple(enhanced.feature_columns)
        + MARKET_CONTEXT_FEATURES
        + interaction_features
    )

    dates = pd.to_datetime(
        challenger_frame["race_date"],
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

    train = challenger_frame.loc[
        train_mask
    ].copy()
    v23 = challenger_frame.loc[
        v23_mask
    ].copy()
    v24 = challenger_frame.loc[
        v24_mask
    ].copy()
    if train.empty or v23.empty or v24.empty:
        raise ValueError(
            "direct trio development split contains an empty period"
        )

    frozen_top3_model = Top3ProbabilityModel(
        list(top3_features),
        iterations=300,
    ).fit(
        train,
        top3_outcomes(train),
    )

    training_candidates, direct_features = (
        build_direct_trio_candidates(
            train,
            training=True,
        )
    )
    direct_model = CatBoostRankingProbabilityModel(
        feature_columns=list(direct_features),
        iterations=DIRECT_TRIO_ITERATIONS,
        depth=7,
        learning_rate=0.05,
        random_seed=DIRECT_TRIO_RANDOM_SEED,
        loss_function="YetiRankPairwise",
    ).fit(
        training_candidates,
        target_col="is_actual_top3_set",
        race_col="race_id",
    )

    def _evaluate_period(
        period: pd.DataFrame,
    ) -> dict:
        top3_probability = (
            frozen_top3_model.predict_probability(
                period
            )
        )
        phase5 = exact_three_combination_race_evidence(
            period,
            top3_probability,
        )

        candidates, period_features = (
            build_direct_trio_candidates(
                period,
                training=False,
            )
        )
        if tuple(period_features) != tuple(direct_features):
            raise ValueError(
                "direct trio feature columns changed between train/evaluation"
            )
        direct_probability = (
            direct_model.predict_win_probability(
                candidates,
                race_col="race_id",
            )
        )
        direct = _direct_realized_evidence(
            candidates,
            direct_probability,
        )

        overall = _compare_direct_to_phase5(
            direct,
            phase5,
        )

        longshot_ids = set(
            direct.loc[
                direct["contains_longshot"],
                "race_id",
            ].astype(str)
        )
        direct_longshot = direct.loc[
            direct["race_id"].astype(str).isin(
                longshot_ids
            )
        ].copy()
        phase5_longshot = phase5.loc[
            phase5["race_id"].astype(str).isin(
                longshot_ids
            )
        ].copy()
        if direct_longshot.empty:
            raise ValueError(
                "direct trio evaluation has no longshot-containing races"
            )
        longshot = _compare_direct_to_phase5(
            direct_longshot,
            phase5_longshot,
        )

        return {
            "period_start": str(
                period["race_date"].min().date()
            ),
            "period_end": str(
                period["race_date"].max().date()
            ),
            "candidate_rows": int(len(candidates)),
            "races": int(
                candidates["race_id"].nunique()
            ),
            "overall": overall,
            "longshot_containing": {
                "definition": (
                    "realized top three contains at least one runner "
                    "with historical final win odds >= 6.0; "
                    "development proxy only"
                ),
                **longshot,
            },
        }

    result_2023 = _evaluate_period(v23)
    result_2024 = _evaluate_period(v24)

    def _period_passed(result: dict) -> bool:
        for segment_name in (
            "overall",
            "longshot_containing",
        ):
            segment = result[segment_name]
            if not (
                float(
                    segment["trio_nll_delta_vs_phase5"]
                ) < 0.0
                and float(
                    segment[
                        "paired_bootstrap_vs_phase5"
                    ][
                        "trio_nll_improvement_support"
                    ]
                ) >= TOP3_MIN_IMPROVEMENT_SUPPORT
            ):
                return False
        return True

    gate = bool(
        _period_passed(result_2023)
        and _period_passed(result_2024)
    )

    return {
        "status": "research_only_direct_trio_phase6",
        "hypothesis": (
            "A race-group ranker trained directly on three-runner set "
            "features can assign more probability to the realized top-three "
            "set than the failed marginal-to-set Phase 5 transform, "
            "especially when the set contains a longshot proxy."
        ),
        "warning": (
            "Historical final win odds remain development-only market "
            "inputs. Phase 6 evaluates trio set probability quality only, "
            "not betting expected value. No timestamped pre-race exotic "
            "combination odds are available in the current free pipeline."
        ),
        "training": {
            "period_start": str(
                train["race_date"].min().date()
            ),
            "period_end": str(
                train["race_date"].max().date()
            ),
            "races": int(
                train["race_id"].nunique()
            ),
            "candidate_rows": int(
                len(training_candidates)
            ),
            "direct_feature_count": int(
                len(direct_features)
            ),
            "direct_iterations": (
                DIRECT_TRIO_ITERATIONS
            ),
            "max_negatives_per_race": (
                DIRECT_TRIO_MAX_NEGATIVES_PER_RACE
            ),
            "hard_market_negatives": (
                DIRECT_TRIO_HARD_MARKET_NEGATIVES
            ),
            "longshot_negatives": (
                DIRECT_TRIO_LONGSHOT_NEGATIVES
            ),
            "random_seed": (
                DIRECT_TRIO_RANDOM_SEED
            ),
        },
        "research_protocol": {
            "baseline": (
                "Phase 5 exact-three set probability from frozen "
                "Phase 2 Top-3 challenger"
            ),
            "development_periods": [
                "training_through_2022",
                "2023_development_reused",
                "2024_development_reused",
            ],
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
        "development_direct_trio_gate_passed": gate,
    }
