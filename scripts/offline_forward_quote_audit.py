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
    if not (0 < quote < float("inf")):
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
    if len(registered) != len(set(registered)):
        return {"status": "DUPLICATE_REGISTRATION"}
    observed = tuple(observed_races)
    if len(observed) != len(set(observed)):
        return {"status": "DUPLICATE_OBSERVATION"}
    seen = set(observed)
    return {"status": "OK", "registered": len(registered),
            "observed": len(seen.intersection(registered)),
            "missing": len(set(registered) - seen),
            "unexpected": len(seen - set(registered))}
