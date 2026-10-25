"""Actual dual CatBoost Friday preview before Sunday's usual Saturday draw.

No fabricated horse numbers, estimated odds, race-day weights/conditions, or
published note. Produces only anonymous digest/counts for private research.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import re

import numpy as np
import pandas as pd

from .dual_candidate_private_preview import LoadedDualResearchCandidate
from .feature_window import align_history_to_training_start
from .friday_predraw_features import assert_friday_predraw_feature_list
from .inference import build_future_feature_frame, predict_future_entries
from .sunday_ai_research import _canonical_model_output_sha256, _market_column

_JST = timezone(timedelta(hours=9))
_FORBIDDEN_OUTCOME = frozenset({
    "finish_position", "is_winner", "finish_time", "last_3f", "margin",
    "prize_money", "corner_1", "corner_2", "corner_3", "corner_4",
    "predicted_win_probability", "upside_score", "manual_rank",
})


def private_friday_predraw_dual_preview(
    candidate: LoadedDualResearchCandidate, *,
    history: pd.DataFrame, entries: pd.DataFrame,
    expected_race_ids: tuple[str, ...], race_date: str,
    observed_at: datetime,
) -> dict:
    """True train-only candidate inference, NOT an authorized forecast."""
    if not isinstance(candidate, LoadedDualResearchCandidate):
        raise ValueError("saved pair of real independent CatBoost models required")
    assert_friday_predraw_feature_list(candidate.features)
    if (not isinstance(observed_at, datetime)
            or observed_at.utcoffset() is None):
        raise ValueError("timezone-aware research timestamp required")
    day = date.fromisoformat(race_date)
    if (day.weekday() != 6 or day.isoformat() != race_date
            or observed_at.astimezone(_JST).date() != day - timedelta(days=2)):
        raise ValueError("Friday-only before-Sunday-draw research")
    frozen_at = datetime.fromisoformat(
        candidate.generated_at.replace("Z", "+00:00")
    )
    if (frozen_at.utcoffset() is None or frozen_at > observed_at
            or date.fromisoformat(candidate.train_end) > date(2024, 12, 31)):
        raise ValueError("real fitted model must be frozen before Friday issue")
    if (not isinstance(history, pd.DataFrame) or history.empty
            or not isinstance(entries, pd.DataFrame) or entries.empty
            or history.columns.duplicated().any()
            or entries.columns.duplicated().any()):
        raise ValueError("complete reviewed history/entries required")
    required = {"race_id", "race_date", "horse_name"}
    if not required.issubset(entries):
        raise ValueError("pre-draw Sunday entrants must be identified")
    if (any(_market_column(c) for c in entries.columns)
            or any(entries[k].notna().any()
                   for k in entries.columns if k in _FORBIDDEN_OUTCOME)):
        raise ValueError("market or outcome leakage in Friday entrants")
    date_now = observed_at.astimezone(_JST).date()
    hist_dates = pd.to_datetime(history["race_date"], errors="raise")
    entry_dates = pd.to_datetime(entries["race_date"], errors="raise")
    if (hist_dates.isna().any() or entry_dates.isna().any()
            or entry_dates.dt.date.ne(day).any()
            or hist_dates.max().date() >= date_now
            or (day - hist_dates.max().date()).days > 14):
        raise ValueError("missing/stale or post-Friday historical form")
    if (not isinstance(expected_race_ids, tuple)
            or len(expected_race_ids) not in (12, 24, 36)
            or len(set(expected_race_ids)) != len(expected_race_ids)):
        raise ValueError("complete scheduled Sunday race IDs required")
    expected_pattern = re.compile(
        r"JRA-" + race_date.replace("-", "") +
        r"-(SAPPORO|HAKODATE|FUKUSHIMA|NIIGATA|NAKAYAMA|TOKYO|CHUKYO|KYOTO|HANSHIN|KOKURA)"
        r"-(0[1-9]|1[0-2])\Z"
    )
    by_course: dict[str, set[int]] = {}
    for rid in expected_race_ids:
        match = expected_pattern.fullmatch(rid)
        if match is None:
            raise ValueError("future manifest has fake/noncanonical race ID")
        by_course.setdefault(match.group(1), set()).add(int(match.group(2)))
    if (len(by_course) != len(expected_race_ids) // 12
            or any(n != set(range(1, 13)) for n in by_course.values())):
        raise ValueError("full twelve-race manifests required")
    if set(entries["race_id"]) != set(expected_race_ids):
        raise ValueError("missing Sunday race or unexpected extra race")
    if (entries[["race_id", "horse_name"]].isna().any().any()
            or entries["horse_name"].astype(str).str.strip().eq("").any()
            or entries.duplicated(["race_id", "horse_name"]).any()):
        raise ValueError("blank or duplicated Friday horse identity")
    counts = entries.groupby("race_id")["horse_name"].transform("size")
    if counts.lt(4).any() or counts.gt(18).any():
        raise ValueError("incomplete or implausible official Friday starter list")
    # Remove any pre-announced exceptional-GI draw numbers as well, preserving
    # one uniform, strictly draw-free model across all races. Never fill -1
    # or invent a numbered order.
    clean_entries = entries.drop(columns=[
        "post_position", "horse_weight", "horse_weight_delta",
        "weather", "track_condition",
    ], errors="ignore")
    nonmarket_history = history.drop(columns=[
        k for k in history.columns if _market_column(k)
    ])
    winner = type("PrivateResearchProxy", (), {})()
    winner.model = candidate.winner
    winner.manifest = type("ResearchManifest", (), {
        "model_version": "strict-oddsfree-friday-predraw-research",
        "experiment_id": "friday-dual-predraw-private",
        "train_start": candidate.train_start,
        "train_end": candidate.train_end,
        "feature_columns": candidate.features,
    })()
    win_preds = predict_future_entries(
        winner, nonmarket_history, clean_entries,
        max_history_gap_days=14, allow_stale_history=False,
    )
    history_aligned = align_history_to_training_start(
        nonmarket_history, train_start=candidate.train_start
    )
    future = build_future_feature_frame(
        history_aligned, clean_entries, candidate.features,
        max_history_gap_days=14, allow_stale_history=False,
    )
    outsider = candidate.outsider.predict_win_probability(
        future, race_col="race_id"
    )
    if (len(win_preds) != len(entries)
            or len(outsider) != len(entries)
            or set(zip(win_preds["race_id"], win_preds["horse_name"]))
            != set(zip(entries["race_id"], entries["horse_name"]))
            or not outsider.index.equals(future.index)
            or not np.isfinite(outsider.to_numpy(dtype=float)).all()
            or outsider.le(0).any()
            or not np.allclose(
                outsider.groupby(future["race_id"]).sum().to_numpy(),
                1.0, atol=1e-9,
            )):
        raise ValueError("genuine Friday model roster/probabilities invalid")
    scored = win_preds[[
        "race_id", "horse_name", "predicted_win_probability"
    ]].merge(
        future[["race_id", "horse_name"]].assign(outsider_score=outsider),
        on=["race_id", "horse_name"], validate="one_to_one", how="inner",
    )
    if len(scored) != len(entries):
        raise ValueError("outsider model must score same Friday horses")
    commitment = []
    for rid, race in scored.groupby("race_id"):
        ranked = race.sort_values(
            ["predicted_win_probability", "horse_name"],
            ascending=[False, True], kind="stable",
        )
        protected_top3 = set(ranked["horse_name"].head(3))
        remaining = ranked.loc[~ranked["horse_name"].isin(protected_top3)]
        choice = remaining.sort_values(
            ["outsider_score", "horse_name"],
            ascending=[False, True], kind="stable",
        ).iloc[0]
        commitment.append([
            str(rid), str(choice["horse_name"]),
            format(float(choice["outsider_score"]), ".17g"),
        ])
    digest = sha256(json.dumps(
        sorted(commitment), ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return {
        "status": "PRIVATE_FRIDAY_PRE_DRAW_RESEARCH_ONLY",
        "raceDate": race_date,
        "raceCount": len(commitment),
        "runnerCount": len(scored),
        "realWinAndOutsiderModelsComputed": True,
        "winModelOutputSha256": _canonical_model_output_sha256(win_preds),
        "outsiderSelectionSha256": digest,
        "raceNumbersKnownOrInvented": False,
        "sourceRightsIndependentlyVerified": False,
        "upstreamOddsIndependentSourceProven": False,
        "published": False,
        "publicationAuthorized": False,
        "positiveExpectedValueDemonstrated": False,
    }
