"""Research-only price-independent Top3+outsider economic evaluation.

Selection is frozen before the race with NO prices. Only later are final
100-yen payouts joined by race and horse ID. Payouts must never be passed to
select_top3_and_outsider. All dates precede 2025 final holdout. This module
does NOT claim positive expected value, permit betting, train, or publish.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from math import isfinite
import random
from typing import Mapping, Sequence


@dataclass(frozen=True)
class FrozenOddsFreeForecast:
    race_id: str
    race_day: str
    post_time_utc: datetime
    predicted_at_utc: datetime
    model_ref: str
    model_fit_through_day: str
    winner_scores: Mapping[str, float]
    outsider_scores: Mapping[str, float]
    odds_used_in_selection: bool = False


@dataclass(frozen=True)
class FinalRaceSettlement:
    race_id: str
    finishing_positions: Mapping[str, int]
    # Final (not forecast-time) payments, inclusive of original 100-yen stake.
    # Zero is required for losing bets. No observed odds are accepted.
    win_return_per_100_yen: Mapping[str, int]
    place_return_per_100_yen: Mapping[str, int]


@dataclass(frozen=True)
class FrozenFour:
    race_id: str
    top3: tuple[str, str, str]
    outsider: str
    model_ref: str


@dataclass(frozen=True)
class OddsFreeEconomicResearch:
    status: str
    races: int
    wagers_per_race: int
    top1_win_stake_yen: int
    top1_win_return_yen: int
    top1_win_roi: float
    outsider_place_stake_yen: int
    outsider_place_return_yen: int
    outsider_place_roi: float
    combined_stake_yen: int
    combined_return_yen: int
    combined_realized_roi: float
    combined_bootstrap_95_lower_roi: float | None
    combined_bootstrap_95_upper_roi: float | None
    independent_race_days: int
    bootstrap_unit: str
    bootstrap_interval_available: bool
    podium_overlap_rate: float
    outsider_podium_hit_rate: float
    positive_expected_value_demonstrated: bool = False
    real_source_rights_verified: bool = False
    protected_final_holdout_opened: bool = False
    publication_authorized: bool = False


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("UTC_AWARE_FORECAST_TIMESTAMPS_REQUIRED")
    return value.astimezone(timezone.utc)


def select_top3_and_outsider(forecast: FrozenOddsFreeForecast) -> FrozenFour:
    """The immutable selection API deliberately has NO payout/odds input."""
    if not isinstance(forecast, FrozenOddsFreeForecast):
        raise ValueError("FROZEN_FORECAST_REQUIRED")
    try:
        day = date.fromisoformat(forecast.race_day)
    except (TypeError, ValueError) as exc:
        raise ValueError("RESEARCH_DAY_REQUIRED") from exc
    if day.isoformat() != forecast.race_day or day >= date(2025, 1, 1):
        raise ValueError("PROTECTED_FINAL_HOLDOUT_FORBIDDEN")
    try:
        last_fit = date.fromisoformat(forecast.model_fit_through_day)
    except (TypeError, ValueError) as exc:
        raise ValueError("FROZEN_MODEL_FIT_DATE_REQUIRED") from exc
    if last_fit.isoformat() != forecast.model_fit_through_day or last_fit >= day:
        raise ValueError("MODEL_MUST_BE_FROZEN_BEFORE_TARGET_RACE")
    if (not isinstance(forecast.race_id, str) or not forecast.race_id
            or not isinstance(forecast.model_ref, str)
            or not forecast.model_ref.strip()
            or forecast.odds_used_in_selection):
        raise ValueError("UNFROZEN_OR_MARKET_DEPENDENT_FORECAST")
    issued = _utc(forecast.predicted_at_utc)
    off = _utc(forecast.post_time_utc)
    if not issued < off or off.astimezone(timezone(timedelta(hours=9))).date() != day:
        raise ValueError("FORECAST_MUST_PRECEDE_RACE_OFF")
    winner = forecast.winner_scores
    outsider = forecast.outsider_scores
    if (not isinstance(winner, Mapping) or not isinstance(outsider, Mapping)
            or not 4 <= len(winner) <= 18
            or set(winner) != set(outsider)
            or not all(isinstance(k, str) and k.strip() for k in winner)):
        raise ValueError("COMPLETE_MATCHING_FIELD_REQUIRED")
    for scores in (winner, outsider):
        if any(type(v) not in (float, int)
               or not isfinite(v) or v < 0 for v in scores.values()):
            raise ValueError("NONFINITE_OR_NEGATIVE_MODEL_SCORE")
        if sum(scores.values()) <= 0:
            raise ValueError("MODEL_SCORES_ALL_ZERO")
    top = tuple(sorted(winner, key=lambda h: (-winner[h], h))[:3])
    remaining = set(winner).difference(top)
    other = min(remaining, key=lambda h: (-outsider[h], h))
    return FrozenFour(
        race_id=forecast.race_id,
        top3=top, outsider=other, model_ref=forecast.model_ref,
    )


def _quantile(sorted_values: list[float], proportion: float) -> float:
    index = (len(sorted_values) - 1) * proportion
    low = int(index)
    high = min(low + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (index - low)


def _race_result(pick: FrozenFour, final: FinalRaceSettlement) -> tuple[int, int, float, float]:
    if pick.race_id != final.race_id:
        raise ValueError("RACE_SETTLEMENT_ID_MISMATCH")
    ranks = final.finishing_positions
    if (not isinstance(ranks, Mapping) or not 5 <= len(ranks) <= 18
            or any(type(i) is not int or i < 1 or i > len(ranks)
                   for i in ranks.values())
            or len(set(ranks.values())) != len(ranks)
            or set(ranks.values()) != set(range(1, len(ranks) + 1))):
        raise ValueError("FINAL_RESULTS_INCOMPLETE_OR_DUPLICATED")
    for mapping in (final.win_return_per_100_yen, final.place_return_per_100_yen):
        if not isinstance(mapping, Mapping) or set(mapping) != set(ranks):
            raise ValueError("FINAL_PAYOUT_FIELD_INCOMPLETE")
        if any(type(v) is not int or v < 0 for v in mapping.values()):
            raise ValueError("INVALID_YEN_PAYOUT")
    if not set(pick.top3 + (pick.outsider,)).issubset(ranks):
        raise ValueError("PREDICTED_HORSE_MISSING_FROM_RESULT")
    # Official JRA rules: place tickets are not sold for <=4 starters;
    # 5-7 starters pay first two; 8+ pay first three.
    place_cutoff = 2 if len(ranks) <= 7 else 3
    if (any((ranks[h] != 1) != (final.win_return_per_100_yen[h] == 0)
            for h in ranks)
            or any((ranks[h] > place_cutoff) !=
                   (final.place_return_per_100_yen[h] == 0)
                   for h in ranks)):
        raise ValueError("PAYOUT_CONTRADICTS_FINAL_FINISH")
    if (any(v < 100 for v in final.win_return_per_100_yen.values() if v)
            or any(v < 100 for v in final.place_return_per_100_yen.values() if v)):
        raise ValueError("WINNING_PAYOUT_BELOW_STAKE")
    selected_win = final.win_return_per_100_yen[pick.top3[0]]
    selected_place = final.place_return_per_100_yen[pick.outsider]
    coverage = sum(ranks[h] <= 3 for h in pick.top3) / 3.0
    outsider_hit = float(ranks[pick.outsider] <= 3)
    return selected_win, selected_place, coverage, outsider_hit


def evaluate_frozen_oddsfree_economics(
    forecasts: Sequence[FrozenOddsFreeForecast],
    settlements: Sequence[FinalRaceSettlement],
    *,
    bootstrap_samples: int = 1000,
) -> OddsFreeEconomicResearch:
    """Equal 100-yen top1-win and outsider-place stakes, race-bootstrap CI.

    Settled final returns are only used *after* the frozen model selections.
    A positive realized ROI or favorable CI cannot alone establish future EV.
    """
    if (not isinstance(forecasts, (list, tuple))
            or not isinstance(settlements, (list, tuple))
            or not 1 <= len(forecasts) <= 20000
            or len(forecasts) != len(settlements)
            or not 200 <= bootstrap_samples <= 5000):
        raise ValueError("MATCHING_BOUNDED_RESEARCH_RACE_SAMPLES_REQUIRED")
    choices = [select_top3_and_outsider(f) for f in forecasts]
    by_id = {s.race_id: s for s in settlements}
    fields_by_id = {
        f.race_id: set(f.winner_scores) for f in forecasts
    }
    if any(
        set(settlement.finishing_positions) != fields_by_id.get(settlement.race_id)
        for settlement in settlements
    ):
        raise ValueError("FROZEN_FORECAST_VS_FINAL_FIELD_MISMATCH")
    if (len({f.race_id for f in forecasts}) != len(forecasts)
            or len(by_id) != len(settlements)
            or set(by_id) != {p.race_id for p in choices}):
        raise ValueError("DUPLICATE_OR_MISSING_SETTLEMENT")
    if len({f.model_ref for f in forecasts}) != 1:
        raise ValueError("FROZEN_SINGLE_MODEL_VERSION_REQUIRED")
    results = [_race_result(p, by_id[p.race_id]) for p in choices]
    n = len(results)
    win = sum(r[0] for r in results)
    place = sum(r[1] for r in results)
    # Avoid treating multiple races on the same calendar day as
    # statistically independent. Resample WHOLE racing DAYS (block
    # bootstrap), and refuse to display a bogus narrow interval if fewer
    # than ten genuinely distinct held-out days exist.
    by_day: dict[str, list[int]] = {}
    for forecast, outcome in zip(forecasts, results, strict=True):
        by_day.setdefault(forecast.race_day, []).append(outcome[0] + outcome[1])
    distinct_days = len(by_day)
    lower = upper = None
    if distinct_days >= 10:
        blocks = [(sum(v), len(v)) for _, v in sorted(by_day.items())]
        rng = random.Random(20241027)
        sampled_roi: list[float] = []
        for _ in range(bootstrap_samples):
            gross = stakes_in_hundreds = 0
            for _ in range(distinct_days):
                daily_gross, races_on_day = blocks[rng.randrange(distinct_days)]
                gross += daily_gross
                stakes_in_hundreds += 2 * races_on_day
            sampled_roi.append(gross / (100 * stakes_in_hundreds) - 1)
        sampled_roi.sort()
        lower = _quantile(sampled_roi, .025)
        upper = _quantile(sampled_roi, .975)
    return OddsFreeEconomicResearch(
        status="RESEARCH_ONLY_REALIZED_RETURNS_NOT_EXPECTED_VALUE",
        races=n, wagers_per_race=2,
        top1_win_stake_yen=100 * n,
        top1_win_return_yen=win,
        top1_win_roi=win / (100 * n) - 1,
        outsider_place_stake_yen=100 * n,
        outsider_place_return_yen=place,
        outsider_place_roi=place / (100 * n) - 1,
        combined_stake_yen=200 * n,
        combined_return_yen=win + place,
        combined_realized_roi=(win + place) / (200 * n) - 1,
        combined_bootstrap_95_lower_roi=lower,
        combined_bootstrap_95_upper_roi=upper,
        independent_race_days=distinct_days,
        bootstrap_unit="race_day",
        bootstrap_interval_available=distinct_days >= 10,
        podium_overlap_rate=sum(r[2] for r in results) / n,
        outsider_podium_hit_rate=sum(r[3] for r in results) / n,
    )
