from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from horse_racing_predictions.jravan_archive_migration import (
    migrate_archive_to_preferred_storage,
)
from horse_racing_predictions.jravan_archive_paths import (
    legacy_localappdata_archive_root,
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

    legacy = legacy_localappdata_archive_root()
    previous_d = Path(r"D:\HorseRacingPredictions\JraVanFreeTrialArchive\pre2025")
    source = legacy
    already_on_d = False
    if not (legacy / "latest_manifest.json").is_file():
        tombstone = legacy / "MOVED_TO_D.json"
        prior_receipt = previous_d / "migration_receipt.json"
        if not tombstone.is_file() or not prior_receipt.is_file():
            raise RuntimeError(
                "C archive lacks a primary manifest and previous D migration "
                "proof is missing; refusing to copy."
            )
        previous_status = json.loads(prior_receipt.read_text(encoding="utf-8"))
        if previous_status.get("status") != "verified":
            raise RuntimeError("Prior D migration receipt is not verified.")
        source = previous_d
        already_on_d = True

    report = migrate_archive_to_preferred_storage(
        source_root=source,
        destination_root=Path(r"D:\JRA-VAN\Data Lab\archive\pre2025"),
        delete_source_after_verify=args.delete_source_after_verify,
    )

    payload = asdict(report)
    payload["destination_storage"] = (
        r"D:\JRA-VAN\Data Lab\archive\pre2025"
    )
    payload["source_storage"] = (
        "previously verified D-drive archive" if already_on_d
        else "legacy LOCALAPPDATA archive on system drive"
    )
    payload["source_previously_migrated_to_d"] = already_on_d
    payload["raw_provider_data_uploaded"] = False
    payload["c_drive_cleanup_candidate_bytes"] = (
        report.bytes_verified
        if report.status == "verified" and not already_on_d
        else 0
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
