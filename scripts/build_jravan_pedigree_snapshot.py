from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path

from horse_racing_predictions.pedigree_snapshot import (
    build_pedigree_snapshot,
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
            "Build local pre-2025 pedigree snapshot from archived BLOD/BLDN. "
            "Only aggregate coverage report is suitable for GitHub artifacts."
        )
    )
    parser.add_argument(
        "--archive-root",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=Path(
            "artifacts/jravan_pedigree_snapshot_report.json"
        ),
    )
    args = parser.parse_args()

    root = args.archive_root or default_archive_root()
    snapshot = root / "pedigree_snapshot.csv"
    report = build_pedigree_snapshot(
        archive_root=root,
        snapshot_path=snapshot,
        report_path=args.report_output,
    )

    # Keep a local copy next to the private snapshot as well.
    local_report = root / "pedigree_snapshot_report.json"
    local_report.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(asdict(report), ensure_ascii=False, indent=2),
        flush=True,
    )


if __name__ == "__main__":
    main()
