import hashlib
import json
from pathlib import Path

import pytest

from horse_racing_predictions.jravan_free_trial_archive import DEFAULT_ARCHIVE_RANGE
import importlib.util

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "preflight_jravan_phase12_phase13.py"
SPEC = importlib.util.spec_from_file_location("jravan_phase12_phase13_preflight", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
preflight = MODULE.preflight


def test_one_shot_preflight_blocks_missing_race_without_consuming_receipts(tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    for name in ("latest_manifest.json", "latest_manifest_v2.json"):
        (root / name).write_text("{}", encoding="utf-8")
    originals = [{
        "relative_path": name,
        "sha256": hashlib.sha256(b"{}").hexdigest(),
    } for name in ("latest_manifest.json", "latest_manifest_v2.json")]
    (root / "migration_file_hashes.json").write_text(json.dumps(originals), encoding="utf-8")
    bldn = root / "bldn_raw.jsonl"
    bldn.write_bytes(b"synthetic\n")
    payload = {
        "status": "partial",
        "jvopen_range": DEFAULT_ARCHIVE_RANGE,
        "protected_holdout": "2025-2026 untouched",
        "raw_redistribution_allowed": False,
        "parts": [{
            "dataspec": "BLDN", "status": "success",
            "research_use_allowed": True,
            "last_file_timestamp": "20241212000000",
            "output_path": str(bldn),
        }],
    }
    data = json.dumps(payload).encode()
    (root / "relocated_manifest_v2.json").write_bytes(data)
    (root / "pedigree_snapshot.csv").write_text("horse_id\n", encoding="utf-8")
    (root / "migration_receipt.json").write_text(json.dumps({
        "status": "verified",
        "source_deleted_after_verify": False,
        "destination_manifest_sha256": hashlib.sha256(data).hexdigest(),
    }), encoding="utf-8")
    result = preflight(root)
    assert result["status"] == "blocked_preconditions"
    assert result["bldn_research_eligible"] is True
    assert result["race_research_eligible"] is False
    assert result["phase12_ready"] is False
    assert result["phase13_ready"] is False
    assert not (root / "phase12_evaluation_receipt.json").exists()
    assert not (root / "phase13_evaluation_receipt.json").exists()
