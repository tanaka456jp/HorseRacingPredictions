"""Synthetic-only forward batch opportunity and full-stake budget audit.

Never connects to a broker/provider or executes a bet. Hypothetical fill
fraction does not reduce worst-case capital reservation; abstentions remain
in the eligible opportunity denominator.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
import re
from typing import Any, Mapping

from .exotic_prebet_odds_contract import _instant

_ID = re.compile(r"(?:S|T)[0-9]{1,5}\Z")
_FRAC = re.compile(r"(?:0(?:\.[0-9]{1,8})?|1(?:\.0{1,8})?)\Z")
_FIELDS = frozenset({
    "synthetic_only", "model_finalized_at", "max_race_stake_yen",
    "max_day_stake_yen", "opportunities",
})
_ROW = frozenset({
    "race_id", "candidate_id", "selection_status",
    "observed_at", "decision_at", "purchase_cutoff_at",
    "scheduled_post_at", "stake_yen", "hypothetical_fill_fraction",
})


def _stake(value: Any, zero: bool = False) -> int:
    if type(value) is not int or not 0 <= value <= 10_000_000 or value % 100:
        raise ValueError("stake must be bounded 100-yen integer")
    if not zero and value < 100:
        raise ValueError("minimum hypothetical stake is 100 yen")
    return value


def audit_synthetic_forward_batch(case: Mapping[str, Any]) -> dict[str, Any]:
    """Reject duplicate, future, time-travelling, oversubscribed scenarios."""
    if not isinstance(case, Mapping) or set(case) != _FIELDS:
        raise ValueError("invalid synthetic forward batch fields")
    if case["synthetic_only"] is not True:
        raise ValueError("explicitly synthetic-only input required")
    model_finalized = _instant(case["model_finalized_at"])
    if not 2017 <= model_finalized.year <= 2024:
        raise ValueError("frozen model time is outside pre-2025 range")
    race_cap = _stake(case["max_race_stake_yen"])
    day_cap = _stake(case["max_day_stake_yen"])
    if race_cap > day_cap:
        raise ValueError("race cap exceeds day cap")
    rows = case["opportunities"]
    if type(rows) is not list or not 1 <= len(rows) <= 1024:
        raise ValueError("bounded nonempty opportunity list required")

    seen: set[str] = set()
    reserved: dict[str, int] = defaultdict(int)
    total = 0
    assumed_filled = Decimal(0)
    attempts = abstentions = 0
    batch_date = None
    for item in rows:
        if not isinstance(item, Mapping) or set(item) != _ROW:
            raise ValueError("unknown or missing synthetic opportunity fields")
        race, ticket = item["race_id"], item["candidate_id"]
        if type(race) is not str or not _ID.fullmatch(race) or not race.startswith("S"):
            raise ValueError("synthetic race ID required")
        if type(ticket) is not str or not _ID.fullmatch(ticket) or not ticket.startswith("T") or ticket in seen:
            raise ValueError("duplicate or invalid synthetic candidate ID")
        seen.add(ticket)
        decision = _instant(item["decision_at"])
        cutoff = _instant(item["purchase_cutoff_at"])
        post = _instant(item["scheduled_post_at"])
        if not (model_finalized <= decision < cutoff < post and
                2017 <= decision.year <= 2024 and post.year <= 2024):
            raise ValueError("invalid model/decision/cutoff/post chronology")
        if batch_date is None:
            batch_date = decision.date()
        if decision.date() != batch_date:
            raise ValueError("daily batch must use one synthetic UTC decision day")
        status = item["selection_status"]
        if status == "attempted":
            observed = _instant(item["observed_at"])
            if not model_finalized <= observed <= decision:
                raise ValueError("quote observed before model freeze or after decision")
            stake = _stake(item["stake_yen"])
            fraction_raw = item["hypothetical_fill_fraction"]
            if type(fraction_raw) is not str or not _FRAC.fullmatch(fraction_raw):
                raise ValueError("fill scenario requires bounded decimal fraction")
            fraction = Decimal(fraction_raw)
            total += stake
            reserved[race] += stake
            if reserved[race] > race_cap or total > day_cap:
                raise ValueError("full-stake race/day reservation cap exceeded")
            assumed_filled += Decimal(stake) * fraction
            attempts += 1
        elif status == "abstained":
            if item["observed_at"] is not None or item["hypothetical_fill_fraction"] is not None or _stake(item["stake_yen"], zero=True) != 0:
                raise ValueError("abstention requires no quote, fill assumption or stake")
            abstentions += 1
        else:
            raise ValueError("unknown synthetic selection status")
    return {
        "status": "synthetic_forward_batch_preflight_only",
        "eligible_opportunity_count": len(rows),
        "attempted_count": attempts,
        "abstained_count": abstentions,
        "distinct_synthetic_races": len({item["race_id"] for item in rows}),
        "worst_case_all_fill_reserved_yen": total,
        "hypothetical_expected_fill_stake_yen": str(assumed_filled),
        "synthetic_cap_check_passed": True,
        "full_stakes_reserved": True,
        "actual_eligible_opportunity_coverage_verified": False,
        "real_quote_rights_verified": False,
        "real_liquidity_verified": False,
        "real_execution_verified": False,
        "positive_executable_ev_proven": False,
        "paper_or_live_action_authorized": False,
        "protected_holdout_used": False,
    }
