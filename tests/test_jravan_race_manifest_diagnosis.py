"""RACE diagnosis must remain metadata-only and redact full error text."""
import importlib.util
import json
from pathlib import Path

import pytest
from horse_racing_predictions.jravan_free_trial_archive import DEFAULT_ARCHIVE_RANGE

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "diagnose_jravan_race_manifest_offline.py"
spec = importlib.util.spec_from_file_location("jravan_race_diagnosis", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def test_failed_race_cannot_become_eligible_through_migration(tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    source = {
        "jvopen_range": DEFAULT_ARCHIVE_RANGE,
        "raw_redistribution_allowed": False,
        "protected_holdout": "2025-2026 untouched",
        "total_records_written": 100,
        "parts": [
            {"dataspec": "RACE", "status": "failed",
             "records_written": 0,
             "research_use_allowed": False,
             "error": "JVOpen failed with return code -301; secret text"},
            {"dataspec": "BLDN", "status": "success",
             "records_written": 100, "research_use_allowed": True,
             "last_file_timestamp": "20241226000000"},
        ],
    }
    for name in module.MANIFEST_NAMES:
        (root / name).write_text(json.dumps(source), encoding="utf-8")
    result = module.diagnose(root)
    assert result["status"] == "race_blocked"
    assert result["race_from_original"]["error_return_code"] == "-301"
    assert "secret text" not in json.dumps(result)
    assert not result["race_from_relocated"]["raw_file_present"]
    assert not result["raw_records_read"]
    assert not result["provider_access_attempted"]

def test_holdout_bound_violation_fails_closed(tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    source = {
        "jvopen_range": "20170101000000-20259999999999",
        "raw_redistribution_allowed": False,
        "protected_holdout": "2025-2026 untouched",
        "parts": [{"dataspec": "RACE", "status": "no_data"}],
    }
    for name in module.MANIFEST_NAMES:
        (root / name).write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(RuntimeError, match="pre-2025"):
        module.diagnose(root)

def test_workflow_never_accesses_provider_or_raw():
    workflow = Path(".github/workflows/jravan-race-manifest-diagnosis-self-hosted.yml").read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows]" in workflow
    assert "DESKTOP-MVV1FD4" in workflow
    assert "clean: false" in workflow
    assert "JVOpen" not in workflow
    assert "JVRTOpen" not in workflow
    assert "raw.jsonl" not in workflow
    assert "pedigree_snapshot.csv" not in workflow
