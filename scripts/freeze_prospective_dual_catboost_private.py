"""Offline PC2-only future JRA/NAR dual-CatBoost paper prediction freeze.

Requires independently reviewed as-of feature input and verified local dual
CBM research artifact. Never contacts providers, places bets, or publishes
races/horses. A blinded digest is NOT itself independent time attestation.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets

import pandas as pd

from horse_racing_predictions.dual_candidate_private_preview import (
    load_dual_research_candidate,
)
from horse_racing_predictions.prospective_dual_model_shadow import (
    freeze_fitted_dual_shadow,
)

_CALENDAR_SCHEMA = "HorseRacing.PrivateFutureCalendar.v1"
_SNAPSHOT_SCHEMA = "HorseRacing.PC2.ProspectiveDualModelPrivate.v1"


def _file(path: Path, limit: int) -> None:
    if (not isinstance(path, Path) or not path.is_absolute()
            or path.is_symlink() or not path.is_file()
            or not 1 <= path.stat().st_size <= limit):
        raise ValueError("PRIVATE_INPUT_INVALID")


def freeze_private_future(
    *, candidate_dir: Path, features_csv: Path,
    calendar_json: Path, private_output_dir: Path,
    now_utc: datetime,
) -> dict:
    """Write exactly one new, local-only snapshot, never revise old picks.

    User-reviewed provenance flags are not independent attestations, nor
    evidence of JRA/NAR source permission. Fail closed on incomplete rosters.
    """
    if (os.environ.get("COMPUTERNAME") != "DESKTOP-MVV1FD4"
            or not isinstance(now_utc, datetime)
            or now_utc.utcoffset() is None
            or not isinstance(candidate_dir, Path)
            or not candidate_dir.is_absolute()
            or candidate_dir.is_symlink()
            or not isinstance(private_output_dir, Path)
            or not private_output_dir.is_absolute()
            or private_output_dir.is_symlink()
            or not private_output_dir.is_dir()):
        raise ValueError("PRIVATE_PC2_CONTEXT_INVALID")
    _file(features_csv, 35_000_000)
    _file(calendar_json, 1_000_000)
    manifest = json.loads(calendar_json.read_text(encoding="utf-8"))
    if (type(manifest) is not dict or set(manifest) != {
            "schema", "jurisdiction", "race_day_jst", "source_asof_utc",
            "scheduled_off_utc", "runner_count_by_race",
            "operator_reviewed_asof_only", "operator_reviewed_complete_roster",
        } or manifest["schema"] != _CALENDAR_SCHEMA
            or manifest["operator_reviewed_asof_only"] is not True
            or manifest["operator_reviewed_complete_roster"] is not True
            or manifest["jurisdiction"] not in ("JRA", "NAR")):
        raise ValueError("PRIVATE_CALENDAR_REVIEW_INVALID")
    expected = manifest["runner_count_by_race"]
    schedule = manifest["scheduled_off_utc"]
    if (type(expected) is not dict or type(schedule) is not dict
            or not expected or set(expected) != set(schedule)
            or any(type(n) is not int or not 4 <= n <= 18
                   for n in expected.values())):
        raise ValueError("PRIVATE_ROSTER_DENOMINATOR_INVALID")
    native = load_dual_research_candidate(candidate_dir)
    frame = pd.read_csv(
        features_csv, encoding="utf-8-sig",
        dtype={"race_id": "string", "horse_id": "string"},
    )
    counts = frame.groupby("race_id").size().to_dict()
    if counts != expected:
        raise ValueError("PRIVATE_ROSTER_COVERAGE_INVALID")
    model_hashes = native.digest_by_role
    combined = sha256(
        (model_hashes["win.cbm"] + model_hashes["outsider.cbm"]).encode("ascii")
    ).hexdigest()
    source = datetime.fromisoformat(manifest["source_asof_utc"].replace("Z", "+00:00"))
    off = {rid: datetime.fromisoformat(value.replace("Z", "+00:00"))
           for rid, value in schedule.items()}
    frozen = freeze_fitted_dual_shadow(
        jurisdiction=manifest["jurisdiction"],
        race_day_jst=manifest["race_day_jst"],
        entries=frame,
        off_by_race=off,
        winner=native.winner, outsider=native.outsider,
        model_trained_through=native.train_end,
        model_sha256_declared=combined,
        source_asof_utc=source,
        generated_utc=now_utc,
    )
    target = private_output_dir / (
        manifest["race_day_jst"].replace("-", "") + "_" +
        manifest["jurisdiction"] + "_dual_catboost_PRIVATE.json"
    )
    # The hash of a deterministic, low-entropy race card must never be
    # logged without secret blinding; salt resides only in the private file.
    salt = secrets.token_bytes(32)
    record = {
        "schema": _SNAPSHOT_SCHEMA,
        "frozen_shadow_PRIVATE": asdict(frozen),
        "salt_hex_PRIVATE": salt.hex(),
        "blinded_digest": sha256(
            b"HORSERACING_FORWARD_DUAL_V1\x00" + salt +
            frozen.commitment_sha256.encode("ascii")
        ).hexdigest(),
        "candidate_binary_checksums_verified": True,
        "source_and_roster_independently_attested": False,
        "hosted_preoff_receipt_verified": False,
        "model_results_or_odds_observed_before_freeze": False,
        "actual_bets": 0,
        "after_cost_positive_ev_proven": False,
        "raw_source_uploaded": False,
    }
    data = json.dumps(
        record, ensure_ascii=False, sort_keys=True, allow_nan=False
    ).encode("utf-8")
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return {
        "schema": _SNAPSHOT_SCHEMA,
        "status": "PRIVATE_FITTED_MODEL_FORECAST_FROZEN_RECEIPT_PENDING",
        "series": frozen.jurisdiction,
        "races": len(frozen.races),
        "runners": sum(len(r.roster) for r in frozen.races),
        "blinded_digest": record["blinded_digest"],
        "official_settlements_verified": False,
        "source_or_horses_uploaded": False,
        "positive_ev_proven": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidate-dir", type=Path, required=True)
    p.add_argument("--preoff-features-csv", type=Path, required=True)
    p.add_argument("--reviewed-calendar-json", type=Path, required=True)
    p.add_argument("--private-output-dir", type=Path, required=True)
    args = p.parse_args()
    try:
        summary = freeze_private_future(
            candidate_dir=args.candidate_dir,
            features_csv=args.preoff_features_csv,
            calendar_json=args.reviewed_calendar_json,
            private_output_dir=args.private_output_dir,
            now_utc=datetime.now(timezone.utc),
        )
    except Exception:
        print(json.dumps({
            "schema": _SNAPSHOT_SCHEMA,
            "status": "HOLD_MODEL_OR_PREOFF_SOURCE_NOT_READY",
            "source_uploaded": False,
            "after_cost_positive_ev_proven": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
