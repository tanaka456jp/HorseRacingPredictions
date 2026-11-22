"""Offline, read-only PC2 evidence readiness. Never export private records."""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
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
        "unmatched_race_rows": 0,
        "missing_popularity_rows": 0,
        "missing_win_odds_rows": 0,
        "invalid_price_or_popularity_rows": 0,
        "failed_preoff_time_rows": 0,
        "market_snapshot_rows": 0,
        "eligible_paired_races": 0,
        "eligible_preoff_quote_rows": 0,
        "excluded_missing_preoff_evidence_races": 0,
        "official_csv_market_rows": 0,
        "official_csv_win_rows": 0,
        "official_csv_place_rows": 0,
        "selected_win_quote_present_rows": 0,
        "selected_win_popularity_present_rows": 0,
        "snapshots_without_any_win_rows": 0,
        "snapshots_with_win_rows_but_no_selected_win_price": 0,
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
        eligible_races = set()
        eligible_quote_rows = 0
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
            source_audit = doc["audit_PRIVATE"]
            for key, dest in (
                ("market_rows", "official_csv_market_rows"),
                ("win_rows", "official_csv_win_rows"),
                ("place_rows", "official_csv_place_rows"),
            ):
                value = source_audit[key]
                if type(value) is not int or value < 0:
                    raise ValueError("INVALID_OFFICIAL_SOURCE_COUNT")
                result[dest] += value
            if (source_audit["market_rows"] < source_audit["win_rows"] + source_audit["place_rows"]
                    or source_audit["planned_win_tickets_with_price"] > source_audit["registered_flat_races"]
                    or source_audit["planned_win_tickets_with_price"] < 0):
                raise ValueError("INCONSISTENT_SOURCE_AUDIT_COUNTS")
            if source_audit["win_rows"] == 0:
                result["snapshots_without_any_win_rows"] += 1
            elif source_audit["planned_win_tickets_with_price"] == 0:
                result["snapshots_with_win_rows_but_no_selected_win_price"] += 1
            selections = doc["selected_quotes_PRIVATE"]["selected_quotes_PRIVATE"]
            for item in selections:
                result["market_snapshot_rows"] += 1
                key = (day, item["race_id"])
                if key not in frozen:
                    result["unmatched_race_rows"] += 1
                    result["unverifiable_or_invalid_quote_rows"] += 1
                    continue
                if key not in seen:
                    seen.add(key)
                    result["quote_rows_matched_to_frozen_races"] += 1
                popularity = item.get("win_popularity")
                if popularity is not None:
                    result["selected_win_popularity_present_rows"] += 1
                if item.get("win_interim_odds") is not None:
                    result["selected_win_quote_present_rows"] += 1
                odds = item.get("win_interim_odds")
                # Distinguish genuinely missing prices from invalid values.
                # Counts are per snapshot row, not distinct races.
                if popularity is None:
                    result["missing_popularity_rows"] += 1
                if odds is None:
                    result["missing_win_odds_rows"] += 1
                valid_popularity = (isinstance(popularity, int)
                                    and not isinstance(popularity, bool)
                                    and popularity >= 1)
                # Official parser serializes Decimal prices as numeric strings.
                # Reject booleans, non-finite values and malformed strings.
                valid_odds = False
                if type(odds) in (int, float, str):
                    try:
                        price = Decimal(str(odds))
                        valid_odds = price.is_finite() and price > 0
                    except InvalidOperation:
                        pass
                if not valid_popularity or not valid_odds:
                    if ((popularity is not None and not valid_popularity)
                            or (odds is not None and not valid_odds)):
                        result["invalid_price_or_popularity_rows"] += 1
                    result["unverifiable_or_invalid_quote_rows"] += 1
                    continue
                result["quotes_with_popularity_and_win_odds"] += 1
                off, generated = frozen[key]
                if generated <= source <= received < off - LEAD:
                    result["chronologically_preoff_quotes"] += 1
                    eligible_races.add(key)
                    eligible_quote_rows += 1
                else:
                    result["failed_preoff_time_rows"] += 1
                    result["unverifiable_or_invalid_quote_rows"] += 1
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        result["status"] = "HOLD_PRIVATE_EVIDENCE_SCHEMA_OR_PROVENANCE_INVALID"
    result["eligible_paired_races"] = len(eligible_races) if "eligible_races" in locals() else 0
    result["eligible_preoff_quote_rows"] = eligible_quote_rows if "eligible_quote_rows" in locals() else 0
    result["excluded_missing_preoff_evidence_races"] = max(0, result["frozen_races"] - result["eligible_paired_races"])
    if result["status"] == "HOLD_INDEPENDENT_FORECAST_WITNESS_AND_OFFICIAL_SETTLEMENT_REQUIRED":
        if result["odds_provenance_files"] and result["official_csv_market_rows"] == 0:
            result["status"] = "HOLD_OFFICIAL_ODDS_CSV_NO_MARKET_ROWS"
        elif result["official_csv_win_rows"] == 0:
            result["status"] = "HOLD_OFFICIAL_ODDS_CSV_NO_WIN_ROWS"
        elif result["selected_win_quote_present_rows"] == 0:
            result["status"] = "HOLD_NO_SELECTED_WIN_QUOTES"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-capture-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.private_capture_dir), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
