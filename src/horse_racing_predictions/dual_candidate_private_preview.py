"""Hash-verified, true dual-CatBoost Sunday PRIVATE research preview.

It does NOT approve source licensing, upstream odds-independent selection,
calibration, independent model attestation, financial EV, or note publication.
No provider access, model training, protected-holdout dataset or network I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

from .feature_window import align_history_to_training_start
from .inference import build_future_feature_frame, predict_future_entries
from .modeling import CatBoostProbabilityModel
from .odds_free_chronological_eval import _validate_research_features
from .sunday_ai_research import (
    _canonical_model_output_sha256, _market_column, private_sunday_ai_preview,
)

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_JST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class LoadedDualResearchCandidate:
    winner: CatBoostProbabilityModel
    outsider: CatBoostProbabilityModel
    features: tuple[str, ...]
    train_start: str
    train_end: str
    generated_at: str
    digest_by_role: dict[str, str]


def _artifact_file(base: Path, name: str, limit: int) -> Path:
    path = base / name
    if (path.is_symlink() or not path.is_file()
            or path.stat().st_size == 0 or path.stat().st_size > limit
            or not path.resolve().is_relative_to(base.resolve())):
        raise ValueError("missing or nonlocal model research artifact")
    return path


def _read_json_no_duplicates(path: Path) -> dict:
    def no_duplicate(pairs):
        obj = {}
        for key, val in pairs:
            if key in obj:
                raise ValueError("duplicate dual manifest key")
            obj[key] = val
        return obj
    obj = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicate,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")),
    )
    if not isinstance(obj, dict):
        raise ValueError("dual manifest is not an object")
    return obj


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while block := handle.read(1_048_576):
            digest.update(block)
    return digest.hexdigest()


def load_dual_research_candidate(directory: Path) -> LoadedDualResearchCandidate:
    """Read a local *research-only* 2-CBM candidate and verify both binaries."""
    if (not isinstance(directory, Path) or directory.is_symlink()
            or not directory.is_dir()):
        raise ValueError("candidate directory missing or linked")
    manifest = _read_json_no_duplicates(
        _artifact_file(directory, "candidate_manifest.json", 300_000)
    )
    if (manifest.get("schemaVersion") != 1
            or manifest.get("artifactKind")
            != "dual-catboost-oddsfree-research-candidate"
            or manifest.get("status")
            != "RESEARCH_NOT_APPROVED_FOR_PUBLICATION"
            or manifest.get("publicationAuthorized") is not False
            or manifest.get("sourceRightsIndependentlyVerified") is not False
            or manifest.get("retrainingOnProtectedHoldoutAllowed") is not False
            or manifest.get("independentOutsiderModelVerified") is not False):
        raise ValueError("dual research manifest may not authorize release")
    features = manifest.get("featureColumns")
    if (not isinstance(features, list) or not features
            or not all(isinstance(v, str) for v in features)
            or any(_market_column(v) for v in features)):
        raise ValueError("invalid or market-dependent dual features")
    _validate_research_features(tuple(features))
    try:
        start = date.fromisoformat(manifest["trainStart"])
        end = date.fromisoformat(manifest["trainEnd"])
        created = datetime.fromisoformat(
            manifest["generatedAt"].replace("Z", "+00:00")
        )
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise ValueError("invalid trained model chronology") from exc
    if (start.isoformat() != manifest["trainStart"]
            or end.isoformat() != manifest["trainEnd"]
            or start > end or end > date(2024, 12, 31)
            or created.utcoffset() is None
            or created.astimezone(_JST).date() < end):
        raise ValueError("dual model dates could include protected holdout")
    metrics = manifest.get("researchMetrics")
    if (not isinstance(metrics, dict)
            or metrics.get("fitThrough") != manifest["trainEnd"]
            or metrics.get("winModelTarget") != "is_winner"
            or metrics.get("outsiderModelTarget")
            != "finish_position_le_3_train_only"
            or metrics.get("publicationAuthorized") is not False
            or metrics.get("positiveExpectedValueDemonstrated") is not False):
        raise ValueError("dual research target/metrics inconsistent")
    declared = manifest.get("artifactSha256")
    if (not isinstance(declared, dict)
            or set(declared) != {"win.cbm", "outsider.cbm"}
            or any(not isinstance(v, str) or not _SHA.fullmatch(v)
                   for v in declared.values())):
        raise ValueError("dual native binary digests missing")
    files: dict[str, Path] = {}
    for name in ("win.cbm", "outsider.cbm"):
        path = _artifact_file(directory, name, 500_000_000)
        if _sha256_file(path) != declared[name]:
            raise ValueError("dual binary checksum mismatch")
        files[name] = path
    # Import only after verifying both bytes; avoid defaulting to a manually
    # authored score table if CatBoost is not available.
    try:
        from catboost import CatBoostClassifier
    except ImportError as exc:
        raise RuntimeError("real CatBoost runtime unavailable") from exc
    wrappers = []
    for name in ("win.cbm", "outsider.cbm"):
        model = CatBoostClassifier()
        model.load_model(str(files[name]))
        actual = tuple(model.feature_names_)
        if actual != tuple(features):
            raise ValueError("native dual CatBoost features differ from manifest")
        wrapped = CatBoostProbabilityModel(feature_columns=list(features))
        wrapped.model = model
        wrappers.append(wrapped)
    return LoadedDualResearchCandidate(
        winner=wrappers[0], outsider=wrappers[1],
        features=tuple(features),
        train_start=start.isoformat(), train_end=end.isoformat(),
        generated_at=manifest["generatedAt"], digest_by_role=declared,
    )


def private_dual_sunday_preview(
    candidate: LoadedDualResearchCandidate, *,
    history: pd.DataFrame, entries: pd.DataFrame,
    expected_race_ids: tuple[str, ...], race_date: str,
    observed_at: datetime,
) -> dict[str, Any]:
    """Real winner and outsider inference; only sanitized anonymous proof."""
    if not isinstance(candidate, LoadedDualResearchCandidate):
        raise ValueError("two native candidate models required")
    proxy = SimpleNamespace(
        model=candidate.winner,
        manifest=SimpleNamespace(
            model_version="strict-oddsfree-dual-research-candidate",
            experiment_id="dual-catboost-pre2025-private-research",
            model_kind="catboost",
            feature_columns=candidate.features,
            train_start=candidate.train_start,
            train_end=candidate.train_end,
            created_at=candidate.generated_at,
        ),
    )
    # This independent existing checker enforces full field roster and
    # Sunday time cutoff; no model values or horse IDs escape the caller.
    preview = private_sunday_ai_preview(
        champion=proxy, history=history, entries=entries,
        expected_race_ids=expected_race_ids,
        race_date=race_date, observed_at=observed_at,
    )
    # Same point-in-time transformations and actual trained winner model as
    # the canonical private preview. Never use target race finish labels.
    approved_history = history.drop(
        columns=[c for c in history.columns if _market_column(c)]
    )
    aligned = align_history_to_training_start(
        approved_history, train_start=candidate.train_start
    )
    features = build_future_feature_frame(
        aligned, entries, candidate.features,
        max_history_gap_days=14, allow_stale_history=False,
    )
    win_prediction = predict_future_entries(
        proxy, approved_history, entries,
        max_history_gap_days=14, allow_stale_history=False,
    )
    if preview["modelOutputSha256"] != _canonical_model_output_sha256(
        win_prediction
    ):
        raise ValueError("winner inference must agree with validated preview")
    outsider_scores = candidate.outsider.predict_win_probability(
        features, race_col="race_id",
    )
    if (not outsider_scores.index.equals(features.index)
            or len(outsider_scores) != len(entries)
            or not np.isfinite(outsider_scores.to_numpy(dtype=float)).all()
            or outsider_scores.le(0).any()
            or not np.allclose(
                outsider_scores.groupby(features["race_id"]).sum().to_numpy(),
                1.0, atol=1e-9,
            )):
        raise ValueError("independently inferred outsider scores invalid")
    scores = win_prediction[
        ["race_id", "horse_name", "predicted_win_probability"]
    ].copy()
    ups = features[["race_id", "horse_name"]].copy()
    ups["outsider_score"] = outsider_scores
    scored = scores.merge(
        ups, on=["race_id", "horse_name"], how="inner", validate="one_to_one"
    )
    if len(scored) != len(entries):
        raise ValueError("independent score roster mismatch")
    anonymous = []
    for rid, race in scored.groupby("race_id"):
        ranked = race.sort_values(
            ["predicted_win_probability", "horse_name"],
            ascending=[False, True], kind="stable",
        )
        top3 = set(ranked["horse_name"].astype(str).head(3))
        remain = ranked.loc[~ranked["horse_name"].astype(str).isin(top3)]
        if remain.empty:
            raise ValueError("not enough runners for a fourth independent horse")
        pick = remain.sort_values(
            ["outsider_score", "horse_name"],
            ascending=[False, True], kind="stable",
        ).iloc[0]
        # Hash only a private commitment to the actual selected identity.
        anonymous.append([str(rid), str(pick["horse_name"])])
    digest = sha256(json.dumps(
        sorted(anonymous), ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return {
        "status": "DUAL_REAL_MODEL_PRIVATE_RESEARCH_ONLY",
        "raceDate": race_date,
        "raceCount": len(anonymous),
        "runnerCount": len(entries),
        "winModelOutputSha256": preview["modelOutputSha256"],
        "outsiderSelectionSha256": digest,
        "bothActualModelsExecuted": True,
        "independentlyApprovedModel": False,
        "sourceRightsIndependentlyVerified": False,
        "upstreamSamplingOddsIndependentlyVerified": False,
        "publicationAuthorized": False,
        "notePublishingPermitted": False,
        "positiveExpectedValueDemonstrated": False,
    }
