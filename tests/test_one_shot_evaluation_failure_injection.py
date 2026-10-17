"""Synthetic failure-injection: aborted Phase 12/13 evals must never rerun."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import hashlib

import pytest


def _script(phase: int):
    name = (
        "evaluate_exotic_pedigree_phase12.py"
        if phase == 12 else "evaluate_exotic_conditional_partner_phase13.py"
    )
    path = Path(__file__).resolve().parents[1] / "scripts" / name
    spec = importlib.util.spec_from_file_location(
        f"phase_{phase}_failure_injection", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, path


@pytest.mark.parametrize("phase", [12, 13])
def test_parse_crash_claim_is_durable_and_second_attempt_is_refused(
    tmp_path, monkeypatch, phase
):
    module, script = _script(phase)
    root = tmp_path / "private_archive"
    root.mkdir()
    race = root / "race_raw.jsonl"
    race.write_bytes(b"synthetic-bound-race-not-JV-data\n")
    if phase == 12:
        (root / "pedigree_snapshot.csv").write_text(
            "blood_registration_number\nSYNTHETIC\n", encoding="utf-8"
        )
    calls = {"parsed": 0}

    def bad_parse(*args, **kwargs):
        calls["parsed"] += 1
        raise RuntimeError("synthetic read interruption")

    monkeypatch.setattr(module, "validate_local_pre2025_archive", lambda *a, **kw: (
        SimpleNamespace(
            parts=(SimpleNamespace(
                path=race,
                sha256=hashlib.sha256(race.read_bytes()).hexdigest(),
                records_written=1,
            ),),
            manifest_path=root / "latest_manifest.json",
            manifest_status="partial",
            jvopen_range="20170101000000-20249999999999",
        )
    ))
    monkeypatch.setattr(module, "parse_raw_jsonl", bad_parse)
    monkeypatch.setattr("sys.argv", [
        str(script), "--archive-root", str(root), "--output",
        str(tmp_path / "metrics.json"),
    ])

    with pytest.raises(RuntimeError, match="synthetic read interruption"):
        module.main()
    assert calls["parsed"] == 1
    receipt = root / f"phase{phase}_evaluation_receipt.json"
    saved = json.loads(receipt.read_text(encoding="utf-8"))
    assert saved["status"] == f"phase{phase}_evaluation_started"
    assert saved["rerun_allowed"] is False

    with pytest.raises(RuntimeError, match="must not be rerun"):
        module.main()
    assert calls["parsed"] == 1


@pytest.mark.parametrize("phase", [12, 13])
def test_no_race_provenance_never_claims_one_shot(
    tmp_path, monkeypatch, phase
):
    module, script = _script(phase)
    root = tmp_path / "private_archive"
    root.mkdir()
    if phase == 12:
        (root / "pedigree_snapshot.csv").write_text(
            "synthetic\n", encoding="utf-8"
        )

    def missing_race(*args, **kwargs):
        raise RuntimeError("RACE JVOpen -301; missing provider-bounded data")

    monkeypatch.setattr(module, "validate_local_pre2025_archive", missing_race)
    monkeypatch.setattr("sys.argv", [
        str(script), "--archive-root", str(root),
    ])
    with pytest.raises(RuntimeError, match="RACE JVOpen -301"):
        module.main()
    assert not (root / f"phase{phase}_evaluation_receipt.json").exists()
