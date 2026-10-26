"""Only synthetic archive samples; no user data or official provider."""
from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_pc2_pre2025_source_headers_local.py"
SPEC = spec_from_file_location("safe_pre2025_source_audit", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
module = module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def test_pre2025_csv_header_candidate_is_not_training_approval(tmp_path):
    root = tmp_path / "pre2025"
    root.mkdir()
    source = root / "fictional.csv"
    source.write_text(
        "race_id,race_date,horse_name,finish_position,win_odds\n"
        "F1,2024-05-01,架空馬,1,3.1\n",
        encoding="utf-8",
    )
    result = module.inspect_archive_sample(
        output=tmp_path / "sanitized.json", root=root,
        computer="DESKTOP-MVV1FD4", bits=64, windows=True,
    )
    assert result["status"] == "METADATA_SAMPLED_NOT_APPROVED_FOR_TRAINING"
    assert result["csvFiles"] == 1
    assert result["csvHeaderPotentiallyUsable"] == 1
    assert result["sampledPre2025DateRows"] == 1
    assert result["sampled2025OrLaterDateRows"] == 0
    assert result["readyForTraining"] is False
    assert result["protectedHoldoutTrainingAllowed"] is False
    assert result["rawDataUploaded"] is False
    assert "架空馬" not in (tmp_path / "sanitized.json").read_text()


def test_sampled_2026_line_flags_holdout_exposure_without_values(tmp_path):
    root = tmp_path / "pre2025"
    root.mkdir()
    (root / "some.jsonl").write_text(
        json.dumps({"record_type": "RA", "text": "RA1        2026102605"}) + "\n"
        + json.dumps({"record_type": "SE", "text": "SE1        2024102605"}) + "\n",
        encoding="utf-8",
    )
    result = module.inspect_archive_sample(
        output=tmp_path / "summary.json", root=root,
        computer="DESKTOP-MVV1FD4", bits=64, windows=True,
    )
    assert result["sampled2025OrLaterDateRows"] == 1
    assert result["sampledPre2025DateRows"] == 1
    assert result["sampledRaRecordTypes"] == 1
    assert result["sampledSeRecordTypes"] == 1
    assert result["readyForTraining"] is False
    data = (tmp_path / "summary.json").read_text()
    assert "20261026" not in data
    assert "20241026" not in data


def test_wrong_runner_cannot_open_any_source(tmp_path):
    root = tmp_path / "pre2025"
    root.mkdir()
    (root / "private.csv").write_text("horse_name\nSECRET\n", encoding="utf8")
    result = module.inspect_archive_sample(
        output=tmp_path / "result.json", root=root,
        computer="PC1", bits=64, windows=True,
    )
    assert result["status"] == "BLOCKED"
    assert result["scannedFiles"] == 0
    assert "SECRET" not in (tmp_path / "result.json").read_text()
