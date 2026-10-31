"""Only invented NAR race CSV rows: full-month denominator and exclusions."""
from __future__ import annotations

import csv
from io import StringIO

import pytest

from horse_racing_predictions.nar_monthly_coverage_audit import (
    audit_nar_monthly_coverage,
)
from horse_racing_predictions.nar_official_zip_probe import UnsafeNarSource
from test_nar_published_result_normalizer import _fixture


def _encode(rows):
    file = StringIO(newline="")
    csv.writer(file).writerows(rows)
    return file.getvalue()


def _second_race(*, race_number="4", bad_win=False, tie=False):
    parts = _fixture()
    for kind, text in list(parts.items()):
        rows = list(csv.reader(StringIO(text)))
        for row in rows:
            row[2] = race_number
        if kind == "payback" and bad_win:
            rows[0][4] = "2"
        if kind == "horselist" and tie:
            rows[1][31] = "1"
        parts[kind] = _encode(rows)
    return parts


def _combine(a, b):
    return {kind: a[kind] + b[kind] for kind in ("racelist", "horselist", "payback")}


def test_all_races_valid_preserves_full_denominator():
    dataset = _combine(_fixture(), _second_race())
    report = audit_nar_monthly_coverage(dataset, month="202402")
    summary = report.summary
    assert summary.observed_races == 2
    assert summary.structurally_accepted_races == 2
    assert summary.structurally_accepted_starters == 16
    assert summary.excluded_races == 0
    assert summary.exclusion_reasons == ()
    assert report.exclusions == ()
    assert summary.complete_month_for_research
    assert not summary.valid_economic_roi_sample
    assert not summary.approved_for_model_training
    assert not summary.positive_ev_demonstrated
    assert not summary.publication_authorized


def test_corrupt_payback_does_not_disappear_from_denominator():
    data = _combine(_fixture(), _second_race(bad_win=True))
    report = audit_nar_monthly_coverage(data, month="202402")
    summary = report.summary
    assert summary.observed_races == 2
    assert summary.structurally_accepted_races == 1
    assert summary.structurally_accepted_starters == 8
    assert summary.excluded_races == 1
    assert summary.exclusion_reasons == (
        ("NAR_PAYOUT_CONTRADICTS_FINAL_RESULTS", 1),
    )
    assert not summary.complete_month_for_research
    assert not summary.valid_economic_roi_sample
    assert not summary.positive_ev_demonstrated
    assert "架空馬" not in repr(report)
    assert "架空競馬場" not in repr(report)
    assert "20240214" not in repr(report)


def test_missing_payback_keeps_race_in_source_denominator():
    first = _fixture()
    second = _second_race()
    second["payback"] = ""
    report = audit_nar_monthly_coverage(_combine(first, second), month="202402")
    assert report.summary.observed_races == 2
    assert report.summary.excluded_races == 1
    assert report.summary.exclusion_reasons == (
        ("NAR_RACE_COVERAGE_MISMATCH", 1),
    )


def test_payback_row_with_no_matching_racelist_is_also_counted():
    first = _fixture()
    orphan = _second_race(race_number="7")
    data = _combine(first, _second_race())
    data["payback"] += orphan["payback"]
    report = audit_nar_monthly_coverage(data, month="202402")
    assert report.summary.observed_races == 3
    assert report.summary.excluded_races == 1
    assert report.summary.exclusion_reasons == (
        ("NAR_RACE_COVERAGE_MISMATCH", 1),
    )


def test_dead_heat_rejected_without_optimistic_roi_selection():
    data = _combine(_fixture(), _second_race(tie=True))
    report = audit_nar_monthly_coverage(data, month="202402")
    assert report.summary.excluded_races == 1
    assert report.summary.exclusion_reasons == (
        ("NAR_DEAD_HEAT_SCRATCH_OR_INCOMPLETE_RANKS", 1),
    )
    assert report.summary.status == "NAR_MONTH_HAS_EXCLUSIONS_RESEARCH_ROI_BLOCKED"


def test_duplicate_payback_is_a_named_exclusion():
    data = _fixture()
    data["payback"] += data["payback"]
    report = audit_nar_monthly_coverage(data, month="202402")
    assert report.summary.exclusion_reasons == (
        ("NAR_DEAD_HEAT_OR_DUPLICATE_PAYOUT", 1),
    )


def test_schema_corruption_still_refuses_entire_source():
    data = _fixture()
    data["payback"] = "BAD\n"
    with pytest.raises(UnsafeNarSource, match="NAR_CSV_SCHEMA_DRIFT"):
        audit_nar_monthly_coverage(data, month="202402")


def test_protected_year_rejected_before_race_audit():
    with pytest.raises(UnsafeNarSource, match="NAR_PROTECTED_OR_INVALID_DATE"):
        audit_nar_monthly_coverage(_fixture(month="202502"), month="202502")
