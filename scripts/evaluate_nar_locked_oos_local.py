"""Explicit local-only NAR locked OOS research review of curated JSON.

No NAR/JRA download, web, provider authentication, arbitrary archive scan,
model fitting, network export, note posting or wagers. Only a separately
reviewed, operator-selected complete 2023-24 forecast/settlement JSON file.
Actual rights and genuine pre-off freeze require evidence outside this CLI.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import sys

from horse_racing_predictions.nar_locked_oos_economics import (
    evaluate_nar_locked_out_of_sample,
)
from horse_racing_predictions.oddsfree_ev_research import (
    FinalRaceSettlement, FrozenOddsFreeForecast,
)

_SCHEMA="NARLockedOOSCandidate.v1"
_ROOT_KEYS=frozenset({
    "schema","expected_races","candidate_forecasts",
    "benchmark_forecasts","settlements","documented_exclusions",
    "extra_cost_yen_per_race",
})
_FORECAST_KEYS=frozenset({
    "race_id","race_day","post_time_utc","predicted_at_utc",
    "model_ref","model_fit_through_day","winner_scores",
    "outsider_scores","odds_used_in_selection",
})
_SETTLEMENT_KEYS=frozenset({
    "race_id","finishing_positions",
    "win_return_per_100_yen","place_return_per_100_yen",
})
_MAX_JSON_BYTES=22_000_000


def _strict_pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_PRIVATE_JSON_FIELD")
        result[key]=value
    return result


def _reject_constant(_value):
    raise ValueError("JSON_NONFINITE_BLOCKED")


def _local_data(path: Path):
    if (not path.is_absolute()
            or path.suffix.lower()!=".json"
            or not path.is_file()
            or path.is_symlink()
            or any(parent.is_symlink() for parent in path.parents)
            or not 0 < path.stat().st_size <= _MAX_JSON_BYTES):
        raise ValueError("SPECIFIC_CURATED_PRIVATE_JSON_REQUIRED")
    raw=path.read_bytes()
    if len(raw)>_MAX_JSON_BYTES:
        raise ValueError("PRIVATE_INPUT_BOUNDS_EXCEEDED")
    obj=json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=_strict_pairs,
        parse_constant=_reject_constant,
    )
    if not isinstance(obj,dict) or set(obj)!=_ROOT_KEYS or obj["schema"]!=_SCHEMA:
        raise ValueError("PRIVATE_NAR_OOS_JSON_SCHEMA_INVALID")
    if (not isinstance(obj["expected_races"],dict)
            or not isinstance(obj["documented_exclusions"],dict)
            or any(not isinstance(obj[k],list) for k in (
                "candidate_forecasts","benchmark_forecasts","settlements",
            ))):
        raise ValueError("PRIVATE_NAR_OOS_UNEXPECTED_FIELD_SHAPES")
    def predictions(name):
        out=[]
        for row in obj[name]:
            if not isinstance(row,dict) or set(row)!=_FORECAST_KEYS:
                raise ValueError("PRIVATE_NAR_OOS_FORECAST_STRUCTURE_INVALID")
            item=dict(row)
            item["post_time_utc"]=datetime.fromisoformat(item["post_time_utc"])
            item["predicted_at_utc"]=datetime.fromisoformat(item["predicted_at_utc"])
            out.append(FrozenOddsFreeForecast(**item))
        return out
    payouts=[]
    for row in obj["settlements"]:
        if not isinstance(row,dict) or set(row)!=_SETTLEMENT_KEYS:
            raise ValueError("PRIVATE_NAR_OOS_PAYOUT_STRUCTURE_INVALID")
        payouts.append(FinalRaceSettlement(**row))
    return (obj["expected_races"],predictions("candidate_forecasts"),
            predictions("benchmark_forecasts"),payouts,
            obj["documented_exclusions"],obj["extra_cost_yen_per_race"])


def evaluate_local_curated_nar(path: Path) -> dict:
    expected,candidate,benchmark,settlements,exclusions,cost=_local_data(path)
    review=evaluate_nar_locked_out_of_sample(
        expected_races=expected,
        candidate_forecasts=candidate,
        benchmark_forecasts=benchmark,
        settlements=settlements,
        documented_exclusions=exclusions,
        extra_cost_yen_per_race=cost,
    )
    # This dataclass contains only aggregates and explicit false permissions.
    result=asdict(review)
    result["schema"]="NARLockedOOSPrivateResearchAggregate.v1"
    result["historical_roi_is_not_future_expected_value"]=True
    result["curated_json_self_attestation_is_not_independent_rights_review"]=True
    return result


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewed-local-json",type=Path,required=True)
    parser.add_argument("--no-provider-access",action="store_true",required=True)
    args=parser.parse_args()
    try:
        summary=evaluate_local_curated_nar(args.reviewed_local_json)
    except (OSError,ValueError,TypeError,KeyError,AttributeError,
            UnicodeError,OverflowError,RecursionError):
        print(json.dumps({
            "status":"BLOCKED",
            "reason":"UNVERIFIED_PRIVATE_NAR_OOS_SOURCE_OR_STRUCTURE",
            "positive_expected_value_demonstrated":False,
            "authorized_for_note":False,
            "authorized_for_betting":False,
            "protected_2025_plus_opened":False,
        },sort_keys=True))
        return 2
    print(json.dumps(summary,ensure_ascii=False,sort_keys=True,allow_nan=False))
    # Passing the sampling minimum means only diagnostic research was done.
    return 0 if summary["economic_diagnostic_performed"] else 2


if __name__=="__main__":
    raise SystemExit(main())
