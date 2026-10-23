"""Strict research-only sample preparation independent of market prices.

Does NOT train a model, prove public publication rights, authorize betting, or
access protected 2025-2026 holdout rows. Source must be independently approved.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re
from typing import Any

import pandas as pd

from .data_sources import COLUMN_ALIASES, NUMERIC_COLUMNS
from .features import build_pre_race_features

_MAX_RESEARCH_DAY = date(2024, 12, 31)
_MARKET = re.compile(
    r"win_odds|place_odds|market|betting|popularity|"
    r"odds|payout|dividend|投票|人気|配当|払戻|単勝|複勝",
    re.IGNORECASE,
)
_REQUIRED = {"race_id", "race_date", "horse_name", "finish_position"}


@dataclass(frozen=True)
class OddsFreeResearchSample:
    frame: pd.DataFrame
    features: tuple[str, ...]
    race_count: int
    runner_count: int
    cutoff: str
    market_columns_excluded: tuple[str, ...]


def prepare_strict_odds_free_training_sample(
    raw: pd.DataFrame, *, train_start: str, train_end: str,
) -> OddsFreeResearchSample:
    """Market-column perturbation must NEVER affect sample or feature values.

    Historical outcome ranks are training labels, not target-race features.
    Keeps complete distinct starter/result rows; never filters by win odds.
    """
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        raise ValueError("nonempty source frame required")
    try:
        start = date.fromisoformat(train_start)
        end = date.fromisoformat(train_end)
    except (TypeError, ValueError) as exc:
        raise ValueError("valid train_start/train_end required") from exc
    if start > end or end > _MAX_RESEARCH_DAY:
        raise ValueError("protected 2025-2026 holdout must not enter research training")
    if raw.columns.duplicated().any():
        raise ValueError("duplicate raw columns forbidden")
    # Drop *all* market fields before any row selection, normalization or
    # feature engineering. The same race/horse list is retained regardless of
    # the presence, distribution or missingness of market odds.
    market = tuple(str(c) for c in raw.columns if _MARKET.search(str(c)))
    input_frame = raw.drop(columns=list(market), errors="ignore")
    normalized: dict[str, Any] = {}
    for name, aliases in COLUMN_ALIASES.items():
        if name == "win_odds" or _MARKET.search(name):
            continue
        matching = [c for c in aliases if c in input_frame.columns]
        if matching:
            normalized[name] = input_frame[matching[0]]
    missing = _REQUIRED - set(normalized)
    if missing:
        raise ValueError("research sample lacks non-market race/date/horse/outcome columns")
    frame = pd.DataFrame(normalized)
    if frame.empty:
        raise ValueError("no entries after normalization")
    frame["race_date"] = pd.to_datetime(frame["race_date"], errors="raise")
    if frame["race_date"].dt.tz is not None:
        frame["race_date"] = frame["race_date"].dt.tz_convert("Asia/Tokyo").dt.tz_localize(None)
    frame = frame.loc[
        frame["race_date"].dt.date.between(start, end)
    ].copy()
    if frame.empty:
        raise ValueError("no eligible pre-holdout historical rows")
    if frame[["race_id", "race_date", "horse_name"]].isna().any().any():
        raise ValueError("race ID/date/horse identity missing")
    frame["race_id"] = frame["race_id"].astype(str)
    frame["horse_name"] = frame["horse_name"].astype(str)
    if (frame["horse_name"].str.strip().eq("").any() or
            frame["race_id"].str.strip().eq("").any()):
        raise ValueError("blank horse or race ID")
    if frame.duplicated(["race_id", "horse_name"]).any():
        raise ValueError("duplicate starter in a race")
    if frame.groupby("race_id")["race_date"].nunique().gt(1).any():
        raise ValueError("race ID assigned multiple dates")
    frame["finish_position"] = pd.to_numeric(
        frame["finish_position"], errors="raise"
    )
    if (frame["finish_position"].isna().any() or
            frame["finish_position"].le(0).any() or
            frame["finish_position"].mod(1).ne(0).any()):
        raise ValueError("incomplete or non-positive result labels")
    counts = frame.groupby("race_id")["horse_name"].transform("size")
    if counts.lt(4).any() or counts.gt(18).any():
        raise ValueError("implausible race field size; verify full starter roster")
    if frame["finish_position"].gt(counts).any():
        raise ValueError("finish exceeds race field size")
    winners = frame["finish_position"].eq(1).groupby(frame["race_id"]).sum()
    if not winners.eq(1).all():
        raise ValueError("each race must have exactly one winner")
    # Historical numeric inputs other than win_odds can be used if and only if
    # the pre-race feature builder permits them. Existing result-derived recent
    # form calculations use strictly preceding races, never same-race outcomes.
    for col in NUMERIC_COLUMNS - {"win_odds", "finish_position"}:
        if col in frame:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame = frame.reset_index(drop=True)
    engineered = build_pre_race_features(frame)
    if any(_MARKET.search(name) for name in engineered.feature_columns):
        raise ValueError("a market-derived model feature escaped elimination")
    # No market column should survive even in the unused feature frame.
    if any(_MARKET.search(name) for name in engineered.frame.columns):
        raise ValueError("market column escaped source projection")
    return OddsFreeResearchSample(
        frame=engineered.frame, features=engineered.feature_columns,
        race_count=int(frame["race_id"].nunique()),
        runner_count=len(frame), cutoff=train_end,
        market_columns_excluded=market,
    )
