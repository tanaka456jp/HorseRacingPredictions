"""One-command private Sunday forecast audit. Never publishes or uploads."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

from horse_racing_predictions.sunday_auto_post_readiness import (
    diagnose_sunday_auto_post,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundle-dir", type=Path,
        default=Path(os.environ.get(
            "HORSE_SUNDAY_20261025_BUNDLE_DIR",
            "D:/HorseRacingPredictions/approved-sunday-20261025",
        )),
        help="pre-existing reviewed local model, history, 36-race card; read-only",
    )
    args = parser.parse_args()
    report = diagnose_sunday_auto_post(
        args.bundle_dir,
        observed_at=datetime.now(timezone(timedelta(hours=9))),
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 2 if report["status"] != "READY_FOR_AUTHORIZED_NOTE_POST" else 0


if __name__ == "__main__":
    raise SystemExit(main())
