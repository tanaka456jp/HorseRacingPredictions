"""PC2 PRIVATE: prospective NAR CatBoost ablation with 3/5 observed features.

Read an ALREADY-captured official preoff DAILY race ZIP; never download data.
Observed: career starts, wins/starts, numeric top-three/starts from 全成績.
Unavailable: historic mean finish, days since last start -> genuine NaN.
This is a 3-of-5 FEATURE-ABLATION research forecast, NOT validated use of
the original full-feature model, wagering advice or prospective positive EV.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import secrets
from zipfile import ZipFile

import pandas as pd

from capture_nar_official_daily_preoff_once import (
    _JST, _rows, validate_official_daily_race_zip, NarPreoffDailyHold,
)
from freeze_nar_official_daily_baseline import _record
from horse_racing_predictions.nar_private_dual_model_loader import (
    load_nar_private_dual_candidate,
)
from horse_racing_predictions.prospective_dual_model_shadow import (
    freeze_fitted_dual_shadow,
)
from score_prospective_dual_model_private import load_verified_private_forecast
from import_nar_manual_daily_race_offline import (
    import_user_downloaded_preoff_race, _OFFICIAL_NAME,
)


_SNAPSHOT_SCHEMA = "HorseRacing.PC2.ProspectiveDualModelPrivate.v1"
_MODE = "NAR_OFFICIAL_CAREER_3_OF_5_RESEARCH_ABLATION"
_MISSING = ("past_mean_finish", "days_since_last_start")


def partial_preoff_features(blob: bytes, *, race_day: date,
                            captured_utc: datetime) -> tuple[pd.DataFrame, dict, dict]:
    """Extract only verifiable, currently available pre-off career totals."""
    audit = validate_official_daily_race_zip(
        blob, race_day=race_day, host_captured_utc=captured_utc,
    )
    with ZipFile(BytesIO(blob)) as archive:
        code = race_day.strftime("%Y%m%d")
        races = _rows(archive.read(f"{code}_racelist.csv"), {
            "競馬場", "競走年月日", "レース番号", "発走時刻", "頭数",
        })
        horses = _rows(archive.read(f"{code}_horselist.csv"), {
            "競馬場", "競走年月日", "レース番号", "馬番", "馬名", "全成績",
        })
    off = {}
    for race in races:
        place = race["競馬場"].strip()
        if place.startswith("帯広"):
            continue
        number = int(race["レース番号"].strip())
        hhmm = race["発走時刻"].strip().replace(":", "")
        kickoff = datetime.combine(
            race_day, time(int(hhmm[:2]), int(hhmm[2:])), _JST,
        ).astimezone(timezone.utc)
        rid = f"NAR:{code}:{place}:{number:02d}"
        if rid in off:
            raise NarPreoffDailyHold("NAR_PARTIAL_DUPLICATE_CALENDAR")
        off[rid] = kickoff
    if len(off) != audit.flat_races:
        raise NarPreoffDailyHold("NAR_PARTIAL_CALENDAR_MISMATCH")
    records = []
    seen = set()
    for row in horses:
        place = row["競馬場"].strip()
        if place.startswith("帯広"):
            continue
        rid = f"NAR:{code}:{place}:{int(row['レース番号'].strip()):02d}"
        horse = row["馬番"].strip()
        key = (rid, horse)
        if rid not in off or key in seen:
            raise NarPreoffDailyHold("NAR_PARTIAL_DUPLICATE_OR_UNKNOWN_RUNNER")
        seen.add(key)
        starts, wins, podiums = _record(row)
        records.append({
            "race_id": rid, "horse_id": horse,
            "past_starts": starts,
            "past_win_rate": wins / starts if starts else 0.0,
            "past_top3_rate": podiums / starts if starts else 0.0,
            "past_mean_finish": float("nan"),
            "days_since_last_start": float("nan"),
        })
    frame = pd.DataFrame.from_records(records)
    if (len(frame) != audit.registered_horses
            or not set(frame["race_id"]) == set(off)):
        raise NarPreoffDailyHold("NAR_PARTIAL_ROSTER_COVERAGE_MISMATCH")
    return frame, off, {
        "races": audit.flat_races,
        "runners": audit.registered_horses,
        "observed_feature_count": 3,
        "unavailable_feature_count": 2,
    }


def freeze_partial_from_official_source(
    blob: bytes, *, day: date, observed_utc: datetime,
    generated_utc: datetime, loaded,
):
    """Apply the ACTUAL previously fitted two CBMs without any new market data."""
    frame, schedule, counts = partial_preoff_features(
        blob, race_day=day, captured_utc=observed_utc,
    )
    digests = loaded.digest_by_role
    if (tuple(loaded.features) != (
            "past_starts", "past_win_rate", "past_top3_rate",
            "past_mean_finish", "days_since_last_start")
            or loaded.train_end != "2021-12-31"):
        raise NarPreoffDailyHold("NAR_PARTIAL_MODEL_FEATURE_SCHEMA_INVALID")
    combined = sha256(
        (digests["win.cbm"] + digests["outsider.cbm"]).encode("ascii")
    ).hexdigest()
    frozen = freeze_fitted_dual_shadow(
        jurisdiction="NAR", race_day_jst=day.isoformat(),
        entries=frame, off_by_race=schedule,
        winner=loaded.winner, outsider=loaded.outsider,
        model_trained_through=loaded.train_end,
        model_sha256_declared=combined,
        source_asof_utc=observed_utc,
        generated_utc=generated_utc,
    )
    return frozen, counts


def freeze_private_from_saved_daily(root: Path, *, generated_utc: datetime) -> dict:
    if (os.environ.get("COMPUTERNAME") != "DESKTOP-MVV1FD4"
            or not root.is_absolute() or root.is_symlink()
            or not root.is_dir() or generated_utc.utcoffset() is None):
        raise ValueError("NAR_PARTIAL_PRIVATE_PC2_CONTEXT_INVALID")
    day = generated_utc.astimezone(_JST).date()
    capture = root / "nar-prospective-captures"
    if not capture.is_dir() or capture.is_symlink():
        raise ValueError("NAR_PARTIAL_PRIVATE_CAPTURE_DIR_MISSING")
    originals = list(capture.glob(f"{day:%Y%m%d}_????????T??????Z_race.zip"))
    if len(originals) != 1:
        raise ValueError("NAR_PARTIAL_EXACTLY_ONE_PRIOR_SOURCE_REQUIRED")
    original = originals[0]
    sidecar = original.with_name(
        original.name.replace("_race.zip", "_private_provenance.json")
    )
    if (original.is_symlink() or not original.is_file()
            or not 32 <= original.stat().st_size <= 18_000_000
            or sidecar.is_symlink() or not sidecar.is_file()
            or not 50 <= sidecar.stat().st_size <= 100_000):
        raise ValueError("NAR_PARTIAL_PRIOR_CAPTURE_INVALID")
    blob = original.read_bytes()
    provenance = json.loads(sidecar.read_text(encoding="utf-8"))
    salt = bytes.fromhex(provenance["salt_hex_PRIVATE"])
    if (provenance.get("schema") != "NAR.OfficialDailyPreoffCapture.v1"
            or len(salt) != 32
            or provenance.get("salted_zip_sha256_PRIVATE") != sha256(
                b"NAR_OFFICIAL_DAILY_RACE_V1\x00" + salt + blob
            ).hexdigest()):
        raise ValueError("NAR_PARTIAL_SALTED_ORIGIN_MISMATCH")
    observed = datetime.fromisoformat(
        provenance["host_captured_utc"].replace("Z", "+00:00")
    )
    if observed.utcoffset() is None or observed > generated_utc:
        raise ValueError("NAR_PARTIAL_SOURCE_CHRONOLOGY_INVALID")
    model = load_nar_private_dual_candidate(
        root / "nar-forward-models" / "2017-2021-fit-2022-tune-v1"
    )
    target = capture / f"{day:%Y%m%d}_NAR_partial3of5_dual_catboost_PRIVATE.json"
    existing_verified = False
    if target.exists() or target.is_symlink():
        # An already frozen forecast must never be regenerated from the
        # current clock. Verify its immutable contents, the original
        # provenance ZIP, and the current native model binaries against the
        # ORIGINAL saved generation time. This can recover a failed hosted
        # receipt before off without changing picks or secret salt.
        previous, previous_doc = load_verified_private_forecast(target)
        if (previous.jurisdiction != "NAR"
                or previous.race_day_jst != day.isoformat()
                or previous_doc.get("source_feature_mode_PRIVATE") != _MODE
                or previous_doc.get("model_missing_features_do_not_equal_full_feature_model") is not True
                or previous_doc.get("raw_source_uploaded") is not False
                or previous_doc.get("hosted_preoff_receipt_verified") is not False):
            raise ValueError("NAR_PARTIAL_EXISTING_COMMITMENT_WRONG_CONTRACT")
        old_generated = datetime.fromisoformat(previous.generated_utc)
        frozen, counts = freeze_partial_from_official_source(
            blob, day=day, observed_utc=observed,
            generated_utc=old_generated, loaded=model,
        )
        if frozen != previous:
            raise ValueError("NAR_PARTIAL_EXISTING_MODEL_FORECAST_MISMATCH")
        result = previous_doc
        existing_verified = True
    else:
        frozen, counts = freeze_partial_from_official_source(
            blob, day=day, observed_utc=observed,
            generated_utc=generated_utc, loaded=model,
        )
        salt2 = secrets.token_bytes(32)
        result = {
            "schema": _SNAPSHOT_SCHEMA,
            "frozen_shadow_PRIVATE": asdict(frozen),
            "salt_hex_PRIVATE": salt2.hex(),
            "blinded_digest": sha256(
                b"HORSERACING_FORWARD_DUAL_V1\x00" + salt2 +
                frozen.commitment_sha256.encode("ascii")
            ).hexdigest(),
            "source_feature_mode_PRIVATE": _MODE,
            "unavailable_feature_names_PRIVATE": list(_MISSING),
            "model_missing_features_do_not_equal_full_feature_model": True,
            "source_and_roster_independently_attested": False,
            "hosted_preoff_receipt_verified": False,
            "actual_bets": 0,
            "after_cost_positive_ev_proven": False,
            "raw_source_uploaded": False,
        }
        content = json.dumps(result, ensure_ascii=False, sort_keys=True,
                             allow_nan=False).encode("utf-8")
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    return {
        "schema": "NAR.PC2.FittedModelPartialFeatureFrozen.v1",
        "status": (
            "PRIVATE_EXISTING_PREOFF_CATBOOST_COMMITMENT_VERIFIED"
            if existing_verified else
            "PRIVATE_ACTUAL_MODEL_PARTIAL_FEATURE_PREOFF_FORECAST_FROZEN"
        ),
        "existing_private_forecast_reused": existing_verified,
        "real_preoff_source_races": counts["races"],
        "real_preoff_source_runners": counts["runners"],
        "race_day_jst": day.isoformat(),
        "earliest_off_utc": min(
            datetime.fromisoformat(r.off_utc) for r in frozen.races
        ).astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_observed_at_utc": observed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "available_model_features": 3,
        "unavailable_model_features": 2,
        "independent_preoff_witness_verified": False,
        "real_outcome_hits_measured": False,
        "real_roi_measured": False,
        "positive_ev_proven": False,
        "raw_data_uploaded": False,
        "actual_bets": 0,
        "blinded_digest": result["blinded_digest"],
    }


def prepare_manual_source_if_needed(root: Path, *, now: datetime) -> bool:
    """Only stage one current-day original, never access a provider.
    
    Existing immutable sources take precedence; ambiguous inboxes HOLD.
    The importer uses its own actual observation clock, not file mtime.
    """
    if (os.environ.get("COMPUTERNAME") != "DESKTOP-MVV1FD4"
            or not root.is_absolute() or not root.is_dir() or root.is_symlink()
            or now.utcoffset() is None):
        raise ValueError("NAR_PARTIAL_PRIVATE_PC2_CONTEXT_INVALID")
    capture = root / "nar-prospective-captures"
    if not capture.is_dir() or capture.is_symlink():
        raise ValueError("NAR_PARTIAL_PRIVATE_CAPTURE_DIR_MISSING")
    day = now.astimezone(_JST).strftime("%Y%m%d")
    if list(capture.glob(f"{day}_????????T??????Z_race.zip")):
        return False
    inbox = capture / "manual-race-inbox"
    if not inbox.exists() and not inbox.is_symlink():
        return False
    if not inbox.is_dir() or inbox.is_symlink():
        raise ValueError("NAR_PARTIAL_MANUAL_INBOX_INVALID")
    candidates = [x for x in inbox.iterdir()
                  if x.name.startswith(day + "_") and _OFFICIAL_NAME.fullmatch(x.name)]
    if not candidates:
        return False
    if len(candidates) != 1:
        raise ValueError("NAR_PARTIAL_MANUAL_SOURCE_AMBIGUOUS")
    import_user_downloaded_preoff_race(capture, candidates[0])
    return True


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-root", type=Path, required=True)
    p.add_argument("--import-manual-if-needed", action="store_true",
                   help="Offline only; accept a single user-staged current-day ZIP.")
    args = p.parse_args()
    try:
        imported = False
        if args.import_manual_if_needed:
            imported = prepare_manual_source_if_needed(
                args.private_root, now=datetime.now(timezone.utc),
            )
        output = freeze_private_from_saved_daily(
            args.private_root, generated_utc=datetime.now(timezone.utc),
        )
        output["manual_source_imported_this_run"] = imported
    except Exception:
        print(json.dumps({
            "schema": "NAR.PC2.FittedModelPartialFeatureFrozen.v1",
            "status": "HOLD_NO_VERIFIED_REAL_PREOFF_SOURCE_OR_MODEL",
            "raw_data_uploaded": False,
            "actual_bets": 0,
            "positive_ev_proven": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
