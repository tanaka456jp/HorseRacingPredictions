"""Fictional ZIP-directory fixtures only; no NAR source downloads."""
from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

from horse_racing_predictions.nar_official_zip_probe import (
    UnsafeNarSource, inspect_nar_monthly_zip_structure,
)


def _fixture(tmp_path, *, month="202401", kinds=("racelist", "horselist", "payback")):
    archive = tmp_path / f"{month}_1730041000_race.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as out:
        for kind in kinds:
            out.writestr(f"{month}_{kind}.csv", "FICTIONAL,COLUMN\n1,2\n")
    return archive


def test_offline_three_csv_candidate_is_not_training_license(tmp_path):
    archive = _fixture(tmp_path)
    result = inspect_nar_monthly_zip_structure(archive)
    assert result.status == "NAR_OFFICIAL_FORMAT_CANDIDATE_RIGHTS_AND_ROWS_UNVERIFIED"
    assert result.source_month == "202401"
    assert result.csv_files == 3
    assert result.race_list_present
    assert result.entry_list_present
    assert result.settlement_present
    assert not result.local_operator_permission_reviewed
    assert not result.actual_rights_independently_verified
    assert not result.opened_source_csv_contents
    assert not result.historical_pre_event_snapshots_verified
    assert not result.eligible_for_training
    assert not result.eligible_for_real_roi
    assert not result.auto_download_enabled
    assert not result.note_publication_authorized
    assert str(archive) not in repr(result)


@pytest.mark.parametrize("month", ["202412", "201701", "199801"])
def test_pre2025_official_month_year_range(tmp_path, month):
    assert inspect_nar_monthly_zip_structure(_fixture(tmp_path, month=month)).source_month == month


@pytest.mark.parametrize("month", ["202501", "202610", "202413", "199712"])
def test_post2024_or_invalid_month_is_blocked(tmp_path, month):
    with pytest.raises(UnsafeNarSource):
        inspect_nar_monthly_zip_structure(_fixture(tmp_path, month=month))


def test_missing_race_payback_file_blocks(tmp_path):
    archive = _fixture(tmp_path, kinds=("racelist", "horselist"))
    with pytest.raises(UnsafeNarSource, match="NAR_ARCHIVE_MEMBER_COUNT_INVALID"):
        inspect_nar_monthly_zip_structure(archive)


def test_archive_with_unexpected_csv_rejected(tmp_path):
    archive = _fixture(tmp_path)
    with zipfile.ZipFile(archive, "a") as out:
        out.writestr("202401_odds.csv", "FICTITIOUS\n")
    with pytest.raises(UnsafeNarSource, match="NAR_UNEXPECTED_CSV_MEMBER"):
        inspect_nar_monthly_zip_structure(archive)


def test_zip_traversal_prohibited_without_any_extraction(tmp_path):
    archive = _fixture(tmp_path)
    with zipfile.ZipFile(archive, "a") as out:
        out.writestr("../PRIVATE.csv", "sensitive\n")
    with pytest.raises(UnsafeNarSource, match="NAR_NONFLAT_ARCHIVE_MEMBER"):
        inspect_nar_monthly_zip_structure(archive)
    assert not (tmp_path.parent / "PRIVATE.csv").exists()


def test_wrong_month_in_members_rejected(tmp_path):
    archive = _fixture(tmp_path)
    with zipfile.ZipFile(archive, "a") as out:
        out.writestr("202402_payback.csv", "FICTIONAL\n")
    with pytest.raises(UnsafeNarSource, match="NAR_UNEXPECTED_CSV_MEMBER"):
        inspect_nar_monthly_zip_structure(archive)


def test_damaged_zip_rejected_privately(tmp_path):
    path = tmp_path / "202401_1730041000_race.zip"
    path.write_bytes(b"NOT A REAL ZIP")
    with pytest.raises(UnsafeNarSource, match="NAR_ARCHIVE_UNREADABLE"):
        inspect_nar_monthly_zip_structure(path)


def test_existing_jravan_archive_folder_is_not_an_alternative(tmp_path):
    base = tmp_path / "JRA-VAN"
    base.mkdir()
    archive = _fixture(base)
    with pytest.raises(UnsafeNarSource, match="NAR_UNRELATED_PROTECTED_ARCHIVE_FORBIDDEN"):
        inspect_nar_monthly_zip_structure(archive)


def test_str_url_cannot_be_used_as_source():
    with pytest.raises(UnsafeNarSource, match="NAR_ABSOLUTE_LOCAL_ZIP_REQUIRED"):
        inspect_nar_monthly_zip_structure("https://www.keiba.go.jp/foo.zip")


def test_symbolic_link_refused(tmp_path):
    real = _fixture(tmp_path)
    link = tmp_path / "202401_1730041001_race.zip"
    try:
        link.symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("symlink unavailable")
    with pytest.raises(UnsafeNarSource, match="NAR_UNTRUSTED_ARCHIVE_PATH"):
        inspect_nar_monthly_zip_structure(link)
