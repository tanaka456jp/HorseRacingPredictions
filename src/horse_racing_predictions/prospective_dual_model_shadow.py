"""Prospective JRA/NAR paper scorekeeper for TWO real, fitted CatBoost models.

No network, file writes, outcome access during inference, bets or publishing.
Callers must independently audit input provenance/coverage and persist a
private frozen snapshot before first off. A local clock is NOT a witness.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from math import isfinite
import re

import numpy as np
import pandas as pd

from .modeling import CatBoostProbabilityModel

_JST = timezone(timedelta(hours=9))
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_LEAD = timedelta(minutes=10)
_FORBIDDEN = re.compile(
    r"(^|_)(odds|popularity|payback|payout|dividend|finish_position|"
    r"is_winner|actual_rank|result|target|prize_money|market_price|"
    r"win_return|place_return)(_|$)", re.I,
)


class ProspectiveShadowHold(ValueError):
    """Static reason only; never expose private race/runner details."""


@dataclass(frozen=True)
class FrozenShadowRace:
    race_id: str
    off_utc: str
    roster: tuple[str, ...]
    top3: tuple[str, str, str]
    outsider: str
    top1_probability: float


@dataclass(frozen=True)
class FrozenModelShadow:
    schema: str
    jurisdiction: str
    race_day_jst: str
    generated_utc: str
    source_asof_utc: str
    model_trained_through: str
    model_sha256_declared: str
    races: tuple[FrozenShadowRace, ...]
    commitment_sha256: str
    verified_external_timestamp: bool = False
    verified_source_licence: bool = False
    real_bets: int = 0
    positive_expected_value_proven: bool = False


@dataclass(frozen=True)
class ShadowAccuracyAndReturn:
    status: str
    jurisdiction: str
    frozen_races: int
    outcome_complete_races: int
    top1_win_hits: int | None
    top1_win_hit_rate: float | None
    top3_numeric_podium_hits: int | None
    top3_numeric_podium_precision: float | None
    outsider_numeric_top3_hits: int | None
    outsider_numeric_top3_hit_rate: float | None
    stake_yen: int | None
    official_paper_returns_yen: int | None
    paper_roi_after_stake: float | None
    result_source_independently_verified: bool = False
    purchase_execution_verified: bool = False
    positive_expected_value_proven: bool = False
    real_bets: int = 0


def _utc(value: datetime) -> datetime:
    if (not isinstance(value, datetime) or value.utcoffset() is None):
        raise ProspectiveShadowHold("NAIVE_OR_INVALID_TIME")
    return value.astimezone(timezone.utc)


def freeze_fitted_dual_shadow(
    *, jurisdiction: str,
    race_day_jst: str,
    entries: pd.DataFrame,
    off_by_race: dict[str, datetime],
    winner: CatBoostProbabilityModel,
    outsider: CatBoostProbabilityModel,
    model_trained_through: str,
    model_sha256_declared: str,
    source_asof_utc: datetime,
    generated_utc: datetime,
) -> FrozenModelShadow:
    """Score a complete pre-event roster with *fitted* CatBoost model objects.

    The frame must be created from approved as-of-only features by a separate
    source adapter; passing an arbitrary CSV does NOT certify that claim.
    No post-event labels, popularity or quoted market prices are permitted.
    """
    gen = _utc(generated_utc)
    source = _utc(source_asof_utc)
    try:
        day = date.fromisoformat(race_day_jst)
        fitted_through = date.fromisoformat(model_trained_through)
    except (ValueError, TypeError) as exc:
        raise ProspectiveShadowHold("INVALID_MODEL_OR_RACE_DATE") from exc
    if (jurisdiction not in ("JRA", "NAR") or day.isoformat() != race_day_jst
            or fitted_through >= day or not source <= gen
            or source.astimezone(_JST).date() > day
            or gen.astimezone(_JST).date() != day
            or type(model_sha256_declared) is not str
            or not _SHA.fullmatch(model_sha256_declared)):
        raise ProspectiveShadowHold("INVALID_MODEL_OR_RACE_DATE")
    if (not isinstance(winner, CatBoostProbabilityModel)
            or not isinstance(outsider, CatBoostProbabilityModel)
            or winner is outsider or winner.model is None
            or outsider.model is None or winner.model is outsider.model):
        raise ProspectiveShadowHold("TWO_FITTED_NATIVE_MODELS_REQUIRED")
    fields = tuple(winner.feature_columns)
    if (not fields or fields != tuple(outsider.feature_columns)
            or any(type(c) is not str or _FORBIDDEN.search(c) for c in fields)):
        raise ProspectiveShadowHold("MODEL_FEATURE_SCHEMA_UNSAFE")
    if (not isinstance(entries, pd.DataFrame) or entries.empty
            or entries.columns.duplicated().any()
            or set(entries) != {"race_id", "horse_id", *fields}
            or entries[["race_id", "horse_id"]].isna().any().any()
            or entries.duplicated(["race_id", "horse_id"]).any()
            or not isinstance(off_by_race, dict)
            or not 1 <= len(off_by_race) <= 500):
        raise ProspectiveShadowHold("INCOMPLETE_OR_UNSAFE_FUTURE_ROSTER")
    if (any(type(v) is not str or not v.strip() or len(v) > 180
            for c in ("race_id", "horse_id") for v in entries[c])
            or set(entries["race_id"]) != set(off_by_race)
            or not entries.index.is_unique):
        raise ProspectiveShadowHold("INCOMPLETE_OR_UNSAFE_FUTURE_ROSTER")
    for rid, off in off_by_race.items():
        event = _utc(off)
        if (type(rid) is not str or not (rid.startswith("JRA-" + day.strftime("%Y%m%d") + "-") if jurisdiction == "JRA"
                        else rid.startswith("NAR:" + day.strftime("%Y%m%d") + ":"))
                or event.astimezone(_JST).date() != day
                or event <= gen + _LEAD):
            raise ProspectiveShadowHold("FROZEN_RACE_CALENDAR_INVALID")
    if (entries.groupby("race_id").size().lt(4).any()
            or entries.groupby("race_id").size().gt(18).any()):
        raise ProspectiveShadowHold("INCOMPLETE_OR_UNSAFE_FUTURE_ROSTER")
    try:
        pwin = winner.predict_win_probability(entries, race_col="race_id")
        ptop3 = outsider.predict_win_probability(entries, race_col="race_id")
    except (ValueError, KeyError, RuntimeError, TypeError) as exc:
        raise ProspectiveShadowHold("CATBOOST_INFERENCE_FAILED") from exc
    if any(
        not isinstance(scores, pd.Series) or not scores.index.equals(entries.index)
        or not np.isfinite(scores.to_numpy(dtype=float)).all()
        or scores.le(0).any()
        or not np.allclose(
            scores.groupby(entries["race_id"]).sum().to_numpy(dtype=float),
            1.0, atol=1e-9,
        )
        for scores in (pwin, ptop3)
    ):
        raise ProspectiveShadowHold("UNNORMALIZED_OR_INVALID_MODEL_SCORES")
    ranked = entries[["race_id", "horse_id"]].copy()
    ranked["__win"] = pwin
    ranked["__top3"] = ptop3
    frozen = []
    for rid in sorted(off_by_race):
        rows = ranked.loc[ranked["race_id"].eq(rid)]
        wins = rows.sort_values(
            ["__win", "horse_id"], ascending=[False, True], kind="stable",
        )
        ids = tuple(wins["horse_id"])
        top3 = tuple(ids[:3])
        eligible = rows.loc[~rows["horse_id"].isin(top3)]
        pick = eligible.sort_values(
            ["__top3", "horse_id"], ascending=[False, True], kind="stable",
        ).iloc[0]["horse_id"]
        frozen.append(FrozenShadowRace(
            race_id=rid,
            off_utc=_utc(off_by_race[rid]).isoformat(),
            roster=tuple(sorted(ids)),
            top3=top3,
            outsider=str(pick),
            top1_probability=float(wins.iloc[0]["__win"]),
        ))
    payload = {
        "schema": "HorseRacing.ProspectiveDualModelShadow.v1",
        "jurisdiction": jurisdiction, "race_day_jst": race_day_jst,
        "generated_utc": gen.isoformat(),
        "source_asof_utc": source.isoformat(),
        "model_trained_through": model_trained_through,
        "model_sha256_declared": model_sha256_declared,
        "races": [asdict(r) for r in frozen],
    }
    commitment = sha256(json.dumps(
        payload, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()
    return FrozenModelShadow(
        **{k: payload[k] for k in payload if k != "races"},
        races=tuple(frozen), commitment_sha256=commitment,
    )


def score_frozen_shadow(
    frozen: FrozenModelShadow, *,
    final_by_race: dict[str, dict],
) -> ShadowAccuracyAndReturn:
    """Audit all frozen races against REVIEWED official post-event outcomes.

    Input requires a full per-horse numeric finish map and selected WIN
    official payout per 100 yen. This cannot authenticate the source and
    never grants betting authorization. Any race absent/ambiguous => HOLD
    for the entire cohort (no profitable cherry-picked subset).
    """
    if (not isinstance(frozen, FrozenModelShadow)
            or not frozen.races or type(final_by_race) is not dict
            or set(final_by_race) != {r.race_id for r in frozen.races}):
        raise ProspectiveShadowHold("INCOMPLETE_OFFICIAL_SETTLEMENT_DENOMINATOR")
    hits = overlap = outsiders = returned = complete = 0
    for race in frozen.races:
        row = final_by_race[race.race_id]
        if type(row) is not dict or set(row) != {
            "finish_by_horse", "selected_top1_win_return_per_100_yen",
        }:
            break
        finishes = row["finish_by_horse"]
        amount = row["selected_top1_win_return_per_100_yen"]
        if (type(finishes) is not dict or set(finishes) != set(race.roster)
                or any(type(v) is not int or v < 1 or v > len(race.roster)
                       for v in finishes.values())
                or not any(v == 1 for v in finishes.values())
                or not any(v == 2 for v in finishes.values())
                or not any(v == 3 for v in finishes.values())
                or type(amount) is not int or not 0 <= amount <= 1_000_000):
            break
        win = finishes[race.top3[0]] == 1
        if (win and amount < 100) or (not win and amount != 0):
            break
        hits += int(win)
        overlap += sum(finishes[horse] <= 3 for horse in race.top3)
        outsiders += int(finishes[race.outsider] <= 3)
        returned += amount
        complete += 1
    ready = complete == len(frozen.races)
    stake = 100 * complete if ready else None
    return ShadowAccuracyAndReturn(
        status=("COMPLETE_DESCRIPTIVE_PROSPECTIVE_PAPER_NO_EV_PROOF"
                if ready else "HOLD_MISSING_OR_AMBIGUOUS_OFFICIAL_RESULTS"),
        jurisdiction=frozen.jurisdiction,
        frozen_races=len(frozen.races),
        outcome_complete_races=complete,
        top1_win_hits=hits if ready else None,
        top1_win_hit_rate=hits / complete if ready else None,
        top3_numeric_podium_hits=overlap if ready else None,
        top3_numeric_podium_precision=overlap / (3 * complete) if ready else None,
        outsider_numeric_top3_hits=outsiders if ready else None,
        outsider_numeric_top3_hit_rate=outsiders / complete if ready else None,
        stake_yen=stake,
        official_paper_returns_yen=returned if ready else None,
        paper_roi_after_stake=(returned - stake) / stake if ready else None,
    )
