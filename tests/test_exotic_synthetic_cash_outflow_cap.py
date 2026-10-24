"""Worst-case synthetic all-fill cash outflow includes BOTH kinds of fees."""
from decimal import Decimal

import pytest

from horse_racing_predictions.exotic_synthetic_cash_outflow_cap import (
    audit_synthetic_cash_outflow_cap,
)


def ticket(n=1, race="S1", **changes):
    item = {
        "attempt_id": f"T{n}",
        "race_id": race,
        "stake_yen": 100,
        "attempt_fee_yen": "10",
        "fill_fee_yen": "5",
        "hypothetical_fill_fraction": "0.5",
    }
    item.update(changes)
    return item


def scenario(rows=None, **changes):
    result = {
        "synthetic_only": True,
        "max_race_cash_outflow_yen": 300,
        "max_day_cash_outflow_yen": 500,
        "attempts": [ticket(1), ticket(2), ticket(3, "S2")]
        if rows is None else rows,
    }
    result.update(changes)
    return result


def test_three_100_yen_attempts_reserve_345_yen_including_all_45_yen_fees():
    out = audit_synthetic_cash_outflow_cap(scenario())
    assert out["attempt_count"] == 3
    assert out["synthetic_race_count"] == 2
    assert Decimal(out["stake_full_reservation_yen"]) == 300
    assert Decimal(out["attempt_fee_full_reservation_yen"]) == 30
    assert Decimal(out["fill_fee_full_reservation_yen"]) == 15
    assert Decimal(out["all_fill_worst_case_cash_outflow_yen"]) == 345
    assert Decimal(out["peak_single_race_outflow_yen"]) == 230
    assert Decimal(out["hypothetical_fill_weighted_cash_outflow_yen"]) == Decimal("187.5")
    assert Decimal(out["unreserved_daily_cash_capacity_yen"]) == 155
    assert out["fill_fraction_never_reduces_reserved_cash"] is True
    assert out["positive_executable_ev_proven"] is False
    assert out["paper_or_live_action_authorized"] is False
    assert out["daily_cap_implemented_in_live_or_paper"] is False


def test_exact_300_yen_daily_limit_rejects_345_yen_outflow():
    with pytest.raises(ValueError, match="day cash outflow"):
        audit_synthetic_cash_outflow_cap(scenario(max_day_cash_outflow_yen=300))


def test_zero_fill_assumption_still_reserves_all_stakes_and_fees():
    out = audit_synthetic_cash_outflow_cap(scenario([
        ticket(1, hypothetical_fill_fraction="0"),
        ticket(2, hypothetical_fill_fraction="0"),
        ticket(3, "S2", hypothetical_fill_fraction="0"),
    ]))
    assert Decimal(out["all_fill_worst_case_cash_outflow_yen"]) == 345
    assert Decimal(out["hypothetical_fill_weighted_cash_outflow_yen"]) == 30


def test_same_race_fee_overload_blocks_even_when_stakes_only_within_cap():
    with pytest.raises(ValueError, match="race cash outflow"):
        audit_synthetic_cash_outflow_cap(scenario([
            ticket(1), ticket(2), ticket(3)
        ]))


def test_no_fill_or_attempt_fee_is_not_invented():
    out = audit_synthetic_cash_outflow_cap(scenario([
        ticket(1, attempt_fee_yen="0", fill_fee_yen="0",
               hypothetical_fill_fraction="1"),
    ]))
    assert Decimal(out["all_fill_worst_case_cash_outflow_yen"]) == 100
    assert Decimal(out["hypothetical_fill_weighted_cash_outflow_yen"]) == 100


def test_day_cap_rejects_cross_race_aggregate_with_tiny_fill_probability():
    attempts = [
        ticket(1, "S1", hypothetical_fill_fraction="0.001"),
        ticket(2, "S2", hypothetical_fill_fraction="0.001"),
        ticket(3, "S3", hypothetical_fill_fraction="0.001"),
        ticket(4, "S4", hypothetical_fill_fraction="0.001"),
        ticket(5, "S5", hypothetical_fill_fraction="0.001"),
    ]
    with pytest.raises(ValueError, match="day cash outflow"):
        audit_synthetic_cash_outflow_cap(scenario(attempts))


@pytest.mark.parametrize("change", [
    {"synthetic_only": False},
    {"synthetic_only": "True"},
    {"max_day_cash_outflow_yen": True},
    {"max_day_cash_outflow_yen": 250},
    {"max_race_cash_outflow_yen": 600},
    {"attempts": []},
    {"attempts": None},
    {"permission_to_bet": True},
])
def test_invalid_envelope_rejected(change):
    with pytest.raises(ValueError):
        audit_synthetic_cash_outflow_cap(scenario(**change))


@pytest.mark.parametrize("bad", [
    {"attempt_id": "20241001"},
    {"race_id": "2024100101"},
    {"stake_yen": 0},
    {"stake_yen": 101},
    {"stake_yen": True},
    {"attempt_fee_yen": "-1"},
    {"attempt_fee_yen": "NaN"},
    {"attempt_fee_yen": 10},
    {"fill_fee_yen": "1000001"},
    {"fill_fee_yen": "inf"},
    {"hypothetical_fill_fraction": "1.001"},
    {"hypothetical_fill_fraction": 0.5},
    {"hypothetical_fill_fraction": "-0.1"},
    {"live_order": True},
])
def test_invalid_ticket_or_real_source_field_rejected(bad):
    with pytest.raises(ValueError):
        audit_synthetic_cash_outflow_cap(scenario([ticket(1, **bad)]))


def test_duplicate_ticket_blocks_entire_batch():
    with pytest.raises(ValueError, match="duplicate"):
        audit_synthetic_cash_outflow_cap(scenario([
            ticket(1, "S1"), ticket(1, "S2"),
        ]))


def test_oversized_batch_blocks_before_processing():
    with pytest.raises(ValueError, match="bounded"):
        audit_synthetic_cash_outflow_cap(scenario([
            ticket(index, f"S{index}") for index in range(1, 1026)
        ], max_day_cash_outflow_yen=10_000_000))
