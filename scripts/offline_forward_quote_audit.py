"""Offline-only prospective quote audit; no network, private inputs or provider SDK.

This module never treats an indicative quote as an executable transaction.
"""
from datetime import datetime, timezone


def audit_quote(*, race_key, market, quote, source_time, received_time,
                off_time, registered_races):
    """Return a public-safe reason code, never a race key or raw quote."""
    if race_key not in registered_races:
        return "UNREGISTERED_RACE"
    if market not in ("WIN", "PLACE"):
        return "INVALID_MARKET"
    if quote is None:
        return "MISSING_PRICE"
    if not isinstance(quote, (int, float)) or isinstance(quote, bool):
        return "INVALID_PRICE"
    if not (1.0 <= quote < float("inf")):
        return "INVALID_PRICE"
    times = (source_time, received_time, off_time)
    if any(not isinstance(t, datetime) or t.tzinfo is None or
           t.utcoffset() is None for t in times):
        return "INVALID_TIMESTAMP"
    source, received, off = (t.astimezone(timezone.utc) for t in times)
    if source > received:
        return "SOURCE_AFTER_RECEIPT"
    if received >= off or source >= off:
        return "AFTER_CUTOFF"
    return "INDICATIVE_ONLY"


def audit_manifest(*, registered_races, observed_races):
    """Count registered denominator without deleting missing or duplicate races."""
    registered = tuple(registered_races)
    observed = tuple(observed_races)
    registered_set = set(registered)
    seen = set(observed)
    if not registered:
        status = "EMPTY_REGISTRATION"
    elif len(registered) != len(registered_set):
        status = "DUPLICATE_REGISTRATION"
    elif len(observed) != len(seen):
        status = "DUPLICATE_OBSERVATION"
    elif seen - registered_set:
        status = "UNEXPECTED_OBSERVATION"
    elif registered_set - seen:
        status = "MISSING_OBSERVATION"
    else:
        status = "OK"
    return {"status": status,
            "registered": len(registered),
            "observed": len(seen.intersection(registered_set)),
            "missing": len(registered_set - seen),
            "unexpected": len(seen - registered_set)}
