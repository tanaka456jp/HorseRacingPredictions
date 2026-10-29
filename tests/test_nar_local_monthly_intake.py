"""Local monthly NAR ZIP intake: all contents are synthetic fixtures."""
from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

from horse_racing_predictions.nar_local_monthly_intake import (
    read_nar_monthly_zip_local,
)
from horse_racing_predictions.nar_official_zip_probe import UnsafeNarSource
from test_nar_published_result_normalizer import _fixture


def _make_zip(tmp_path: Path, *, month="202402", starters=8,
              override=None, extra=None) -> Path:
    source = tmp_path / f"{month}_1730041000_race.zip"
    parts = _fixture(month=month, starters=starters)
    if override:
        parts.update(override)
    with zipfile.ZipFile(source, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for kind, content in parts.items():
            zf.writestr(f"{month}_{kind}.csv", content.encode("cp932"))
        if extra is not None:
            zf.writestr(extra[0], extra[1])
    return source


@pytest.mark.parametrize("starters", [5, 8, 18])
def test_authorized_local_fictional_zip_full_integrity(tmp_path, starters):
    archive = _make_zip(tmp_path, starters=starters)
    before = archive.read_bytes()
    result = read_nar_monthly_zip_local(
        archive, personal_private_permission_confirmed=True,
    )
    assert result.parsed_races == 1
    assert result.parsed_starters == starters
    assert result.min_year == result.max_year == 2024
    assert result.status == "NAR_LOCAL_FINAL_RESULTS_VALIDATED_NO_PRE_EVENT_PROOF"
    assert not result.source_rights_verified_by_software
    assert not result.pre_event_snapshot_available
    assert not result.authorized_for_training_by_this_check
    assert not result.ev_demonstrated
    assert not result.note_publication_authorized
    assert not result.network_accessed
    assert archive.read_bytes() == before
    assert "架空馬" not in repr(result)
    assert str(archive) not in repr(result)


def test_permission_flag_is_mandatory_before_zip_content_read(tmp_path):
    archive = _make_zip(tmp_path)
    with pytest.raises(UnsafeNarSource, match="NAR_PERSONAL_RESEARCH_PERMISSION_REQUIRED"):
        read_nar_monthly_zip_local(
            archive, personal_private_permission_confirmed=False,
        )


def test_unsupported_race_requires_review_not_silent_omission(tmp_path):
    parts = _fixture(starters=8)
    # Empty payback is a hard failure, not zero-payout real loss.
    import csv
    from io import StringIO
    raw = list(csv.reader(StringIO(parts["payback"])))
    raw[0][4] = ""
    raw[0][5] = ""
    dest = StringIO(newline="")
    csv.writer(dest).writerows(raw)
    archive = _make_zip(tmp_path, override={"payback": dest.getvalue()})
    with pytest.raises(UnsafeNarSource, match="NAR_PAYOUT_CONTRADICTS_FINAL_RESULTS"):
        read_nar_monthly_zip_local(archive, personal_private_permission_confirmed=True)


def test_post2024_protected_month_is_refused_without_csv_read(tmp_path):
    archive = _make_zip(tmp_path, month="202502")
    with pytest.raises(UnsafeNarSource, match="NAR_MONTH_OUTSIDE_PRE2025_RESEARCH_WINDOW"):
        read_nar_monthly_zip_local(archive, personal_private_permission_confirmed=True)


def test_csv_member_zip_bomb_is_refused_by_size_cap(tmp_path):
    archive = _make_zip(tmp_path)
    # No giant archive allocation needed: source content uses compressible bytes
    # but is still larger than the 16 MB per-member cap.
    month = "202402"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{month}_horselist.csv", "X" * 16_000_001)
        for kind in ("racelist", "payback"):
            zf.writestr(f"{month}_{kind}.csv", _fixture()[kind])
    with pytest.raises(UnsafeNarSource, match="NAR_LOCAL_CSV_BYTE_CAP"):
        read_nar_monthly_zip_local(archive, personal_private_permission_confirmed=True)


def test_bad_member_crc_is_not_silently_accepted(tmp_path):
    archive = _make_zip(tmp_path)
    source = archive.read_bytes()
    # Truncation of end-of-central-directory always corrupts the ZIP.
    archive.write_bytes(source[:-7])
    with pytest.raises(UnsafeNarSource):
        read_nar_monthly_zip_local(archive, personal_private_permission_confirmed=True)


def test_cli_has_explicit_local_opt_in_and_no_network():
    source = Path("scripts/inspect_nar_monthly_results_local.py").read_text(
        encoding="utf-8",
    )
    assert "--confirm-personal-private-nar-permission" in source
    assert "--local-monthly-race-zip" in source
    assert "newDataDownloaded" in source
    assert "network" not in source.lower() or "no network" in source.lower()
    assert "urlopen" not in source
    assert "requests.get" not in source
