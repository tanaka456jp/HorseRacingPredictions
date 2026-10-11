from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path

from horse_racing_predictions.jravan_archive_provenance import (
    validate_local_pre2025_archive,
)
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
    provenance = validate_local_pre2025_archive(
        root,
        required_dataspecs=("BLDN",),
    )
    snapshot = root / "pedigree_snapshot.csv"
    report = build_pedigree_snapshot(
        archive_root=root,
        snapshot_path=snapshot,
        report_path=args.report_output,
    )

    output = asdict(report)
    output["archive_manifest"] = str(provenance.manifest_path)
    output["bldn_records_written"] = int(
        provenance.parts[0].records_written
    )
    output["bldn_sha256"] = provenance.parts[0].sha256

    # Replace the first-pass aggregate report with the same sanitized report
    # plus validated BLDN provenance. Raw pedigree identifiers remain local.
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Keep an identical local copy next to the private snapshot as well.
    local_report = root / "pedigree_snapshot_report.json"
    local_report.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(output, ensure_ascii=False, indent=2),
        flush=True,
    )


if __name__ == "__main__":
    main()
