"""Fictional-only matched three-series research regression."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pandas as pd
import pytest

from horse_racing_predictions.modeling import CatBoostProbabilityModel
from horse_racing_predictions.nar_paired_future_comparison import (
    compare_nar_future_rankings,
)
from horse_racing_predictions.nar_future_asof_form_projection import (
    prepare_reviewed_nar_full_form,
)
from test_nar_future_asof_form_projection import (
    history, reviewed_entries, NOW, DAY, RID,
)


class NativeFake:
    def __init__(self, column):
        self.column = column
        self.calls = []

    def predict(self, frame, prediction_type):
        assert prediction_type == "RawFormulaVal"
        self.calls.append(frame.copy())
        return frame[self.column].fillna(-1).to_numpy(dtype=float)


def inputs():
    h, e = history(), reviewed_entries()
    expected = {RID: 4}
    partial = prepare_reviewed_nar_full_form(
        h, e, race_day_jst=DAY, source_asof_utc=NOW,
        expected_runner_counts=expected,
    )
    columns = list(partial.columns[2:])
    partial[["past_mean_finish", "days_since_last_start"]] = float("nan")
    winner = CatBoostProbabilityModel(feature_columns=columns)
    outsider = CatBoostProbabilityModel(feature_columns=columns)
    winner.model = NativeFake("past_mean_finish")
    outsider.model = NativeFake("past_top3_rate")
    generated = datetime(2026, 11, 24, 0, tzinfo=timezone.utc)
    return dict(official_partial=partial, reviewed_entries=e, history=h,
                off_by_race={RID: generated + timedelta(hours=2)},
                expected_runner_counts=expected, race_day_jst=DAY,
                source_asof_utc=NOW, generated_utc=generated,
                loaded=SimpleNamespace(features=columns,
                    train_end="2021-12-31", winner=winner, outsider=outsider,
                    digest_by_role={"win.cbm": "a"*64, "outsider.cbm": "b"*64}))


def test_same_roster_and_distinct_feature_views_without_mutating_inputs():
    kw = inputs()
    before = kw["official_partial"].copy(deep=True)
    out = compare_nar_future_rankings(**kw)
    partial = out["catboost_3_of_5"].races[0]
    full = out["catboost_reviewed_5_feature"].races[0]
    baseline = out["fixed_career_baseline"][0]
    assert partial.roster == full.roster == ("1", "2", "3", "4")
    assert baseline["race_id"] == RID
    assert baseline["top3"][0] == "1"
    assert len(set(baseline["top3"]) | {baseline["outsider"]}) == 4
    assert out["race_count"] == 1 and out["runner_count"] == 4
    assert not out["independent_preoff_receipt_verified"]
    assert not out["outcomes_measured"]
    calls = kw["loaded"].winner.model.calls
    assert len(calls) == 2
    assert calls[0]["past_mean_finish"].isna().all()
    assert calls[1]["past_mean_finish"].notna().sum() == 1
    pd.testing.assert_frame_equal(before, kw["official_partial"])


@pytest.mark.parametrize("issue", ["career", "roster", "extra"])
def test_mismatched_or_contaminated_official_input_is_rejected(issue):
    kw = inputs()
    frame = kw["official_partial"]
    if issue == "career":
        frame.loc[0, "past_starts"] += 1
    elif issue == "roster":
        frame.loc[0, "horse_id"] = "different"
    else:
        frame.loc[0, "past_mean_finish"] = 1
    with pytest.raises(ValueError, match="NAR_PAIRED"):
        compare_nar_future_rankings(**kw)
    assert not kw["loaded"].winner.model.calls
