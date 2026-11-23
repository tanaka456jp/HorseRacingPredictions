"""PC2-only offline scoring of a genuinely frozen dual-CatBoost forecast.

Never opens racing websites, changes a frozen forecast, prints private
horse/race identities or treats source review as independent attestation.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re

from horse_racing_predictions.prospective_dual_model_shadow import (
    FrozenModelShadow, FrozenShadowRace, score_frozen_shadow,
)

_PRIVATE_SCHEMA = "HorseRacing.PC2.ProspectiveDualModelPrivate.v1"
_RESULTS_SCHEMA = "HorseRacing.PC2.ReviewedOfficialResults.v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")


def load_verified_private_forecast(
    frozen_file: Path,
) -> tuple[FrozenModelShadow, dict]:
    """Verify full PRIVATE model snapshot and salted immutable commitment.

    No network or output. Reusable for a separately authenticated official
    postevent ZIP importer without weakening the existing review gate.
    """
    if (os.environ.get("COMPUTERNAME") != "DESKTOP-MVV1FD4"
            or not isinstance(frozen_file, Path)
            or not frozen_file.is_absolute()
            or not frozen_file.is_file()
            or frozen_file.is_symlink()
            or not 100 < frozen_file.stat().st_size <= 25_000_000):
        raise ValueError("INVALID_PRIVATE_SOURCE")
    doc = json.loads(frozen_file.read_text(encoding="utf-8"))
    if (type(doc) is not dict or doc.get("schema") != _PRIVATE_SCHEMA
            or doc.get("source_and_roster_independently_attested") is not False
            or doc.get("actual_bets") != 0
            or doc.get("after_cost_positive_ev_proven") is not False
            or doc.get("raw_source_uploaded") is not False):
        raise ValueError("UNTRUSTED_PRIVATE_FORECAST")
    original = doc["frozen_shadow_PRIVATE"]
    necessary = {
        "schema", "jurisdiction", "race_day_jst", "generated_utc",
        "source_asof_utc", "model_trained_through",
        "model_sha256_declared", "races",
    }
    if (type(original) is not dict
            or not necessary.issubset(original)
            or type(original["races"]) is not list
            or not original["races"]):
        raise ValueError("FROZEN_FORECAST_STRUCTURE_INVALID")
    canonical = {k: original[k] for k in necessary}
    commitment = sha256(json.dumps(
        canonical, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()
    if (not _SHA.fullmatch(commitment)
            or commitment != original.get("commitment_sha256")
            or not isinstance(doc.get("salt_hex_PRIVATE"), str)
            or not re.fullmatch(r"[0-9a-f]{64}\Z",
                                doc["salt_hex_PRIVATE"])
            or sha256(
                b"HORSERACING_FORWARD_DUAL_V1\x00" +
                bytes.fromhex(doc["salt_hex_PRIVATE"]) +
                commitment.encode("ascii")
            ).hexdigest() != doc.get("blinded_digest")):
        raise ValueError("FROZEN_FORECAST_COMMITMENT_INVALID")
    races = tuple(FrozenShadowRace(
        race_id=r["race_id"], off_utc=r["off_utc"],
        roster=tuple(r["roster"]), top3=tuple(r["top3"]),
        outsider=r["outsider"], top1_probability=r["top1_probability"],
    ) for r in original["races"])
    if (len(races) != len(set(r.race_id for r in races))
            or any(len(set(r.roster)) != len(r.roster)
                   or len(r.top3) != 3
                   or len(set(r.top3)) != 3
                   or not set(r.top3).issubset(r.roster)
                   or r.outsider not in r.roster
                   or r.outsider in r.top3
                   for r in races)):
        raise ValueError("UNSAFE_FROZEN_ROSTER_OR_PICKS")
    snapshot = FrozenModelShadow(
        schema=original["schema"], jurisdiction=original["jurisdiction"],
        race_day_jst=original["race_day_jst"],
        generated_utc=original["generated_utc"],
        source_asof_utc=original["source_asof_utc"],
        model_trained_through=original["model_trained_through"],
        model_sha256_declared=original["model_sha256_declared"],
        races=races, commitment_sha256=commitment,
    )
    return snapshot, doc


def score_private_forward_files(
    frozen_file: Path, reviewed_official_results: Path,
) -> dict:
    if os.environ.get("COMPUTERNAME") != "DESKTOP-MVV1FD4":
        raise ValueError("WRONG_PRIVATE_MACHINE")
    for path in (frozen_file, reviewed_official_results):
        if (not isinstance(path, Path) or not path.is_absolute()
                or not path.is_file() or path.is_symlink()
                or not 100 < path.stat().st_size <= 25_000_000):
            raise ValueError("INVALID_PRIVATE_SOURCE")
    snapshot, doc = load_verified_private_forecast(frozen_file)
    official = json.loads(reviewed_official_results.read_text(encoding="utf-8"))
    if (type(official) is not dict
            or set(official) != {
                "schema", "jurisdiction", "race_day_jst",
                "observed_postevent_utc",
                "operator_reviewed_official_results",
                "independently_verified_source_provenance",
                "official_races",
            }
            or official["schema"] != _RESULTS_SCHEMA
            or official["jurisdiction"] != snapshot.jurisdiction
            or official["race_day_jst"] != snapshot.race_day_jst
            or official["operator_reviewed_official_results"] is not True
            or official["independently_verified_source_provenance"] is not False):
        raise ValueError("OFFICIAL_REVIEW_OR_SOURCE_PROVENANCE_INVALID")
    receipt = datetime.fromisoformat(
        official["observed_postevent_utc"].replace("Z", "+00:00")
    )
    if receipt.utcoffset() is None or receipt.astimezone(timezone.utc) <= max(
        datetime.fromisoformat(r.off_utc).astimezone(timezone.utc)
        for r in races
    ) + timedelta(minutes=15):
        raise ValueError("OFFICIAL_FINAL_SOURCE_TOO_EARLY")
    outcome = score_frozen_shadow(
        snapshot, final_by_race=official["official_races"],
    )
    output = asdict(outcome)
    output["schema"] = "HorseRacing.PC2.ModelProspectiveAggregateOnly.v1"
    output["independent_prediction_receipt_verified"] = False
    output["source_review_only_not_independent_authentication"] = True
    output["model_digest_blinded_witness"] = doc["blinded_digest"]
    output["source_data_uploaded"] = False
    return output


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-frozen-json", type=Path, required=True)
    p.add_argument("--reviewed-official-results-json", type=Path, required=True)
    args = p.parse_args()
    try:
        result = score_private_forward_files(
            args.private_frozen_json, args.reviewed_official_results_json,
        )
    except Exception:
        print(json.dumps({
            "schema": "HorseRacing.PC2.ModelProspectiveAggregateOnly.v1",
            "status": "HOLD_MISSING_OR_UNTRUSTED_FROZEN_OR_OFFICIAL_RESULTS",
            "source_data_uploaded": False,
            "positive_expected_value_proven": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0 if result["status"].startswith("COMPLETE_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
