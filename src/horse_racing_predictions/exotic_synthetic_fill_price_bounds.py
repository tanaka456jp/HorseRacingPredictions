"""Synthetic-only, outcome-free price/fill EV sensitivity diagnostics.

No quote acquisition, actual race data, settlement, execution, or permissions.
The probability is a hypothetical LOWER BOUND *conditional on a fill*;
using an unconditional race-win probability here would hide adverse selection.
"""
from __future__ import annotations

from decimal import Decimal
import re
from typing import Any, Mapping


_FIELDS = frozenset({
    "synthetic_only", "conditional_win_probability_lower", "displayed_decimal_odds",
    "payout_haircut", "fill_fraction", "stake_yen", "fee_per_fill_yen",
    "fee_per_attempt_yen", "max_race_stake_yen", "max_day_stake_yen",
})
_DECIMAL = re.compile(r"(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,8})?\Z")


def _number(value: Any, field: str) -> Decimal:
    if type(value) is not str or not _DECIMAL.fullmatch(value):
        raise ValueError(f"{field} must be a bounded, unsigned decimal string")
    return Decimal(value)


def audit_synthetic_fill_price_bounds(case: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed; return only hypothetical per-attempt net EV diagnostics.

    Fill fraction is a *scenario parameter*, not a measured fill probability.
    Net per attempt = fill_fraction * [stake*(conditional_p*haircut_odds-1)
                    - fee_per_fill] - fee_per_attempt.
    A missed fill incurs no stake/fee-per-fill, but does incur attempt cost.
    No profit or live/paper trading approval is ever granted.
    """
    if not isinstance(case, Mapping) or set(case) != _FIELDS:
        raise ValueError("missing or unexpected synthetic scenario fields")
    if case["synthetic_only"] is not True:
        raise ValueError("only explicitly synthetic scenarios are permitted")
    stake = case["stake_yen"]
    race_cap = case["max_race_stake_yen"]
    day_cap = case["max_day_stake_yen"]
    if any(type(x) is not int or not 100 <= x <= 10_000_000 or x % 100
           for x in (stake, race_cap, day_cap)):
        raise ValueError("stake and caps must be bounded 100-yen multiples")
    if stake > race_cap or stake > day_cap:
        raise ValueError("hypothetical stake exceeds race or day cap")

    p = _number(case["conditional_win_probability_lower"], "conditional_win_probability_lower")
    odds = _number(case["displayed_decimal_odds"], "displayed_decimal_odds")
    haircut = _number(case["payout_haircut"], "payout_haircut")
    fill = _number(case["fill_fraction"], "fill_fraction")
    per_fill = _number(case["fee_per_fill_yen"], "fee_per_fill_yen")
    per_attempt = _number(case["fee_per_attempt_yen"], "fee_per_attempt_yen")
    if not (Decimal(0) <= p <= 1 and Decimal(1) < odds <= 1000000):
        raise ValueError("conditional probability or quote outside bounds")
    if not (Decimal(0) <= haircut < 1 and Decimal(0) <= fill <= 1):
        raise ValueError("haircut or fill fraction outside bounds")
    if per_fill > 1_000_000 or per_attempt > 1_000_000:
        raise ValueError("synthetic fees exceed bounded scenario limit")
    adjusted_odds = odds * (1 - haircut)
    net_per_fill = Decimal(stake) * (p * adjusted_odds - 1) - per_fill
    net_per_attempt = fill * net_per_fill - per_attempt
    return {
        "status": "synthetic_sensitivity_only",
        "net_ev_yen_per_filled_ticket": str(net_per_fill),
        "net_ev_yen_per_attempt": str(net_per_attempt),
        "assumed_adjusted_payout_multiple": str(adjusted_odds),
        "conditional_on_fill_probability_assumed": True,
        "fill_fraction_empirically_verified": False,
        "quote_rights_verified": False,
        "purchase_price_verified": False,
        "calibration_verified": False,
        "formal_confidence_interval": False,
        "positive_executable_ev_proven": False,
        "paper_or_live_action_authorized": False,
        "protected_holdout_used": False,
        "limitations": (
            "Synthetic scenario only. Fill probability and conditional win "
            "probability are unverified; pari-mutuel payout haircuts are not "
            "executable odds or a price guarantee. No positive-EV claim."
        ),
    }
