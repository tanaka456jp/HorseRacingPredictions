"""Local-only CLI for user-authorized NAR monthly race ZIP inspection.

Run manually on the operator's own PC. No download, browser, cloud, note
publication, training or source-data export. Prints aggregate counts only.
The user-reported NAR personal-use permission does not authorize automated
bulk retrieval or commercial reuse.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from horse_racing_predictions.nar_local_monthly_intake import (
    read_nar_monthly_zip_local,
)
from horse_racing_predictions.nar_official_zip_probe import UnsafeNarSource


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-monthly-race-zip", type=Path, required=True)
    parser.add_argument(
        "--confirm-personal-private-nar-permission",
        action="store_true",
        help="Acknowledge a personal private NAR permission received independently.",
    )
    args = parser.parse_args()
    try:
        report = read_nar_monthly_zip_local(
            args.local_monthly_race_zip,
            personal_private_permission_confirmed=(
                args.confirm_personal_private_nar_permission
            ),
        )
    except (UnsafeNarSource, ValueError, OSError, TypeError):
        print(json.dumps({
            "status": "NAR_LOCAL_SOURCE_REJECTED_OR_PERMISSION_NOT_CONFIRMED",
            "approvedForTraining": False,
            "notePublicationAuthorized": False,
            "newDataDownloaded": False,
        }, sort_keys=True))
        return 2
    print(json.dumps({
        "status": report.status,
        "month": report.source_month,
        "parsedRaces": report.parsed_races,
        "parsedStarters": report.parsed_starters,
        "minYear": report.min_year,
        "maxYear": report.max_year,
        "preEventSnapshotProven": False,
        "sourceRightsVerifiedBySoftware": False,
        "approvedForTraining": False,
        "positiveEvDemonstrated": False,
        "notePublicationAuthorized": False,
        "newDataDownloaded": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
