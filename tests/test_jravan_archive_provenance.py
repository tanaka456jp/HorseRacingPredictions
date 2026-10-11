import hashlib
import json

import pytest

from horse_racing_predictions.jravan_archive_provenance import (
    validate_local_pre2025_archive,
)
from horse_racing_predictions.jravan_free_trial_archive import (
    DEFAULT_ARCHIVE_RANGE,
)


def _write_manifest(root, *, raw_path, raw_hash, status="complete", range_value=DEFAULT_ARCHIVE_RANGE, part_status="success", records=2):
    payload = {
        "status": status,
        "jvopen_range": range_value,
        "option": 4,
        "dataspecs": ["RACE"],
        "excluded_dataspecs": ["TOKU", "YSCH"],
        "protected_holdout": "2025-2026 not used for modeling/evaluation",
        "raw_redistribution_allowed": False,
        "parts": [
            {
                "dataspec": "RACE",
                "status": part_status,
                "records_written": records,
                "record_type_counts": {"RA": 1, "SE": 1},
                "output_sha256": raw_hash,
                "output_path": str(raw_path),
                "read_count": 2,
                "download_count": 0,
                "last_file_timestamp": "20241299999999",
                "error": None,
            }
        ],
        "total_records_written": records,
    }
    (root / "latest_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_validated_archive_requires_exact_bounded_range_and_matching_hash(tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    raw = root / "race_raw.jsonl"
    raw.write_bytes(b"one\ntwo\n")
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()
    _write_manifest(
        root,
        raw_path=raw,
        raw_hash=digest,
    )

    result = validate_local_pre2025_archive(root)

    assert result.jvopen_range == DEFAULT_ARCHIVE_RANGE
    assert result.manifest_status == "complete"
    assert result.parts[0].dataspec == "RACE"
    assert result.parts[0].path == raw.resolve()
    assert result.parts[0].records_written == 2
    assert result.parts[0].sha256 == digest


def test_partial_manifest_is_allowed_only_when_required_part_itself_succeeded(tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    raw = root / "race_raw.jsonl"
    raw.write_bytes(b"race\n")
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()
    _write_manifest(
        root,
        raw_path=raw,
        raw_hash=digest,
        status="partial",
        records=1,
    )

    result = validate_local_pre2025_archive(root)
    assert result.manifest_status == "partial"

    _write_manifest(
        root,
        raw_path=raw,
        raw_hash=digest,
        status="partial",
        part_status="failed",
        records=0,
    )
    with pytest.raises(RuntimeError, match="not successful"):
        validate_local_pre2025_archive(root)


@pytest.mark.parametrize(
    "range_value",
    [
        "20170101000000-20241231235959",
        "20170101000000-20250101000000",
        "20180101000000-20249999999999",
    ],
)
def test_wrong_provider_range_is_rejected(tmp_path, range_value):
    root = tmp_path / "archive"
    root.mkdir()
    raw = root / "race_raw.jsonl"
    raw.write_bytes(b"race\n")
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()
    _write_manifest(
        root,
        raw_path=raw,
        raw_hash=digest,
        range_value=range_value,
        records=1,
    )

    with pytest.raises(RuntimeError, match="range differs"):
        validate_local_pre2025_archive(root)


def test_mutated_raw_file_is_rejected_before_research_use(tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    raw = root / "race_raw.jsonl"
    raw.write_bytes(b"original\n")
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()
    _write_manifest(
        root,
        raw_path=raw,
        raw_hash=digest,
        records=1,
    )

    raw.write_bytes(b"mutated\n")

    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        validate_local_pre2025_archive(root)


def test_required_file_outside_archive_root_is_rejected(tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    outside = tmp_path / "race_raw.jsonl"
    outside.write_bytes(b"race\n")
    digest = hashlib.sha256(outside.read_bytes()).hexdigest()
    _write_manifest(
        root,
        raw_path=outside,
        raw_hash=digest,
        records=1,
    )

    with pytest.raises(RuntimeError, match="outside local archive root"):
        validate_local_pre2025_archive(root)


def test_manifest_must_explicitly_preserve_holdout_and_forbid_redistribution(tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    raw = root / "race_raw.jsonl"
    raw.write_bytes(b"race\n")
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()
    _write_manifest(
        root,
        raw_path=raw,
        raw_hash=digest,
        records=1,
    )

    manifest_path = root / "latest_manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["protected_holdout"] = ""
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RuntimeError, match="2025-2026 holdout"):
        validate_local_pre2025_archive(root)

    payload["protected_holdout"] = "2025-2026 untouched"
    payload["raw_redistribution_allowed"] = True
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RuntimeError, match="forbid raw redistribution"):
        validate_local_pre2025_archive(root)


def test_duplicate_or_missing_required_dataspec_is_rejected(tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    raw = root / "race_raw.jsonl"
    raw.write_bytes(b"race\n")
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()
    _write_manifest(
        root,
        raw_path=raw,
        raw_hash=digest,
        records=1,
    )

    manifest_path = root / "latest_manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["parts"].append(dict(payload["parts"][0]))
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RuntimeError, match="duplicate"):
        validate_local_pre2025_archive(root)

    payload["parts"] = []
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RuntimeError, match="missing"):
        validate_local_pre2025_archive(root)
