"""Private, odds-free paired ranking experiment; no I/O or outcome access.

Compare two feature views of the same fitted NAR models against the
existing smoothed career-form comparator. The caller must bind the
official pre-off input and independently reviewed history to a private
pre-off commitment; this function does not establish their provenance.
"""
from __future__ import annotations

from hashlib import sha256

import numpy as np
import pandas as pd

from .nar_future_asof_form_projection import prepare_reviewed_nar_full_form
from .prospective_dual_model_shadow import freeze_fitted_dual_shadow

_KEYS = ["race_id", "horse_id"]
_CORE = ["past_starts", "past_win_rate", "past_top3_rate"]
_EXTRA = ["past_mean_finish", "days_since_last_start"]


def compare_nar_future_rankings(*, official_partial: pd.DataFrame,
        reviewed_entries: pd.DataFrame, history: pd.DataFrame,
        off_by_race: dict, expected_runner_counts: dict,
        race_day_jst: str, source_asof_utc, generated_utc, loaded) -> dict:
    """Compare all three on the exact same roster and verified career counts.

    The official_partial frame is the existing official DAILY preoff
    parser's output. A mismatch with the reviewed history is HOLD.
    Nothing is persisted, published or independently timestamped here.
    """
    if (not isinstance(official_partial, pd.DataFrame)
            or official_partial.columns.duplicated().any()
            or set(official_partial) != set(_KEYS + _CORE + _EXTRA)
            or official_partial[_KEYS].isna().any().any()
            or official_partial.duplicated(_KEYS).any()
            or not official_partial[_EXTRA].isna().all().all()
            or official_partial.groupby("race_id").size().to_dict()
               != expected_runner_counts):
        raise ValueError("NAR_PAIRED_OFFICIAL_ROSTER_INVALID")
    full = prepare_reviewed_nar_full_form(
        history, reviewed_entries, race_day_jst=race_day_jst,
        source_asof_utc=source_asof_utc,
        expected_runner_counts=expected_runner_counts,
    )
    official = official_partial.set_index(_KEYS).sort_index()
    reviewed = full.set_index(_KEYS).sort_index()
    if (not official.index.equals(reviewed.index)
            or not np.isfinite(official[_CORE].to_numpy(dtype=float)).all()
            or not np.allclose(official[_CORE].to_numpy(dtype=float),
                               reviewed[_CORE].to_numpy(dtype=float),
                               rtol=0, atol=1e-10)):
        raise ValueError("NAR_PAIRED_CAREER_TOTAL_OR_ROSTER_MISMATCH")
    if (tuple(loaded.features) != tuple(_CORE + _EXTRA)
            or loaded.train_end != "2021-12-31"):
        raise ValueError("NAR_PAIRED_MODEL_CONTRACT_INVALID")
    digests = loaded.digest_by_role
    combined = sha256((digests["win.cbm"] +
                       digests["outsider.cbm"]).encode("ascii")).hexdigest()
    args = dict(jurisdiction="NAR", race_day_jst=race_day_jst,
                off_by_race=off_by_race, winner=loaded.winner,
                outsider=loaded.outsider, model_trained_through=loaded.train_end,
                model_sha256_declared=combined, source_asof_utc=source_asof_utc,
                generated_utc=generated_utc)
    partial = freeze_fitted_dual_shadow(entries=official.reset_index(), **args)
    complete = freeze_fitted_dual_shadow(entries=reviewed.reset_index(), **args)
    # Existing fixed career-form policy; never fitted on these outcomes.
    baseline = []
    for rid, group in official.reset_index().groupby("race_id", sort=True):
        starts = group["past_starts"]
        win = (starts * group["past_win_rate"] + 1) / (starts + 10)
        podium = (starts * group["past_top3_rate"] + 1) / (starts + 10)
        ranked = group.assign(win=win, podium=podium)
        top = tuple(ranked.sort_values(["win", "horse_id"],
                    ascending=[False, True])["horse_id"].iloc[:3])
        outsider = ranked.loc[~ranked["horse_id"].isin(top)].sort_values(
            ["podium", "horse_id"], ascending=[False, True]
        ).iloc[0]["horse_id"]
        baseline.append(dict(race_id=rid, top3=top, outsider=outsider))
    return {"catboost_3_of_5": partial, "catboost_reviewed_5_feature": complete,
            "fixed_career_baseline": tuple(baseline),
            "race_count": len(partial.races),
            "runner_count": len(full),
            "independent_preoff_receipt_verified": False,
            "outcomes_measured": False}
