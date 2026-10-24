"""Synthetic-only probabilistic correctness checks; no JV provider/EV calls."""
from itertools import combinations, permutations
from math import isclose

import pytest

from horse_racing_predictions.exotic_combination_probability import (
    ordered_trifecta_probability,
    synthetic_combination_probability_audit,
    unordered_trio_probability,
)


def test_three_horses_have_certain_unordered_trio_and_six_equal_orders():
    weights = {1: 1.0, 2: 1.0, 3: 1.0}
    assert isclose(unordered_trio_probability(weights, (1, 2, 3)), 1.0)
    assert isclose(ordered_trifecta_probability(weights, (1, 2, 3)), 1 / 6)
    assert isclose(ordered_trifecta_probability(weights, (3, 2, 1)), 1 / 6)
    audit = synthetic_combination_probability_audit(weights)
    assert audit["mass_normalized"]
    assert audit["trio_combinations"] == 1
    assert audit["trifecta_combinations"] == 6


def test_four_equal_horses_have_four_trios_and_24_trifectas():
    weights = {i: 1.0 for i in range(1, 5)}
    assert isclose(unordered_trio_probability(weights, (3, 2, 1)), 0.25)
    assert isclose(ordered_trifecta_probability(weights, (1, 2, 3)), 1 / 24)
    audit = synthetic_combination_probability_audit(weights)
    assert audit["trio_combinations"] == 4
    assert audit["trifecta_combinations"] == 24
    assert audit["mass_normalized"]
    assert audit["real_race_calibrated"] is False
    assert audit["expected_value_computed"] is False
    assert audit["ticket_generation_authorized"] is False


def test_unordered_trio_equals_sum_of_six_exact_permutations():
    weights = {1: 7.0, 2: 4.0, 3: 2.0, 4: 1.0, 5: 0.5}
    chosen = (5, 1, 2)
    sum_orders = sum(
        ordered_trifecta_probability(weights, order)
        for order in permutations(chosen)
    )
    assert isclose(unordered_trio_probability(weights, chosen), sum_orders)
    assert isclose(unordered_trio_probability(weights, (1, 2, 5)), sum_orders)
    assert (
        ordered_trifecta_probability(weights, (1, 2, 5))
        > ordered_trifecta_probability(weights, (5, 2, 1))
    )


@pytest.mark.parametrize("field", [3, 4, 6, 12, 18])
def test_full_distribution_sums_to_one_for_up_to_18_runners(field):
    weights = {i: float(i ** 2) for i in range(1, field + 1)}
    audit = synthetic_combination_probability_audit(weights)
    assert audit["mass_normalized"]
    assert isclose(audit["trio_probability_mass"], 1, abs_tol=1e-12)
    assert isclose(audit["trifecta_probability_mass"], 1, abs_tol=1e-12)
    assert audit["trifecta_combinations"] == 6 * audit["trio_combinations"]
    assert not audit["pre_purchase_odds_verified"]
    assert not audit["holdout_2025_2026_used"]


def test_scale_invariance_of_strength_weights():
    p = {1: 0.1, 2: 0.2, 3: 0.5, 4: 0.7}
    scaled = {k: v * 10000 for k, v in p.items()}
    assert isclose(
        ordered_trifecta_probability(p, (4, 3, 1)),
        ordered_trifecta_probability(scaled, (4, 3, 1)),
        abs_tol=1e-12,
    )
    assert isclose(
        unordered_trio_probability(p, (3, 1, 4)),
        unordered_trio_probability(scaled, (3, 1, 4)),
        abs_tol=1e-12,
    )


@pytest.mark.parametrize("weights", [
    {1: 1.0, 2: 0.0, 3: 1.0},
    {1: 1.0, 2: -2.0, 3: 1.0},
    {1: 1.0, 2: float("nan"), 3: 1.0},
    {1: 1.0, 2: float("inf"), 3: 1.0},
    {1: 1.0, 2: True, 3: 1.0},
    {1: 1.0, 2: "0.1", 3: 1.0},
    {1: 1.0, 2: 1.0},
    {1: 1.0, 2: 1.0, 19: 1.0},
    {False: 1.0, 2: 1.0, 3: 1.0},
    {1: 1e-320, 2: 1e308, 3: 1.0},
])
def test_invalid_weights_are_rejected_before_audit(weights):
    with pytest.raises(ValueError):
        synthetic_combination_probability_audit(weights)


@pytest.mark.parametrize("triple", [
    (1, 1, 3), (1, 2, 4), (1, 2), (1, True, 3),
    [1, 2, 3], (1, 2, 3, 4),
])
def test_invalid_ordered_combination_is_rejected(triple):
    with pytest.raises(ValueError):
        ordered_trifecta_probability({1: 3, 2: 2, 3: 1}, triple)


def test_no_model_or_real_odds_are_needed_for_math():
    # This is purely a mathematical identity and cannot establish
    # positive EV or authorize any real/paper wagering.
    audit = synthetic_combination_probability_audit(
        {1: 10, 2: 4, 3: 3, 4: 1}
    )
    assert audit["expected_value_computed"] is False
    assert audit["real_race_calibrated"] is False
    assert audit["ticket_generation_authorized"] is False
