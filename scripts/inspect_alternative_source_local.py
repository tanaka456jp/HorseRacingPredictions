"""Manual offline inspection for independently licensed alternative CSV data.

DO NOT invoke via GitHub Actions, a PC2 runner, or a previously refused
archive-read pathway. Operator supplies *exact* local CSV and private manifest
paths in an expressly authorized local session. Never downloads or trains.
No filenames, hashes, horse IDs, keys, data rows or evidence links in stdout.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path

from horse_racing_predictions.alternative_source_intake import (
    inspect_alternative_csv,
)
from horse_racing_predictions.pre2025_training_csv_audit import (
    UnsafeTrainingSource,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-csv", type=Path, required=True)
    parser.add_argument("--private-rights-manifest", type=Path, required=True)
    parser.add_argument("--kind", required=True, choices=("history", "settlement"))
    args = parser.parse_args()
    try:
        report = inspect_alternative_csv(
            args.source_csv, args.private_rights_manifest, kind=args.kind,
        )
    except (UnsafeTrainingSource, ValueError, OSError, TypeError, KeyError):
        # Keep the public-facing report non-sensitive. Detailed source
        # evidence must remain in an operator-controlled local review.
        print(json.dumps({
            "status": "BLOCKED_SOURCE_OR_RIGHTS_REVIEW_REQUIRED",
            "privateResearchPermissionConfirmedByThisTool": False,
            "approvedForModelTraining": False,
            "newDataDownloaded": False,
            "notePublicationAuthorized": False,
        }, sort_keys=True))
        return 2
    print(json.dumps({
        "status": report.status,
        "kind": report.kind,
        "checkedRows": report.total_rows,
        "minYear": report.min_year,
        "maxYear": report.max_year,
        "sourceDigestMatches": report.source_digest_matches,
        "privateResearchPermissionConfirmedByThisTool": False,
        "approvedForModelTraining": report.approved_for_model_training,
        "newDataDownloaded": report.web_data_downloaded,
        "notePublicationAuthorized": report.published_to_note,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
