"""Full-stake synthetic daily budget: no real quotes, tickets or data."""
from decimal import Decimal

import pytest

from horse_racing_predictions.exotic_synthetic_daily_budget import (
    audit_synthetic_daily_budget,
)


def attempt(id="T1", race="S1", **changes):
    result = {
        "attempt_id": id,
        "race_id": race,
        "stake_yen": 100,
        "conditional_win_probability_lower": "0.15",
        "displayed_decimal_odds": "10",
        "payout_haircut": "0.20",
        "fill_fraction": "0.5",
        "fee_per_fill_yen": "10",
        "fee_per_attempt_yen": "5",
    }
    result.update(changes)
    return result


def day(attempts=None, **changes):
    result = {
        "synthetic_only": True,
        "max_race_stake_yen": 200,
        "max_day_stake_yen": 300,
        "attempts": (
            [attempt("T1", "S1"), attempt("T2", "S1"),
             attempt("T3", "S2")]
            if attempts is None else attempts
        ),
    }
    result.update(changes)
    return result


def test_all_fill_reservation_counts_all_attempts_not_expected_fill():
    out = audit_synthetic_daily_budget(day())
    assert out["status"] == "synthetic_daily_budget_diagnostic_only"
    assert out["attempt_count"] == 3
    assert out["synthetic_race_count"] == 2
    assert out["worst_case_all_attempts_fill_exposure_yen"] == 300
    assert out["peak_single_race_reserved_yen"] == 200
    assert out["remaining_uncommitted_daily_budget_yen"] == 0
    assert out["assumed_filled_stake_yen"] == "150.0"
    # Each individual hypothetical attempt is break-even (including fees).
    assert Decimal(out["hypothetical_net_ev_yen_per_attempt_set"]) == 0
    assert out["synthetic_aggregate_reservation_passed"] is True
    assert out["full_stakes_reserved_not_fill_weighted"] is True
    assert out["positive_executable_ev_proven"] is False
    assert out["paper_or_live_action_authorized"] is False
    assert out["daily_aggregate_cap_verified"] is False
    assert out["eligible_opportunity_coverage_verified"] is False


def test_zero_fill_cannot_hide_three_full_stake_reservations():
    attempts = [
        attempt("T1", "S1", fill_fraction="0"),
        attempt("T2", "S1", fill_fraction="0"),
        attempt("T3", "S2", fill_fraction="0"),
    ]
    out = audit_synthetic_daily_budget(day(attempts))
    assert out["worst_case_all_attempts_fill_exposure_yen"] == 300
    assert Decimal(out["assumed_filled_stake_yen"]) == 0
    assert Decimal(out["hypothetical_net_ev_yen_per_attempt_set"]) == -15


def test_oversubscribed_same_race_is_rejected_even_when_fill_is_zero():
    attempts = [
        attempt("T1", "S1", fill_fraction="0"),
        attempt("T2", "S1", fill_fraction="0"),
        attempt("T3", "S1", fill_fraction="0"),
    ]
    with pytest.raises(ValueError, match="same-race"):
        audit_synthetic_daily_budget(day(attempts))


def test_cross_race_daily_oversubscription_is_rejected():
    attempts = [
        attempt("T1", "S1"),
        attempt("T2", "S1"),
        attempt("T3", "S2"),
        attempt("T4", "S2"),
    ]
    with pytest.raises(ValueError, match="daily cap"):
        audit_synthetic_daily_budget(day(attempts))


def test_positive_synthetic_ev_does_not_override_oversubscription():
    items = [
        attempt("T1", "S1", conditional_win_probability_lower="0.99"),
        attempt("T2", "S1", conditional_win_probability_lower="0.99"),
        attempt("T3", "S2", conditional_win_probability_lower="0.99"),
        attempt("T4", "S2", conditional_win_probability_lower="0.99"),
    ]
    with pytest.raises(ValueError, match="daily cap"):
        audit_synthetic_daily_budget(day(items))


def test_two_race_individual_limit_also_blocks_large_ticket():
    with pytest.raises(ValueError, match="race cap"):
        audit_synthetic_daily_budget(day(
            [attempt("T1", "S1", stake_yen=300)],
            max_day_stake_yen=500,
        ))


def test_fees_aggregate_even_when_fill_fraction_zero():
    items = [
        attempt("T1", "S1", fill_fraction="0", fee_per_attempt_yen="3"),
        attempt("T2", "S2", fill_fraction="1",
                fee_per_attempt_yen="3", fee_per_fill_yen="0"),
    ]
    out = audit_synthetic_daily_budget(day(items))
    # Second ticket: 100 * (0.15*8 - 1) - 3 = 17; first = -3
    assert Decimal(out["hypothetical_net_ev_yen_per_attempt_set"]) == 14
    assert Decimal(out["minimum_hypothetical_per_attempt_net_ev_yen"]) == -3
    assert out["positive_executable_ev_proven"] is False


@pytest.mark.parametrize("change", [
    {"synthetic_only": False}, {"synthetic_only": "true"},
    {"max_day_stake_yen": True}, {"max_day_stake_yen": 0},
    {"max_day_stake_yen": 250}, {"max_race_stake_yen": 400},
    {"attempts": []}, {"attempts": None}, {"attempts": tuple()},
    {"extra_permission": True},
])
def test_invalid_daily_scenarios_fail_closed(change):
    with pytest.raises(ValueError):
        audit_synthetic_daily_budget(day(**change))


@pytest.mark.parametrize("bad_attempts", [
    [attempt("T1", "S1"), attempt("T1", "S2")],
    [attempt("T1", "S1"), attempt("T2", "20261019")],
    [attempt("not_synthetic", "S1")],
    [attempt("T1", "S1", fill_fraction=0.5)],
    [attempt("T1", "S1", stake_yen=101)],
    [attempt("T1", "S1", fee_per_fill_yen="-1")],
    [attempt("T1", "S1", live_bet=True)],
    [attempt("T1", "S1", conditional_win_probability_lower="NaN")],
])
def test_duplicate_invalid_realworld_or_extra_attempts_fail_closed(bad_attempts):
    with pytest.raises(ValueError):
        audit_synthetic_daily_budget(day(bad_attempts))


def test_large_synthetic_attempt_list_is_bounded():
    with pytest.raises(ValueError, match="bounded"):
        audit_synthetic_daily_budget(day(
            [attempt(f"T{i}", f"S{i}") for i in range(1, 1026)],
            max_day_stake_yen=10_000_000,
        ))
