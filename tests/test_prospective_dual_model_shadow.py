"""Synthetic-only forward prediction and full-denominator settlement tests."""
from datetime import datetime, timedelta, timezone
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from horse_racing_predictions.modeling import CatBoostProbabilityModel
from horse_racing_predictions.prospective_dual_model_shadow import (
    ProspectiveShadowHold, freeze_fitted_dual_shadow, score_frozen_shadow,
)

JST = timezone(timedelta(hours=9))
DAY = "2026-12-06"
NOW = datetime(2026, 12, 6, 9, tzinfo=JST)


class NativeFake:
    """Only for isolated tests: exercise real wrapper's score-normalization."""
    def __init__(self, feature):
        self.feature = feature

    def predict(self, frame, prediction_type):
        assert prediction_type == "RawFormulaVal"
        return frame[self.feature].to_numpy(dtype=float)


def sample(jurisdiction="JRA"):
    race = jurisdiction + ":20261206:FICTIONAL:01"
    frame = pd.DataFrame([
        dict(race_id=race, horse_id=str(i), past_starts=i,
             past_top3_rate=8 - abs(i - 2) * 3)
        for i in (1, 2, 3, 4)
    ])
    winner = CatBoostProbabilityModel(
        feature_columns=["past_starts", "past_top3_rate"])
    outsider = CatBoostProbabilityModel(
        feature_columns=["past_starts", "past_top3_rate"])
    winner.model = NativeFake("past_starts")
    outsider.model = NativeFake("past_top3_rate")
    off = NOW + timedelta(hours=2)
    kwargs = dict(
        jurisdiction=jurisdiction, race_day_jst=DAY,
        entries=frame, off_by_race={race: off},
        winner=winner, outsider=outsider,
        model_trained_through="2022-12-31",
        model_sha256_declared="a" * 64,
        source_asof_utc=NOW - timedelta(minutes=1),
        generated_utc=NOW,
    )
    return kwargs


@pytest.mark.parametrize("jurisdiction", ["JRA", "NAR"])
def test_two_models_select_top_three_and_separate_outsider(jurisdiction):
    frozen = freeze_fitted_dual_shadow(**sample(jurisdiction))
    assert frozen.jurisdiction == jurisdiction
    assert len(frozen.races) == 1
    race = frozen.races[0]
    assert race.top3 == ("4", "3", "2")
    assert race.outsider == "1"
    assert len(frozen.commitment_sha256) == 64
    assert frozen.verified_external_timestamp is False
    assert frozen.positive_expected_value_proven is False


def test_official_payout_and_actual_numeric_finish_are_kept_distinct():
    frozen = freeze_fitted_dual_shadow(**sample())
    rid = frozen.races[0].race_id
    outcomes = {rid: {
        "finish_by_horse": {"1": 2, "2": 3, "3": 4, "4": 1},
        "selected_top1_win_return_per_100_yen": 180,
    }}
    result = score_frozen_shadow(frozen, final_by_race=outcomes)
    assert result.status.startswith("COMPLETE_DESCRIPTIVE")
    assert result.top1_win_hit_rate == 1.0
    assert result.top3_numeric_podium_hits == 2
    assert result.outsider_numeric_top3_hits == 1
    assert result.stake_yen == 100
    assert result.official_paper_returns_yen == 180
    assert result.paper_roi_after_stake == 0.8
    assert not result.positive_expected_value_proven


def test_full_cohort_hold_on_missing_or_inconsistent_official_outcome():
    frozen = freeze_fitted_dual_shadow(**sample("NAR"))
    rid = frozen.races[0].race_id
    with pytest.raises(ProspectiveShadowHold, match="DENOMINATOR"):
        score_frozen_shadow(frozen, final_by_race={})
    false_payout = {rid: {
        "finish_by_horse": {"1": 2, "2": 3, "3": 4, "4": 1},
        "selected_top1_win_return_per_100_yen": 0,
    }}
    audit = score_frozen_shadow(frozen, final_by_race=false_payout)
    assert audit.status.startswith("HOLD")
    assert audit.paper_roi_after_stake is None
    assert not audit.positive_expected_value_proven


def test_no_fabricated_inference_or_future_leakage():
    kw = sample()
    kw["outsider"].model = kw["winner"].model
    with pytest.raises(ProspectiveShadowHold, match="TWO_FITTED"):
        freeze_fitted_dual_shadow(**kw)
    kw = sample()
    kw["entries"]["finish_position"] = 1
    with pytest.raises(ProspectiveShadowHold, match="ROSTER"):
        freeze_fitted_dual_shadow(**kw)
    kw = sample()
    kw["off_by_race"] = {next(iter(kw["off_by_race"])): NOW + timedelta(minutes=10)}
    with pytest.raises(ProspectiveShadowHold, match="CALENDAR"):
        freeze_fitted_dual_shadow(**kw)


def test_race_day_and_model_chronology_enforced():
    kw = sample()
    kw["model_trained_through"] = DAY
    with pytest.raises(ProspectiveShadowHold, match="MODEL_OR_RACE_DATE"):
        freeze_fitted_dual_shadow(**kw)
