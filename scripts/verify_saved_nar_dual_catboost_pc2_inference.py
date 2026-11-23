"""PC2 offline native inference smoke with real trained private NAR CatBoost.

The 4 input runners and race below are entirely fictional. This NEVER
counts as a real prospective forecast, return, independent receipt or EV.
No licensed source rows, model weights or picks are sent to GitHub.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path

import pandas as pd

from horse_racing_predictions.dual_candidate_private_preview import (
    load_dual_research_candidate,
)
from horse_racing_predictions.prospective_dual_model_shadow import (
    freeze_fitted_dual_shadow,
)

_JST = timezone(timedelta(hours=9))
_FEATURES = (
    "past_starts", "past_win_rate", "past_top3_rate",
    "past_mean_finish", "days_since_last_start",
)
_MODEL = "nar-forward-models/2017-2021-fit-2022-tune-v1"
_SCHEMA = "NAR.PC2.NativeDualCatBoostFictionalInference.v1"


def verify_saved_model(private_root: Path) -> dict:
    if (os.environ.get("COMPUTERNAME") != "DESKTOP-MVV1FD4"
            or not isinstance(private_root, Path)
            or not private_root.is_absolute()
            or private_root.is_symlink()
            or not private_root.is_dir()):
        raise ValueError("NAR_PRIVATE_PC2_CONTEXT_INVALID")
    try:
        loaded = load_dual_research_candidate(private_root / _MODEL)
    except Exception as exc:
        # The real loader's known static failure strings are mapped to
        # fixed safe codes; never emit unknown native exception text.
        known = {
            "candidate directory missing or linked": "NAR_NATIVE_DIRECTORY_INVALID",
            "missing or nonlocal model research artifact": "NAR_NATIVE_ARTIFACT_FILE_INVALID",
            "dual research manifest may not authorize release": "NAR_NATIVE_MANIFEST_RIGHTS_GATE",
            "invalid trained model chronology": "NAR_NATIVE_MODEL_CHRONOLOGY_INVALID",
            "dual research target/metrics inconsistent": "NAR_NATIVE_METRICS_CONTRACT_INVALID",
            "dual native binary digests missing": "NAR_NATIVE_DIGEST_SCHEMA_INVALID",
            "dual binary checksum mismatch": "NAR_NATIVE_BINARY_SHA_MISMATCH",
            "native dual CatBoost features differ from manifest": "NAR_NATIVE_FEATURE_NAMES_MISMATCH",
            "real CatBoost runtime unavailable": "NAR_NATIVE_RUNTIME_DEPENDENCY_MISSING",
            "duplicate dual manifest key": "NAR_NATIVE_MANIFEST_DUPLICATE_KEY",
        }
        reason = known.get(str(exc), "NAR_NATIVE_UNCLASSIFIED_LOADER_FAILURE")
        raise ValueError(reason) from None
    if (tuple(loaded.features) != _FEATURES
            or loaded.train_end != "2021-12-31"
            or len(loaded.digest_by_role) != 2
            or loaded.winner.model is loaded.outsider.model):
        raise ValueError("NAR_PRIVATE_MODEL_SCHEMA_MISMATCH")
    # Fixed synthetic date, independent of the PC clock or racing calendar.
    generated = datetime(2026, 12, 6, 9, tzinfo=_JST)
    off = generated + timedelta(hours=3)
    rid = "NAR:20261206:FICTIONAL_TEST_TRACK:01"
    rows = pd.DataFrame([
        {
            "race_id": rid,
            "horse_id": f"FICTIONAL_HORSE_{n}",
            "past_starts": n * 3,
            "past_win_rate": 0.05 * n,
            "past_top3_rate": 0.10 * n,
            "past_mean_finish": float(n + 2),
            "days_since_last_start": float(n * 7),
        }
        for n in range(1, 5)
    ])
    combined = sha256(
        (loaded.digest_by_role["win.cbm"] +
         loaded.digest_by_role["outsider.cbm"]).encode("ascii")
    ).hexdigest()
    try:
        frozen = freeze_fitted_dual_shadow(
            jurisdiction="NAR", race_day_jst="2026-12-06",
            entries=rows, off_by_race={rid: off},
            winner=loaded.winner, outsider=loaded.outsider,
            model_trained_through=loaded.train_end,
            model_sha256_declared=combined,
            source_asof_utc=generated - timedelta(minutes=2),
            generated_utc=generated,
        )
    except Exception:
        raise ValueError("NAR_NATIVE_CATBOOST_FORWARD_INFERENCE_FAILED") from None
    if (len(frozen.races) != 1 or len(frozen.races[0].roster) != 4
            or len(frozen.races[0].top3) != 3
            or frozen.races[0].outsider in frozen.races[0].top3
            or not 0 < frozen.races[0].top1_probability <= 1):
        raise ValueError("NAR_PRIVATE_MODEL_NATIVE_PREDICTION_INVALID")
    return {
        "schema": _SCHEMA,
        "status": "PRIVATE_REAL_TRAINED_MODELS_EXECUTED_ON_FICTIONAL_ROSTER",
        "real_saved_model_binary_checksums_verified": True,
        "independent_native_win_and_podium_inference_executed": True,
        "fictional_races_scored": 1,
        "real_future_races_scored": 0,
        "real_hit_rate_measured": False,
        "real_roi_measured": False,
        "source_or_model_bytes_uploaded": False,
        "real_bets": 0,
        "positive_ev_proven": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-root", type=Path, required=True)
    args = p.parse_args()
    try:
        out = verify_saved_model(args.private_root)
    except Exception as exc:
        safe_reasons = {
            "NAR_PRIVATE_PC2_CONTEXT_INVALID",
            "NAR_NATIVE_DIRECTORY_INVALID",
            "NAR_NATIVE_ARTIFACT_FILE_INVALID",
            "NAR_NATIVE_MANIFEST_RIGHTS_GATE",
            "NAR_NATIVE_MODEL_CHRONOLOGY_INVALID",
            "NAR_NATIVE_METRICS_CONTRACT_INVALID",
            "NAR_NATIVE_DIGEST_SCHEMA_INVALID",
            "NAR_NATIVE_BINARY_SHA_MISMATCH",
            "NAR_NATIVE_FEATURE_NAMES_MISMATCH",
            "NAR_NATIVE_RUNTIME_DEPENDENCY_MISSING",
            "NAR_NATIVE_MANIFEST_DUPLICATE_KEY",
            "NAR_NATIVE_UNCLASSIFIED_LOADER_FAILURE",
            "NAR_PRIVATE_MODEL_SCHEMA_MISMATCH",
            "NAR_NATIVE_CATBOOST_FORWARD_INFERENCE_FAILED",
            "NAR_PRIVATE_MODEL_NATIVE_PREDICTION_INVALID",
        }
        reason = str(exc) if str(exc) in safe_reasons else "NAR_NATIVE_UNCLASSIFIED_FAILURE"
        print(json.dumps({
            "schema": _SCHEMA,
            "staticReason": reason,
            "status": "HOLD_NATIVE_PRIVATE_MODEL_INFERENCE_NOT_VERIFIED",
            "source_or_model_bytes_uploaded": False,
            "real_bets": 0,
            "positive_ev_proven": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
