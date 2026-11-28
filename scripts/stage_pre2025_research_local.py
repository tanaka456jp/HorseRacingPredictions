"""Operator-only OFFLINE RA/SE historical research staging.

No existing PC2 runner workflow calls this CLI. Requires explicit source
files and a fresh destination. Full historical date audits happen before
private SQLite/CSV staging. Returns only safe aggregate counts; NEVER outputs
source filenames, horse identities or raw JV-Data. Does NOT authorize model
training, redistribution, betting or note publication.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from horse_racing_predictions.pre2025_research_assembler import (
    stage_pre2025_ra_se_shards,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-jsonl", action="append", type=Path, required=True,
                   help="explicit absolute local source; repeat per shard")
    p.add_argument("--destination", type=Path, required=True,
                   help="a BRAND-NEW private local D research directory")
    p.add_argument("--private-research-only", action="store_true", required=True,
                   help="acknowledge outputs remain UNAPPROVED for training")
    a = p.parse_args()
    try:
        if (not a.private_research_only
                or not a.destination.is_absolute()
                or a.destination.drive not in ("D:", "d:") and
                   __import__("sys").platform == "win32"):
            raise ValueError("PRIVATE_D_RESEARCH_ACKNOWLEDGEMENT_REQUIRED")
        result = stage_pre2025_ra_se_shards(
            a.source_jsonl, destination=a.destination,
        )
        print(json.dumps(asdict(result), sort_keys=True, ensure_ascii=False))
        return 0
    except Exception:
        # Strictly no original exception messages from any local path, JSON
        # record, runtime, key or licensed data may escape into a log.
        print(json.dumps({
            "status": "BLOCKED",
            "reason": "HISTORICAL_SOURCE_CHRONOLOGY_OR_STAGING_FAILED",
            "trainerReady": False,
            "publicationAuthorized": False,
            "protectedHoldoutTrainingAllowed": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
