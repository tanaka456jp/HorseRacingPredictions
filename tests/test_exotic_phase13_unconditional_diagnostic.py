"""Synthetic-only full-denominator historical trio assertions."""
from __future__ import annotations

import pandas as pd
import pytest

from horse_racing_predictions.exotic_phase13_unconditional_diagnostic import (
    summarize_unconditional_trio_diagnostic,
)


def evidence(baseline, challenger):
    return pd.DataFrame({
        "race_id": [f"r{index}" for index in range(len(baseline))],
        "baseline_exact_pair_hit": baseline,
        "challenger_exact_pair_hit": challenger,
    })


def test_oracle_conditional_50_percent_is_only_five_percent_all_races():
    result = summarize_unconditional_trio_diagnostic(
        evidence([0, 1], [1, 1]),
        evaluated_races=40,
        nominated_candidate_races=10,
        anchor_top3_races=2,
        conditional_partner_races=2,
    )
    # Challenger had 2 of 2 hits CONDITIONALLY, but those cannot be
    # called 100% trio hit-rate. There were 40 eligible evaluation races.
    assert result["baseline_exact_trio_hits"] == 1
    assert result["challenger_exact_trio_hits"] == 2
    assert result["challenger_exact_trio_hit_rate_per_candidate_race"] == 0.2
    assert result["challenger_exact_trio_hit_rate_per_evaluated_race"] == 0.05
    assert result["baseline_exact_trio_hit_rate_per_evaluated_race"] == 0.025
    assert result["exact_trio_hit_rate_delta_per_evaluated_race"] == 0.025
    assert result["conditional_sample_is_oracle_selected"]
    assert result["expected_value_calculated"] is False
    assert result["paper_or_live_staking_authorized"] is False


def test_anchor_misses_lower_unconditional_rate_even_with_perfect_pairs():
    result = summarize_unconditional_trio_diagnostic(
        evidence([1], [1]),
        evaluated_races=100,
        nominated_candidate_races=50,
        anchor_top3_races=1,
        conditional_partner_races=1,
    )
    assert result["challenger_exact_trio_hit_rate_per_candidate_race"] == .02
    assert result["challenger_exact_trio_hit_rate_per_evaluated_race"] == .01


def test_zero_nominations_never_fabricates_probability():
    result = summarize_unconditional_trio_diagnostic(
        evidence([], []), evaluated_races=5,
        nominated_candidate_races=0,
        anchor_top3_races=0, conditional_partner_races=0,
    )
    assert result["challenger_exact_trio_hits"] == 0
    assert result["challenger_exact_trio_hit_rate_per_candidate_race"] is None
    assert result["challenger_exact_trio_hit_rate_per_evaluated_race"] == 0.0
    assert result["expected_value_calculated"] is False


@pytest.mark.parametrize("counts", [
    dict(evaluated_races=5, nominated_candidate_races=6, anchor_top3_races=1, conditional_partner_races=1),
    dict(evaluated_races=5, nominated_candidate_races=3, anchor_top3_races=4, conditional_partner_races=1),
    dict(evaluated_races=5, nominated_candidate_races=3, anchor_top3_races=1, conditional_partner_races=2),
    dict(evaluated_races=-1, nominated_candidate_races=3, anchor_top3_races=1, conditional_partner_races=1),
])
def test_invalid_nested_counts_fail_closed(counts):
    with pytest.raises(ValueError):
        summarize_unconditional_trio_diagnostic(
            evidence([1], [1]), **counts,
        )


def test_duplicate_races_and_nonbinary_hits_are_rejected():
    frame = evidence([0, 1], [1, 1])
    frame.loc[1, "race_id"] = frame.loc[0, "race_id"]
    with pytest.raises(ValueError, match="unique"):
        summarize_unconditional_trio_diagnostic(
            frame,
            evaluated_races=2, nominated_candidate_races=2,
            anchor_top3_races=2, conditional_partner_races=2,
        )
    frame = evidence([0, 1], [1, 4])
    with pytest.raises(ValueError, match="binary"):
        summarize_unconditional_trio_diagnostic(
            frame,
            evaluated_races=2, nominated_candidate_races=2,
            anchor_top3_races=2, conditional_partner_races=2,
        )


def test_mismatch_between_conditional_count_and_pairs_fails_closed():
    with pytest.raises(ValueError, match="disagree"):
        summarize_unconditional_trio_diagnostic(
            evidence([1], [1]),
            evaluated_races=2, nominated_candidate_races=2,
            anchor_top3_races=2, conditional_partner_races=2,
        )
