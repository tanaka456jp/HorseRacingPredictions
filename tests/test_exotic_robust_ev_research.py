"""Purely synthetic prebet EV stress tests. No real data or ticket execution."""
from copy import deepcopy
from decimal import Decimal

import pytest

from horse_racing_predictions.exotic_robust_ev_research import (
    audit_conservative_exotic_ev,
)


def source():
    return {
        "provider_name": "SYNTHETIC SOURCE",
        "terms_reference": "https://example.invalid/terms",
        "source_reference": "https://example.invalid/quotes",
        "race_id_mapping": "fictional stable race key",
        "combination_mapping": "trio sorted and trifecta ordered",
        "capture_clock_evidence": "fictional synchronized clock",
        "purchase_cutoff_reference": "https://example.invalid/cutoff",
        "retention_policy_reference": "https://example.invalid/retention",
        "free_access_confirmed": True,
        "automated_capture_permitted": True,
        "ml_research_permitted": True,
        "snapshot_retention_permitted": True,
        "pre_decision_quotes_available": True,
        "purchase_availability_verified": True,
        "immutable_capture_supported": True,
        "provider_refresh_seconds": 60,
        "access_cost_yen": 0,
        "rights_reviewed_at": "2024-12-30T00:00:00+00:00",
        "source_kind": "official_public",
    }


def quote():
    return {
        "race_id": "SYNTHETIC-RACE",
        "bet_type": "trio",
        "horse_numbers": [9, 2, 5],
        "decimal_odds": "50.0",
        "source_name": "SYNTHETIC SOURCE",
        "source_reference": "https://example.invalid/quotes",
        "quote_stage": "pre_race",
        "odds_kind": "decimal_quote",
        "observed_at": "2024-12-31T05:28:30+00:00",
        "captured_at": "2024-12-31T05:28:40+00:00",
        "scheduled_post_time": "2024-12-31T05:30:00+00:00",
    }


def prediction():
    return {
        "race_id": "SYNTHETIC-RACE",
        "bet_type": "trio",
        "horse_numbers": [5, 9, 2],
        "point_probability": "0.060",
        "lower_confidence_probability": "0.035",
        "estimated_at": "2024-12-31T05:28:45+00:00",
        "model_frozen_at": "2024-01-01T00:00:00+00:00",
        "model_sha256": "a" * 64,
        "calibration_report_sha256": "b" * 64,
        "confidence_method": "race_cluster_bootstrap",
        "confidence_level": "0.95",
        "validation_period_end": "2023-12-31",
        "validation_races": 300,
    }


def economics():
    return {
        "stake_yen": 100,
        "odds_haircut_fraction": "0.20",
        "per_ticket_cost_yen": "10",
    }


def audit(q=None, s=None, p=None, e=None):
    return audit_conservative_exotic_ev(
        quote() if q is None else q,
        source() if s is None else s,
        prediction() if p is None else p,
        economics() if e is None else e,
        decision_at="2024-12-31T05:29:00+00:00",
        purchase_cutoff_at="2024-12-31T05:29:30+00:00",
    )


def test_synthetic_positive_math_is_never_claimed_as_real_profit():
    result = audit()
    assert result["status"] == "research_review_required"
    assert result["blockers"] == []
    assert result["canonical_combination_key"] == "SYNTHETIC-RACE:trio:2-5-9"
    assert Decimal(result["hypothetically_haircut_return_multiple"]) == 40
    assert Decimal(result["breakeven_probability_under_assumptions"]) == Decimal(".0275")
    assert Decimal(result["point_ev_yen_per_stake_yen"]) == Decimal("1.30")
    assert Decimal(result["lower_bound_ev_yen_per_stake_yen"]) == Decimal(".30")
    assert Decimal(result["lower_bound_ev_yen_per_ticket"]) == 30
    assert result["positive_lower_bound_ev_under_assumptions"] is True
    assert result["positive_ev_proven"] is False
    assert result["approved_for_ev"] is False
    assert result["approved_for_paper_staking"] is False
    assert result["approved_for_live_staking"] is False


def test_optimistic_point_estimate_cannot_hide_negative_lower_bound():
    p = prediction()
    p["lower_confidence_probability"] = "0.01"
    result = audit(p=p)
    assert result["status"] == "research_review_required"
    assert result["positive_point_ev_under_assumptions"] is True
    assert result["positive_lower_bound_ev_under_assumptions"] is False
    assert Decimal(result["lower_bound_ev_yen_per_ticket"]) == Decimal("-70")


@pytest.mark.parametrize("patch", [
    {"lower_confidence_probability": "0.061"},
    {"lower_confidence_probability": "-0.01"},
    {"point_probability": "1.01"},
    {"point_probability": "NaN"},
    {"point_probability": True},
    {"estimated_at": "2024-12-31T05:29:01+00:00"},
    {"model_frozen_at": "2024-12-31T05:29:00+00:00"},
    {"validation_period_end": "2025-01-01"},
    {"validation_period_end": "2026-10-01"},
    {"validation_period_end": "2024-12-31"},  # frozen in Jan 2024
    {"validation_races": 29},
    {"validation_races": True},
    {"confidence_method": "naive_independent_ticket_bootstrap"},
    {"confidence_level": "0.90"},
    {"model_sha256": "not-a-hash"},
    {"race_id": "ANOTHER-RACE"},
    {"horse_numbers": [5, 9, 7]},
    {"bet_type": "trifecta"},
    {"finish_position": 1},
])
def test_prediction_provenance_fails_closed(patch):
    p = prediction()
    p.update(patch)
    result = audit(p=p)
    assert result["status"] == "blocked"
    assert result["approved_for_ev"] is False
    assert result["canonical_combination_key"] is None


@pytest.mark.parametrize("patch", [
    {"stake_yen": 99},
    {"stake_yen": 250},
    {"stake_yen": True},
    {"odds_haircut_fraction": "0"},
    {"odds_haircut_fraction": "1"},
    {"odds_haircut_fraction": "-0.01"},
    {"odds_haircut_fraction": "NaN"},
    {"odds_haircut_fraction": 0.2},
    {"per_ticket_cost_yen": "-1"},
    {"per_ticket_cost_yen": "Infinity"},
    {"new_fee": "0"},
])
def test_economics_invalid_assumptions_fail_closed(patch):
    e = economics()
    e.update(patch)
    result = audit(e=e)
    assert result["status"] == "blocked"
    assert not result["approved_for_ev"]


def test_costs_and_haircut_reverse_apparent_positive_ev():
    e = economics()
    e["odds_haircut_fraction"] = "0.80"
    e["per_ticket_cost_yen"] = "200"
    result = audit(e=e)
    assert Decimal(result["point_ev_yen_per_stake_yen"]) < 0
    assert Decimal(result["lower_bound_ev_yen_per_stake_yen"]) < 0
    assert result["positive_lower_bound_ev_under_assumptions"] is False


def test_quote_stale_or_cutoff_missed_blocks_arithmetic():
    q = quote()
    q["observed_at"] = "2024-12-31T05:26:00+00:00"
    result = audit(q=q)
    assert result["status"] == "blocked"
    assert "lower_bound_ev_yen_per_ticket" not in result
    assert result["canonical_combination_key"] is None


def test_unverified_rights_block_even_when_all_arithmetic_is_positive():
    s = source()
    s["snapshot_retention_permitted"] = False
    result = audit(s=s)
    assert result["status"] == "blocked"
    assert "lower_bound_ev_yen_per_ticket" not in result


def test_final_odds_and_settlement_field_cannot_be_used_as_prebet_quote():
    q = quote()
    q["final_payout"] = "500"
    result = audit(q=q)
    assert result["status"] == "blocked"
    assert "lower_bound_ev_yen_per_ticket" not in result


def test_trifecta_order_mismatch_is_rejected():
    q = quote()
    q["bet_type"] = "trifecta"
    p = prediction()
    p["bet_type"] = "trifecta"
    result = audit(q=q, p=p)
    assert result["status"] == "blocked"
    p["horse_numbers"] = [9, 2, 5]
    assert audit(q=q, p=p)["status"] == "research_review_required"


def test_no_input_mutations_or_hidden_execution():
    q, s, p, e = quote(), source(), prediction(), economics()
    originals = deepcopy((q, s, p, e))
    audit(q=q, s=s, p=p, e=e)
    assert originals == (q, s, p, e)


def test_missing_or_non_object_quote_is_blocked():
    assert audit(q=None)["approved_for_ev"] is False
    result = audit(q="not a mapping")
    assert result["status"] == "blocked"
    assert result["positive_ev_proven"] is False
