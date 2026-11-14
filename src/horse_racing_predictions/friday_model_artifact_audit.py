"""Read-only binary/manifest integrity check for a Friday odds-free candidate.

This module never establishes model provenance, permission to publish,
independent probabilities or live data freshness. No CatBoost dependency.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping
from unicodedata import normalize

_MARKET = re.compile(
    r"odds|popularity|market[_ -]?(?:rank|share|odds)|"
    r"betting|payout|dividend|単勝|複勝|人気|オッズ|払戻|配当",
    re.IGNORECASE,
)
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_JST = timezone(timedelta(hours=9))


def _time(value: Any) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
        r"(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", value
    ):
        raise ValueError("invalid timestamp")
    date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if date.utcoffset() is None:
        raise ValueError("timestamp missing timezone")
    return date


def _read_small_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 300_000:
        raise ValueError("manifest missing, linked or too large")
    def no_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for name, value in pairs:
            if name in result:
                raise ValueError("duplicate manifest keys")
            result[name] = value
        return result
    result = json.loads(path.read_text(encoding="utf-8"),
                        object_pairs_hook=no_duplicate)
    if not isinstance(result, dict):
        raise ValueError("manifest must be JSON object")
    return result


def inspect_frozen_model_bytes(
    *, artifact_directory: Path, candidate_model: Mapping[str, Any] | None,
    issue_date: str, forecast: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Inspect local bytes and manifest; never return publication PASS."""
    refused = lambda reason: {
        "status": "REJECTED", "reason": reason,
    }
    try:
        if candidate_model is None or not isinstance(candidate_model, Mapping):
            return refused("candidate model manifest missing")
        if (not isinstance(artifact_directory, Path)
                or artifact_directory.is_symlink()
                or not artifact_directory.is_dir()):
            return refused("model directory missing or linked")
        binary = artifact_directory / "model.cbm"
        manifest_path = artifact_directory / "manifest.json"
        if (binary.is_symlink() or not binary.is_file()
                or binary.stat().st_size <= 0
                or binary.stat().st_size > 500_000_000):
            return refused("model binary missing, linked or invalid size")
        content = sha256()
        size = 0
        with binary.open("rb") as handle:
            while True:
                block = handle.read(1024 * 1024)
                if not block:
                    break
                size += len(block)
                if size > 500_000_000:
                    return refused("model binary too large")
                content.update(block)
        digest = content.hexdigest()
        if not _SHA.fullmatch(str(candidate_model.get("artifactSha256", ""))):
            return refused("candidate artifact digest missing")
        if digest != candidate_model["artifactSha256"]:
            return refused("model binary SHA-256 mismatch")
        native = _read_small_json(manifest_path)
        cols = native.get("feature_columns")
        cats = native.get("categorical_columns")
        if (native.get("model_kind") != "catboost"
                or not isinstance(cols, list) or not cols
                or not all(isinstance(x, str) and x for x in cols)
                or len(set(cols)) != len(cols)
                or not isinstance(cats, list)
                or not set(cats).issubset(set(cols))):
            return refused("native CatBoost feature manifest malformed")
        if any(_MARKET.search(normalize("NFKC", name).replace(" ", "")) for name in cols):
            return refused("native model contains market/popularity feature names")
        declared = candidate_model.get("featureNames")
        if cols != declared:
            return refused("native model feature columns differ from candidate")
        if (candidate_model.get("modelId") not in (
                native.get("model_version"), native.get("experiment_id"))):
            return refused("native model identifier differs from candidate")
        created = _time(native.get("created_at"))
        freeze = _time(candidate_model.get("frozenAt"))
        issue_end = _time(issue_date + "T23:59:59+09:00")
        if not (created <= freeze <= issue_end):
            return refused("model creation/freeze/issue chronology invalid")
        try:
            training_start = date.fromisoformat(native["train_start"])
            train_end = date.fromisoformat(native["train_end"])
            issue = date.fromisoformat(issue_date)
            if (training_start.isoformat() != native["train_start"]
                    or train_end.isoformat() != native["train_end"]
                    or issue.isoformat() != issue_date):
                return refused("training cutoff is malformed")
        except (KeyError, ValueError, TypeError):
            return refused("training cutoff is malformed")
        if training_start > train_end:
            return refused("training start follows training end")
        # Never accept a model trained on protected 2025–2026 final holdout,
        # even if that training predates the article's 2026 issue date.
        if train_end > date(2024, 12, 31):
            return refused("protected final holdout in training manifest")
        if train_end > issue:
            return refused("training includes post-issue races")
        if created.date() < train_end:
            return refused("model creation predates training cutoff")
        if forecast is not None:
            if (forecast.get("model_id") != candidate_model["modelId"]
                    or forecast.get("model_frozen_at") != candidate_model["frozenAt"]):
                return refused("forecast model/freeze mismatch")
        return {
            "status": "REVIEW_REQUIRED",
            "modelBytesSha256": digest,
            "modelBytes": size,
            "featureCount": len(cols),
            "trainEnd": train_end.isoformat(),
            "trainGapDays": (issue - train_end).days,
            "trainingSampleSelectionMarketExposureNeedsReview": True,
            "reason": (
                "binary and native manifest match candidate, but true model "
                "provenance, training sample selection, out-of-sample calibration, "
                "post-2021 data freshness and predicted scores remain unverified"
            ),
        }
    except (ValueError, OSError, UnicodeError, KeyError, TypeError):
        return refused("model artifact/manifest unreadable or invalid")
