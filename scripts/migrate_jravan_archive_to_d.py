from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from horse_racing_predictions.jravan_archive_migration import (
    migrate_archive_to_preferred_storage,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Move the private JRA-VAN free-trial archive from legacy C-drive "
            "LOCALAPPDATA storage to the D-drive preferred archive root. "
            "Source deletion occurs only after full SHA-256 and provenance "
            "verification."
        )
    )
    parser.add_argument(
        "--delete-source-after-verify",
        action="store_true",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=Path(
            "artifacts/jravan_archive_d_drive_migration_report.json"
        ),
    )
    args = parser.parse_args()

    report = migrate_archive_to_preferred_storage(
        delete_source_after_verify=args.delete_source_after_verify,
    )

    payload = asdict(report)
    payload["destination_storage"] = (
        r"D:\HorseRacingPredictions\JraVanFreeTrialArchive\pre2025"
    )
    payload["source_storage"] = "legacy LOCALAPPDATA archive on system drive"
    payload["raw_provider_data_uploaded"] = False

    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        json.dumps(payload, ensure_ascii=False, indent=2),
        flush=True,
    )


if __name__ == "__main__":
    main()
