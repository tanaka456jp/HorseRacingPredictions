"""One-shot, read-only official NAR DAILY race ZIP capture on PC2.

Use only the NAR-documented public daily race download endpoint, once per
invocation. Never download licensed JRA-VAN data, upload raw rows, settle
tickets, or open historical protected holdouts. The local host clock and
published ZIP filename do NOT constitute independent pre-off proof.
Official reference: https://www.keiba.go.jp/pdf/manual/data_pdf_manual.pdf
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import re
import secrets
import urllib.request
from zipfile import BadZipFile, ZipFile

_JST = timezone(timedelta(hours=9))
_OFFICIAL_RACE = "https://www.keiba.go.jp/KeibaWeb/DataDownload/RaceDataDownload?type=daily"
_MAX_COMPRESSED = 18 * 1024 * 1024
_MAX_UNCOMPRESSED = 32 * 1024 * 1024
_MIN_LEAD = timedelta(minutes=10)
_CSV_NAMES = {"racelist", "horselist", "payback"}
_RESULT_HORSE_COLUMNS = ("着順", "タイム", "着差", "上がり3F")
_RESULT_RACE_PREFIXES = ("上がり", "ハロンタイム", "コーナー通過順")


class NarPreoffDailyHold(ValueError):
    """No economically usable preoff evidence was certified."""


@dataclass(frozen=True)
class NarPreoffDailyAudit:
    race_day_jst: str
    flat_races: int
    out_of_scope_banei_races: int
    registered_horses: int
    earliest_off_utc: str
    host_captured_utc: str
    min_lead_seconds: int
    official_zip_structure_validated: bool = True
    host_clock_independently_attested: bool = False
    race_schedule_independently_verified: bool = False
    before_off_forecast_exists: bool = False
    real_wagers_placed: bool = False
    positive_expected_value_demonstrated: bool = False


def _rows(data: bytes, required: set[str]) -> list[dict[str, str]]:
    if len(data) > _MAX_UNCOMPRESSED:
        raise NarPreoffDailyHold("NAR_PREOFF_CSV_TOO_LARGE")
    try:
        decoded = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            decoded = data.decode("cp932")
        except UnicodeDecodeError:
            raise NarPreoffDailyHold("NAR_PREOFF_CSV_ENCODING_UNRECOGNIZED") from None
    reader = csv.DictReader(StringIO(decoded))
    if (not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames)
            or not required.issubset(set(reader.fieldnames))):
        raise NarPreoffDailyHold("NAR_PREOFF_OFFICIAL_CSV_HEADER_MISMATCH")
    result = []
    for row in reader:
        if (len(result) >= 5000 or None in row
                or any(value is None for value in row.values())):
            raise NarPreoffDailyHold("NAR_PREOFF_OFFICIAL_CSV_ROW_INVALID")
        result.append(row)
    return result


def validate_official_daily_race_zip(
    blob: bytes, *, race_day: date, host_captured_utc: datetime,
) -> NarPreoffDailyAudit:
    """Validate DAILY input before any outcome can have occurred.

    This is an offline structure/missingness check, not a trusted timestamp,
    not proof of current roster, not odds, and not economic evidence.
    """
    if (type(blob) is not bytes or len(blob) > _MAX_COMPRESSED
            or len(blob) < 32 or not blob.startswith(b"PK\x03\x04")
            or not isinstance(race_day, date)
            or isinstance(race_day, datetime)
            or not isinstance(host_captured_utc, datetime)
            or host_captured_utc.tzinfo is None
            or host_captured_utc.utcoffset() is None):
        raise NarPreoffDailyHold("NAR_PREOFF_CAPTURE_INPUT_INVALID")
    captured = host_captured_utc.astimezone(timezone.utc)
    if race_day != captured.astimezone(_JST).date():
        raise NarPreoffDailyHold("NAR_PREOFF_CURRENT_JST_DAY_REQUIRED")
    try:
        with ZipFile(BytesIO(blob)) as package:
            infos = package.infolist()
            if not 2 <= len(infos) <= 4:
                raise NarPreoffDailyHold("NAR_PREOFF_ZIP_MEMBERS_UNEXPECTED")
            members = {}
            total = 0
            for info in infos:
                name = info.filename
                match = re.fullmatch(
                    rf"{race_day:%Y%m%d}_(racelist|horselist|payback)\.csv", name,
                )
                if (not match or info.is_dir() or info.flag_bits & 1
                        or info.file_size > _MAX_UNCOMPRESSED or match[1] in members):
                    raise NarPreoffDailyHold("NAR_PREOFF_ZIP_MEMBER_UNTRUSTED")
                members[match[1]] = name
                total += info.file_size
            if (total > _MAX_UNCOMPRESSED
                    or not {"racelist", "horselist"}.issubset(members)):
                raise NarPreoffDailyHold("NAR_PREOFF_REQUIRED_FILES_MISSING")
            race_rows = _rows(package.read(members["racelist"]), {
                "競馬場", "競走年月日", "レース番号", "発走時刻", "頭数",
            })
            horse_rows = _rows(package.read(members["horselist"]), {
                "競馬場", "競走年月日", "レース番号", "馬番", "馬名",
                *_RESULT_HORSE_COLUMNS,
            })
    except (BadZipFile, RuntimeError, OSError, UnicodeError) as exc:
        raise NarPreoffDailyHold("NAR_PREOFF_ZIP_UNREADABLE") from exc
    if not 1 <= len(race_rows) <= 300 or not 4 <= len(horse_rows) <= 4500:
        raise NarPreoffDailyHold("NAR_PREOFF_RACE_OR_ROSTER_EMPTY")
    schedule = {}
    banei_count = 0
    for row in race_rows:
        if row["競走年月日"].strip() != race_day.strftime("%Y%m%d"):
            raise NarPreoffDailyHold("NAR_PREOFF_RACE_DATE_MISMATCH")
        place, number = row["競馬場"].strip(), row["レース番号"].strip()
        if place.startswith("帯広"):
            banei_count += 1
            continue
        clock = row["発走時刻"].strip().replace(":", "")
        headcount = row["頭数"].strip()
        if (not place or not number.isdecimal() or not 1 <= int(number) <= 20
                or not re.fullmatch(r"\d{4}", clock)
                or not headcount.isdecimal() or not 4 <= int(headcount) <= 18):
            raise NarPreoffDailyHold("NAR_PREOFF_UNSUPPORTED_SCHEDULE")
        hour, minute = int(clock[:2]), int(clock[2:])
        if hour > 23 or minute > 59:
            raise NarPreoffDailyHold("NAR_PREOFF_INVALID_OFF_TIME")
        # The official daily race list includes post-event outcome fields too.
        if any((value or "").strip() for key, value in row.items()
               if key.startswith(_RESULT_RACE_PREFIXES)):
            raise NarPreoffDailyHold("NAR_PREOFF_POST_EVENT_RACE_DATA_PRESENT")
        key = (place, number)
        if key in schedule:
            raise NarPreoffDailyHold("NAR_PREOFF_DUPLICATE_RACE")
        off = datetime.combine(race_day, time(hour, minute), _JST)
        schedule[key] = (int(headcount), off.astimezone(timezone.utc))
    if not schedule:
        raise NarPreoffDailyHold("NAR_PREOFF_NO_IN_SCOPE_FLAT_RACES")
    earliest = min(off for _, off in schedule.values())
    if captured + _MIN_LEAD >= earliest:
        raise NarPreoffDailyHold("NAR_PREOFF_NOT_EARLY_ENOUGH")
    counts = {}
    for row in horse_rows:
        if row["競馬場"].strip().startswith("帯広"):
            continue
        if row["競走年月日"].strip() != race_day.strftime("%Y%m%d"):
            raise NarPreoffDailyHold("NAR_PREOFF_HORSE_DATE_MISMATCH")
        key = (row["競馬場"].strip(), row["レース番号"].strip())
        number = row["馬番"].strip()
        if (key not in schedule or not number.isdecimal()
                or not 1 <= int(number) <= 18 or not row["馬名"].strip()
                or any((row.get(col) or "").strip() for col in _RESULT_HORSE_COLUMNS)):
            raise NarPreoffDailyHold("NAR_PREOFF_HORSE_RESULTS_OR_ROSTER_INVALID")
        counts.setdefault(key, set())
        if number in counts[key]:
            raise NarPreoffDailyHold("NAR_PREOFF_DUPLICATE_HORSE_NUMBER")
        counts[key].add(number)
    if set(counts) != set(schedule) or any(
        len(counts[k]) != total for k, (total, _) in schedule.items()
    ):
        raise NarPreoffDailyHold("NAR_PREOFF_INCOMPLETE_RACE_ROSTER")
    return NarPreoffDailyAudit(
        race_day_jst=race_day.isoformat(), flat_races=len(schedule),
        out_of_scope_banei_races=banei_count,
        registered_horses=sum(map(len, counts.values())),
        earliest_off_utc=earliest.isoformat().replace("+00:00", "Z"),
        host_captured_utc=captured.isoformat().replace("+00:00", "Z"),
        min_lead_seconds=int((earliest - captured).total_seconds()),
    )


def capture_once(*, directory: Path, now_utc: datetime) -> NarPreoffDailyAudit:
    """Single official fetch; persist ZIP privately only if ALL gates pass."""
    day = now_utc.astimezone(_JST).date()
    if (not directory.is_dir() or directory.is_symlink()
            or any(directory.glob(f"{day:%Y%m%d}_*_race.zip"))):
        raise NarPreoffDailyHold("NAR_PREOFF_PRIVATE_DIRECTORY_OR_DUPLICATE_INVALID")
    request = urllib.request.Request(
        _OFFICIAL_RACE, headers={"User-Agent": "HorseRacingPredictions/1.0 personal research"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.geturl() != _OFFICIAL_RACE:
            raise NarPreoffDailyHold("NAR_PREOFF_REDIRECT_REJECTED")
        blob = response.read(_MAX_COMPRESSED + 1)
    after_download = datetime.now(timezone.utc)
    audit = validate_official_daily_race_zip(
        blob, race_day=day, host_captured_utc=after_download,
    )
    stamp = after_download.strftime("%Y%m%dT%H%M%SZ")
    target = directory / f"{day:%Y%m%d}_{stamp}_race.zip"
    provenance = directory / f"{day:%Y%m%d}_{stamp}_private_provenance.json"
    salt = secrets.token_bytes(32)
    record = {
        "schema": "NAR.OfficialDailyPreoffCapture.v1",
        "source": _OFFICIAL_RACE,
        "host_captured_utc": audit.host_captured_utc,
        "earliest_off_utc": audit.earliest_off_utc,
        "race_count": audit.flat_races,
        "salt_hex_PRIVATE": salt.hex(),
        "salted_zip_sha256_PRIVATE": sha256(
            b"NAR_OFFICIAL_DAILY_RACE_V1\x00" + salt + blob,
        ).hexdigest(),
        "independent_preoff_attestation": False,
        "source_and_provenance_never_upload": True,
    }
    # Exclusive creation: no modifications to any existing ZIP or private data.
    for path, payload in (
        (target, blob),
        (provenance, json.dumps(record, sort_keys=True).encode("utf-8")),
    ):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    return audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        audit = capture_once(
            directory=args.private_output_dir,
            now_utc=datetime.now(timezone.utc),
        )
    except Exception:
        # No private ZIP path, identity, raw row, stack trace or digest in CI.
        print(json.dumps({
            "schema": "NAR.OfficialDailyPreoffCapture.v1", "result": "HOLD",
            "source_bytes_uploaded": False, "positive_ev_proven": False,
        }, sort_keys=True))
        return 2
    print(json.dumps({
        "schema": "NAR.OfficialDailyPreoffCapture.v1", "result": "PASS",
        "registered_races": audit.flat_races,
        "registered_horses": audit.registered_horses,
        "excluded_banei_races": audit.out_of_scope_banei_races,
        "lead_minutes": audit.min_lead_seconds // 60,
        "preoff_forecast_created": False,
        "independent_preoff_proof": False, "source_bytes_uploaded": False,
        "positive_ev_proven": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
