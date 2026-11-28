"""Read-only local Sunday audit. Missing inputs never unlock publishing.

Use only explicitly staged local, independently licensed data. No network,
JRA-VAN access, account session, paid service, training or note mutations.
The wall clock is always obtained internally; no user-controlled --as-of flag.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from horse_racing_predictions.future_sunday_readiness import (
    diagnose_future_sunday_bundle,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--race-date", required=True, help="Sunday YYYY-MM-DD")
    p.add_argument("--bundle-dir", type=Path, required=True,
                   help="existing approved local model, history and full card")
    args = p.parse_args()
    try:
        # Prefer the independent dual candidate only when its distinct
        # native artifacts are present; never silently downgrade a partial
        # dual bundle to the legacy single-model inference path.
        dual_names = (
            "model/candidate_manifest.json",
            "model/win.cbm",
            "model/outsider.cbm",
        )
        dual_mode = any(
            (args.bundle_dir / filename).exists()
            or (args.bundle_dir / filename).is_symlink()
            for filename in dual_names
        )
        result = diagnose_future_sunday_bundle(
            args.bundle_dir, race_date=args.race_date,
            observed_at=datetime.now(timezone.utc),
            model_mode="dual" if dual_mode else "single",
        )
    except (ValueError, OSError, TypeError, UnicodeError):
        result = {
            "status": "BLOCKED",
            "blockers": ["INVALID_RACE_DATE_OR_LOCAL_CONFIGURATION"],
            "modelComputed": False, "publicationAuthorized": False,
            "notePostAttempted": False, "providerAccessAttempted": False,
            "rawDataUploaded": False,
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    # A blocked publication is expected diagnostic data, not a runner failure.
    # Exit code 0 means ONLY that read-only diagnostics ran.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
