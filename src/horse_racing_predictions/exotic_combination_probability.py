"""Synthetic-only ordered and unordered top-three probability identities.

This is a Plackett-Luce mathematical *hypothesis*, NOT a fitted or validated
race model. Input must be strictly positive hypothetical WIN strengths, never
Top-3 probabilities, post-race odds, payouts, or a JRA-VAN provider response.
No quote access, decision making, ROI, staking, or ticket generation.
"""
from __future__ import annotations

from itertools import combinations, permutations
from math import fsum, isfinite
from typing import Mapping


def _strict_win_strengths(strengths: Mapping[int, float]) -> dict[int, float]:
    if not isinstance(strengths, Mapping):
        raise ValueError("win strengths must be an ID-to-weight mapping")
    if not 3 <= len(strengths) <= 18:
        raise ValueError("top-three probabilities require 3..18 horses")
    values: dict[int, float] = {}
    for horse, strength in strengths.items():
        if type(horse) is not int or not 1 <= horse <= 18:
            raise ValueError("horse numbers must be integers 1..18")
        if type(strength) not in (int, float):
            raise ValueError("win strength must be a positive numeric scalar")
        value = float(strength)
        if not isfinite(value) or value <= 0.0:
            raise ValueError("win strengths must be finite and positive")
        values[horse] = value

    # Scale before summation to avoid overflow and improve numerical stability.
    maximum = max(values.values())
    scaled = {horse: weight / maximum for horse, weight in values.items()}
    # Reject extreme ratios that underflow to zero in double precision. These
    # inputs cannot produce a trustworthy complete full-race distribution.
    if not all(v > 0.0 for v in scaled.values()):
        raise ValueError("win strength dynamic range underflows")
    return scaled


def _ordered_probability(
    scaled: Mapping[int, float],
    first: int,
    second: int,
    third: int,
) -> float:
    remaining = dict(scaled)
    result = 1.0
    for horse in (first, second, third):
        # Re-sum the remaining weights to avoid catastrophic subtraction.
        denominator = fsum(remaining.values())
        score = remaining.pop(horse)
        result *= score / denominator
    return result


def _validate_triple(
    scaled: Mapping[int, float],
    triple: tuple[int, ...],
) -> tuple[int, int, int]:
    if not isinstance(triple, tuple) or len(triple) != 3:
        raise ValueError("exactly three horse numbers required")
    if any(type(n) is not int or n not in scaled for n in triple):
        raise ValueError("triple contains unknown horse number")
    if len(set(triple)) != 3:
        raise ValueError("triple members must be distinct")
    return triple


def ordered_trifecta_probability(
    win_strengths: Mapping[int, float],
    ordered_horses: tuple[int, int, int],
) -> float:
    """P(exact 1st, 2nd, 3rd), conditional on hypothetical win strengths."""
    scaled = _strict_win_strengths(win_strengths)
    triple = _validate_triple(scaled, ordered_horses)
    return _ordered_probability(scaled, *triple)


def unordered_trio_probability(
    win_strengths: Mapping[int, float],
    horses: tuple[int, int, int],
) -> float:
    """P(these three fill the top 3 in ANY order) under Plackett-Luce."""
    scaled = _strict_win_strengths(win_strengths)
    triple = _validate_triple(scaled, horses)
    return fsum(
        _ordered_probability(scaled, *order)
        for order in permutations(triple)
    )


def synthetic_combination_probability_audit(
    win_strengths: Mapping[int, float],
) -> dict:
    """Check full probability mass and return no odds/EV/betting decisions.

    Only caller-supplied hypothetical *winner strengths* may enter. This audit
    does not imply that Plackett-Luce fits real racing outcomes; the assumption
    needs separately approved pre-2025 data, temporal calibration and testing.
    """
    scaled = _strict_win_strengths(win_strengths)
    horses = tuple(sorted(scaled))
    trio_mass = fsum(
        fsum(
            _ordered_probability(scaled, *order)
            for order in permutations(triple)
        )
        for triple in combinations(horses, 3)
    )
    trifecta_mass = fsum(
        _ordered_probability(scaled, *order)
        for order in permutations(horses, 3)
    )
    return {
        "status": "synthetic_probability_identity_only",
        "hypothesis": "Plackett-Luce sequential without-replacement finish order",
        "score_semantics": "hypothetical positive win strengths only",
        "runners": len(horses),
        "trio_combinations": len(horses) * (len(horses) - 1)
        * (len(horses) - 2) // 6,
        "trifecta_combinations": len(horses) * (len(horses) - 1)
        * (len(horses) - 2),
        "trio_probability_mass": trio_mass,
        "trifecta_probability_mass": trifecta_mass,
        "mass_normalized": (
            abs(trio_mass - 1.0) <= 1e-10
            and abs(trifecta_mass - 1.0) <= 1e-10
        ),
        "real_race_calibrated": False,
        "pre_purchase_odds_verified": False,
        "expected_value_computed": False,
        "ticket_generation_authorized": False,
        "holdout_2025_2026_used": False,
    }
