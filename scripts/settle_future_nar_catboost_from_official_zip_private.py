"""PC2-only OFFLINE final official NAR ZIP -> immutable model paper accuracy/ROI.

This is a conservative ALL-RACES, ordinary numeric-finishes-only settlement.
ANY missing official result, scratch, DNF, dead heat, payout inconsistency, or
changed horse name keeps the whole day's ROI in HOLD: no favorable subset.
Requires a previously frozen tamper-checked private model forecast and its
original official preoff ZIP. Does not download, write or upload sources.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import secrets
from zipfile import BadZipFile, ZipFile

from capture_nar_official_daily_preoff_once import (
    _JST, _rows, validate_official_daily_race_zip,
)
from score_prospective_dual_model_private import load_verified_private_forecast
from horse_racing_predictions.prospective_dual_model_shadow import (
    score_frozen_shadow,
)

_SCHEMA = "NAR.PC2.PosteventRealModelPaperAccuracyROI.v1"
_MODE = "NAR_OFFICIAL_CAREER_3_OF_5_RESEARCH_ABLATION"
_MAX_SOURCE = 32 * 1024 * 1024
_WAIT = timedelta(minutes=20)
_FRESH = timedelta(minutes=40)


class PrivateNarSettlementHold(ValueError):
    """Reasons are fixed source-only status codes; do not print raw values."""


def _rid(row: dict[str, str], day: date) -> str:
    if (row["競走年月日"].strip() != day.strftime("%Y%m%d")
            or not row["レース番号"].strip().isascii()
            or not row["レース番号"].strip().isdecimal()
            or not 1 <= int(row["レース番号"].strip()) <= 20
            or not row["競馬場"].strip()):
        raise PrivateNarSettlementHold("NAR_MODEL_FINAL_RACE_ID_INVALID")
    return "NAR:%s:%s:%02d" % (
        day.strftime("%Y%m%d"), row["競馬場"].strip(),
        int(row["レース番号"].strip()),
    )


def _daily_tables(blob: bytes, day: date, *, final: bool) -> dict:
    if (type(blob) is not bytes or not 32 < len(blob) <= _MAX_SOURCE
            or not blob.startswith(b"PK\x03\x04")):
        raise PrivateNarSettlementHold("NAR_MODEL_OFFICIAL_FINAL_ZIP_INVALID")
    prefix = day.strftime("%Y%m%d")
    names = {
        f"{prefix}_racelist.csv",
        f"{prefix}_horselist.csv",
        f"{prefix}_payback.csv",
    }
    try:
        with ZipFile(BytesIO(blob)) as archive:
            infos = archive.infolist()
            if (len(infos) != 3 or set(x.filename for x in infos) != names
                    or sum(x.file_size for x in infos) > 4 * _MAX_SOURCE
                    or any(x.is_dir() or x.flag_bits & 1 or
                           x.file_size > _MAX_SOURCE for x in infos)
                    or archive.testzip() is not None):
                raise PrivateNarSettlementHold("NAR_MODEL_OFFICIAL_FINAL_MEMBERS_INVALID")
            result = {
                "races": _rows(archive.read(f"{prefix}_racelist.csv"),
                               {"競馬場", "競走年月日", "レース番号", "頭数"}),
                "horses": _rows(archive.read(f"{prefix}_horselist.csv"),
                                {"競馬場", "競走年月日", "レース番号",
                                 "馬番", "馬名", "着順"}),
            }
            if final:
                result["pays"] = _rows(
                    archive.read(f"{prefix}_payback.csv"),
                    {"競馬場", "競走年月日", "レース番号",
                     "単勝組番", "単勝払戻金（円）"},
                )
            return result
    except (BadZipFile, KeyError, OSError, RuntimeError) as exc:
        raise PrivateNarSettlementHold("NAR_MODEL_OFFICIAL_FINAL_UNREADABLE") from exc


def _model_final_outcomes(
    preoff_zip: bytes, final_zip: bytes, *,
    day: date, races: tuple,
) -> dict[str, dict]:
    """Reject any incomplete or unusual race rather than cherry-pick ROI."""
    before = _daily_tables(preoff_zip, day, final=False)
    after = _daily_tables(final_zip, day, final=True)
    expected = {r.race_id: r for r in races}
    if len(expected) != len(races):
        raise PrivateNarSettlementHold("NAR_MODEL_DUPLICATE_FROZEN_RACE")
    original_names = {}
    for row in before["horses"]:
        if row["競馬場"].strip().startswith("帯広"):
            continue
        rid = _rid(row, day)
        number = row["馬番"].strip()
        key = (rid, number)
        if (rid not in expected or number not in expected[rid].roster
                or key in original_names or not row["馬名"].strip()):
            raise PrivateNarSettlementHold("NAR_MODEL_ORIGINAL_ROSTER_CHANGED")
        original_names[key] = row["馬名"].strip()
    if (len(original_names) != sum(len(r.roster) for r in races)
            or set(k[0] for k in original_names) != set(expected)):
        raise PrivateNarSettlementHold("NAR_MODEL_ORIGINAL_ROSTER_MISSING")
    final_races = set()
    for row in after["races"]:
        if row["競馬場"].strip().startswith("帯広"):
            continue
        rid = _rid(row, day)
        if rid in final_races or rid not in expected:
            raise PrivateNarSettlementHold("NAR_MODEL_FINAL_CALENDAR_MISMATCH")
        final_races.add(rid)
    if final_races != set(expected):
        raise PrivateNarSettlementHold("NAR_MODEL_FINAL_CALENDAR_MISSING")
    finishes = {}
    for row in after["horses"]:
        if row["競馬場"].strip().startswith("帯広"):
            continue
        rid = _rid(row, day)
        number = row["馬番"].strip()
        key = (rid, number)
        if (key not in original_names or
                original_names[key] != row["馬名"].strip() or
                number in finishes.setdefault(rid, {})):
            raise PrivateNarSettlementHold("NAR_MODEL_FINAL_HORSE_IDENTITY_CHANGED")
        rank = row["着順"].strip()
        if (not rank.isascii() or not rank.isdecimal()
                or not 1 <= int(rank) <= len(expected[rid].roster)):
            raise PrivateNarSettlementHold("NAR_MODEL_NON_NUMERIC_OR_AMBIGUOUS_FINISH")
        finishes[rid][number] = int(rank)
    for rid, race in expected.items():
        if (set(finishes.get(rid, {})) != set(race.roster)
                or sorted(finishes[rid].values()) !=
                list(range(1, len(race.roster) + 1))):
            raise PrivateNarSettlementHold("NAR_MODEL_UNRESOLVED_FINISH_DENOMINATOR")
    win_pays = {}
    saw_payback = set()
    for row in after["pays"]:
        if row["競馬場"].strip().startswith("帯広"):
            continue
        rid = _rid(row, day)
        if rid not in expected:
            raise PrivateNarSettlementHold("NAR_MODEL_UNKNOWN_PAYOUT_RACE")
        saw_payback.add(rid)
        number = row["単勝組番"].strip()
        amount = row["単勝払戻金（円）"].strip()
        if number == "" and amount == "":
            continue
        if (not number.isascii() or not number.isdecimal()
                or not amount.isascii() or not amount.isdecimal()
                or number not in finishes[rid]
                or not 100 <= int(amount) <= 500_000):
            raise PrivateNarSettlementHold("NAR_MODEL_OFFICIAL_WIN_PAYOUT_INVALID")
        group = win_pays.setdefault(rid, {})
        if number in group and group[number] != int(amount):
            raise PrivateNarSettlementHold("NAR_MODEL_CONFLICTING_WIN_PAYOUTS")
        group[number] = int(amount)
    if saw_payback != set(expected):
        raise PrivateNarSettlementHold("NAR_MODEL_PAYOUT_RACE_MISSING")
    data = {}
    for rid, race in expected.items():
        winners = {h for h, rank in finishes[rid].items() if rank == 1}
        payouts = win_pays.get(rid, {})
        if len(winners) != 1 or set(payouts) != winners:
            raise PrivateNarSettlementHold("NAR_MODEL_OFFICIAL_WINNER_PAYOUT_MISMATCH")
        selected = race.top3[0]
        data[rid] = {
            "finish_by_horse": finishes[rid],
            "selected_top1_win_return_per_100_yen": payouts.get(selected, 0),
        }
    return data


def score_private_postevent_zip(
    root: Path, final_zip_path: Path, *,
    now_utc: datetime,
) -> dict:
    if (os.environ.get("COMPUTERNAME") != "DESKTOP-MVV1FD4"
            or not isinstance(root, Path) or not root.is_absolute()
            or not root.is_dir() or root.is_symlink()
            or not isinstance(final_zip_path, Path)
            or not final_zip_path.is_absolute()
            or final_zip_path.is_symlink() or not final_zip_path.is_file()
            or not 32 < final_zip_path.stat().st_size <= _MAX_SOURCE
            or not isinstance(now_utc, datetime)
            or now_utc.utcoffset() is None):
        raise PrivateNarSettlementHold("NAR_MODEL_PRIVATE_PC2_CONTEXT_INVALID")
    folder = root / "nar-prospective-captures"
    inbox = folder / "postevent-inbox"
    if (not folder.is_dir() or folder.is_symlink()
            or not inbox.is_dir() or inbox.is_symlink()
            or final_zip_path.parent.resolve() != inbox.resolve()):
        raise PrivateNarSettlementHold("NAR_MODEL_PRIVATE_POSTEVENT_INBOX_INVALID")
    filename = final_zip_path.name
    m = re.fullmatch(r"([0-9]{8})_([1-9][0-9]{8,12})_race\.zip", filename)
    if not m:
        raise PrivateNarSettlementHold("NAR_MODEL_POSTEVENT_OFFICIAL_SOURCE_NAME_INVALID")
    day = datetime.strptime(m[1], "%Y%m%d").date()
    capture_time = now_utc.astimezone(timezone.utc)
    generated = datetime.fromtimestamp(int(m[2]), timezone.utc)
    if (generated > capture_time + timedelta(seconds=90) or
            capture_time - generated > _FRESH):
        raise PrivateNarSettlementHold("NAR_MODEL_POSTEVENT_SOURCE_TIMESTAMP_UNTRUSTED")
    frozen_path = folder / f"{day:%Y%m%d}_NAR_partial3of5_dual_catboost_PRIVATE.json"
    frozen, private_doc = load_verified_private_forecast(frozen_path)
    if (frozen.jurisdiction != "NAR" or frozen.race_day_jst != day.isoformat()
            or private_doc.get("source_feature_mode_PRIVATE") != _MODE
            or private_doc.get("model_missing_features_do_not_equal_full_feature_model") is not True):
        raise PrivateNarSettlementHold("NAR_MODEL_PRIVATE_FROZEN_MODE_INVALID")
    last_off = max(datetime.fromisoformat(r.off_utc).astimezone(timezone.utc)
                   for r in frozen.races)
    if generated < last_off + _WAIT or capture_time < last_off + _WAIT:
        raise PrivateNarSettlementHold("NAR_MODEL_OFFICIAL_SOURCE_BEFORE_FINAL")
    originals = list(folder.glob(f"{day:%Y%m%d}_????????T??????Z_race.zip"))
    if len(originals) != 1 or originals[0].is_symlink():
        raise PrivateNarSettlementHold("NAR_MODEL_ORIGINAL_PREOFF_ZIP_MISSING")
    original = originals[0]
    meta = original.with_name(
        original.name.replace("_race.zip", "_private_provenance.json")
    )
    if not meta.is_file() or meta.is_symlink():
        raise PrivateNarSettlementHold("NAR_MODEL_ORIGINAL_PREOFF_SIDECAR_MISSING")
    provenance = json.loads(meta.read_text(encoding="utf-8"))
    preoff_blob = original.read_bytes()
    salt = bytes.fromhex(provenance["salt_hex_PRIVATE"])
    if (len(salt) != 32 or
            provenance.get("schema") != "NAR.OfficialDailyPreoffCapture.v1"
            or not secrets.compare_digest(
                provenance.get("salted_zip_sha256_PRIVATE", ""),
                sha256(b"NAR_OFFICIAL_DAILY_RACE_V1\x00" +
                       salt + preoff_blob).hexdigest())):
        raise PrivateNarSettlementHold("NAR_MODEL_PREOFF_ORIGINAL_HASH_MISMATCH")
    original_time = datetime.fromisoformat(
        provenance["host_captured_utc"].replace("Z", "+00:00")
    )
    audit = validate_official_daily_race_zip(
        preoff_blob, race_day=day, host_captured_utc=original_time,
    )
    if (frozen.source_asof_utc != original_time.astimezone(timezone.utc).isoformat()
            or len(frozen.races) != audit.flat_races
            or sum(len(r.roster) for r in frozen.races) != audit.registered_horses):
        raise PrivateNarSettlementHold("NAR_MODEL_FROZEN_SOURCE_CHRONOLOGY_CONFLICT")
    outcomes = _model_final_outcomes(
        preoff_blob, final_zip_path.read_bytes(),
        day=day, races=frozen.races,
    )
    result = score_frozen_shadow(frozen, final_by_race=outcomes)
    if not result.status.startswith("COMPLETE_"):
        raise PrivateNarSettlementHold("NAR_MODEL_ALL_RACES_ECONOMIC_RESULT_HOLD")
    return {
        "schema": _SCHEMA,
        "status": "COMPLETE_DESCRIPTIVE_WIN_HITS_AND_PAPER_ROI_NO_EV_PROOF",
        "jurisdiction": "NAR", "race_day_jst": day.isoformat(),
        "frozen_race_denominator": result.frozen_races,
        "ordinary_fully_settled_races": result.outcome_complete_races,
        "top1_win_hits": result.top1_win_hits,
        "top1_win_hit_rate": result.top1_win_hit_rate,
        "top3_numeric_podium_hits": result.top3_numeric_podium_hits,
        "top3_numeric_podium_precision": result.top3_numeric_podium_precision,
        "outsider_top3_hits": result.outsider_numeric_top3_hits,
        "outsider_top3_hit_rate": result.outsider_numeric_top3_hit_rate,
        "hypothetical_100_yen_win_stake": result.stake_yen,
        "hypothetical_official_return_yen": result.official_paper_returns_yen,
        "hypothetical_net_paper_roi": result.paper_roi_after_stake,
        "three_of_five_feature_ablation": True,
        "independent_prediction_receipt_checked": False,
        "independent_source_authentication": False,
        "real_wagers": 0, "positive_ev_proven": False,
        "private_source_or_predictions_uploaded": False,
        "private_files_modified": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-root", type=Path, required=True)
    p.add_argument("--final-official-daily-zip", type=Path, required=True)
    args = p.parse_args()
    try:
        result = score_private_postevent_zip(
            args.private_root, args.final_official_daily_zip,
            now_utc=datetime.now(timezone.utc),
        )
    except Exception:
        print(json.dumps({
            "schema": _SCHEMA,
            "status": "HOLD_INCOMPLETE_OR_UNTRUSTED_REAL_FINAL_SETTLEMENT",
            "hypothetical_net_paper_roi": None,
            "private_source_or_predictions_uploaded": False,
            "real_wagers": 0,
            "positive_ev_proven": False,
        },sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
