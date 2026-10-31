"""Synthetic-only tests for the local 2017–2024 NAR research-fold gate."""
from pathlib import Path
import zipfile

import pytest

from horse_racing_predictions.nar_multiyear_readiness import (
    check_nar_multiyear_local,
)
from horse_racing_predictions.nar_official_zip_probe import UnsafeNarSource
from test_nar_prior_day_features import _month
from test_nar_published_result_normalizer import _fixture


def _archive(tmp_path, month):
    archive = tmp_path / f"{month}_1730041000_race.zip"
    race = _month(month)
    payout = _fixture(month=month)["payback"]
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for kind, source in {**race, "payback": payout}.items():
            zf.writestr(f"{month}_{kind}.csv", source.encode("cp932"))
    return archive


def test_two_licensed_fictional_months_report_missing_94_months(tmp_path):
    january = _archive(tmp_path, "202401")
    february = _archive(tmp_path, "202402")
    untouched = january.read_bytes(), february.read_bytes()
    report = check_nar_multiyear_local(
        [february, january], personal_private_permission_confirmed=True,
    )
    assert report.status == "NAR_PARTIAL_MONTH_COVERAGE_NO_REAL_ROI_INFERENCE"
    assert report.observed_months == 2
    assert report.required_months == 96
    assert report.missing_months == 94
    assert report.source_races == 2
    assert report.reconstructed_target_races == 2
    assert report.reconstructed_runner_rows == 16
    assert report.fit_2017_2021_races == 0
    assert report.tune_2022_races == 0
    assert report.unseen_2023_2024_races == 2
    assert not report.training_approved
    assert not report.official_payout_roi_demonstrated
    assert not report.immutable_pre_event_forecast_verified
    assert not report.note_publication_authorized
    assert (january.read_bytes(), february.read_bytes()) == untouched
    assert str(january) not in repr(report)


def test_pre2025_protected_holdout_rejected(tmp_path):
    archive = _archive(tmp_path, "202502")
    with pytest.raises(UnsafeNarSource, match="NAR_MONTH_OUTSIDE_PRE2025_RESEARCH_WINDOW"):
        check_nar_multiyear_local(
            [archive], personal_private_permission_confirmed=True,
        )


def test_repeated_source_path_must_not_be_double_counted(tmp_path):
    archive = _archive(tmp_path, "202401")
    with pytest.raises(UnsafeNarSource, match="NAR_EXPLICIT_APPROVED_MONTHLY_SOURCES_REQUIRED"):
        check_nar_multiyear_local(
            [archive, archive], personal_private_permission_confirmed=True,
        )


def test_missing_operator_confirmation_blocks(tmp_path):
    archive = _archive(tmp_path, "202401")
    with pytest.raises(UnsafeNarSource, match="NAR_EXPLICIT_APPROVED_MONTHLY_SOURCES_REQUIRED"):
        check_nar_multiyear_local(
            [archive], personal_private_permission_confirmed=False,
        )


def test_no_directory_auto_discovery(tmp_path):
    _archive(tmp_path, "202401")
    with pytest.raises(UnsafeNarSource):
        check_nar_multiyear_local(
            [tmp_path], personal_private_permission_confirmed=True,
        )


def test_two_different_files_for_same_month_blocked(tmp_path):
    a = _archive(tmp_path, "202401")
    b = tmp_path / "202401_1730041001_race.zip"
    b.write_bytes(a.read_bytes())
    with pytest.raises(UnsafeNarSource, match="NAR_DUPLICATE_OR_OUTSIDE_RESEARCH_MONTH"):
        check_nar_multiyear_local(
            [a, b], personal_private_permission_confirmed=True,
        )


def test_price_mismatch_blocks_all_roi_not_only_bad_race(tmp_path):
    a = _archive(tmp_path, "202401")
    b = _archive(tmp_path, "202402")
    raw = _fixture(month="202402")
    # A missing official payback record is not a losing 100JPY bet.
    import csv
    from io import StringIO
    data = list(csv.reader(StringIO(raw["payback"])))
    data[0][4] = "2"  # actual winner is horse #1
    stream = StringIO(newline="")
    csv.writer(stream).writerows(data)
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as zf:
        for kind, source in {**_month("202402"), "payback": stream.getvalue()}.items():
            zf.writestr(f"202402_{kind}.csv", source.encode("cp932"))
    with pytest.raises(UnsafeNarSource, match="NAR_MULTIMONTH_HAS_EXCLUDED_RACES_ROI_BLOCKED"):
        check_nar_multiyear_local(
            [a, b], personal_private_permission_confirmed=True,
        )
