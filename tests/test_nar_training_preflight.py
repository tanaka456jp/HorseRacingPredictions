"""All NAR preflight data are fictional one-race ZIP fixtures."""
from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

import pytest

from horse_racing_predictions.nar_training_preflight import (
    diagnose_nar_training_folder,
)
from horse_racing_predictions.nar_official_zip_probe import UnsafeNarSource
from test_nar_local_monthly_intake import _make_zip
from test_nar_published_result_normalizer import _fixture
from test_nar_official_exception_audit import _synthetic_with_status


def _bad_payback(month):
    sample = _fixture(month=month)
    rows = list(csv.reader(StringIO(sample["payback"])))
    rows[0][4] = "2"
    buf = StringIO(newline="")
    csv.writer(buf).writerows(rows)
    return buf.getvalue()


def test_partial_two_month_preflight_preserves_all_months_and_anomaly_reasons(tmp_path):
    _make_zip(tmp_path, month="201701")
    _make_zip(tmp_path, month="201702",
              override={"payback": _bad_payback("201702")})
    before = {x.name: x.stat().st_size for x in tmp_path.iterdir()}
    report = diagnose_nar_training_folder(
        tmp_path, personal_private_permission_confirmed=True,
    )
    assert report.months_present == 2
    assert report.months_missing == 70
    assert "201703" in report.missing_month_ids
    assert "201701" not in report.missing_month_ids
    assert report.months_structurally_accepted == 1
    assert report.months_with_unresolved_errors == 1
    assert report.observed_races == 2
    assert report.accepted_flat_races == 1
    assert report.unresolved_flat_races == 1
    assert report.diagnostic[0].month == "201701"
    assert report.diagnostic[1].month == "201702"
    assert report.diagnostic[1].static_reasons == (
        ("NAR_PAYOUT_CONTRADICTS_FINAL_RESULTS", 1),
    )
    assert not report.model_training_performed
    assert not report.payouts_or_roi_evaluated
    assert not report.protected_holdout_opened
    assert not report.data_sent_to_network
    assert not report.all_months_study_eligible
    assert {x.name: x.stat().st_size for x in tmp_path.iterdir()} == before
    assert str(tmp_path) not in repr(report)
    assert "架空馬" not in repr(report)


def test_one_corrupt_zip_does_not_hide_other_month_diagnostics(tmp_path):
    a = _make_zip(tmp_path, month="202201")
    broken = tmp_path / "202202_1730041000_race.zip"
    broken.write_bytes(b"INTENTIONALLY_NOT_A_ZIP")
    _make_zip(tmp_path, month="202203")
    report = diagnose_nar_training_folder(
        tmp_path, personal_private_permission_confirmed=True,
    )
    assert [r.month for r in report.diagnostic] == [
        "202201", "202202", "202203"
    ]
    assert report.months_structurally_accepted == 2
    assert report.months_with_unresolved_errors == 1
    assert report.diagnostic[1].status == "MONTH_SOURCE_REJECTED"
    assert report.diagnostic[1].static_reasons[0][0].startswith("NAR_")
    assert a.is_file()


def test_all_72_fictional_months_full_source_diagnostic(tmp_path):
    for year in range(2017, 2023):
        for month in range(1, 13):
            _make_zip(tmp_path, month=f"{year}{month:02d}")
    report = diagnose_nar_training_folder(
        tmp_path, personal_private_permission_confirmed=True,
    )
    assert report.status == "NAR_72_MONTHS_STRUCTURALLY_READY_FOR_SEPARATE_PRIVATE_REVIEW"
    assert report.months_present == 72
    assert report.months_missing == 0
    assert report.missing_month_ids == ()
    assert report.months_structurally_accepted == 72
    assert report.months_with_unresolved_errors == 0
    assert report.observed_races == 72
    assert report.accepted_flat_races == 72
    assert report.unresolved_flat_races == 0
    assert not report.model_training_performed
    assert not report.actual_rights_independently_verified
    assert not report.all_months_study_eligible


def test_sealed_holdout_zip_never_read_or_indexed(tmp_path):
    _make_zip(tmp_path, month="201701")
    hidden = tmp_path / "202301_1730041000_race.zip"
    hidden.write_bytes(b"HOLDOUT_DATA_MUST_NOT_BE_OPENED")
    with pytest.raises(UnsafeNarSource, match="NAR_MANIFEST_UNEXPECTED_OR_SEALED_ZIP"):
        diagnose_nar_training_folder(
            tmp_path, personal_private_permission_confirmed=True,
        )


def test_user_permission_must_be_explicit(tmp_path):
    _make_zip(tmp_path, month="201701")
    with pytest.raises(UnsafeNarSource, match="NAR_MANIFEST_PERSONAL_PERMISSION_REQUIRED"):
        diagnose_nar_training_folder(
            tmp_path, personal_private_permission_confirmed=False,
        )


def test_no_network_or_user_identity_in_cli_output_contract():
    source = Path("scripts/diagnose_nar_training_months_local.py").read_text(
        encoding="utf-8",
    )
    assert "perMonth" in source
    assert "realDataUploaded" in source
    assert "protectedHoldoutOpened" in source
    assert "horseName" not in source
    assert "raceId" not in source
    assert "requests." not in source
    assert "urllib." not in source


def test_official_status_analysis_resolves_dnf_without_releasing_training(tmp_path):
    """Two fictional monthly ZIPs, not NAR user archives."""
    _make_zip(tmp_path, month="201711",
              override=_synthetic_with_status("中止"))
    _make_zip(tmp_path, month="201712")
    report = diagnose_nar_training_folder(
        tmp_path, personal_private_permission_confirmed=True,
    )
    assert report.months_present == 2
    assert report.months_missing == 70
    assert report.accepted_flat_races == 1
    assert report.unresolved_flat_races == 1
    assert report.status_aware_validated_flat_races == 2
    assert report.status_aware_unresolved_flat_races == 0
    assert report.months_structurally_accepted == 1
    assert report.months_status_aware_complete == 2
    assert report.diagnostic[0].status_aware_validated_flat_races == 1
    assert report.diagnostic[0].status_aware_unresolved_flat_races == 0
    assert report.diagnostic[0].status_aware_reasons == ()
    assert not report.all_months_study_eligible
    assert not report.actual_rights_independently_verified
    assert not report.model_training_performed
    assert not report.payouts_or_roi_evaluated
    assert not report.data_sent_to_network
    assert "架空" not in repr(report)


def test_official_paid_disqualification_must_remain_unresolved(tmp_path):
    """Never conceal the structural conflict observed in real 2017-11."""
    case = _synthetic_with_status("失格")
    pay = list(csv.reader(StringIO(case["payback"])))
    pay[1][4] = "8"
    out = StringIO(newline="")
    csv.writer(out).writerows(pay)
    case["payback"] = out.getvalue()
    _make_zip(tmp_path, month="201711", override=case)
    result = diagnose_nar_training_folder(
        tmp_path, personal_private_permission_confirmed=True,
    )
    assert result.status_aware_validated_flat_races == 0
    assert result.status_aware_unresolved_flat_races == 1
    assert result.months_status_aware_complete == 0
    assert result.diagnostic[0].status_aware_reasons == (
        ("NAR_WIN_PAYOUT_TO_DISQUALIFIED_STATUS", 1),
    )
    assert not result.all_months_study_eligible
    assert not result.payouts_or_roi_evaluated


def test_parallel_status_reconciliation_all_72_fictional_months(tmp_path):
    for year in range(2017, 2023):
        for month in range(1, 13):
            _make_zip(tmp_path, month=f"{year}{month:02d}")
    report = diagnose_nar_training_folder(
        tmp_path, personal_private_permission_confirmed=True,
    )
    assert report.status_aware_validated_flat_races == 72
    assert report.status_aware_unresolved_flat_races == 0
    assert report.months_status_aware_complete == 72
    assert report.all_months_study_eligible is False
