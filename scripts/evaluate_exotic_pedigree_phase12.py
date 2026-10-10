from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pandas as pd

from horse_racing_predictions.exotic_pedigree_phase12 import (
    evaluate_pedigree_phase12,
)
from horse_racing_predictions.jravan_parser import (
    parse_raw_jsonl,
)


def default_archive_root() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError("LOCALAPPDATA is required.")
    return (
        Path(local)
        / "HorseRacingPredictions"
        / "JraVanFreeTrialArchive"
        / "pre2025"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run preregistered Phase 12 using only the local provider-bounded "
            "pre-2025 RACE archive and local pedigree snapshot."
        )
    )
    parser.add_argument(
        "--archive-root",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "artifacts/exotic_pedigree_phase12/summary.json"
        ),
    )
    args = parser.parse_args()

    root = args.archive_root or default_archive_root()
    race_raw = root / "race_raw.jsonl"
    pedigree_path = root / "pedigree_snapshot.csv"

    if not race_raw.is_file():
        raise FileNotFoundError(
            f"local bounded RACE archive missing: {race_raw}"
        )
    if not pedigree_path.is_file():
        raise FileNotFoundError(
            f"local pedigree snapshot missing: {pedigree_path}"
        )

    history, parse_report = parse_raw_jsonl(
        race_raw,
        jra_only=True,
        completed_only=True,
    )
    if history.empty:
        raise RuntimeError(
            "local bounded RACE archive produced no completed JRA history"
        )
    pedigree = pd.read_csv(
        pedigree_path,
        encoding="utf-8-sig",
        dtype="string",
    )

    result = evaluate_pedigree_phase12(
        history,
        pedigree,
    )
    result["input_provenance"] = {
        "race_archive": "LOCALAPPDATA pre2025/race_raw.jsonl",
        "pedigree_snapshot": "LOCALAPPDATA pre2025/pedigree_snapshot.csv",
        "parse_spec_version": parse_report.spec_version,
        "history_rows": int(parse_report.output_rows),
        "history_races": int(parse_report.output_races),
        "current_history_csv_used": False,
        "protected_holdout": "2025-2026 untouched",
    }

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    args.output.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(json.dumps({
        "status": result["status"],
        "history_rows": int(parse_report.output_rows),
        "history_races": int(parse_report.output_races),
        "pedigree_matched_rows": (
            result["feature_design"]["pedigree_matched_rows"]
        ),
        "evaluation_2023": {
            "binary_log_loss_delta": (
                result["evaluation_2023"]["binary_log_loss_delta"]
            ),
            "brier_delta": result["evaluation_2023"]["brier_delta"],
        },
        "evaluation_2024": {
            "binary_log_loss_delta": (
                result["evaluation_2024"]["binary_log_loss_delta"]
            ),
            "brier_delta": result["evaluation_2024"]["brier_delta"],
        },
        "development_pedigree_gate_passed": (
            result["development_pedigree_gate_passed"]
        ),
        "protected_holdout": "2025-2026 untouched",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
