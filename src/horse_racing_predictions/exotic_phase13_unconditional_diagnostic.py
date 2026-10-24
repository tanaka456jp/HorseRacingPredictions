"""Selection-bias diagnostic for the frozen Phase 13 conditional partner study.

Exact partner-pair hit-rate is computed only AFTER the nominated longshot
anchor finished in the top three. It is therefore NOT a direct trifecta/trio
hit rate. This supplementary descriptive statistic restores the complete
pre-nomination denominator without modifying the preregistered Phase 13
gate, the model or its one-shot split.

The statistic does not establish an executable bet, positive expected
value, or pre-purchase odds rights. All computed hit counts are historical
after-outcome diagnostics. No JRA-VAN access occurs here.
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd


def _count(name: str, value: Any) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def summarize_unconditional_trio_diagnostic(
    evidence: pd.DataFrame,
    *,
    evaluated_races: int,
    nominated_candidate_races: int,
    anchor_top3_races: int,
    conditional_partner_races: int,
) -> dict:
    """Restore exact-trio hit denominators to all candidate/evaluated races.

    Conditional evidence rows only exist when a nominated longshot anchor
    actually finished top-3. On every other race the exact nominated trio
    cannot hit, independent of partner order. The conditional exact-pair
    hit indicators therefore equal the complete exact-trio success counts.

    'evaluated_races' here means the *pre-filtered research evaluation frame*
    (e.g. eligible JRA races with valid historical win odds), not all JRA
    races. It is a historical, non-executable proxy.
    """
    total = _count("evaluated_races", evaluated_races)
    nominated = _count("nominated_candidate_races", nominated_candidate_races)
    anchor = _count("anchor_top3_races", anchor_top3_races)
    conditional = _count("conditional_partner_races", conditional_partner_races)
    if not (conditional <= anchor <= nominated <= total):
        raise ValueError("inconsistent nested race counts")
    if not isinstance(evidence, pd.DataFrame):
        raise ValueError("conditional evidence must be a pandas DataFrame")
    expected = {
        "race_id", "baseline_exact_pair_hit", "challenger_exact_pair_hit"
    }
    if expected - set(evidence.columns):
        raise ValueError("conditional evidence columns are missing")
    if len(evidence) != conditional:
        raise ValueError("conditional pair evidence and race count disagree")
    if evidence["race_id"].isna().any() or evidence["race_id"].duplicated().any():
        raise ValueError("conditional race identities must be unique")
    for key in ("baseline_exact_pair_hit", "challenger_exact_pair_hit"):
        if not evidence[key].isin([0, 1]).all():
            raise ValueError("exact-pair hit indicators must be binary")

    baseline_hits = int(evidence["baseline_exact_pair_hit"].sum())
    challenger_hits = int(evidence["challenger_exact_pair_hit"].sum())
    if baseline_hits > conditional or challenger_hits > conditional:
        raise ValueError("exact hit count exceeds conditionally evaluated races")

    def rate(hits: int, denominator: int) -> float | None:
        return float(hits / denominator) if denominator else None

    candidate_baseline = rate(baseline_hits, nominated)
    candidate_challenger = rate(challenger_hits, nominated)
    all_baseline = rate(baseline_hits, total)
    all_challenger = rate(challenger_hits, total)

    return {
        "status": "historical_selection_bias_diagnostic_only",
        "evaluated_races": total,
        "nominated_candidate_races": nominated,
        "anchor_top3_races": anchor,
        "conditional_partner_races": conditional,
        "baseline_exact_trio_hits": baseline_hits,
        "challenger_exact_trio_hits": challenger_hits,
        "baseline_exact_trio_hit_rate_per_candidate_race": candidate_baseline,
        "challenger_exact_trio_hit_rate_per_candidate_race": candidate_challenger,
        "exact_trio_hit_rate_delta_per_candidate_race": (
            candidate_challenger - candidate_baseline
            if nominated else None
        ),
        "baseline_exact_trio_hit_rate_per_evaluated_race": all_baseline,
        "challenger_exact_trio_hit_rate_per_evaluated_race": all_challenger,
        "exact_trio_hit_rate_delta_per_evaluated_race": (
            all_challenger - all_baseline
            if total else None
        ),
        "conditional_sample_is_oracle_selected": True,
        "historical_final_win_odds_proxy_only": True,
        "pre_purchase_exotic_odds_verified": False,
        "expected_value_calculated": False,
        "paper_or_live_staking_authorized": False,
        "protected_holdout": "2025-2026 untouched",
        "denominator_note": (
            "Rates include anchor misses and races without eligible longshot "
            "nominations as zero exact-trio hits. The evaluated frame has "
            "historical outcome and odds filters and is not every JRA race. "
            "Conditional exact-pair hit-rates must not be reported as "
            "unconditional trio hit-rates or expected value."
        ),
    }
