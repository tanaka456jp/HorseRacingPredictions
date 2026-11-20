"""Fictional NAR CSV only: no private licensed rows or training."""
from __future__ import annotations

from dataclasses import replace
from collections import Counter

import pytest

from horse_racing_predictions.nar_official_zip_probe import UnsafeNarSource
from horse_racing_predictions.nar_official_exception_audit import (
    audit_nar_official_exceptions,
)
from horse_racing_predictions.nar_status_aware_training_labels import (
    derive_nar_status_aware_outcome_labels,
)
from test_nar_published_result_normalizer import _fixture
from test_nar_official_exception_audit import _synthetic_with_status


def _labels(sample):
    report = audit_nar_official_exceptions(sample, month="201711")
    return derive_nar_status_aware_outcome_labels(report)


def test_fictional_regular_race_retains_all_winner_and_place_labels():
    batch = _labels(_fixture(month="201711", with_header=True))
    a = batch.audit
    assert a.source_races == a.in_scope_flat_races == a.validated_flat_races == 1
    assert a.unresolved_flat_races == 0
    assert a.labeled_runner_rows == a.observed_roster_rows == 8
    assert a.official_started_rows == a.official_finished_rows == 8
    assert (a.excluded_scratch_rows, a.excluded_refunded_rows,
            a.unknown_disqualification_rows) == (0, 0, 0)
    assert sum(x.win_label for x in batch.labels) == 1
    assert sum(x.place_label for x in batch.labels) == 3
    assert all(x.usable_as_preoff_feature is False for x in batch.labels)
    assert all(x.prior_start_increment == 1 for x in batch.labels)
    assert not a.model_training_authorized
    assert not a.realized_roi_authorized
    assert not a.positive_expected_value_demonstrated


@pytest.mark.parametrize(("marker", "status", "start", "offered", "win_label",
                          "rows_labeled", "placers"), [
    ("取消", "SCRATCH_NOT_OFFERED", 0, False, None, 7, 2),
    ("除外", "EXCLUDED_REFUND", 0, True, None, 7, 3),
    ("中止", "DNF_NO_REFUND", 1, True, 0, 8, 3),
    ("失格", "DISQUALIFIED_REVIEW", 1, True, None, 7, 3),
])
def test_status_aware_training_labels_do_not_turn_scratch_refund_or_dq_to_losses(
    marker, status, start, offered, win_label, rows_labeled, placers,
):
    batch = _labels(_synthetic_with_status(
        marker, only_two_placers=(marker == "取消")
    ))
    a = batch.audit
    assert a.observed_roster_rows == 8
    assert a.labeled_runner_rows == rows_labeled
    assert a.official_started_rows == 7 + start
    assert a.official_finished_rows == 7
    assert (a.excluded_scratch_rows + a.excluded_refunded_rows
            + a.unknown_disqualification_rows) == 8 - rows_labeled
    horse = [label for label in batch.labels if label.horse_number == 8][0]
    assert horse.status == status
    assert horse.started_race == bool(start)
    assert horse.prior_start_increment == start
    assert horse.betting_option_offered is offered
    assert horse.win_label is win_label
    assert horse.place_label is win_label
    assert horse.prior_numeric_rank_observed is False
    assert horse.official_finish_rank is None
    assert sum(label.place_label or 0 for label in batch.labels) == placers
    assert not a.model_training_authorized
    assert not a.positive_expected_value_demonstrated


def test_invalid_race_remains_in_denominator_not_posthoc_excluded_from_profit():
    original = _synthetic_with_status("中止")
    data = dict(original)
    import csv
    from io import StringIO
    rows = list(csv.reader(StringIO(data["payback"])))
    rows[1][4] = "2"
    sink = StringIO(newline="")
    csv.writer(sink).writerows(rows)
    data["payback"] = sink.getvalue()
    official = audit_nar_official_exceptions(data, month="201711")
    batch = derive_nar_status_aware_outcome_labels(official)
    assert batch.audit.source_races == 1
    assert batch.audit.validated_flat_races == 0
    assert batch.audit.unresolved_flat_races == 1
    assert batch.audit.observed_roster_rows == 0
    assert batch.labels == ()
    assert not batch.audit.realized_roi_authorized


def test_corrupted_research_authorization_cannot_launder_unverified_source():
    sample = _fixture(month="201711", with_header=True)
    report = audit_nar_official_exceptions(sample, month="201711")
    for alteration in (
        {"training_authorized": True},
        {"economic_roi_authorized": True},
        {"positive_ev_demonstrated": True},
        {"source_bytes_exported": True},
        {"status_validated_flat_races": 2},
        {"unresolved_flat_races": 1},
        {"source_races": 2},
    ):
        corrupt = replace(report, audit=replace(report.audit, **alteration))
        with pytest.raises(UnsafeNarSource, match="NAR_STATUS_LABEL_SOURCE_AUDIT_INVALID"):
            derive_nar_status_aware_outcome_labels(corrupt)


def test_duplicate_identity_and_inconsistent_payout_mapping_block_labels():
    report = audit_nar_official_exceptions(
        _fixture(month="201711", with_header=True), month="201711",
    )
    race = report.validated_races[0]
    duplicated = replace(race, status_by_number=(
        race.status_by_number[0], race.status_by_number[0],
        *race.status_by_number[2:],
    ))
    altered = replace(report, validated_races=(duplicated,))
    with pytest.raises(UnsafeNarSource, match="NAR_STATUS_LABEL_ROSTER_MISMATCH"):
        derive_nar_status_aware_outcome_labels(altered)

    fake = replace(
        race, win_yen_by_number=tuple(
            (n, None if n == 2 else p)
            for n, p in race.win_yen_by_number
        ),
    )
    altered = replace(report, validated_races=(fake,))
    with pytest.raises(UnsafeNarSource, match="NAR_STATUS_LABEL_FINISH_INVALID"):
        derive_nar_status_aware_outcome_labels(altered)


def test_month_label_audit_does_not_expose_source_names():
    batch = _labels(_synthetic_with_status("除外"))
    assert "架空" not in repr(batch)
    assert "20171114" not in repr(batch)
    assert "架空" not in repr(batch.audit)
    assert not hasattr(batch.audit, "odds")
    assert not hasattr(batch.audit, "popularity")
    assert not hasattr(batch.audit, "win_return_yen")
    assert Counter(x.status for x in batch.labels) == {
        "FINISHED": 7, "EXCLUDED_REFUND": 1,
    }
