"""Manual local-only NAR monthly ZIP metadata check.

Not a downloader, scraper, archive extractor, training gate or a GitHub
Actions entry point. Use only in a human-authorized private session with
a personally downloaded official ZIP and only under reviewed provider terms.
Source contents, file paths, hashes and race identities are not printed.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from horse_racing_predictions.nar_official_zip_probe import (
    UnsafeNarSource, inspect_nar_monthly_zip_structure,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-monthly-race-zip", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = inspect_nar_monthly_zip_structure(
            args.local_monthly_race_zip
        )
    except (UnsafeNarSource, TypeError, OSError, ValueError):
        print(json.dumps({
            "status": "NAR_FORMAT_OR_LOCAL_PERMISSION_REVIEW_REQUIRED",
            "trainApproved": False,
            "payoutRoiApproved": False,
            "publicPostingApproved": False,
            "downloadAttempted": False,
        }, sort_keys=True))
        return 2
    print(json.dumps({
        "status": report.status,
        "sourceMonth": report.source_month,
        "archiveKind": report.archive_kind,
        "archiveFileCount": report.csv_files,
        "entryPresent": report.entry_list_present,
        "raceListPresent": report.race_list_present,
        "paybackPresent": report.settlement_present,
        "totalUncompressedBytes": report.total_uncompressed_bytes,
        "sourceRightsVerified": False,
        "rowsRead": False,
        "trainApproved": False,
        "payoutRoiApproved": False,
        "downloadAttempted": False,
        "publicPostingApproved": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
