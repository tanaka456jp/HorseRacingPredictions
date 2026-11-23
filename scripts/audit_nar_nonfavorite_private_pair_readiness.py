"""Offline, read-only PC2 evidence readiness. Never export private records."""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re

LEAD = timedelta(minutes=10)
_MANUAL_ZIP_NAME = re.compile(r"([0-9]{8})_([1-9][0-9]{8,12})_odds\.zip\Z")


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
        "manual_offline_odds_provenance_files": 0,
        "manual_offline_market_rows": 0,
        "manual_offline_win_rows": 0,
        "manual_offline_place_rows": 0,
        "manual_offline_matched_quote_rows": 0,
        "manual_offline_verified_chronology_quote_rows": 0,
        "manual_offline_distinct_races_with_quote": 0,
        "manual_offline_missing_win_quote_rows": 0,
        "manual_offline_source_unattested": True,
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
        "empty_source_snapshots_with_preoff_eligible_races": 0,
        "empty_source_snapshots_before_first_off": 0,
        "empty_source_snapshots_after_first_off": 0,
        "empty_source_lead_ge_240min": 0,
        "empty_source_lead_120_to_239min": 0,
        "empty_source_lead_30_to_119min": 0,
        "empty_source_lead_0_to_29min": 0,
        "preoff_eligible_race_observations": 0,
        "timing_derived_from_legacy_provenance_snapshots": 0,
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
    manual_quotes = sorted(directory.glob("*_manually_downloaded_odds_PRIVATE.json"))
    result["baseline_files"] = len(baselines)
    result["odds_provenance_files"] = len(quotes)
    result["manual_offline_odds_provenance_files"] = len(manual_quotes)
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
            # The source ZIP might contain only a header even while some
            # frozen races remain in their allowed pre-off window. Report
            # aggregate timing, never dates, horses, prices or identifiers.
            registered = source_audit["registered_flat_races"]
            futures = source_audit.get("future_preoff_eligible_races")
            closed = source_audit.get("past_or_closed_races")
            minutes = source_audit.get("minutes_before_first_scheduled_off")
            if type(registered) is not int or registered < 1:
                raise ValueError("INVALID_SOURCE_RACE_COUNT")
            day_windows = [
                (off, generated)
                for (race_day, _), (off, generated) in frozen.items()
                if race_day == day
            ]
            if len(day_windows) != registered:
                raise ValueError("SOURCE_REGISTERED_RACE_COUNT_MISMATCH")
            # Older immutable provenance snapshots did not serialize the
            # timing counters, or serialized their default (0, 0) before
            # the counters were populated. Do NOT rewrite private originals
            # and do NOT classify them as corrupt solely for this reason.
            # Derive conservative pre-off eligibility from stored source,
            # receipt, and frozen schedule timestamps. These are recorded
            # local claims, not independent clock attestation.
            legacy = (
                futures is None or closed is None or minutes is None
                or (futures == 0 and closed == 0 and registered > 0)
            )
            if legacy:
                if any(v is not None and type(v) is not int
                       for v in (futures, closed, minutes)):
                    raise ValueError("INVALID_LEGACY_TIMING_FIELD")
                futures = sum(
                    generated <= source <= received < off - LEAD
                    for off, generated in day_windows
                )
                closed = registered - futures
                minutes = int(
                    (min(off for off, _ in day_windows) - received)
                    .total_seconds() // 60
                )
                result["timing_derived_from_legacy_provenance_snapshots"] += 1
            if (any(type(v) is not int for v in (futures, closed, minutes))
                    or not (0 <= futures <= registered)
                    or not (0 <= closed <= registered)
                    or futures + closed != registered):
                raise ValueError("INCONSISTENT_SOURCE_TIMING_COUNTS")
            result["preoff_eligible_race_observations"] += futures
            if source_audit["market_rows"] == 0:
                if futures:
                    result["empty_source_snapshots_with_preoff_eligible_races"] += 1
                if minutes >= 0:
                    result["empty_source_snapshots_before_first_off"] += 1
                    if minutes >= 240:
                        result["empty_source_lead_ge_240min"] += 1
                    elif minutes >= 120:
                        result["empty_source_lead_120_to_239min"] += 1
                    elif minutes >= 30:
                        result["empty_source_lead_30_to_119min"] += 1
                    else:
                        result["empty_source_lead_0_to_29min"] += 1
                else:
                    result["empty_source_snapshots_after_first_off"] += 1
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

        # Offline user-downloaded ZIP imports use a DIFFERENT immutable
        # sidecar contract. Count these separately; neither a user-reported
        # source nor a local receipt is independently authenticated.
        # They must never inflate the automated-source evidence denominator,
        # independent witness counts, settled ROI, or a positive-EV flag.
        seen_manual_names = set()
        manual_quoted_races = set()
        for path in manual_quotes:
            if not path.is_file() or path.is_symlink():
                raise ValueError("UNSAFE_MANUAL_ODDS_PROVENANCE")
            doc = json.loads(path.read_text(encoding="utf-8"))
            if (doc.get("schema") != "NAR.PC2.ManuallyDownloadedDailyOddsAuditPrivate.v1"
                    or doc.get("download_mode") != "USER_SUPPLIED_OFFLINE_NO_PROVIDER_REQUEST"
                    or doc.get("individual_authorized_automated_polling") is not False
                    or doc.get("source_hostname_independently_attested") is not False
                    or doc.get("independent_hosted_receipt_verified") is not False
                    or doc.get("positive_ev_proven") is not False
                    or doc.get("actual_order_execution_verified") is not False
                    or doc.get("source_uploaded") is not False):
                raise ValueError("UNTRUSTED_MANUAL_ORIGIN_FLAGS")
            audit_info = doc["audit_PRIVATE"]
            day = audit_info["source_day_jst"]
            if day not in digests or doc["frozen_forecast_commitment_PRIVATE"] != digests[day]:
                raise ValueError("MANUAL_FORECAST_DIGEST_MISMATCH")
            filename = doc["source_zip_filename_PRIVATE"]
            m = _MANUAL_ZIP_NAME.fullmatch(filename) if type(filename) is str else None
            if (m is None or m[1] != day.replace("-", "")
                    or filename in seen_manual_names):
                raise ValueError("MANUAL_ORIGINAL_SOURCE_NAME_INVALID")
            seen_manual_names.add(filename)
            source = _utc(audit_info["source_generated_at_utc"])
            received = _utc(doc["local_receipt_utc"])
            if (_utc(audit_info["observed_at_utc"]) != received
                    or source > received):
                raise ValueError("MANUAL_SOURCE_RECEIPT_INCONSISTENT")
            registered = audit_info["registered_flat_races"]
            values = [audit_info[k] for k in ("market_rows", "win_rows",
                      "place_rows", "planned_win_tickets_with_price")]
            if (type(registered) is not int or registered < 1
                    or any(type(v) is not int or v < 0 for v in values)
                    or values[1] + values[2] > values[0]
                    or values[3] > registered):
                raise ValueError("MANUAL_SOURCE_COUNTS_INVALID")
            for name, val in zip(("manual_offline_market_rows",
                                  "manual_offline_win_rows",
                                  "manual_offline_place_rows"), values[:3]):
                result[name] += val
            rows = doc["quotes_PRIVATE"]["selected_quotes_PRIVATE"]
            expected_ids = {key[1] for key in frozen if key[0] == day}
            if (type(rows) is not list or len(rows) != registered
                    or len(expected_ids) != registered):
                raise ValueError("MANUAL_QUOTE_DENOMINATOR_MISMATCH")
            observed_ids = set()
            priced = 0
            for item in rows:
                rid = item["race_id"]
                key = (day, rid)
                if rid in observed_ids or rid not in expected_ids:
                    raise ValueError("MANUAL_DUPLICATE_OR_UNKNOWN_RACE")
                observed_ids.add(rid)
                result["manual_offline_matched_quote_rows"] += 1
                odds = item.get("win_interim_odds")
                rank = item.get("win_popularity")
                if odds is None or rank is None:
                    result["manual_offline_missing_win_quote_rows"] += 1
                    continue
                if type(rank) is not int or rank < 1 or type(odds) not in (str, int, float):
                    raise ValueError("MANUAL_WIN_QUOTE_INVALID")
                try:
                    price = Decimal(str(odds))
                except InvalidOperation as exc:
                    raise ValueError("MANUAL_WIN_QUOTE_INVALID") from exc
                if not price.is_finite() or price < 1:
                    raise ValueError("MANUAL_WIN_QUOTE_INVALID")
                priced += 1
                off, generated = frozen[key]
                if generated <= source <= received < off - LEAD:
                    result["manual_offline_verified_chronology_quote_rows"] += 1
                    manual_quoted_races.add(key)
            if observed_ids != expected_ids or priced != values[3]:
                raise ValueError("MANUAL_SELECTION_COUNTS_INCONSISTENT")
        result["manual_offline_distinct_races_with_quote"] = len(manual_quoted_races)
    except (OSError, ValueError, KeyError, TypeError, AttributeError,
            OverflowError, json.JSONDecodeError):
        result["status"] = "HOLD_PRIVATE_EVIDENCE_SCHEMA_OR_PROVENANCE_INVALID"
    result["eligible_paired_races"] = len(eligible_races) if "eligible_races" in locals() else 0
    result["eligible_preoff_quote_rows"] = eligible_quote_rows if "eligible_quote_rows" in locals() else 0
    result["excluded_missing_preoff_evidence_races"] = max(0, result["frozen_races"] - result["eligible_paired_races"])
    if result["status"] == "HOLD_INDEPENDENT_FORECAST_WITNESS_AND_OFFICIAL_SETTLEMENT_REQUIRED":
        if result["manual_offline_verified_chronology_quote_rows"] > 0:
            result["status"] = "HOLD_MANUAL_OFFLINE_SOURCE_NOT_INDEPENDENTLY_ATTESTED"
        elif result["odds_provenance_files"] and result["official_csv_market_rows"] == 0:
            result["status"] = "HOLD_OFFICIAL_ODDS_CSV_NO_MARKET_ROWS"
        elif result["manual_offline_odds_provenance_files"] and not result["odds_provenance_files"]:
            result["status"] = "HOLD_MANUAL_OFFLINE_NO_VERIFIED_PREOFF_WIN_QUOTES"
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
