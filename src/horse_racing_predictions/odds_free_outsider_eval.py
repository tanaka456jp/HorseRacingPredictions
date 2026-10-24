"""Evaluate an independently fitted non-market podium outsider *research* model.

This uses ONLY the caller-approved pre-2025 sample and a strictly later
pre-2025 validation fold. The win model and the outsider model have distinct
training targets. The podium model's race-normalized scores are *relative
rankings*, not calibrated top-three probabilities. No betting, protected
holdout reads, note posting, or artifact promotion occurs here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite

import numpy as np
import pandas as pd

from .modeling import BaselineProbabilityModel
from .odds_free_training import OddsFreeResearchSample
from .odds_free_chronological_eval import (
    _check_race_groups, _strict_date, _validate_research_features, _MARKET,
)

_FINAL_HOLDOUT = date(2025, 1, 1)


@dataclass(frozen=True)
class IndependentOutsiderResearchReport:
    status: str
    winnerModelTarget: str
    outsiderModelTarget: str
    fitThrough: str
    validationFrom: str
    validationThrough: str
    trainingRaces: int
    validationRaces: int
    candidateHitTopThreeRate: float
    baselineFourthRankHitTopThreeRate: float
    improvementOverFourthRank: float
    modelSelectionIndependentOfOdds: bool
    independentModelPublicationProven: bool
    publicationAuthorized: bool
    positiveExpectedValueDemonstrated: bool


def evaluate_independent_outsider_chronologically(
    sample: OddsFreeResearchSample,
    *, fit_through: str, validation_from: str, validation_through: str,
    minimum_training_races: int = 5,
    minimum_validation_races: int = 3,
) -> IndependentOutsiderResearchReport:
    """Compare a separate podium model's outsider to fourth win-score rank.

    Top-three labels from validation outcomes are referenced *only after*
    each validated race has been scored and its outsider has been selected.
    """
    fit = _strict_date(fit_through, "fit_through")
    start = _strict_date(validation_from, "validation_from")
    end = _strict_date(validation_through, "validation_through")
    if not fit < start <= end < _FINAL_HOLDOUT:
        raise ValueError("outsider folds must precede protected final holdout")
    if minimum_training_races < 5 or minimum_validation_races < 3:
        raise ValueError("cannot bypass independent outsider fold sizes")
    if not isinstance(sample, OddsFreeResearchSample):
        raise ValueError("approved strict research sample required")
    _validate_research_features(sample.features)
    if _strict_date(sample.cutoff, "sample cutoff") >= _FINAL_HOLDOUT:
        raise ValueError("protected final holdout sample forbidden")
    if _strict_date(sample.cutoff, "sample cutoff") < end:
        raise ValueError("validation period not fully covered")
    if any(_MARKET.search(str(c)) for c in sample.frame.columns):
        raise ValueError("market columns forbidden in outsider modeling")

    frame = sample.frame.copy()
    required = {"race_id", "race_date", "horse_name", "finish_position", "is_winner"}
    if not required.issubset(frame):
        raise ValueError("race, horse and finish labels required")
    frame["race_date"] = pd.to_datetime(frame["race_date"], errors="raise")
    if (frame["race_date"].isna().any()
            or frame["race_date"].dt.tz is not None
            or frame["race_date"].dt.date.ge(_FINAL_HOLDOUT).any()):
        raise ValueError("protected final holdout or invalid race dates")
    finish = pd.to_numeric(frame["finish_position"], errors="coerce")
    winner = pd.to_numeric(frame["is_winner"], errors="coerce")
    if (finish.isna().any() or winner.isna().any()
            or not winner.eq(finish.eq(1).astype(int)).all()):
        raise ValueError("winner label and actual finish inconsistent")

    train = frame.loc[frame["race_date"].dt.date.le(fit)].copy()
    valid = frame.loc[frame["race_date"].dt.date.between(start, end)].copy()
    if train.empty or valid.empty or set(train["race_id"]) & set(valid["race_id"]):
        raise ValueError("outsider fitting and validation folds overlap or are empty")
    ntrain = _check_race_groups(train, require_podium=True)
    nvalid = _check_race_groups(valid, require_podium=True)
    if ntrain < minimum_training_races or nvalid < minimum_validation_races:
        raise ValueError("insufficient outsider train/validation races")

    # Two separately fitted estimators, two different training targets.
    # Only the *training* fold supplies target-race finish information.
    train["__podium_target_train_only"] = train["finish_position"].le(3).astype(int)
    winner_model = BaselineProbabilityModel(list(sample.features))
    outsider_model = BaselineProbabilityModel(list(sample.features))
    winner_model.fit(train, target_col="is_winner")
    outsider_model.fit(train, target_col="__podium_target_train_only")
    if winner_model.pipeline is outsider_model.pipeline:
        raise ValueError("outsider model must be independently fitted")

    # Strip target results before either model can inspect the held-out fold.
    inference = valid.drop(columns=[
        "finish_position", "is_winner", "__podium_target_train_only",
        "finish_time", "margin", "last_3f", "corner_1", "corner_2",
        "corner_3", "corner_4", "prize_money",
    ], errors="ignore")
    win = winner_model.predict_win_probability(inference, race_col="race_id")
    upside = outsider_model.predict_win_probability(inference, race_col="race_id")
    if (not win.index.equals(valid.index) or not upside.index.equals(valid.index)
            or not np.isfinite(win.to_numpy()).all()
            or not np.isfinite(upside.to_numpy()).all()
            or win.le(0).any() or upside.le(0).any()):
        raise ValueError("invalid independently computed outsider model scores")
    scored = inference[["race_id", "horse_name"]].copy()
    scored["__win"] = win
    scored["__upside"] = upside
    truth = valid.set_index(["race_id", "horse_name"])["finish_position"]
    selected_hits = baseline_hits = 0
    for race_id, race in scored.groupby("race_id", sort=False):
        ranked = race.sort_values(
            ["__win", "horse_name"], ascending=[False, True], kind="stable",
        )
        excluded = set(ranked["horse_name"].astype(str).head(3))
        eligible = ranked.loc[~ranked["horse_name"].astype(str).isin(excluded)]
        if eligible.empty:
            raise ValueError("not enough other runners for independent outsider")
        outsider = eligible.sort_values(
            ["__upside", "horse_name"], ascending=[False, True], kind="stable",
        ).iloc[0]["horse_name"]
        fourth = ranked.iloc[3]["horse_name"]
        selected_hits += int(truth.loc[(race_id, outsider)] <= 3)
        baseline_hits += int(truth.loc[(race_id, fourth)] <= 3)
    selected_rate = selected_hits / nvalid
    baseline_rate = baseline_hits / nvalid
    if not all(isfinite(x) for x in (selected_rate, baseline_rate)):
        raise ValueError("outsider evaluation yielded nonfinite metrics")
    return IndependentOutsiderResearchReport(
        status="RESEARCH_ONLY_NOT_FROZEN_NOT_PUBLISHABLE",
        winnerModelTarget="is_winner",
        outsiderModelTarget="finish_position_le_3_train_only",
        fitThrough=fit.isoformat(),
        validationFrom=start.isoformat(),
        validationThrough=end.isoformat(),
        trainingRaces=ntrain,
        validationRaces=nvalid,
        candidateHitTopThreeRate=selected_rate,
        baselineFourthRankHitTopThreeRate=baseline_rate,
        improvementOverFourthRank=selected_rate - baseline_rate,
        modelSelectionIndependentOfOdds=True,
        independentModelPublicationProven=False,
        publicationAuthorized=False,
        positiveExpectedValueDemonstrated=False,
    )
