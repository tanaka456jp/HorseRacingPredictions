"""Synthetic-only execution-time triage. Never approves acquisition, EV or staking."""
from __future__ import annotations
from collections.abc import Mapping
from datetime import timedelta
from typing import Any
from urllib.parse import urlsplit
from .exotic_odds_source_triage import triage_exotic_odds_source
from .exotic_prebet_odds_contract import _instant, inspect_exotic_prebet_quote

def triage_exotic_prebet_execution(quote: Mapping[str, Any], source_evidence: Mapping[str, Any], *, decision_at: str, purchase_cutoff_at: str) -> dict[str, Any]:
    """Fail closed on mismatched sources, stale quotes or unavailable purchase windows."""
    source = triage_exotic_odds_source(source_evidence)
    inspected = inspect_exotic_prebet_quote(quote, decision_at=decision_at)
    blockers = [f"source: {b}" for b in source["blockers"]]
    blockers += [f"quote: {b}" for b in inspected["blockers"]]
    if isinstance(quote, Mapping) and isinstance(source_evidence, Mapping):
        if quote.get("source_name") != source_evidence.get("provider_name"):
            blockers.append("source name mismatch")
        if quote.get("source_reference") != source_evidence.get("source_reference"):
            blockers.append("source reference mismatch")
        reference = source_evidence.get("purchase_cutoff_reference")
        try:
            if not isinstance(reference, str):
                raise ValueError("missing")
            url = urlsplit(reference)
            if (url.scheme != "https" or not url.hostname or url.username is not None
                or url.password is not None or any(c.isspace() for c in reference)):
                raise ValueError("invalid")
        except ValueError:
            blockers.append("purchase cutoff reference requires HTTPS")
    else:
        blockers.append("source and quote must be objects")
    try:
        decision = _instant(decision_at)
        cutoff = _instant(purchase_cutoff_at)
        if not isinstance(quote, Mapping) or not isinstance(source_evidence, Mapping):
            raise ValueError("quote and source must be objects")
        scheduled = _instant(quote.get("scheduled_post_time"))
        observed = _instant(quote.get("observed_at"))
        cadence = source_evidence.get("provider_refresh_seconds")
        if type(cadence) is not int or not 0 < cadence <= 86400:
            blockers.append("invalid or unknown refresh cadence")
        elif decision - observed > timedelta(seconds=cadence):
            blockers.append("quote exceeds documented refresh cadence")
        if not decision < cutoff < scheduled:
            blockers.append("purchase cutoff must fall between decision and scheduled post")
    except (ValueError, TypeError, OverflowError) as exc:
        blockers.append(f"invalid purchase window: {exc}")
    return {
        "status": "blocked" if blockers else "human_review_required",
        "blockers": blockers,
        "canonical_combination_key": inspected.get("canonical_combination_key") if not blockers else None,
        "approved_for_acquisition": False,
        "approved_for_ev": False,
        "approved_for_paper_staking": False,
        "note": "All rights, timestamps and cutoff evidence remain unverified human assertions.",
    }
