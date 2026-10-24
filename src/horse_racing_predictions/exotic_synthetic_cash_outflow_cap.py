"""Synthetic-only, worst-case cash-outflow reservation for multiple attempts.

A fill assumption of zero does NOT release capital: reserve stake plus
per-attempt fees and fees that might be incurred if every attempt fills.
This is a conservative cash-outflow accounting identity, not live/Paper
bankroll logic, profitability proof, provider access or betting authorization.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
import re
from typing import Any, Mapping

_FIELDS = frozenset({
    "synthetic_only", "max_race_cash_outflow_yen",
    "max_day_cash_outflow_yen", "attempts",
})
_ITEM = frozenset({
    "attempt_id", "race_id", "stake_yen", "attempt_fee_yen",
    "fill_fee_yen", "hypothetical_fill_fraction",
})
_ID = re.compile(r"(?:S|T)[0-9]{1,5}\Z")
_DECIMAL = re.compile(r"(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,8})?\Z")


def _cap(value: Any) -> int:
    if type(value) is not int or not 100 <= value <= 10_000_000 or value % 100:
        raise ValueError("cash outflow caps must be bounded 100-yen integers")
    return value


def _money(value: Any, name: str) -> Decimal:
    if type(value) is not str or not _DECIMAL.fullmatch(value):
        raise ValueError(f"{name} must be a bounded canonical nonnegative decimal")
    amount = Decimal(value)
    if amount > 1_000_000:
        raise ValueError(f"{name} exceeds bounded scenario fee limit")
    return amount


def _fraction(value: Any) -> Decimal:
    if type(value) is not str or not _DECIMAL.fullmatch(value):
        raise ValueError("hypothetical fill fraction must be decimal text")
    amount = Decimal(value)
    if amount > 1:
        raise ValueError("hypothetical fill fraction exceeds one")
    return amount


def audit_synthetic_cash_outflow_cap(case: Mapping[str, Any]) -> dict[str, Any]:
    """Block any fictional batch whose ALL-FILL expenses breach either cap.

    No selective acceptance of safe rows is allowed: an error fails the
    complete batch. Attempt fees are reserved even for non-fills.
    """
    if not isinstance(case, Mapping) or set(case) != _FIELDS:
        raise ValueError("missing or unexpected synthetic cash outflow fields")
    if case["synthetic_only"] is not True:
        raise ValueError("explicit synthetic-only protocol required")
    cap_race = _cap(case["max_race_cash_outflow_yen"])
    cap_day = _cap(case["max_day_cash_outflow_yen"])
    if cap_race > cap_day:
        raise ValueError("race cash outflow cap exceeds day cap")
    attempts = case["attempts"]
    if type(attempts) is not list or not 1 <= len(attempts) <= 1024:
        raise ValueError("bounded nonempty synthetic attempts required")

    seen: set[str] = set()
    by_race: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
    total = Decimal(0)
    stake_total = Decimal(0)
    attempt_fee_total = Decimal(0)
    full_fill_fee_total = Decimal(0)
    hypothetical_filled_cash = Decimal(0)
    for item in attempts:
        if not isinstance(item, Mapping) or set(item) != _ITEM:
            raise ValueError("unexpected synthetic attempt fields")
        ticket, race = item["attempt_id"], item["race_id"]
        if (
            type(ticket) is not str or not _ID.fullmatch(ticket)
            or not ticket.startswith("T") or ticket in seen
        ):
            raise ValueError("duplicate or invalid synthetic ticket ID")
        if (
            type(race) is not str or not _ID.fullmatch(race)
            or not race.startswith("S")
        ):
            raise ValueError("invalid synthetic race ID")
        seen.add(ticket)
        stake = _cap(item["stake_yen"])
        attempt_fee = _money(item["attempt_fee_yen"], "attempt fee")
        fill_fee = _money(item["fill_fee_yen"], "fill fee")
        fraction = _fraction(item["hypothetical_fill_fraction"])
        maximum_cash = Decimal(stake) + attempt_fee + fill_fee
        stake_total += Decimal(stake)
        attempt_fee_total += attempt_fee
        full_fill_fee_total += fill_fee
        total += maximum_cash
        by_race[race] += maximum_cash
        if by_race[race] > cap_race:
            raise ValueError("aggregate race cash outflow cap exceeded")
        if total > cap_day:
            raise ValueError("aggregate day cash outflow cap exceeded")
        hypothetical_filled_cash += (
            attempt_fee + fraction * (Decimal(stake) + fill_fee)
        )

    return {
        "status": "synthetic_cash_outflow_bound_only",
        "attempt_count": len(attempts),
        "synthetic_race_count": len(by_race),
        "max_race_cash_outflow_yen": cap_race,
        "max_day_cash_outflow_yen": cap_day,
        "stake_full_reservation_yen": str(stake_total),
        "attempt_fee_full_reservation_yen": str(attempt_fee_total),
        "fill_fee_full_reservation_yen": str(full_fill_fee_total),
        "all_fill_worst_case_cash_outflow_yen": str(total),
        "peak_single_race_outflow_yen": str(max(by_race.values())),
        "unreserved_daily_cash_capacity_yen": str(Decimal(cap_day) - total),
        "hypothetical_fill_weighted_cash_outflow_yen": str(
            hypothetical_filled_cash
        ),
        "synthetic_cash_outflow_cap_passed": True,
        "stake_plus_attempt_plus_fill_fees_reserved": True,
        "fill_fraction_never_reduces_reserved_cash": True,
        "daily_cap_implemented_in_live_or_paper": False,
        "real_costs_or_liquidity_verified": False,
        "eligible_opportunity_coverage_verified": False,
        "positive_executable_ev_proven": False,
        "paper_or_live_action_authorized": False,
        "protected_holdout_used": False,
    }
