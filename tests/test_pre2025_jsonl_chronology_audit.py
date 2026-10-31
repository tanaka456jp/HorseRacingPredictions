"""Offline fictional RA/SE JSONL streaming holdout gate tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from horse_racing_predictions.pre2025_jsonl_chronology_audit import (
    audit_pre2025_ra_se_jsonl,
)
from horse_racing_predictions.pre2025_training_csv_audit import (
    UnsafeTrainingSource,
)
from test_jv_fixedwidth_ra_se_preflight import fictional_record


def _write(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf8") as f:
        for kind, text in rows:
            f.write(json.dumps({"record_type": kind, "text": text},
                               ensure_ascii=False) + "\n")
    return path


def test_two_real_layout_shapes_but_fictional_only(tmp_path):
    p = _write(tmp_path / "mock.jsonl", [
        ("RA", fictional_record("RA", year="2024", md="1001")),
        ("SE", fictional_record("SE", year="2024", md="1001")),
        ("JG", "SECRET_HORSE_NAME"),
    ])
    result = audit_pre2025_ra_se_jsonl(p)
    assert result.scanned_records == 3
    assert result.ra_records == result.se_records == 1
    assert result.other_record_types == 1
    assert result.latest_ra_se_year == 2024
    assert result.status == "FULL_RA_SE_CHRONOLOGY_VERIFIED_RESEARCH_RIGHTS_PENDING"
    assert result.whole_archive_source_rights_verified is False
    assert result.trainer_input_csv_created is False
    assert result.publication_authorized is False
    assert result.protected_holdout_opened_for_training is False
    assert "SECRET_HORSE_NAME" not in repr(result)
    assert str(p) not in repr(result)


def test_protected_2026_record_after_large_early_sample_rejected(tmp_path):
    p = _write(tmp_path / "fictional.jsonl",
        [("RA", fictional_record("RA", year="2024"))] * 360
        + [("SE", fictional_record("SE", year="2026"))])
    assert p.stat().st_size > 262144
    with pytest.raises(UnsafeTrainingSource, match="PROTECTED_HOLDOUT_IN_JSONL"):
        audit_pre2025_ra_se_jsonl(p)


def test_missing_se_is_partial_not_approved(tmp_path):
    p = _write(tmp_path / "only_ra.jsonl", [
        ("RA", fictional_record("RA", year="2022"))
    ])
    result = audit_pre2025_ra_se_jsonl(p)
    assert result.status == "PARTIAL_RA_SE_SHARD_RIGHTS_PENDING"
    assert result.ra_records == 1
    assert result.se_records == 0
    assert result.trainer_input_csv_created is False


def test_malformed_layout_dates_and_sensitive_payload_are_rejected(tmp_path):
    p = _write(tmp_path / "bad.jsonl", [
        ("RA", "PRIVATE_NAME " + fictional_record("RA"))
    ])
    with pytest.raises(UnsafeTrainingSource) as e:
        audit_pre2025_ra_se_jsonl(p)
    assert "PRIVATE_NAME" not in str(e.value)
    assert str(p) not in str(e.value)


def test_2026_quarantine_folder_refused_before_open(tmp_path):
    p = _write(tmp_path / "jravan-private-quarantine" / "race.jsonl", [
        ("RA", fictional_record("RA")), ("SE", fictional_record("SE"))
    ])
    with pytest.raises(UnsafeTrainingSource, match="PROTECTED_ARCHIVE_SOURCE_FORBIDDEN"):
        audit_pre2025_ra_se_jsonl(p)


def test_unknown_only_dataset_cannot_claim_ra_se(tmp_path):
    p = _write(tmp_path / "other.jsonl", [("JG", "JGSENSITIVE")])
    with pytest.raises(UnsafeTrainingSource, match="NO_RA_OR_SE_IN_SOURCE"):
        audit_pre2025_ra_se_jsonl(p)


def test_extremely_long_jsonl_line_fails_before_full_line_memory_use(tmp_path):
    from horse_racing_predictions.pre2025_jsonl_chronology_audit import MAX_LINE_BYTES
    p = tmp_path / "huge.jsonl"
    p.write_bytes(b"X" * (MAX_LINE_BYTES + 100) + b"\\n")
    with pytest.raises(UnsafeTrainingSource, match="JSONL_LINE_TOO_LARGE"):
        audit_pre2025_ra_se_jsonl(p)
