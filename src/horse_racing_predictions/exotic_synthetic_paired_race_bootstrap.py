"""Synthetic-only paired race-level market comparison, never an EV approval.

No network, files, real outcomes, quotes, credentials or broker integration.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from random import Random
from typing import Any, Mapping
import re

_FIELDS = frozenset({
    "synthetic_only", "source_kind", "race_id", "race_date", "reference_budget_yen",
    "strategy_stake_yen", "strategy_gross_return_yen", "strategy_fees_yen",
    "market_stake_yen", "market_gross_return_yen", "market_fees_yen",
})


def _checked_yen(value: Any, label: str) -> int:
    if type(value) is not int or not 0 <= value <= 100_000_000:
        raise ValueError(f"invalid {label}")
    return value


def audit_synthetic_paired_race_bootstrap(
    rows: list[Mapping[str, Any]], *, seed: int = 0, resamples: int = 1000
) -> dict[str, Any]:
    """Bootstrap paired net-return differences at the race, not ticket, level."""
    result: dict[str, Any] = {
        "status": "blocked", "blockers": [], "positive_executable_ev_proven": False,
        "quote_rights_verified": False, "purchase_time_price_verified": False,
        "calibration_verified": False, "forward_paper_verified": False,
        "approved_for_paper_or_live": False, "protected_holdout_used": False,
    }
    try:
        if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
            raise ValueError("invalid seed")
        if type(resamples) is not int or not 200 <= resamples <= 2000:
            raise ValueError("invalid resample count")
        if type(rows) is not list or not 30 <= len(rows) <= 2000:
            raise ValueError("30..2000 synthetic race rows required")
        seen: set[str] = set()
        previous: date | None = None
        paired: list[Decimal] = []
        for row in rows:
            if not isinstance(row, Mapping) or set(row) != _FIELDS:
                raise ValueError("invalid fields")
            if row["synthetic_only"] is not True or row["source_kind"] != "synthetic_fixture":
                raise ValueError("non-synthetic provenance")
            race_id = row["race_id"]
            if (type(race_id) is not str or not re.fullmatch(r"SYN-[0-9]{4}", race_id)
                    or race_id in seen):
                raise ValueError("invalid or duplicate synthetic race id")
            seen.add(race_id)
            raw_date = row["race_date"]
            if type(raw_date) is not str or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw_date):
                raise ValueError("invalid synthetic date")
            race_date = date.fromisoformat(raw_date)
            if not date(2017, 1, 1) <= race_date <= date(2024, 12, 31):
                raise ValueError("protected or out-of-window date")
            if previous is not None and race_date < previous:
                raise ValueError("race rows must be chronological")
            previous = race_date
            budget = _checked_yen(row["reference_budget_yen"], "budget")
            if not 100 <= budget <= 10_000_000 or budget % 100:
                raise ValueError("invalid reference budget")
            net = []
            for prefix in ("strategy", "market"):
                stake = _checked_yen(row[f"{prefix}_stake_yen"], "stake")
                gross = _checked_yen(row[f"{prefix}_gross_return_yen"], "gross")
                fee = _checked_yen(row[f"{prefix}_fees_yen"], "fee")
                if stake > budget or stake % 100 or (stake == 0 and gross):
                    raise ValueError("invalid synthetic stake/return")
                net.append(gross - stake - fee)
            paired.append(Decimal(net[0] - net[1]) / Decimal(budget))
        count = len(paired)
        observed = sum(paired, Decimal(0)) / Decimal(count)
        rng = Random(seed)
        draws = sorted(sum((paired[rng.randrange(count)] for _ in range(count)), Decimal(0))
                       / Decimal(count) for _ in range(resamples))
        result.update({
            "status": "synthetic_diagnostic_only", "race_count": count,
            "paired_net_advantage_per_reference_yen": str(observed),
            "synthetic_race_bootstrap_95pct_lower": str(draws[resamples // 40]),
            "synthetic_race_bootstrap_95pct_upper": str(draws[min(resamples - 1, resamples * 39 // 40)]),
            "bootstrap_seed": seed, "bootstrap_resamples": resamples,
            "limitations": "Synthetic fixtures only; no executable odds, fill, rights, calibration or forward EV proof.",
        })
    except (ValueError, TypeError, OverflowError) as exc:
        result["blockers"].append(str(exc))
    return result
