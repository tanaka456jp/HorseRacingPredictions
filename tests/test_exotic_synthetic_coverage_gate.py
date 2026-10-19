"""Synthetic-only: lost quote/unfilled opportunity must never disappear."""
import pytest

from horse_racing_predictions.exotic_synthetic_coverage_gate import (
    audit_synthetic_coverage_gate,
)


def opportunity(rid="S1", **changes):
    item = {
        "race_id": rid,
        "race_date": "2024-10-01",
        "quote_status": "ready",
        "observed_at": "2024-10-01T00:00:00Z",
        "captured_at": "2024-10-01T00:00:01Z",
        "decision_at": "2024-10-01T00:00:10Z",
        "purchase_cutoff_at": "2024-10-01T00:00:30Z",
        "scheduled_post_at": "2024-10-01T00:02:00Z",
    }
    item.update(changes)
    return item


def evaluated(rid="S1", **changes):
    item = {
        "race_id": rid,
        "strategy_status": "filled",
        "market_status": "filled",
        "strategy_attempted_stake_yen": 100,
        "market_attempted_stake_yen": 100,
    }
    item.update(changes)
    return item


def scenario(opps=None, rows=None, **changes):
    if opps is None:
        opps = [
            opportunity("S1"),
            opportunity("S2", quote_status="missing",
                        observed_at=None, captured_at=None,
                        purchase_cutoff_at=None),
            opportunity("S3", quote_status="stale",
                        observed_at="2024-10-01T00:00:00Z",
                        captured_at="2024-10-01T00:00:01Z",
                        decision_at="2024-10-01T00:03:00Z",
                        purchase_cutoff_at="2024-10-01T00:03:30Z",
                        scheduled_post_at="2024-10-01T00:04:00Z"),
            opportunity("S4", quote_status="cutoff_unknown",
                        purchase_cutoff_at=None),
            opportunity("S5"),
        ]
    if rows is None:
        rows = [
            evaluated("S1"),
            evaluated("S2", strategy_status="abstained", market_status="abstained",
                      strategy_attempted_stake_yen=0, market_attempted_stake_yen=0),
            evaluated("S3", strategy_status="abstained", market_status="abstained",
                      strategy_attempted_stake_yen=0, market_attempted_stake_yen=0),
            evaluated("S4", strategy_status="abstained", market_status="abstained",
                      strategy_attempted_stake_yen=0, market_attempted_stake_yen=0),
            evaluated("S5", strategy_status="unfilled", market_status="abstained",
                      market_attempted_stake_yen=0),
        ]
    result = {
        "synthetic_only": True,
        "max_quote_age_seconds": 60,
        "max_race_stake_yen": 100,
        "max_day_stake_yen": 300,
        "opportunities": opps,
        "evaluated": rows,
    }
    result.update(changes)
    return result


def test_missing_stale_cutoff_unknown_unfilled_all_retained_in_denominator():
    got = audit_synthetic_coverage_gate(scenario())
    assert got["eligible_opportunity_count"] == 5
    assert got["evaluated_opportunity_count"] == 5
    assert got["quote_ready_count"] == 2
    assert got["missing_quote_count"] == 1
    assert got["stale_quote_count"] == 1
    assert got["unknown_cutoff_count"] == 1
    assert got["strategy_execution_counts"] == {
        "filled": 1, "unfilled": 1, "abstained": 3
    }
    assert got["market_execution_counts"] == {
        "filled": 1, "unfilled": 0, "abstained": 4
    }
    assert got["strategy_worst_case_reserved_yen"] == 200
    assert got["market_worst_case_reserved_yen"] == 100
    assert got["complete_synthetic_opportunity_coverage"]
    assert got["positive_executable_ev_proven"] is False
    assert got["actual_eligible_opportunity_coverage_verified"] is False
    assert got["paper_or_live_action_authorized"] is False


def test_dropped_missing_quote_race_fails_instead_of_selecting_only_successes():
    case = scenario()
    case["evaluated"] = [r for r in case["evaluated"] if r["race_id"] != "S2"]
    with pytest.raises(ValueError, match="one-to-one"):
        audit_synthetic_coverage_gate(case)


def test_duplicated_unknown_cutoff_cannot_hide_missing_manifest_race():
    case = scenario()
    case["evaluated"][-1]["race_id"] = "S4"
    with pytest.raises(ValueError, match="duplicate"):
        audit_synthetic_coverage_gate(case)


@pytest.mark.parametrize("bad", [
    {"quote_status": "settled"},
    {"quote_status": "ready", "observed_at": "2024-09-30T23:00:00Z"},
    {"quote_status": "stale"},
    {"quote_status": "missing"},
    {"quote_status": "cutoff_unknown"},
    {"captured_at": "2024-10-01T00:00:11Z"},
    {"observed_at": "2024-10-01T00:00:11Z"},
    {"purchase_cutoff_at": None},
    {"purchase_cutoff_at": "2024-10-01T00:02:00Z"},
    {"race_date": "2025-01-01"},
    {"race_date": "2023-02-30"},
    {"race_id": "2024100101"},
    {"race_date": "2024-09-30"},
    {"race_result": 1},
])
def test_manifest_bad_quote_evidence_fails_closed(bad):
    with pytest.raises(ValueError):
        audit_synthetic_coverage_gate(scenario(opps=[opportunity(**bad)],
                                               rows=[evaluated()]))


@pytest.mark.parametrize("bad", [
    {"strategy_status": "settled"},
    {"market_status": "settled"},
    {"strategy_attempted_stake_yen": 0},
    {"strategy_attempted_stake_yen": True},
    {"strategy_attempted_stake_yen": 101},
    {"strategy_attempted_stake_yen": 200},
    {"market_attempted_stake_yen": 200},
    {"strategy_status": "abstained"},
    {"market_status": "abstained"},
    {"final_payout": 999},
])
def test_invalid_synthetic_evaluated_rows_are_rejected(bad):
    with pytest.raises(ValueError):
        audit_synthetic_coverage_gate(scenario(opps=[opportunity()],
                                               rows=[evaluated(**bad)]))


def test_strategy_and_market_daily_caps_applied_independently():
    case = scenario(
        opps=[opportunity("S1"), opportunity("S2")],
        rows=[evaluated("S1"), evaluated("S2")],
        max_day_stake_yen=100,
    )
    with pytest.raises(ValueError, match="day capital cap"):
        audit_synthetic_coverage_gate(case)


def test_market_cap_cannot_be_hidden_by_strategy_abstention():
    case = scenario(
        opps=[opportunity("S1"), opportunity("S2")],
        rows=[
            evaluated("S1", strategy_status="abstained",
                      strategy_attempted_stake_yen=0),
            evaluated("S2", strategy_status="abstained",
                      strategy_attempted_stake_yen=0),
        ],
        max_day_stake_yen=100,
    )
    with pytest.raises(ValueError, match="day capital cap"):
        audit_synthetic_coverage_gate(case)


@pytest.mark.parametrize("change", [
    {"synthetic_only": False},
    {"max_quote_age_seconds": True},
    {"max_quote_age_seconds": 3601},
    {"max_race_stake_yen": 101},
    {"max_race_stake_yen": 400},
    {"analysis_result": "PASS"},
])
def test_bad_protocol_flags_and_limits_fail_closed(change):
    with pytest.raises(ValueError):
        audit_synthetic_coverage_gate(scenario(**change))
