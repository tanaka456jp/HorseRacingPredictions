from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path

from horse_racing_predictions.jravan_archive_reassessment import (
    reassess_local_archive_manifest,
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
            "Metadata-only reassessment of the existing local JRA-VAN archive. "
            "Raw JV-Data records are not opened."
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
            "artifacts/jravan_archive_reassessment_report.json"
        ),
    )
    args = parser.parse_args()

    root = args.archive_root or default_archive_root()
    reassessed, summary = reassess_local_archive_manifest(
        root,
        report_path=args.report_output,
    )

    print(
        json.dumps(
            {
                "status": reassessed["status"],
                "manifest_version": reassessed["manifest_version"],
                "total_records_written": summary.total_records_written,
                "research_approved_dataspecs": list(
                    summary.research_approved_dataspecs
                ),
                "quarantined_dataspecs": list(
                    summary.quarantined_dataspecs
                ),
                "no_data_dataspecs": list(
                    summary.no_data_dataspecs
                ),
                "failed_dataspecs": list(
                    summary.failed_dataspecs
                ),
                "raw_records_read": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
