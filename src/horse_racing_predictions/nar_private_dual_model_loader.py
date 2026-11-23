"""Read a PRIVATE fitted NAR dual-CatBoost research artifact safely.

The JRA strict-dual loader intentionally only permits JRA feature names.
NAR is a distinct five-feature historical-form model, so this validator
has an explicit allowlist rather than relaxing JRA's leakage protections.
Neither model nor source data may be uploaded or published by this loader.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import re

from .dual_candidate_private_preview import (
    LoadedDualResearchCandidate, _artifact_file,
    _read_json_no_duplicates, _sha256_file,
)
from .modeling import CatBoostProbabilityModel

_NAR_FEATURES = (
    "past_starts", "past_win_rate", "past_top3_rate",
    "past_mean_finish", "days_since_last_start",
)
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def load_nar_private_dual_candidate(directory: Path) -> LoadedDualResearchCandidate:
    """Return two independent native NAR research models if all gates pass."""
    if (not isinstance(directory, Path)
            or directory.is_symlink() or not directory.is_dir()):
        raise ValueError("NAR_DUAL_CANDIDATE_DIRECTORY_INVALID")
    manifest = _read_json_no_duplicates(
        _artifact_file(directory, "candidate_manifest.json", 300_000)
    )
    if (manifest.get("schemaVersion") != 1
            or manifest.get("artifactKind")
            != "dual-catboost-oddsfree-research-candidate"
            or manifest.get("status") != "RESEARCH_NOT_APPROVED_FOR_PUBLICATION"
            or manifest.get("jurisdiction") != "NAR"
            or manifest.get("sourceRef")
            != "nar-personal-2017-2022-72months-reviewed-local"
            or manifest.get("publicationAuthorized") is not False
            or manifest.get("sourceRightsIndependentlyVerified") is not False
            or manifest.get("independentOutsiderModelVerified") is not False
            or manifest.get("modelRuntimeProvenanceVerified") is not False
            or manifest.get("retrainingOnProtectedHoldoutAllowed") is not False
            or manifest.get("sourceRowsOrRaceIdentitiesExported") is not False
            or tuple(manifest.get("featureColumns", ())) != _NAR_FEATURES):
        raise ValueError("NAR_DUAL_MANIFEST_OR_FEATURE_CONTRACT_INVALID")
    if (manifest.get("trainStart") != "2017-01-01"
            or manifest.get("trainEnd") != "2021-12-31"):
        raise ValueError("NAR_DUAL_SEALED_TRAINING_PERIOD_INVALID")
    try:
        created = datetime.fromisoformat(
            manifest["generatedAt"].replace("Z", "+00:00")
        )
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise ValueError("NAR_DUAL_MODEL_TIMESTAMP_INVALID") from exc
    if (created.utcoffset() is None
            or created.astimezone(timezone.utc).date() < date(2022, 1, 1)):
        raise ValueError("NAR_DUAL_MODEL_TIMESTAMP_INVALID")
    metrics = manifest.get("researchMetrics")
    if (not isinstance(metrics, dict)
            or metrics.get("fitThrough") != "2021-12-31"
            or metrics.get("winModelTarget") != "is_winner"
            or metrics.get("outsiderModelTarget")
            != "finish_position_le_3_train_only"
            or metrics.get("publicationAuthorized") is not False
            or metrics.get("positiveExpectedValueDemonstrated") is not False
            or type(metrics.get("trainingRaces")) is not int
            or metrics["trainingRaces"] < 5
            or type(metrics.get("validationRaces")) is not int
            or metrics["validationRaces"] < 3):
        raise ValueError("NAR_DUAL_MODEL_METRICS_INVALID")
    hashes = manifest.get("artifactSha256")
    if (not isinstance(hashes, dict)
            or set(hashes) != {"win.cbm", "outsider.cbm"}
            or any(type(x) is not str or not _DIGEST.fullmatch(x)
                   for x in hashes.values())):
        raise ValueError("NAR_DUAL_MODEL_DIGEST_MANIFEST_INVALID")
    files = {}
    for name in ("win.cbm", "outsider.cbm"):
        path = _artifact_file(directory, name, 500_000_000)
        if _sha256_file(path) != hashes[name]:
            raise ValueError("NAR_DUAL_MODEL_SHA256_MISMATCH")
        files[name] = path
    try:
        from catboost import CatBoostClassifier
    except ImportError as exc:
        raise RuntimeError("NAR_DUAL_MODEL_CATBOOST_RUNTIME_UNAVAILABLE") from exc
    wrappers = []
    for name in ("win.cbm", "outsider.cbm"):
        native = CatBoostClassifier()
        native.load_model(str(files[name]))
        if tuple(native.feature_names_) != _NAR_FEATURES:
            raise ValueError("NAR_DUAL_NATIVE_FEATURE_SCHEMA_MISMATCH")
        wrapped = CatBoostProbabilityModel(feature_columns=list(_NAR_FEATURES))
        wrapped.model = native
        wrappers.append(wrapped)
    if wrappers[0].model is wrappers[1].model:
        raise ValueError("NAR_DUAL_NATIVE_MODEL_IDENTITY_COLLISION")
    return LoadedDualResearchCandidate(
        winner=wrappers[0], outsider=wrappers[1],
        features=_NAR_FEATURES,
        train_start="2017-01-01", train_end="2021-12-31",
        generated_at=manifest["generatedAt"],
        digest_by_role=hashes,
    )
