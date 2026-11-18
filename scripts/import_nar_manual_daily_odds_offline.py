"""User-downloaded NAR daily odds ZIP: *offline*, private PC2 research only.

This is a distinct workflow from repeated automated provider requests.
No provider SDK, HTTP, browser automation or external source call occurs.
The user's reported NAR telephone permission covers personal research and
source-attributed information sharing, not demonstrated automated polling.

All derived prices/race IDs remain in PC2's private D-drive area.
Source file times are NOT proof of actual order execution or a hosted receipt.
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

from capture_nar_official_daily_preoff_once import _JST, NarPreoffDailyHold
from capture_nar_official_daily_odds_preoff_once import (
    _DAY_ZIP_NAME,
    _MAX_ZIP_BYTES,
    _PRIVATE_DOMAIN,
    _load_original_frozen_forecast,
    validate_private_official_odds_zip,
)

_INBOX_NAME = "manual-odds-inbox"
_MAX_MANUAL_ARCHIVES_IN_DAY = 6


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def import_user_downloaded_daily_odds(
    private_folder: Path, local_odds_zip: Path,
):
    """Validate the manually supplied original ZIP strictly before saving.

    The local file must already be in the restricted PC2 inbox.
    Never backdate receipt to source filename, mtime or user testimony.
    """
    if (not isinstance(private_folder, Path) or
            not private_folder.is_dir() or private_folder.is_symlink()):
        raise NarPreoffDailyHold("NAR_MANUAL_ODDS_PRIVATE_FOLDER_HOLD")
    inbox = private_folder / _INBOX_NAME
    if (not inbox.is_dir() or inbox.is_symlink()
            or not isinstance(local_odds_zip, Path)
            or local_odds_zip.parent != inbox
            or not local_odds_zip.is_file()
            or local_odds_zip.is_symlink()):
        raise NarPreoffDailyHold("NAR_MANUAL_ODDS_INBOX_ONLY")
    now = _now_utc()
    if now.tzinfo is None or now.utcoffset() is None:
        raise NarPreoffDailyHold("NAR_MANUAL_ODDS_RECEIPT_CLOCK_INVALID")
    day = now.astimezone(_JST).date()
    filename = local_odds_zip.name
    m = _DAY_ZIP_NAME.fullmatch(filename)
    if not m or m[1] != day.strftime("%Y%m%d"):
        raise NarPreoffDailyHold("NAR_MANUAL_ODDS_WRONG_DAY_OR_FILENAME")
    size = local_odds_zip.stat().st_size
    if not 32 <= size <= _MAX_ZIP_BYTES:
        raise NarPreoffDailyHold("NAR_MANUAL_ODDS_ZIP_SIZE_INVALID")
    provenance = private_folder / filename.replace(
        "_odds.zip", "_manually_downloaded_odds_PRIVATE.json",
    )
    if provenance.exists() or provenance.is_symlink():
        raise NarPreoffDailyHold("NAR_MANUAL_ODDS_ALREADY_IMPORTED")
    existing = list(private_folder.glob(
        f"{day:%Y%m%d}_*_manually_downloaded_odds_PRIVATE.json"
    ))
    if len(existing) >= _MAX_MANUAL_ARCHIVES_IN_DAY:
        raise NarPreoffDailyHold("NAR_MANUAL_ODDS_DAILY_PRIVATE_LIMIT")
    frozen, _ = _load_original_frozen_forecast(private_folder, day)
    raw = local_odds_zip.read_bytes()
    # The current local wall clock is the receiver's actual first
    # successful read; user-provided file metadata cannot backdate it.
    received = _now_utc()
    audit, selected_private = validate_private_official_odds_zip(
        raw, day=day, source_filename=filename,
        captured_utc=received, frozen=frozen,
    )
    salt = secrets.token_bytes(32)
    document = {
        "schema": "NAR.PC2.ManuallyDownloadedDailyOddsAuditPrivate.v1",
        "download_mode": "USER_SUPPLIED_OFFLINE_NO_PROVIDER_REQUEST",
        "user_reported_source": "NAR official daily odds download",
        "user_reported_authority": (
            "NAR telephone response: personal use or source-attributed "
            "website information sharing, no resale"
        ),
        "individual_authorized_automated_polling": False,
        "source_hostname_independently_attested": False,
        "independent_hosted_receipt_verified": False,
        "actual_order_execution_verified": False,
        "positive_ev_proven": False,
        "source_zip_filename_PRIVATE": filename,
        "private_salted_source_sha256": sha256(
            _PRIVATE_DOMAIN + salt + raw
        ).hexdigest(),
        "private_salt_hex": salt.hex(),
        "local_receipt_utc": received.isoformat(),
        "frozen_forecast_commitment_PRIVATE": frozen["commitment_digest"],
        "audit_PRIVATE": asdict(audit),
        "quotes_PRIVATE": selected_private,
        "source_uploaded": False,
    }
    # No overwrite, single private sidecar, original source untouched.
    fd = os.open(provenance, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(json.dumps(
            document, ensure_ascii=False, sort_keys=True,
        ).encode("utf-8"))
        stream.flush()
        os.fsync(stream.fileno())
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Offline-only NAR manually downloaded daily odds ZIP"
    )
    parser.add_argument("--private-capture-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        folder = args.private_capture_dir
        now = _now_utc()
        day = now.astimezone(_JST).date()
        inbox = folder / _INBOX_NAME
        if not inbox.is_dir() or inbox.is_symlink():
            raise NarPreoffDailyHold("NAR_MANUAL_ODDS_INBOX_ONLY")
        candidates = [
            p for p in inbox.iterdir()
            if _DAY_ZIP_NAME.fullmatch(p.name)
            and p.name.startswith(day.strftime("%Y%m%d") + "_")
        ]
        if len(candidates) != 1:
            raise NarPreoffDailyHold(
                "NAR_MANUAL_ODDS_EXPECT_EXACT_ONE_CURRENT_DAY_ZIP"
            )
        a = import_user_downloaded_daily_odds(folder, candidates[0])
    except Exception:
        # No local exception text, filename, races or original odds
        # can appear in the publicly retrievable Actions logs.
        print(json.dumps({
            "schema": "NAR.PC2.ManualDailyOddsOfflineAudit.v1",
            "status": "RESEARCH_HOLD_NO_PROVIDER_REQUEST",
            "source_uploaded": False,
            "actual_tickets": 0,
            "positive_ev_proven": False,
        }, sort_keys=True))
        return 2
    print(json.dumps({
        "schema": "NAR.PC2.ManualDailyOddsOfflineAudit.v1",
        "status": (
            "PRIVATE_OFFLINE_INTERIM_QUOTES_SEEN_INDICATIVE_ONLY"
            if a.planned_win_tickets_with_price
            or a.planned_place_tickets_with_min_price
            else "PRIVATE_OFFLINE_SOURCE_READ_ZERO_VALID_QUOTES"
        ),
        "source_day_jst": a.source_day_jst,
        "frozen_flat_races": a.registered_flat_races,
        "future_preoff_eligible_races": a.future_preoff_eligible_races,
        "past_or_closed_races": a.past_or_closed_races,
        "quoted_selected_win": a.planned_win_tickets_with_price,
        "quoted_selected_place": a.planned_place_tickets_with_min_price,
        "missing_selected_win": a.missing_win_prices,
        "missing_selected_place": a.missing_place_min_prices,
        "late_price_rows_ignored": a.after_cutoff_raw_quote_rows_ignored,
        "provider_network_requests": 0,
        "official_provider_provenance_independent": False,
        "order_executability_verified": False,
        "positive_ev_proven": False,
        "private_source_uploaded": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
