"""PC2 READ-ONLY replay: real native CatBoost on REAL Nov 10 preoff ZIP.

This is deliberately post-event REPLAY, NOT prospectively frozen CatBoost
forecast, NOT hit-rate/ROI evidence, NOT an independent timestamp proof.
The source/old baseline is verified immutable. No source, horse, model
binary or new individual predictions leave private PC2 memory.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
import json
import os
from pathlib import Path

from capture_nar_official_daily_odds_preoff_once import (
    _load_original_frozen_forecast,
)
from freeze_nar_partial_catboost_daily_private import (
    freeze_partial_from_official_source,
)
from horse_racing_predictions.nar_private_dual_model_loader import (
    load_nar_private_dual_candidate,
)

_DAY = date(2026, 11, 10)
_SCHEMA = "NAR.PC2.HistoricalRealPreoffSourceNativeCatBoostReplay.v1"


def replay_private_source(
    root: Path, *,
    expected_races: int = 59,
    expected_runners: int = 641,
) -> dict:
    if (os.environ.get("COMPUTERNAME") != "DESKTOP-MVV1FD4"
            or not isinstance(root, Path)
            or not root.is_absolute() or not root.is_dir()
            or root.is_symlink()):
        raise ValueError("NAR_PRIVATE_REPLAY_PC2_CONTEXT_INVALID")
    captures = root / "nar-prospective-captures"
    if captures.is_symlink() or not captures.is_dir():
        raise ValueError("NAR_PRIVATE_REPLAY_ORIGINAL_SOURCE_MISSING")
    baseline, blob = _load_original_frozen_forecast(captures, _DAY)
    if (baseline["source_races"] != expected_races
            or baseline["source_horses"] != expected_runners
            or baseline["day"] != _DAY.isoformat()
            or baseline["odds_observed"] is not False
            or baseline["positive_ev_proven"] is not False
            or baseline["no_real_tickets"] is not True):
        raise ValueError("NAR_PRIVATE_REPLAY_BASELINE_DENOMINATOR_INVALID")
    model = load_nar_private_dual_candidate(
        root / "nar-forward-models" / "2017-2021-fit-2022-tune-v1"
    )
    frozen, counts = freeze_partial_from_official_source(
        blob,
        day=_DAY,
        observed_utc=datetime.fromisoformat(baseline["host_observed_utc"]),
        generated_utc=datetime.fromisoformat(baseline["host_generated_utc"]),
        loaded=model,
    )
    if (len(frozen.races) != expected_races
            or counts["races"] != expected_races
            or counts["runners"] != expected_runners
            or sum(len(x.roster) for x in frozen.races) != expected_runners
            or frozen.positive_expected_value_proven
            or frozen.verified_external_timestamp):
        raise ValueError("NAR_PRIVATE_REPLAY_NATIVE_COHORT_MISMATCH")
    # No actual race IDs, horse identities, predictions, SHA/digests or
    # sensitive source data are output. Model replay is NOT pre-event lock.
    return {
        "schema": _SCHEMA,
        "status": "REAL_PREOFF_SOURCE_AND_REAL_FITTED_NAR_MODELS_REPLAYED_AFTER_EVENT",
        "official_prior_preoff_flat_races": expected_races,
        "official_prior_preoff_runners": expected_runners,
        "model_observed_career_features": 3,
        "model_missing_historical_features": 2,
        "actual_native_two_catboost_models_executed": True,
        "prospective_model_selection_frozen_before_results": False,
        "prospective_hit_rate_measured": False,
        "prospective_roi_measured": False,
        "actual_bets": 0,
        "positive_ev_proven": False,
        "private_bytes_uploaded": False,
        "private_files_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        data = replay_private_source(args.private_root)
    except Exception:
        print(json.dumps({
            "schema": _SCHEMA,
            "status": "HOLD_REAL_PREOFF_SOURCE_NATIVE_MODEL_REPLAY_UNVERIFIED",
            "private_bytes_uploaded": False,
            "private_files_modified": False,
            "positive_ev_proven": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(data, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
