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


def seal_paired_comparison(comparison: dict, *, source_sha256: dict,
                           private_salt: bytes) -> dict:
    """Bind all three selections, input hashes and shared chronology at once.

    The returned private record is not an external timestamp. The source
    hashes must come from the actual reviewed input bytes, not placeholders.
    """
    import json
    import re
    from dataclasses import asdict

    if (type(private_salt) is not bytes or len(private_salt) != 32
            or type(source_sha256) is not dict
            or set(source_sha256) != {"official_preoff_zip", "reviewed_entries",
                                     "reviewed_prior_history"}
            or any(type(v) is not str or not re.fullmatch(r"[0-9a-f]{64}", v)
                   for v in source_sha256.values())):
        raise ValueError("NAR_PAIRED_COMMITMENT_SOURCE_INVALID")
    partial = comparison["catboost_3_of_5"]
    complete = comparison["catboost_reviewed_5_feature"]
    baseline = comparison["fixed_career_baseline"]
    if (partial.jurisdiction != "NAR" or complete.jurisdiction != "NAR"
            or any(getattr(partial, field) != getattr(complete, field)
                   for field in ("race_day_jst", "generated_utc",
                                 "source_asof_utc", "model_trained_through",
                                 "model_sha256_declared"))
            or not partial.races
            or len(partial.races) != len(complete.races)
            or len(partial.races) != len(baseline)):
        raise ValueError("NAR_PAIRED_COMMITMENT_COHORT_INVALID")
    for a, b, c in zip(partial.races, complete.races, baseline):
        if (a.race_id != b.race_id or a.race_id != c["race_id"]
                or a.roster != b.roster or a.off_utc != b.off_utc
                or len(c["top3"]) != 3 or len(set(c["top3"])) != 3
                or not set(c["top3"]).issubset(a.roster)
                or c["outsider"] not in a.roster
                or c["outsider"] in c["top3"]):
            raise ValueError("NAR_PAIRED_COMMITMENT_ROSTER_INVALID")
    payload = {
        "schema": "NAR.PC2.PairedThreeSeriesPrivate.v1",
        "source_sha256_PRIVATE": dict(source_sha256),
        "catboost_3_of_5_PRIVATE": asdict(partial),
        "catboost_reviewed_5_feature_PRIVATE": asdict(complete),
        "fixed_career_baseline_PRIVATE": baseline,
        "baseline_policy": "NAR_OFFICIAL_CAREER_FORM_BASELINE_V1_FIXED_20261110",
        "independent_preoff_receipt_verified": False,
        "outcomes_measured": False,
        "actual_bets": 0,
        "positive_ev_proven": False,
    }
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")
    digest = sha256(b"NAR_PAIRED_THREE_SERIES_V1" + bytes([0])
                    + private_salt + data).hexdigest()
    return {"payload_PRIVATE": payload, "salt_hex_PRIVATE": private_salt.hex(),
            "blinded_digest": digest}


def verify_paired_commitment(record: dict, expected_digest: str) -> bool:
    """Verify against a separately obtained digest; never authenticate its time."""
    import json
    import re
    import secrets

    try:
        if (type(record) is not dict
                or set(record) != {"payload_PRIVATE", "salt_hex_PRIVATE",
                                   "blinded_digest"}
                or type(expected_digest) is not str
                or not re.fullmatch(r"[0-9a-f]{64}", expected_digest)
                or not re.fullmatch(r"[0-9a-f]{64}", record["salt_hex_PRIVATE"])
                or record["payload_PRIVATE"]["schema"]
                   != "NAR.PC2.PairedThreeSeriesPrivate.v1"):
            return False
        data = json.dumps(record["payload_PRIVATE"], ensure_ascii=False,
                          sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode("utf-8")
        actual = sha256(b"NAR_PAIRED_THREE_SERIES_V1" + bytes([0])
                        + bytes.fromhex(record["salt_hex_PRIVATE"]) + data).hexdigest()
        return (secrets.compare_digest(actual, expected_digest)
                and secrets.compare_digest(actual, record["blinded_digest"]))
    except (KeyError, ValueError, TypeError, AttributeError):
        return False
