"""Synthetic-only prebet quote / hypothetical fill provenance reconciliation.

This module models a *possible* execution timeline; no brokerage access,
provider acquisition, user data, real fills or economic validation occur.
"""
from __future__ import annotations

from decimal import Decimal
import re
from typing import Any, Mapping

from .exotic_prebet_odds_contract import _instant

_NUMERIC = re.compile(r"(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,8})?\Z")
_FIELDS = frozenset({
    "synthetic_only", "outcome", "observed_at", "captured_at",
    "decision_at", "purchase_cutoff_at", "scheduled_post_at",
    "fill_at", "displayed_decimal_odds", "filled_decimal_odds",
    "stake_yen", "attempt_fee_yen",
})


def _price(text: Any, field: str) -> Decimal:
    if type(text) is not str or not _NUMERIC.fullmatch(text):
        raise ValueError(f"{field} requires bounded canonical decimal string")
    value = Decimal(text)
    if not Decimal("1") < value <= Decimal("1000000"):
        raise ValueError(f"{field} outside allowed synthetic price bounds")
    return value


def audit_synthetic_quote_fill_reconciliation(case: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed on time travel and mismatched hypothetical fill evidence.

    Neither displayed nor filled odds are claimed to represent legally
    obtained, reliably executable pari-mutuel odds.
    """
    if not isinstance(case, Mapping) or set(case) != _FIELDS:
        raise ValueError("unexpected or missing synthetic quote/fill fields")
    if case["synthetic_only"] is not True:
        raise ValueError("only synthetic quote/fill experiments are allowed")
    if type(case["stake_yen"]) is not int or not (
        100 <= case["stake_yen"] <= 10_000_000
    ) or case["stake_yen"] % 100:
        raise ValueError("stake must be a bounded 100-yen multiple")
    fee_raw = case["attempt_fee_yen"]
    if type(fee_raw) is not str or not _NUMERIC.fullmatch(fee_raw):
        raise ValueError("attempt fee must be canonical nonnegative decimal")
    if Decimal(fee_raw) > 1_000_000:
        raise ValueError("attempt fee exceeds synthetic limit")

    observed = _instant(case["observed_at"])
    captured = _instant(case["captured_at"])
    decided = _instant(case["decision_at"])
    cutoff = _instant(case["purchase_cutoff_at"])
    scheduled = _instant(case["scheduled_post_at"])
    if not observed <= captured <= decided < cutoff < scheduled:
        raise ValueError("invalid pre-purchase quote/cutoff chronology")

    displayed = _price(case["displayed_decimal_odds"], "displayed_decimal_odds")
    outcome = case["outcome"]
    if outcome not in ("filled", "unfilled"):
        raise ValueError("outcome must be filled or unfilled")
    if outcome == "filled":
        filled_at = _instant(case["fill_at"])
        if not decided <= filled_at <= cutoff:
            raise ValueError("fill occurred outside hypothetical purchase window")
        purchased = _price(case["filled_decimal_odds"], "filled_decimal_odds")
        odds_delta = purchased - displayed
        slippage = odds_delta / displayed
        filled_stake = case["stake_yen"]
    else:
        if case["fill_at"] is not None or case["filled_decimal_odds"] is not None:
            raise ValueError("unfilled attempt cannot have a fill time or price")
        purchased, odds_delta, slippage, filled_stake = None, None, None, 0

    return {
        "status": "synthetic_execution_timeline_only",
        "outcome": outcome,
        "attempted_stake_yen": case["stake_yen"],
        "filled_stake_yen": filled_stake,
        "paid_attempt_fee_yen": fee_raw,
        "displayed_odds": str(displayed),
        "hypothetical_filled_odds": str(purchased) if purchased is not None else None,
        "hypothetical_price_slippage_multiple": (
            str(odds_delta) if odds_delta is not None else None
        ),
        "hypothetical_relative_price_slippage": (
            str(slippage) if slippage is not None else None
        ),
        "quote_and_fill_timestamps_structurally_valid": True,
        "liquidity_verified": False,
        "real_fill_verified": False,
        "pre_purchase_quote_rights_verified": False,
        "purchase_price_verified": False,
        "positive_executable_ev_proven": False,
        "paper_or_live_action_authorized": False,
        "protected_holdout_used": False,
    }
