"""Offline-only prospective quote audit; no network, private inputs or provider SDK.

This module never treats an indicative quote as an executable transaction.
"""
from datetime import datetime, timezone


def audit_quote(*, race_key, market, quote, source_time, received_time,
                off_time, registered_races):
    """Return a public-safe reason code, never a race key or raw quote."""
    # A malformed roster or unhashable identifier must fail closed without
    # logging private identifiers or interrupting a prospective audit.
    if isinstance(registered_races, (str, bytes)):
        return "INVALID_MANIFEST"
    try:
        registered = tuple(registered_races)
        registered_set = set(registered)
    except (TypeError, ValueError):
        return "INVALID_MANIFEST"
    # Validate the complete frozen roster before classifying the target race.
    # An empty/duplicated roster is a manifest error, not an absent race.
    if (not registered or len(registered_set) != len(registered) or
            any(not isinstance(k, str) or not k.strip() for k in registered)):
        return "INVALID_MANIFEST"
    if not isinstance(race_key, str) or not race_key or race_key not in registered_set:
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
    # A scalar string is one identifier, not a roster of character IDs.
    # Fail closed without printing potentially private race identifiers.
    if isinstance(registered_races, (str, bytes)) or isinstance(observed_races, (str, bytes)):
        return {"status": "INVALID_MANIFEST", "registered": 0,
                "observed": 0, "missing": 0, "unexpected": 0}
    try:
        registered = tuple(registered_races)
        observed = tuple(observed_races)
        registered_set = set(registered)
        seen = set(observed)
    except (TypeError, ValueError):
        # Malformed/unhashable identifiers must not crash the offline audit.
        return {"status": "INVALID_MANIFEST", "registered": 0,
                "observed": 0, "missing": 0, "unexpected": 0}
    if (any(not isinstance(k, str) or not k.strip() for k in registered) or
            any(not isinstance(k, str) or not k.strip() for k in observed)):
        status = "INVALID_MANIFEST"
    elif not registered:
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
