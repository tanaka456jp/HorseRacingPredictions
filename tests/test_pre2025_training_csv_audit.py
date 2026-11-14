"""Fictional-only chronology gate tests; no local JRA archive accessed."""
from __future__ import annotations

from datetime import date
from hashlib import sha256
from pathlib import Path

import pytest

from horse_racing_predictions.pre2025_training_csv_audit import (
    UnsafeTrainingSource, audit_pre2025_training_csv,
)

HEADER = "race_id,race_date,horse_name,finish_position,win_odds\n"


def _file(tmp_path, rows, *, encoding="utf-8"):
    path = tmp_path / "fictional_training.csv"
    path.write_text(HEADER + "".join(rows), encoding=encoding)
    return path


def test_full_file_pre2025_chronology_is_only_structure_not_licence(tmp_path):
    p = _file(tmp_path, [
        "fictional1,2022-01-08,架空馬,1,3.8\n",
        "fictional2,2024-12-31,テスト馬,2,4.0\n",
    ])
    a = audit_pre2025_training_csv(p)
    assert a.checked_rows == 2
    assert a.min_year == 2022 and a.max_year == 2024
    assert a.sha256 == sha256(p.read_bytes()).hexdigest()
    assert a.all_source_dates_pre2025
    assert a.status == "FULL_SOURCE_CHRONOLOGY_VERIFIED_PRIVATE_RIGHTS_PENDING"
    assert a.source_training_approved_by_this_audit is False
    assert a.independently_licensed_research_authorized is False
    assert a.public_redistribution_authorized is False
    assert a.protected_holdout_used_as_training is False
    assert "架空馬" not in str(a)
    assert "テスト馬" not in str(a)
    assert str(p) not in str(a)


def test_post2024_row_after_256k_sample_rejected_entire_file(tmp_path):
    earlier = ["F,2024-01-01,MOCK,2,3.0\n"] * 14000
    p = _file(tmp_path, earlier + ["FINAL,2026-10-25,SECRET,1,1.2\n"])
    assert p.stat().st_size > 262144
    with pytest.raises(UnsafeTrainingSource, match="PROTECTED_HOLDOUT_IN_SOURCE"):
        audit_pre2025_training_csv(p)


def test_even_outside_training_window_2025_is_rejected(tmp_path):
    p = _file(tmp_path, [
        "A,2018-04-02,TEST,1,3.1\n",
        "B,2025-01-01,UNSAFE,1,3.2\n",
    ])
    with pytest.raises(UnsafeTrainingSource, match="PROTECTED_HOLDOUT_IN_SOURCE"):
        audit_pre2025_training_csv(p)


@pytest.mark.parametrize("bad", [
    "2024notadate", "2024-13-02", "2024-02-30", "",
    "1900-01-01", "20240199", " 2024-01-01garbage "
])
def test_invalid_dates_not_trusted_by_prefix(tmp_path, bad):
    p = _file(tmp_path, [f"F,{bad},MOCK,2,3.0\n"])
    with pytest.raises(UnsafeTrainingSource, match="INVALID_SOURCE_DATE"):
        audit_pre2025_training_csv(p)


def test_cp932_csv_support_and_no_identity_leak(tmp_path):
    p = _file(tmp_path, ["A,2024/01/04,京都の架空馬,1,5.1\n"], encoding="cp932")
    a = audit_pre2025_training_csv(p)
    assert a.checked_rows == 1
    assert a.max_year == 2024
    assert "京都の架空馬" not in repr(a)


@pytest.mark.parametrize("header", [
    "race_id,race_date,horse_name,finish_position,race_date\n",
    "race_id,race_date,horse_name\n",
    "race_id,race_date,horse_name,finish_position,レース日付\n",
    "race_id,race_date,horse_name,finish_position,finish_position\n",
])
def test_bad_duplicate_or_ambiguous_headers_rejected(tmp_path, header):
    p = tmp_path / "duplicate.csv"
    p.write_text(header + "F,2024-01-01,TEST,1\n", encoding="utf-8")
    with pytest.raises(UnsafeTrainingSource):
        audit_pre2025_training_csv(p)


def test_malformed_rows_and_blank_identity_rejected(tmp_path):
    p = _file(tmp_path, ["F,2024-01-01,MOCK,1\n"])
    with pytest.raises(UnsafeTrainingSource, match="MALFORMED_SOURCE_ROW"):
        audit_pre2025_training_csv(p)
    p = _file(tmp_path, [",2024-01-01,MOCK,1,2.0\n"])
    with pytest.raises(UnsafeTrainingSource, match="SOURCE_IDENTITY_MISSING"):
        audit_pre2025_training_csv(p)


def test_symlink_to_other_dataset_never_read(tmp_path):
    source = _file(tmp_path, ["F,2024-01-01,SECRET,1,2.0\n"])
    link = tmp_path / "hidden.csv"
    try:
        link.symlink_to(source)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    with pytest.raises(UnsafeTrainingSource, match="UNTRUSTED_SOURCE_PATH"):
        audit_pre2025_training_csv(link)


def test_no_content_in_any_rejection_message(tmp_path):
    p = _file(tmp_path, ["PRIVATE_RACE,2025-10-25,SECRET_HORSE,1,1.0\n"])
    try:
        audit_pre2025_training_csv(p)
    except UnsafeTrainingSource as e:
        assert "SECRET_HORSE" not in str(e)
        assert "PRIVATE_RACE" not in str(e)
        assert str(p) not in str(e)
    else:
        pytest.fail("should block protected period")
