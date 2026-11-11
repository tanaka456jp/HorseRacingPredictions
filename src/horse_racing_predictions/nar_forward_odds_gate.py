"""Offline fail-closed gate for fictional forward-day NAR odds audit receipts.

This module never reads private files, contacts providers, or authorizes betting.
The caller must supply a separately frozen, pre-event manifest (not a value
inferred from the downloaded ZIP). No individual prices/identifiers are emitted.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


class ForwardOddsGateError(ValueError):
    pass


def _utc(value):
    if not isinstance(value, str):
        raise ForwardOddsGateError("INVALID_TIMESTAMP")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ForwardOddsGateError("INVALID_TIMESTAMP") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ForwardOddsGateError("INVALID_TIMESTAMP")
    return dt.astimezone(timezone.utc)


def _count(obj, key):
    value = obj.get(key)
    if type(value) is not int or value < 0:
        raise ForwardOddsGateError("INVALID_AGGREGATE")
    return value


def validate_forward_receipt(receipt, frozen_manifest):
    """Return safe aggregate summary or reject; never accept ZIP-derived baseline."""
    if not isinstance(receipt, dict) or not isinstance(frozen_manifest, dict):
        raise ForwardOddsGateError("INVALID_INPUT")
    day = frozen_manifest.get("race_day_jst")
    if not isinstance(day, str):
        raise ForwardOddsGateError("MISSING_FROZEN_DAY")
    try:
        if datetime.strptime(day, "%Y-%m-%d").strftime("%Y-%m-%d") != day:
            raise ValueError
    except ValueError as exc:
        raise ForwardOddsGateError("INVALID_FROZEN_DAY") from exc
    if receipt.get("source_day_jst") != day:
        raise ForwardOddsGateError("DAY_MISMATCH")
    observed = _utc(receipt.get("observed_at_utc"))
    source = _utc(receipt.get("official_source_time_utc"))
    first_off = _utc(frozen_manifest.get("first_off_at_utc"))
    frozen_at = _utc(frozen_manifest.get("frozen_at_utc"))
    if observed.astimezone(ZoneInfo("Asia/Tokyo")).date().isoformat() != day:
        raise ForwardOddsGateError("OBSERVED_DAY_MISMATCH")
    if not (frozen_at < source <= observed < first_off):
        raise ForwardOddsGateError("CHRONOLOGY_HOLD")
    if (first_off - observed).total_seconds() < 600:
        raise ForwardOddsGateError("TOO_LATE")
    races = _count(frozen_manifest, "frozen_races")
    horses = _count(frozen_manifest, "frozen_horses")
    if races < 1 or horses < races:
        raise ForwardOddsGateError("INVALID_FROZEN_ROSTER")
    if _count(receipt, "flat_races") != races or _count(receipt, "registered_horses") != horses:
        raise ForwardOddsGateError("ROSTER_MISMATCH")
    win = _count(receipt, "frozen_win_tickets_with_quote")
    place = _count(receipt, "frozen_place_tickets_with_quote")
    missing_win = _count(receipt, "missing_frozen_win_quotes")
    missing_place = _count(receipt, "missing_frozen_place_quotes")
    if win + missing_win != races or place + missing_place != races:
        raise ForwardOddsGateError("TICKET_DENOMINATOR_MISMATCH")
    if _count(frozen_manifest, "planned_ticket_count") != 2 * races:
        raise ForwardOddsGateError("PLAN_MISMATCH")
    if receipt.get("original_forecast_unchanged") is not True or receipt.get("source_uploaded") is not False:
        raise ForwardOddsGateError("PRIVACY_OR_FREEZE_HOLD")
    if _count(receipt, "actual_tickets") != 0 or receipt.get("after_cost_ev_proven") is not False:
        raise ForwardOddsGateError("ECONOMIC_CLAIM_HOLD")
    return {
        "status": "PRIVATE_FORWARD_PRICE_COVERAGE_AUDIT_ONLY",
        "raceDay": day, "frozenRaces": races, "frozenHorses": horses,
        "winQuoted": win, "placeQuoted": place,
        "winMissing": missing_win, "placeMissing": missing_place,
        "executablePriceProven": False, "afterCostPositiveEVProven": False,
    }
