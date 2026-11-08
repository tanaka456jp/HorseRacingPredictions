"""Fictional NAR official CSV rows: no licensed input exposed."""
from __future__ import annotations

import csv
from io import StringIO
import pytest

from horse_racing_predictions.nar_official_exception_audit import (
    audit_nar_official_exceptions, _status_and_rank,
)
from horse_racing_predictions.nar_official_zip_probe import UnsafeNarSource
from test_nar_published_result_normalizer import _fixture


def _dump(rows):
    out = StringIO(newline="")
    csv.writer(out).writerows(rows)
    return out.getvalue()


def _synthetic_with_status(status: str, *, only_two_placers=False):
    values = _fixture(starters=8, month="201711", with_header=True)
    rows = list(csv.reader(StringIO(values["horselist"])))
    rows[8][31] = ""
    rows[8][33] = status
    values["horselist"] = _dump(rows)
    if only_two_placers:
        pay = list(csv.reader(StringIO(values["payback"])))
        pay[1][13] = ""
        pay[1][14] = ""
        values["payback"] = _dump(pay)
    return values


@pytest.mark.parametrize(("marker", "expected"), [
    ("取消", "SCRATCH_NOT_OFFERED"),
    ("出走取消", "SCRATCH_NOT_OFFERED"),
    ("除外", "EXCLUDED_REFUND"),
    ("競走除外", "EXCLUDED_REFUND"),
    ("中止", "DNF_NO_REFUND"),
    ("競走中止", "DNF_NO_REFUND"),
    ("失格", "DISQUALIFIED_REVIEW"),
])
def test_official_status_from_margin_only(marker, expected):
    row = [""] * 36
    row[33] = marker
    assert _status_and_rank(row) == (expected, None)


@pytest.mark.parametrize(("rank", "marker", "error"), [
    ("", "", "NAR_BLANK_WITHOUT_OFFICIAL_STATUS"),
    ("", "unknown", "NAR_BLANK_WITHOUT_OFFICIAL_STATUS"),
    ("1", "中止", "NAR_CONFLICTING_RANK_AND_EXCEPTION"),
    ("19", "", "NAR_FINISH_RANK_INVALID"),
])
def test_ambiguous_or_conflicting_status_never_assumed(rank, marker, error):
    row = [""] * 36
    row[31], row[33] = rank, marker
    with pytest.raises(UnsafeNarSource, match=error):
        _status_and_rank(row)


@pytest.mark.parametrize(("marker", "expected_return", "field_size", "starter_size", "only_two"), [
    ("取消", None, 7, 7, True),
    ("除外", 100, 8, 7, False),
    ("中止", 0, 8, 8, False),
    ("失格", None, 8, 8, False),
])
def test_strict_status_aware_audit_never_manufactures_a_losing_bet(
    marker, expected_return, field_size, starter_size, only_two,
):
    data = _synthetic_with_status(marker, only_two_placers=only_two)
    report = audit_nar_official_exceptions(data, month="201711")
    audit = report.audit
    assert audit.source_races == 1
    assert audit.status_validated_flat_races == 1
    assert audit.unresolved_flat_races == 0
    assert audit.complete_flat_outcome_interpretation
    assert not audit.training_authorized
    assert not audit.economic_roi_authorized
    assert not audit.positive_ev_demonstrated
    assert not audit.source_bytes_exported
    race = report.validated_races[0]
    assert race.offered_field_size == field_size
    assert race.actual_starting_horses == starter_size
    assert dict(race.win_yen_by_number)[8] == expected_return
    assert dict(race.place_yen_by_number)[8] == expected_return
    assert not race.economic_roi_authorized
    assert not race.pre_event_availability_proven
    assert "架空" not in repr(report)
    assert "20171114" not in repr(report)


def test_sale_time_field_controls_place_cutoff_not_post_exclusion_field():
    data = _synthetic_with_status("除外", only_two_placers=True)
    result = audit_nar_official_exceptions(data, month="201711").audit
    assert result.status_validated_flat_races == 0
    assert result.unresolved_reason_counts == (
        ("NAR_STATUS_AWARE_PLACE_PAYOUT_MISMATCH", 1),
    )


def test_scratch_before_sales_requires_changed_place_ticket_cutoff():
    data = _synthetic_with_status("取消", only_two_placers=False)
    result = audit_nar_official_exceptions(data, month="201711").audit
    assert result.status_validated_flat_races == 0
    assert result.unresolved_reason_counts == (
        ("NAR_STATUS_AWARE_PLACE_PAYOUT_MISMATCH", 1),
    )


def test_blank_with_no_official_margin_status_is_counted_not_dropped():
    data = _synthetic_with_status("")
    report = audit_nar_official_exceptions(data, month="201711")
    assert report.audit.source_races == 1
    assert report.audit.in_scope_flat_races == 1
    assert report.audit.status_validated_flat_races == 0
    assert report.audit.unresolved_flat_races == 1
    assert report.audit.unresolved_reason_counts == (
        ("NAR_BLANK_WITHOUT_OFFICIAL_STATUS", 1),
    )
    assert report.validated_races == ()


def test_already_complete_regular_race_does_not_change_results():
    data = _fixture(starters=8, month="201711", with_header=True)
    report = audit_nar_official_exceptions(data, month="201711")
    race = report.validated_races[0]
    assert dict(race.win_yen_by_number)[1] == 250
    assert dict(race.win_yen_by_number)[8] == 0
    assert dict(race.place_yen_by_number)[3] == 130
    assert report.audit.status_horse_counts == (("FINISHED", 8),)


def test_payback_contradiction_rejected_without_cherry_picking():
    data = _synthetic_with_status("中止")
    pay = list(csv.reader(StringIO(data["payback"])))
    pay[1][4] = "2"
    data["payback"] = _dump(pay)
    report = audit_nar_official_exceptions(data, month="201711")
    assert report.audit.unresolved_flat_races == 1
    assert report.audit.status_validated_flat_races == 0
    assert report.audit.unresolved_reason_counts == (
        ("NAR_WIN_PAYOUT_BOTH_MISSING_AND_UNEXPECTED", 1),
    )


def test_status_report_is_not_open_authorization_to_fit_or_sell():
    data = _synthetic_with_status("中止")
    audit = audit_nar_official_exceptions(data, month="201711").audit
    assert audit.status == "NAR_OFFICIAL_STATUS_INTERPRETED_NO_PREOFF_PROOF"
    assert audit.complete_flat_outcome_interpretation
    assert not audit.training_authorized
    assert not audit.economic_roi_authorized
    assert not audit.positive_ev_demonstrated


def test_tied_winner_payout_missing_one_is_named_without_horse_identity():
    data = _fixture(starters=8, month="201711", with_header=True)
    rows = list(csv.reader(StringIO(data["horselist"])))
    rows[2][31] = "1"
    data["horselist"] = _dump(rows)
    audited = audit_nar_official_exceptions(data, month="201711").audit
    assert audited.unresolved_reason_counts == (
        ("NAR_WIN_PAYOUT_MISSING_RANK_ONE", 1),
    )


def test_extra_payout_to_nonwinner_is_rejected_without_retrospective_selection():
    data = _fixture(starters=8, month="201711", with_header=True)
    rows = list(csv.reader(StringIO(data["payback"])))
    extra = rows[1].copy()
    extra[4], extra[5] = "2", "250"
    data["payback"] = _dump([rows[0], rows[1], extra])
    audited = audit_nar_official_exceptions(data, month="201711").audit
    assert audited.unresolved_reason_counts == (
        ("NAR_WIN_PAYOUT_TO_NON_RANK_ONE", 1),
    )


def test_official_ticket_on_disqualified_runner_is_quarantined_for_adjudication():
    # Fictional case: the archived final status says 失格 but a published
    # winning return still names that number. Whether adjudication came
    # after betting settlement is NOT knowable from this CSV alone.
    data = _fixture(starters=8, month="201711", with_header=True)
    rows = list(csv.reader(StringIO(data["horselist"])))
    rows[1][31] = ""
    rows[1][33] = "失格"
    for i in range(2, 9):
        rows[i][31] = str(i - 1)
    data["horselist"] = _dump(rows)
    report = audit_nar_official_exceptions(data, month="201711")
    assert report.audit.unresolved_reason_counts == (
        ("NAR_WIN_PAYOUT_TO_DISQUALIFIED_STATUS", 1),
    )
    assert not report.audit.complete_flat_outcome_interpretation
    assert not report.audit.economic_roi_authorized
    assert not report.audit.positive_ev_demonstrated


@pytest.mark.parametrize(("marker", "expected_shape"), [
    ("", "BOTH_FIELDS_BLANK_ONE_HORSE"),
    ("取止", "KNOWN_RACE_CANCEL_OR_NON_ESTABLISHED_MARKER"),
    ("競走不成立", "KNOWN_RACE_CANCEL_OR_NON_ESTABLISHED_MARKER"),
    ("未定義の状態", "UNRECOGNIZED_NONEMPTY_STATUS_MARKER"),
])
def test_unknown_finish_reason_is_safely_split_by_official_marker(marker, expected_shape):
    fake = _synthetic_with_status(marker)
    audit = audit_nar_official_exceptions(fake, month="201711").audit
    assert audit.unresolved_reason_counts == (
        ("NAR_BLANK_WITHOUT_OFFICIAL_STATUS", 1),
    )
    assert audit.ambiguous_finish_pattern_counts == ((expected_shape, 1),)
    assert audit.status_validated_flat_races == 0
    assert not audit.training_authorized
    assert not audit.economic_roi_authorized


@pytest.mark.parametrize(("n", "category"), [
    (2, "BOTH_FIELDS_BLANK_TWO_OR_THREE_HORSES"),
    (3, "BOTH_FIELDS_BLANK_TWO_OR_THREE_HORSES"),
    (4, "BOTH_FIELDS_BLANK_FOUR_OR_MORE_HORSES"),
])
def test_multiple_horses_missing_rank_and_margin_remain_one_unresolved_race(n, category):
    data = _fixture(starters=8, month="201711", with_header=True)
    rows = list(csv.reader(StringIO(data["horselist"])))
    for row in rows[-n:]:
        row[31] = ""
        row[33] = ""
    data["horselist"] = _dump(rows)
    report = audit_nar_official_exceptions(data, month="201711").audit
    assert report.unresolved_flat_races == 1
    assert report.ambiguous_finish_pattern_counts == ((category, 1),)
    assert not report.economic_roi_authorized
