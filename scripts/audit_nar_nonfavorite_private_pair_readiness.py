"""Offline, read-only PC2 evidence readiness. Never export private records."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

LEAD = timedelta(minutes=10)


def _utc(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("NAIVE_TIMESTAMP")
    return result.astimezone(timezone.utc)


def audit(directory: Path) -> dict:
    result = {
        "schema": "NAR.PC2.NonfavoritePairReadiness.v1",
        "status": "HOLD_INDEPENDENT_FORECAST_WITNESS_AND_OFFICIAL_SETTLEMENT_REQUIRED",
        "baseline_files": 0,
        "odds_provenance_files": 0,
        "frozen_races": 0,
        "quote_rows_matched_to_frozen_races": 0,
        "quotes_with_popularity_and_win_odds": 0,
        "chronologically_preoff_quotes": 0,
        "unverifiable_or_invalid_quote_rows": 0,
        "independently_witnessed_forecasts": 0,
        "officially_settled_races": 0,
        "source_records_exported": False,
        "after_cost_positive_expected_value_proven": False,
        "actual_tickets_purchased": False,
    }
    if not directory.is_dir() or directory.is_symlink():
        result["status"] = "HOLD_PRIVATE_DIRECTORY_UNAVAILABLE"
        return result
    baselines = sorted(directory.glob("*_baseline_forecast_PRIVATE.json"))
    quotes = sorted(directory.glob("*_odds_private_provenance.json"))
    result["baseline_files"] = len(baselines)
    result["odds_provenance_files"] = len(quotes)
    frozen = {}
    digests = {}
    try:
        for path in baselines:
            if not path.is_file() or path.is_symlink():
                raise ValueError("UNSAFE_BASELINE")
            doc = json.loads(path.read_text(encoding="utf-8"))
            if doc.get("schema") != "NAR.PC2.OfficialDailyForwardBaseline.v1":
                raise ValueError("BAD_BASELINE_SCHEMA")
            day = doc["day"]
            if day in digests:
                raise ValueError("DUPLICATE_BASELINE_DAY")
            digests[day] = doc["commitment_digest"]
            entries = doc["complete_private_forecasts"]
            if not isinstance(entries, list) or len(entries) != doc["source_races"]:
                raise ValueError("INCOMPLETE_BASELINE")
            for entry in entries:
                key = (day, entry["race_id"])
                if key in frozen or entry["race_day"] != day:
                    raise ValueError("DUPLICATE_OR_MISMATCHED_RACE")
                frozen[key] = (_utc(entry["scheduled_off_utc"]),
                               _utc(entry["generated_at_utc"]))
        result["frozen_races"] = len(frozen)
        seen = set()
        for path in quotes:
            if not path.is_file() or path.is_symlink():
                raise ValueError("UNSAFE_ODDS_PROVENANCE")
            doc = json.loads(path.read_text(encoding="utf-8"))
            if doc.get("schema") != "NAR.PC2.OfficialDailyInterimOddsProvenance.v1":
                raise ValueError("BAD_ODDS_SCHEMA")
            day = doc["audit_PRIVATE"]["source_day_jst"]
            if day not in digests or doc["frozen_private_forecast_digest"] != digests[day]:
                raise ValueError("FORECAST_DIGEST_MISMATCH")
            source = _utc(doc["source_generated_utc"])
            received = _utc(doc["captured_utc"])
            selections = doc["selected_quotes_PRIVATE"]["selected_quotes_PRIVATE"]
            for item in selections:
                key = (day, item["race_id"])
                if key not in frozen:
                    result["unverifiable_or_invalid_quote_rows"] += 1
                    continue
                if key not in seen:
                    seen.add(key)
                    result["quote_rows_matched_to_frozen_races"] += 1
                popularity = item.get("win_popularity")
                odds = item.get("win_interim_odds")
                if (not isinstance(popularity, int) or isinstance(popularity, bool)
                        or popularity < 1 or not isinstance(odds, (int, float))
                        or isinstance(odds, bool) or odds <= 0):
                    result["unverifiable_or_invalid_quote_rows"] += 1
                    continue
                result["quotes_with_popularity_and_win_odds"] += 1
                off, generated = frozen[key]
                if generated <= source <= received < off - LEAD:
                    result["chronologically_preoff_quotes"] += 1
                else:
                    result["unverifiable_or_invalid_quote_rows"] += 1
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        result["status"] = "HOLD_PRIVATE_EVIDENCE_SCHEMA_OR_PROVENANCE_INVALID"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-capture-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.private_capture_dir), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
