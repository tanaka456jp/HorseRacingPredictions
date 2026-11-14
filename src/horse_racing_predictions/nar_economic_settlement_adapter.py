"""In-memory, private, settlement-only bridge to frozen-forecast evaluator.

This does NOT derive a pre-event prediction from an official finished-race
export. Actual economic evaluation also requires independently timestamped,
immutable forecasts made *before* the race and legally permitted input.
No network or file access, no save/export/posting, no EV claim.
"""
from __future__ import annotations

from .nar_official_zip_probe import UnsafeNarSource
from .nar_published_result_normalizer import NarInMemoryResult, RaceKey
from .oddsfree_ev_research import FinalRaceSettlement


def nar_canonical_race_id(key: RaceKey) -> str:
    """Private, deterministic NAR namespace (not JRA race keys)."""
    track, yyyymmdd, number = key
    if (not track or not isinstance(yyyymmdd, str)
            or len(yyyymmdd) != 8 or not isinstance(number, int)
            or not 1 <= number <= 20):
        raise UnsafeNarSource("NAR_EVALUATION_RACE_KEY_INVALID")
    return f"NAR:{yyyymmdd}:{track}:{number:02d}"


def to_nar_final_settlements(
    dataset: NarInMemoryResult,
) -> tuple[FinalRaceSettlement, ...]:
    """Convert *validated final outcomes* only, not forecast features."""
    if (not isinstance(dataset, NarInMemoryResult)
            or not dataset.audit.final_results_only
            or dataset.audit.pre_event_snapshot_verified
            or dataset.audit.authorized_for_model_training
            or not dataset.races
            or len(dataset.races) != dataset.audit.checked_races):
        raise UnsafeNarSource("NAR_INDEPENDENT_SETTLEMENT_REVIEW_REQUIRED")
    output = []
    ids = set()
    for race in dataset.races:
        key = nar_canonical_race_id(race.race_key)
        if key in ids:
            raise UnsafeNarSource("NAR_DUPLICATE_EVALUATION_RACE")
        ids.add(key)
        finish = {str(n): pos for n, pos in race.finish_by_number}
        wins = {str(n): yen for n, yen in race.win_return_by_number}
        places = {str(n): yen for n, yen in race.place_return_by_number}
        if not finish or set(finish) != set(wins) or set(finish) != set(places):
            raise UnsafeNarSource("NAR_SETTLEMENT_ROSTER_MISMATCH")
        output.append(FinalRaceSettlement(
            race_id=key,
            finishing_positions=finish,
            win_return_per_100_yen=wins,
            place_return_per_100_yen=places,
        ))
    return tuple(output)
