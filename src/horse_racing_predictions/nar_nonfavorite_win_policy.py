"""Outcome-blind preregistered NAR favorite-exclusion policy, private paper audit.

A: 100 JPY hypothetical WIN on every frozen top-ranked candidate.
B: same candidate ONLY if its independently observed pre-off market rank != 1.

NEVER use final popularity, final odds, or official dividends to choose B.
Incomplete pre-off popularity/price timestamps HOLD the WHOLE cohort's ROI;
missing races remain in the original denominator. This is a future
research tool, not a winning model, a trading order, or an EV proof.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from math import isfinite
from random import Random
from zoneinfo import ZoneInfo

_JST = ZoneInfo("Asia/Tokyo")
_MIN_LEAD = timedelta(minutes=10)
_MAX_SOURCE_AGE = timedelta(minutes=25)
_PAYOUT_STATUSES = frozenset({
    "FINISHED", "DNF_NO_REFUND", "EXCLUDED_REFUND",
    "SCRATCH_NOT_OFFERED", "RACE_CANCELLED_REFUND",
})


class NonfavoriteEvidenceHold(ValueError):
    """Only static, nonidentifying error codes leave the private evaluator."""


@dataclass(frozen=True)
class NonfavoriteWinRace:
    # Never disclose identifiers or quoted odds in a public log.
    race_id: str = field(repr=False)
    race_day_jst: str
    top_win_horse: str = field(repr=False)
    entrants: int
    forecast_frozen_utc: datetime
    hosted_forecast_receipt_utc: datetime | None
    scheduled_off_utc: datetime
    selected_preoff_popularity: int | None
    selected_preoff_win_odds: float | None
    official_market_source_utc: datetime | None
    locally_received_market_utc: datetime | None
    settlement_status: str
    official_win_return_per_100_yen: int | None


@dataclass(frozen=True)
class NonfavoriteWinAudit:
    status: str
    frozen_races: int
    evidence_complete_races: int
    missing_or_unverifiable_preoff_prices: int
    unresolved_settlements: int
    first_favorite_predictions: int
    nonfavorite_predictions: int
    selected_nonfavorite_bets: int
    full_policy_purchased_races: int | None
    nonfavorite_policy_excluded_races: int | None
    unoffered_races: int
    refunded_races: int
    full_policy_decided_tickets: int | None
    nonfavorite_policy_decided_tickets: int | None
    full_policy_win_hits: int | None
    nonfavorite_policy_win_hits: int | None
    full_policy_win_hit_rate: float | None
    nonfavorite_policy_win_hit_rate: float | None
    full_policy_paper_net_yen: int | None
    nonfavorite_policy_paper_net_yen: int | None
    full_policy_hypothetical_stake_yen: int | None
    full_policy_official_return_yen: int | None
    full_policy_paper_roi: float | None
    nonfavorite_policy_hypothetical_stake_yen: int | None
    nonfavorite_policy_official_return_yen: int | None
    nonfavorite_policy_paper_roi: float | None
    roi_change_percentage_points: float | None
    total_paper_net_change_yen: int | None
    evaluated_race_days: int
    day_clustered_descriptive_roi_difference_ci95: tuple[float, float] | None
    after_cost_positive_expected_value_proven: bool = False
    market_execution_verified: bool = False
    actual_tickets_purchased: bool = False
    source_records_exported: bool = False


def _utc(t: datetime | None) -> datetime | None:
    if (not isinstance(t, datetime) or t.tzinfo is None
            or t.utcoffset() is None):
        return None
    return t.astimezone(timezone.utc)


def _complete_preoff_price(r: NonfavoriteWinRace) -> bool:
    frozen = _utc(r.forecast_frozen_utc)
    witnessed = _utc(r.hosted_forecast_receipt_utc)
    source = _utc(r.official_market_source_utc)
    received = _utc(r.locally_received_market_utc)
    off = _utc(r.scheduled_off_utc)
    if None in (frozen, witnessed, source, received, off):
        return False
    # A witnessed model selection must predate the provider's market
    # snapshot itself, not merely the later local ZIP receipt.
    if not (frozen <= witnessed < source <= received < off - _MIN_LEAD
            and timedelta(0) <= received - source <= _MAX_SOURCE_AGE):
        return False
    if (source.astimezone(_JST).date().isoformat() != r.race_day_jst
            or received.astimezone(_JST).date().isoformat() != r.race_day_jst):
        return False
    rank = r.selected_preoff_popularity
    price = r.selected_preoff_win_odds
    return (type(rank) is int and 1 <= rank <= r.entrants
            and isinstance(price, (int, float))
            and not isinstance(price, bool)
            and isfinite(float(price)) and float(price) >= 1.0)


def _settled_amount(r: NonfavoriteWinRace) -> tuple[int, int] | None:
    if r.settlement_status not in _PAYOUT_STATUSES:
        return None
    amount = r.official_win_return_per_100_yen
    if r.settlement_status == "SCRATCH_NOT_OFFERED":
        return (0, 0) if amount is None else None
    if type(amount) is not int or amount < 0 or amount > 1_000_000:
        return None
    if r.settlement_status in ("EXCLUDED_REFUND", "RACE_CANCELLED_REFUND"):
        return (100, 100) if amount == 100 else None
    if r.settlement_status == "DNF_NO_REFUND":
        return (100, 0) if amount == 0 else None
    # FINISHED: official losing tickets pay zero, winners at least 100 yen.
    return (100, amount) if amount == 0 or amount >= 100 else None


def _roi(stake: int, paid: int) -> float:
    return (paid - stake) / stake


def _interval_by_day(
    daily: dict[str, tuple[int, int, int, int]],
) -> tuple[float, float] | None:
    # Purely descriptive 95% day-clustered bootstrap, NOT a multiple-test
    # corrected forward EV test, confidence in execution or a strategy GO.
    if len(daily) < 20:
        return None
    clusters = list(daily.values())
    draws = Random(20261119)
    values = []
    for _ in range(2000):
        picked = [clusters[draws.randrange(len(clusters))]
                  for _ in clusters]
        a_stake = sum(v[0] for v in picked)
        a_paid = sum(v[1] for v in picked)
        b_stake = sum(v[2] for v in picked)
        b_paid = sum(v[3] for v in picked)
        if a_stake and b_stake:
            values.append(_roi(b_stake, b_paid) - _roi(a_stake, a_paid))
    if len(values) < 1900:
        return None
    values.sort()
    return values[int(.025 * len(values))], values[int(.975 * len(values))]


def compare_nonfavorite_win_policies(
    frozen_race_days: dict[str, str],
    observations: list[NonfavoriteWinRace] | tuple[NonfavoriteWinRace, ...],
) -> NonfavoriteWinAudit:
    """Return safe aggregates only; full original preregistered scope required.

    Neither callers nor the software can cryptographically establish
    provider rights or a genuine independent witness from supplied JSON.
    A positive paper ROI remains exploratory and never authorizes betting.
    """
    if (type(frozen_race_days) is not dict or not frozen_race_days
            or not isinstance(observations, (tuple, list))
            or len(frozen_race_days) > 20000
            or any(type(k) is not str or not k.strip() or type(v) is not str
                   or len(v) != 10 for k, v in frozen_race_days.items())):
        raise NonfavoriteEvidenceHold("INVALID_FROZEN_RACE_MANIFEST")
    rows = {}
    for r in observations:
        if (not isinstance(r, NonfavoriteWinRace)
                or r.race_id not in frozen_race_days
                or r.race_id in rows):
            raise NonfavoriteEvidenceHold("UNREGISTERED_OR_DUPLICATE_OBSERVATION")
        if (not r.race_id.strip() or type(r.race_day_jst) is not str
                or frozen_race_days[r.race_id] != r.race_day_jst
                or type(r.top_win_horse) is not str
                or not r.top_win_horse.strip()
                or type(r.entrants) is not int
                or not 2 <= r.entrants <= 18):
            raise NonfavoriteEvidenceHold("FROZEN_RACE_ROSTER_MISMATCH")
        off = _utc(r.scheduled_off_utc)
        frozen = _utc(r.forecast_frozen_utc)
        if (off is None or frozen is None or frozen >= off - _MIN_LEAD
                or off.astimezone(_JST).date().isoformat() != r.race_day_jst):
            raise NonfavoriteEvidenceHold("INVALID_FROZEN_PREDICTION_TIME")
        rows[r.race_id] = r
    missing_count = len(set(frozen_race_days) - set(rows))
    price_missing = missing_count
    unresolved = missing_count
    favorite = other = 0
    full_stake = full_paid = filtered_stake = filtered_paid = 0
    a_decided = b_decided = a_wins = b_wins = 0
    daily: dict[str, tuple[int, int, int, int]] = {}
    for race_id in frozen_race_days:
        r = rows.get(race_id)
        if r is None:
            continue
        price_ok = _complete_preoff_price(r)
        if not price_ok:
            price_missing += 1
        settled = _settled_amount(r)
        if settled is None:
            unresolved += 1
        if not price_ok or settled is None:
            continue
        stake, paid = settled
        decided = r.settlement_status in ("FINISHED", "DNF_NO_REFUND")
        won = r.settlement_status == "FINISHED" and paid >= 100
        if decided:
            a_decided += 1
            a_wins += int(won)
            if r.selected_preoff_popularity != 1:
                b_decided += 1
                b_wins += int(won)
        if r.selected_preoff_popularity == 1:
            favorite += 1
            b_stake = b_paid = 0
        else:
            other += 1
            b_stake, b_paid = stake, paid
        full_stake += stake
        full_paid += paid
        filtered_stake += b_stake
        filtered_paid += b_paid
        ds = daily.get(r.race_day_jst, (0, 0, 0, 0))
        daily[r.race_day_jst] = (
            ds[0] + stake, ds[1] + paid,
            ds[2] + b_stake, ds[3] + b_paid,
        )
    valid = len(frozen_race_days) - price_missing - (
        # Count distinct unresolved-only rows; errors may overlap.
        sum(1 for r in rows.values()
            if _settled_amount(r) is None and _complete_preoff_price(r))
    )
    ready = (price_missing == 0 and unresolved == 0
             and full_stake > 0 and filtered_stake > 0)
    if ready:
        a_roi, b_roi = (_roi(full_stake, full_paid),
                        _roi(filtered_stake, filtered_paid))
        ci = _interval_by_day(daily)
    else:
        a_roi = b_roi = ci = None
    return NonfavoriteWinAudit(
        status=("COMPLETE_RETROSPECTIVE_PAPER_COMPARISON_NO_EV_PROOF"
                if ready else "HOLD_MISSING_PREOFF_EVIDENCE_OR_SETTLEMENT"),
        frozen_races=len(frozen_race_days),
        evidence_complete_races=max(0, valid),
        missing_or_unverifiable_preoff_prices=price_missing,
        unresolved_settlements=unresolved,
        first_favorite_predictions=favorite,
        nonfavorite_predictions=other,
        selected_nonfavorite_bets=(filtered_stake // 100 if ready else 0),
        full_policy_purchased_races=(full_stake // 100 if ready else None),
        nonfavorite_policy_excluded_races=(
            len(frozen_race_days) - filtered_stake // 100 if ready else None
        ),
        unoffered_races=sum(
            r.settlement_status == "SCRATCH_NOT_OFFERED" for r in rows.values()
        ),
        refunded_races=sum(
            r.settlement_status in ("EXCLUDED_REFUND", "RACE_CANCELLED_REFUND")
            for r in rows.values()
        ),
        full_policy_decided_tickets=(a_decided if ready else None),
        nonfavorite_policy_decided_tickets=(b_decided if ready else None),
        full_policy_win_hits=(a_wins if ready else None),
        nonfavorite_policy_win_hits=(b_wins if ready else None),
        full_policy_win_hit_rate=(
            a_wins / a_decided if ready and a_decided else None
        ),
        nonfavorite_policy_win_hit_rate=(
            b_wins / b_decided if ready and b_decided else None
        ),
        full_policy_paper_net_yen=(
            full_paid - full_stake if ready else None
        ),
        nonfavorite_policy_paper_net_yen=(
            filtered_paid - filtered_stake if ready else None
        ),
        full_policy_hypothetical_stake_yen=full_stake if ready else None,
        full_policy_official_return_yen=full_paid if ready else None,
        full_policy_paper_roi=a_roi,
        nonfavorite_policy_hypothetical_stake_yen=filtered_stake if ready else None,
        nonfavorite_policy_official_return_yen=filtered_paid if ready else None,
        nonfavorite_policy_paper_roi=b_roi,
        roi_change_percentage_points=(100 * (b_roi - a_roi)
                                      if ready else None),
        total_paper_net_change_yen=(
            (filtered_paid - filtered_stake) - (full_paid - full_stake)
            if ready else None
        ),
        evaluated_race_days=len(daily),
        day_clustered_descriptive_roi_difference_ci95=ci,
    )
