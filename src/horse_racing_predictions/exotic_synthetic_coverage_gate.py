"""Synthetic-only manifest-to-evaluation coverage and timing integrity audit.

Every eligible fictional opportunity MUST occur exactly once in the analysis,
including missing/stale quotes, unknown cutoffs, abstentions and unfilled
attempts. Both the strategy and frozen market comparator reserve full attempted
capital independently. No data acquisition, order placement or betting rights.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
import re
from typing import Any, Mapping

from .exotic_prebet_odds_contract import _instant

_IDENTIFIER = re.compile(r"S[0-9]{1,5}\Z")
_DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_FIELDS = frozenset({
    "synthetic_only", "max_race_stake_yen", "max_day_stake_yen",
    "max_quote_age_seconds", "opportunities", "evaluated",
})
_OPPORTUNITY = frozenset({
    "race_id", "race_date", "quote_status", "observed_at", "captured_at",
    "decision_at", "purchase_cutoff_at", "scheduled_post_at",
})
_EVALUATED = frozenset({
    "race_id", "strategy_status", "market_status",
    "strategy_attempted_stake_yen", "market_attempted_stake_yen",
})
_STATUSES = frozenset({"ready", "missing", "stale", "cutoff_unknown"})
_EXECUTION = frozenset({"filled", "unfilled", "abstained"})


def _stake(value: Any, *, allow_zero: bool) -> int:
    if type(value) is not int or not 0 <= value <= 10_000_000 or value % 100:
        raise ValueError("stake must be a bounded 100-yen integer")
    if not allow_zero and value == 0:
        raise ValueError("attempted stake must be positive")
    return value


def _synthetic_id(value: Any) -> str:
    if type(value) is not str or not _IDENT.fullmatch(value):
        raise ValueError("synthetic S-number race ID required")
    return value


def audit_synthetic_coverage_gate(case: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed on selective exclusion, temporal defects and capital risk."""
    if not isinstance(case, Mapping) or set(case) != _FIELDS:
        raise ValueError("unexpected or missing coverage fields")
    if case["synthetic_only"] is not True:
        raise ValueError("synthetic-only protocol is required")
    race_cap = _stake(case["max_race_stake_yen"], allow_zero=False)
    day_cap = _stake(case["max_day_stake_yen"], allow_zero=False)
    if race_cap > day_cap:
        raise ValueError("race capital cap exceeds day cap")
    max_age = case["max_quote_age_seconds"]
    if type(max_age) is not int or not 1 <= max_age <= 3600:
        raise ValueError("bounded quote age required")
    manifest, evaluated = case["opportunities"], case["evaluated"]
    if (
        type(manifest) is not list or type(evaluated) is not list
        or not 1 <= len(manifest) <= 2000 or len(manifest) != len(evaluated)
    ):
        raise ValueError("exact one-to-one eligible opportunity count required")

    original: dict[str, dict[str, Any]] = {}
    for item in manifest:
        if not isinstance(item, Mapping) or set(item) != _OPPORTUNITY:
            raise ValueError("invalid synthetic opportunity fields")
        rid = _synthetic_id(item["race_id"])
        if rid in original:
            raise ValueError("duplicate manifest race")
        raw_day = item["race_date"]
        if type(raw_day) is not str or not _DAY.fullmatch(raw_day):
            raise ValueError("canonical synthetic race date required")
        try:
            race_day = date.fromisoformat(raw_day)
        except ValueError as exc:
            raise ValueError("invalid synthetic race date") from exc
        if not date(2023, 1, 1) <= race_day <= date(2024, 12, 31):
            raise ValueError("protected holdout or unsupported race date")
        status = item["quote_status"]
        if status not in _STATUSES:
            raise ValueError("unknown quote evidence status")

        decision = _instant(item["decision_at"])
        post = _instant(item["scheduled_post_at"])
        if not decision < post or post.year > 2024 or decision.year < 2023:
            raise ValueError("decision/post timeline outside development period")
        if post.date() != race_day:
            raise ValueError("race date must match canonical UTC post date")
        observed_raw, captured_raw, cutoff_raw = (
            item["observed_at"], item["captured_at"],
            item["purchase_cutoff_at"],
        )
        if status == "missing":
            if any(value is not None for value in (
                observed_raw, captured_raw, cutoff_raw,
            )):
                raise ValueError("missing quote cannot fabricate evidence")
        else:
            observed = _instant(observed_raw)
            captured = _instant(captured_raw)
            if not observed <= captured <= decision:
                raise ValueError("quote observed/captured after decision")
            age = decision - observed
            if status == "cutoff_unknown":
                if cutoff_raw is not None:
                    raise ValueError("unknown cutoff must stay explicitly unknown")
            else:
                cutoff = _instant(cutoff_raw)
                if not decision < cutoff < post:
                    raise ValueError("purchase cutoff outside decision window")
                if status == "ready" and age > timedelta(seconds=max_age):
                    raise ValueError("ready quote exceeds freshness bound")
                if status == "stale" and age <= timedelta(seconds=max_age):
                    raise ValueError("stale quote cannot hide a fresh quote")
        original[rid] = {
            "date": race_day, "status": status,
        }

    encountered: set[str] = set()
    exposure: dict[str, dict[date, int]] = {
        "strategy": defaultdict(int), "market": defaultdict(int),
    }
    summary = {
        prefix: {"filled": 0, "unfilled": 0, "abstained": 0}
        for prefix in ("strategy", "market")
    }
    for row in evaluated:
        if not isinstance(row, Mapping) or set(row) != _EVALUATED:
            raise ValueError("invalid synthetic evaluation fields")
        rid = _synthetic_id(row["race_id"])
        if rid in encountered or rid not in original:
            raise ValueError("duplicate or unlisted evaluated race")
        encountered.add(rid)
        for prefix in ("strategy", "market"):
            action = row[f"{prefix}_status"]
            if action not in _EXECUTION:
                raise ValueError("unknown synthetic execution status")
            stake = _stake(
                row[f"{prefix}_attempted_stake_yen"],
                allow_zero=(action == "abstained"),
            )
            if action == "abstained" and stake != 0:
                raise ValueError("abstained strategy/market requires zero stake")
            if original[rid]["status"] != "ready" and action != "abstained":
                raise ValueError("unavailable quote cannot authorize an attempt")
            if stake > race_cap:
                raise ValueError("independent race capital cap exceeded")
            day = original[rid]["date"]
            exposure[prefix][day] += stake
            if exposure[prefix][day] > day_cap:
                raise ValueError("independent day capital cap exceeded")
            summary[prefix][action] += 1

    if set(original) != encountered:
        raise ValueError("missing eligible race from evaluation")

    return {
        "status": "synthetic_coverage_diagnostic_only",
        "eligible_opportunity_count": len(original),
        "evaluated_opportunity_count": len(encountered),
        "quote_ready_count": sum(x["status"] == "ready" for x in original.values()),
        "missing_quote_count": sum(x["status"] == "missing" for x in original.values()),
        "stale_quote_count": sum(x["status"] == "stale" for x in original.values()),
        "unknown_cutoff_count": sum(x["status"] == "cutoff_unknown" for x in original.values()),
        "strategy_execution_counts": summary["strategy"],
        "market_execution_counts": summary["market"],
        "strategy_worst_case_reserved_yen": sum(exposure["strategy"].values()),
        "market_worst_case_reserved_yen": sum(exposure["market"].values()),
        "complete_synthetic_opportunity_coverage": True,
        "independent_strategy_market_caps_passed": True,
        "actual_quote_capture_or_rights_verified": False,
        "actual_eligible_opportunity_coverage_verified": False,
        "positive_executable_ev_proven": False,
        "paper_or_live_action_authorized": False,
        "protected_holdout_used": False,
    }
