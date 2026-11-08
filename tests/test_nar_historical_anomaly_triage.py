"""Synthetic-only 72-month NAR anomaly and held-out safety contracts."""
from __future__ import annotations

from dataclasses import replace
import csv
from io import StringIO

import pytest

from horse_racing_predictions.nar_historical_anomaly_triage import (
    triage_historical_nar_anomalies,
)
from horse_racing_predictions.nar_official_zip_probe import UnsafeNarSource
from horse_racing_predictions.nar_training_preflight import (
    diagnose_nar_training_folder,
)
from test_nar_local_monthly_intake import _make_zip
from test_nar_official_exception_audit import _synthetic_with_status


@pytest.fixture(scope="module")
def synthetic_72_months(tmp_path_factory):
    folder = tmp_path_factory.mktemp("fictional_private_nar_72")
    conflict = _synthetic_with_status("失格")
    rows = list(csv.reader(StringIO(conflict["payback"])))
    rows[1][4] = "8"
    out = StringIO(newline="")
    csv.writer(out).writerows(rows)
    conflict["payback"] = out.getvalue()
    for y in range(2017, 2023):
        for m in range(1, 13):
            mo = f"{y}{m:02d}"
            _make_zip(folder, month=mo,
                      override=conflict if mo == "201711" else None)
    return diagnose_nar_training_folder(
        folder, personal_private_permission_confirmed=True,
    )


def test_full_72_months_root_cause_is_counted_without_deleting_bad_race(synthetic_72_months):
    report = triage_historical_nar_anomalies(synthetic_72_months)
    assert report.months_verified == 72
    assert report.flat_races == 72
    assert report.strict_unresolved_flat == 1
    assert report.status_aware_unresolved_flat == 1
    assert report.newly_interpreted_flat == 0
    assert report.by_reason == (("NAR_WIN_PAYOUT_TO_DISQUALIFIED_STATUS", 1),)
    assert report.by_category == (("DQ_SETTLEMENT_PRIMARY_SOURCE", 1),)
    assert tuple(x.year for x in report.by_year) == tuple(range(2017, 2023))
    assert all(x.source_months == 12 for x in report.by_year)
    assert report.by_year[0].status_aware_unresolved_flat == 1
    assert all(x.status_aware_unresolved_flat == 0 for x in report.by_year[1:])
    assert sum(x.total_flat_races for x in report.by_year) == 72
    assert not report.source_records_exported
    assert not report.historical_protected_oos_opened
    assert report.training_rows_released == 0
    assert not report.actual_cost_adjusted_roi_evaluated
    assert not report.positive_expected_value_demonstrated
    assert "架空" not in repr(report)


def test_status_aware_relief_differs_from_rank_only_without_release(synthetic_72_months):
    original = synthetic_72_months
    items = list(original.diagnostic)
    # Fictional status-resolved 2017-12 exception. Full denominator stays.
    old = items[11]
    items[11] = replace(
        old, accepted_flat_races=0,
        unresolved_flat_races=1,
        static_reasons=(("NAR_OFFICIAL_BLANK_FINISH_STATUS_UNRESOLVED", 1),),
    )
    tweaked = replace(original,
        diagnostic=tuple(items),
        accepted_flat_races=original.accepted_flat_races - 1,
        unresolved_flat_races=original.unresolved_flat_races + 1,
        months_structurally_accepted=original.months_structurally_accepted - 1,
        months_with_unresolved_errors=original.months_with_unresolved_errors + 1,
    )
    found = triage_historical_nar_anomalies(tweaked)
    assert found.strict_unresolved_flat == 2
    assert found.status_aware_unresolved_flat == 1
    assert found.newly_interpreted_flat == 1
    assert found.training_rows_released == 0


@pytest.mark.parametrize(("field", "value", "error"), [
    ("months_present", 71, "NAR_TRIAGE_COMPLETE_PRIVATE_TRAINING_MONTHS_REQUIRED"),
    ("months_missing", 1, "NAR_TRIAGE_COMPLETE_PRIVATE_TRAINING_MONTHS_REQUIRED"),
    ("model_training_performed", True, "NAR_TRIAGE_COMPLETE_PRIVATE_TRAINING_MONTHS_REQUIRED"),
    ("payouts_or_roi_evaluated", True, "NAR_TRIAGE_COMPLETE_PRIVATE_TRAINING_MONTHS_REQUIRED"),
    ("protected_holdout_opened", True, "NAR_TRIAGE_COMPLETE_PRIVATE_TRAINING_MONTHS_REQUIRED"),
    ("data_sent_to_network", True, "NAR_TRIAGE_COMPLETE_PRIVATE_TRAINING_MONTHS_REQUIRED"),
])
def test_incomplete_or_unauthorized_study_held_closed(synthetic_72_months, field, value, error):
    with pytest.raises(UnsafeNarSource, match=error):
        triage_historical_nar_anomalies(
            replace(synthetic_72_months, **{field: value}),
        )


def test_duplicate_month_or_private_source_rejection_is_not_ignored(synthetic_72_months):
    original = synthetic_72_months
    dup = list(original.diagnostic)
    dup[5] = replace(dup[5], month="201711")
    with pytest.raises(UnsafeNarSource, match="NAR_TRIAGE_COMPLETE_PRIVATE_TRAINING_MONTHS_REQUIRED"):
        triage_historical_nar_anomalies(replace(original, diagnostic=tuple(dup)))
    bad = list(original.diagnostic)
    bad[7] = replace(bad[7], status="MONTH_SOURCE_REJECTED")
    with pytest.raises(UnsafeNarSource, match="NAR_TRIAGE_REJECTED_MONTH_OR_INVALID_COUNTS"):
        triage_historical_nar_anomalies(replace(original, diagnostic=tuple(bad)))


def test_status_reason_sum_inconsistency_and_unsafe_code_blocked(synthetic_72_months):
    original = synthetic_72_months
    bad = list(original.diagnostic)
    old = bad[10]  # official synthetic 2017-11 disqualification conflict
    bad[10] = replace(old, status_aware_reasons=())
    with pytest.raises(UnsafeNarSource, match="NAR_TRIAGE_RACE_DENOMINATOR_CONFLICT"):
        triage_historical_nar_anomalies(replace(original, diagnostic=tuple(bad)))
    bad[10] = replace(old, status_aware_reasons=(("NAR_SENSITIVE_HORSE_PERSON", 1),))
    # Unknown, but well-formed static class is explicitly UNKNOWN.
    report = triage_historical_nar_anomalies(
        replace(original, diagnostic=tuple(bad)),
    )
    assert report.by_category == (("UNKNOWN_REQUIRES_REVIEW", 1),)
    bad[10] = replace(old, status_aware_reasons=(("NAR_LEAKED:PRIVATE_NAME", 1),))
    with pytest.raises(UnsafeNarSource, match="NAR_TRIAGE_UNSAFE_REASON_CODE"):
        triage_historical_nar_anomalies(replace(original, diagnostic=tuple(bad)))


def test_tampered_overall_flat_denominator_is_rejected(synthetic_72_months):
    orig = synthetic_72_months
    for field, delta in (("unresolved_flat_races", 1),
                         ("status_aware_unresolved_flat_races", 1),
                         ("status_aware_validated_flat_races", 1),
                         ("months_status_aware_complete", 1)):
        with pytest.raises(UnsafeNarSource, match="NAR_TRIAGE_ALL_PERIOD_TOTALS_CONFLICT"):
            triage_historical_nar_anomalies(
                replace(orig, **{field: getattr(orig, field) + delta}),
            )
