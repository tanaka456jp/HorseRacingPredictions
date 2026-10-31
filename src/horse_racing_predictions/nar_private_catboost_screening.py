"""NAR private, odds-free CatBoost screening with a sealed 2023–24 holdout.

Only prior-day horse-form measurements feed the model; all contemporaneous
odds, popularity, finishing time, jockey, weather, current final result and
2023–24 labels are excluded. The *model screening* uses 2017–21 fitting and
2022 tuning, not historical official returns or any future holdout.

This module does no I/O, download, publication, betting, model saving or
GitHub upload. It is a research screener, NOT a verified positive-EV model.
The input must come from independently permitted, complete offline sources.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from math import isfinite
from typing import Any

import numpy as np
import pandas as pd

from .modeling import CatBoostProbabilityModel
from .nar_official_zip_probe import UnsafeNarSource
from .nar_prior_day_features import NarAsOfResearchBatch, NarResearchTarget

_FEATURES = (
    "past_starts",
    "past_win_rate",
    "past_top3_rate",
    "past_mean_finish",
    "days_since_last_start",
)
_TRAIN_END = date(2021, 12, 31)
_TUNE_START = date(2022, 1, 1)
_TUNE_END = date(2022, 12, 31)
_SEALED_FROM = date(2023, 1, 1)
_PROTECTED_FROM = date(2025, 1, 1)


@dataclass(frozen=True)
class NarCatBoostScreeningMetrics:
    status: str
    training_races: int
    tuning_races: int
    sealed_races_unscored: int
    training_runners: int
    tuning_runners: int
    winner_top1_hit_rate_2022: float
    win_rank_top3_overlap_2022: float
    independent_outsider_podium_hit_rate_2022: float
    independent_models_fitted: bool
    used_market_or_popularity: bool = False
    sealed_holdout_labels_used: bool = False
    official_returns_evaluated: bool = False
    real_positive_expected_value_proven: bool = False
    public_distribution_authorized: bool = False


@dataclass
class NarCatBoostScreeningCandidate:
    winner: CatBoostProbabilityModel = field(repr=False)
    outsider: CatBoostProbabilityModel = field(repr=False)
    metrics: NarCatBoostScreeningMetrics
    feature_names: tuple[str, ...] = _FEATURES


def _race_id(row: NarResearchTarget) -> str:
    track, ymd, number = row.race_key
    return f"NAR:{ymd}:{track}:{number:02d}"


def _project_only_fit_and_tune(
    batch: NarAsOfResearchBatch,
) -> tuple[pd.DataFrame, int]:
    """No finish label is read for 2023–24; no future rows are materialized.

    For pre-2023 rows, final results remain train/tuning labels in a
    separate column; all 2023–24 rows contribute to counts *only*.
    """
    if (not isinstance(batch, NarAsOfResearchBatch)
            or batch.target_result_entered_features
            or batch.popularity_or_odds_used
            or not batch.features_are_prior_day_only
            or not batch.return_data
            or len(batch.return_data) != batch.target_runner_rows):
        raise UnsafeNarSource("NAR_SCREENING_SOURCE_NOT_ASOF_VERIFIED")

    records: list[dict[str, Any]] = []
    sealed_race_ids: set[str] = set()
    seen: set[tuple[str, int]] = set()
    for target in batch.return_data:
        if not isinstance(target, NarResearchTarget):
            raise UnsafeNarSource("NAR_SCREENING_TARGET_INVALID")
        try:
            race_day = date.fromisoformat(target.race_day)
        except ValueError:
            raise UnsafeNarSource("NAR_SCREENING_TARGET_DAY_INVALID") from None
        if race_day < date(2017, 1, 1) or race_day >= _PROTECTED_FROM:
            raise UnsafeNarSource("NAR_SCREENING_PROTECTED_OR_UNEXPECTED_PERIOD")
        rid = _race_id(target)
        pair = (rid, target.horse_number)
        if pair in seen:
            raise UnsafeNarSource("NAR_SCREENING_DUPLICATE_RUNNER")
        seen.add(pair)
        if race_day >= _SEALED_FROM:
            # This intentionally does NOT access target.final_finish_label.
            sealed_race_ids.add(rid)
            continue
        asof = target.asof
        if (asof.prior_starts < 0 or asof.prior_wins < 0
                or asof.prior_top3 < asof.prior_wins
                or asof.prior_top3 > asof.prior_starts
                or not 0 <= asof.prior_win_rate <= 1
                or not 0 <= asof.prior_top3_rate <= 1):
            raise UnsafeNarSource("NAR_SCREENING_ASOF_FEATURE_INVALID")
        if not isinstance(target.final_finish_label, int) or not 1 <= target.final_finish_label <= 18:
            raise UnsafeNarSource("NAR_SCREENING_LABEL_INVALID")
        records.append({
            "race_id": rid,
            "race_day": race_day,
            "horse_number": target.horse_number,
            "past_starts": asof.prior_starts,
            "past_win_rate": asof.prior_win_rate,
            "past_top3_rate": asof.prior_top3_rate,
            "past_mean_finish": (
                asof.prior_mean_finish if asof.prior_mean_finish is not None
                else float("nan")
            ),
            "days_since_last_start": (
                asof.days_since_prior_start
                if asof.days_since_prior_start is not None else float("nan")
            ),
            "__finish_label": target.final_finish_label,
        })

    if not records:
        raise UnsafeNarSource("NAR_SCREENING_NO_FIT_OR_TUNE_DATA")
    df = pd.DataFrame(records)
    return df, len(sealed_race_ids)


def _check_races(frame: pd.DataFrame, minimum: int) -> int:
    if frame.empty:
        raise UnsafeNarSource("NAR_SCREENING_FOLD_EMPTY")
    races = 0
    for rid, group in frame.groupby("race_id", sort=False):
        finish = group["__finish_label"].tolist()
        n = len(finish)
        if (not 5 <= n <= 18 or set(finish) != set(range(1, n + 1))
                or group["horse_number"].nunique() != n
                or group["race_day"].nunique() != 1):
            raise UnsafeNarSource("NAR_SCREENING_INCOMPLETE_RACE")
        races += 1
    if races < minimum:
        raise UnsafeNarSource("NAR_SCREENING_NOT_ENOUGH_RACES")
    return races


def fit_nar_private_catboost_screening(
    batch: NarAsOfResearchBatch, *, iterations: int = 40,
) -> NarCatBoostScreeningCandidate:
    """Fit independent winner and top-three learners on *past-only* features.

    Requires at least 5 independent fitting races and 3 tuning races.
    The 2023–24 holdout is counted but neither fitted, scored nor used to
    choose features or threshold. No value should be construed as ROI.
    """
    if type(iterations) is not int or not 30 <= iterations <= 600:
        raise UnsafeNarSource("NAR_SCREENING_ITERATIONS_INVALID")
    frame, sealed = _project_only_fit_and_tune(batch)
    fit = frame.loc[frame.race_day.le(_TRAIN_END)].copy()
    tune = frame.loc[frame.race_day.between(_TUNE_START, _TUNE_END)].copy()
    nr_fit = _check_races(fit, 5)
    nr_tune = _check_races(tune, 3)
    if set(fit["race_id"]) & set(tune["race_id"]):
        raise UnsafeNarSource("NAR_SCREENING_FOLDS_OVERLAP")

    fit["__winner_train_label"] = fit["__finish_label"].eq(1).astype(int)
    fit["__outsider_train_label"] = fit["__finish_label"].le(3).astype(int)

    winner = CatBoostProbabilityModel(
        feature_columns=list(_FEATURES), iterations=iterations,
    )
    outsider = CatBoostProbabilityModel(
        feature_columns=list(_FEATURES), iterations=iterations,
    )
    winner.fit(fit, target_col="__winner_train_label")
    outsider.fit(fit, target_col="__outsider_train_label")
    if (winner.model is None or outsider.model is None
            or winner.model is outsider.model):
        raise UnsafeNarSource("NAR_SCREENING_INDEPENDENT_MODELS_REQUIRED")

    # The prediction frames contain no target labels.
    inference = tune[["race_id", "horse_number", *_FEATURES]].copy()
    win_scores = winner.predict_win_probability(inference, race_col="race_id")
    outsider_scores = outsider.predict_win_probability(inference, race_col="race_id")
    if (not win_scores.index.equals(inference.index)
            or not outsider_scores.index.equals(inference.index)
            or not np.isfinite(win_scores.to_numpy(dtype=float)).all()
            or not np.isfinite(outsider_scores.to_numpy(dtype=float)).all()):
        raise UnsafeNarSource("NAR_SCREENING_INVALID_PREDICTIONS")
    for scores in (win_scores, outsider_scores):
        if (scores.le(0).any()
                or not np.allclose(scores.groupby(inference.race_id).sum().to_numpy(), 1.0)):
            raise UnsafeNarSource("NAR_SCREENING_UNNORMALIZED_PREDICTIONS")

    rated = inference[["race_id", "horse_number"]].copy()
    rated["win_score"] = win_scores
    rated["outsider_score"] = outsider_scores
    # Results are looked up ONLY after the fitted model has produced scores
    # for all tuning runners. Neither choice is based on the outcome labels.
    true_ranks = tune.set_index(["race_id", "horse_number"])["__finish_label"]
    n_winner = n_overlap = n_outsider = 0
    for rid, race in rated.groupby("race_id", sort=False):
        order = race.sort_values(
            ["win_score", "horse_number"], ascending=[False, True],
            kind="stable",
        )
        top3 = order.horse_number.head(3).tolist()
        predicted_winner = top3[0]
        rank_by_horse = true_ranks.loc[rid]
        n_winner += int(rank_by_horse.loc[predicted_winner] == 1)
        n_overlap += sum(int(rank_by_horse.loc[n] <= 3) for n in top3)
        excluded = race.loc[~race.horse_number.isin(top3)]
        outsider_pick = excluded.sort_values(
            ["outsider_score", "horse_number"], ascending=[False, True],
            kind="stable",
        ).horse_number.iloc[0]
        n_outsider += int(rank_by_horse.loc[outsider_pick] <= 3)

    metrics = NarCatBoostScreeningMetrics(
        status="NAR_2022_MODEL_SELECTION_ONLY_SEALED_2023_2024",
        training_races=nr_fit, tuning_races=nr_tune,
        sealed_races_unscored=sealed,
        training_runners=len(fit), tuning_runners=len(tune),
        winner_top1_hit_rate_2022=n_winner / nr_tune,
        win_rank_top3_overlap_2022=n_overlap / (3 * nr_tune),
        independent_outsider_podium_hit_rate_2022=n_outsider / nr_tune,
        independent_models_fitted=True,
    )
    if not all(isfinite(v) for v in (
        metrics.winner_top1_hit_rate_2022,
        metrics.win_rank_top3_overlap_2022,
        metrics.independent_outsider_podium_hit_rate_2022,
    )):
        raise UnsafeNarSource("NAR_SCREENING_NONFINITE_METRIC")
    return NarCatBoostScreeningCandidate(winner, outsider, metrics)
