"""Compute a local Sunday *research preview* by actual model inference only.

No fallback to journalist tips or manually typed strengths. This code never
publishes, signs provenance, trains a model, assigns an outsider or claims EV.
The ordinary Champion v7 is excluded because its training selected rows
using win_odds. Missing/old history and incomplete entries are hard errors.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from unicodedata import normalize
from typing import Any

import numpy as np
import pandas as pd

from .inference import predict_future_entries

_JST = timezone(timedelta(hours=9))
_MARKET = re.compile(
    r"odds|popular(?:ity)?|market|betting|payout|dividend|"
    r"オッズ|人気|単勝|複勝|払戻|配当|投票", re.IGNORECASE
)
_ID = re.compile(r"JRA-[0-9]{8}-[0-9A-Za-z-]{1,24}\Z")
def _market_column(label: Any) -> bool:
    # Prevent full-width and whitespace variants of market labels bypassing
    # the guard. A research preview is not a data publication permission.
    canonical = normalize("NFKC", str(label))
    return bool(_MARKET.search(re.sub(r"[\s\u200b-\u200d\ufeff]+", "", canonical)))


def _canonical_model_output_sha256(predictions: pd.DataFrame) -> str:
    canonical = [
        [str(rid), str(name), format(float(probability), ".17g")]
        for rid, name, probability in sorted(
            zip(predictions["race_id"], predictions["horse_name"],
                predictions["predicted_win_probability"]),
            key=lambda x: (str(x[0]), str(x[1])),
        )
    ]
    return sha256(json.dumps(
        canonical, ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


_RESULT = frozenset({
    "finish_position", "is_winner", "finish_time", "last_3f", "margin",
    "prize_money", "corner_1", "corner_2", "corner_3", "corner_4",
    "strength", "upside_score", "predicted_win_probability", "manual_rank",
})


def private_sunday_ai_preview(
    *, champion: Any, history: pd.DataFrame, entries: pd.DataFrame,
    expected_race_ids: tuple[str, ...], race_date: str,
    observed_at: datetime,
) -> dict[str, Any]:
    """Run existing genuine inference; return a nonpublishable private preview.

    The returned rankings are model outputs, but their *correctness*, lawful
    source rights, evidence and independent condition-upside outsider are
    NOT verified by this routine. A model-version prefix is not proof of
    independent training integrity and cannot enable note posting.
    """
    try:
        day = date.fromisoformat(race_date)
    except (TypeError, ValueError) as exc:
        raise ValueError("valid Sunday race_date required") from exc
    if day.isoformat() != race_date or day.weekday() != 6:
        raise ValueError("target must be a Sunday")
    if not isinstance(observed_at, datetime) or observed_at.utcoffset() is None:
        raise ValueError("observed_at must have timezone")
    observed = observed_at.astimezone(_JST).date()
    if not day - timedelta(days=2) <= observed < day:
        raise ValueError("must prepare preview before Sunday, within two days")

    manifest = getattr(champion, "manifest", None)
    version = getattr(manifest, "model_version", "")
    features = getattr(manifest, "feature_columns", ())
    if not isinstance(version, str) or not version.startswith("strict-oddsfree-"):
        raise ValueError("legacy Champion v7 or other unverified model refused")
    if (getattr(manifest, "model_kind", None) != "catboost"
            or not isinstance(features, (tuple, list)) or not features
            or any(not isinstance(f, str) or _market_column(f) for f in features)
            or len(set(features)) != len(features)):
        raise ValueError("model features/kind not acceptable")
    try:
        train_start = date.fromisoformat(manifest.train_start)
        train_end = date.fromisoformat(manifest.train_end)
        created_at = datetime.fromisoformat(
            manifest.created_at.replace("Z", "+00:00")
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("model training/creation chronology invalid") from exc
    if (train_start > train_end or train_end > date(2024, 12, 31)
            or train_start.isoformat() != manifest.train_start
            or train_end.isoformat() != manifest.train_end):
        raise ValueError("protected final holdout or invalid training window")
    if (created_at.utcoffset() is None
            or created_at > observed_at
            or created_at.date() < train_end):
        raise ValueError("model artifact must predate Sunday research preview")

    if not callable(getattr(getattr(champion, "model", None),
                            "predict_win_probability", None)):
        raise ValueError("executable trained model missing")

    if not isinstance(history, pd.DataFrame) or history.empty:
        raise ValueError("real historical data missing")
    if not isinstance(entries, pd.DataFrame) or entries.empty:
        raise ValueError("real Sunday entrants missing")
    if history.columns.duplicated().any() or entries.columns.duplicated().any():
        raise ValueError("duplicate source columns")
    if (not isinstance(expected_race_ids, tuple) or not expected_race_ids
            or len(expected_race_ids) > 36
            or any(not isinstance(r, str) or not _ID.fullmatch(r)
                   for r in expected_race_ids)
            or len(set(expected_race_ids)) != len(expected_race_ids)):
        raise ValueError("complete canonical Sunday race manifest needed")
    required = {"race_id", "race_date", "horse_name", "post_position"}
    if not required.issubset(entries):
        raise ValueError("Sunday race/horse identification missing")
    if any(_market_column(c) for c in entries.columns):
        raise ValueError("market information cannot enter Sunday prediction")
    if any(entries[c].notna().any() for c in _RESULT.intersection(entries)):
        raise ValueError("future finish/outcome information is forbidden")
    days = pd.to_datetime(entries["race_date"], errors="raise")
    hist_days = pd.to_datetime(history["race_date"], errors="raise")
    if (days.isna().any() or days.dt.date.ne(day).any()
            or hist_days.isna().any() or hist_days.max().date() >= day):
        raise ValueError("historical/target race time boundary invalid")
    if (day - hist_days.max().date()).days > 14:
        raise ValueError("historical race inputs are stale (>14 days)")
    if hist_days.max().date() >= observed:
        raise ValueError(
            "same-day or future history has no verified pre-preview timestamp"
        )

    if any(not rid.startswith("JRA-" + day.strftime("%Y%m%d") + "-")
           for rid in expected_race_ids):
        raise ValueError("race IDs do not encode the target Sunday date")
    if set(entries["race_id"]) != set(expected_race_ids):
        raise ValueError("all expected Sunday races must be present")
    if entries[["race_id", "horse_name", "post_position"]].isna().any().any():
        raise ValueError("missing race/horse identity")
    if (entries["horse_name"].astype(str).str.strip().eq("").any()
            or entries["race_id"].astype(str).str.strip().eq("").any()
            or entries.duplicated(["race_id", "horse_name"]).any()):
        raise ValueError("duplicate/blank Sunday horses")
    counts = entries.groupby("race_id")["horse_name"].transform("size")
    if counts.lt(4).any() or counts.gt(18).any():
        raise ValueError("incomplete Sunday race field")
    nums = pd.to_numeric(entries["post_position"], errors="coerce")
    if (nums.isna().any() or nums.lt(1).any() or nums.gt(18).any()
            or nums.mod(1).ne(0).any()
            or pd.DataFrame({"rid": entries["race_id"], "num": nums})
              .duplicated().any()):
        raise ValueError("horse numbers must be confirmed, distinct integers")

    # Strip historical market columns BEFORE building any model features.
    # Carrying even unused market fields into the feature frame is an
    # unnecessary leakage risk.
    nonmarket_history = history.drop(
        columns=[c for c in history.columns if _market_column(c)]
    )
    # No manual model scores are accepted. The existing inference computes
    # probabilities from real inputs and enforces its own age cutoff.
    predictions = predict_future_entries(
        champion, nonmarket_history, entries, max_history_gap_days=14,
        allow_stale_history=False,
    )
    if (len(predictions) != len(entries)
            or set(zip(predictions["race_id"], predictions["horse_name"]))
            != set(zip(entries["race_id"], entries["horse_name"]))):
        raise ValueError("actual model predictions do not cover Sunday entrants")
    probs = predictions["predicted_win_probability"].to_numpy(dtype=float)
    if (not np.isfinite(probs).all() or (probs <= 0).any()
            or (probs >= 1).any()):
        raise ValueError("invalid runtime model outputs")
    totals = predictions.groupby("race_id")["predicted_win_probability"].sum()
    if not np.allclose(totals.to_numpy(dtype=float), 1.0, atol=1e-9):
        raise ValueError("runtime probabilities do not sum to one")

    preview = []
    for rid, race in predictions.groupby("race_id", sort=False):
        ranked = race.sort_values(
            ["predicted_win_probability", "horse_name"],
            ascending=[False, True], kind="stable",
        )
        preview.append({
            "raceId": str(rid),
            "modelTopThree": ranked["horse_name"].astype(str).head(3).tolist(),
            "modelComputed": True,
            "outsiderModelVerified": False,
        })
    return {
        "status": "PRIVATE_MODEL_RESEARCH_ONLY",
        "raceDate": day.isoformat(), "modelVersion": version,
        "raceCount": len(preview), "runnerCount": len(predictions),
        "modelOutputSha256": _canonical_model_output_sha256(predictions),
        "races": preview, "publicationAuthorized": False,
        "notePublishingPermitted": False,
        "sourceRightsVerified": False,
        "modelTrainingAndProvenanceIndependentlyVerified": False,
        "independentOutsiderModelVerified": False,
        "predictionAccuracyOrEVProven": False,
    }
