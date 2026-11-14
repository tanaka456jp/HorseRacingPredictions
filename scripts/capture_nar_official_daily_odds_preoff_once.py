"""Private bounded one-shot NAR *interim* official DAILY odds capture on PC2.

Always preserve the 2026-11-10 complete prior pre-off forecast and original
daily ZIP. NEVER modify choices on seeing market prices or official results.
This is a paper research snapshot, not a bet, real-money ROI or executable
trading price. No licensed source, horse, odds or private salt leaves PC2.

Official schema: https://www.keiba.go.jp/pdf/manual/data_pdf_manual.pdf
NAR data-download button URL, verified public endpoint:
https://www.keiba.go.jp/KeibaWeb/DataDownload/OddsDataDownload?type=daily
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO, TextIOWrapper
import json
import os
from pathlib import Path
import re
import secrets
import urllib.request
from zipfile import BadZipFile, ZipFile

from capture_nar_official_daily_preoff_once import (
    _JST, NarPreoffDailyHold,
)
from freeze_nar_official_daily_baseline import prepare_private_daily_baseline

_OFFICIAL_ODDS_URL = (
    "https://www.keiba.go.jp/KeibaWeb/DataDownload/OddsDataDownload?type=daily"
)
_MAX_ZIP_BYTES = 48 * 1024 * 1024
_MAX_UNCOMPRESSED = 256 * 1024 * 1024
_MAX_ROWS = 1_500_000
_MAX_SNAPSHOTS_PER_DAY = 6
_MIN_REQUEST_GAP = timedelta(seconds=150)
_MIN_ALL_RACE_LEAD = timedelta(minutes=10)
_REQUIRED = frozenset({
    "競馬場", "競走年月日", "レース番号", "賭式",
    "番号1", "番号2", "番号3", "オッズ", "オッズ（最大）", "人気",
})
_SCHEME = {"単勝": "WIN", "複勝": "PLACE"}
_PRIVATE_DOMAIN = b"NAR_DAILY_INTERIM_ODDS_PREOFF_V1\x00"
_DIGITS = re.compile(r"[0-9]{1,6}(?:\.[0-9]{1,3})?\Z")
_DAY_ZIP_NAME = re.compile(r"([0-9]{8})_([1-9][0-9]{8,12})_odds\.zip\Z")


@dataclass(frozen=True)
class NarPrivateOddsAudit:
    schema: str
    source_day_jst: str
    registered_flat_races: int
    frozen_registered_horses: int
    market_rows: int
    win_rows: int
    place_rows: int
    in_scope_races_with_win_quote: int
    in_scope_races_with_place_quote: int
    planned_win_tickets_with_price: int
    planned_place_tickets_with_min_price: int
    planned_place_tickets_with_max_price: int
    planned_ticket_count: int
    missing_win_prices: int
    missing_place_min_prices: int
    source_generated_at_utc: str
    observed_at_utc: str
    minutes_before_first_scheduled_off: int
    complete_forecast_previously_frozen: bool = True
    odds_influenced_selection: bool = False
    independent_official_schedule_verified: bool = False
    price_executable_at_order_time_verified: bool = False
    any_purchases: bool = False
    after_cost_positive_ev_verified: bool = False


def _decode_number(value: str, *, optional: bool = False) -> str | None:
    v = value.strip().replace("．", ".")
    if not v or v in {"-", "--", "---", "発売前", "発売なし", "取消", "中止"}:
        return None
    if not _DIGITS.fullmatch(v):
        raise NarPreoffDailyHold("NAR_PREOFF_ODDS_NUMERIC_FORMAT_INVALID")
    try:
        amount = Decimal(v)
    except InvalidOperation:
        raise NarPreoffDailyHold("NAR_PREOFF_ODDS_PRICE_INVALID") from None
    if amount <= 0 or amount > 999999:
        # Not offered is not the same as a price of 0 yen.
        return None if amount == 0 else _reject_high()
    return str(amount)


def _reject_high() -> None:
    raise NarPreoffDailyHold("NAR_PREOFF_ODDS_OUT_OF_RANGE")


def _load_original_frozen_forecast(folder: Path, race_day: date) -> tuple[dict, bytes]:
    """Verify actual private source + full previously frozen selection.

    No historical 2023+ files; only today's exact private original capture.
    """
    key = race_day.strftime("%Y%m%d")
    files = list(folder.glob(f"{key}_????????T??????Z_race.zip"))
    if len(files) != 1:
        raise NarPreoffDailyHold("NAR_PREOFF_REQUIRES_ORIGINAL_RACE_CAPTURE")
    original = files[0]
    meta = original.with_name(
        original.name.replace("_race.zip", "_private_provenance.json")
    )
    frozen = folder / f"{key}_baseline_forecast_PRIVATE.json"
    if any((not p.is_file() or p.is_symlink()) for p in (original, meta, frozen)):
        raise NarPreoffDailyHold("NAR_PREOFF_FORECAST_SOURCE_MISSING")
    metadata = json.loads(meta.read_text(encoding="utf-8"))
    snapshot = json.loads(frozen.read_text(encoding="utf-8"))
    blob = original.read_bytes()
    salt = bytes.fromhex(metadata["salt_hex_PRIVATE"])
    if (metadata.get("schema") != "NAR.OfficialDailyPreoffCapture.v1"
            or metadata.get("source") != (
                "https://www.keiba.go.jp/KeibaWeb/DataDownload/RaceDataDownload?type=daily"
            )
            or len(salt) != 32
            or not secrets.compare_digest(
                sha256(b"NAR_OFFICIAL_DAILY_RACE_V1\x00" + salt + blob).hexdigest(),
                metadata["salted_zip_sha256_PRIVATE"],
            )):
        raise NarPreoffDailyHold("NAR_PREOFF_SOURCE_PROVENANCE_CHANGED")
    if not isinstance(snapshot, dict):
        raise NarPreoffDailyHold("NAR_PREOFF_FORECAST_MISSING")
    generated = datetime.fromisoformat(snapshot["host_generated_utc"])
    observed = datetime.fromisoformat(metadata["host_captured_utc"].replace("Z", "+00:00"))
    private_salt = bytes.fromhex(snapshot["private_salt_hex"])
    if len(private_salt) != 32:
        raise NarPreoffDailyHold("NAR_PREOFF_FORECAST_SALT_INVALID")
    again, digest = prepare_private_daily_baseline(
        blob, observed_at_utc=observed, generated_at_utc=generated,
        race_day=race_day, private_salt=private_salt,
    )
    if (again != snapshot or
            not secrets.compare_digest(digest, snapshot["commitment_digest"])):
        raise NarPreoffDailyHold("NAR_PREOFF_FORECAST_SNAPSHOT_MODIFIED")
    return snapshot, blob


def _parse_csv_bounded(
    package: ZipFile, name: str, *,
    expected: dict[str, dict],
    race_day: date,
) -> tuple[dict[str, dict[str, dict[str, dict]]], dict[str, int]]:
    """Stream only WIN/PLACE quotes, retaining missingness on full frozen races."""
    if (len(package.infolist()) != 1 or
            package.infolist()[0].filename != name or
            package.infolist()[0].flag_bits & 1 or
            package.infolist()[0].file_size > _MAX_UNCOMPRESSED):
        raise NarPreoffDailyHold("NAR_PREOFF_ODDS_ARCHIVE_LAYOUT_INVALID")
    if not package.testzip() is None:
        raise NarPreoffDailyHold("NAR_PREOFF_ODDS_ARCHIVE_CRC_FAILED")
    stats = {"market_rows": 0, "win_rows": 0, "place_rows": 0}
    selections = {rid: {"WIN": {}, "PLACE": {}} for rid in expected}
    # Try UTF-8-SIG first, then official PC CSV-compatible CP932;
    # never decode with replacement that could mangle track/horse keys.
    last_decode_error = None
    for encoding in ("utf-8-sig", "cp932"):
        stats = {"market_rows": 0, "win_rows": 0, "place_rows": 0}
        selections = {rid: {"WIN": {}, "PLACE": {}} for rid in expected}
        try:
            with package.open(name) as binary:
                with TextIOWrapper(binary, encoding=encoding, errors="strict", newline="") as text:
                    rows = csv.DictReader(text)
                    if (not rows.fieldnames
                            or len(set(rows.fieldnames)) != len(rows.fieldnames)
                            or not _REQUIRED.issubset(set(rows.fieldnames))):
                        raise NarPreoffDailyHold("NAR_PREOFF_ODDS_OFFICIAL_CSV_SCHEMA_CHANGED")
                    for row in rows:
                        stats["market_rows"] += 1
                        if (stats["market_rows"] > _MAX_ROWS or None in row
                                or any(v is None for v in row.values())):
                            raise NarPreoffDailyHold("NAR_PREOFF_ODDS_ROW_INVALID")
                        if row["競走年月日"].strip() != race_day.strftime("%Y%m%d"):
                            raise NarPreoffDailyHold("NAR_PREOFF_ODDS_ROW_WRONG_DAY")
                        track = row["競馬場"].strip()
                        if track.startswith("帯広"):
                            continue
                        kind = _SCHEME.get(row["賭式"].strip())
                        if kind is None:
                            continue
                        number = row["レース番号"].strip()
                        horse = row["番号1"].strip()
                        if (not number.isascii() or not number.isdecimal()
                                or not horse.isascii() or not horse.isdecimal()
                                or row["番号2"].strip() or row["番号3"].strip()):
                            raise NarPreoffDailyHold("NAR_PREOFF_ODDS_TICKET_KEY_INVALID")
                        rid = f"NAR:{race_day:%Y%m%d}:{track}:{int(number):02d}"
                        if rid not in selections:
                            # A non-frozen in-scope race must not silently be
                            # treated as one of the initially selected races.
                            raise NarPreoffDailyHold("NAR_PREOFF_ODDS_RACE_NOT_IN_FROZEN_CALENDAR")
                        if horse not in expected[rid]["winner_scores"]:
                            raise NarPreoffDailyHold("NAR_PREOFF_ODDS_HORSE_NOT_FROZEN")
                        if horse in selections[rid][kind]:
                            raise NarPreoffDailyHold("NAR_PREOFF_ODDS_DUPLICATE_TICKET")
                        price = _decode_number(row["オッズ"])
                        upper = _decode_number(row["オッズ（最大）"])
                        if (kind == "WIN" and upper is not None
                                or kind == "PLACE" and upper is not None
                                and price is not None and Decimal(upper) < Decimal(price)):
                            raise NarPreoffDailyHold("NAR_PREOFF_ODDS_RANGE_INVALID")
                        popularity = row["人気"].strip()
                        if popularity and (
                            not popularity.isascii() or not popularity.isdecimal()
                        ):
                            raise NarPreoffDailyHold("NAR_PREOFF_ODDS_POPULARITY_INVALID")
                        selections[rid][kind][horse] = {
                            "min_quote": price,
                            "max_quote": upper if kind == "PLACE" else None,
                            "popularity": int(popularity) if popularity else None,
                        }
                        stats["win_rows" if kind == "WIN" else "place_rows"] += 1
            return selections, stats
        except UnicodeDecodeError as exc:
            last_decode_error = exc
    raise NarPreoffDailyHold("NAR_PREOFF_ODDS_CSV_ENCODING_INVALID") from last_decode_error


def validate_private_official_odds_zip(
    odds_blob: bytes, *, day: date,
    source_filename: str, captured_utc: datetime,
    frozen: dict,
) -> tuple[NarPrivateOddsAudit, dict]:
    """Parse and compare official interim odds against an UNCHANGED complete forecast.

    Returns the private selected quotes; no market filter or new forecast.
    """
    if (not isinstance(day, date) or isinstance(day, datetime)
            or type(odds_blob) is not bytes
            or len(odds_blob) < 32 or len(odds_blob) > _MAX_ZIP_BYTES
            or not odds_blob.startswith(b"PK\x03\x04")
            or captured_utc.tzinfo is None
            or captured_utc.utcoffset() is None
            or not isinstance(frozen, dict)
            or frozen.get("schema") != "NAR.PC2.OfficialDailyForwardBaseline.v1"
            or frozen.get("day") != day.isoformat()
            or frozen.get("odds_observed") is not False
            or frozen.get("no_real_tickets") is not True):
        raise NarPreoffDailyHold("NAR_PREOFF_ODDS_INPUT_OR_PRIOR_FORECAST_INVALID")
    now = captured_utc.astimezone(timezone.utc)
    off = datetime.fromisoformat(frozen["earliest_off_utc"].replace("Z", "+00:00"))
    if (now.astimezone(_JST).date() != day
            or not now + _MIN_ALL_RACE_LEAD < off):
        raise NarPreoffDailyHold("NAR_PREOFF_ODDS_TOO_LATE_FOR_FULL_CALENDAR")
    match = _DAY_ZIP_NAME.fullmatch(source_filename)
    if match is None or match[1] != day.strftime("%Y%m%d"):
        raise NarPreoffDailyHold("NAR_PREOFF_ODDS_OFFICIAL_NAME_INVALID")
    source_time = datetime.fromtimestamp(int(match[2]), tz=timezone.utc)
    if (source_time > now + timedelta(seconds=90)
            or now - source_time > timedelta(minutes=25)):
        raise NarPreoffDailyHold("NAR_PREOFF_ODDS_SOURCE_TIMESTAMP_STALE_OR_FUTURE")
    rows = frozen["complete_private_forecasts"]
    expected = {r["race_id"]: r for r in rows}
    if (len(expected) != len(rows)
            or len(expected) != frozen["source_races"]):
        raise NarPreoffDailyHold("NAR_PREOFF_ODDS_FORECAST_RACE_COUNT_MISMATCH")
    try:
        with ZipFile(BytesIO(odds_blob)) as package:
            selection, stats = _parse_csv_bounded(
                package, f"{day:%Y%m%d}_odds.csv",
                expected=expected, race_day=day,
            )
    except (BadZipFile, RuntimeError, EOFError) as exc:
        raise NarPreoffDailyHold("NAR_PREOFF_ODDS_ZIP_INVALID") from exc
    selected_quotes = []
    win_p, place_p, place_u = 0, 0, 0
    win_races = sum(bool(v["WIN"]) for v in selection.values())
    place_races = sum(bool(v["PLACE"]) for v in selection.values())
    for rid in sorted(expected):
        pick = expected[rid]
        h_win = pick["top3"][0]
        h_place = pick["outsider"]
        w = selection[rid]["WIN"].get(h_win, {})
        p = selection[rid]["PLACE"].get(h_place, {})
        win_p += bool(w.get("min_quote"))
        place_p += bool(p.get("min_quote"))
        place_u += bool(p.get("max_quote"))
        selected_quotes.append({
            "race_id": rid,
            "scheduled_off_utc": pick["scheduled_off_utc"],
            "frozen_win_horse_number": h_win,
            "frozen_place_horse_number": h_place,
            "win_interim_odds": w.get("min_quote"),
            "place_interim_odds_min": p.get("min_quote"),
            "place_interim_odds_max": p.get("max_quote"),
            "win_popularity": w.get("popularity"),
            "place_popularity": p.get("popularity"),
            "original_full_race_offered_win_odds_count": len(selection[rid]["WIN"]),
            "original_full_race_offered_place_odds_count": len(selection[rid]["PLACE"]),
            "forecast_modified": False, "tickets_purchased": False,
        })
    audit = NarPrivateOddsAudit(
        schema="NAR.PC2.OfficialDailyInterimOddsAudit.v1",
        source_day_jst=day.isoformat(),
        registered_flat_races=len(expected),
        frozen_registered_horses=frozen["source_horses"],
        market_rows=stats["market_rows"],
        win_rows=stats["win_rows"],
        place_rows=stats["place_rows"],
        in_scope_races_with_win_quote=win_races,
        in_scope_races_with_place_quote=place_races,
        planned_win_tickets_with_price=win_p,
        planned_place_tickets_with_min_price=place_p,
        planned_place_tickets_with_max_price=place_u,
        planned_ticket_count=2*len(expected),
        missing_win_prices=len(expected)-win_p,
        missing_place_min_prices=len(expected)-place_p,
        source_generated_at_utc=source_time.isoformat().replace("+00:00","Z"),
        observed_at_utc=now.isoformat().replace("+00:00","Z"),
        minutes_before_first_scheduled_off=int((off-now).total_seconds()//60),
    )
    return audit, {"selected_quotes_PRIVATE": selected_quotes,
                   "all_market_per_race_PRIVATE": selection}


def capture_private_daily_odds_once(directory: Path) -> NarPrivateOddsAudit:
    """At most one official request per invocation; never overwrite a snapshot."""
    if not directory.is_dir() or directory.is_symlink():
        raise NarPreoffDailyHold("NAR_PREOFF_ODDS_D_PATH_INVALID")
    now = datetime.now(timezone.utc)
    day = now.astimezone(_JST).date()
    frozen, _ = _load_original_frozen_forecast(directory, day)
    first_off = datetime.fromisoformat(
        frozen["earliest_off_utc"].replace("Z", "+00:00")
    )
    if now + _MIN_ALL_RACE_LEAD >= first_off:
        raise NarPreoffDailyHold("NAR_PREOFF_ODDS_CAPTURE_WINDOW_CLOSED")
    existing = list(directory.glob(f"{day:%Y%m%d}_*_odds_private_provenance.json"))
    if len(existing) >= _MAX_SNAPSHOTS_PER_DAY:
        raise NarPreoffDailyHold("NAR_PREOFF_ODDS_DAILY_CAPTURE_LIMIT")
    for p in existing:
        if not p.is_file() or p.is_symlink():
            raise NarPreoffDailyHold("NAR_PREOFF_ODDS_PROVENANCE_BAD")
        meta = json.loads(p.read_text(encoding="utf-8"))
        if meta.get("schema") != "NAR.PC2.OfficialDailyInterimOddsProvenance.v1":
            raise NarPreoffDailyHold("NAR_PREOFF_ODDS_PROVENANCE_SCHEMA_INVALID")
        old = datetime.fromisoformat(meta["captured_utc"].replace("Z","+00:00"))
        if now - old < _MIN_REQUEST_GAP:
            raise NarPreoffDailyHold("NAR_PREOFF_ODDS_REQUEST_TOO_SOON")
    request = urllib.request.Request(
        _OFFICIAL_ODDS_URL, headers={
            "User-Agent": "HorseRacingPredictions/1.0 personal-private-research",
        },
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        if response.geturl() != _OFFICIAL_ODDS_URL:
            raise NarPreoffDailyHold("NAR_PREOFF_ODDS_REDIRECT_OR_WRONG_SOURCE")
        cd = response.headers.get("Content-Disposition", "")
        match = re.search(r'filename="?([0-9]{8}_[0-9]{9,13}_odds\.zip)"?', cd)
        if not match:
            raise NarPreoffDailyHold("NAR_PREOFF_ODDS_OFFICIAL_NAME_MISSING")
        name = match[1]
        blob = response.read(_MAX_ZIP_BYTES + 1)
    captured = datetime.now(timezone.utc)
    audit, private_selected = validate_private_official_odds_zip(
        blob, day=day, source_filename=name,
        captured_utc=captured, frozen=frozen,
    )
    destination = directory / name
    meta_path = directory / name.replace("_odds.zip", "_odds_private_provenance.json")
    # Do not overwrite repeated source snapshots.
    salt = secrets.token_bytes(32)
    provenance = {
        "schema": "NAR.PC2.OfficialDailyInterimOddsProvenance.v1",
        "official_endpoint": _OFFICIAL_ODDS_URL,
        "official_filename": name,
        "source_generated_utc": audit.source_generated_at_utc,
        "captured_utc": audit.observed_at_utc,
        "frozen_private_forecast_digest": frozen["commitment_digest"],
        "source_zip_sha256_salted_PRIVATE": sha256(
            _PRIVATE_DOMAIN + salt + blob,
        ).hexdigest(),
        "source_salt_hex_PRIVATE": salt.hex(),
        "audit_PRIVATE": asdict(audit),
        "selected_quotes_PRIVATE": private_selected,
        "external_official_schedule_verified": False,
        "actual_purchase_executability_verified": False,
        "positive_ev_proven": False,
    }
    for p, data in (
        (destination, blob),
        (meta_path, json.dumps(provenance, ensure_ascii=False,
                              sort_keys=True).encode("utf-8")),
    ):
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    return audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-capture-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        a = capture_private_daily_odds_once(args.private_capture_dir)
    except Exception:
        print(json.dumps({
            "schema": "NAR.PC2.OfficialDailyInterimOddsAudit.v1",
            "result": "RESEARCH_HOLD",
            "no_original_data_uploaded": True,
            "after_cost_positive_ev_verified": False,
        }, sort_keys=True))
        return 2
    print(json.dumps({
        "schema": a.schema,
        "result": ("PRIVATE_REAL_INTERIM_QUOTES_CAPTURED"
                   if a.planned_win_tickets_with_price + a.planned_place_tickets_with_min_price > 0
                   else "PRIVATE_OFFICIAL_ZIP_CAPTURED_NO_QUOTED_PRICES_YET"),
        "flat_races": a.registered_flat_races,
        "registered_horses": a.frozen_registered_horses,
        "raw_market_rows": a.market_rows,
        "win_rows": a.win_rows,
        "place_rows": a.place_rows,
        "quoted_win_races": a.in_scope_races_with_win_quote,
        "quoted_place_races": a.in_scope_races_with_place_quote,
        "frozen_win_tickets_with_quote": a.planned_win_tickets_with_price,
        "frozen_place_tickets_with_quote": a.planned_place_tickets_with_min_price,
        "frozen_place_tickets_with_upper_bound": a.planned_place_tickets_with_max_price,
        "missing_frozen_win_quotes": a.missing_win_prices,
        "missing_frozen_place_quotes": a.missing_place_min_prices,
        "minutes_before_first_scheduled_off": a.minutes_before_first_scheduled_off,
        "official_source_time_utc": a.source_generated_at_utc,
        "observed_time_utc": a.observed_at_utc,
        "original_forecast_unchanged": True,
        "source_uploaded": False,
        "actual_tickets": 0,
        "after_cost_ev_proven": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
