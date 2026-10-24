"""Synthetic-only paired race bootstrap regression for recovered research code.

No odds acquisition, paid service, real betting, protected final holdout,
or inference about actual market-beating expected value.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from horse_racing_predictions.exotic_synthetic_paired_race_bootstrap import (
    audit_synthetic_paired_race_bootstrap,
)


def fixture_rows(n=30):
    return [
        {
            "synthetic_only": True,
            "source_kind": "synthetic_fixture",
            "race_id": f"SYN-{index:04d}",
            "race_date": "2023-06-01",
            "reference_budget_yen": 1000,
            "strategy_stake_yen": 100,
            "strategy_gross_return_yen": 200,
            "strategy_fees_yen": 10,
            "market_stake_yen": 100,
            "market_gross_return_yen": 100,
            "market_fees_yen": 10,
        }
        for index in range(1, n + 1)
    ]


def test_constant_paired_race_advantage_has_deterministic_bootstrap():
    result = audit_synthetic_paired_race_bootstrap(
        fixture_rows(), seed=42, resamples=200,
    )
    assert result["status"] == "synthetic_diagnostic_only"
    assert result["race_count"] == 30
    assert Decimal(result["paired_net_advantage_per_reference_yen"]) == Decimal("0.1")
    assert Decimal(result["synthetic_race_bootstrap_95pct_lower"]) == Decimal("0.1")
    assert Decimal(result["synthetic_race_bootstrap_95pct_upper"]) == Decimal("0.1")
    assert result["positive_executable_ev_proven"] is False
    assert result["approved_for_paper_or_live"] is False
    assert result["protected_holdout_used"] is False
    assert result["quote_rights_verified"] is False


def test_market_outperforms_strategy_without_becoming_an_ev_approval():
    rows = fixture_rows()
    for row in rows:
        row["market_gross_return_yen"] = 300
    result = audit_synthetic_paired_race_bootstrap(rows, seed=13, resamples=200)
    assert result["status"] == "synthetic_diagnostic_only"
    assert Decimal(result["paired_net_advantage_per_reference_yen"]) == Decimal("-0.1")
    assert result["positive_executable_ev_proven"] is False


def test_random_draws_reproduce_exactly_at_fixed_seed():
    rows = fixture_rows()
    for index, row in enumerate(rows):
        if index % 2 == 0:
            row["strategy_gross_return_yen"] = 0
    a = audit_synthetic_paired_race_bootstrap(rows, seed=99, resamples=250)
    b = audit_synthetic_paired_race_bootstrap(rows, seed=99, resamples=250)
    assert a == b


def test_abstained_comparator_is_retained_as_zero_stake():
    rows = fixture_rows()
    rows[0]["market_stake_yen"] = 0
    rows[0]["market_gross_return_yen"] = 0
    rows[0]["market_fees_yen"] = 0
    result = audit_synthetic_paired_race_bootstrap(rows, resamples=200)
    assert result["race_count"] == 30
    assert result["positive_executable_ev_proven"] is False


@pytest.mark.parametrize("override", [
    {"race_id": "202310070101"},
    {"race_id": "SYN-0002"},
    {"race_date": "2025-01-01"},
    {"race_date": "2026-01-01"},
    {"race_date": "2023-02-30"},
    {"source_kind": "real_race"},
    {"synthetic_only": False},
    {"strategy_stake_yen": True},
    {"strategy_stake_yen": 101},
    {"strategy_stake_yen": 2000},
    {"strategy_gross_return_yen": -1},
    {"market_stake_yen": 0, "market_gross_return_yen": 10},
    {"reference_budget_yen": 0},
    {"leaked_final_odds": "10"},
])
def test_malformed_or_out_of_scope_race_blocks_entire_bootstrap(override):
    rows = fixture_rows()
    rows[0].update(override)
    result = audit_synthetic_paired_race_bootstrap(rows, resamples=200)
    assert result["status"] == "blocked"
    assert result["blockers"]
    assert result["positive_executable_ev_proven"] is False


@pytest.mark.parametrize("sample_count", [0, 1, 29, 2001])
def test_sample_count_gate(sample_count):
    rows = fixture_rows(sample_count)
    result = audit_synthetic_paired_race_bootstrap(rows, resamples=200)
    assert result["status"] == "blocked"


@pytest.mark.parametrize("kwargs", [
    {"seed": -1}, {"seed": True}, {"seed": 2**32},
    {"resamples": 199}, {"resamples": 2001}, {"resamples": True},
])
def test_invalid_bootstrap_parameters_block(kwargs):
    result = audit_synthetic_paired_race_bootstrap(
        fixture_rows(), **kwargs,
    )
    assert result["status"] == "blocked"


def test_chronological_reverse_order_blocked():
    rows = fixture_rows()
    rows[-1]["race_date"] = "2018-01-01"
    result = audit_synthetic_paired_race_bootstrap(rows)
    assert result["status"] == "blocked"
