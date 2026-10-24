"""Fail-closed, synthetic-only multi-ticket daily budget and EV aggregation.

The input is a fictional *attempt set*. Every attempted ticket reserves its
FULL stake, not its fill-weighted expectation. Reservation is conservative
because multiple attempts may fill at once. Aggregated hypothetical EV includes
attempt fees even for unfilled attempts.

No quotes, identities, historical results, live data, purchases, nor payment
can enter this module. It is not a portfolio optimizer or staking instruction.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
import re
from typing import Any, Mapping

from .exotic_synthetic_fill_price_bounds import (
    audit_synthetic_fill_price_bounds,
)

_DAILY_FIELDS = frozenset({
    "synthetic_only", "max_day_stake_yen",
    "max_race_stake_yen", "attempts",
})
_ATTEMPT_FIELDS = frozenset({
    "attempt_id", "race_id", "stake_yen",
    "conditional_win_probability_lower", "displayed_decimal_odds",
    "payout_haircut", "fill_fraction", "fee_per_fill_yen",
    "fee_per_attempt_yen",
})
_SYNTHETIC_ID = re.compile(r"(?:S|T)[0-9]{1,4}\Z")


def _yen_cap(value: Any, name: str) -> int:
    if type(value) is not int or not (100 <= value <= 10_000_000) or value % 100:
        raise ValueError(f"{name} must be a bounded 100-yen multiple")
    return value


def audit_synthetic_daily_budget(case: Mapping[str, Any]) -> dict[str, Any]:
    """Return synthetic full-stake exposure and sum of per-attempt net EVs.

    Any malformed attempt, duplicate ID or breached aggregate reservation
    blocks the WHOLE scenario rather than approving a surviving subset.
    In particular, *fill fraction never reduces the reserved budget*.
    """
    if not isinstance(case, Mapping) or set(case) != _DAILY_FIELDS:
        raise ValueError("missing or unexpected synthetic daily budget fields")
    if case["synthetic_only"] is not True:
        raise ValueError("explicit synthetic-only flag is required")

    day_cap = _yen_cap(case["max_day_stake_yen"], "max_day_stake_yen")
    race_cap = _yen_cap(case["max_race_stake_yen"], "max_race_stake_yen")
    if race_cap > day_cap:
        raise ValueError("race stake cap must not exceed daily cap")
    attempts = case["attempts"]
    if type(attempts) is not list or not 1 <= len(attempts) <= 1024:
        raise ValueError("bounded nonempty attempt list required")

    seen: set[str] = set()
    reserved_by_race: dict[str, int] = defaultdict(int)
    all_reserved = 0
    hypothetical_ev = Decimal("0")
    assumed_filled_stake = Decimal("0")
    min_attempt_net_ev: Decimal | None = None
    for item in attempts:
        if not isinstance(item, Mapping) or set(item) != _ATTEMPT_FIELDS:
            raise ValueError("missing or unexpected synthetic attempt fields")
        attempt_id = item["attempt_id"]
        race_id = item["race_id"]
        if (
            type(attempt_id) is not str or not _SYNTHETIC_ID.fullmatch(attempt_id)
            or not attempt_id.startswith("T")
            or attempt_id in seen
        ):
            raise ValueError("attempt IDs must be distinct synthetic T-numbers")
        if (
            type(race_id) is not str or not _SYNTHETIC_ID.fullmatch(race_id)
            or not race_id.startswith("S")
        ):
            raise ValueError("race IDs must be synthetic S-numbers")
        seen.add(attempt_id)
        stake = _yen_cap(item["stake_yen"], "stake_yen")
        # Prove aggregate reservation bounds BEFORE using EV estimates.
        # The worst-case must assume all orders fill, not just an assumed
        # fraction. Failure cannot be masked by appealing synthetic ROI.
        reserved_by_race[race_id] += stake
        all_reserved += stake
        if reserved_by_race[race_id] > race_cap:
            raise ValueError("aggregate same-race stake exceeds race cap")
        if all_reserved > day_cap:
            raise ValueError("aggregate attempted stake exceeds daily cap")

        single = audit_synthetic_fill_price_bounds({
            "synthetic_only": True,
            "max_race_stake_yen": race_cap,
            "max_day_stake_yen": day_cap,
            **{
                field: item[field]
                for field in _ATTEMPT_FIELDS - {"attempt_id", "race_id"}
            },
        })
        attempt_ev = Decimal(single["net_ev_yen_per_attempt"])
        fraction = Decimal(item["fill_fraction"])
        hypothetical_ev += attempt_ev
        assumed_filled_stake += Decimal(stake) * fraction
        if min_attempt_net_ev is None or attempt_ev < min_attempt_net_ev:
            min_attempt_net_ev = attempt_ev

    return {
        "status": "synthetic_daily_budget_diagnostic_only",
        "attempt_count": len(attempts),
        "synthetic_race_count": len(reserved_by_race),
        "max_day_stake_yen": day_cap,
        "max_race_stake_yen": race_cap,
        "worst_case_all_attempts_fill_exposure_yen": all_reserved,
        "remaining_uncommitted_daily_budget_yen": day_cap - all_reserved,
        "peak_single_race_reserved_yen": max(reserved_by_race.values()),
        "assumed_filled_stake_yen": str(assumed_filled_stake),
        "hypothetical_net_ev_yen_per_attempt_set": str(hypothetical_ev),
        "minimum_hypothetical_per_attempt_net_ev_yen": str(min_attempt_net_ev),
        "synthetic_aggregate_reservation_passed": True,
        "full_stakes_reserved_not_fill_weighted": True,
        "cross_ticket_outcome_dependence_verified": False,
        "fill_fraction_empirically_verified": False,
        "daily_aggregate_cap_verified": False,
        "eligible_opportunity_coverage_verified": False,
        "quote_rights_verified": False,
        "purchase_price_verified": False,
        "calibration_verified": False,
        "formal_confidence_interval": False,
        "positive_executable_ev_proven": False,
        "paper_or_live_action_authorized": False,
        "protected_holdout_used": False,
        "limitations": (
            "Hypothetical selected attempts only; actual available "
            "opportunities, filling, returns, odds rights and correlated "
            "ticket outcomes remain unverified. No executable positive-EV "
            "claim or staking authorization."
        ),
    }
