"""Fictional-only multi-year cohort admission tests.

No real racing files, JV-Link data or PC2 archive are read.
"""
from pathlib import Path

import pytest

from horse_racing_predictions.pre2025_multiyear_csv_audit import (
    audit_multiyear_pre2025_csvs,
)
from horse_racing_predictions.pre2025_training_csv_audit import (
    UnsafeTrainingSource,
)


def _year_csv(root: Path, year: int, *, race_id: str,
              horse: str = "MOCK", encoding: str = "utf-8") -> Path:
    p = root / f"synthetic_{year}_{race_id}.csv"
    p.write_text(
        "race_id,race_date,horse_name,finish_position\n"
        f"{race_id},{year}-08-01,{horse},1\n"
        f"{race_id},{year}-08-01,{horse}2,2\n",
        encoding=encoding,
    )
    return p


def test_distinct_years_offline_only(tmp_path):
    a = _year_csv(tmp_path, 2017, race_id="FAKE17")
    b = _year_csv(tmp_path, 2022, race_id="FAKE22")
    c = _year_csv(tmp_path, 2024, race_id="FAKE24")
    result = audit_multiyear_pre2025_csvs([c, a, b])
    assert result.source_files == 3
    assert result.source_rows == 6
    assert result.source_years == (2017, 2022, 2024)
    assert result.unique_races == 3
    assert not result.approved_for_training_by_this_audit
    assert not result.independently_verified_research_rights
    assert not result.publication_authorized
    assert not result.protected_2025_2026_holdout_opened
    assert "FAKE17" not in str(result)
    assert str(a) not in str(result)


def test_repeat_race_id_across_year_shards_rejected(tmp_path):
    a = _year_csv(tmp_path, 2018, race_id="SAME")
    b = _year_csv(tmp_path, 2019, race_id="SAME")
    with pytest.raises(UnsafeTrainingSource, match="COHORT_CROSS_SHARD_RACE_COLLISION"):
        audit_multiyear_pre2025_csvs([a, b])


def test_mixed_year_file_fails_even_when_pre2025(tmp_path):
    a = _year_csv(tmp_path, 2018, race_id="A")
    b = tmp_path / "mixed.csv"
    b.write_text("race_id,race_date,horse_name,finish_position\n"
                 "B,2020-01-01,M1,1\nC,2021-01-01,M2,2\n")
    with pytest.raises(UnsafeTrainingSource, match="COHORT_YEAR_PARTITION_INVALID"):
        audit_multiyear_pre2025_csvs([a, b])


def test_duplicate_year_partition_rejected(tmp_path):
    a = _year_csv(tmp_path, 2020, race_id="A")
    b = _year_csv(tmp_path, 2020, race_id="B")
    with pytest.raises(UnsafeTrainingSource, match="COHORT_YEAR_PARTITION_DUPLICATED"):
        audit_multiyear_pre2025_csvs([a, b])


def test_full_source_protected_holdout_not_sampled(tmp_path):
    a = _year_csv(tmp_path, 2017, race_id="SAFE")
    b = _year_csv(tmp_path, 2024, race_id="LATE")
    with b.open("a", encoding="utf-8") as handle:
        handle.write("HIDDEN,2025-01-01,HORSE,1\n")
    with pytest.raises(UnsafeTrainingSource, match="PROTECTED_HOLDOUT_IN_SOURCE"):
        audit_multiyear_pre2025_csvs([a, b])


def test_marked_staging_parent_refused_even_in_nested_directory(tmp_path):
    approved = _year_csv(tmp_path, 2017, race_id="SAFE")
    staging = tmp_path / "staging"
    nested = staging / "deep"
    nested.mkdir(parents=True)
    (staging / "REVIEW_ONLY_NOT_APPROVED_FOR_TRAINING").write_text("NO")
    candidate = _year_csv(nested, 2018, race_id="PRIVATE")
    with pytest.raises(UnsafeTrainingSource, match="UNAPPROVED_PRIVATE_STAGING_SOURCE"):
        audit_multiyear_pre2025_csvs([approved, candidate])


def test_legacy_cp932_encoding_is_supported(tmp_path):
    a = _year_csv(tmp_path, 2021, race_id="A", horse="架空馬", encoding="cp932")
    b = _year_csv(tmp_path, 2022, race_id="B")
    report = audit_multiyear_pre2025_csvs([a, b])
    assert report.unique_races == 2


def test_two_distinct_absolute_files_are_required(tmp_path):
    a = _year_csv(tmp_path, 2017, race_id="A")
    for paths in ([a], [a, a], []):
        with pytest.raises(UnsafeTrainingSource, match="EXPLICIT_DISTINCT"):
            audit_multiyear_pre2025_csvs(paths)


def test_symlink_rejected_by_underlying_audit(tmp_path):
    a = _year_csv(tmp_path, 2017, race_id="A")
    b = _year_csv(tmp_path, 2018, race_id="B")
    link = tmp_path / "link.csv"
    try:
        link.symlink_to(b)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    with pytest.raises(UnsafeTrainingSource, match="UNTRUSTED_SOURCE_PATH"):
        audit_multiyear_pre2025_csvs([a, link])
