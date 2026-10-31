"""Strict as-of-date NAR historical form, built only from earlier race days.

Input is already-authorized, decoded NAR *result* CSV text: racelist +
horselist. The finished target race's rank is a label stored separately,
never a model feature. Target odds/popularity, finishing time, final 3F,
same-day results, race-day weather, payouts and body-weight changes are
excluded from features. No source fetching, archives, disk writes or posting.

This creates *retrospectively reconstructed* pre-day features. It does not
prove a contemporaneous archived pre-off racecard or advance actual EV.
Reference: https://www.keiba.go.jp/pdf/manual/data_pdf_manual.pdf
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from statistics import mean
from typing import Mapping

from .nar_official_zip_probe import UnsafeNarSource
from .nar_published_result_normalizer import _parse, RaceKey


@dataclass(frozen=True)
class NarAsOfFeatures:
    prior_starts: int
    prior_wins: int
    prior_top3: int
    prior_win_rate: float
    prior_top3_rate: float
    prior_mean_finish: float | None
    days_since_prior_start: int | None


@dataclass(frozen=True)
class NarResearchTarget:
    race_key: RaceKey = field(repr=False)
    horse_key: tuple[str, str] = field(repr=False)
    horse_number: int
    race_day: str
    surface: str
    distance_m: int
    asof: NarAsOfFeatures
    # A separate label for offline training/evaluation; never in asof.
    final_finish_label: int = field(repr=False)


@dataclass(frozen=True)
class NarAsOfResearchBatch:
    status: str
    eligible_races: int
    target_runner_rows: int
    first_year: int
    last_year: int
    features_are_prior_day_only: bool = True
    target_result_entered_features: bool = False
    popularity_or_odds_used: bool = False
    contemporaneous_preoff_snapshot_proven: bool = False
    rights_verified_by_software: bool = False
    return_data: tuple[NarResearchTarget, ...] = field(repr=False, default=())


def _integer(cell: str, *, low: int, high: int) -> int:
    cell = cell.strip()
    if (not cell.isascii() or not cell.isdecimal()
            or len(cell) > 8):
        raise UnsafeNarSource("NAR_ASOF_INTEGER_INVALID")
    value = int(cell)
    if not low <= value <= high:
        raise UnsafeNarSource("NAR_ASOF_INTEGER_INVALID")
    return value


def _birthday(cell: str) -> str:
    raw = cell.strip()
    try:
        day = datetime.strptime(raw, "%Y%m%d").date()
    except ValueError:
        raise UnsafeNarSource("NAR_ASOF_HORSE_IDENTITY_UNVERIFIED") from None
    if day.strftime("%Y%m%d") != raw:
        raise UnsafeNarSource("NAR_ASOF_HORSE_IDENTITY_UNVERIFIED")
    return raw


def build_prior_day_features(
    snapshots: Mapping[str, Mapping[str, str]],
) -> NarAsOfResearchBatch:
    """Build strict chronological form from month -> official CSV texts.

    This function does not trust input order, does not infer a horse's ID
    from a name alone, and does not update its cumulative history until
    the *entire date* has been evaluated.
    """
    if (not isinstance(snapshots, Mapping)
            or not 1 <= len(snapshots) <= 120
            or any(set(files) != {"racelist", "horselist"}
                   for files in snapshots.values())):
        raise UnsafeNarSource("NAR_ASOF_MONTHLY_INPUT_REQUIRED")

    races: dict[RaceKey, tuple[str, int, str]] = {}
    runners: dict[RaceKey, list[tuple[tuple[str, str], int, int]]] = defaultdict(list)
    for month, files in snapshots.items():
        for key, row in _parse(files["racelist"], "racelist", month):
            if key in races:
                raise UnsafeNarSource("NAR_ASOF_DUPLICATE_RACE")
            if ("帯広" in key[0] or row[21].strip() not in {"芝", "ダート"}):
                raise UnsafeNarSource("NAR_ASOF_NON_FLAT_RACE")
            distance = _integer(row[23], low=100, high=5000)
            size = _integer(row[26], low=5, high=18)
            races[key] = (row[21].strip(), distance, str(size))
        for key, row in _parse(files["horselist"], "horselist", month):
            name = row[6].strip()
            if not name or len(name) > 100:
                raise UnsafeNarSource("NAR_ASOF_HORSE_IDENTITY_UNVERIFIED")
            identity = name, _birthday(row[10])
            number = _integer(row[5], low=1, high=18)
            finish = _integer(row[31], low=1, high=18)
            runners[key].append((identity, number, finish))
    if not races or set(races) != set(runners):
        raise UnsafeNarSource("NAR_ASOF_RACE_COVERAGE_MISMATCH")

    # Preflight every race before calculating even one training target.
    for key, entries in runners.items():
        size = int(races[key][2])
        if (len(entries) != size
                or len({row[1] for row in entries}) != size
                or len({row[0] for row in entries}) != size
                or {row[2] for row in entries} != set(range(1, size + 1))):
            raise UnsafeNarSource("NAR_ASOF_RESULT_ROSTER_INCOMPLETE")

    # Date is sorted explicitly, not the original record/source order.
    groups: dict[date, list[RaceKey]] = defaultdict(list)
    for key in races:
        groups[date.fromisoformat(
            f"{key[1][:4]}-{key[1][4:6]}-{key[1][6:]}"
        )].append(key)

    history: dict[tuple[str, str], list[tuple[date, int]]] = defaultdict(list)
    targets: list[NarResearchTarget] = []
    for current_day in sorted(groups):
        same_day: list[tuple[tuple[str, str], int]] = []
        for key in sorted(groups[current_day]):
            surface, distance, _ = races[key]
            for identity, number, target_finish in sorted(runners[key], key=lambda row: row[1]):
                prior = history.get(identity, [])
                starts = len(prior)
                wins = sum(rank == 1 for _, rank in prior)
                top3 = sum(rank <= 3 for _, rank in prior)
                last_day = max((day for day, _ in prior), default=None)
                if last_day is not None and last_day >= current_day:
                    raise UnsafeNarSource("NAR_ASOF_CHRONOLOGY_VIOLATION")
                feat = NarAsOfFeatures(
                    prior_starts=starts,
                    prior_wins=wins,
                    prior_top3=top3,
                    prior_win_rate=(wins / starts if starts else 0.0),
                    prior_top3_rate=(top3 / starts if starts else 0.0),
                    prior_mean_finish=(mean(rank for _, rank in prior) if prior else None),
                    days_since_prior_start=(
                        (current_day - last_day).days if last_day else None
                    ),
                )
                targets.append(NarResearchTarget(
                    race_key=key, horse_key=identity,
                    horse_number=number, race_day=current_day.isoformat(),
                    surface=surface, distance_m=distance,
                    asof=feat, final_finish_label=target_finish,
                ))
                same_day.append((identity, target_finish))
        # Day boundary: no intra-day race result can affect a prediction.
        for identity, rank in same_day:
            history[identity].append((current_day, rank))

    return NarAsOfResearchBatch(
        status="NAR_RETROSPECTIVE_PRIOR_DAY_FEATURES_NO_PREOFF_PROOF",
        eligible_races=len(races),
        target_runner_rows=len(targets),
        first_year=min(day.year for day in groups),
        last_year=max(day.year for day in groups),
        return_data=tuple(targets),
    )
