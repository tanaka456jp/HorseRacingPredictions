"""PC2 private read-only forward fitted-model readiness; no provider calls."""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re

JST = timezone(timedelta(hours=9))
MODEL_LOCATIONS = {
    "NAR": "nar-forward-models/2017-2021-fit-2022-tune-v1",
    "JRA": "jra-forward-models/strict-dual-v1",
}
FORBIDDEN = re.compile(
    r"(^|_)(odds|popularity|payback|payout|dividend|finish_position|is_winner|"
    r"actual_rank|result|target|prize_money|win_return|place_return)(_|$)", re.I
)


def safe_file(path: Path, max_size: int) -> bool:
    return (path.is_file() and not path.is_symlink()
            and 0 < path.stat().st_size <= max_size)


def utc(timestamp: str) -> datetime:
    d = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if d.utcoffset() is None:
        raise ValueError("NAIVE_TIME")
    return d.astimezone(timezone.utc)


def verified_model_features(root: Path, series: str) -> tuple[str, ...] | None:
    folder = root / MODEL_LOCATIONS[series]
    manifest = folder / "candidate_manifest.json"
    if (not folder.is_dir() or folder.is_symlink()
            or not safe_file(manifest, 300_000)):
        return None
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    if (doc.get("schemaVersion") != 1 or
            doc.get("artifactKind") != "dual-catboost-oddsfree-research-candidate" or
            doc.get("status") != "RESEARCH_NOT_APPROVED_FOR_PUBLICATION" or
            doc.get("publicationAuthorized") is not False or
            doc.get("sourceRightsIndependentlyVerified") is not False or
            doc.get("independentOutsiderModelVerified") is not False or
            date.fromisoformat(doc["trainEnd"]) > date(2024, 12, 31)):
        return None
    features = tuple(doc["featureColumns"])
    if (not features or len(set(features)) != len(features)
            or any(type(v) is not str or FORBIDDEN.search(v) for v in features)):
        return None
    hashes = doc["artifactSha256"]
    if type(hashes) is not dict or set(hashes) != {"win.cbm", "outsider.cbm"}:
        return None
    for name in ("win.cbm", "outsider.cbm"):
        model_file = folder / name
        if (not safe_file(model_file, 500_000_000)
                or not isinstance(hashes[name], str)
                or not re.fullmatch(r"[0-9a-f]{64}", hashes[name])):
            return None
        digest = sha256()
        with model_file.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        if digest.hexdigest() != hashes[name]:
            return None
    return features


def count_staged_cards(root: Path, series: str, features: tuple[str, ...],
                       now: datetime) -> int:
    directory = root / "forward-model-inputs"
    if not directory.is_dir() or directory.is_symlink():
        return 0
    count = 0
    for delta in range(15):
        day = now.astimezone(JST).date() + timedelta(days=delta)
        prefix = f"{day:%Y%m%d}_{series}_future"
        calendar = directory / (prefix + "_calendar.json")
        rows_file = directory / (prefix + "_features.csv")
        if (not safe_file(calendar, 1_000_000)
                or not safe_file(rows_file, 35_000_000)):
            continue
        document = json.loads(calendar.read_text(encoding="utf-8"))
        if (not isinstance(document, dict) or set(document) != {
                "schema", "jurisdiction", "race_day_jst", "source_asof_utc",
                "scheduled_off_utc", "runner_count_by_race",
                "operator_reviewed_asof_only", "operator_reviewed_complete_roster"
            } or document["schema"] != "HorseRacing.PrivateFutureCalendar.v1"
                or document["jurisdiction"] != series
                or document["race_day_jst"] != day.isoformat()
                or document["operator_reviewed_asof_only"] is not True
                or document["operator_reviewed_complete_roster"] is not True):
            continue
        expected = document["runner_count_by_race"]
        scheduled = document["scheduled_off_utc"]
        if (type(expected) is not dict or not expected
                or len(expected) > 500 or type(scheduled) is not dict
                or set(expected) != set(scheduled)
                or any(type(v) is not int or not 4 <= v <= 18
                       for v in expected.values())
                or utc(document["source_asof_utc"]) > now):
            continue
        if any(utc(off).astimezone(JST).date() != day
               or utc(off) <= now + timedelta(minutes=10)
               for off in scheduled.values()):
            continue
        observed = {}
        identities = set()
        with rows_file.open(encoding="utf-8-sig", newline="") as stream:
            rows = csv.DictReader(stream)
            if (not rows.fieldnames or
                    len(rows.fieldnames) != len(set(rows.fieldnames)) or
                    set(rows.fieldnames) != {"race_id", "horse_id", *features}):
                continue
            invalid = False
            for index, row in enumerate(rows):
                rid, horse = row["race_id"], row["horse_id"]
                if (index >= 10000 or not rid or not horse
                        or rid not in expected or (rid, horse) in identities):
                    invalid = True
                    break
                identities.add((rid, horse))
                observed[rid] = observed.get(rid, 0) + 1
        if not invalid and observed == expected:
            count += 1
    return count


def audit(root: Path, now: datetime) -> dict:
    output = {
        "schema": "HorseRacing.PC2.FutureFittedModelReadiness.v1",
        "status": "HOLD_FITTED_MODEL_OR_PREOFF_FEATURE_INPUT_MISSING",
        "NAR_model_checksums_verified": False,
        "JRA_model_checksums_verified": False,
        "NAR_complete_future_cards": 0,
        "JRA_complete_future_cards": 0,
        "model_prediction_executed": False,
        "real_forward_hit_rate_measured": False,
        "real_forward_roi_measured": False,
        "provider_requests": 0,
        "source_model_or_horse_data_uploaded": False,
        "actual_bets": 0,
        "positive_ev_proven": False,
    }
    if (os.environ.get("COMPUTERNAME") != "DESKTOP-MVV1FD4"
            or not root.is_absolute() or not root.is_dir()
            or root.is_symlink() or now.utcoffset() is None):
        output["status"] = "HOLD_PRIVATE_PC2_CONTEXT_INVALID"
        return output
    try:
        ready = False
        for series in ("JRA", "NAR"):
            features = verified_model_features(root, series)
            output[series + "_model_checksums_verified"] = features is not None
            if features is not None:
                n = count_staged_cards(root, series, features, now)
                output[series + "_complete_future_cards"] = n
                ready |= n > 0
        if ready:
            output["status"] = "FUTURE_INPUTS_READY_PRIVATE_INFERENCE_PENDING"
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, csv.Error):
        output["status"] = "HOLD_PRIVATE_MODEL_OR_FEATURE_STRUCTURE_INVALID"
    return output


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--private-root", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(audit(args.private_root, datetime.now(timezone.utc)),
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
