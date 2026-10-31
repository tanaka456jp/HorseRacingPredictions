"""Fictional-only reference-equivalence tests for monthly streaming as-of NAR."""
from __future__ import annotations

from dataclasses import replace
import csv
from io import StringIO

import pytest

from horse_racing_predictions.nar_incremental_prior_day import (
    build_prior_day_features_month_by_month,
)
from horse_racing_predictions.nar_prior_day_features import (
    build_prior_day_features,
)
from horse_racing_predictions.nar_official_zip_probe import UnsafeNarSource
from test_nar_prior_day_features import _month


def _fake(month):
    return _month(month)


def _rewrite(text, index, value):
    rows = list(csv.reader(StringIO(text)))
    for row in rows:
        row[index] = value
    output = StringIO(newline="")
    csv.writer(output).writerows(rows)
    return output.getvalue()


def test_streaming_exactly_matches_old_nonstreaming_two_month_reference():
    source = {"202401": _fake("202401"), "202402": _fake("202402")}
    reference = build_prior_day_features(source)
    streaming = build_prior_day_features_month_by_month(iter(source.items()))
    assert streaming.eligible_races == reference.eligible_races == 2
    assert streaming.target_runner_rows == reference.target_runner_rows == 16
    assert streaming.first_year == reference.first_year == 2024
    assert streaming.last_year == reference.last_year == 2024
    assert streaming.return_data == reference.return_data
    assert streaming.features_are_prior_day_only
    assert not streaming.target_result_entered_features
    assert not streaming.popularity_or_odds_used
    assert not streaming.contemporaneous_preoff_snapshot_proven


def test_earlier_result_may_change_later_history_but_not_same_race_features():
    source = [("202401", _fake("202401")), ("202402", _fake("202402"))]
    baseline = build_prior_day_features_month_by_month(source)
    modified = _fake("202402")
    rows = list(csv.reader(StringIO(modified["horselist"])))
    rows[0][31], rows[7][31] = rows[7][31], rows[0][31]
    output = StringIO(newline="")
    csv.writer(output).writerows(rows)
    modified["horselist"] = output.getvalue()
    changed = build_prior_day_features_month_by_month([
        source[0], ("202402", modified),
    ])
    assert [r.asof for r in baseline.return_data] == [
        r.asof for r in changed.return_data
    ]
    assert baseline.return_data[-8].final_finish_label == 1
    assert changed.return_data[-8].final_finish_label == 8
    assert not changed.contemporaneous_preoff_snapshot_proven


def test_delayed_day_updates_even_with_two_tracks_on_same_day():
    first = _fake("202402")
    second = _fake("202402")
    race_rows = list(csv.reader(StringIO(second["racelist"])))
    for row in race_rows:
        row[0] = "別の架空競馬場"
        row[2] = "4"
    second["racelist"] = _dump(race_rows)
    horse_rows = list(csv.reader(StringIO(second["horselist"])))
    for i, row in enumerate(horse_rows):
        row[0] = "別の架空競馬場"
        row[2] = "4"
        row[6] = f"別の架空馬{i}"
    second["horselist"] = _dump(horse_rows)
    combined = {
        "racelist": first["racelist"] + second["racelist"],
        "horselist": first["horselist"] + second["horselist"],
    }
    result = build_prior_day_features_month_by_month([("202402", combined)])
    assert result.eligible_races == 2
    assert result.target_runner_rows == 16
    assert all(x.asof.prior_starts == 0 for x in result.return_data)


def _dump(rows):
    buf = StringIO(newline="")
    csv.writer(buf).writerows(rows)
    return buf.getvalue()


def test_rejects_reversed_or_duplicate_months_before_learning():
    with pytest.raises(UnsafeNarSource, match="NAR_INCREMENTAL_MONTH_ORDER_OR_SCHEMA_INVALID"):
        build_prior_day_features_month_by_month([
            ("202402", _fake("202402")), ("202401", _fake("202401")),
        ])
    with pytest.raises(UnsafeNarSource, match="NAR_INCREMENTAL_MONTH_ORDER_OR_SCHEMA_INVALID"):
        build_prior_day_features_month_by_month([
            ("202402", _fake("202402")), ("202402", _fake("202402")),
        ])


def test_protected_future_month_cannot_enter_stream():
    with pytest.raises(UnsafeNarSource, match="NAR_INCREMENTAL_MONTH_ORDER_OR_SCHEMA_INVALID"):
        build_prior_day_features_month_by_month([
            ("202501", _fake("202501")),
        ])


def test_unrecognized_birthdate_refused_without_name_only_fallback():
    data = _fake("202401")
    data["horselist"] = _rewrite(data["horselist"], 10, "")
    with pytest.raises(UnsafeNarSource, match="NAR_ASOF_HORSE_IDENTITY_UNVERIFIED"):
        build_prior_day_features_month_by_month([("202401", data)])


def test_no_result_lists_retained_by_per_horse_aggregates():
    import horse_racing_predictions.nar_incremental_prior_day as module
    fields = module._Aggregate.__dataclass_fields__
    assert set(fields) == {"starts", "wins", "top3", "rank_sum", "last_date"}
    assert not hasattr(module._Aggregate(), "__dict__")
