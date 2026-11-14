"""Private retrospective NAR ranking signal screen; NEVER economic EV evidence.

2017–2021 fit and 2022 tune on a predeclared available-outcome sample.
Unresolved flat races stay in the denominator and pessimistic accuracy
bound. No 2023–24 independent holdout read, no 2025+ final holdout read.
No betting odds or historical pre-off snapshot is available for these
old monthly result ZIPs. This is intentionally incapable of proving ROI.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite
from typing import Any

import numpy as np
import pandas as pd

from .modeling import CatBoostProbabilityModel
from .nar_official_zip_probe import UnsafeNarSource
from .nar_status_aware_prior_day import NarStatusAwareAsOfBatch

_FEATURES = ("past_starts", "past_win_rate", "past_top3_rate",
             "past_mean_finish", "days_since_last_start")


@dataclass(frozen=True)
class NarExploratoryRankingMetrics:
    status: str
    source_flat_races_2017_2022: int
    unresolved_flat_races_2017_2022: int
    fit_races_2017_2021: int
    tune_races_2022: int
    unevaluable_tune_races_2022: int
    fit_horses: int
    tune_horses: int
    winner_top1_hit_rate_2022: float
    random_baseline_top1_expected_2022: float
    smoothed_prior_win_baseline_top1_2022: float
    top1_uplift_over_simple_form_2022: float
    top1_uplift_day_bootstrap_ci95_lower: float
    top1_uplift_day_bootstrap_ci95_upper: float
    independent_2022_race_days: int
    winner_top1_worst_case_all_flat_2022: float
    winner_top1_best_case_all_flat_2022: float
    top3_picks_podium_precision_2022: float
    outsider_podium_hit_rate_2022: float
    # Post-event official paid prices; never historical pre-off prices.
    historical_official_win_payouts_reconciled: bool = False
    historical_official_place_payouts_reconciled: bool = False
    hypothetical_outsider_place_gross_yen_2022: int | None = None
    hypothetical_outsider_place_roi_2022: float | None = None
    hypothetical_two_ticket_roi_2022: float | None = None
    hypothetical_two_ticket_all_flat_adverse_missing_roi_2022: float | None = None
    hypothetical_two_ticket_day_ci95_lower: float | None = None
    hypothetical_two_ticket_day_ci95_upper: float | None = None
    hypothetical_two_ticket_stake_yen_2022: int | None = None
    hypothetical_two_ticket_paid_yen_2022: int | None = None
    hypothetical_two_ticket_break_even_shortfall_yen_2022: int | None = None
    hypothetical_two_ticket_gross_uplift_needed_2022: float | None = None
    two_ticket_2022_research_decision: str = "NO_OFFICIAL_PAYOUT_EVALUATION"
    hypothetical_model_win_gross_yen_2022: int | None = None
    hypothetical_simple_form_win_gross_yen_2022: int | None = None
    hypothetical_model_win_roi_2022: float | None = None
    hypothetical_simple_form_win_roi_2022: float | None = None
    hypothetical_model_win_all_flat_adverse_missing_roi_2022: float | None = None
    hypothetical_model_minus_form_roi_2022: float | None = None
    hypothetical_paired_day_roi_ci95_lower: float | None = None
    hypothetical_paired_day_roi_ci95_upper: float | None = None
    independently_fitted_models: bool = True
    real_data_used_locally_only: bool = True
    retrospective_selected_outcomes_only: bool = True
    full_race_denominator_preserved: bool = True
    pre_off_roster_snapshots_verified: bool = False
    betting_odds_evaluated: bool = False
    independent_oos_2023_2024_opened: bool = False
    protected_final_holdout_opened: bool = False
    trained_model_exported: bool = False
    source_bytes_exported: bool = False
    actual_after_cost_roi_verified: bool = False
    positive_expected_value_demonstrated: bool = False


def _row(target: Any) -> dict[str, Any]:
    track, ymd, number = target.race_key
    try:
        d = date.fromisoformat(f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}")
    except (ValueError, TypeError):
        raise UnsafeNarSource("NAR_EXPLORATORY_RACE_DATE_INVALID") from None
    if not date(2017, 1, 1) <= d <= date(2022, 12, 31):
        raise UnsafeNarSource("NAR_EXPLORATORY_TRAINING_PERIOD_ONLY")
    f = target.feature
    if (type(target.target_win) is not int or target.target_win not in (0, 1)
            or type(target.target_place) is not int or target.target_place not in (0, 1)
            or type(target.target_top3) is not int or target.target_top3 not in (0, 1)
            or target.target_win > target.target_top3
            or not 0 <= f.prior_win_rate <= 1
            or not 0 <= f.prior_top3_rate <= 1
            or f.prior_starts < 0 or f.prior_wins > f.prior_starts):
        raise UnsafeNarSource("NAR_EXPLORATORY_FORM_OR_LABEL_INVALID")
    return {
        "race_id": f"NAR:{ymd}:{track}:{number:02d}",
        "race_day": d, "horse_number": target.horse_number,
        "past_starts": f.prior_starts,
        "past_win_rate": f.prior_win_rate,
        "past_top3_rate": f.prior_top3_rate,
        "past_mean_finish": (
            f.prior_mean_finish if f.prior_mean_finish is not None else float("nan")
        ),
        "days_since_last_start": (
            f.days_since_prior_start if f.days_since_prior_start is not None
            else float("nan")
        ),
        "__win": target.target_win,
        "__podium": target.target_top3,
        "__place": target.target_place,  # Actual paid place != numeric top-three.
    }


def _retrospective_two_ticket_decision(roi: float, descriptive_upper: float) -> str:
    """Decision about the tested 2022 policy, never prospective EV.

    On the 2022 selection sample, a negative day-bootstrap upper bound
    means the unconditional policy is unsuitable for deployment.
    The other branches are still insufficient to establish true EV.
    """
    if not isfinite(roi) or not isfinite(descriptive_upper):
        raise UnsafeNarSource("NAR_EXPLORATORY_DECISION_NONFINITE")
    if roi < 0 and descriptive_upper < 0:
        return "REJECT_UNCONDITIONAL_2022_POLICY"
    return "RETROSPECTIVE_INCONCLUSIVE_NO_POSITIVE_EV_PROOF"


def explore_nar_2017_2022_ranking_signal(
    batch: NarStatusAwareAsOfBatch,
    *, flat_races_by_year: dict[int, int],
    iterations: int = 40,
    official_win_payouts_2022: dict[str, dict[int, int]] | None = None,
    official_place_payouts_2022: dict[str, dict[int, int]] | None = None,
) -> NarExploratoryRankingMetrics:
    """Research-only; retrospectively selected complete labels aren't EV.

    Requires all 72 training/tuning months. Missing/cancelled races MUST
    remain in annual source denominators. No tuning on a future holdout.
    """
    if (not isinstance(batch, NarStatusAwareAsOfBatch)
            or batch.audit.months != 72
            or batch.audit.usable_for_training
            or batch.audit.independently_captured_preoff_roster
            or batch.audit.official_source_rights_verified
            or batch.audit.independent_oos_opened
            or batch.audit.positive_expected_value_demonstrated
            or not batch.targets
            or type(iterations) is not int or not 30 <= iterations <= 120
            or type(flat_races_by_year) is not dict
            or set(flat_races_by_year) != set(range(2017, 2023))
            or any(type(v) is not int or v <= 0 for v in flat_races_by_year.values())
            or sum(flat_races_by_year.values()) != batch.audit.source_flat_races
            or batch.audit.validated_flat_races
               + batch.audit.unresolved_flat_races != batch.audit.source_flat_races):
        raise UnsafeNarSource("NAR_EXPLORATORY_EXPLICIT_72_MONTH_DENOMINATOR_REQUIRED")

    # A validated race with some non-offered runners or DQ may have fewer
    # than four supervised entrants; mark it unevaluable, never invent bets.
    records = [_row(t) for t in batch.targets]
    frame = pd.DataFrame.from_records(records)
    if frame[["race_id", "horse_number"]].duplicated().any():
        raise UnsafeNarSource("NAR_EXPLORATORY_DUPLICATE_HORSE")
    groups = frame.groupby("race_id", sort=False)
    valid_ids = []
    unevaluable_validated = 0
    for rid, group in groups:
        n = len(group)
        if (n < 4 or n > 18 or group.race_day.nunique() != 1
                or group.horse_number.nunique() != n
                or group["__win"].sum() < 1
                or group["__win"].sum() > 3
                or group["__podium"].sum() < group["__win"].sum()):
            unevaluable_validated += 1
        else:
            valid_ids.append(rid)
    frame = frame.loc[frame.race_id.isin(valid_ids)].copy()
    fit = frame.loc[frame.race_day.lt(date(2022, 1, 1))].copy()
    tune = frame.loc[frame.race_day.ge(date(2022, 1, 1))].copy()
    n_fit, n_tune = fit.race_id.nunique(), tune.race_id.nunique()
    if n_fit < 5 or n_tune < 3:
        raise UnsafeNarSource("NAR_EXPLORATORY_INSUFFICIENT_WHOLE_RACES")
    if set(fit.race_id) & set(tune.race_id):
        raise UnsafeNarSource("NAR_EXPLORATORY_TEMPORAL_OVERLAP")

    # The after-event labels never appear in the inference dataframes.
    winner = CatBoostProbabilityModel(
        feature_columns=list(_FEATURES), iterations=iterations,
    )
    outsider = CatBoostProbabilityModel(
        feature_columns=list(_FEATURES), iterations=iterations,
    )
    winner.fit(fit, target_col="__win")
    outsider.fit(fit, target_col="__podium")
    if (winner.model is None or outsider.model is None
            or winner.model is outsider.model):
        raise UnsafeNarSource("NAR_EXPLORATORY_INDEPENDENT_MODELS_REQUIRED")
    no_label_features = tune[["race_id", "horse_number", *_FEATURES]].copy()
    win = winner.predict_win_probability(
        no_label_features, race_col="race_id",
    )
    out = outsider.predict_win_probability(
        no_label_features, race_col="race_id",
    )
    if (not win.index.equals(no_label_features.index)
            or not out.index.equals(no_label_features.index)
            or not np.isfinite(win.to_numpy(dtype=float)).all()
            or not np.isfinite(out.to_numpy(dtype=float)).all()):
        raise UnsafeNarSource("NAR_EXPLORATORY_SCORE_NOT_FINITE")
    scored = no_label_features[["race_id", "horse_number", "past_starts",
                                "past_win_rate"]].copy()
    scored["race_day"] = tune["race_day"]
    scored["win_prediction"] = win
    scored["outsider_prediction"] = out
    labels = tune.set_index(["race_id", "horse_number"])[["__win", "__podium", "__place"]]
    wins = overlap = outsiders = simple_wins = 0
    gross_model_win = gross_simple_win = 0
    payout_day_pairs: dict[date, list[tuple[int, int]]] = {}
    place_day_pairs: dict[date, list[int]] = {}
    gross_outsider_place = 0
    if official_place_payouts_2022 is not None and (
        official_win_payouts_2022 is None
        or type(official_place_payouts_2022) is not dict
        or not set(scored["race_id"]).issubset(official_place_payouts_2022)
    ):
        raise UnsafeNarSource("NAR_EXPLORATORY_PLACE_PAYOUT_COVERAGE_REQUIRED")
    if official_win_payouts_2022 is not None and (
        type(official_win_payouts_2022) is not dict
        or not set(scored["race_id"]).issubset(official_win_payouts_2022)
    ):
        raise UnsafeNarSource("NAR_EXPLORATORY_PAYOUT_COVERAGE_REQUIRED")
    random_expected = 0.0
    # Race days, not horses or individual races, are sampled in CI.
    # Purely descriptive post-hoc 2022 tuning uncertainty; not an
    # independent holdout significance test.
    race_day_paired_hits: dict[date, list[tuple[int, int]]] = {}
    for rid, g in scored.groupby("race_id", sort=False):
        g = g.sort_values(
            ["win_prediction", "horse_number"],
            ascending=[False, True], kind="stable",
        )
        top = g.horse_number.head(3).tolist()
        actual = labels.loc[rid]
        model_hit = int(actual.loc[top[0], "__win"] == 1)
        wins += model_hit
        # Explicit simple, odds-free comparator using strictly prior-day
        # form only: Beta-smoothed past win fraction (wins+1)/(starts+10).
        # No label, popularity or current result enters the choice.
        simple = g.copy()
        simple["smoothed_form"] = (
            simple["past_win_rate"] * simple["past_starts"] + 1.0
        ) / (simple["past_starts"] + 10.0)
        simple = simple.sort_values(
            ["smoothed_form", "horse_number"],
            ascending=[False, True], kind="stable",
        )
        simple_hit = int(actual.loc[int(simple.horse_number.iloc[0]), "__win"] == 1)
        simple_wins += simple_hit
        day = g["race_day"].iloc[0]
        if official_win_payouts_2022 is not None:
            amounts = official_win_payouts_2022[rid]
            horses = set(int(x) for x in g.horse_number)
            if type(amounts) is not dict or set(amounts) != horses:
                raise UnsafeNarSource("NAR_EXPLORATORY_PAYOUT_ROSTER_MISMATCH")
            for h in horses:
                amount = amounts[h]
                if (type(amount) is not int or amount < 0
                        or (amount >= 100) != (int(actual.loc[h, "__win"]) == 1)):
                    raise UnsafeNarSource("NAR_EXPLORATORY_PAYOUT_WIN_LABEL_MISMATCH")
            model_amount = amounts[int(top[0])]
            simple_amount = amounts[int(simple.horse_number.iloc[0])]
            gross_model_win += model_amount
            gross_simple_win += simple_amount
            payout_day_pairs.setdefault(day, []).append(
                (model_amount, simple_amount)
            )
        race_day_paired_hits.setdefault(day, []).append((model_hit, simple_hit))
        overlap += sum(int(actual.loc[h, "__podium"] == 1) for h in top)
        random_expected += float(actual["__win"].sum()) / len(g)
        other = g.loc[~g.horse_number.isin(top)].sort_values(
            ["outsider_prediction", "horse_number"],
            ascending=[False, True], kind="stable",
        )
        outsider_horse = int(other.horse_number.iloc[0])
        outsiders += int(actual.loc[outsider_horse, "__podium"] == 1)
        if official_place_payouts_2022 is not None:
            places = official_place_payouts_2022[rid]
            horses = set(int(x) for x in g.horse_number)
            if type(places) is not dict or set(places) != horses:
                raise UnsafeNarSource("NAR_EXPLORATORY_PLACE_ROSTER_MISMATCH")
            for h in horses:
                amount = places[h]
                if (type(amount) is not int or amount < 0
                        or (amount >= 100) != (int(actual.loc[h, "__place"]) == 1)):
                    raise UnsafeNarSource("NAR_EXPLORATORY_PLACE_LABEL_MISMATCH")
            amount = places[outsider_horse]
            gross_outsider_place += amount
            place_day_pairs.setdefault(day, []).append(amount)

    # Full 2022 flat-race denominator includes all unresolved races,
    # failed roster checks and known cancellation candidates. This wide
    # pessimistic bound cannot assert an actually offered bet.
    total2022 = flat_races_by_year[2022]
    unevaluable = total2022 - n_tune
    if (unevaluable < 0 or n_fit > sum(flat_races_by_year[y] for y in range(2017, 2022))
            or n_fit + n_tune > batch.audit.validated_flat_races):
        raise UnsafeNarSource("NAR_EXPLORATORY_DENOMINATOR_LEAK_OR_SELECTION")
    if sum(map(len, race_day_paired_hits.values())) != n_tune:
        raise UnsafeNarSource("NAR_EXPLORATORY_DAY_BOOTSTRAP_DENOMINATOR_INVALID")
    days = sorted(race_day_paired_hits)
    day_arrays = np.asarray([
        (len(race_day_paired_hits[d]),
         sum(a for a, _ in race_day_paired_hits[d]),
         sum(b for _, b in race_day_paired_hits[d]))
        for d in days
    ], dtype=np.float64)
    if not len(days) or not np.isfinite(day_arrays).all():
        raise UnsafeNarSource("NAR_EXPLORATORY_DAY_BOOTSTRAP_INVALID")
    # Fixed-seed, paired whole-day resampling. Confidence intervals from
    # the *tuning set* are descriptive only and must not be sold as OOS.
    rng = np.random.default_rng(20261109)
    draw = rng.integers(0, len(days), size=(1000, len(days)))
    boot = day_arrays[draw].sum(axis=1)
    paired_uplift = (boot[:, 1] - boot[:, 2]) / boot[:, 0]
    ci_low, ci_high = (float(x) for x in np.quantile(
        paired_uplift, [0.025, 0.975]
    ))
    historical_payouts_joined = official_win_payouts_2022 is not None
    economic = {}
    if historical_payouts_joined:
        if (len(payout_day_pairs) != len(days)
                or sum(map(len, payout_day_pairs.values())) != n_tune):
            raise UnsafeNarSource("NAR_EXPLORATORY_PAYOUT_DAY_COVERAGE_INVALID")
        money_days = np.asarray([
            (len(payout_day_pairs[d]),
             sum(a for a, _ in payout_day_pairs[d]),
             sum(b for _, b in payout_day_pairs[d]))
            for d in days
        ], dtype=np.float64)
        money_boot = money_days[draw].sum(axis=1)
        if not (money_boot[:, 0] > 0).all():
            raise UnsafeNarSource("NAR_EXPLORATORY_PAYOUT_BOOTSTRAP_INVALID")
        difference = (money_boot[:, 1] - money_boot[:, 2]) / (
            100.0 * money_boot[:, 0]
        )
        money_low, money_high = (
            float(x) for x in np.quantile(difference, [0.025, 0.975])
        )
        model_roi = gross_model_win / (100.0 * n_tune) - 1.0
        form_roi = gross_simple_win / (100.0 * n_tune) - 1.0
        adverse_roi = gross_model_win / (100.0 * total2022) - 1.0
        if (not all(isfinite(x) for x in (
            model_roi, form_roi, adverse_roi, money_low, money_high
        )) or money_low > money_high or adverse_roi > model_roi):
            raise UnsafeNarSource("NAR_EXPLORATORY_PAYOUT_METRICS_INVALID")
        economic = dict(
            hypothetical_model_win_gross_yen_2022=gross_model_win,
            hypothetical_simple_form_win_gross_yen_2022=gross_simple_win,
            hypothetical_model_win_roi_2022=model_roi,
            hypothetical_simple_form_win_roi_2022=form_roi,
            hypothetical_model_win_all_flat_adverse_missing_roi_2022=adverse_roi,
            hypothetical_model_minus_form_roi_2022=model_roi - form_roi,
            hypothetical_paired_day_roi_ci95_lower=money_low,
            hypothetical_paired_day_roi_ci95_upper=money_high,
        )
    if official_place_payouts_2022 is not None:
        if (len(place_day_pairs) != len(days)
                or sum(map(len, place_day_pairs.values())) != n_tune):
            raise UnsafeNarSource("NAR_EXPLORATORY_PLACE_DAY_COVERAGE_INVALID")
        combo_days = np.asarray([
            (len(place_day_pairs[d]),
             sum(a for a, _ in payout_day_pairs[d]),
             sum(place_day_pairs[d]))
            for d in days
        ], dtype=np.float64)
        paired_draw = combo_days[draw].sum(axis=1)
        combined_boot = (
            (paired_draw[:, 1] + paired_draw[:, 2])
            / (200.0 * paired_draw[:, 0]) - 1.0
        )
        combo_low, combo_high = (
            float(x) for x in np.quantile(combined_boot, [0.025, 0.975])
        )
        combo_roi = (gross_model_win + gross_outsider_place) / (200.0 * n_tune) - 1.0
        adverse_combo = (
            (gross_model_win + gross_outsider_place) / (200.0 * total2022) - 1.0
        )
        place_roi = gross_outsider_place / (100.0 * n_tune) - 1.0
        if (not all(isfinite(x) for x in (
            combo_roi, adverse_combo, place_roi, combo_low, combo_high
        )) or combo_low > combo_high or adverse_combo > combo_roi):
            raise UnsafeNarSource("NAR_EXPLORATORY_TWO_TICKET_METRICS_INVALID")
        combined_stake = 200 * n_tune
        combined_paid = gross_model_win + gross_outsider_place
        shortfall = max(0, combined_stake - combined_paid)
        needed = (combined_stake / combined_paid - 1.0
                  if combined_paid > 0 else None)
        economic.update(
            hypothetical_two_ticket_stake_yen_2022=combined_stake,
            hypothetical_two_ticket_paid_yen_2022=combined_paid,
            hypothetical_two_ticket_break_even_shortfall_yen_2022=shortfall,
            hypothetical_two_ticket_gross_uplift_needed_2022=needed,
            two_ticket_2022_research_decision=_retrospective_two_ticket_decision(
                combo_roi, combo_high,
            ),
            hypothetical_outsider_place_gross_yen_2022=gross_outsider_place,
            hypothetical_outsider_place_roi_2022=place_roi,
            hypothetical_two_ticket_roi_2022=combo_roi,
            hypothetical_two_ticket_all_flat_adverse_missing_roi_2022=adverse_combo,
            hypothetical_two_ticket_day_ci95_lower=combo_low,
            hypothetical_two_ticket_day_ci95_upper=combo_high,
        )
    nums = (
        wins / n_tune, random_expected / n_tune, wins / total2022,
        (wins + unevaluable) / total2022, overlap / (3 * n_tune),
        outsiders / n_tune,
    )
    if (not all(isfinite(x) and 0 <= x <= 1 for x in nums)
            or not all(isfinite(x) for x in (ci_low, ci_high))
            or ci_low > ci_high):
        raise UnsafeNarSource("NAR_EXPLORATORY_NONFINITE_METRIC")

    return NarExploratoryRankingMetrics(
        status="NAR_EXPLORATORY_2022_RANKING_ONLY_SELECTION_BIAS_HOLD",
        source_flat_races_2017_2022=batch.audit.source_flat_races,
        unresolved_flat_races_2017_2022=batch.audit.unresolved_flat_races,
        fit_races_2017_2021=n_fit,
        tune_races_2022=n_tune,
        unevaluable_tune_races_2022=unevaluable,
        fit_horses=len(fit), tune_horses=len(tune),
        winner_top1_hit_rate_2022=nums[0],
        random_baseline_top1_expected_2022=nums[1],
        smoothed_prior_win_baseline_top1_2022=simple_wins / n_tune,
        top1_uplift_over_simple_form_2022=(wins-simple_wins)/n_tune,
        top1_uplift_day_bootstrap_ci95_lower=ci_low,
        top1_uplift_day_bootstrap_ci95_upper=ci_high,
        independent_2022_race_days=len(days),
        winner_top1_worst_case_all_flat_2022=nums[2],
        winner_top1_best_case_all_flat_2022=nums[3],
        top3_picks_podium_precision_2022=nums[4],
        outsider_podium_hit_rate_2022=nums[5],
        historical_official_win_payouts_reconciled=historical_payouts_joined,
        historical_official_place_payouts_reconciled=official_place_payouts_2022 is not None,
        **economic,
    )
