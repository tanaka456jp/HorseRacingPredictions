"""Outcome-conditioned hypothetical adverse stress grid; synthetic ONLY.

Ex-post dropping profitable fills is deliberately pessimistic sensitivity,
not a prospective filling process, calibrated probability, EV estimate, or
live/paper execution system. Does not access provider data or the holdout.
"""
from __future__ import annotations

from decimal import Decimal
import re
from typing import Any, Mapping

_NUM = re.compile(r"(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,8})?\Z")
_SIGNED = re.compile(r"-?(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,8})?\Z")
_ID = re.compile(r"S[0-9]{1,5}\Z")
_FIELDS = frozenset({
    "synthetic_only", "protocol_frozen_before_evaluation",
    "max_day_stake_yen", "payout_haircuts", "adverse_nonfill_counts", "races",
})
_RACE_FIELDS = frozenset({
    "race_id", "strategy_status", "strategy_stake_yen", "attempt_fee_yen",
    "hypothetical_settlement_multiplier", "frozen_market_net_yen",
})


def _decimal(raw: Any, pattern: re.Pattern[str], name: str) -> Decimal:
    if type(raw) is not str or not pattern.fullmatch(raw):
        raise ValueError(f"{name} must be bounded canonical decimal text")
    value = Decimal(raw)
    if abs(value) > Decimal(1_000_000_000):
        raise ValueError(f"{name} magnitude exceeds synthetic bound")
    return value


def audit_synthetic_stress_grid(case: Mapping[str, Any]) -> dict[str, Any]:
    """Reconcile all eligible fictional races over a bounded adverse grid."""
    if not isinstance(case, Mapping) or set(case) != _FIELDS:
        raise ValueError("missing or unexpected synthetic grid fields")
    if case["synthetic_only"] is not True or case["protocol_frozen_before_evaluation"] is not True:
        raise ValueError("synthetic and preregistered protocol flags required")
    cap = case["max_day_stake_yen"]
    if type(cap) is not int or not 100 <= cap <= 10_000_000 or cap % 100:
        raise ValueError("bounded daily capital cap required")
    rows = case["races"]
    if type(rows) is not list or not 1 <= len(rows) <= 200:
        raise ValueError("bounded nonempty fictional race list required")
    haircuts, counts = case["payout_haircuts"], case["adverse_nonfill_counts"]
    if type(haircuts) is not list or type(counts) is not list or not haircuts or not counts:
        raise ValueError("nonempty bounded stress axes required")
    if len(haircuts) * len(counts) > 100:
        raise ValueError("stress grid too large")
    h = [_decimal(raw, _NUM, "payout haircut") for raw in haircuts]
    if h[0] != 0 or any(not 0 <= x <= Decimal("0.95") for x in h) or h != sorted(set(h)):
        raise ValueError("payout haircuts must be strictly increasing from zero")
    if (counts[0] != 0 or any(type(x) is not int or x < 0 or x > len(rows) for x in counts)
            or counts != sorted(set(counts))):
        raise ValueError("nonfill counts must be strictly increasing from zero")

    seen: set[str] = set()
    parsed: list[tuple[str, int, Decimal, Decimal, Decimal]] = []
    total_reserved = 0
    market_total = Decimal(0)
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != _RACE_FIELDS:
            raise ValueError("invalid fictional race fields")
        race_id = row["race_id"]
        if type(race_id) is not str or not _ID.fullmatch(race_id) or race_id in seen:
            raise ValueError("synthetic race ID must be unique")
        seen.add(race_id)
        status, stake = row["strategy_status"], row["strategy_stake_yen"]
        if status not in ("filled", "unfilled", "abstained") or type(stake) is not int:
            raise ValueError("invalid synthetic execution status or stake")
        if status == "abstained":
            if stake != 0:
                raise ValueError("abstention must have zero stake")
        elif not 100 <= stake <= cap or stake % 100:
            raise ValueError("attempted stake must be bounded 100-yen multiple")
        fee = _decimal(row["attempt_fee_yen"], _NUM, "attempt fee")
        if fee > 1_000_000 or (status == "abstained" and fee != 0):
            raise ValueError("invalid synthetic attempt fees")
        payout = row["hypothetical_settlement_multiplier"]
        if status == "filled":
            multiplier = _decimal(payout, _NUM, "hypothetical settlement payout")
            if multiplier > 1_000_000:
                raise ValueError("synthetic payout multiplier too high")
        else:
            if payout is not None:
                raise ValueError("unfilled/abstained race cannot have a payout")
            multiplier = Decimal(0)
        market = _decimal(row["frozen_market_net_yen"], _SIGNED, "market net")
        total_reserved += stake
        if total_reserved > cap:
            raise ValueError("aggregate day cap exceeded")
        market_total += market
        parsed.append((status, stake, fee, multiplier, market))

    cells = []
    last_by_count: dict[int, Decimal] = {}
    for haircut in h:
        profits = []
        for status, stake, fee, multiplier, _ in parsed:
            if status == "filled":
                net = Decimal(stake) * (multiplier * (1 - haircut) - 1) - fee
                # Ex-post profit lost by making an actual positive winner
                # into a *fictional* no-fill, preserving its attempt fee.
                forgone = net + fee if net > 0 else Decimal(0)
            else:
                net = -fee
                forgone = Decimal(0)
            profits.append((net, forgone))
        unstressed_total = sum((x[0] for x in profits), Decimal(0))
        removable = sorted((x[1] for x in profits if x[1] > 0), reverse=True)
        for count in counts:
            loss = sum(removable[:count], Decimal(0))
            stressed = unstressed_total - loss
            previous = last_by_count.get(count)
            if previous is not None and stressed > previous:
                raise RuntimeError("higher haircut must not increase synthetic profit")
            last_by_count[count] = stressed
            cells.append({
                "payout_haircut": str(haircut),
                "adverse_nonfill_budget": count,
                "fictional_strategy_net_yen": str(stressed),
                "frozen_market_net_yen": str(market_total),
                "fictional_delta_vs_market_yen": str(stressed - market_total),
            })
    # Ensure within each haircut, more harmful ex-post nonfills never help.
    for offset in range(0, len(cells), len(counts)):
        group = cells[offset:offset + len(counts)]
        if any(Decimal(group[i]["fictional_strategy_net_yen"]) >
               Decimal(group[i - 1]["fictional_strategy_net_yen"])
               for i in range(1, len(group))):
            raise RuntimeError("adverse nonfills must not improve profit")

    return {
        "status": "synthetic_outcome_conditioned_stress_only",
        "eligible_synthetic_races": len(parsed),
        "attempted_worst_case_stake_yen": total_reserved,
        "cells": cells,
        "all_eligible_opportunities_preserved": True,
        "ex_post_adverse_nonfills_not_prospective_model": True,
        "market_baseline_frozen": True,
        "formal_confidence_interval": False,
        "real_fill_probability_verified": False,
        "real_pre_purchase_quote_verified": False,
        "positive_executable_ev_proven": False,
        "paper_or_live_action_authorized": False,
        "protected_holdout_used": False,
    }
