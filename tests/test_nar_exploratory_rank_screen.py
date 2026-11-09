"""Fictional-only 2017-2022 72-month exploratory ranking controls."""
from dataclasses import replace

import pytest

from horse_racing_predictions.nar_exploratory_rank_screen import (
    explore_nar_2017_2022_ranking_signal,
)
from horse_racing_predictions.nar_official_zip_probe import UnsafeNarSource
from horse_racing_predictions.nar_prior_day_features import NarAsOfFeatures
from horse_racing_predictions.nar_status_aware_prior_day import (
    NarStatusAwareAsOfAudit, NarStatusAwareAsOfBatch, NarStatusAwareAsOfTarget,
)

_DAYS = (
    "20170301", "20180501", "20190601",
    "20200201", "20211201",
    "20220102", "20220403", "20221105",
)


def fictional_batch():
    rows = []
    for r, ymd in enumerate(_DAYS):
        for n in range(1, 8):
            finish = ((n + 2*r - 1) % 7) + 1
            rows.append(NarStatusAwareAsOfTarget(
                race_key=("架空地方場", ymd, 1),
                horse_number=n,
                horse_identity=(f"架空馬{n}", f"2011{n:02d}01"),
                feature=NarAsOfFeatures(
                    prior_starts=r,
                    prior_wins=int(n == 1 and r > 0),
                    prior_top3=min(r, 2) if n in (1, 2, 3) else 0,
                    prior_win_rate=(int(n == 1 and r > 0) / r if r else 0.0),
                    prior_top3_rate=(min(r, 2) / r if r and n <= 3 else 0.0),
                    prior_mean_finish=(float(n) if r else None),
                    days_since_prior_start=(30 if r else None),
                ),
                target_win=int(finish == 1),
                target_place=int(finish <= 2),  # May NOT equal top3.
                target_top3=int(finish <= 3),
                after_event_status="FINISHED",
            ))
    # 100 fictional flat races in 72 months, of which 92 outcomes
    # are unresolved. The model must not claim live pre-off ROI.
    by_year = {2017: 10, 2018: 10, 2019: 10, 2020: 10,
               2021: 10, 2022: 50}
    report = NarStatusAwareAsOfAudit(
        months=72, source_flat_races=100,
        validated_flat_races=8, unresolved_flat_races=92,
        projected_target_rows=56, no_target_scratch_or_exclusion_rows=0,
        no_target_disqualification_rows=0,
        historical_started_rows=56, historical_ranked_rows=56,
        target_rows_with_prior_start=49,
        target_rows_without_prior_start=7,
        target_rows_with_prior_win=0, target_rows_with_prior_top3=0,
        target_rows_with_numeric_prior_finish=49,
    )
    return NarStatusAwareAsOfBatch(
        audit=report, targets=tuple(rows),
    ), by_year


def test_2022_missing_races_are_counted_not_treated_as_win():
    pytest.importorskip("catboost")
    batch, years = fictional_batch()
    m = explore_nar_2017_2022_ranking_signal(
        batch, flat_races_by_year=years, iterations=30,
    )
    assert m.status == "NAR_EXPLORATORY_2022_RANKING_ONLY_SELECTION_BIAS_HOLD"
    assert m.fit_races_2017_2021 == 5
    assert m.tune_races_2022 == 3
    assert m.unevaluable_tune_races_2022 == 47
    assert m.fit_horses == 35
    assert m.tune_horses == 21
    assert 0 <= m.winner_top1_worst_case_all_flat_2022 <= m.winner_top1_hit_rate_2022
    assert m.winner_top1_best_case_all_flat_2022 >= m.winner_top1_worst_case_all_flat_2022
    assert 0 <= m.random_baseline_top1_expected_2022 <= 1
    assert 0 <= m.smoothed_prior_win_baseline_top1_2022 <= 1
    assert abs(
        m.top1_uplift_over_simple_form_2022
        - (m.winner_top1_hit_rate_2022
           - m.smoothed_prior_win_baseline_top1_2022)
    ) < 1e-12
    assert -1 <= m.top1_uplift_day_bootstrap_ci95_lower <= 1
    assert -1 <= m.top1_uplift_day_bootstrap_ci95_upper <= 1
    assert m.top1_uplift_day_bootstrap_ci95_lower <= (
        m.top1_uplift_day_bootstrap_ci95_upper
    )
    assert m.independent_2022_race_days == 3
    assert 0 <= m.top3_picks_podium_precision_2022 <= 1
    assert 0 <= m.outsider_podium_hit_rate_2022 <= 1
    assert m.independently_fitted_models
    assert m.retrospective_selected_outcomes_only
    assert not m.pre_off_roster_snapshots_verified
    assert not m.betting_odds_evaluated
    assert not m.independent_oos_2023_2024_opened
    assert not m.protected_final_holdout_opened
    assert not m.source_bytes_exported
    assert not m.actual_after_cost_roi_verified
    assert not m.positive_expected_value_demonstrated
    assert "架空馬" not in repr(m)
    assert "架空地方場" not in repr(m)


@pytest.mark.parametrize(("field", "value"), [
    ("months", 71),
    ("source_flat_races", 101),
    ("usable_for_training", True),
    ("independently_captured_preoff_roster", True),
    ("independent_oos_opened", True),
    ("positive_expected_value_demonstrated", True),
])
def test_forged_full_source_readiness_is_rejected(field, value):
    batch, years = fictional_batch()
    with pytest.raises(
        UnsafeNarSource, match="NAR_EXPLORATORY_EXPLICIT_72_MONTH_DENOMINATOR_REQUIRED"
    ):
        explore_nar_2017_2022_ranking_signal(
            replace(batch, audit=replace(batch.audit, **{field: value})),
            flat_races_by_year=years,
            iterations=30,
        )


def test_future_or_protected_target_cannot_enter_training():
    batch, years = fictional_batch()
    future = replace(
        batch.targets[-1],
        race_key=("架空地方場", "20230305", 1),
    )
    with pytest.raises(UnsafeNarSource, match="NAR_EXPLORATORY_TRAINING_PERIOD_ONLY"):
        explore_nar_2017_2022_ranking_signal(
            replace(batch, targets=(*batch.targets[:-1], future)),
            flat_races_by_year=years, iterations=30,
        )


def test_duplicate_candidate_and_year_count_forgery_hold_closed():
    batch, years = fictional_batch()
    duplicate = replace(
        batch, targets=(*batch.targets, batch.targets[-1]),
    )
    with pytest.raises(UnsafeNarSource, match="NAR_EXPLORATORY_DUPLICATE_HORSE"):
        explore_nar_2017_2022_ranking_signal(
            duplicate, flat_races_by_year=years, iterations=30,
        )
    with pytest.raises(
        UnsafeNarSource, match="NAR_EXPLORATORY_EXPLICIT_72_MONTH_DENOMINATOR_REQUIRED"
    ):
        explore_nar_2017_2022_ranking_signal(
            batch, flat_races_by_year={**years, 2022: 51},
            iterations=30,
        )


def test_7_runner_podium_target_is_not_two_place_dividend():
    batch, _ = fictional_batch()
    third = next(t for t in batch.targets if t.target_top3 == 1
                 and t.target_place == 0)
    assert third.target_top3 == 1
    assert third.target_place == 0


def test_fixed_seed_race_day_bootstrap_is_deterministic_for_fictional_runs():
    pytest.importorskip("catboost")
    batch, years = fictional_batch()
    one = explore_nar_2017_2022_ranking_signal(
        batch, flat_races_by_year=years, iterations=30,
    )
    two = explore_nar_2017_2022_ranking_signal(
        batch, flat_races_by_year=years, iterations=30,
    )
    assert one == two
    assert not one.actual_after_cost_roi_verified


def _fictional_2022_official_win_returns(batch):
    amounts = {}
    for target in batch.targets:
        track, ymd, number = target.race_key
        if ymd.startswith("2022"):
            race_id = f"NAR:{ymd}:{track}:{number:02d}"
            amounts.setdefault(race_id, {})[target.horse_number] = (
                300 if target.target_win else 0
            )
    return amounts


def test_retrospective_win_only_official_payouts_do_not_prove_ev():
    pytest.importorskip("catboost")
    batch, years = fictional_batch()
    m = explore_nar_2017_2022_ranking_signal(
        batch, flat_races_by_year=years, iterations=30,
        official_win_payouts_2022=_fictional_2022_official_win_returns(batch),
    )
    assert m.historical_official_win_payouts_reconciled
    assert m.hypothetical_model_win_gross_yen_2022 is not None
    assert m.hypothetical_simple_form_win_gross_yen_2022 is not None
    assert m.hypothetical_model_win_roi_2022 == (
        m.hypothetical_model_win_gross_yen_2022 / (100 * 3) - 1
    )
    assert m.hypothetical_model_win_all_flat_adverse_missing_roi_2022 == (
        m.hypothetical_model_win_gross_yen_2022 / (100 * 50) - 1
    )
    assert m.hypothetical_model_minus_form_roi_2022 == (
        m.hypothetical_model_win_roi_2022
        - m.hypothetical_simple_form_win_roi_2022
    )
    assert m.hypothetical_paired_day_roi_ci95_lower <= m.hypothetical_paired_day_roi_ci95_upper
    assert not m.actual_after_cost_roi_verified
    assert not m.positive_expected_value_demonstrated


def test_missing_or_conflicting_retrospective_payout_is_not_silently_zeroed():
    pytest.importorskip("catboost")
    batch, years = fictional_batch()
    payouts = _fictional_2022_official_win_returns(batch)
    del payouts[sorted(payouts)[0]]
    with pytest.raises(UnsafeNarSource, match="NAR_EXPLORATORY_PAYOUT_COVERAGE_REQUIRED"):
        explore_nar_2017_2022_ranking_signal(
            batch, flat_races_by_year=years, iterations=30,
            official_win_payouts_2022=payouts,
        )
    payouts = _fictional_2022_official_win_returns(batch)
    first = sorted(payouts)[0]
    loser = next(h for h, amount in payouts[first].items() if amount == 0)
    payouts[first][loser] = 100
    with pytest.raises(UnsafeNarSource, match="NAR_EXPLORATORY_PAYOUT_WIN_LABEL_MISMATCH"):
        explore_nar_2017_2022_ranking_signal(
            batch, flat_races_by_year=years, iterations=30,
            official_win_payouts_2022=payouts,
        )
