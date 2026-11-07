"""Pure synthetic chronological form. No private NAR licensed CSV."""
from __future__ import annotations

import csv
from dataclasses import replace
from io import StringIO

import pytest

from horse_racing_predictions.nar_official_exception_audit import (
    audit_nar_official_exceptions,
)
from horse_racing_predictions.nar_official_zip_probe import UnsafeNarSource
from horse_racing_predictions.nar_status_aware_training_labels import (
    derive_nar_status_aware_outcome_labels,
)
from horse_racing_predictions.nar_status_aware_prior_day import (
    reconstruct_nar_status_aware_prior_day,
)
from test_nar_published_result_normalizer import _fixture
from test_nar_official_exception_audit import _synthetic_with_status


def _month(source, *, sample_birth="20110101"):
    report = audit_nar_official_exceptions(source, month="201711")
    labels = derive_nar_status_aware_outcome_labels(report)
    # Fictional stable identities, not extracted from a private archive.
    ids = {
        (row.race_key, row.horse_number): (f"架空馬{row.horse_number}", sample_birth)
        for row in labels.labels
    }
    return ("201711", labels, ids)


def _merge_days(one, two, *, day="20171115", number="3"):
    result = {}
    for kind in ("racelist", "horselist", "payback"):
        rows1 = list(csv.reader(StringIO(one[kind])))
        rows2 = list(csv.reader(StringIO(two[kind])))
        for row in rows2[1:]:
            row[1] = day
            row[2] = number
        buf = StringIO(newline="")
        csv.writer(buf).writerows([*rows1, *rows2[1:]])
        result[kind] = buf.getvalue()
    return result


@pytest.mark.parametrize(("exception", "expected_starts", "mean_rank"), [
    ("取消", 0, None),
    ("除外", 0, None),
    ("中止", 1, None),
])
def test_prior_history_correctly_skips_nonstarts_and_counts_dnf(
    exception, expected_starts, mean_rank,
):
    first = _synthetic_with_status(
        exception, only_two_placers=(exception == "取消")
    )
    second = _fixture(month="201711", with_header=True)
    source = _merge_days(first, second)
    batch = reconstruct_nar_status_aware_prior_day([_month(source)])
    assert batch.audit.months == 1
    assert batch.audit.validated_flat_races == 2
    assert batch.audit.unresolved_flat_races == 0
    assert not batch.audit.usable_for_training
    assert not batch.audit.independently_captured_preoff_roster
    assert len(batch.targets) == batch.audit.projected_target_rows
    at_second_day = {
        t.horse_number: t for t in batch.targets
        if t.race_key[1] == "20171115"
    }
    later = at_second_day[8].feature
    assert later.prior_starts == expected_starts
    assert batch.audit.target_rows_with_prior_start == 7 + expected_starts
    assert batch.audit.target_rows_without_prior_start == 8
    assert batch.audit.target_rows_with_prior_win == 1
    assert batch.audit.target_rows_with_prior_top3 == 3
    assert batch.audit.target_rows_with_numeric_prior_finish == 7
    assert later.prior_wins == 0
    assert later.prior_top3 == 0
    assert later.prior_mean_finish == mean_rank
    assert later.days_since_prior_start == (1 if expected_starts else None)
    winner = at_second_day[1].feature
    assert winner.prior_starts == 1
    assert winner.prior_wins == 1
    assert winner.prior_top3 == 1
    assert winner.prior_mean_finish == 1
    assert winner.days_since_prior_start == 1
    assert not batch.audit.positive_expected_value_demonstrated
    assert "架空" not in repr(batch)


def test_top3_form_not_wrongly_derived_from_two_place_winners():
    first = _fixture(month="201711", with_header=True, starters=7)
    second = _fixture(month="201711", with_header=True, starters=7)
    source = _merge_days(first, second)
    batch = reconstruct_nar_status_aware_prior_day([_month(source)])
    later = next(
        t for t in batch.targets
        if t.race_key[1] == "20171115" and t.horse_number == 3
    )
    # The horse was third in a 7-runner race: no *place* dividend,
    # nevertheless its last result is a legitimate top-three finish.
    assert batch.audit.target_rows_with_prior_start == 7
    assert batch.audit.target_rows_without_prior_start == 7
    assert batch.audit.target_rows_with_prior_win == 1
    assert batch.audit.target_rows_with_prior_top3 == 3
    assert batch.audit.target_rows_with_numeric_prior_finish == 7
    assert later.feature.prior_top3 == 1
    assert later.feature.prior_starts == 1
    assert later.feature.prior_mean_finish == 3


def test_incomplete_month_has_no_training_targets_even_diagnostic_mode():
    data = _fixture(month="201711", with_header=True)
    pay = list(csv.reader(StringIO(data["payback"])))
    pay[1][4] = "2"  # fictional incompatible published winning ticket
    sink = StringIO(newline="")
    csv.writer(sink).writerows(pay)
    data["payback"] = sink.getvalue()
    month = _month(data)
    with pytest.raises(UnsafeNarSource, match="NAR_ASOF_INCOMPLETE_MONTH_FAIL_CLOSED"):
        reconstruct_nar_status_aware_prior_day([month])
    preview = reconstruct_nar_status_aware_prior_day(
        [month], allow_incomplete_diagnostic=True,
    )
    assert preview.audit.unresolved_flat_races == 1
    assert preview.audit.projected_target_rows == 0
    assert preview.targets == ()
    assert not preview.audit.usable_for_training


def test_incomplete_month_with_valid_races_does_not_return_partial_targets():
    good = _fixture(month="201711", with_header=True)
    bad = _fixture(month="201711", with_header=True)
    both = _merge_days(good, bad)
    pay = list(csv.reader(StringIO(both["payback"])))
    pay[2][4] = "3"
    sink = StringIO(newline="")
    csv.writer(sink).writerows(pay)
    both["payback"] = sink.getvalue()
    month = _month(both)
    report = reconstruct_nar_status_aware_prior_day(
        [month], allow_incomplete_diagnostic=True,
    )
    assert report.audit.source_flat_races == 2
    assert report.audit.validated_flat_races == 1
    assert report.audit.unresolved_flat_races == 1
    assert report.audit.projected_target_rows == 8
    assert report.targets == ()
    assert not report.audit.usable_for_training


def test_wrong_or_duplicated_race_identity_blocks_model_features():
    month, labels, identities = _month(
        _fixture(month="201711", with_header=True)
    )
    broken = dict(identities)
    broken.pop(next(iter(broken)))
    with pytest.raises(UnsafeNarSource, match="NAR_ASOF_LABEL_IDENTITY_COVERAGE_MISMATCH"):
        reconstruct_nar_status_aware_prior_day([(month, labels, broken)])
    wrong = dict(identities)
    for key in wrong:
        wrong[key] = ("架空馬", "20110101")
    with pytest.raises(UnsafeNarSource, match="NAR_ASOF_SAME_HORSE_TWICE_ONE_DAY"):
        reconstruct_nar_status_aware_prior_day([(month, labels, wrong)])


def test_later_month_cannot_run_before_earlier_month_and_rights_stay_unverified():
    month = _month(_fixture(month="201711", with_header=True))
    with pytest.raises(UnsafeNarSource, match="NAR_ASOF_SOURCE_MONTH_ORDER_OR_RIGHTS_INVALID"):
        reconstruct_nar_status_aware_prior_day([month, month])
    corrupted = (
        month[0],
        replace(month[1], audit=replace(month[1].audit, model_training_authorized=True)),
        month[2],
    )
    with pytest.raises(UnsafeNarSource, match="NAR_ASOF_SOURCE_MONTH_ORDER_OR_RIGHTS_INVALID"):
        reconstruct_nar_status_aware_prior_day([corrupted])

def test_single_month_first_day_has_no_prior_day_history_and_no_ev_evidence():
    month = _month(_fixture(month="201711", with_header=True))
    result = reconstruct_nar_status_aware_prior_day([month])
    a = result.audit
    assert a.projected_target_rows == 8
    assert a.target_rows_without_prior_start == 8
    assert a.target_rows_with_prior_start == 0
    assert a.target_rows_with_prior_win == 0
    assert a.target_rows_with_prior_top3 == 0
    assert a.target_rows_with_numeric_prior_finish == 0
    assert not a.usable_for_training
    assert not a.positive_expected_value_demonstrated

