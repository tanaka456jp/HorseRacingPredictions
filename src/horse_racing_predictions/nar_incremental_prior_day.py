"""Memory-bounded monthly NAR prior-day form reconstruction.

This is for *already permission-cleared*, locally decoded month-at-a-time
official NAR race/horse CSV text. Do not retain all monthly CSVs in memory.
Historical form requires only (starts, wins, podiums, rank-sum, last date)
per horse. In-sample finish labels are kept separate from features.

Each whole month is parsed/validated before advancing historical state.
Every race on the same date receives features from previous *dates* only;
history is updated after all races on that date are projected. No network,
JRA-VAN, files, pre-off snapshot claim, market inputs or publication.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Mapping

from .nar_official_zip_probe import UnsafeNarSource
from .nar_published_result_normalizer import _parse, RaceKey, _competition_rank_sequence
from .nar_prior_day_features import (
    NarAsOfFeatures, NarAsOfResearchBatch, NarResearchTarget,
    _birthday, _integer,
)

_MAX_TARGET_ROWS = 1_000_000
_MAX_MONTHS = 120


@dataclass(slots=True)
class _Aggregate:
    starts: int = 0
    wins: int = 0
    top3: int = 0
    rank_sum: int = 0
    last_date: date | None = None


def build_prior_day_features_month_by_month(
    monthly_source: Iterable[tuple[str, Mapping[str, str]]],
) -> NarAsOfResearchBatch:
    """Consume 1 valid flat-race month at a time, chronological and complete.

    Callers must separately check all official payouts and preregistered
    exclusions before passing a month. A historical final entry list does
    NOT prove that list was available at the original forecast deadline.
    """
    aggregate: dict[tuple[str, str], _Aggregate] = {}
    targets: list[NarResearchTarget] = []
    previous_month = ""
    previous_day: date | None = None
    first_day: date | None = None
    n_months = n_races = 0

    for month, files in monthly_source:
        if (not isinstance(month, str) or len(month) != 6
                or not month.isascii() or not month.isdecimal()
                or not 1998 <= int(month[:4]) <= 2024
                or not 1 <= int(month[4:]) <= 12
                or month <= previous_month
                or not isinstance(files, Mapping)
                or set(files) != {"racelist", "horselist"}):
            raise UnsafeNarSource("NAR_INCREMENTAL_MONTH_ORDER_OR_SCHEMA_INVALID")
        n_months += 1
        if n_months > _MAX_MONTHS:
            raise UnsafeNarSource("NAR_INCREMENTAL_TOO_MANY_MONTHS")

        races: dict[RaceKey, tuple[str, int, int]] = {}
        entrants: dict[RaceKey, list[tuple[tuple[str, str], int, int]]] = defaultdict(list)
        for key, row in _parse(files["racelist"], "racelist", month):
            if key in races:
                raise UnsafeNarSource("NAR_ASOF_DUPLICATE_RACE")
            if ("帯広" in key[0] or row[21].strip() not in ("芝", "ダート")):
                raise UnsafeNarSource("NAR_ASOF_NON_FLAT_RACE")
            races[key] = (
                row[21].strip(),
                _integer(row[23], low=100, high=5000),
                _integer(row[26], low=5, high=18),
            )

        for key, row in _parse(files["horselist"], "horselist", month):
            name = row[6].strip()
            if not name or len(name) > 100:
                raise UnsafeNarSource("NAR_ASOF_HORSE_IDENTITY_UNVERIFIED")
            identity = (name, _birthday(row[10]))
            number = _integer(row[5], low=1, high=18)
            finish = _integer(row[31], low=1, high=18)
            entrants[key].append((identity, number, finish))

        if not races or set(races) != set(entrants):
            raise UnsafeNarSource("NAR_ASOF_RACE_COVERAGE_MISMATCH")

        # Validate ALL month rosters before adding any of their results.
        for key, horses in entrants.items():
            size = races[key][2]
            if (len(horses) != size
                    or len({entry[0] for entry in horses}) != size
                    or len({entry[1] for entry in horses}) != size
                    or _competition_rank_sequence([entry[2] for entry in horses])
                  not in {"COMPLETE", "DEAD_HEAT"}):
                raise UnsafeNarSource("NAR_ASOF_RESULT_ROSTER_INCOMPLETE")

        by_day: dict[date, list[RaceKey]] = defaultdict(list)
        for key in races:
            raw = key[1]
            by_day[date.fromisoformat(
                f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
            )].append(key)

        for current_day in sorted(by_day):
            if previous_day is not None and current_day <= previous_day:
                raise UnsafeNarSource("NAR_INCREMENTAL_DATE_NOT_INCREASING")
            if first_day is None:
                first_day = current_day
            updates: list[tuple[tuple[str, str], int]] = []
            seen_today: set[tuple[str, str]] = set()
            for key in sorted(by_day[current_day]):
                surface, distance, _ = races[key]
                for identity, number, finish in sorted(
                    entrants[key], key=lambda h: h[1]
                ):
                    if identity in seen_today:
                        raise UnsafeNarSource("NAR_ASOF_SAME_HORSE_TWICE_ONE_DAY")
                    seen_today.add(identity)
                    prior = aggregate.get(identity, _Aggregate())
                    if prior.last_date is not None and prior.last_date >= current_day:
                        raise UnsafeNarSource("NAR_ASOF_CHRONOLOGY_VIOLATION")
                    starts = prior.starts
                    features = NarAsOfFeatures(
                        prior_starts=starts,
                        prior_wins=prior.wins,
                        prior_top3=prior.top3,
                        prior_win_rate=prior.wins / starts if starts else 0.0,
                        prior_top3_rate=prior.top3 / starts if starts else 0.0,
                        prior_mean_finish=(
                            prior.rank_sum / starts if starts else None
                        ),
                        days_since_prior_start=(
                            (current_day - prior.last_date).days
                            if prior.last_date else None
                        ),
                    )
                    targets.append(NarResearchTarget(
                        race_key=key, horse_key=identity,
                        horse_number=number, race_day=current_day.isoformat(),
                        surface=surface, distance_m=distance,
                        asof=features, final_finish_label=finish,
                    ))
                    if len(targets) > _MAX_TARGET_ROWS:
                        raise UnsafeNarSource("NAR_INCREMENTAL_TARGET_MEMORY_LIMIT")
                    updates.append((identity, finish))

            # Delayed update is essential for same-date information isolation.
            for identity, finish in updates:
                item = aggregate.setdefault(identity, _Aggregate())
                item.starts += 1
                item.wins += int(finish == 1)
                item.top3 += int(finish <= 3)
                item.rank_sum += finish
                item.last_date = current_day
            previous_day = current_day
        n_races += len(races)
        previous_month = month

    if not n_months or first_day is None or previous_day is None:
        raise UnsafeNarSource("NAR_INCREMENTAL_NO_RESEARCH_RACES")
    return NarAsOfResearchBatch(
        status="NAR_RETROSPECTIVE_PRIOR_DAY_FEATURES_NO_PREOFF_PROOF",
        eligible_races=n_races,
        target_runner_rows=len(targets),
        first_year=first_day.year,
        last_year=previous_day.year,
        return_data=tuple(targets),
    )
