"""Research-only conservative EV arithmetic for hypothetical exotic quotes.

A positive calculated EV is NOT evidence of executable positive EV:
provider rights, odds-at-purchase, uncertainty coverage, and costs are
unverified. This module cannot authorize acquisition, paper/live staking,
or change the existing Champion. No network or outcome data are used.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from .exotic_prebet_execution_triage import triage_exotic_prebet_execution
from .exotic_prebet_odds_contract import _combination, _instant


_PREDICTION_FIELDS = frozenset({
    "race_id", "bet_type", "horse_numbers", "point_probability",
    "lower_confidence_probability", "estimated_at", "model_frozen_at",
    "model_sha256", "calibration_report_sha256", "confidence_method",
    "confidence_level", "validation_period_end", "validation_races",
})
_ECONOMICS_FIELDS = frozenset({
    "stake_yen", "odds_haircut_fraction", "per_ticket_cost_yen",
})


def _decimal_string(value: Any, name: str, *, minimum: Decimal | None = None,
                    maximum: Decimal | None = None) -> Decimal:
    # Strings avoid lossy binary float conversion and reject bool/NaN/Inf.
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a decimal string")
    try:
        result = Decimal(value.strip())
    except InvalidOperation as exc:
        raise ValueError(f"{name} must be a decimal string") from exc
    if not result.is_finite() or (
        minimum is not None and result < minimum
    ) or (maximum is not None and result > maximum):
        raise ValueError(f"{name} is out of bounds")
    return result


def _digest(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(
        char not in "0123456789abcdef"
        for char in value.lower()
    ):
        raise ValueError(f"{name} must be a SHA-256 hex digest")
    return value.lower()


def _prediction_check(
    quote: Mapping[str, Any], prediction: Mapping[str, Any], decision_at: str
) -> tuple[Decimal, Decimal]:
    if not isinstance(quote, Mapping):
        raise ValueError("quote must be a mapping")
    if not isinstance(prediction, Mapping) or set(prediction) != _PREDICTION_FIELDS:
        raise ValueError("prediction evidence fields are missing or unexpected")
    if prediction["race_id"] != quote.get("race_id"):
        raise ValueError("prediction and quote race mismatch")
    kind = prediction["bet_type"]
    if kind not in ("trio", "trifecta") or kind != quote.get("bet_type"):
        raise ValueError("prediction and quote bet type mismatch")
    combination = _combination(prediction["horse_numbers"], kind)
    if combination != _combination(quote.get("horse_numbers"), kind):
        raise ValueError("prediction and quote combination mismatch")
    point = _decimal_string(
        prediction["point_probability"], "point_probability",
        minimum=Decimal("0"), maximum=Decimal("1"),
    )
    lower = _decimal_string(
        prediction["lower_confidence_probability"],
        "lower_confidence_probability",
        minimum=Decimal("0"), maximum=Decimal("1"),
    )
    if not Decimal("0") < point < Decimal("1") or not Decimal("0") <= lower <= point:
        raise ValueError("invalid probability interval")
    decision = _instant(decision_at)
    estimated = _instant(prediction["estimated_at"])
    frozen = _instant(prediction["model_frozen_at"])
    if not frozen <= estimated <= decision:
        raise ValueError("model must be frozen before estimate and decision")
    _digest(prediction["model_sha256"], "model_sha256")
    _digest(prediction["calibration_report_sha256"], "calibration_report_sha256")
    if prediction["confidence_method"] != "race_cluster_bootstrap":
        raise ValueError("confidence interval must use race-cluster bootstrap")
    if prediction["confidence_level"] != "0.95":
        raise ValueError("confidence level must be the preregistered 0.95")
    if type(prediction["validation_races"]) is not int or prediction["validation_races"] < 30:
        raise ValueError("at least 30 held-out validation races are required")
    try:
        end = date.fromisoformat(prediction["validation_period_end"])
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid validation_period_end") from exc
    if not date(2017, 1, 1) <= end <= date(2024, 12, 31):
        raise ValueError("2025-2026 final holdout is forbidden")
    if not end < frozen.date():
        raise ValueError("validation period must end before model is frozen")
    return point, lower


def audit_conservative_exotic_ev(
    quote: Mapping[str, Any],
    source_evidence: Mapping[str, Any],
    prediction: Mapping[str, Any],
    economics: Mapping[str, Any],
    *,
    decision_at: str,
    purchase_cutoff_at: str,
) -> dict[str, Any]:
    """Produce bounded arithmetic diagnostics, never a trade authorization.

    Assumptions:
      estimated per-unit RETURN factor: displayed decimal quote after a
      hypothetical downward haircut for pre-purchase price movement.
      net EV/stake = P(combination)*adjusted_return_factor - 1
                      - flat_cost_yen/stake_yen.
    Winning return includes the original stake. Fixed fees are subtracted on
    every hypothetical wager. This is **not** a tested guarantee that the
    haircut bounds actual dynamic tote odds.
    """
    triage = triage_exotic_prebet_execution(
        quote, source_evidence,
        decision_at=decision_at,
        purchase_cutoff_at=purchase_cutoff_at,
    )
    blockers = list(triage["blockers"])
    point = lower = None
    try:
        point, lower = _prediction_check(quote, prediction, decision_at)
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        blockers.append(f"prediction: {exc}")
    stake = cost = haircut = None
    try:
        if not isinstance(economics, Mapping) or set(economics) != _ECONOMICS_FIELDS:
            raise ValueError("economics fields are missing or unexpected")
        stake = economics["stake_yen"]
        if type(stake) is not int or stake < 100 or stake % 100:
            raise ValueError("stake must be a positive multiple of 100 yen")
        haircut = _decimal_string(
            economics["odds_haircut_fraction"],
            "odds_haircut_fraction",
            minimum=Decimal("0"), maximum=Decimal("1"),
        )
        if not Decimal("0") < haircut < Decimal("1"):
            raise ValueError("a strictly positive sub-100% odds haircut is required")
        cost = _decimal_string(
            economics["per_ticket_cost_yen"],
            "per_ticket_cost_yen", minimum=Decimal("0"),
        )
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        blockers.append(f"economics: {exc}")

    base = {
        "status": "blocked" if blockers else "research_review_required",
        "blockers": blockers,
        "canonical_combination_key": (
            triage.get("canonical_combination_key") if not blockers else None
        ),
        "approved_for_acquisition": False,
        "approved_for_ev": False,
        "approved_for_paper_staking": False,
        "approved_for_live_staking": False,
        "positive_ev_proven": False,
        "protected_holdout": "2025-2026 untouched",
        "assumption_note": (
            "The odds haircut is a hypothetical price-stress scenario, "
            "NOT a guaranteed executable quote. Submitted source rights, "
            "model calibration and confidence coverage are unverified."
        ),
    }
    if blockers:
        return base

    try:
        odds = _decimal_string(quote["decimal_odds"], "decimal_odds",
                               minimum=Decimal("1.00000000000001"))
        adjusted = odds * (Decimal("1") - haircut)
        fee_per_yen = cost / Decimal(stake)
        net_point = point * adjusted - Decimal("1") - fee_per_yen
        net_lower = lower * adjusted - Decimal("1") - fee_per_yen
        breakeven = (Decimal("1") + fee_per_yen) / adjusted
        if not all(v.is_finite() for v in (adjusted, net_point, net_lower, breakeven)):
            raise ValueError("nonfinite EV arithmetic")
    except (ValueError, InvalidOperation, OverflowError, ZeroDivisionError) as exc:
        base["status"] = "blocked"
        base["blockers"].append(f"arithmetic: {exc}")
        base["canonical_combination_key"] = None
        return base

    base.update({
        "displayed_decimal_odds": str(odds),
        "hypothetically_haircut_return_multiple": str(adjusted),
        "breakeven_probability_under_assumptions": str(breakeven),
        "point_ev_yen_per_stake_yen": str(net_point),
        "lower_bound_ev_yen_per_stake_yen": str(net_lower),
        "lower_bound_ev_yen_per_ticket": str(net_lower * Decimal(stake)),
        "positive_point_ev_under_assumptions": net_point > 0,
        "positive_lower_bound_ev_under_assumptions": net_lower > 0,
        "claim_note": (
            "Positive arithmetic under unverified assumptions does NOT "
            "demonstrate positive realizable EV or authorize paper/live orders."
        ),
    })
    return base
