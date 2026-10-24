"""Synthetic-only forward settlement accounting with separate price/result stages.

Post-race fictional settlement multipliers are NEVER fed back into quote
validation or pre-purchase EV. This module makes no outcome predictions,
performs no bets, and reads no provider files or final holdout data.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
import re
from typing import Any, Mapping

from .exotic_prebet_odds_contract import _instant

_NUM = re.compile(r"(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,8})?\Z")
_ID = re.compile(r"(?:S|T)[0-9]{1,5}\Z")
_FIELDS = frozenset({"synthetic_only", "max_race_stake_yen", "max_day_stake_yen", "opportunities"})
_ROW = frozenset({
    "attempt_id", "race_id", "observed_at", "decision_at",
    "purchase_at", "purchase_cutoff_at", "scheduled_post_at",
    "settled_at", "status", "stake_yen",
    "pre_purchase_decimal_odds", "hypothetical_settlement_multiplier",
    "fee_yen",
})


def _amount(value: Any, field: str) -> Decimal:
    if type(value) is not str or not _NUM.fullmatch(value):
        raise ValueError(f"{field} must be bounded unsigned decimal text")
    return Decimal(value)


def _stake(value: Any, field: str) -> int:
    if type(value) is not int or not 100 <= value <= 10_000_000 or value % 100:
        raise ValueError(f"{field} must be bounded 100-yen integer")
    return value


def audit_synthetic_forward_settlement(case: Mapping[str, Any]) -> dict[str, Any]:
    """Validate opportunity ledger including failures, costs and drawdown."""
    if not isinstance(case, Mapping) or set(case) != _FIELDS:
        raise ValueError("missing or unexpected synthetic settlement fields")
    if case["synthetic_only"] is not True:
        raise ValueError("synthetic-only forward settlement required")
    race_cap = _stake(case["max_race_stake_yen"], "race cap")
    day_cap = _stake(case["max_day_stake_yen"], "day cap")
    if race_cap > day_cap:
        raise ValueError("race cap must be at most day cap")
    rows = case["opportunities"]
    if type(rows) is not list or not 1 <= len(rows) <= 1024:
        raise ValueError("nonempty bounded opportunity ledger required")
    seen = set()
    reserve: dict[str, int] = defaultdict(int)
    total_reserved = 0
    ledger: list[tuple[object, str, Decimal]] = []
    fills = 0
    unfilled = 0
    for item in rows:
        if not isinstance(item, Mapping) or set(item) != _ROW:
            raise ValueError("missing or unexpected opportunity fields")
        ticket, race = item["attempt_id"], item["race_id"]
        if type(ticket) is not str or not _ID.fullmatch(ticket) or not ticket.startswith("T") or ticket in seen:
            raise ValueError("duplicate or invalid synthetic ticket ID")
        if type(race) is not str or not _ID.fullmatch(race) or not race.startswith("S"):
            raise ValueError("invalid synthetic race ID")
        seen.add(ticket)
        stake = _stake(item["stake_yen"], "stake")
        reserve[race] += stake
        total_reserved += stake
        if reserve[race] > race_cap or total_reserved > day_cap:
            raise ValueError("aggregate all-fill race/day capital cap exceeded")
        observed = _instant(item["observed_at"])
        decision = _instant(item["decision_at"])
        cutoff = _instant(item["purchase_cutoff_at"])
        post = _instant(item["scheduled_post_at"])
        if not (2017 <= post.year <= 2024 and
                observed <= decision < cutoff < post and
                observed.year >= 2017 and decision.year <= 2024):
            raise ValueError("invalid bounded synthetic pre-purchase timeline")
        odds = _amount(item["pre_purchase_decimal_odds"], "pre-purchase odds")
        if not 1 < odds <= 1_000_000:
            raise ValueError("invalid pre-purchase decimal odds")
        fee = _amount(item["fee_yen"], "fee")
        if fee > 1_000_000:
            raise ValueError("synthetic fee exceeds cap")
        status = item["status"]
        if status == "unfilled":
            if any(item[field] is not None for field in
                   ("purchase_at", "settled_at", "hypothetical_settlement_multiplier")):
                raise ValueError("unfilled opportunity cannot have purchase/settlement")
            unfilled += 1
            ledger.append((decision, ticket, -fee))
        elif status == "filled":
            bought = _instant(item["purchase_at"])
            settled = _instant(item["settled_at"])
            if not (decision <= bought <= cutoff < post < settled):
                raise ValueError("invalid pre-purchase or post-race settlement order")
            if settled.year > 2024:
                raise ValueError("protected 2025-2026 settlement dates are not allowed")
            multiplier = _amount(item["hypothetical_settlement_multiplier"], "settlement multiplier")
            if multiplier > 1_000_000:
                raise ValueError("hypothetical settlement multiplier exceeds cap")
            fills += 1
            ledger.append((settled, ticket, Decimal(stake) * (multiplier - 1) - fee))
        else:
            raise ValueError("status must be filled or unfilled")
    balance = Decimal(0)
    high_water = Decimal(0)
    max_drawdown = Decimal(0)
    for _, __, profit in sorted(ledger, key=lambda row: (row[0], row[1])):
        balance += profit
        if balance > high_water:
            high_water = balance
        if high_water - balance > max_drawdown:
            max_drawdown = high_water - balance

    net = sum((entry[2] for entry in ledger), Decimal(0))
    filled_stake = sum(
        item["stake_yen"] for item in rows if item["status"] == "filled"
    )
    return {
        "status": "synthetic_forward_settlement_diagnostic_only",
        "opportunities": len(rows),
        "filled_attempts": fills,
        "unfilled_attempts": unfilled,
        "all_fill_reserved_yen": total_reserved,
        "peak_single_race_reserved_yen": max(reserve.values()),
        "hypothetical_filled_stake_yen": filled_stake,
        "hypothetical_net_profit_yen": str(net),
        "hypothetical_filled_stake_roi": (
            str(net / Decimal(filled_stake)) if filled_stake else None
        ),
        "chronological_max_drawdown_yen": str(max_drawdown),
        "outcome_stage_separated_from_quote_stage": True,
        "real_quote_availability_verified": False,
        "real_execution_verified": False,
        "real_settlement_verified": False,
        "positive_executable_ev_proven": False,
        "paper_or_live_action_authorized": False,
        "protected_holdout_used": False,
    }
