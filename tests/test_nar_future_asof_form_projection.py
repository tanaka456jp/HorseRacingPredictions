"""Fictional-only temporal CatBoost feature projection tests."""
from datetime import datetime, timedelta, timezone
import pandas as pd
import pytest

from horse_racing_predictions.nar_future_asof_form_projection import (
    nar_future_form_features, prepare_reviewed_nar_full_form,
)

UTC = timezone.utc
NOW = datetime(2026, 11, 23, 8, tzinfo=UTC)
DAY = "2026-11-24"
RID = "NAR:20261124:架空場:01"


def entries():
    return pd.DataFrame([
        dict(race_id=RID, horse_id=str(i), horse_name=f"架空馬{i}",
             birth_ymd="20210304") for i in range(1, 5)
    ])


def history():
    return pd.DataFrame([
        dict(horse_name="架空馬1", birth_ymd="20210304",
             race_day_jst="2026-11-18",
             result_released_utc="2026-11-18T10:00:00Z",
             official_status="FINISHED", finish_rank=1),
        dict(horse_name="架空馬1", birth_ymd="20210304",
             race_day_jst="2026-11-20",
             result_released_utc="2026-11-20T10:00:00Z",
             official_status="DNF_NO_REFUND", finish_rank=None),
        dict(horse_name="架空馬2", birth_ymd="20210304",
             race_day_jst="2026-11-21",
             result_released_utc="2026-11-21T10:00:00Z",
             official_status="SCRATCH_NOT_OFFERED", finish_rank=None),
    ])


def test_asof_features_identical_training_mean_and_dnf_semantics():
    out = nar_future_form_features(
        history(), entries(), race_day_jst=DAY, source_asof_utc=NOW)
    row = out.iloc[0]
    assert row["past_starts"] == 2
    assert row["past_win_rate"] == 0.5
    assert row["past_top3_rate"] == 0.5
    assert row["past_mean_finish"] == 1.0
    assert row["days_since_last_start"] == 4.0
    assert out.iloc[1]["past_starts"] == 0
    assert pd.isna(out.iloc[1]["days_since_last_start"])
    assert set(out) == {"race_id","horse_id","past_starts","past_win_rate",
                        "past_top3_rate","past_mean_finish","days_since_last_start"}


@pytest.mark.parametrize("change", ["same_day", "late_publication", "wrong_rank"])
def test_future_results_and_inconsistent_history_rejected(change):
    h=history()
    if change == "same_day":
        h.loc[0, "race_day_jst"] = DAY
    if change == "late_publication":
        h.loc[0, "result_released_utc"] = "2026-11-25T10:00:00Z"
    if change == "wrong_rank":
        h.loc[1, "finish_rank"] = 2
    with pytest.raises(ValueError):
        nar_future_form_features(h, entries(), race_day_jst=DAY, source_asof_utc=NOW)


def test_duplicate_horse_date_and_roster_breach_rejected():
    with pytest.raises(ValueError):
        nar_future_form_features(
            pd.concat([history(), history().iloc[:1]], ignore_index=True),
            entries(), race_day_jst=DAY, source_asof_utc=NOW,
        )
    with pytest.raises(ValueError):
        nar_future_form_features(
            history(), entries().iloc[:3].copy(),
            race_day_jst=DAY, source_asof_utc=NOW,
        )


def reviewed_entries():
    out = entries()
    out["reviewed_starts"] = [2, 0, 0, 0]
    out["reviewed_wins"] = [1, 0, 0, 0]
    out["reviewed_top3"] = [1, 0, 0, 0]
    return out


def test_full_history_matches_reviewed_counts():
    result = prepare_reviewed_nar_full_form(
        history(), reviewed_entries(), race_day_jst=DAY,
        source_asof_utc=NOW, expected_runner_counts={RID: 4},
    )
    assert result.iloc[0]["past_starts"] == 2
    assert result.iloc[0]["days_since_last_start"] == 4
    assert pd.isna(result.iloc[1]["past_mean_finish"])


@pytest.mark.parametrize("issue", ["missing_history", "missing_runner", "naive", "before_race", "wrong_total"])
def test_reviewed_full_form_refuses_unverified_coverage(issue):
    h, e = history(), reviewed_entries()
    if issue == "missing_history":
        h = h.iloc[1:]
    elif issue == "missing_runner":
        e = e.iloc[:-1]
    elif issue == "naive":
        h.loc[0, "result_released_utc"] = "2026-11-18T10:00:00"
    elif issue == "before_race":
        h.loc[0, "result_released_utc"] = "2026-11-17T00:00:00Z"
    else:
        e.loc[0, "reviewed_top3"] = 2
    with pytest.raises(ValueError):
        prepare_reviewed_nar_full_form(h, e, race_day_jst=DAY,
            source_asof_utc=NOW, expected_runner_counts={RID: 4})


def test_disqualified_prior_start_matches_training_denominator():
    h = history()
    h.loc[1, "official_status"] = "DISQUALIFIED_REVIEW"
    h.loc[0, "horse_name"] = " 架空馬1 "
    out = prepare_reviewed_nar_full_form(
        h, reviewed_entries(), race_day_jst=DAY,
        source_asof_utc=NOW, expected_runner_counts={RID: 4},
    )
    assert out.iloc[0]["past_starts"] == 2
    assert out.iloc[0]["past_win_rate"] == 0.5
    assert out.iloc[0]["past_mean_finish"] == 1
    assert out.iloc[0]["days_since_last_start"] == 4


@pytest.mark.parametrize("issue", [
    "bad_birthday", "birth_after_race", "same_horse_twice",
    "duplicate_index", "naive_release", "before_race_release",
    "whitespace_duplicate_history",
])
def test_shared_projector_rejects_identity_and_time_mismatch(issue):
    h, e = history(), entries()
    if issue == "bad_birthday":
        e.loc[0, "birth_ymd"] = "20210230"
    elif issue == "birth_after_race":
        h.loc[0, "birth_ymd"] = "20261119"
    elif issue == "same_horse_twice":
        e.loc[1, "horse_name"] = " 架空馬1 "
    elif issue == "duplicate_index":
        e.index = [0, 0, 1, 2]
    elif issue == "naive_release":
        h.loc[0, "result_released_utc"] = "2026-11-18T10:00:00"
    elif issue == "before_race_release":
        h.loc[0, "result_released_utc"] = "2026-11-17T10:00:00Z"
    else:
        extra = h.iloc[:1].copy()
        extra["horse_name"] = " 架空馬1 "
        h = pd.concat([h, extra], ignore_index=True)
    with pytest.raises(ValueError):
        nar_future_form_features(h, e, race_day_jst=DAY, source_asof_utc=NOW)
