"""Metadata-only rejection of illegal provider years before raw reads."""
from __future__ import annotations

import hashlib
import json

import pytest

from horse_racing_predictions.jravan_archive_provenance import (
    validate_local_pre2025_archive,
)
from horse_racing_predictions.jravan_free_trial_archive import DEFAULT_ARCHIVE_RANGE


def make_archive(tmp_path, timestamp):
    root = tmp_path / "archive"
    root.mkdir()
    raw = root / "race_raw.jsonl"
    raw.write_bytes(b"synthetic\n")
    payload = {
        "status": "partial",
        "jvopen_range": DEFAULT_ARCHIVE_RANGE,
        "raw_redistribution_allowed": False,
        "protected_holdout": "2025-2026 untouched",
        "parts": [{
            "dataspec": "RACE",
            "status": "success",
            "research_use_allowed": True,
            "records_written": 1,
            "last_file_timestamp": timestamp,
            "output_path": str(raw),
            "output_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
        }],
    }
    (root / "latest_manifest_v2.json").write_text(
        json.dumps(payload), encoding="utf-8",
    )
    return root, raw


@pytest.mark.parametrize("timestamp", [
    None, "", "20250101000000", "20261231235959",
    "20259999999999", "2024", "99999999999999",
    "2024-12-31", "２０１４１２３１２３５９５９",
    "2024123123595x", "20161231235959",
])
def test_holdout_or_invalid_provider_timestamp_rejected(tmp_path, timestamp, monkeypatch):
    root, raw = make_archive(tmp_path, timestamp)

    def forbidden(_):
        raise AssertionError("raw RACE bytes must not be opened")

    monkeypatch.setattr(
        "horse_racing_predictions.jravan_archive_provenance._sha256",
        forbidden,
    )
    with pytest.raises(RuntimeError, match="pre-2025 provider file timestamp"):
        validate_local_pre2025_archive(root)
    assert raw.read_bytes() == b"synthetic\n"


@pytest.mark.parametrize("timestamp", [
    "20170101000000", "20241231235959", "20249999999999",
])
def test_provider_bounded_timestamp_accepted_with_matching_hash(tmp_path, timestamp):
    root, _ = make_archive(tmp_path, timestamp)
    validated = validate_local_pre2025_archive(root)
    assert validated.parts[0].dataspec == "RACE"
    assert validated.parts[0].records_written == 1
