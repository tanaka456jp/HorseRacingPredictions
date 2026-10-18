"""Synthetic-only same-race profit comparison with day-cluster sensitivity.

Fictional input only. No real odds, settlement, scraping, accounts, or
confidence statement about tradable positive expected value.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
import random
import re
from typing import Any, Mapping

_SIGNED = re.compile(r"-?(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,8})?\Z")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_RACE = re.compile(r"S[0-9]{1,5}\Z")
_FIELDS = frozenset({
    "synthetic_only", "strategy_frozen_before_evaluation",
    "benchmark_frozen_before_evaluation", "max_race_stake_yen",
    "max_day_stake_yen", "bootstrap_samples", "bootstrap_seed", "comparisons",
})
_ROW = frozenset({
    "day", "race_id", "strategy_stake_yen", "market_stake_yen",
    "strategy_net_yen", "market_net_yen",
})


def _stake(value: Any) -> int:
    if type(value) is not int or not 0 <= value <= 10_000_000 or value % 100:
        raise ValueError("stake must be bounded 100-yen integer, including zero")
    return value


def _profit(value: Any) -> Decimal:
    if type(value) is not str or not _SIGNED.fullmatch(value):
        raise ValueError("synthetic signed net profit requires bounded decimal")
    result = Decimal(value)
    if abs(result) > 1_000_000_000:
        raise ValueError("synthetic profit magnitude out of bounds")
    return result


def audit_synthetic_forward_day_profit(case: Mapping[str, Any]) -> dict[str, Any]:
    """Test a frozen hypothetical strategy against a same-race comparator.

    Bootstrap resamples whole synthetic days, not individual tickets/races.
    An exploratory interval can never establish independent profitability.
    """
    if not isinstance(case, Mapping) or set(case) != _FIELDS:
        raise ValueError("unknown or missing day-profit research fields")
    for flag in ("synthetic_only", "strategy_frozen_before_evaluation",
                 "benchmark_frozen_before_evaluation"):
        if case[flag] is not True:
            raise ValueError(f"{flag} must be explicitly true")
    cap_race, cap_day = _stake(case["max_race_stake_yen"]), _stake(case["max_day_stake_yen"])
    if cap_race < 100 or cap_day < cap_race:
        raise ValueError("race/day capital caps must be positive and ordered")
    samples, seed = case["bootstrap_samples"], case["bootstrap_seed"]
    if type(samples) is not int or not 100 <= samples <= 2000:
        raise ValueError("bounded exploratory day bootstrap samples required")
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError("bounded deterministic bootstrap seed required")
    rows = case["comparisons"]
    if type(rows) is not list or not 1 <= len(rows) <= 5000:
        raise ValueError("nonempty bounded same-race comparisons required")

    seen: set[str] = set()
    day_cap_stakes: dict[date, list[int]] = defaultdict(lambda: [0, 0])
    day_profit: dict[date, list[Decimal]] = defaultdict(lambda: [Decimal(0), Decimal(0)])
    no_stake_opps = [0, 0]
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != _ROW:
            raise ValueError("invalid same-race comparison columns")
        raw_date, race_id = row["day"], row["race_id"]
        if type(raw_date) is not str or not _DATE.fullmatch(raw_date):
            raise ValueError("canonical synthetic evaluation day required")
        try:
            day = date.fromisoformat(raw_date)
        except ValueError as exc:
            raise ValueError("invalid synthetic calendar day") from exc
        if not date(2023, 1, 1) <= day <= date(2024, 12, 31):
            raise ValueError("protected 2025-2026 dates forbidden")
        if type(race_id) is not str or not _RACE.fullmatch(race_id) or race_id in seen:
            raise ValueError("distinct synthetic race IDs required")
        seen.add(race_id)
        a, b = _stake(row["strategy_stake_yen"]), _stake(row["market_stake_yen"])
        if a > cap_race or b > cap_race:
            raise ValueError("race capital cap exceeded")
        pa, pb = _profit(row["strategy_net_yen"]), _profit(row["market_net_yen"])
        if (a == 0 and pa > 0) or (b == 0 and pb > 0):
            raise ValueError("unbought race cannot report positive net profit")
        if a == 0: no_stake_opps[0] += 1
        if b == 0: no_stake_opps[1] += 1
        cap = day_cap_stakes[day]
        cap[0] += a
        cap[1] += b
        if cap[0] > cap_day or cap[1] > cap_day:
            raise ValueError("day capital cap exceeded")
        profit = day_profit[day]
        profit[0] += pa
        profit[1] += pb

    ordered_days = sorted(day_profit)
    strategy = sum((day_profit[day][0] for day in ordered_days), Decimal(0))
    market = sum((day_profit[day][1] for day in ordered_days), Decimal(0))
    a_stake = sum(x[0] for x in day_cap_stakes.values())
    b_stake = sum(x[1] for x in day_cap_stakes.values())
    day_deltas = [day_profit[d][0] - day_profit[d][1] for d in ordered_days]
    rng = random.Random(seed)
    # Report an exploratory, day-resampled PROFIT DELTA, not ROI or a
    # formal confidence interval. Preserve same-race pairing within each day.
    draws = []
    n = len(day_deltas)
    for _ in range(samples):
        draws.append(sum((day_deltas[rng.randrange(n)] for _ in range(n)), Decimal(0)))
    draws.sort()
    return {
        "status": "synthetic_day_cluster_sensitivity_only",
        "synthetic_races": len(seen),
        "synthetic_days": n,
        "strategy_no_stake_opportunities": no_stake_opps[0],
        "market_no_stake_opportunities": no_stake_opps[1],
        "strategy_total_stake_yen": a_stake,
        "market_total_stake_yen": b_stake,
        "strategy_net_profit_yen": str(strategy),
        "market_net_profit_yen": str(market),
        "net_profit_delta_vs_market_yen": str(strategy - market),
        "strategy_net_roi": str(strategy / a_stake) if a_stake else None,
        "market_net_roi": str(market / b_stake) if b_stake else None,
        "day_cluster_bootstrap_samples": samples,
        "exploratory_delta_q05_yen": str(draws[(samples - 1) * 5 // 100]),
        "exploratory_delta_q95_yen": str(draws[(samples - 1) * 95 // 100]),
        "same_race_benchmark_preserved": True,
        "strategy_eligibility_frozen_by_assertion_only": True,
        "formal_confidence_interval": False,
        "real_observation_verified": False,
        "positive_executable_ev_proven": False,
        "paper_or_live_action_authorized": False,
        "protected_holdout_used": False,
    }
