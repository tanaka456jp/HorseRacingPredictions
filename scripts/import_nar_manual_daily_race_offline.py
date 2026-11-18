"""Offline import of a user-manually-downloaded future NAR DAILY race ZIP.

Personal use was reported as permitted by NAR telephone response. This
program NEVER requests any NAR endpoint. It prepares the identical local
private source/provenance contract used by the pre-off forecast-freeze
pipeline; the capture time is the actual local read time, never a
user-supplied file creation time. No results, betting or hindsight.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import secrets

from capture_nar_official_daily_preoff_once import (
    _JST, _OFFICIAL_RACE, _MAX_COMPRESSED,
    NarPreoffDailyHold, validate_official_daily_race_zip,
)

_INBOX_NAME = "manual-race-inbox"
_OFFICIAL_NAME = re.compile(
    r"([0-9]{8})_([1-9][0-9]{8,12})_race\.zip\Z"
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def import_user_downloaded_preoff_race(
    private_folder: Path, local_race_zip: Path,
):
    """Read one manually supplied ZIP, validate and archive without overwrite."""
    if (not isinstance(private_folder, Path) or
            not private_folder.is_dir() or private_folder.is_symlink()):
        raise NarPreoffDailyHold("NAR_MANUAL_RACE_PRIVATE_FOLDER_HOLD")
    inbox = private_folder / _INBOX_NAME
    if (not inbox.is_dir() or inbox.is_symlink()
            or not isinstance(local_race_zip, Path)
            or local_race_zip.parent != inbox
            or not local_race_zip.is_file()
            or local_race_zip.is_symlink()):
        raise NarPreoffDailyHold("NAR_MANUAL_RACE_INBOX_ONLY")
    now = _now_utc()
    if now.tzinfo is None or now.utcoffset() is None:
        raise NarPreoffDailyHold("NAR_MANUAL_RACE_LOCAL_CLOCK_INVALID")
    day = now.astimezone(_JST).date()
    match = _OFFICIAL_NAME.fullmatch(local_race_zip.name)
    if match is None or match[1] != day.strftime("%Y%m%d"):
        raise NarPreoffDailyHold("NAR_MANUAL_RACE_WRONG_DAY_OR_NAME")
    generated = datetime.fromtimestamp(int(match[2]), tz=timezone.utc)
    if (generated > now + __import__("datetime").timedelta(seconds=90)
            or generated.astimezone(_JST).date() != day):
        raise NarPreoffDailyHold("NAR_MANUAL_RACE_SOURCE_TIME_INVALID")
    originals = list(private_folder.glob(
        f"{day:%Y%m%d}_????????T??????Z_race.zip"
    ))
    if originals:
        raise NarPreoffDailyHold("NAR_MANUAL_RACE_PRIOR_SOURCE_EXISTS")
    size = local_race_zip.stat().st_size
    if not 32 <= size <= _MAX_COMPRESSED:
        raise NarPreoffDailyHold("NAR_MANUAL_RACE_FILE_SIZE_INVALID")
    blob = local_race_zip.read_bytes()
    observed = _now_utc()  # DO NOT backdate to user file mtime.
    audit = validate_official_daily_race_zip(
        blob, race_day=day, host_captured_utc=observed,
    )
    stamp = observed.strftime("%Y%m%dT%H%M%SZ")
    target = private_folder / f"{day:%Y%m%d}_{stamp}_race.zip"
    sidecar = private_folder / f"{day:%Y%m%d}_{stamp}_private_provenance.json"
    salt = secrets.token_bytes(32)
    metadata = {
        "schema": "NAR.OfficialDailyPreoffCapture.v1",
        "source": _OFFICIAL_RACE,
        "host_captured_utc": audit.host_captured_utc,
        "earliest_off_utc": audit.earliest_off_utc,
        "race_count": audit.flat_races,
        "salt_hex_PRIVATE": salt.hex(),
        "salted_zip_sha256_PRIVATE": sha256(
            b"NAR_OFFICIAL_DAILY_RACE_V1\x00" + salt + blob,
        ).hexdigest(),
        "source_input_mode": "USER_DOWNLOADED_OFFLINE",
        "source_origin_user_attested_not_independently_verified": True,
        "automated_nar_requests": 0,
        "independent_preoff_attestation": False,
        "source_and_provenance_never_upload": True,
    }
    for path, payload in (
        (target, blob),
        (sidecar, json.dumps(
            metadata, sort_keys=True,
        ).encode("utf-8")),
    ):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Offline-only future NAR user-downloaded race ZIP"
    )
    parser.add_argument("--private-capture-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        root = args.private_capture_dir
        day = _now_utc().astimezone(_JST).strftime("%Y%m%d")
        inbox = root / _INBOX_NAME
        if not inbox.is_dir() or inbox.is_symlink():
            raise NarPreoffDailyHold("NAR_MANUAL_RACE_INBOX_ONLY")
        matches = [
            p for p in inbox.iterdir()
            if _OFFICIAL_NAME.fullmatch(p.name)
            and p.name.startswith(day + "_")
        ]
        if len(matches) != 1:
            raise NarPreoffDailyHold("NAR_MANUAL_RACE_EXPECT_ONE_SOURCE")
        audit = import_user_downloaded_preoff_race(root, matches[0])
    except Exception:
        print(json.dumps({
            "schema": "NAR.PC2.ManualPreoffRaceOfflineAudit.v1",
            "status": "HOLD_NO_PROVIDER_REQUEST",
            "raw_source_uploaded": False,
            "real_tickets": 0, "positive_ev_proven": False,
        }, sort_keys=True))
        return 2
    print(json.dumps({
        "schema": "NAR.PC2.ManualPreoffRaceOfflineAudit.v1",
        "status": "PRIVATE_PREOFF_SOURCE_VALIDATED_NOT_YET_FROZEN",
        "flat_races": audit.flat_races,
        "horses": audit.registered_horses,
        "min_first_off_lead_seconds": audit.min_lead_seconds,
        "provider_network_requests": 0,
        "original_frozen_forecast_created": False,
        "independent_source_and_schedule_verified": False,
        "raw_source_uploaded": False,
        "real_tickets": 0, "positive_ev_proven": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
