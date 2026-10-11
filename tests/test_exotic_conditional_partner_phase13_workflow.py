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
    / "evaluate_exotic_conditional_partner_phase13.py"
)
WORKFLOW = Path(
    ".github/workflows/exotic-conditional-partner-phase13-self-hosted.yml"
)

SPEC = importlib.util.spec_from_file_location(
    "evaluate_exotic_conditional_partner_phase13_script",
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


def test_existing_phase13_receipt_blocks_before_history_parse(
    tmp_path,
    monkeypatch,
):
    root = tmp_path / "archive"
    root.mkdir()
    (root / "phase13_evaluation_receipt.json").write_text(
        "{}",
        encoding="utf-8",
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("history must not be parsed")

    monkeypatch.setattr(
        MODULE,
        "parse_raw_jsonl",
        forbidden,
    )
    monkeypatch.setattr(
        "sys.argv",
        _argv(root, tmp_path / "summary.json"),
    )

    with pytest.raises(RuntimeError, match="must not be rerun"):
        MODULE.main()


def test_phase13_first_success_writes_hash_receipt_and_blocks_second_run(
    tmp_path,
    monkeypatch,
):
    root = tmp_path / "archive"
    root.mkdir()
    race_raw = root / "race_raw.jsonl"
    race_raw.write_bytes(b"synthetic-pre2025-race-archive\n")
    output = tmp_path / "summary.json"

    history = pd.DataFrame([{
        "race_id": "2024:R1",
        "race_date": pd.Timestamp("2024-01-01"),
    }])
    parse_report = SimpleNamespace(
        spec_version="test",
        output_rows=1,
        output_races=1,
    )
    monkeypatch.setattr(
        MODULE,
        "parse_raw_jsonl",
        lambda *args, **kwargs: (history, parse_report),
    )
    monkeypatch.setattr(
        MODULE,
        "evaluate_conditional_partner_phase13",
        lambda *args, **kwargs: {
            "status": "research_only_conditional_partner_phase13",
            "evaluation_2023": {
                "nominated_anchor_top3_hit_rate": 0.25,
                "exact_partner_pair_hit_rate_delta": 0.02,
                "partner_recall_at_2_delta": 0.03,
            },
            "evaluation_2024": {
                "nominated_anchor_top3_hit_rate": 0.30,
                "exact_partner_pair_hit_rate_delta": 0.01,
                "partner_recall_at_2_delta": 0.02,
            },
            "development_conditional_partner_gate_passed": True,
        },
    )
    monkeypatch.setattr(
        "sys.argv",
        _argv(root, output),
    )
    monkeypatch.setenv("GITHUB_SHA", "phase13sha")

    MODULE.main()

    receipt_path = root / "phase13_evaluation_receipt.json"
    receipt = json.loads(
        receipt_path.read_text(encoding="utf-8")
    )
    assert receipt["status"] == "phase13_real_evaluation_consumed"
    assert receipt["git_sha"] == "phase13sha"
    assert receipt["rerun_allowed"] is False
    assert receipt["protected_holdout"] == "2025-2026 untouched"
    assert len(receipt["race_archive_sha256"]) == 64
    assert receipt["summary_sha256"] == hashlib.sha256(
        output.read_bytes()
    ).hexdigest()

    summary = json.loads(
        output.read_text(encoding="utf-8")
    )
    assert summary["input_provenance"]["current_history_csv_used"] is False
    assert (
        summary["input_provenance"]["protected_holdout"]
        == "2025-2026 untouched"
    )

    with pytest.raises(RuntimeError, match="must not be rerun"):
        MODULE.main()


def test_phase13_runner_never_references_current_or_combined_history():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "current_history.csv" not in text
    assert "combined" not in text
    assert "race_raw.jsonl" in text
    assert "LOCALAPPDATA" in text
    assert "2025-2026 untouched" in text


def test_phase13_workflow_uploads_metrics_only():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows]" in text
    assert (
        "research/exotic_conditional_partner_phase13_execute_request.txt"
        in text
    )
    upload = text.split(
        "- name: Publish metrics only",
        maxsplit=1,
    )[1]
    assert (
        "artifacts/exotic_conditional_partner_phase13/summary.json"
        in upload
    )
    assert "race_raw.jsonl" not in upload
    assert "phase13_evaluation_receipt.json" not in upload
    assert "JraVanFreeTrialArchive" not in upload


def test_phase13_workflow_does_not_collect_provider_data_or_make_tickets():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "JVRTOpen" not in text
    assert "JVOpen" not in text
    assert "archive_jravan_free_trial_pre2025.py" not in text
    assert "ticket" not in text.lower()
