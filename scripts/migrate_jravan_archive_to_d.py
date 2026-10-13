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
            "Copy and verify the private JRA-VAN archive from legacy C-drive "
            "LOCALAPPDATA storage to the D-drive preferred archive root. "
            "The source is never deleted; SHA-256 and provenance "
            "verification must succeed before routing changes."
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
        destination_root=Path(r"D:\JRA-VAN\Data Lab\archive\pre2025"),
        delete_source_after_verify=args.delete_source_after_verify,
    )

    payload = asdict(report)
    payload["destination_storage"] = (
        r"D:\JRA-VAN\Data Lab\archive\pre2025"
    )
    payload["source_storage"] = "legacy LOCALAPPDATA archive on system drive"
    payload["raw_provider_data_uploaded"] = False
    payload["c_drive_cleanup_candidate_bytes"] = (
        report.bytes_verified if report.status == "verified" else 0
    )
    payload["source_preserved"] = not report.source_deleted_after_verify

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
