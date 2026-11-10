"""Reconcile already-frozen REAL 2026-11-10 forecasts with official final results.

Strictly POST-event, private PC2 D-drive only. It models 100-yen hypothetical
WIN+PLACE per complete offered flat race; no verified prices, wagers,
profitability expectation, protected historical OOS or additional fees.

Never regenerate a forecast, select tickets by realized dividend, upload
licensed source rows or silently drop races/scratches/refunds.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import secrets
import urllib.request
from zipfile import ZipFile, BadZipFile

from capture_nar_official_daily_preoff_once import (
    _JST, _OFFICIAL_RACE, _rows, NarPreoffDailyHold,
)
from capture_nar_official_daily_odds_preoff_once import (
    _load_original_frozen_forecast,
)

_TARGET = date(2026, 11, 10)
_MAX_BYTES = 32 * 1024 * 1024
_WAIT_AFTER_LAST_OFF = timedelta(minutes=20)
_MAX_SOURCE_AGE = timedelta(minutes=40)
_FILENAME = re.compile(r'20261110_([1-9][0-9]{8,12})_race\.zip\Z')
_CREDENTIALS = b"NAR_REAL_DAILY_POSTEVENT_SETTLEMENT_V1\x00"
_FINAL_FINISH = re.compile(r'[0-9]{1,2}\Z')
_INVALID_MARKERS = {
    "取消", "出走取消", "除外", "競走除外", "中止", "競走中止",
    "失格", "取止", "不成", "競走取止", "競走不成立",
}


@dataclass(frozen=True)
class NarRealForwardSettlementAudit:
    schema: str
    forecast_day: str
    frozen_flat_races: int
    frozen_horses: int
    official_result_races: int
    official_result_horses: int
    official_payback_races: int
    fully_interpretable_races: int
    unresolved_races: int
    hypothetical_full_day_win_stake_yen: int | None
    hypothetical_full_day_place_stake_yen: int | None
    hypothetical_full_day_gross_return_yen: int | None
    hypothetical_full_day_net_yen: int | None
    hypothetical_full_day_roi: float | None
    unresolved_reason_counts: tuple[tuple[str, int], ...] = ()
    forecast_unchanged: bool = True
    selected_using_results: bool = False
    contemporaneous_quoted_prices_verified: bool = False
    real_tickets_purchased: bool = False
    independent_real_wager_proof: bool = False
    after_cost_positive_ev_proven: bool = False
    protected_historical_oos_opened: bool = False
    source_uploaded: bool = False


def _rid(row: dict[str, str], *, day: date) -> str:
    ymd = row["競走年月日"].strip()
    track = row["競馬場"].strip()
    n = row["レース番号"].strip()
    if (ymd != day.strftime("%Y%m%d") or not track
            or not n.isascii() or not n.isdecimal()
            or not 1 <= int(n) <= 20):
        raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_BAD_RACE_KEY")
    return f"NAR:{ymd}:{track}:{int(n):02d}"


def _money(row: dict[str, str], horse_label: str,
           cash_label: str) -> tuple[str,int] | None:
    num = row[horse_label].strip()
    amount = row[cash_label].strip()
    if not num and not amount:
        return None
    if (not num.isascii() or not num.isdecimal()
            or not 1 <= int(num) <= 18 or not amount.isascii()
            or not amount.isdecimal() or not 100 <= int(amount) <= 500_000):
        raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_UNSAFE_PAYOUT")
    return str(int(num)), int(amount)


def _payout_table(
    rows: list[dict[str, str]], *,
    day: date, frozen_ids: set[str],
) -> dict[str, tuple[dict[str,int],dict[str,int]]]:
    by_race: dict[str, tuple[dict[str,int],dict[str,int]]] = {}
    for row in rows:
        rid = _rid(row, day=day)
        if rid not in frozen_ids:
            # Banei was outside the registered flat scope before outcomes.
            if row["競馬場"].strip().startswith("帯広"):
                continue
            raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_NEW_FLAT_RACE")
        if rid not in by_race:
            by_race[rid] = ({}, {})
        wins, places = by_race[rid]
        for first, second, target in (
            ("単勝組番", "単勝払戻金（円）", wins),
            ("複勝組番1", "複勝払戻金1（円）", places),
            ("複勝組番2", "複勝払戻金2（円）", places),
            ("複勝組番3", "複勝払戻金3（円）", places),
        ):
            p = _money(row, first, second)
            if p is not None:
                horse, amount = p
                if horse in target and target[horse] != amount:
                    raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_PAYOUT_CONFLICT")
                target[horse] = amount
    return by_race


def verify_real_forward_final_results(
    frozen: dict, prior_blob: bytes, final_blob: bytes, *,
    result_source_name: str, observed_utc: datetime,
) -> NarRealForwardSettlementAudit:
    """Only a WHOLE 59-race verified 200-yen paper policy receives ROI.

    Any non-terminal horse, ambiguous refund, absent payout, changed roster,
    later addition, stale source or mismatched time => entire sample HOLD.
    """
    if (not isinstance(frozen, dict)
            or frozen.get("schema") != "NAR.PC2.OfficialDailyForwardBaseline.v1"
            or frozen.get("day") != _TARGET.isoformat()
            or frozen.get("source_races") != 59
            or frozen.get("source_horses") != 641
            or frozen.get("no_real_tickets") is not True
            or frozen.get("odds_observed") is not False
            or not isinstance(observed_utc, datetime)
            or observed_utc.tzinfo is None
            or observed_utc.utcoffset() is None
            or type(final_blob) is not bytes
            or len(final_blob) < 32 or len(final_blob) > _MAX_BYTES
            or not final_blob.startswith(b"PK\x03\x04")):
        raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_SOURCE_OR_FORECAST_INVALID")
    obs = observed_utc.astimezone(timezone.utc)
    if obs.astimezone(_JST).date() != _TARGET:
        raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_ONLY_ORIGINAL_FORWARD_DAY")
    m = _FILENAME.fullmatch(result_source_name)
    if not m:
        raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_OFFICIAL_FILENAME_INVALID")
    generated = datetime.fromtimestamp(int(m[1]), timezone.utc)
    if generated > obs + timedelta(seconds=90) or obs - generated > _MAX_SOURCE_AGE:
        raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_STALE_SOURCE_TIME")
    expected_list = frozen["complete_private_forecasts"]
    expected = {row["race_id"]: row for row in expected_list}
    if len(expected) != len(expected_list) or len(expected) != 59:
        raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_FROZEN_MANIFEST_INVALID")
    last_off = max(
        datetime.fromisoformat(r["scheduled_off_utc"])
        for r in expected_list
    )
    if generated < last_off + _WAIT_AFTER_LAST_OFF:
        raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_LAST_OFF_NOT_FINISHED")
    try:
        with ZipFile(BytesIO(prior_blob)) as source:
            old = _rows(source.read("20261110_horselist.csv"), {
                "競馬場", "競走年月日", "レース番号", "馬番", "馬名",
            })
        with ZipFile(BytesIO(final_blob)) as archive:
            names = set(archive.namelist())
            if names != {
                "20261110_racelist.csv", "20261110_horselist.csv",
                "20261110_payback.csv",
            } or sum(z.file_size for z in archive.infolist()) > _MAX_BYTES * 4:
                raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_OFFICIAL_ZIP_LAYOUT")
            race_rows = _rows(archive.read("20261110_racelist.csv"), {
                "競馬場", "競走年月日", "レース番号", "頭数",
            })
            horse_rows = _rows(archive.read("20261110_horselist.csv"), {
                "競馬場", "競走年月日", "レース番号", "馬番",
                "馬名", "着順", "着差",
            })
            pay_rows = _rows(archive.read("20261110_payback.csv"), {
                "競馬場", "競走年月日", "レース番号",
                "単勝組番", "単勝払戻金（円）",
                "複勝組番1", "複勝払戻金1（円）",
                "複勝組番2", "複勝払戻金2（円）",
                "複勝組番3", "複勝払戻金3（円）",
            })
    except (BadZipFile, KeyError, RuntimeError) as exc:
        raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_ZIP_UNREADABLE") from exc
    old_names: dict[str,dict[str,str]] = defaultdict(dict)
    for row in old:
        if row["競馬場"].startswith("帯広"):
            continue
        rid = _rid(row, day=_TARGET)
        h = row["馬番"].strip()
        if rid not in expected or h in old_names[rid] or h not in expected[rid]["winner_scores"]:
            raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_FROZEN_ORIGINAL_MISMATCH")
        old_names[rid][h] = row["馬名"].strip()
    if len(old_names) != len(expected):
        raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_OLD_RACE_COVERAGE")
    completed: dict[str,dict[str,int]] = defaultdict(dict)
    uncertain: set[str] = set()
    unresolved_reasons: dict[str, str] = {}
    full_races = set()
    for row in race_rows:
        if row["競馬場"].startswith("帯広"):
            continue
        rid = _rid(row, day=_TARGET)
        if rid not in expected or rid in full_races:
            raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_RACELIST_MISMATCH")
        full_races.add(rid)
    for row in horse_rows:
        if row["競馬場"].startswith("帯広"):
            continue
        rid = _rid(row, day=_TARGET)
        h = row["馬番"].strip()
        if (rid not in expected or not h.isascii() or not h.isdecimal()
                or str(int(h)) not in old_names[rid]
                or row["馬名"].strip() != old_names[rid][str(int(h))]):
            raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_HORSE_ID_CHANGED")
        h = str(int(h))
        if h in completed[rid]:
            raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_DUPLICATE_HORSE")
        value = row["着順"].strip()
        if not _FINAL_FINISH.fullmatch(value):
            uncertain.add(rid)
            unresolved_reasons.setdefault(rid, "NONNUMERIC_OR_EXCEPTION_FINISH")
            completed[rid][h] = 0
        elif not 1 <= int(value) <= 18:
            uncertain.add(rid)
            unresolved_reasons.setdefault(rid, "FINISH_RANK_OUT_OF_RANGE")
            completed[rid][h] = 0
        else:
            completed[rid][h] = int(value)
    pays = _payout_table(pay_rows, day=_TARGET, frozen_ids=set(expected))
    total_gross = 0
    full_ok = 0
    for rid in sorted(expected):
        horse_ranks = completed.get(rid, {})
        if rid not in full_races:
            uncertain.add(rid)
            unresolved_reasons.setdefault(rid, "RACE_RESULT_MISSING")
            continue
        if rid not in pays:
            uncertain.add(rid)
            unresolved_reasons.setdefault(rid, "OFFICIAL_PAYBACK_MISSING")
            continue
        if rid in uncertain:
            continue
        if (set(horse_ranks) != set(old_names[rid])
                or set(horse_ranks) != set(expected[rid]["winner_scores"])):
            uncertain.add(rid)
            unresolved_reasons.setdefault(rid, "FINAL_ROSTER_INCOMPLETE")
            continue
        if len(horse_ranks) <= 4:
            uncertain.add(rid)
            unresolved_reasons.setdefault(rid, "PLACE_NOT_UNCONDITIONALLY_OFFERED")
            continue
        win_pays, place_pays = pays[rid]
        n = len(horse_ranks)
        place_limit = 2 if n <= 7 else 3
        actual_winners = {h for h, pos in horse_ranks.items() if pos == 1}
        actual_places = {h for h, pos in horse_ranks.items() if pos <= place_limit}
        if (not actual_winners
                or set(win_pays) != actual_winners
                or sum(1 for v in horse_ranks.values() if v == 1) > 3):
            uncertain.add(rid)
            unresolved_reasons.setdefault(rid, "WIN_PAYOUT_OR_WINNER_MISMATCH")
            continue
        if set(place_pays) != actual_places:
            uncertain.add(rid)
            unresolved_reasons.setdefault(rid, "PLACE_PAYOUT_OR_FINISH_MISMATCH")
            continue
        if any(h not in horse_ranks for h in win_pays | place_pays):
            uncertain.add(rid)
            unresolved_reasons.setdefault(rid, "PAYOUT_HORSE_NOT_IN_ROSTER")
            continue
        win_horse = expected[rid]["top3"][0]
        place_horse = expected[rid]["outsider"]
        if (win_horse not in horse_ranks or place_horse not in horse_ranks
                or win_horse == place_horse):
            uncertain.add(rid)
            unresolved_reasons.setdefault(rid, "FROZEN_SELECTED_HORSE_MISSING")
            continue
        total_gross += win_pays.get(win_horse, 0) + place_pays.get(place_horse, 0)
        full_ok += 1
    if (full_ok + len(uncertain) != len(expected)
            or set(unresolved_reasons) != uncertain):
        raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_AUDIT_DENOMINATOR_INVALID")
    # No favorable subset P&L. A single unresolved event invalidates
    # the entire 59-race retrospective paper policy metric.
    eligible = full_ok == len(expected)
    stake = 100 * len(expected) if eligible else None
    gross = total_gross if eligible else None
    return NarRealForwardSettlementAudit(
        schema="NAR.PC2.RealProspectiveDaySettlement.v1",
        forecast_day=_TARGET.isoformat(),
        frozen_flat_races=len(expected), frozen_horses=frozen["source_horses"],
        official_result_races=len(full_races),
        official_result_horses=sum(map(len, completed.values())),
        official_payback_races=len(pays),
        fully_interpretable_races=full_ok,
        unresolved_races=len(uncertain),
        hypothetical_full_day_win_stake_yen=stake,
        hypothetical_full_day_place_stake_yen=stake,
        hypothetical_full_day_gross_return_yen=gross,
        hypothetical_full_day_net_yen=(gross-2*stake if eligible else None),
        hypothetical_full_day_roi=(gross/(2*stake)-1 if eligible else None),
        unresolved_reason_counts=tuple(sorted(
            (reason, sum(v == reason for v in unresolved_reasons.values()))
            for reason in set(unresolved_reasons.values())
        )),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        dest = args.private_output_dir
        if not dest.is_dir() or dest.is_symlink():
            raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_D_FOLDER_INVALID")
        frozen, old_blob = _load_original_frozen_forecast(dest, _TARGET)
        now = datetime.now(timezone.utc)
        if now.astimezone(_JST).date() != _TARGET:
            raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_DATE_CLOSED")
        final_off = max(
            datetime.fromisoformat(r["scheduled_off_utc"])
            for r in frozen["complete_private_forecasts"]
        )
        if now < final_off + _WAIT_AFTER_LAST_OFF:
            raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_TOO_EARLY")
        saved = list(dest.glob("20261110_*_official_postevent_race.zip"))
        if len(saved) > 1:
            raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_MULTIPLE_PRIVATE_RESULTS")
        replay = bool(saved)
        if replay:
            # Re-run NEW diagnostic code against the single OLD original
            # without network access, overwriting or hindsight refitting.
            oldpath = saved[0]
            oldmeta = oldpath.with_name(
                oldpath.name.replace(
                    "_official_postevent_race.zip",
                    "_official_postevent_audit_PRIVATE.json",
                )
            )
            if (not oldpath.is_file() or oldpath.is_symlink()
                    or not oldmeta.is_file() or oldmeta.is_symlink()):
                raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_REPLAY_FILE_INVALID")
            metadata = json.loads(oldmeta.read_text(encoding="utf-8"))
            if (metadata.get("schema") != "NAR.PC2.RealProspectiveDaySettlementPrivate.v1"
                    or metadata.get("frozen_commitment_digest")
                       != frozen["commitment_digest"]):
                raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_REPLAY_PROVENANCE_HOLD")
            original_name = metadata["official_source_name"]
            received = datetime.fromisoformat(metadata["captured_utc"])
            blob = oldpath.read_bytes()
            report = verify_real_forward_final_results(
                frozen, old_blob, blob, result_source_name=original_name,
                observed_utc=received,
            )
            previous = metadata["audit"]
            new = asdict(report)
            if (not isinstance(previous, dict) or
                    any(k not in new or new[k] != value
                        for k, value in previous.items())):
                raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_REPLAY_OLD_AUDIT_CHANGED")
        else:
            req = urllib.request.Request(
                _OFFICIAL_RACE,
                headers={"User-Agent": "HorseRacingPredictions/1.0 personal-research"},
            )
            with urllib.request.urlopen(req, timeout=45) as response:
                if response.geturl() != _OFFICIAL_RACE:
                    raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_REDIRECT_FORBIDDEN")
                disposition = response.headers.get("Content-Disposition", "")
                match = re.search(
                    r'filename="?((?:20261110)_([1-9][0-9]{8,12})_race\.zip)"?',
                    disposition,
                )
                if not match:
                    raise NarPreoffDailyHold("NAR_FORWARD_SETTLEMENT_OFFICIAL_NAME_MISSING")
                official_name = match[1]
                blob = response.read(_MAX_BYTES+1)
            observed = datetime.now(timezone.utc)
            report = verify_real_forward_final_results(
                frozen, old_blob, blob, result_source_name=official_name,
                observed_utc=observed,
            )
            # Local original only; no public artifact or source transfer.
            stamp = observed.strftime("%Y%m%dT%H%M%SZ")
            path = dest / f"20261110_{stamp}_official_postevent_race.zip"
            raw = json.dumps({
                "schema":"NAR.PC2.RealProspectiveDaySettlementPrivate.v1",
                "official_source_name": official_name,
                "captured_utc": observed.isoformat(),
                "frozen_commitment_digest": frozen["commitment_digest"],
                "audit": asdict(report),
                "raw_lawful_source_never_uploaded": True,
            }, sort_keys=True).encode("utf-8")
            for target, payload in (
                (path, blob),
                (dest/f"20261110_{stamp}_official_postevent_audit_PRIVATE.json", raw),
            ):
                fd = os.open(target, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
    except Exception:
        print(json.dumps({
            "schema":"NAR.PC2.RealProspectiveDaySettlement.v1",
            "status":"RESEARCH_HOLD_NO_EV",
            "original_forecast_unchanged":True,
            "positive_ev_proven":False,
            "protected_oos_opened":False,
            "source_uploaded":False,
        }, sort_keys=True))
        return 2
    print(json.dumps({
        "schema":report.schema,
        "status":("COMPLETE_FORWARD_PAPER_SETTLEMENT_ONLY_NOT_EV"
                  if report.unresolved_races == 0 else
                  "INCOMPLETE_FORWARD_SETTLEMENT_FULL_DAY_ROI_HELD"),
        "frozen_races":report.frozen_flat_races,
        "frozen_horses":report.frozen_horses,
        "official_result_races":report.official_result_races,
        "official_payback_races":report.official_payback_races,
        "interpretable_races":report.fully_interpretable_races,
        "unresolved_races":report.unresolved_races,
        "unresolved_reason_counts":dict(report.unresolved_reason_counts),
        "previous_official_final_zip_readonly_replayed": replay,
        "hypothetical_full_day_stake_yen":(
            2*report.hypothetical_full_day_win_stake_yen
            if report.hypothetical_full_day_win_stake_yen is not None else None
        ),
        "hypothetical_full_day_paid_yen":report.hypothetical_full_day_gross_return_yen,
        "hypothetical_full_day_net_yen":report.hypothetical_full_day_net_yen,
        "hypothetical_full_day_roi":report.hypothetical_full_day_roi,
        "preoff_market_prices_known":False,
        "actual_wager_count":0,
        "positive_ev_proven":False,
        "private_source_uploaded":False,
        "protected_historical_oos_opened":False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
