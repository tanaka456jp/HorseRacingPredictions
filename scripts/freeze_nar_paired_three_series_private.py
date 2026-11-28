"""PC2-only, offline, same-day three-series research freeze.

Inputs are already lawfully staged, explicitly reviewed, and never fetched.
Only the salted commitment and aggregate counts may leave the private PC.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
import argparse
import json
import os
from pathlib import Path
import secrets
from zipfile import ZipFile

import pandas as pd

from capture_nar_official_daily_preoff_once import _JST, _rows
from freeze_nar_partial_catboost_daily_private import partial_preoff_features
from horse_racing_predictions.nar_private_dual_model_loader import load_nar_private_dual_candidate
from horse_racing_predictions.nar_paired_future_comparison import (
    compare_nar_future_rankings, seal_paired_comparison,
)


def _read(path, limit):
    if (path.is_symlink() or not path.is_file()
            or not 0 < path.stat().st_size <= limit):
        raise ValueError("PAIRED_PRIVATE_INPUT_MISSING")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if not 0 < len(data) <= limit:
        raise ValueError("PAIRED_PRIVATE_INPUT_SIZE")
    return data


def _folder(path):
    if not path.is_dir() or path.is_symlink():
        raise ValueError("PAIRED_PRIVATE_DIRECTORY_MISSING")


def freeze(root: Path, *, clock=lambda: datetime.now(timezone.utc)):
    now = clock()
    if (os.environ.get("COMPUTERNAME") != "DESKTOP-MVV1FD4"
            or not root.is_absolute() or now.utcoffset() is None):
        raise ValueError("PAIRED_PRIVATE_CONTEXT")
    _folder(root)
    day = now.astimezone(_JST).date()
    prefix = day.strftime("%Y%m%d")
    capture = root / "nar-prospective-captures"
    staged = root / "forward-model-inputs"
    _folder(capture)
    _folder(staged)
    target = capture / f"{prefix}_NAR_paired_three_series_PRIVATE.json"
    if target.exists() or target.is_symlink():
        raise ValueError("PAIRED_PRIVATE_ALREADY_FROZEN")
    originals = list(capture.glob(f"{prefix}_????????T??????Z_race.zip"))
    if len(originals) != 1:
        raise ValueError("PAIRED_PRIVATE_SINGLE_PREOFF_ZIP_REQUIRED")
    original = originals[0]
    blob = _read(original, 18_000_000)
    provenance = json.loads(_read(original.with_name(
        original.name.replace("_race.zip", "_private_provenance.json")
    ), 100_000))
    salt = bytes.fromhex(provenance["salt_hex_PRIVATE"])
    if (provenance["schema"] != "NAR.OfficialDailyPreoffCapture.v1"
            or len(salt) != 32 or not secrets.compare_digest(
                sha256(b"NAR_OFFICIAL_DAILY_RACE_V1" + bytes([0])
                       + salt + blob).hexdigest(),
                provenance["salted_zip_sha256_PRIVATE"])):
        raise ValueError("PAIRED_PRIVATE_SOURCE_HASH_MISMATCH")
    observed = datetime.fromisoformat(provenance["host_captured_utc"].replace("Z", "+00:00"))
    if observed.utcoffset() is None or observed > now:
        raise ValueError("PAIRED_PRIVATE_SOURCE_TIME")
    frame, schedule, counts = partial_preoff_features(
        blob, race_day=day, captured_utc=observed)
    if now + timedelta(minutes=10) >= min(schedule.values()):
        raise ValueError("PAIRED_PRIVATE_TOO_LATE")
    entries_bytes = _read(staged / f"{prefix}_NAR_reviewed_entries.csv", 10_000_000)
    history_bytes = _read(staged / f"{prefix}_NAR_reviewed_prior_history.csv", 400_000_000)
    source_hashes = {
        "official_preoff_zip": sha256(blob).hexdigest(),
        "reviewed_entries": sha256(entries_bytes).hexdigest(),
        "reviewed_prior_history": sha256(history_bytes).hexdigest(),
    }
    review = json.loads(_read(staged / f"{prefix}_NAR_paired_review.json", 100_000))
    if (review != {
        "schema": "NAR.PC2.PairedInputReview.v1",
        "race_day_jst": day.isoformat(),
        "source_sha256_PRIVATE": source_hashes,
        "permitted_prior_history_reviewed": True,
        "same_scope_career_counts_reviewed": True,
        "horse_birth_identity_reviewed": True,
        "protected_holdout_used": False,
    }):
        raise ValueError("PAIRED_PRIVATE_EXPLICIT_REVIEW_REQUIRED")
    entries = pd.read_csv(BytesIO(entries_bytes), encoding="utf-8-sig",
        dtype={"race_id": str, "horse_id": str, "horse_name": str, "birth_ymd": str},
        keep_default_na=False)
    history = pd.read_csv(BytesIO(history_bytes), encoding="utf-8-sig",
        dtype=str, keep_default_na=False)
    history["finish_rank"] = history["finish_rank"].replace("", None)
    # Cross-check official horse names, not merely gate numbers and totals.
    with ZipFile(BytesIO(blob)) as package:
        rows = _rows(package.read(f"{prefix}_horselist.csv"),
                     {"競馬場", "レース番号", "馬番", "馬名"})
    official_names = {
        (f"NAR:{prefix}:{row['競馬場'].strip()}:{int(row['レース番号']):02d}",
         row["馬番"].strip()): row["馬名"].strip()
        for row in rows if not row["競馬場"].strip().startswith("帯広")
    }
    reviewed_names = {(row.race_id, row.horse_id): row.horse_name.strip()
                      for row in entries.itertuples(index=False)}
    if reviewed_names != official_names or len(entries) != len(official_names):
        raise ValueError("PAIRED_PRIVATE_HORSE_IDENTITY_MISMATCH")
    loaded = load_nar_private_dual_candidate(
        root / "nar-forward-models" / "2017-2021-fit-2022-tune-v1")
    generated = clock()
    if generated < now:
        raise ValueError("PAIRED_PRIVATE_CLOCK_REVERSED")
    comparison = compare_nar_future_rankings(
        official_partial=frame, reviewed_entries=entries, history=history,
        off_by_race=schedule, expected_runner_counts=frame.groupby("race_id").size().to_dict(),
        race_day_jst=day.isoformat(), source_asof_utc=observed,
        generated_utc=generated, loaded=loaded)
    record = seal_paired_comparison(comparison, source_sha256=source_hashes,
                                   private_salt=secrets.token_bytes(32))
    data = json.dumps(record, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
    finished = clock()
    if finished < generated or finished + timedelta(minutes=10) >= min(schedule.values()):
        raise ValueError("PAIRED_PRIVATE_TOO_LATE")
    fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return {"schema": "NAR.PC2.PairedThreeSeriesFreezeSummary.v1",
            "status": "PRIVATE_PAIRED_FORECAST_FROZEN_RECEIPT_PENDING",
            "race_day_jst": day.isoformat(), "races": counts["races"],
            "runners": counts["runners"],
            "earliest_off_utc": min(schedule.values()).isoformat().replace("+00:00", "Z"),
            "blinded_digest": record["blinded_digest"],
            "independent_preoff_receipt_verified": False, "actual_bets": 0,
            "raw_source_uploaded": False, "positive_ev_proven": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = freeze(args.private_root)
    except Exception:
        print(json.dumps({"status": "HOLD_PAIRED_PRIVATE_INPUT_OR_CLOCK",
                          "actual_bets": 0, "raw_source_uploaded": False,
                          "positive_ev_proven": False}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
