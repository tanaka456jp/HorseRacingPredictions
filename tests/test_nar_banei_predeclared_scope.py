"""Fictional official-schema tests for predeclared Banei venue scope.

Scope is set BEFORE finish or payout. No outcome-based survivor filtering,
provider requests, ZIP uploads, or PC2 archive reads are performed.
"""
from __future__ import annotations

import csv
from io import StringIO
from zipfile import ZipFile

import pytest

from horse_racing_predictions.nar_monthly_coverage_audit import (
    audit_nar_monthly_coverage, select_predeclared_flat_races,
)
from horse_racing_predictions.nar_local_monthly_intake import (
    read_nar_monthly_zip_local, load_nar_monthly_zip_local,
)
from horse_racing_predictions.nar_official_zip_probe import UnsafeNarSource
from horse_racing_predictions.nar_published_result_normalizer import (
    normalize_nar_published_results,
)
from test_nar_published_result_normalizer import _fixture


def _write_rows(rows):
    text = StringIO(newline="")
    csv.writer(text).writerows(rows)
    return text.getvalue()


def _banei_fixture(*, include_payback=False, broken_finish=True):
    data = _fixture(month="202402")
    result = {}
    for kind, raw in data.items():
        rows = list(csv.reader(StringIO(raw)))
        for row in rows:
            row[0] = "帯広"
            row[2] = "4"
            if kind == "racelist":
                row[21] = "ばんえい"
            elif kind == "horselist" and broken_finish:
                row[31] = ""  # invalid outcome MUST NOT affect predeclared scope
        result[kind] = _write_rows(rows)
    if not include_payback:
        result["payback"] = ""
    return result


def _mixed(*, broken_flat=False):
    flat = _fixture(month="202402")
    if broken_flat:
        rows = list(csv.reader(StringIO(flat["payback"])))
        rows[0][4] = "2"  # not actual #1 winner; invalid IN scope
        flat["payback"] = _write_rows(rows)
    banei = _banei_fixture()
    return {kind: flat[kind] + banei[kind] for kind in flat}


def _archive(tmp_path, data):
    path = tmp_path / "202402_1730041000_race.zip"
    with ZipFile(path, "w") as zf:
        for kind, text in data.items():
            zf.writestr(f"202402_{kind}.csv", text.encode("cp932"))
    return path


def test_scope_is_fixed_by_obihiro_track_not_finished_result():
    info = audit_nar_monthly_coverage(_mixed(), month="202402").summary
    assert info.observed_races == 2
    assert info.structurally_accepted_races == 1
    assert info.predeclared_out_of_scope_races == 1
    assert info.unresolved_in_scope_races == 0
    assert info.excluded_races == 1
    assert info.exclusion_reasons == (
        ("NAR_PREDECLARED_BANEI_OUT_OF_SCOPE", 1),
    )
    assert info.complete_month_for_research
    assert not info.valid_economic_roi_sample
    assert not info.approved_for_model_training
    assert not info.positive_ev_demonstrated
    assert info.status == "NAR_MONTH_PREDECLARED_SCOPE_ONLY_PRE_EVENT_UNVERIFIED"


def test_banei_not_in_normalized_flat_results_but_denominator_persists():
    data = _mixed()
    allowed = select_predeclared_flat_races(data, month="202402")
    parsed = normalize_nar_published_results(allowed, month="202402")
    assert parsed.audit.checked_races == 1
    assert parsed.audit.checked_starters == 8
    assert all(race.race_key[0] != "帯広" for race in parsed.races)


def test_local_operator_zip_accepts_only_ex_ante_scope_exclusion(tmp_path):
    path = _archive(tmp_path, _mixed())
    state = read_nar_monthly_zip_local(
        path, personal_private_permission_confirmed=True,
    )
    assert state.observed_races == 2
    assert state.parsed_races == 1
    assert state.predeclared_out_of_scope_races == 1
    assert state.unresolved_in_scope_races == 0
    assert state.excluded_races == 1
    assert not state.ev_demonstrated
    accepted = load_nar_monthly_zip_local(
        path, personal_private_permission_confirmed=True,
    )
    assert accepted.audit.checked_races == 1


def test_real_flat_payout_error_cannot_hide_behind_banei_exclusion(tmp_path):
    mixed = _mixed(broken_flat=True)
    status = audit_nar_monthly_coverage(mixed, month="202402").summary
    assert status.predeclared_out_of_scope_races == 1
    assert status.unresolved_in_scope_races == 1
    assert not status.complete_month_for_research
    assert ("NAR_PAYOUT_CONTRADICTS_FINAL_RESULTS", 1) in status.exclusion_reasons
    with pytest.raises(UnsafeNarSource, match="NAR_FLAT_SCOPE_HAS_UNRESOLVED_RESULTS"):
        select_predeclared_flat_races(mixed, month="202402")
    path = _archive(tmp_path, mixed)
    with pytest.raises(UnsafeNarSource, match="NAR_PAYOUT_CONTRADICTS_FINAL_RESULTS"):
        load_nar_monthly_zip_local(
            path, personal_private_permission_confirmed=True,
        )


def test_only_banei_still_has_no_flat_training_sample():
    data = _banei_fixture()
    report = audit_nar_monthly_coverage(data, month="202402").summary
    assert report.observed_races == 1
    assert report.predeclared_out_of_scope_races == 1
    assert report.unresolved_in_scope_races == 0
    assert report.structurally_accepted_races == 0
    assert not report.complete_month_for_research
    with pytest.raises(UnsafeNarSource, match="NAR_FLAT_SCOPE_HAS_UNRESOLVED_RESULTS"):
        select_predeclared_flat_races(data, month="202402")


def test_other_venue_nonflat_data_is_not_automatically_excluded():
    data = _fixture(month="202402")
    rows = list(csv.reader(StringIO(data["racelist"])))
    rows[0][21] = "障害"
    data["racelist"] = _write_rows(rows)
    report = audit_nar_monthly_coverage(data, month="202402").summary
    assert report.predeclared_out_of_scope_races == 0
    assert report.unresolved_in_scope_races == 1
    assert ("NAR_NONSTANDARD_RACE_TYPE", 1) in report.exclusion_reasons
    assert not report.complete_month_for_research
