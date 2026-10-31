"""Entirely fictional NAR results: prove as-of reconstructed inputs cannot see target outcomes."""
from __future__ import annotations

import csv
from io import StringIO

import pytest

from horse_racing_predictions.nar_prior_day_features import (
    build_prior_day_features,
)
from horse_racing_predictions.nar_official_zip_probe import UnsafeNarSource
from test_nar_published_result_normalizer import _fixture


def _read(text):
    return list(csv.reader(StringIO(text)))


def _write(rows):
    buffer = StringIO(newline="")
    csv.writer(buffer).writerows(rows)
    return buffer.getvalue()


def _month(month, *, race="3", rank_swap=False, previous_identical=True):
    files = _fixture(month=month, starters=8)
    races = _read(files["racelist"])
    races[0][2] = race
    races[0][23] = "1600"
    entries = _read(files["horselist"])
    for i, row in enumerate(entries):
        row[2] = race
        row[10] = f"20190{i+1:02d}01" if not previous_identical else f"201903{i+1:02d}"
        # Only the target label changes. Any same-race 3F, time and
        # popularity must stay outside model features.
        row[32] = "9999"
        row[34] = "11.1"
        row[35] = "1"
    if rank_swap:
        entries[0][31], entries[7][31] = entries[7][31], entries[0][31]
    return {"racelist": _write(races), "horselist": _write(entries)}


def _by_horse_number(batch, month, number):
    return next(
        t for t in batch.return_data
        if t.race_key[1].startswith(month) and t.horse_number == number
    )


def test_only_earlier_dates_enter_form_even_if_input_order_reversed():
    inputs = {"202402": _month("202402"), "202401": _month("202401")}
    result = build_prior_day_features(inputs)
    assert result.status == "NAR_RETROSPECTIVE_PRIOR_DAY_FEATURES_NO_PREOFF_PROOF"
    assert result.eligible_races == 2
    assert result.target_runner_rows == 16
    assert result.features_are_prior_day_only
    assert not result.target_result_entered_features
    assert not result.popularity_or_odds_used
    assert not result.contemporaneous_preoff_snapshot_proven
    assert not result.rights_verified_by_software
    assert "架空馬" not in repr(result)
    first = _by_horse_number(result, "202401", 1)
    second = _by_horse_number(result, "202402", 1)
    assert first.asof.prior_starts == 0
    assert first.asof.prior_mean_finish is None
    assert first.asof.days_since_prior_start is None
    assert second.asof.prior_starts == 1
    assert second.asof.prior_wins == 1
    assert second.asof.prior_top3 == 1
    assert second.asof.prior_win_rate == 1.0
    assert second.asof.prior_top3_rate == 1.0
    assert second.asof.prior_mean_finish == 1.0
    assert second.asof.days_since_prior_start == 31
    loser = _by_horse_number(result, "202402", 8)
    assert loser.asof.prior_starts == 1
    assert loser.asof.prior_wins == 0
    assert loser.asof.prior_top3 == 0
    assert loser.asof.prior_mean_finish == 8


def test_changing_target_finish_popularity_or_time_does_not_change_features():
    original = {"202401": _month("202401"), "202402": _month("202402")}
    baseline = build_prior_day_features(original)
    changed = {"202401": original["202401"].copy(),
               "202402": _month("202402", rank_swap=True)}
    base = _by_horse_number(baseline, "202402", 1)
    after = _by_horse_number(build_prior_day_features(changed), "202402", 1)
    assert base.asof == after.asof
    assert base.final_finish_label == 1
    assert after.final_finish_label == 8
    assert not hasattr(base.asof, "final_finish_label")
    assert not hasattr(base.asof, "popularity")
    assert not hasattr(base.asof, "odds")
    assert not hasattr(base.asof, "finish_time")
    assert not hasattr(base.asof, "today_3f")


def test_horse_name_alone_cannot_join_different_birthdates():
    january = _month("202401")
    february = _month("202402")
    records = _read(february["horselist"])
    records[0][10] = "20180201"  # same name, different horse birth date
    february["horselist"] = _write(records)
    data = build_prior_day_features({"202401": january, "202402": february})
    assert _by_horse_number(data, "202402", 1).asof.prior_starts == 0


def test_missing_birth_date_blocks_identity_based_learning():
    month = _month("202402")
    entries = _read(month["horselist"])
    entries[0][10] = ""
    month["horselist"] = _write(entries)
    with pytest.raises(UnsafeNarSource, match="NAR_ASOF_HORSE_IDENTITY_UNVERIFIED"):
        build_prior_day_features({"202402": month})


def test_same_horse_cannot_race_twice_one_day_even_if_two_races_well_formed():
    first = _month("202402", race="3")
    second = _month("202402", race="4")
    merged = {kind: first[kind] + second[kind]
              for kind in ("racelist", "horselist")}
    with pytest.raises(UnsafeNarSource, match="NAR_ASOF_SAME_HORSE_TWICE_ONE_DAY"):
        build_prior_day_features({"202402": merged})


def test_finishes_must_cover_whole_field_no_ties():
    month = _month("202402")
    entries = _read(month["horselist"])
    entries[1][31] = "1"
    month["horselist"] = _write(entries)
    with pytest.raises(UnsafeNarSource, match="NAR_ASOF_RESULT_ROSTER_INCOMPLETE"):
        build_prior_day_features({"202402": month})


def test_protected_2025_2026_holdout_not_used_in_asof_features():
    with pytest.raises(UnsafeNarSource, match="NAR_PROTECTED_OR_INVALID_DATE"):
        build_prior_day_features({"202502": _month("202502")})


def test_duplicate_race_across_months_is_rejected():
    month = _month("202402")
    with pytest.raises(UnsafeNarSource, match="NAR_ASOF_MONTHLY_INPUT_REQUIRED"):
        build_prior_day_features({"202402": {**month, "payback": "x"}})
