"""Synthetic-only strict chronological research-split audit.

Provides an *isolated guard*, not a live data gateway or a real evaluation.
Train dates are bounded to 2017-2022, development evaluation to 2023-2024,
and at least 7 full calendar days must separate the periods.
"""
from __future__ import annotations

from datetime import date
import re
from typing import Any, Mapping

_IDENT = re.compile(r"S[0-9]{1,5}\Z")
_DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_KEYS = frozenset({"synthetic_only", "embargo_days", "train", "evaluation"})
_ROW_KEYS = frozenset({"race_id", "race_date"})


def _rows(value: Any, name: str, lower: date, upper: date) -> tuple[list[date], set[str]]:
    if type(value) is not list or not 1 <= len(value) <= 5000:
        raise ValueError(f"{name}: nonempty bounded synthetic rows required")
    days: list[date] = []
    ids: set[str] = set()
    for row in value:
        if not isinstance(row, Mapping) or set(row) != _ROW_KEYS:
            raise ValueError(f"{name}: invalid row fields")
        race = row["race_id"]
        raw = row["race_date"]
        if type(race) is not str or not _IDENT.fullmatch(race):
            raise ValueError(f"{name}: synthetic race ID required")
        if race in ids:
            raise ValueError(f"{name}: duplicated synthetic race")
        if type(raw) is not str or not _DAY.fullmatch(raw):
            raise ValueError(f"{name}: canonical calendar date required")
        try:
            parsed = date.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError(f"{name}: impossible calendar date") from exc
        if not lower <= parsed <= upper:
            raise ValueError(f"{name}: date outside frozen pre-holdout period")
        days.append(parsed)
        ids.add(race)
    return days, ids


def audit_synthetic_oos_protocol(case: Mapping[str, Any]) -> dict[str, Any]:
    """Reject overlapping or contaminated development splits before modelling."""
    if not isinstance(case, Mapping) or set(case) != _KEYS:
        raise ValueError("unexpected OOS protocol fields")
    if case["synthetic_only"] is not True:
        raise ValueError("synthetic-only input required")
    embargo = case["embargo_days"]
    if type(embargo) is not int or embargo < 7 or embargo > 366:
        raise ValueError("at least seven bounded calendar embargo days required")

    training_days, training_ids = _rows(
        case["train"], "train", date(2017, 1, 1), date(2022, 12, 31),
    )
    evaluation_days, evaluation_ids = _rows(
        case["evaluation"], "evaluation", date(2023, 1, 1), date(2024, 12, 31),
    )
    if training_ids & evaluation_ids:
        raise ValueError("race identity appears in both train and evaluation")
    gap = (min(evaluation_days) - max(training_days)).days - 1
    if gap < embargo:
        raise ValueError("insufficient strict chronological embargo")

    return {
        "status": "synthetic_oos_protocol_check_only",
        "training_races": len(training_ids),
        "evaluation_races": len(evaluation_ids),
        "actual_gap_full_days": gap,
        "required_embargo_days": embargo,
        "no_race_identity_overlap": True,
        "train_through_date": max(training_days).isoformat(),
        "development_starts_date": min(evaluation_days).isoformat(),
        "protected_holdout": "2025-2026 untouched",
        "historical_provider_data_read": False,
        "real_oos_verified": False,
        "economic_return_verified": False,
        "positive_executable_ev_proven": False,
        "paper_or_live_action_authorized": False,
    }
