"""PC2 private DAILY real-roster baseline forecast frozen BEFORE all first offs.

This is a prospective fixed *historical form baseline* based only on
official '全成績' pre-off career totals, NOT CatBoost or positive EV.
No unapproved data API, no NAR archive beyond today's already captured ZIP,
no bets, no result rows, no odds or JRA-VAN source. Private full snapshot
stays on D. Its *salted* commitment can be registered externally later.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import secrets
from zipfile import ZipFile

from capture_nar_official_daily_preoff_once import (
    _JST, _rows, validate_official_daily_race_zip, NarPreoffDailyHold,
)
from horse_racing_predictions.nar_forward_preoff_commitment import (
    NarProspectiveForecast, seal_nar_prospective_batch,
)

_POLICY_NAME = "NAR_OFFICIAL_CAREER_FORM_BASELINE_V1_FIXED_20261110"
_POLICY_SHA = sha256(_POLICY_NAME.encode("ascii")).hexdigest()
_NO_BETS = True


def _record(row: dict[str, str]) -> tuple[int, int, int]:
    """Official career form W-2nd-3rd-unplaced; no same-day race result."""
    raw = row.get("全成績", "").replace(" ", "").replace("　", "")
    match = re.fullmatch(r"(\d+)-(\d+)-(\d+)-(\d+)", raw)
    if not match:
        raise NarPreoffDailyHold("NAR_FORWARD_CAREER_FORM_MISSING")
    wins, second, third, other = map(int, match.groups())
    starts = wins + second + third + other
    if (starts > 500 or wins + second + third > starts
            or any(x < 0 for x in (wins, second, third, other))):
        raise NarPreoffDailyHold("NAR_FORWARD_CAREER_FORM_IMPLAUSIBLE")
    return starts, wins, wins + second + third


def prepare_private_daily_baseline(
    blob: bytes, *, observed_at_utc: datetime,
    generated_at_utc: datetime, race_day: date,
    private_salt: bytes,
) -> tuple[dict, str]:
    """Return a complete PRIVATE snapshot and its blind salted commitment.

    Live-day official career forms do not reproduce the historical 2017-21
    source feature contract, so this model is explicitly a non-ML comparator.
    """
    audit = validate_official_daily_race_zip(
        blob, race_day=race_day, host_captured_utc=observed_at_utc,
    )
    generated = generated_at_utc.astimezone(timezone.utc)
    if (generated.tzinfo is None or generated.astimezone(_JST).date() != race_day
            or generated >= datetime.fromisoformat(
                audit.earliest_off_utc.replace("Z", "+00:00"),
            ) - timedelta(minutes=10)):
        raise NarPreoffDailyHold("NAR_FORWARD_FREEZE_BEFORE_FIRST_OFF_REQUIRED")
    with ZipFile(BytesIO(blob)) as package:
        ymd = race_day.strftime("%Y%m%d")
        race_rows = _rows(package.read(f"{ymd}_racelist.csv"), {
            "競馬場", "競走年月日", "レース番号", "発走時刻", "頭数",
        })
        horse_rows = _rows(package.read(f"{ymd}_horselist.csv"), {
            "競馬場", "競走年月日", "レース番号", "馬番", "馬名", "全成績",
        })
    schedule = {}
    for row in race_rows:
        track = row["競馬場"].strip()
        if track.startswith("帯広"):
            continue
        num = int(row["レース番号"].strip())
        clock = row["発走時刻"].strip().replace(":", "")
        off = datetime.combine(
            race_day, time(int(clock[:2]), int(clock[2:])), _JST,
        ).astimezone(timezone.utc)
        rid = f"NAR:{ymd}:{track}:{num:02d}"
        if rid in schedule:
            raise NarPreoffDailyHold("NAR_FORWARD_DUPLICATE_CALENDAR_RACE")
        schedule[rid] = off
    if len(schedule) != audit.flat_races:
        raise NarPreoffDailyHold("NAR_FORWARD_CALENDAR_COVERAGE_INVALID")
    all_scores: dict[str, dict[str, tuple[float, float]]] = {
        rid: {} for rid in schedule
    }
    for row in horse_rows:
        track = row["競馬場"].strip()
        if track.startswith("帯広"):
            continue
        rid = f"NAR:{ymd}:{track}:{int(row['レース番号']):02d}"
        number = row["馬番"].strip()
        if rid not in all_scores or number in all_scores[rid]:
            raise NarPreoffDailyHold("NAR_FORWARD_HORSE_RACE_DUPLICATE")
        starts, wins, podiums = _record(row)
        # Fixed Beta smoothing; never fit or tune to live dividends.
        win = (wins + 1.0) / (starts + 10.0)
        top3 = (podiums + 1.0) / (starts + 10.0)
        all_scores[rid][number] = (win, top3)
    forecasts = []
    private_entries = []
    for rid in sorted(schedule):
        scores = all_scores[rid]
        if not 4 <= len(scores) <= 18:
            raise NarPreoffDailyHold("NAR_FORWARD_INCOMPLETE_ROSTER")
        w = {horse: value[0] for horse, value in sorted(scores.items())}
        p = {horse: value[1] for horse, value in sorted(scores.items())}
        item = NarProspectiveForecast(
            race_id=rid, race_day=race_day.isoformat(),
            scheduled_off_utc=schedule[rid],
            generated_at_utc=generated, roster_observed_at_utc=observed_at_utc,
            model_source_sha256=_POLICY_SHA,
            model_fit_through_day="2022-12-31",
            winner_scores=w, outsider_scores=p,
            market_odds_in_selection=False,
        )
        forecasts.append(item)
        top3 = sorted(w, key=lambda h: (-w[h], h))[:3]
        outsider = min(set(p).difference(top3), key=lambda h: (-p[h], h))
        private_entries.append({
            "race_id": rid, "race_day": item.race_day,
            "scheduled_off_utc": schedule[rid].isoformat(),
            "winner_scores": w, "outsider_scores": p,
            "top3": top3, "outsider": outsider,
            "model_source_sha256": _POLICY_SHA,
            "model_fit_through_day": item.model_fit_through_day,
            "generated_at_utc": generated.isoformat(),
            "roster_observed_at_utc": observed_at_utc.isoformat(),
        })
    commitment = seal_nar_prospective_batch(
        {rid: race_day.isoformat() for rid in schedule}, forecasts,
        private_salt=private_salt,
    )
    if (commitment.locked_forecasts != audit.flat_races
            or commitment.missing_forecasts != 0
            or commitment.freeze_time_independently_verified
            or commitment.actual_wagers_proven):
        raise NarPreoffDailyHold("NAR_FORWARD_COMMITMENT_INCOMPLETE")
    snapshot = {
        "schema": "NAR.PC2.OfficialDailyForwardBaseline.v1",
        "status": "FROZEN_PRIVATE_UNATTESTED_NO_ECONOMIC_EV",
        "day": race_day.isoformat(),
        "host_generated_utc": generated.isoformat(),
        "host_observed_utc": observed_at_utc.isoformat(),
        "earliest_off_utc": audit.earliest_off_utc,
        "source_races": audit.flat_races,
        "source_horses": audit.registered_horses,
        "policy_name": _POLICY_NAME,
        "policy_sha256": _POLICY_SHA,
        "model_train_through_day_label": "2022-12-31",
        "private_salt_hex": private_salt.hex(),
        "commitment_digest": commitment.sha256_digest,
        "complete_private_forecasts": private_entries,
        "odds_observed": False,
        "independent_time_attestation": False,
        "positive_ev_proven": False,
        "no_real_tickets": _NO_BETS,
    }
    return snapshot, commitment.sha256_digest


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-capture-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        directory = args.private_capture_dir
        today = datetime.now(timezone.utc).astimezone(_JST).date()
        if not directory.is_dir() or directory.is_symlink():
            raise NarPreoffDailyHold("NAR_FORWARD_PRIVATE_DIR_INVALID")
        zips = list(directory.glob(f"{today:%Y%m%d}_????????T??????Z_race.zip"))
        if len(zips) != 1:
            raise NarPreoffDailyHold("NAR_FORWARD_SINGLE_CAPTURE_REQUIRED")
        path = zips[0]
        provenance = path.with_name(path.name.replace("_race.zip", "_private_provenance.json"))
        if not provenance.is_file() or provenance.is_symlink() or path.is_symlink():
            raise NarPreoffDailyHold("NAR_FORWARD_PRIVATE_PROVENANCE_REQUIRED")
        record = json.loads(provenance.read_text(encoding="utf-8"))
        blob = path.read_bytes()
        salt = bytes.fromhex(record["salt_hex_PRIVATE"])
        verified = sha256(b"NAR_OFFICIAL_DAILY_RACE_V1\x00" + salt + blob).hexdigest()
        if (record.get("schema") != "NAR.OfficialDailyPreoffCapture.v1"
                or record["salted_zip_sha256_PRIVATE"] != verified):
            raise NarPreoffDailyHold("NAR_FORWARD_SOURCE_SALTED_HASH_MISMATCH")
        observed = datetime.fromisoformat(record["host_captured_utc"].replace("Z", "+00:00"))
        output = directory / f"{today:%Y%m%d}_baseline_forecast_PRIVATE.json"
        if output.exists():
            # A finished freeze is immutable. Never replace it with a new
            # salt, a later timestamp, or hindsight-corrupted scores.
            if not output.is_file() or output.is_symlink():
                raise NarPreoffDailyHold("NAR_FORWARD_EXISTING_SNAPSHOT_NOT_REGULAR")
            original = json.loads(output.read_text(encoding="utf-8"))
            if (not isinstance(original, dict)
                    or original.get("schema") != "NAR.PC2.OfficialDailyForwardBaseline.v1"
                    or original.get("status") != "FROZEN_PRIVATE_UNATTESTED_NO_ECONOMIC_EV"
                    or original.get("day") != today.isoformat()
                    or original.get("no_real_tickets") is not True
                    or original.get("odds_observed") is not False
                    or original.get("positive_ev_proven") is not False):
                raise NarPreoffDailyHold("NAR_FORWARD_EXISTING_SNAPSHOT_UNTRUSTED")
            saved_salt = bytes.fromhex(original["private_salt_hex"])
            saved_generated = datetime.fromisoformat(original["host_generated_utc"])
            if len(saved_salt) != 32:
                raise NarPreoffDailyHold("NAR_FORWARD_EXISTING_SALT_INVALID")
            reconstructed, digest = prepare_private_daily_baseline(
                blob, observed_at_utc=observed,
                generated_at_utc=saved_generated, race_day=today,
                private_salt=saved_salt,
            )
            if (reconstructed != original
                    or not secrets.compare_digest(
                        digest, original["commitment_digest"]
                    )):
                raise NarPreoffDailyHold("NAR_FORWARD_EXISTING_SNAPSHOT_ALTERED")
            snapshot = original
        else:
            generated = datetime.now(timezone.utc)
            salt_forecast = secrets.token_bytes(32)
            snapshot, digest = prepare_private_daily_baseline(
                blob, observed_at_utc=observed,
                generated_at_utc=generated, race_day=today,
                private_salt=salt_forecast,
            )
            fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                json.dump(snapshot, out, ensure_ascii=False, sort_keys=True)
                out.flush()
                os.fsync(out.fileno())
    except Exception:
        print(json.dumps({
            "schema": "NAR.PC2.OfficialDailyForwardBaseline.v1",
            "result": "HOLD", "source_uploaded": False, "positive_ev_proven": False,
        }, sort_keys=True))
        return 2
    # Blinded salted FORECAST digest only, not raw data or private salt.
    print(json.dumps({
        "schema": "NAR.PC2.OfficialDailyForwardBaseline.v1",
        "result": "PRIVATE_FORECAST_FROZEN_NO_EV_PROOF",
        "race_day_jst": snapshot["day"],
        "flat_races": snapshot["source_races"],
        "registered_horses": snapshot["source_horses"],
        "earliest_off_utc": snapshot["earliest_off_utc"],
        "commitment_digest_salted": digest,
        "independently_timestamped_before_off": False,
        "odds_observed": False, "source_uploaded": False,
        "real_wagers": 0, "positive_ev_proven": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
