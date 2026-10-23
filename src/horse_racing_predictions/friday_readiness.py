"""Offline audit of actual Friday note forecast prerequisites.

Read-only and fail-closed by design. Validates envelopes, hashes, canonical
timestamps, market-feature exclusions and cross-file identity consistency.
NO file, user JSON, note page or self-attestation can grant publication.
No network, scraping, model training, scoring, betting or note mutation.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .odds_free_friday_article import (
    ForecastInputError,
    render_friday_jra_article,
)

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_MARKET = re.compile(
    r"odds|popularity|market[_ -]?(?:rank|share|odds)|betting|"
    r"payout|dividend|オッズ|人気|投票|払戻|配当", re.IGNORECASE
)
_PRIVATE_ONLY = frozenset({
    "jra-van-datalab",
    "jra-van-jv-link",
    "jra-van-data-lab",
})
_MAX_FILE = 4_000_000
_JST = timezone(timedelta(hours=9))


class FridayAuditError(ValueError):
    """Unusable or unverifiable evidence; never a publication permission."""


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise FridayAuditError("duplicate JSON keys are forbidden")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> None:
    raise FridayAuditError("non-finite JSON is forbidden")


def _read_json(path: Path | None) -> tuple[Mapping[str, Any] | None, dict[str, Any]]:
    if path is None:
        return None, {"status": "MISSING", "reason": "no candidate file supplied"}
    try:
        if path.is_symlink() or not path.is_file():
            raise FridayAuditError("source must be a real local file, not a link")
        if path.suffix.lower() != ".json":
            raise FridayAuditError("source must be JSON")
        if path.stat().st_size > _MAX_FILE:
            raise FridayAuditError("input size limit exceeded")
        raw = path.read_bytes()
        if len(raw) > _MAX_FILE:
            raise FridayAuditError("input size limit exceeded")
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate_keys,
                         parse_constant=_reject_nonfinite)
        if not isinstance(doc, Mapping):
            raise FridayAuditError("top-level JSON object required")
        return doc, {"status": "INSPECTED", "sha256": sha256(raw).hexdigest(),
                     "bytes": len(raw)}
    except (OSError, ValueError, UnicodeError) as exc:
        # Never include a potentially sensitive filename, path, JSON value,
        # account name or URL in a published audit report.
        reason = "invalid/unsafe input"
        if isinstance(exc, FridayAuditError):
            reason = str(exc)
        return None, {"status": "REJECTED", "reason": reason}


def _timestamp(text: Any) -> datetime:
    if not isinstance(text, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
        r"(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", text
    ):
        raise FridayAuditError("canonical timestamp with timezone required")
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FridayAuditError("invalid timestamp") from exc
    if value.utcoffset() is None:
        raise FridayAuditError("timezone required")
    return value


def _issue(issue_date: str) -> date:
    try:
        day = date.fromisoformat(issue_date)
        if day.isoformat() != issue_date or day.weekday() != 4:
            raise ValueError("issue is not Friday")
        return day
    except (TypeError, ValueError) as exc:
        raise FridayAuditError("issue must be an actual Friday (YYYY-MM-DD)") from exc


def _source_rights(doc: Mapping[str, Any], issue: date) -> dict[str, Any]:
    provider = str(doc.get("providerId", "")).strip().lower()
    kind = str(doc.get("datasetKind", "")).strip().lower()
    reuse = doc.get("publicationPermission")
    basis = doc.get("permissionBasisUrl")
    observed = doc.get("capturedAt")
    if provider in _PRIVATE_ONLY or "jra-van" in provider or kind == "jv-link":
        if doc.get("separateWrittenPermission") is not True:
            return {"status": "PROHIBITED",
                    "reason": "ordinary JRA-VAN/JV-Link access does not grant dataset republication"}
    if (doc.get("schemaVersion") != 1 or not provider or
            reuse is not True or not isinstance(basis, str) or
            not basis.startswith("https://") or len(basis) > 1000 or
            doc.get("personalUseOnly") is not False):
        return {"status": "REJECTED", "reason": "public reuse permission has no admissible candidate"}
    try:
        when = _timestamp(observed)
    except FridayAuditError:
        return {"status": "REJECTED", "reason": "permission capture timestamp missing"}
    if when.astimezone(_JST).date() > issue:
        return {"status": "REJECTED", "reason": "rights evidence is from after issue Friday"}
    # Still NOT verified: claims from JSON are self-attested.
    return {"status": "REVIEW_REQUIRED",
            "reason": "source terms and any separate grant need independent human review"}


def _race_manifest(doc: Mapping[str, Any], issue: date,
                   forecast: Mapping[str, Any] | None) -> dict[str, Any]:
    ids = doc.get("expectedRaceIds")
    if (doc.get("schemaVersion") != 1 or doc.get("issueDate") != issue.isoformat()
            or not isinstance(ids, list) or not ids or len(ids) > 72
            or any(not isinstance(x, str) or not re.fullmatch(
                r"JRA-[0-9]{8}-[0-9A-Za-z-]{1,24}", x
            ) for x in ids) or len(set(ids)) != len(ids)):
        return {"status": "REJECTED", "reason": "race manifest structure or issue mismatch"}
    try:
        observed = _timestamp(doc.get("observedAt"))
        if observed.astimezone(_JST).date() > issue:
            raise FridayAuditError("late manifest")
    except FridayAuditError:
        return {"status": "REJECTED", "reason": "manifest timestamp is invalid/too late"}
    if forecast is not None and set(forecast.get("expected_race_ids", [])) != set(ids):
        return {"status": "REJECTED", "reason": "schedule/forecast race IDs do not match"}
    return {"status": "REVIEW_REQUIRED", "raceCount": len(ids),
            "reason": "complete actual JRA weekend schedule needs independent verification"}


def _model_manifest(doc: Mapping[str, Any], issue: date,
                    forecast: Mapping[str, Any] | None) -> dict[str, Any]:
    cols = doc.get("featureNames")
    ident = doc.get("modelId")
    artifact = doc.get("artifactSha256")
    if (doc.get("schemaVersion") != 1 or not isinstance(ident, str) or not ident
            or not isinstance(artifact, str) or not _SHA.fullmatch(artifact)
            or not isinstance(cols, list) or not cols
            or not all(isinstance(v, str) and v.strip() for v in cols)
            or len(set(cols)) != len(cols)
            or doc.get("oddsFreeClaim") is not True):
        return {"status": "REJECTED", "reason": "model artifact/features are not documented"}
    if any(_MARKET.search(feature) for feature in cols):
        return {"status": "REJECTED", "reason": "market/popularity feature name detected"}
    try:
        frozen = _timestamp(doc.get("frozenAt"))
        if frozen.astimezone(_JST).date() > issue:
            raise FridayAuditError("model frozen after issue")
    except FridayAuditError:
        return {"status": "REJECTED", "reason": "model frozenAt invalid/too late"}
    if forecast is not None and (forecast.get("model_id") != ident or
                                forecast.get("model_frozen_at") != doc.get("frozenAt")):
        return {"status": "REJECTED", "reason": "model identity/freeze mismatch"}
    return {"status": "REVIEW_REQUIRED", "featureCount": len(cols),
            "reason": "actual model bytes, predictions and feature provenance require independent verification"}


def audit_friday_inputs(
    *, issue_date: str, forecast_json: Path | None = None,
    source_rights_json: Path | None = None,
    race_manifest_json: Path | None = None,
    model_manifest_json: Path | None = None,
) -> dict[str, Any]:
    """Return disclosure-safe structural blockers; NEVER authorize publishing."""
    issue = _issue(issue_date)
    files = {
        "sourceRights": source_rights_json,
        "raceManifest": race_manifest_json,
        "modelManifest": model_manifest_json,
        "forecastInput": forecast_json,
    }
    checks: dict[str, dict[str, Any]] = {}
    documents: dict[str, Mapping[str, Any] | None] = {}
    for key, path in files.items():
        document, checked = _read_json(path)
        checks[key] = checked
        documents[key] = document

    forecast = documents["forecastInput"]
    if forecast is not None:
        try:
            if forecast.get("issue_date") != issue.isoformat():
                raise FridayAuditError("forecast issue differs from requested date")
            article = render_friday_jra_article(forecast)
            checks["forecastInput"] = {
                **checks["forecastInput"], "status": "REVIEW_REQUIRED",
                "raceCount": len(forecast["races"]), "renderSha256": sha256(
                    article.encode("utf-8")
                ).hexdigest(),
                "reason": "article format valid; real horses/scores and source rights unverified",
            }
        except (ForecastInputError, FridayAuditError, KeyError, TypeError) as exc:
            checks["forecastInput"] = {**checks["forecastInput"], "status": "REJECTED",
                "reason": "forecast envelope or point-in-time/odds-free checks failed"}
            forecast = None

    if documents["sourceRights"] is not None:
        checks["sourceRights"].update(_source_rights(documents["sourceRights"], issue))
    if documents["raceManifest"] is not None:
        checks["raceManifest"].update(
            _race_manifest(documents["raceManifest"], issue, forecast))
    if documents["modelManifest"] is not None:
        checks["modelManifest"].update(
            _model_manifest(documents["modelManifest"], issue, forecast))

    return {
        "schemaVersion": 1,
        "issueDate": issue.isoformat(),
        "status": "BLOCKED",
        "publicationAuthorized": False,
        "independentVerifierSatisfied": False,
        "notes": ("This audit only classifies candidate files. A file hash or self-attested "
                  "flag never proves lawful publication rights, completeness, actual "
                  "horse identity, or a pre-frozen predictive model."),
        "checks": checks,
    }
