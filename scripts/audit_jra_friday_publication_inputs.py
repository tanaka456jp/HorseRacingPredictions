"""Read-only local JRA Friday input audit, never a note publisher."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from horse_racing_predictions.friday_readiness import (
    FridayAuditError, audit_friday_inputs,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Identify verified/missing JRA note input *candidates*, not permission to publish."
    )
    parser.add_argument("--issue-date", required=True, help="YYYY-MM-DD Friday in Japan")
    parser.add_argument("--forecast-json", type=Path)
    parser.add_argument("--source-rights-json", type=Path)
    parser.add_argument("--race-manifest-json", type=Path)
    parser.add_argument("--model-manifest-json", type=Path)
    args = parser.parse_args()
    try:
        report = audit_friday_inputs(
            issue_date=args.issue_date,
            forecast_json=args.forecast_json,
            source_rights_json=args.source_rights_json,
            race_manifest_json=args.race_manifest_json,
            model_manifest_json=args.model_manifest_json,
        )
    except FridayAuditError as exc:
        report = {
            "status": "BLOCKED", "publicationAuthorized": False,
            "reason": str(exc),
        }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    # Non-zero even for all structurally valid files: an independent signature
    # and the trusted note publishing app remain mandatory.
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
