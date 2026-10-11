from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "evaluate_exotic_pedigree_phase12.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_exotic_pedigree_phase12_script",
    SCRIPT,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _argv(root: Path, output: Path) -> list[str]:
    return [
        str(SCRIPT),
        "--archive-root",
        str(root),
        "--output",
        str(output),
    ]


def test_existing_receipt_blocks_before_any_provider_archive_parse(
    tmp_path,
    monkeypatch,
):
    root = tmp_path / "archive"
    root.mkdir()
    (root / "phase12_evaluation_receipt.json").write_text(
        "{}",
        encoding="utf-8",
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("history must not be parsed after receipt exists")

    monkeypatch.setattr(MODULE, "parse_raw_jsonl", forbidden)
    monkeypatch.setattr(
        "sys.argv",
        _argv(root, tmp_path / "summary.json"),
    )

    with pytest.raises(RuntimeError, match="must not be rerun"):
        MODULE.main()


def test_first_success_writes_hash_receipt_and_second_run_is_blocked(
    tmp_path,
    monkeypatch,
):
    root = tmp_path / "archive"
    root.mkdir()
    race_raw = root / "race_raw.jsonl"
    pedigree = root / "pedigree_snapshot.csv"
    race_raw.write_bytes(b"synthetic-pre2025-race-archive\n")
    pedigree.write_bytes(
        b"blood_registration_number,sire_breeding_registration_number,"
        b"damsire_breeding_registration_number\n"
        b"B1,S1,D1\n"
    )
    output = tmp_path / "summary.json"

    history = pd.DataFrame([{
        "race_id": "2024-01-01:R1",
        "race_date": pd.Timestamp("2024-01-01"),
    }])
    parse_report = SimpleNamespace(
        spec_version="test",
        output_rows=1,
        output_races=1,
    )

    monkeypatch.setattr(
        MODULE,
        "validate_local_pre2025_archive",
        lambda *args, **kwargs: SimpleNamespace(
            manifest_path=root / "latest_manifest.json",
            manifest_status="complete",
            jvopen_range="20170101000000-20249999999999",
            parts=(
                SimpleNamespace(
                    path=race_raw,
                    sha256=hashlib.sha256(
                        race_raw.read_bytes()
                    ).hexdigest(),
                    records_written=1,
                ),
            ),
        ),
    )
    monkeypatch.setattr(
        MODULE,
        "parse_raw_jsonl",
        lambda *args, **kwargs: (history, parse_report),
    )
    monkeypatch.setattr(
        MODULE.pd,
        "read_csv",
        lambda *args, **kwargs: pd.DataFrame([{
            "blood_registration_number": "B1",
            "sire_breeding_registration_number": "S1",
            "damsire_breeding_registration_number": "D1",
        }]),
    )
    monkeypatch.setattr(
        MODULE,
        "evaluate_pedigree_phase12",
        lambda *args, **kwargs: {
            "status": "research_only_exotic_pedigree_phase12",
            "feature_design": {
                "pedigree_matched_rows": 1,
            },
            "evaluation_2023": {
                "binary_log_loss_delta": -0.001,
                "brier_delta": -0.001,
            },
            "evaluation_2024": {
                "binary_log_loss_delta": -0.001,
                "brier_delta": -0.001,
            },
            "development_pedigree_gate_passed": True,
        },
    )
    monkeypatch.setattr(
        "sys.argv",
        _argv(root, output),
    )
    monkeypatch.setenv("GITHUB_SHA", "abc123")

    MODULE.main()

    receipt_path = root / "phase12_evaluation_receipt.json"
    receipt = json.loads(
        receipt_path.read_text(encoding="utf-8")
    )
    assert receipt["status"] == "phase12_real_evaluation_consumed"
    assert receipt["git_sha"] == "abc123"
    assert receipt["rerun_allowed"] is False
    assert receipt["protected_holdout"] == "2025-2026 untouched"
    assert len(receipt["race_archive_sha256"]) == 64
    assert len(receipt["pedigree_snapshot_sha256"]) == 64
    assert receipt["summary_sha256"] == hashlib.sha256(
        output.read_bytes()
    ).hexdigest()

    summary = json.loads(output.read_text(encoding="utf-8"))
    assert summary["input_provenance"]["current_history_csv_used"] is False
    assert (
        summary["input_provenance"]["protected_holdout"]
        == "2025-2026 untouched"
    )

    with pytest.raises(RuntimeError, match="must not be rerun"):
        MODULE.main()
