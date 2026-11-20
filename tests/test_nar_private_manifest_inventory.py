"""NAR private 72-month filename inventory using fabricated ZIP names only."""
from __future__ import annotations

from pathlib import Path

import pytest

from horse_racing_predictions.nar_private_manifest_inventory import (
    inventory_private_nar_training_directory,
)
from horse_racing_predictions.nar_official_zip_probe import UnsafeNarSource


def _fake_zip(folder, month, *, suffix="1730041000"):
    source = folder / f"{month}_{suffix}_race.zip"
    source.write_bytes(b"NOT_OPENED_BY_INVENTORY")
    return source


def test_complete_72_months_only_reads_names_not_source_bytes(tmp_path, monkeypatch):
    folder = tmp_path / "nar-licensed"
    folder.mkdir()
    for year in range(2017, 2023):
        for month in range(1, 13):
            _fake_zip(folder, f"{year}{month:02d}")

    # Source byte methods are unusable: the inventory must not open them.
    def forbidden_read(*_args, **_kwargs):
        raise AssertionError("CSV/ZIP bytes must never be opened")

    monkeypatch.setattr(Path, "read_bytes", forbidden_read)
    result = inventory_private_nar_training_directory(
        folder, personal_private_permission_confirmed=True,
    )
    assert result.observed_months == result.required_months == 72
    assert result.missing_months == ()
    assert len(result.absolute_source_paths) == 72
    assert result.absolute_source_paths[0].name.startswith("201701_")
    assert result.absolute_source_paths[-1].name.startswith("202212_")
    assert not result.opened_zip_bytes
    assert not result.contains_newly_downloaded_data
    assert not result.model_training_approved
    assert not result.source_rights_verified_by_software
    assert str(folder) not in repr(result)
    assert "201701_1730041000_race.zip" not in repr(result)


def test_missing_months_are_disclosed_without_opening_sources(tmp_path):
    folder = tmp_path / "nar-licensed"
    folder.mkdir()
    _fake_zip(folder, "201701")
    _fake_zip(folder, "202212")
    result = inventory_private_nar_training_directory(
        folder, personal_private_permission_confirmed=True,
    )
    assert result.observed_months == 2
    assert len(result.missing_months) == 70
    assert "201702" in result.missing_months
    assert "202211" in result.missing_months


def test_2023_holdout_zip_rejected_on_filename_without_opening_it(tmp_path):
    folder = tmp_path / "nar-licensed"
    folder.mkdir()
    _fake_zip(folder, "202301")
    with pytest.raises(UnsafeNarSource, match="NAR_MANIFEST_UNEXPECTED_OR_SEALED_ZIP"):
        inventory_private_nar_training_directory(
            folder, personal_private_permission_confirmed=True,
        )


def test_duplicate_month_versions_are_rejected(tmp_path):
    folder = tmp_path / "nar-licensed"
    folder.mkdir()
    _fake_zip(folder, "201701")
    _fake_zip(folder, "201701", suffix="1730041001")
    with pytest.raises(UnsafeNarSource, match="NAR_MANIFEST_DUPLICATE_MONTH"):
        inventory_private_nar_training_directory(
            folder, personal_private_permission_confirmed=True,
        )


def test_expired_jravan_archive_directory_never_scanned(tmp_path):
    base = tmp_path / "JRA-VAN"
    folder = base / "nar-licensed"
    folder.mkdir(parents=True)
    with pytest.raises(UnsafeNarSource, match="NAR_MANIFEST_UNTRUSTED_DIRECTORY"):
        inventory_private_nar_training_directory(
            folder, personal_private_permission_confirmed=True,
        )


def test_no_recursive_search_or_symlink_reroute(tmp_path):
    folder = tmp_path / "nar-licensed"
    folder.mkdir()
    (folder / "nested").mkdir()
    with pytest.raises(UnsafeNarSource, match="NAR_MANIFEST_RECURSION_FORBIDDEN"):
        inventory_private_nar_training_directory(
            folder, personal_private_permission_confirmed=True,
        )
    (folder / "nested").rmdir()
    source = _fake_zip(folder, "201701")
    link = folder / "201702_1730041000_race.zip"
    try:
        link.symlink_to(source)
    except (NotImplementedError, OSError):
        pytest.skip("symlinks unavailable")
    with pytest.raises(UnsafeNarSource, match="NAR_MANIFEST_SYMLINK_FORBIDDEN"):
        inventory_private_nar_training_directory(
            folder, personal_private_permission_confirmed=True,
        )


def test_no_unapproved_file_inspection(tmp_path):
    folder = tmp_path / "nar-licensed"
    folder.mkdir()
    _fake_zip(folder, "201701")
    with pytest.raises(UnsafeNarSource, match="NAR_MANIFEST_PERSONAL_PERMISSION_REQUIRED"):
        inventory_private_nar_training_directory(
            folder, personal_private_permission_confirmed=False,
        )


def test_manual_cli_requires_explicit_output_location_outside_repo():
    source = Path("scripts/prepare_nar_private_training_manifest_local.py").read_text(
        encoding="utf-8",
    )
    assert "--private-manifest-output" in source
    assert "--write-private-manifest" in source
    assert "output.is_relative_to(Path(__file__).resolve().parents[1])" in source
    assert "output.open(\"x\"" in source
    assert "requests.get" not in source
    assert "urllib" not in source
    assert "zipfile" not in source
