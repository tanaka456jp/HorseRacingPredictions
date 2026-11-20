"""Offline-only PRIVATE PC2 NAR favorite-exclusion comparison (no NAR fetch).

Requires an independently preregistered full-race manifest and explicit
pre-off market timestamps in a reviewed local JSON. Prints aggregate
counts only: never print private horse/race names, ZIPs, odds or paths.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path

from horse_racing_predictions.nar_nonfavorite_win_policy import (
    NonfavoriteWinRace,
    compare_nonfavorite_win_policies,
)

_SCHEMA = "NAR.PC2.PrivateNonfavoriteForwardEvidence.v1"
_KEYS = frozenset({
    "schema", "input_mode", "frozen_race_days", "observations",
    "ticket_unit_yen", "market_observations_preoff_only",
    "forecast_registered_before_off",
})
_ROW_FIELDS = frozenset(NonfavoriteWinRace.__dataclass_fields__)
_DATETIMES = frozenset({
    "forecast_frozen_utc", "hosted_forecast_receipt_utc",
    "scheduled_off_utc", "official_market_source_utc",
    "locally_received_market_utc",
})


def audit_private_file(path: Path):
    if (not isinstance(path, Path) or not path.is_absolute()
            or not path.is_file() or path.is_symlink()
            or not 10 <= path.stat().st_size <= 16 * 1024 * 1024):
        raise ValueError("PRIVATE_FILE_INVALID")
    data = json.loads(path.read_text(encoding="utf-8"))
    if type(data) is not dict or set(data) != _KEYS:
        raise ValueError("PRIVATE_SCHEMA_INVALID")
    if (data["schema"] != _SCHEMA
            or data["input_mode"] != "LOCAL_PERSONAL_MANUAL_PREOFF_SOURCE"
            or data["market_observations_preoff_only"] is not True
            or data["forecast_registered_before_off"] is not True
            or data["ticket_unit_yen"] != 100
            or type(data["ticket_unit_yen"]) is not int):
        raise ValueError("PRIVATE_PREOFF_SCOPE_INVALID")
    observations = data["observations"]
    if type(observations) is not list or len(observations) > 20000:
        raise ValueError("PRIVATE_OBSERVATION_COUNT_INVALID")
    rows = []
    for raw in observations:
        if type(raw) is not dict or set(raw) != _ROW_FIELDS:
            raise ValueError("PRIVATE_RACE_EVIDENCE_SCHEMA_INVALID")
        obj = raw.copy()
        for name in _DATETIMES:
            t = obj[name]
            if t is not None:
                if type(t) is not str or len(t) > 50:
                    raise ValueError("PRIVATE_TIMESTAMP_INVALID")
                obj[name] = datetime.fromisoformat(t.replace("Z", "+00:00"))
        rows.append(NonfavoriteWinRace(**obj))
    return compare_nonfavorite_win_policies(
        data["frozen_race_days"], rows,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviewed-local-json", type=Path, required=True)
    args = parser.parse_args()
    try:
        audit = audit_private_file(args.reviewed_local_json)
    except Exception:
        print(json.dumps({
            "schema": "NAR.PC2.NonfavoriteAggregateOnly.v1",
            "status": "PRIVATE_RESEARCH_HOLD",
            "source_uploaded": False, "real_bets": 0,
            "after_cost_positive_ev_proven": False,
        }, sort_keys=True))
        return 2
    summary = asdict(audit)
    summary["schema"] = "NAR.PC2.NonfavoriteAggregateOnly.v1"
    summary["result_is_paper_only"] = True
    summary["historical_2022_favorite_rank_imputed"] = False
    summary["official_source_data_uploaded"] = False
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
