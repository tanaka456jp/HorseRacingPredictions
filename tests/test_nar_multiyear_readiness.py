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
    assert report.status == "NAR_PARTIAL_MONTH_COVERAGE_SEALED_MONTHS_UNOPENED"
    assert report.observed_months == 2
    assert report.required_months == 96
    assert report.missing_months == 94
    assert report.source_races == 0
    assert report.reconstructed_target_races == 0
    assert report.reconstructed_runner_rows == 0
    assert report.sealed_2023_2024_months_listed == 2
    assert not report.sealed_2023_2024_zip_bytes_opened
    assert report.fit_2017_2021_races == 0
    assert report.tune_2022_races == 0
    assert report.unseen_2023_2024_races == 0
    assert not report.training_approved
    assert not report.official_payout_roi_demonstrated
    assert not report.immutable_pre_event_forecast_verified
    assert not report.note_publication_authorized
    assert (january.read_bytes(), february.read_bytes()) == untouched
    assert str(january) not in repr(report)


def test_pre2025_protected_holdout_rejected(tmp_path):
    archive = _archive(tmp_path, "202502")
    with pytest.raises(UnsafeNarSource, match="NAR_DUPLICATE_OR_OUTSIDE_RESEARCH_MONTH"):
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
    a = _archive(tmp_path, "202101")
    b = _archive(tmp_path, "202102")
    raw = _fixture(month="202102")
    # A missing official payback record is not a losing 100JPY bet.
    import csv
    from io import StringIO
    data = list(csv.reader(StringIO(raw["payback"])))
    data[0][4] = "2"  # actual winner is horse #1
    stream = StringIO(newline="")
    csv.writer(stream).writerows(data)
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as zf:
        for kind, source in {**_month("202102"), "payback": stream.getvalue()}.items():
            zf.writestr(f"202102_{kind}.csv", source.encode("cp932"))
    with pytest.raises(UnsafeNarSource, match="NAR_MULTIMONTH_HAS_EXCLUDED_RACES_ROI_BLOCKED"):
        check_nar_multiyear_local(
            [a, b], personal_private_permission_confirmed=True,
        )


def test_even_corrupted_2023_2024_holdout_bytes_are_never_opened(tmp_path, monkeypatch):
    # This is a malformed ZIP, but the catalogue must inspect only its name.
    sealed = tmp_path / "202303_1730041000_race.zip"
    sealed.write_bytes(b"SEALED_NO_FORMAT_OR_RESULTS_READ")
    import horse_racing_predictions.nar_multiyear_readiness as module
    original = module._read_nar_local_csv_texts

    def assert_not_read(path, **kwargs):
        if path.name.startswith("2023") or path.name.startswith("2024"):
            raise AssertionError("2023-24 holdout contents MUST remain unopened")
        return original(path, **kwargs)

    monkeypatch.setattr(module, "_read_nar_local_csv_texts", assert_not_read)
    report = check_nar_multiyear_local(
        [sealed], personal_private_permission_confirmed=True,
    )
    assert report.sealed_2023_2024_months_listed == 1
    assert report.unseen_2023_2024_races == 0
    assert report.missing_months == 95
    assert not report.sealed_2023_2024_zip_bytes_opened
    assert not report.final_holdout_opened


def test_training_month_remains_readable_but_sealed_period_does_not(tmp_path):
    training = _archive(tmp_path, "202101")
    sealed = tmp_path / "202401_1730041000_race.zip"
    sealed.write_bytes(b"SEALED_UNREAD_DATA")
    report = check_nar_multiyear_local(
        [sealed, training], personal_private_permission_confirmed=True,
    )
    assert report.fit_2017_2021_races == 1
    assert report.tune_2022_races == 0
    assert report.source_races == 1
    assert report.reconstructed_target_races == 1
    assert report.sealed_2023_2024_months_listed == 1
    assert report.unseen_2023_2024_races == 0
